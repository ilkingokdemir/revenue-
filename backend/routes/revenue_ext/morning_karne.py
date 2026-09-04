"""
Sabah Karnesi (Daily Morning Report Card) — RevenueIQ gap P2.
Sistem her sabah kendi bekçi-zinciri karnesini yöneticilere e-postayla verir:
doluluk, giriş/çıkış, merdiven kademeleri, ikinci-yazıcı alarmları, vitrin sapmaları,
5xx hataları. Resend anahtarı yoksa zarifçe MOCK'lanır (email_outbox).
Collection: daily_report_cards
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import asyncio
import logging

from routes.platform_ext.mailer import send_email

logger = logging.getLogger(__name__)

SEND_HOUR_UTC = 6  # ≈ 09:00 TR


def _now():
    return datetime.now(timezone.utc)


async def compute_ladder_weekly(db, pid: str) -> Dict:
    """İki merdivenin son 7 günde kazandırdığı gelirin dürüst TAHMİNİ."""
    since = (_now() - timedelta(days=7)).isoformat()
    ld_steps = await db.ladder_steps.find(
        {"property_id": pid, "created_at": {"$gte": since}}, {"_id": 0}).to_list(500)
    rp_steps = await db.ramp_steps.find(
        {"property_id": pid, "created_at": {"$gte": since}}, {"_id": 0}).to_list(500)
    reversals = [s for s in ld_steps if s.get("direction") == "up"]
    # kurtarılan: satışla sonuçlanan indirimli geceler (satış anındaki fiyat ~ reversal öncesi kademe)
    recovered = round(sum(float(s.get("rate", 0)) for s in reversals), 2)
    ramp_ups = [s for s in rp_steps if s.get("direction", "up") == "up"]
    approved = [s for s in ramp_ups if s.get("guest_approved")]
    cfg = await db.ramp_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    p = float(cfg.get("step_pct", 5.0)) / 100.0
    uplift = round(sum(float(s.get("rate", 0)) * (1 - 1 / (1 + p)) for s in approved), 2)
    return {"lastday": {"steps": len(ld_steps), "sold_after_discount": len(reversals),
                        "recovered_estimate": recovered},
            "ramp": {"steps": len(ramp_ups), "guest_approved": len(approved),
                     "uplift_estimate": uplift},
            "total_estimate": round(recovered + uplift, 2)}


async def build_karne(db, pid: str) -> Dict:
    now = _now()
    today = now.date().isoformat()
    since24 = (now - timedelta(hours=24)).isoformat()
    total_rooms = 0
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1}):
        total_rooms += int(rt.get("total_rooms", 0))
    active_q = {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]}}
    in_house = await db.bookings.count_documents(
        {**active_q, "check_in": {"$lte": today}, "check_out": {"$gt": today}})
    arrivals = await db.bookings.count_documents({**active_q, "check_in": today})
    departures = await db.bookings.count_documents({**active_q, "check_out": today})
    occ = round(in_house / total_rooms * 100, 1) if total_rooms else 0.0

    ladder_steps = await db.ladder_steps.count_documents(
        {"property_id": pid, "created_at": {"$gte": since24}})
    ladder_reversals = await db.ladder_steps.count_documents(
        {"property_id": pid, "created_at": {"$gte": since24}, "direction": "up"})
    ramp_steps = await db.ramp_steps.count_documents(
        {"property_id": pid, "created_at": {"$gte": since24}})
    sw_open = await db.second_writer_alerts.count_documents(
        {"property_id": pid, "status": "open"})
    sf = await db.storefront_scans.find_one(
        {"property_id": pid}, {"_id": 0, "flagged": 1, "total": 1, "scanned_at": 1},
        sort=[("scanned_at", -1)])
    errors_5xx = await db.system_health_logs.count_documents(
        {"timestamp": {"$gte": since24}, "status_code": {"$gte": 500}})
    hi_notif = await db.notifications.count_documents(
        {"property_id": pid, "priority": "high", "read": False})
    ladder_week = await compute_ladder_weekly(db, pid)
    # Misafir robotları (24s): ön varış e-postası · yorum isteği · OTA A/B kazanan
    pq = {"property_id": pid} if pid != "all" else {}
    arr_n = await db.arrival_reminder_log.count_documents({**pq, "sent_at": {"$gte": since24}})
    rev_n = await db.bookings.count_documents({**pq, "review_request_sent_at": {"$gte": since24, "$regex": "^20"}})
    ab_cfg = await db.booking_widget_config.find_one({**pq, "ota_ab_auto_locked.at": {"$gte": since24}}, {"_id": 0, "ota_ab_auto_locked": 1})
    ab_txt = f", A/B kazanan sabitlendi (Varyant {ab_cfg['ota_ab_auto_locked']['variant']} %{ab_cfg['ota_ab_auto_locked']['pct']:g})" if ab_cfg else ""

    checks = [
        ("Doluluk (bugün)", f"%{occ} — {in_house}/{total_rooms} oda", "ok"),
        ("Giriş / Çıkış (bugün)", f"{arrivals} giriş · {departures} çıkış", "ok"),
        ("Son-gün merdiveni (24s)", f"{ladder_steps} kademe, {ladder_reversals} satışla geri çıkış", "ok"),
        ("Zam merdiveni (24s)", f"{ramp_steps} misafir-onaylı/kanıtlı kademe", "ok"),
        ("Merdiven geliri (7g, tahmini)",
         f"≈{ladder_week['lastday']['recovered_estimate']} kurtarılan + ≈{ladder_week['ramp']['uplift_estimate']} ek gelir",
         "ok"),
        ("İkinci yazıcı alarmı", f"{sw_open} açık alarm", "ok" if sw_open == 0 else "warn"),
        ("Vitrin doğrulaması", (f"{sf['flagged']}/{sf['total']} gün sapmalı" if sf else "henüz tarama yok"),
         "ok" if (not sf or sf.get("flagged", 0) == 0) else "warn"),
        ("5xx hataları (24s)", f"{errors_5xx} hata", "ok" if errors_5xx == 0 else "warn"),
        ("Okunmamış yüksek öncelik bildirim", f"{hi_notif} adet", "ok" if hi_notif < 5 else "warn"),
        ("Misafir robotları (24s)", f"{arr_n} ön varış e-postası · {rev_n} yorum isteği{ab_txt}", "ok"),
    ]
    grade = "A" if all(c[2] == "ok" for c in checks) else ("B" if sum(1 for c in checks if c[2] != "ok") <= 2 else "C")
    return {"date": today, "grade": grade, "occ": occ,
            "ladder_weekly": ladder_week,
            "checks": [{"name": n, "value": v, "status": s} for n, v, s in checks]}


def _karne_html(prop_name: str, k: Dict) -> str:
    color = {"A": "#059669", "B": "#d97706", "C": "#dc2626"}[k["grade"]]
    rows = "".join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'>{'✅' if c['status']=='ok' else '⚠️'} {c['name']}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;font-weight:600'>{c['value']}</td></tr>"
        for c in k["checks"])
    return (f"<div style='font-family:sans-serif;max-width:560px'>"
            f"<h2>🌅 Sabah Karnesi — {prop_name} · {k['date']}</h2>"
            f"<p>Genel not: <span style='font-size:28px;font-weight:800;color:{color}'>{k['grade']}</span></p>"
            f"<table style='width:100%;border-collapse:collapse'>{rows}</table>"
            f"<p style='color:#888;font-size:12px'>Bu karne MyHotelBox bekçi-zinciri tarafından otomatik üretildi.</p></div>")


async def send_karne(db, pid: str, forced: bool = False) -> Dict:
    today = _now().date().isoformat()
    if not forced:
        existing = await db.daily_report_cards.find_one({"property_id": pid, "date": today})
        if existing:
            return {"skipped": "already_sent_today"}
    karne = await build_karne(db, pid)
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
    admins = await db.users.find({"role": {"$in": ["admin", "manager"]},
                                  "is_active": {"$ne": False}},
                                 {"_id": 0, "email": 1, "phone": 1, "karne_whatsapp": 1}).to_list(20)
    html = _karne_html(prop.get("name", pid), karne)
    sent_to = []
    for a in admins:
        if a.get("email"):
            await send_email(db, a["email"],
                             f"🌅 Sabah Karnesi ({karne['grade']}) — {prop.get('name', pid)} · {today}",
                             html, kind="morning_karne", meta={"property_id": pid})
            sent_to.append(a["email"])
    wa_sent = []
    try:
        from routes.marketing.whatsapp_voice import _send_whatsapp_reply
        top = [c for c in karne.get("checks", []) if c.get("status") != "ok"][:3]
        lines = [f"🌅 Sabah Karnesi {today} — {prop.get('name', pid)} · Not: {karne.get('grade')}"]
        lines += [f"• {c['name']}: {c['value']}" for c in top] or ["• Tüm kontroller ✅"]
        text = "\n".join(lines)
        for a in admins:
            phone = (a.get("phone") or "").strip()
            if not phone or a.get("karne_whatsapp") is False:
                continue
            to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone if phone.startswith('+') else '+' + phone}"
            r = await _send_whatsapp_reply(to, text)
            wa_sent.append({"to": phone, "status": r.get("status")})
    except Exception as ex:
        logger.info("karne whatsapp skipped: %s", ex)
    doc = {"id": str(uuid.uuid4()), "property_id": pid, "date": today, "karne": karne,
           "sent_to": sent_to, "whatsapp": wa_sent, "forced": forced, "created_at": _now().isoformat()}
    await db.daily_report_cards.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def morning_karne_loop(db, interval_seconds: int = 1800):
    await asyncio.sleep(240)
    while True:
        try:
            now = _now()
            if now.hour >= SEND_HOUR_UTC:
                for pid in await db.properties.distinct("id"):
                    cfg = await db.morning_karne_config.find_one({"property_id": pid}, {"_id": 0})
                    if cfg and cfg.get("enabled") is False:
                        continue
                    r = await send_karne(db, pid)
                    if not r.get("skipped"):
                        logger.info("Sabah karnesi gönderildi: %s (%s)", pid, r["karne"]["grade"])
        except Exception as ex:
            logger.warning("Morning karne loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_morning_karne_router(db, require_roles):
    router = APIRouter(prefix="/morning-karne", tags=["morning-karne"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}/latest")
    async def latest(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await db.morning_karne_config.find_one({"property_id": pid}, {"_id": 0}) or {"enabled": True}
        card = await db.daily_report_cards.find_one({"property_id": pid}, {"_id": 0},
                                                    sort=[("created_at", -1)])
        preview = await build_karne(db, pid)
        return {"config": {"enabled": cfg.get("enabled", True), "send_hour_utc": SEND_HOUR_UTC},
                "latest": card, "live_preview": preview}

    @router.get("/{pid}/ladder-weekly")
    async def ladder_weekly(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await compute_ladder_weekly(db, pid)

    @router.get("/{pid}/ladder-trend")
    async def ladder_trend(pid: str, days: int = 14, _u: dict = Depends(require_roles(*ROLES))):
        """Merdiven kazançlarının günlük trendi (son N gün, tahmini)."""
        days = max(7, min(days, 30))
        since = (_now() - timedelta(days=days)).isoformat()
        cfg = await db.ramp_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        p = float(cfg.get("step_pct", 5.0)) / 100.0
        buckets = {}
        for off in range(days - 1, -1, -1):
            d = (_now() - timedelta(days=off)).date().isoformat()
            buckets[d] = {"date": d, "recovered": 0.0, "uplift": 0.0}
        async for s in db.ladder_steps.find(
                {"property_id": pid, "created_at": {"$gte": since}, "direction": "up"}, {"_id": 0}):
            d = s["created_at"][:10]
            if d in buckets:
                buckets[d]["recovered"] += float(s.get("rate", 0))
        async for s in db.ramp_steps.find(
                {"property_id": pid, "created_at": {"$gte": since},
                 "guest_approved": True}, {"_id": 0}):
            if s.get("direction", "up") != "up":
                continue
            d = s["created_at"][:10]
            if d in buckets:
                buckets[d]["uplift"] += float(s.get("rate", 0)) * (1 - 1 / (1 + p))
        trend = [{**v, "recovered": round(v["recovered"], 2), "uplift": round(v["uplift"], 2),
                  "total": round(v["recovered"] + v["uplift"], 2)} for v in buckets.values()]
        return {"days": days, "trend": trend}

    @router.get("/{pid}/history")
    async def history(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cards = await db.daily_report_cards.find(
            {"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(30)
        return {"history": cards}

    @router.post("/{pid}/send-now")
    async def send_now(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await send_karne(db, pid, forced=True)

    @router.put("/{pid}/config")
    async def put_config(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        await db.morning_karne_config.update_one(
            {"property_id": pid}, {"$set": {"enabled": bool(data.get("enabled", True))}}, upsert=True)
        return {"ok": True, "enabled": bool(data.get("enabled", True))}

    return router
