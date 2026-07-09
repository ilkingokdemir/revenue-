"""
Upsell Auto-Pilot (iter 396) — automatically emails branded upsell offers to
high-propensity upcoming arrivals (score >= threshold), closing the last
manual loop in the automation stack.
"""
import os
import logging
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional

from fastapi import APIRouter, Depends

from routes.ai.ai_predictions import _score_upsell_propensity

try:
    import resend
except ImportError:
    resend = None

logger = logging.getLogger(__name__)

CATEGORY_TR = {
    "room_upgrade": ("Oda Yükseltme", "Konaklamanızı bir üst sınıf odayla taçlandırın."),
    "late_checkout": ("Geç Çıkış", "Gününüzü aceleye getirmeyin — saat 14:00'e kadar odanız sizin."),
    "breakfast": ("Kahvaltı Paketi", "Güne zengin açık büfe kahvaltıyla başlayın."),
    "spa": ("Spa & Wellness", "Kendinize bir mola verin — spa seansınız hazır."),
    "transport": ("Havalimanı Transferi", "Kapıdan kapıya konforlu özel transfer."),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _send_email(to_email: str, subject: str, html: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] Upsell autopilot to {to_email}: {subject}")
        return "mock"
    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
            "to": [to_email], "subject": subject, "html": html,
        })
        return "sent"
    except Exception as e:
        logger.warning(f"Upsell autopilot email failed: {e}")
        return "failed"


def _email_html(guest_name: str, check_in: str, cat_key: str) -> str:
    title, pitch = CATEGORY_TR.get(cat_key, ("Özel Teklif", ""))
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#292524;">
      <h2 style="color:#b45309;">Konaklamanıza özel: {title}</h2>
      <p>Merhaba {guest_name or 'değerli misafirimiz'},</p>
      <p>{check_in} tarihli konaklamanız yaklaşıyor. Size özel hazırladığımız teklif:</p>
      <div style="background:#fffbeb;border:1px dashed #f59e0b;border-radius:12px;padding:18px;margin:18px 0;">
        <div style="font-size:16px;font-weight:bold;">{title}</div>
        <div style="font-size:13px;color:#57534e;margin-top:6px;">{pitch}</div>
      </div>
      <p style="font-size:13px;">Resepsiyona yanıt vererek veya check-in sırasında talep edebilirsiniz.</p>
    </div>
    """


def create_upsell_autopilot_router(db, require_roles):
    router = APIRouter()

    async def _autopilot_core(property_id: str = "", min_score: int = 60,
                              days_ahead: int = 14) -> dict:
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        q: Dict = {"status": {"$in": ["confirmed", "checked_in", "pending_payment"]},
                   "check_in": {"$gte": today, "$lte": horizon}}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(2000)

        offered = set()
        if bookings:
            offs = await db.upsell_offers.find(
                {"booking_id": {"$in": [b["id"] for b in bookings]}},
                {"_id": 0, "booking_id": 1}).to_list(5000)
            offered = {o["booking_id"] for o in offs}

        scanned, sent, skipped_low = len(bookings), 0, 0
        by_cat: Dict[str, int] = {}
        for b in bookings:
            if b["id"] in offered:
                continue
            guest = await db.guest_profiles.find_one(
                {"id": b.get("guest_id")}, {"_id": 0}) or {}
            r = _score_upsell_propensity(b, guest)
            if r["top_score"] < min_score:
                skipped_low += 1
                continue
            cat = r["top_recommendation"]
            email_result = "no_email"
            if b.get("guest_email"):
                title, _ = CATEGORY_TR.get(cat, ("Özel Teklif", ""))
                email_result = await _send_email(
                    b["guest_email"],
                    f"Konaklamanıza özel teklif: {title}",
                    _email_html(b.get("guest_name", ""), b.get("check_in", ""), cat))
            await db.upsell_offers.insert_one({
                "id": f"UP-{b['id'][:6].upper()}-{cat[:3].upper()}",
                "booking_id": b["id"],
                "property_id": b.get("property_id"),
                "category": cat,
                "score": r["top_score"],
                "status": "sent" if email_result in ("sent", "mock") else "queued",
                "source": "autopilot",
                "email_result": email_result,
                "created_at": _now(),
                "created_by": "autopilot",
            })
            by_cat[cat] = by_cat.get(cat, 0) + 1
            sent += 1
        return {"ok": True, "scanned": scanned, "offers_sent": sent,
                "skipped_low_score": skipped_low, "by_category": by_cat,
                "min_score": min_score, "window_days": days_ahead}

    @router.post("/ai-predictions/upsell/autopilot/run")
    async def run_autopilot(data: Optional[Dict] = None,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        return await _autopilot_core(
            property_id=body.get("property_id", ""),
            min_score=int(body.get("min_score") or 60),
            days_ahead=int(body.get("days_ahead") or 14))

    @router.get("/ai-predictions/upsell/autopilot/stats/{property_id}")
    async def stats(property_id: str, days: int = 30,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"source": "autopilot", "created_at": {"$gte": since}}
        if property_id != "all":
            q["property_id"] = property_id
        rows = await db.upsell_offers.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
        by_cat: Dict[str, int] = {}
        for r in rows:
            by_cat[r.get("category", "?")] = by_cat.get(r.get("category", "?"), 0) + 1
        return {"property_id": property_id, "days": days, "total_sent": len(rows),
                "by_category": by_cat, "recent": rows[:50]}

    router.run_autopilot_internal = _autopilot_core
    return router
