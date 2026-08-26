"""
MRR Hedef Kutlaması — aylık MRR hedefi aşıldığında yöneticilere kutlama
bildirimi + e-postası (ay başına bir kez). Resend yoksa MOCK (email_outbox).
Collections: mrr_celebrations | Hedef: platform_settings {id:'billing'}.mrr_target
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from typing import Dict
import uuid
import asyncio
import logging

from routes.platform_ext.mailer import send_email

logger = logging.getLogger(__name__)

PLAN_PRICES = {"basic": 49, "rms": 99, "cm": 99, "pro": 149, "full": 199}


def _now():
    return datetime.now(timezone.utc)


async def compute_mrr(db) -> float:
    now = _now().isoformat()
    mrr = 0.0
    async for p in db.properties.find(
            {"is_active": {"$ne": False}},
            {"_id": 0, "plan": 1, "suspended": 1, "promo_code": 1, "promo_pct": 1, "promo_until": 1}):
        if p.get("suspended"):
            continue
        price = PLAN_PRICES.get(p.get("plan") or "full", 199)
        if p.get("promo_code") == "WINBACK20" and (p.get("promo_until") or "") > now:
            price = round(price * (1 - (p.get("promo_pct") or 0) / 100), 2)
        mrr += price
    return round(mrr, 2)


async def check_and_celebrate(db) -> Dict:
    settings = await db.platform_settings.find_one({"id": "billing"}, {"_id": 0, "mrr_target": 1}) or {}
    target = float(settings.get("mrr_target") or 0)
    mrr = await compute_mrr(db)
    month = _now().strftime("%Y-%m")
    already = await db.mrr_celebrations.find_one({"month": month}, {"_id": 0})
    result = {"mrr": mrr, "target": target, "month": month,
              "reached": target > 0 and mrr >= target,
              "celebrated_this_month": bool(already)}
    if not result["reached"] or already:
        return result
    pct = round(mrr / target * 100)
    admins = await db.users.find({"role": "admin", "is_active": {"$ne": False}},
                                 {"_id": 0, "email": 1}).to_list(20)
    sent_to = []
    html = (f"<div style='font-family:sans-serif;max-width:520px;text-align:center'>"
            f"<h1 style='font-size:42px;margin:8px'>🎉🏆🎉</h1>"
            f"<h2>Aylık MRR Hedefi AŞILDI!</h2>"
            f"<p style='font-size:22px'><b>£{mrr}</b> / hedef £{target} (%{pct})</p>"
            f"<p>{month} ayı hedefi başarıyla geçildi. Tüm ekibin emeğine sağlık! 🥂</p></div>")
    for a in admins:
        if a.get("email"):
            await send_email(db, a["email"], f"🎉 MRR hedefi aşıldı: £{mrr} / £{target} ({month})",
                             html, kind="mrr_celebration", meta={"month": month})
            sent_to.append(a["email"])
    doc = {"id": str(uuid.uuid4()), "month": month, "mrr": mrr, "target": target,
           "pct": pct, "sent_to": sent_to, "celebrated_at": _now().isoformat()}
    await db.mrr_celebrations.insert_one(dict(doc))
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "property_id": "all", "category": "mrr_celebration",
        "priority": "high", "target_user": "", "target_role": "admin",
        "title": f"🎉 MRR hedefi aşıldı: £{mrr} / £{target} (%{pct})",
        "message": f"{month} ayı geliri hedefi geçti — kutlama e-postası yöneticilere gönderildi. 🥂",
        "read": False, "created_at": _now().isoformat()})
    result.update({"celebrated_this_month": True, "celebration": {k: v for k, v in doc.items() if k != "_id"}})
    logger.info("MRR celebration fired: %s / %s (%s)", mrr, target, month)
    return result


async def mrr_celebration_loop(db, interval_seconds: int = 21600):
    await asyncio.sleep(270)
    while True:
        try:
            await check_and_celebrate(db)
        except Exception as ex:
            logger.warning("MRR celebration loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_mrr_celebration_router(db, require_roles):
    router = APIRouter(prefix="/mrr-celebration", tags=["mrr-celebration"])

    @router.get("/status")
    async def status(_u: dict = Depends(require_roles("admin"))):
        settings = await db.platform_settings.find_one({"id": "billing"}, {"_id": 0, "mrr_target": 1}) or {}
        target = float(settings.get("mrr_target") or 0)
        mrr = await compute_mrr(db)
        month = _now().strftime("%Y-%m")
        history = await db.mrr_celebrations.find({}, {"_id": 0}).sort("celebrated_at", -1).to_list(24)
        return {"mrr": mrr, "target": target, "month": month,
                "pct": round(mrr / target * 100) if target > 0 else None,
                "reached": target > 0 and mrr >= target,
                "celebrated_this_month": any(h["month"] == month for h in history),
                "history": history}

    @router.post("/check")
    async def manual_check(_u: dict = Depends(require_roles("admin"))):
        return await check_and_celebrate(db)

    @router.delete("/reset/{month}")
    async def reset_month(month: str, _u: dict = Depends(require_roles("admin"))):
        """Test amaçlı: ayın kutlama kaydını sil (tekrar tetiklenebilsin)."""
        r = await db.mrr_celebrations.delete_many({"month": month})
        return {"ok": True, "deleted": r.deleted_count}

    return router
