"""
Upsell Auto-Pilot (iter 396) — automatically emails branded upsell offers to
high-propensity upcoming arrivals (score >= threshold), closing the last
manual loop in the automation stack.
"""
import os
import logging
import uuid
import secrets
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

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

# (unit price GBP, per_night?)
CATEGORY_PRICE = {
    "room_upgrade": (40.0, True),
    "late_checkout": (25.0, False),
    "breakfast": (15.0, True),
    "spa": (20.0, True),
    "transport": (45.0, False),
}


def _offer_price(cat: str, nights: int) -> float:
    unit, per_night = CATEGORY_PRICE.get(cat, (25.0, False))
    return round(unit * (max(nights, 1) if per_night else 1), 2)


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


def _email_html(guest_name: str, check_in: str, cat_key: str, price: float = 0,
                accept_url: str = "", seg_profile: dict = None) -> str:
    title, pitch = CATEGORY_TR.get(cat_key, ("Özel Teklif", ""))
    greeting = (seg_profile or {}).get("greeting", "Merhaba")
    intro = (seg_profile or {}).get("intro",
             f"{check_in} tarihli konaklamanız yaklaşıyor. Size özel hazırladığımız teklif:")
    closing = (seg_profile or {}).get("closing", "")
    closing_html = f'<p style="font-size:13px;color:#78716c;">{closing}</p>' if closing else ""
    btn = (f"""<p style="text-align:center;margin:20px 0 6px;">
        <a href="{accept_url}" style="background:#b45309;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block;">
          Tek Tıkla Kabul Et — £{price * 0.9:.0f}
        </a></p>
        <p style="text-align:center;font-size:12px;color:#b45309;">48 saat içinde kabul ederseniz %10 erken kabul indirimi (normal fiyat £{price:.0f})</p>""" if accept_url else
        '<p style="font-size:13px;">Resepsiyona yanıt vererek veya check-in sırasında talep edebilirsiniz.</p>')
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#292524;">
      <h2 style="color:#b45309;">Konaklamanıza özel: {title}</h2>
      <p>{greeting} {guest_name or 'değerli misafirimiz'},</p>
      <p>{intro}</p>
      <div style="background:#fffbeb;border:1px dashed #f59e0b;border-radius:12px;padding:18px;margin:18px 0;">
        <div style="font-size:16px;font-weight:bold;">{title} — £{price:.0f}</div>
        <div style="font-size:13px;color:#57534e;margin-top:6px;">{pitch}</div>
      </div>
      {btn}
      {closing_html}
    </div>
    """


EARLY_BIRD_PCT = 10.0
EARLY_BIRD_HOURS = 48


def _early_bird(o: dict):
    """Returns (final_price, discount_active, expires_at_iso)."""
    price = float(o.get("price") or 0)
    created = o.get("created_at") or ""
    try:
        created_dt = datetime.fromisoformat(created)
    except Exception:
        return price, False, ""
    expires = created_dt + timedelta(hours=EARLY_BIRD_HOURS)
    if datetime.now(timezone.utc) < expires:
        return round(price * (1 - EARLY_BIRD_PCT / 100), 2), True, expires.isoformat()
    return price, False, expires.isoformat()


def create_upsell_autopilot_router(db, require_roles):
    router = APIRouter()

    async def _autopilot_core(property_id: str = "", min_score: int = None,
                              days_ahead: int = None) -> dict:
        from routes.platform_ext.automation_settings import get_params
        cfg = await get_params(db, "upsell_autopilot", {"min_score": 60, "days_ahead": 14})
        min_score = int(min_score) if min_score is not None else int(cfg["min_score"])
        days_ahead = int(days_ahead) if days_ahead is not None else int(cfg["days_ahead"])
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
        by_segment: Dict[str, int] = {}
        from routes.guests.segments import segment_allows, apply_segment_boost, SEGMENT_OFFER_PROFILES
        for b in bookings:
            if b["id"] in offered:
                continue
            if not await segment_allows(db, b.get("guest_email"), "upsell_autopilot"):
                continue
            guest = await db.guest_profiles.find_one(
                {"id": b.get("guest_id")}, {"_id": 0}) or {}
            if not guest and b.get("guest_email"):
                guest = await db.guest_profiles.find_one(
                    {"email": (b["guest_email"] or "").lower()}, {"_id": 0}) or {}
            segment = guest.get("segment") or "standart"
            seg_profile = SEGMENT_OFFER_PROFILES.get(segment)
            r = _score_upsell_propensity(b, guest)
            _, cat, top_score = apply_segment_boost(r["scores"], segment)
            if top_score < min_score:
                skipped_low += 1
                continue
            nights = max(int(b.get("nights") or 1), 1)
            price = _offer_price(cat, nights)
            token = secrets.token_urlsafe(20)
            base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
            accept_url = f"{base}/offer/{token}" if base else ""
            email_result = "no_email"
            if b.get("guest_email"):
                title, _ = CATEGORY_TR.get(cat, ("Özel Teklif", ""))
                email_result = await _send_email(
                    b["guest_email"],
                    f"Konaklamanıza özel teklif: {title}",
                    _email_html(b.get("guest_name", ""), b.get("check_in", ""), cat, price,
                                accept_url, seg_profile))
            await db.upsell_offers.insert_one({
                "id": f"UP-{b['id'][:6].upper()}-{cat[:3].upper()}",
                "booking_id": b["id"],
                "property_id": b.get("property_id"),
                "category": cat,
                "score": top_score,
                "segment": segment,
                "price": price,
                "accept_token": token,
                "status": "sent" if email_result in ("sent", "mock") else "queued",
                "source": "autopilot",
                "email_result": email_result,
                "created_at": _now(),
                "created_by": "autopilot",
            })
            by_cat[cat] = by_cat.get(cat, 0) + 1
            by_segment[segment] = by_segment.get(segment, 0) + 1
            sent += 1
        return {"ok": True, "scanned": scanned, "offers_sent": sent,
                "skipped_low_score": skipped_low, "by_category": by_cat,
                "by_segment": by_segment,
                "min_score": min_score, "window_days": days_ahead}

    @router.post("/ai-predictions/upsell/autopilot/run")
    async def run_autopilot(data: Optional[Dict] = None,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        return await _autopilot_core(
            property_id=body.get("property_id", ""),
            min_score=int(body["min_score"]) if body.get("min_score") else None,
            days_ahead=int(body["days_ahead"]) if body.get("days_ahead") else None)

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

    @router.get("/public/upsell-offer/{token}")
    async def public_offer(token: str):
        o = await db.upsell_offers.find_one({"accept_token": token}, {"_id": 0})
        if not o:
            raise HTTPException(404, "Offer not found")
        if not o.get("viewed_at"):
            await db.upsell_offers.update_one(
                {"accept_token": token}, {"$set": {"viewed_at": _now()}})
        b = await db.bookings.find_one({"id": o["booking_id"]}, {"_id": 0}) or {}
        title, pitch = CATEGORY_TR.get(o.get("category"), ("Özel Teklif", ""))
        prop = await db.properties.find_one({"id": o.get("property_id")}, {"_id": 0, "name": 1}) or {}
        final_price, discount_active, expires_at = _early_bird(o)
        since30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        social_q: Dict = {"category": o.get("category"), "status": "accepted",
                          "accepted_at": {"$gte": since30}}
        if o.get("property_id"):
            social_q["property_id"] = o["property_id"]
        social_count = await db.upsell_offers.count_documents(social_q)
        return {"status": o.get("status"), "category": o.get("category"),
                "title": title, "pitch": pitch, "price": o.get("price", 0),
                "final_price": final_price, "discount_active": discount_active,
                "discount_pct": EARLY_BIRD_PCT if discount_active else 0,
                "expires_at": expires_at, "social_count": social_count,
                "guest_name": b.get("guest_name", ""), "check_in": b.get("check_in", ""),
                "check_out": b.get("check_out", ""), "room_type": b.get("room_type_name", ""),
                "hotel_name": prop.get("name", "")}

    @router.post("/public/upsell-offer/{token}/accept")
    async def public_accept(token: str):
        o = await db.upsell_offers.find_one({"accept_token": token}, {"_id": 0})
        if not o:
            raise HTTPException(404, "Offer not found")
        if o.get("status") == "accepted":
            return {"ok": True, "status": "accepted", "already": True}
        if o.get("status") == "declined":
            raise HTTPException(400, "Offer already declined")
        now = _now()
        price, discount_active, _ = _early_bird(o)
        title, _t = CATEGORY_TR.get(o.get("category"), ("Özel Teklif", ""))
        await db.upsell_offers.update_one(
            {"accept_token": token},
            {"$set": {"status": "accepted", "accepted_at": now, "accepted_by": "guest-selfservice",
                      "charged_amount": price, "early_bird_applied": discount_active}})
        await db.folio_items.insert_one({
            "id": str(uuid.uuid4()), "booking_id": o["booking_id"],
            "property_id": o.get("property_id"),
            "type": "charge", "category": "upsell",
            "description": f"Upsell (autopilot) · {title}" + (" · erken kabul -%10" if discount_active else ""),
            "quantity": 1, "unit_price": price, "amount": price,
            "currency": "GBP", "created_at": now, "created_by": "guest-selfservice"})
        await db.upsell_log.insert_one({
            "id": str(uuid.uuid4()), "booking_id": o["booking_id"],
            "type": o.get("category"), "revenue": price,
            "accepted_at": now, "accepted_by": "guest-selfservice"})
        return {"ok": True, "status": "accepted", "amount": price}

    @router.post("/public/upsell-offer/{token}/decline")
    async def public_decline(token: str):
        o = await db.upsell_offers.find_one({"accept_token": token}, {"_id": 0})
        if not o:
            raise HTTPException(404, "Offer not found")
        if o.get("status") not in ("accepted",):
            await db.upsell_offers.update_one(
                {"accept_token": token},
                {"$set": {"status": "declined", "declined_at": _now()}})
        return {"ok": True, "status": "declined"}

    router.run_autopilot_internal = _autopilot_core
    return router
