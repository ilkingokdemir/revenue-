"""
Direct Booking Conversion Engine (iter 375)
============================================
OTA misafirlerini direct booking'e çevirme motoru:
- Checkout anında OTA kaynaklı booking tespit edilir
- Misafire özel kupon kodu üretilir (DIRECT-XXXXXX)
- Promo e-posta gönderilir (Resend; key yoksa mock)
- Kupon redeem edilince komisyon tasarrufu hesaplanır

Endpoints
---------
  GET  /api/direct-conversion/settings
  PUT  /api/direct-conversion/settings
  GET  /api/direct-conversion/offers
  GET  /api/direct-conversion/stats
  POST /api/direct-conversion/scan               — checked_out OTA bookingleri tara
  POST /api/direct-conversion/trigger/{booking_id}
  POST /api/direct-conversion/redeem             — public (booking widget kullanır)
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import os
import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    import resend
except Exception:
    resend = None

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "enabled": True,
    "discount_pct": 15,
    "validity_days": 90,
    "min_booking_value": 0,
    "email_subject": "Bir dahaki konaklamanızda %{discount} indirim — direkt rezervasyon yapın!",
}

# OTA komisyon oranları (tasarruf tahmini için) — ota_commission.py ile uyumlu
_COMMISSION_RATES = {
    "booking_com": 0.15, "expedia": 0.18, "airbnb": 0.03,
    "agoda": 0.17, "trip_com": 0.15,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_coupon() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "DIRECT-" + "".join(secrets.choice(alphabet) for _ in range(6))


def _detect_ota_channel(bk: dict) -> Optional[str]:
    src = (bk.get("source") or "").lower()
    if src.startswith("ota:"):
        return src.replace("ota:", "")
    ch = (bk.get("channel") or "").lower()
    if ch in _COMMISSION_RATES:
        return ch
    return None


async def _get_settings(db) -> dict:
    row = await db.direct_conversion_settings.find_one({"_id": "global"}) or {}
    row.pop("_id", None)
    return {**DEFAULT_SETTINGS, **row}


def _build_email_html(offer: dict, hotel_name: str) -> str:
    return f"""
    <div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:32px;background:#faf9f7;border:1px solid #e7e2da;">
      <h2 style="color:#1c1917;margin:0 0 8px;">Bizi tercih ettiğiniz için teşekkürler, {offer['guest_name']}!</h2>
      <p style="color:#57534e;font-size:15px;line-height:1.6;">
        {hotel_name}'de konaklamanızdan memnun kaldıysanız, bir dahaki gelişinizde
        <strong>web sitemizden direkt rezervasyon yaparak %{offer['discount_pct']} indirim</strong> kazanın.
      </p>
      <div style="background:#065f46;color:#fff;text-align:center;padding:20px;margin:24px 0;border-radius:8px;">
        <div style="font-size:12px;letter-spacing:2px;opacity:.8;">KUPON KODUNUZ</div>
        <div style="font-size:28px;font-weight:bold;letter-spacing:3px;margin-top:6px;">{offer['coupon_code']}</div>
      </div>
      <p style="color:#78716c;font-size:13px;">
        Geçerlilik: {offer['valid_until'][:10]} tarihine kadar · Sadece direkt rezervasyonlarda geçerlidir.
      </p>
    </div>
    """


async def _send_offer_email(db, offer: dict) -> str:
    """Returns email_status: 'sent' | 'mocked' | 'failed'."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] Direct conversion offer to {offer['guest_email']}: {offer['coupon_code']}")
        return "mocked"

    hotel_name = "Otelimiz"
    try:
        b = await db.branding_settings.find_one({}, {"_id": 0, "app_name": 1})
        if b and b.get("app_name"):
            hotel_name = b["app_name"]
    except Exception:
        pass

    subject = f"%{offer['discount_pct']} indirim kuponunuz hazır — {hotel_name}"
    html = _build_email_html(offer, hotel_name)
    try:
        sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
        resend.emails.send({
            "from": sender,
            "to": [offer["guest_email"]],
            "subject": subject,
            "html": html,
        })
        return "sent"
    except Exception as e:
        logger.warning(f"Direct conversion email failed: {e}")
        return "failed"


async def process_checkout_conversion(db, booking: dict) -> Optional[dict]:
    """Checkout hook — OTA booking ise kupon üret + email gönder. Idempotent."""
    try:
        channel = _detect_ota_channel(booking)
        if not channel:
            return None
        guest_email = booking.get("guest_email")
        if not guest_email:
            return None
        settings = await _get_settings(db)
        if not settings.get("enabled"):
            return None
        gross = float(booking.get("total_price") or 0)
        if gross < float(settings.get("min_booking_value") or 0):
            return None
        booking_id = booking.get("id")
        existing = await db.direct_conversion_offers.find_one(
            {"booking_id": booking_id}, {"_id": 0, "id": 1})
        if existing:
            return None

        valid_until = (datetime.now(timezone.utc)
                       + timedelta(days=int(settings["validity_days"]))).isoformat()
        rate = _COMMISSION_RATES.get(channel, 0.15)
        offer = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "property_id": booking.get("property_id"),
            "guest_name": booking.get("guest_name", "-"),
            "guest_email": guest_email,
            "channel": channel,
            "coupon_code": _gen_coupon(),
            "discount_pct": int(settings["discount_pct"]),
            "valid_until": valid_until,
            "status": "sent",
            "source_booking_value": gross,
            "commission_saved_estimate": round(gross * rate, 2),
            "created_at": _now(),
        }
        offer["email_status"] = await _send_offer_email(db, offer)
        await db.direct_conversion_offers.insert_one({**offer})
        offer.pop("_id", None)

        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "type": "direct_conversion_offer",
            "title": f"🎯 Direct booking kuponu gönderildi: {offer['guest_name']}",
            "message": f"{channel.upper()} misafiri · {offer['coupon_code']} · %{offer['discount_pct']} indirim",
            "property_id": booking.get("property_id"),
            "target_role": "manager",
            "priority": "low",
            "read": False,
            "created_by": "Direct Conversion Engine",
            "created_at": _now(),
        })
        return offer
    except Exception as e:
        logger.warning(f"process_checkout_conversion failed: {e}")
        return None


class SettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    discount_pct: Optional[int] = None
    validity_days: Optional[int] = None
    min_booking_value: Optional[float] = None


class RedeemRequest(BaseModel):
    coupon_code: str
    booking_value: float = 0
    guest_email: Optional[str] = None


def create_direct_conversion_router(db, require_roles):
    router = APIRouter(prefix="/direct-conversion", tags=["direct-conversion"])

    @router.get("/settings")
    async def get_settings(_: dict = Depends(require_roles("admin", "manager"))):
        return await _get_settings(db)

    @router.put("/settings")
    async def update_settings(body: SettingsUpdate,
                              _: dict = Depends(require_roles("admin", "manager"))):
        upd = {k: v for k, v in body.model_dump().items() if v is not None}
        if "discount_pct" in upd and not (1 <= upd["discount_pct"] <= 50):
            raise HTTPException(400, "discount_pct 1..50 aralığında olmalı")
        if "validity_days" in upd and not (7 <= upd["validity_days"] <= 365):
            raise HTTPException(400, "validity_days 7..365 aralığında olmalı")
        if upd:
            upd["updated_at"] = _now()
            await db.direct_conversion_settings.update_one(
                {"_id": "global"}, {"$set": upd}, upsert=True)
        return await _get_settings(db)

    @router.get("/offers")
    async def list_offers(status: Optional[str] = None, limit: int = 100,
                          _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if status:
            q["status"] = status
        rows = await db.direct_conversion_offers.find(q, {"_id": 0}) \
            .sort("created_at", -1).to_list(min(limit, 500))
        return {"total": len(rows), "items": rows}

    @router.get("/stats")
    async def stats(_: dict = Depends(require_roles("admin", "manager"))):
        offers = await db.direct_conversion_offers.find({}, {"_id": 0}).to_list(10000)
        now = _now()
        sent = len(offers)
        redeemed = [o for o in offers if o.get("status") == "redeemed"]
        expired = [o for o in offers if o.get("status") == "sent" and o.get("valid_until", "9") < now]
        active = sent - len(redeemed) - len(expired)
        commission_saved = round(sum(float(o.get("commission_saved_actual") or 0) for o in redeemed), 2)
        potential_saving = round(sum(float(o.get("commission_saved_estimate") or 0)
                                     for o in offers if o.get("status") == "sent"), 2)
        direct_revenue = round(sum(float(o.get("redeemed_booking_value") or 0) for o in redeemed), 2)
        by_channel: dict = {}
        for o in offers:
            ch = o.get("channel", "?")
            row = by_channel.setdefault(ch, {"channel": ch, "sent": 0, "redeemed": 0})
            row["sent"] += 1
            if o.get("status") == "redeemed":
                row["redeemed"] += 1
        return {
            "sent": sent,
            "active": active,
            "redeemed": len(redeemed),
            "expired": len(expired),
            "conversion_rate_pct": round(len(redeemed) / sent * 100, 1) if sent else 0,
            "direct_revenue": direct_revenue,
            "commission_saved": commission_saved,
            "potential_saving": potential_saving,
            "by_channel": sorted(by_channel.values(), key=lambda x: x["sent"], reverse=True),
        }

    @router.post("/scan")
    async def scan(limit: int = 200,
                   _: dict = Depends(require_roles("admin", "manager"))):
        """Checked-out OTA bookingleri tara, kupon gönderilmemişleri işle."""
        settings = await _get_settings(db)
        if not settings.get("enabled"):
            return {"scanned": 0, "offers_created": 0, "items": [],
                    "reason": "engine_disabled"}
        q = {"status": "checked_out",
             "guest_email": {"$nin": [None, ""]},
             "$or": [{"source": {"$regex": "^ota:"}},
                     {"channel": {"$in": list(_COMMISSION_RATES.keys())}}]}
        bookings = await db.bookings.find(q, {"_id": 0}).sort("updated_at", -1).to_list(limit)
        offered_ids = {o["booking_id"] async for o in db.direct_conversion_offers.find(
            {}, {"_id": 0, "booking_id": 1})}
        created = []
        for bk in bookings:
            if bk.get("id") in offered_ids:
                continue
            offer = await process_checkout_conversion(db, bk)
            if offer:
                created.append({"booking_id": bk.get("id"),
                                "coupon_code": offer["coupon_code"],
                                "guest_email": offer["guest_email"],
                                "email_status": offer["email_status"]})
        return {"scanned": len(bookings), "offers_created": len(created), "items": created}

    @router.post("/trigger/{booking_id}")
    async def trigger(booking_id: str,
                      _: dict = Depends(require_roles("admin", "manager"))):
        bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not bk:
            raise HTTPException(404, "Booking bulunamadı")
        offer = await process_checkout_conversion(db, bk)
        if not offer:
            existing = await db.direct_conversion_offers.find_one(
                {"booking_id": booking_id}, {"_id": 0})
            if existing:
                return {"ok": False, "reason": "already_offered", "offer": existing}
            raise HTTPException(400, "Uygun değil (OTA kaynaklı değil, email yok veya engine kapalı)")
        return {"ok": True, "offer": offer}

    @router.post("/redeem")
    async def redeem(body: RedeemRequest):
        """Booking widget / front desk kupon doğrulama + kullanım."""
        code = body.coupon_code.strip().upper()
        offer = await db.direct_conversion_offers.find_one({"coupon_code": code}, {"_id": 0})
        if not offer:
            raise HTTPException(404, "Kupon bulunamadı")
        if offer.get("status") == "redeemed":
            raise HTTPException(400, "Kupon daha önce kullanılmış")
        if offer.get("valid_until", "9") < _now():
            await db.direct_conversion_offers.update_one(
                {"coupon_code": code}, {"$set": {"status": "expired"}})
            raise HTTPException(400, "Kupon süresi dolmuş")

        rate = _COMMISSION_RATES.get(offer.get("channel", ""), 0.15)
        saved = round(float(body.booking_value or 0) * rate, 2)
        discount_amount = round(float(body.booking_value or 0) * offer["discount_pct"] / 100, 2)
        await db.direct_conversion_offers.update_one(
            {"coupon_code": code},
            {"$set": {"status": "redeemed",
                      "redeemed_at": _now(),
                      "redeemed_booking_value": float(body.booking_value or 0),
                      "redeemed_by_email": body.guest_email,
                      "commission_saved_actual": saved}})
        return {"ok": True, "coupon_code": code,
                "discount_pct": offer["discount_pct"],
                "discount_amount": discount_amount,
                "commission_saved": saved}

    return router
