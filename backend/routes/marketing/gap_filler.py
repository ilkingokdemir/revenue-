"""
AI Boşluk Doldurma Kampanyaları (Gap Filler) — önümüzdeki günlerde düşük
doluluklu tarih pencerelerini bulur, otomatik promo kodu üretir (promo_codes)
ve hazır e-posta + WhatsApp kampanya taslağı çıkarır. Aktive edilince mevcut
Campaigns modülüne (db.campaigns) e-posta taslağı olarak düşer.
Collections: gap_campaigns, gap_filler_config (+ promo_codes, campaigns)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
import uuid
import random
import string
import logging

logger = logging.getLogger(__name__)

DEFAULT_CFG = {"occ_threshold": 40, "discount_pct": 15, "days_ahead": 45, "min_window_days": 2}


def _iso():
    return datetime.now(timezone.utc).isoformat()


async def _get_cfg(db, property_id: str) -> Dict:
    doc = await db.gap_filler_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
    return {**DEFAULT_CFG, **{k: doc[k] for k in DEFAULT_CFG if k in doc}}


def _promo_code() -> str:
    return "GAP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


def _tr_date(ds: str) -> str:
    months = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
              "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    d = ddate.fromisoformat(ds)
    return f"{d.day} {months[d.month]}"


def _copy(hotel_name: str, start: str, end: str, pct: int, code: str) -> Dict:
    window = f"{_tr_date(start)} – {_tr_date(end)}"
    subject = f"⚡ Sadece bu tarihlere özel: %{pct} indirim ({window})"
    body = (f"Merhaba {{guest_name}},\n\n"
            f"{hotel_name} olarak {window} tarihleri arasında konaklamalarda "
            f"size özel %{pct} indirim sunuyoruz!\n\n"
            f"🎟 Promosyon kodunuz: {code}\n"
            f"Web sitemizden rezervasyon yaparken kodu girmeniz yeterli. "
            f"Kontenjan sınırlıdır — kod yalnızca bu tarih aralığında ve stoklarla sınırlı sayıda geçerlidir.\n\n"
            f"Sizi yeniden ağırlamak dileğiyle,\n{hotel_name} Ekibi")
    wa = (f"⚡ {hotel_name} — {window} arasına özel %{pct} indirim! "
          f"Kod: {code} · Web sitemizden rezervasyonda geçerli. Kontenjan sınırlı! 🏨")
    return {"email_subject": subject, "email_body": body, "wa_message": wa}


async def _low_occ_windows(db, property_id: str, cfg: Dict):
    total = 0
    for rt in await db.room_types.find({"property_id": property_id}, {"_id": 0, "total_rooms": 1}).to_list(50):
        total += int(rt.get("total_rooms", 0))
    if total <= 0:
        return []
    today = ddate.today()
    horizon = today + timedelta(days=int(cfg["days_ahead"]))
    bookings = await db.bookings.find({
        "property_id": property_id, "status": {"$in": ["confirmed", "checked_in"]},
        "check_in": {"$lte": horizon.isoformat()}, "check_out": {"$gt": today.isoformat()},
    }, {"_id": 0, "check_in": 1, "check_out": 1}).to_list(8000)
    occ = {}
    for b in bookings:
        try:
            ci, co = ddate.fromisoformat(b["check_in"][:10]), ddate.fromisoformat(b["check_out"][:10])
        except Exception:
            continue
        d = max(ci, today)
        while d < co and d <= horizon:
            occ[d.isoformat()] = occ.get(d.isoformat(), 0) + 1
            d += timedelta(days=1)
    windows, cur = [], None
    d = today + timedelta(days=3)  # çok yakın tarihleri atla (kampanya süresi kalsın)
    while d <= horizon:
        pct = round(occ.get(d.isoformat(), 0) / total * 100, 1)
        if pct < cfg["occ_threshold"]:
            if cur is None:
                cur = {"start": d, "end": d, "occs": [pct]}
            else:
                cur["end"] = d
                cur["occs"].append(pct)
        else:
            if cur:
                windows.append(cur)
                cur = None
        d += timedelta(days=1)
    if cur:
        windows.append(cur)
    return [{"start_date": w["start"].isoformat(), "end_date": w["end"].isoformat(),
             "days": len(w["occs"]), "avg_occ_pct": round(sum(w["occs"]) / len(w["occs"]), 1)}
            for w in windows if len(w["occs"]) >= int(cfg["min_window_days"])]


async def run_gap_filler(db, property_id: str = "") -> Dict:
    pids = [property_id] if property_id and property_id != "all" else await db.properties.distinct("id")
    created, details = 0, []
    for pid in pids:
        cfg = await _get_cfg(db, pid)
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        hotel_name = prop.get("name", pid)
        windows = await _low_occ_windows(db, pid, cfg)
        pid_created = 0
        for w in windows:
            exists = await db.gap_campaigns.find_one({
                "property_id": pid, "status": {"$ne": "dismissed"},
                "start_date": {"$lte": w["end_date"]}, "end_date": {"$gte": w["start_date"]}}, {"_id": 0})
            if exists:
                continue
            code = _promo_code()
            pct = int(cfg["discount_pct"])
            promo = {"id": str(uuid.uuid4()), "property_id": pid, "code": code,
                     "kind": "percent", "amount": pct,
                     "valid_from": ddate.today().isoformat(), "valid_to": w["end_date"],
                     "max_uses": 20, "used": 0, "min_nights": 1,
                     "applies_to_products": [], "active": True,
                     "created_at": _iso(), "source": "gap_filler"}
            await db.promo_codes.insert_one(dict(promo))
            copy = _copy(hotel_name, w["start_date"], w["end_date"], pct, code)
            camp = {"id": str(uuid.uuid4()), "property_id": pid,
                    "start_date": w["start_date"], "end_date": w["end_date"],
                    "days": w["days"], "avg_occ_pct": w["avg_occ_pct"],
                    "discount_pct": pct, "promo_code": code, "promo_id": promo["id"],
                    **copy, "status": "draft", "created_at": _iso()}
            await db.gap_campaigns.insert_one(dict(camp))
            created += 1
            pid_created += 1
        if pid_created:
            details.append({"property_id": pid, "campaigns": pid_created})
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "property_id": pid,
                "category": "gap_filler", "priority": "normal",
                "target_user": "", "target_role": "manager",
                "title": f"🪄 {pid_created} boşluk doldurma kampanyası hazır",
                "message": "Düşük doluluklu tarihler için promo kodlu kampanya taslakları oluşturuldu. Gap Filler panelinden aktive edin.",
                "read": False, "created_at": _iso()})
    return {"properties_scanned": len(pids), "campaigns_created": created, "details": details}


def create_gap_filler_router(db, require_roles):
    router = APIRouter(prefix="/gap-filler")
    router.run_internal = lambda pid="": run_gap_filler(db, pid)

    @router.get("/{property_id}")
    async def list_campaigns(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        rows = await db.gap_campaigns.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
        for r in rows:
            promo = await db.promo_codes.find_one({"id": r.get("promo_id", "")}, {"_id": 0, "used": 1})
            r["promo_used"] = int(promo.get("used", 0)) if promo else 0
        cfg = await _get_cfg(db, property_id if property_id != "all" else "all")
        return {"campaigns": rows, "config": cfg,
                "summary": {"draft": sum(1 for r in rows if r["status"] == "draft"),
                            "activated": sum(1 for r in rows if r["status"] == "activated"),
                            "redemptions": sum(r["promo_used"] for r in rows)}}

    @router.put("/{property_id}/config")
    async def put_config(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = {}
        for k, lo, hi in (("occ_threshold", 10, 80), ("discount_pct", 5, 50),
                          ("days_ahead", 14, 120), ("min_window_days", 1, 14)):
            if k in data and data[k] is not None:
                upd[k] = max(lo, min(int(data[k]), hi))
        if upd:
            await db.gap_filler_config.update_one({"property_id": property_id},
                                                  {"$set": upd}, upsert=True)
        return {"ok": True, "config": await _get_cfg(db, property_id)}

    @router.post("/{property_id}/scan")
    async def manual_scan(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_gap_filler(db, property_id)

    @router.post("/campaigns/{campaign_id}/activate")
    async def activate(campaign_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        c = await db.gap_campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Kampanya bulunamadı")
        if c["status"] == "activated":
            return {"ok": True, "already": True}
        email_campaign = {"id": str(uuid.uuid4()), "property_id": c["property_id"],
                          "name": f"Gap Filler · {c['start_date']} → {c['end_date']} (%{c['discount_pct']})",
                          "channel": "email", "status": "draft",
                          "subject": c["email_subject"], "message": c["email_body"],
                          "segment": {}, "scheduled_at": "", "sent_at": "",
                          "total_recipients": 0, "total_sent": 0, "total_delivered": 0,
                          "total_opened": 0, "created_by": "Gap Filler AI",
                          "created_at": _iso(), "source": "gap_filler",
                          "gap_campaign_id": campaign_id}
        await db.campaigns.insert_one(dict(email_campaign))
        await db.promo_codes.update_one({"id": c["promo_id"]}, {"$set": {"active": True}})
        await db.gap_campaigns.update_one({"id": campaign_id}, {"$set": {
            "status": "activated", "activated_at": _iso(),
            "activated_by": current_user.get("name", ""),
            "email_campaign_id": email_campaign["id"]}})
        return {"ok": True, "email_campaign_id": email_campaign["id"]}

    @router.post("/campaigns/{campaign_id}/dismiss")
    async def dismiss(campaign_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        c = await db.gap_campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Kampanya bulunamadı")
        await db.promo_codes.update_one({"id": c["promo_id"]}, {"$set": {"active": False}})
        await db.gap_campaigns.update_one({"id": campaign_id}, {"$set": {
            "status": "dismissed", "dismissed_at": _iso()}})
        return {"ok": True}

    return router
