"""
Abandoned Booking Recovery (iter 393)
-------------------------------------
Widget captures guest email at the checkout form; if the booking is not
completed within 1 hour, guest gets a reminder email with a small
single-use incentive coupon (COMEBACK-XXXXXX) and a resume link.
Runs hourly-safe via JOB_HANDLERS["abandoned_recovery"].
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import logging
import os
import re
import secrets
import string
import uuid

try:
    import resend
except Exception:
    resend = None

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INCENTIVE_PCT = 5.0


def _now_dt():
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def _gen_coupon() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "COMEBACK-" + "".join(secrets.choice(alphabet) for _ in range(6))


async def _send_email(to_email: str, subject: str, html: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] Abandoned recovery to {to_email}: {subject}")
        return "mock"
    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
            "to": [to_email], "subject": subject, "html": html,
        })
        return "sent"
    except Exception as e:
        logger.warning(f"Abandoned recovery email failed: {e}")
        return "failed"


def _email_html(cart: dict, resume_url: str, coupon: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#292524;">
      <h2 style="color:#0e7490;">Rezervasyonunuz sizi bekliyor{', ' + cart.get('guest_name') if cart.get('guest_name') else ''}!</h2>
      <p>{cart.get('check_in','')} – {cart.get('check_out','')} tarihleri için başlattığınız rezervasyon
         tamamlanmadı. Aşağıdaki kuponla kaldığınız yerden devam edebilirsiniz:</p>
      <div style="background:#ecfeff;border:1px dashed #06b6d4;border-radius:12px;padding:16px;text-align:center;margin:16px 0;">
        <div style="font-size:13px;color:#57534e;">%{int(INCENTIVE_PCT)} indirim kuponu</div>
        <div style="font-size:24px;font-weight:bold;letter-spacing:3px;margin-top:6px;">{coupon}</div>
      </div>
      <p style="text-align:center;">
        <a href="{resume_url}" style="background:#0891b2;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block;">
          Rezervasyonu Tamamla
        </a>
      </p>
      <p style="font-size:12px;color:#78716c;">Fiyatlar ve müsaitlik değişebilir — kupon 7 gün geçerlidir.</p>
    </div>
    """


def create_abandoned_recovery_router(db, require_roles):
    router = APIRouter()

    @router.post("/booking-widget/abandoned/capture")
    async def capture(data: Dict):
        email = (data.get("guest_email") or "").strip().lower()
        sid = (data.get("session_id") or "").strip()
        if not sid or not EMAIL_RE.match(email):
            return {"ok": False}
        doc = {
            "session_id": sid,
            "property_id": data.get("property_id", "default"),
            "guest_email": email,
            "guest_name": (data.get("guest_name") or "").strip(),
            "check_in": data.get("check_in", ""), "check_out": data.get("check_out", ""),
            "room_type_id": data.get("room_type_id", ""),
            "rate": float(data.get("rate") or 0),
            "status": "abandoned", "updated_at": _now(),
        }
        await db.abandoned_carts.update_one(
            {"session_id": sid},
            {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": _now(),
                                           "email_sent": False, "recovered": False}},
            upsert=True)
        return {"ok": True}

    @router.post("/booking-widget/abandoned/convert")
    async def convert(data: Dict):
        sid = (data.get("session_id") or "").strip()
        if not sid:
            return {"ok": False}
        cart = await db.abandoned_carts.find_one({"session_id": sid}, {"_id": 0, "email_sent": 1})
        res = await db.abandoned_carts.update_one(
            {"session_id": sid},
            {"$set": {"status": "converted", "converted_at": _now(),
                      "recovered": bool(cart and cart.get("email_sent"))}})
        return {"ok": res.matched_count > 0}

    async def _recovery_core(property_id: str = "") -> dict:
        now = _now_dt()
        min_age = (now - timedelta(hours=1)).isoformat()
        max_age = (now - timedelta(hours=48)).isoformat()
        q: Dict = {"status": "abandoned", "email_sent": False,
                   "updated_at": {"$lt": min_age, "$gt": max_age}}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        carts = await db.abandoned_carts.find(q, {"_id": 0}).to_list(500)
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        sent = 0
        for c in carts:
            coupon = _gen_coupon()
            await db.direct_conversion_offers.insert_one({
                "id": str(uuid.uuid4()), "coupon_code": coupon,
                "property_id": c.get("property_id", "default"),
                "guest_email": c["guest_email"], "guest_name": c.get("guest_name", ""),
                "discount_pct": INCENTIVE_PCT, "channel": "comeback",
                "source": "abandoned_recovery", "status": "sent",
                "created_at": _now(),
                "valid_until": (now + timedelta(days=7)).isoformat(),
            })
            resume = (f"{base}/book/{c.get('property_id') or 'default'}"
                      f"?coupon={coupon}&checkin={c.get('check_in','')}&checkout={c.get('check_out','')}")
            result = await _send_email(c["guest_email"],
                                       "Rezervasyonunuz yarım kaldı — %5 indirimle tamamlayın",
                                       _email_html(c, resume, coupon))
            await db.abandoned_carts.update_one(
                {"session_id": c["session_id"]},
                {"$set": {"email_sent": True, "email_result": result,
                          "coupon_code": coupon, "emailed_at": _now()}})
            if result in ("sent", "mock"):
                sent += 1
        return {"ok": True, "eligible": len(carts), "emails_sent": sent}

    @router.post("/booking-widget/abandoned/run-recovery")
    async def run_recovery(data: Dict = None,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _recovery_core((data or {}).get("property_id", ""))

    @router.get("/booking-widget/abandoned/stats/{property_id}")
    async def stats(property_id: str, days: int = 30,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (_now_dt() - timedelta(days=min(max(days, 1), 90))).isoformat()
        q: Dict = {"created_at": {"$gte": since}}
        if property_id != "all":
            q["property_id"] = property_id
        rows = await db.abandoned_carts.find(q, {"_id": 0}).sort("updated_at", -1).to_list(1000)
        abandoned = [r for r in rows if r.get("status", "abandoned") == "abandoned"]
        emailed = [r for r in rows if r.get("email_sent")]
        recovered = [r for r in rows if r.get("recovered")]
        return {"property_id": property_id, "total_captured": len(rows),
                "abandoned": len(abandoned), "emailed": len(emailed),
                "recovered": len(recovered),
                "recovery_rate": round(len(recovered) * 100 / max(len(emailed), 1), 1),
                "recent": rows[:20]}

    router.run_recovery_internal = _recovery_core
    return router
