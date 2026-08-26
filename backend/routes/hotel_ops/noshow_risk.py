"""
No-Show Riski Tahmini — yarınki girişler risk faktörleriyle puanlanır,
yüksek riskliler önceden işaretlenir ve günlük bildirim gönderilir.
Faktörler: iletişim eksikliği, ödeme durumu, OTA kanalı, 1 gece, misafirin
geçmiş no-show'u, çok eski rezervasyon. Collection: yok (canlı hesap) + notifications.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

OTA_CHANNELS = {"booking", "booking.com", "expedia", "airbnb", "ota", "agoda"}

DEFAULT_WEIGHTS = {"no_email": 15, "no_phone": 15, "unpaid": 25, "ota": 10,
                   "one_night": 10, "past_noshow": 30, "old_booking": 5}
DEFAULT_THRESHOLDS = {"high": 50, "medium": 30}

WEIGHT_LABELS = {"no_email": "E-posta yok", "no_phone": "Telefon yok",
                 "unpaid": "Ödeme alınmamış", "ota": "OTA kanalı",
                 "one_night": "Tek gece", "past_noshow": "Geçmiş no-show (adet başı)",
                 "old_booking": "30+ gün önce rezerve"}


async def get_risk_model(db, pid: str):
    doc = await db.risk_model_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    weights = {**DEFAULT_WEIGHTS, **(doc.get("weights") or {})}
    th = {**DEFAULT_THRESHOLDS, **(doc.get("thresholds") or {})}
    return weights, th


def _now():
    return datetime.now(timezone.utc)


async def score_arrivals(db, pid: str, day: str) -> List[Dict]:
    W, TH = await get_risk_model(db, pid)
    arrivals = await db.bookings.find(
        {"property_id": pid, "check_in": day,
         "status": {"$nin": ["cancelled", "no_show", "checked_in"]}},
        {"_id": 0}).to_list(200)
    out = []
    for b in arrivals:
        score, reasons = 0, []
        if not (b.get("guest_email") or "").strip():
            score += W["no_email"]
            reasons.append("E-posta yok")
        if not (b.get("guest_phone") or "").strip():
            score += W["no_phone"]
            reasons.append("Telefon yok")
        if (b.get("payment_status") or "pending") in ("pending", "unpaid", ""):
            score += W["unpaid"]
            reasons.append("Ödeme alınmamış")
        if (b.get("channel") or "").lower() in OTA_CHANNELS:
            score += W["ota"]
            reasons.append("OTA kanalı")
        if int(b.get("nights", 1) or 1) <= 1:
            score += W["one_night"]
            reasons.append("Tek gece")
        # misafirin geçmiş no-show'u
        guest_q = []
        if (b.get("guest_email") or "").strip():
            guest_q.append({"guest_email": b["guest_email"]})
        if (b.get("guest_name") or "").strip():
            guest_q.append({"guest_name": b["guest_name"]})
        if guest_q:
            past_ns = await db.bookings.count_documents(
                {"property_id": pid, "status": "no_show", "$or": guest_q,
                 "id": {"$ne": b.get("id")}})
            if past_ns > 0:
                score += W["past_noshow"]
                reasons.append(f"Geçmişte {past_ns} no-show")
        try:
            created = datetime.fromisoformat(b.get("created_at", "").replace("Z", "+00:00"))
            if (_now() - created).days > 30:
                score += W["old_booking"]
                reasons.append("30+ gün önce rezerve")
        except Exception:
            pass
        level = "high" if score >= TH["high"] else ("medium" if score >= TH["medium"] else "low")
        out.append({"booking_id": b.get("id"), "booking_ref": b.get("booking_ref"),
                    "guest_name": b.get("guest_name"), "room_type": b.get("room_type"),
                    "channel": b.get("channel", "direct"), "nights": b.get("nights", 1),
                    "total_price": b.get("total_price", 0),
                    "payment_status": b.get("payment_status", "pending"),
                    "score": min(score, 100), "level": level, "reasons": reasons,
                    "suggestion": ("Bugün telefonla teyit alın + ön provizyon isteyin" if level == "high"
                                   else "Teyit SMS/e-postası gönderin" if level == "medium"
                                   else "İzleme yeterli")})
    out.sort(key=lambda x: -x["score"])
    return out


async def record_snapshot(db, pid: str, day: str, items) -> None:
    if not items:
        return
    avg = round(sum(i["score"] for i in items) / len(items), 1)
    await db.noshow_risk_snapshots.update_one(
        {"property_id": pid, "date": day},
        {"$set": {"avg_score": avg, "total": len(items),
                  "high": sum(1 for i in items if i["level"] == "high"),
                  "medium": sum(1 for i in items if i["level"] == "medium"),
                  "updated_at": _now().isoformat()}}, upsert=True)


async def noshow_risk_loop(db, interval_seconds: int = 3600):
    await asyncio.sleep(330)
    while True:
        try:
            now = _now()
            if 14 <= now.hour <= 18:  # öğleden sonra tek sefer bildirim penceresi
                tomorrow = (now.date() + timedelta(days=1)).isoformat()
                for pid in await db.properties.distinct("id"):
                    risks = await score_arrivals(db, pid, tomorrow)
                    await record_snapshot(db, pid, tomorrow, risks)
                    already = await db.notifications.find_one(
                        {"property_id": pid, "category": "noshow_risk",
                         "meta_date": tomorrow})
                    if already:
                        continue
                    high = [r for r in risks if r["level"] == "high"]
                    if not high:
                        continue
                    names = ", ".join(r["guest_name"] or r["booking_ref"] for r in high[:3])
                    await db.notifications.insert_one({
                        "id": str(uuid.uuid4()), "property_id": pid, "category": "noshow_risk",
                        "meta_date": tomorrow, "priority": "high",
                        "target_user": "", "target_role": "manager",
                        "title": f"⚠️ Yarın {len(high)} yüksek no-show riski",
                        "message": f"{names}… — bugün teyit araması + ön provizyon önerilir. Detay: No-Show Riski paneli.",
                        "read": False, "created_at": now.isoformat()})
        except Exception as ex:
            logger.warning("No-show risk loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_noshow_risk_router(db, require_roles):
    router = APIRouter(prefix="/noshow-risk", tags=["noshow-risk"])
    ROLES = ("admin", "manager", "receptionist")

    @router.get("/{pid}")
    async def risks(pid: str, day: str = "", _u: dict = Depends(require_roles(*ROLES))):
        target = day or (_now().date() + timedelta(days=1)).isoformat()
        items = await score_arrivals(db, pid, target)
        await record_snapshot(db, pid, target, items)
        conf = {c["booking_id"]: c async for c in db.noshow_confirmations.find(
            {"property_id": pid}, {"_id": 0})}
        deps = {d["booking_id"]: d["status"] async for d in db.deposit_requests.find(
            {"property_id": pid}, {"_id": 0, "booking_id": 1, "status": 1})}
        for i in items:
            c = conf.get(i["booking_id"])
            i["confirmation_sent"] = bool(c)
            i["confirmation_channel"] = (c or {}).get("channel")
            i["confirmation_response"] = (c or {}).get("response")
            i["deposit_status"] = deps.get(i["booking_id"])
        return {"date": target, "items": items,
                "summary": {"total": len(items),
                            "high": sum(1 for i in items if i["level"] == "high"),
                            "medium": sum(1 for i in items if i["level"] == "medium")}}

    @router.get("/{pid}/trend")
    async def trend(pid: str, days: int = 14, _u: dict = Depends(require_roles(*ROLES))):
        """Günlük risk skoru ortalamaları + haftalık ortalama."""
        days = max(7, min(days, 30))
        # bugünün ve yarının snapshot'ı yoksa canlı hesapla (grafik boş kalmasın)
        for off in (0, 1):
            d = (_now().date() + timedelta(days=off)).isoformat()
            if not await db.noshow_risk_snapshots.find_one({"property_id": pid, "date": d}):
                await record_snapshot(db, pid, d, await score_arrivals(db, pid, d))
        snaps = await db.noshow_risk_snapshots.find(
            {"property_id": pid}, {"_id": 0}).sort("date", -1).to_list(days)
        snaps.reverse()
        last7 = snaps[-7:]
        weekly_avg = round(sum(s["avg_score"] for s in last7) / len(last7), 1) if last7 else 0
        return {"trend": snaps, "weekly_avg": weekly_avg,
                "weekly_high_total": sum(s.get("high", 0) for s in last7)}

    @router.get("/{pid}/model")
    async def get_model(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        W, TH = await get_risk_model(db, pid)
        return {"weights": W, "thresholds": TH, "labels": WEIGHT_LABELS}

    @router.put("/{pid}/model")
    async def put_model(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {}
        if isinstance(data.get("weights"), dict):
            upd["weights"] = {k: max(0, min(int(v), 60))
                              for k, v in data["weights"].items() if k in DEFAULT_WEIGHTS}
        if isinstance(data.get("thresholds"), dict):
            th = {k: max(10, min(int(v), 100))
                  for k, v in data["thresholds"].items() if k in DEFAULT_THRESHOLDS}
            if th.get("high", 50) <= th.get("medium", 30):
                raise HTTPException(422, "Yüksek eşik, orta eşikten büyük olmalı")
            upd["thresholds"] = th
        if upd:
            await db.risk_model_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        W, TH = await get_risk_model(db, pid)
        return {"ok": True, "weights": W, "thresholds": TH}

    @router.post("/{pid}/model/reset")
    async def reset_model(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.risk_model_config.delete_many({"property_id": pid})
        return {"ok": True, "weights": DEFAULT_WEIGHTS, "thresholds": DEFAULT_THRESHOLDS}

    @router.get("/rsvp/{token}")
    async def rsvp(token: str, answer: str = "coming"):
        """Misafir teyit yanıtı — PUBLIC (e-postadaki butonlardan gelir)."""
        from fastapi.responses import HTMLResponse
        conf = await db.noshow_confirmations.find_one({"rsvp_token": token}, {"_id": 0})
        if not conf:
            return HTMLResponse("<h3 style='font-family:sans-serif;text-align:center;margin-top:80px'>Bağlantı geçersiz veya süresi dolmuş.</h3>", status_code=404)
        ans = "coming" if answer != "not_coming" else "not_coming"
        await db.noshow_confirmations.update_one(
            {"rsvp_token": token},
            {"$set": {"response": ans, "responded_at": _now().isoformat()}})
        if ans == "not_coming":
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "property_id": conf["property_id"],
                "category": "noshow_rsvp", "priority": "high",
                "target_user": "", "target_role": "manager",
                "title": "🚫 Misafir GELEMİYORUM dedi",
                "message": f"Rezervasyon {conf.get('booking_id','')} için misafir gelmeyeceğini bildirdi — odayı satışa açmayı değerlendirin.",
                "read": False, "created_at": _now().isoformat()})
        msg = ("Teşekkürler! Rezervasyonunuz teyit edildi, sizi ağırlamayı sabırsızlıkla bekliyoruz. 🏨"
               if ans == "coming" else
               "Bilgilendirdiğiniz için teşekkürler. Rezervasyonunuzla ilgili ekibimiz sizinle iletişime geçebilir.")
        return HTMLResponse(f"<div style='font-family:sans-serif;text-align:center;margin-top:80px;max-width:420px;margin-left:auto;margin-right:auto'>"
                            f"<div style='font-size:48px'>{'✅' if ans=='coming' else '📩'}</div><h2>{msg}</h2></div>")

    @router.post("/{pid}/confirm/{booking_id}")
    async def send_confirmation(pid: str, booking_id: str, request: Request, data: Dict = None,
                                u: dict = Depends(require_roles(*ROLES))):
        """Tek tıkla teyit mesajı — e-posta (Geliyorum/Gelemiyorum butonlu) veya SMS (MOCK)."""
        from routes.platform_ext.mailer import send_email
        data = data or {}
        channel = data.get("channel", "email")
        b = await db.bookings.find_one({"id": booking_id, "property_id": pid}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        token = str(uuid.uuid4())
        base = str(request.base_url).rstrip("/")
        yes_url = f"{base}/api/noshow-risk/rsvp/{token}?answer=coming"
        no_url = f"{base}/api/noshow-risk/rsvp/{token}?answer=not_coming"
        msg = (f"Sayın {b.get('guest_name','Misafirimiz')}, {b.get('check_in')} tarihli "
               f"{prop.get('name','otelimiz')} rezervasyonunuzu ({b.get('booking_ref','')}) teyit etmenizi rica ederiz.")
        status = "mocked"
        if channel == "email":
            if not (b.get("guest_email") or "").strip():
                raise HTTPException(422, "Misafirin e-postası yok — SMS deneyin")
            status = await send_email(
                db, b["guest_email"], f"Rezervasyon teyidi rica ederiz — {b.get('booking_ref','')}",
                (f"<div style='font-family:sans-serif;max-width:520px'><p>{msg}</p>"
                 f"<p style='margin:22px 0'>"
                 f"<a href='{yes_url}' style='background:#059669;color:#fff;padding:12px 22px;border-radius:999px;text-decoration:none;font-weight:700;margin-right:10px'>✅ Geliyorum</a>"
                 f"<a href='{no_url}' style='background:#dc2626;color:#fff;padding:12px 22px;border-radius:999px;text-decoration:none;font-weight:700'>❌ Gelemiyorum</a></p>"
                 f"<p style='color:#888;font-size:12px'>Tek tıkla yanıtlayın — resepsiyonumuz anında bilgilenir.</p></div>"),
                kind="noshow_confirm", meta={"booking_id": booking_id})
        else:
            if not (b.get("guest_phone") or "").strip():
                raise HTTPException(422, "Misafirin telefonu yok — e-posta deneyin")
            await db.sms_outbox.insert_one({
                "id": str(uuid.uuid4()), "to": b["guest_phone"],
                "body": f"{msg} Geliyorum: {yes_url} | Gelemiyorum: {no_url}",
                "kind": "noshow_confirm", "booking_id": booking_id,
                "status": "mocked", "created_at": _now().isoformat()})
        await db.noshow_confirmations.update_one(
            {"property_id": pid, "booking_id": booking_id},
            {"$set": {"channel": channel, "status": status, "rsvp_token": token,
                      "response": None,
                      "sent_by": u.get("name") or u.get("email", ""),
                      "sent_at": _now().isoformat()}}, upsert=True)
        return {"ok": True, "channel": channel, "status": status, "rsvp_token": token}

    return router
