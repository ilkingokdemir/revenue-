"""
Quick Re-booking CTA — completed loop (iter 392)
------------------------------------------------
N days after checkout, guests get a personalized "stay again" email with a
REAL single-use coupon (validated by the booking widget) and a tracked
one-click /rebook/{token} link. Sweep runs manually, via panel, or daily
through the scheduler (JOB_HANDLERS["rebook_sweep"]).
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
import logging
import os
import secrets
import string
import uuid

try:
    import resend
except Exception:
    resend = None

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _gen_coupon() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "REBOOK-" + "".join(secrets.choice(alphabet) for _ in range(6))


def _build_email_html(d: dict, book_url: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#292524;">
      <h2 style="color:#0e7490;">Sizi tekrar ağırlamak isteriz, {d.get('guest_name') or 'değerli misafirimiz'}!</h2>
      <p>Son konaklamanızın üzerinden biraz zaman geçti. Bir sonraki rezervasyonunuzda geçerli
         size özel indirim kuponunuz hazır:</p>
      <div style="background:#ecfeff;border:1px dashed #06b6d4;border-radius:12px;padding:18px;text-align:center;margin:18px 0;">
        <div style="font-size:13px;color:#57534e;">%{int(d.get('loyalty_discount_pct', 10))} indirim kuponu</div>
        <div style="font-size:26px;font-weight:bold;letter-spacing:3px;margin-top:6px;">{d.get('coupon_code','')}</div>
      </div>
      <p style="text-align:center;">
        <a href="{book_url}" style="background:#0891b2;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block;">
          Tek Tıkla Tekrar Rezervasyon
        </a>
      </p>
      <p style="font-size:12px;color:#78716c;">Kupon tek kullanımlıktır ve {d.get('coupon_valid_until','')[:10]} tarihine kadar geçerlidir.</p>
    </div>
    """


async def _send_email(to_email: str, subject: str, html: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] Rebook offer to {to_email}: {subject}")
        return "mock"
    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
            "to": [to_email], "subject": subject, "html": html,
        })
        return "sent"
    except Exception as e:
        logger.warning(f"Rebook email send failed: {e}")
        return "failed"


def create_rebook_router(db, require_roles):
    router = APIRouter()

    async def _sweep_core(property_id: str = "", days_after: int = 30,
                          discount_pct: float = 10.0) -> dict:
        target = (_today() - timedelta(days=days_after)).isoformat()
        q: Dict = {"check_out": {"$regex": f"^{target}"}, "status": "checked_out"}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(5000)
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        queued, sent = 0, 0
        for b in bookings:
            if await db.rebook_dispatches.find_one({"booking_id": b["id"]}, {"_id": 0, "id": 1}):
                continue
            token = secrets.token_urlsafe(20)
            coupon = _gen_coupon()
            valid_until = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
            # real single-use coupon — validated/redeemed by the booking widget
            await db.direct_conversion_offers.insert_one({
                "id": str(uuid.uuid4()), "coupon_code": coupon,
                "property_id": b.get("property_id", ""),
                "guest_email": (b.get("guest_email") or "").lower(),
                "guest_name": b.get("guest_name", ""),
                "discount_pct": float(discount_pct),
                "channel": "rebook", "source": "rebook_sweep",
                "status": "sent", "created_at": _now(), "valid_until": valid_until,
            })
            dispatch = {
                "id": str(uuid.uuid4()), "token": token,
                "property_id": b.get("property_id", ""), "booking_id": b["id"],
                "guest_email": (b.get("guest_email") or "").lower(),
                "guest_name": b.get("guest_name", ""),
                "last_room_type": b.get("room_type", ""),
                "last_check_in": b.get("check_in", ""),
                "last_check_out": b.get("check_out", ""),
                "loyalty_discount_pct": float(discount_pct),
                "coupon_code": coupon, "coupon_valid_until": valid_until,
                "channel": "email", "scheduled_for": _now(),
                "status": "pending", "clicked": False, "clicked_at": "",
            }
            if dispatch["guest_email"]:
                book_url = f"{base}/book/{dispatch['property_id'] or 'default'}?coupon={coupon}&rebook={token}"
                result = await _send_email(
                    dispatch["guest_email"],
                    f"%{int(discount_pct)} indirimle tekrar bekliyoruz — kuponunuz içeride",
                    _build_email_html(dispatch, book_url))
                dispatch["status"] = "sent" if result in ("sent", "mock") else "failed"
                dispatch["email_result"] = result
                if dispatch["status"] == "sent":
                    sent += 1
            await db.rebook_dispatches.insert_one(dispatch)
            dispatch.pop("_id", None)
            queued += 1
        return {"ok": True, "scanned": len(bookings), "queued": queued,
                "emails_sent": sent, "target_date": target}

    @router.post("/rebook/sweep")
    async def sweep(data: Optional[Dict] = None,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        return await _sweep_core(
            property_id=body.get("property_id", ""),
            days_after=int(body.get("days_after_checkout") or 30),
            discount_pct=float(body.get("loyalty_discount_pct") or 10.0))

    @router.get("/rebook/{property_id}/dispatches")
    async def list_disp(property_id: str, days: int = 60,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.rebook_dispatches.find(
            {"property_id": property_id, "scheduled_for": {"$gte": since}}, {"_id": 0}
        ).sort("scheduled_for", -1).to_list(500)
        clicked = sum(1 for r in rows if r.get("clicked"))
        redeemed = 0
        codes = [r["coupon_code"] for r in rows if r.get("coupon_code")]
        if codes:
            redeemed = await db.direct_conversion_offers.count_documents(
                {"coupon_code": {"$in": codes}, "status": "redeemed"})
        return {"items": rows, "count": len(rows), "clicked": clicked,
                "click_rate": round(clicked * 100 / max(len(rows), 1), 1),
                "redeemed": redeemed,
                "conversion_rate": round(redeemed * 100 / max(len(rows), 1), 1)}

    @router.post("/rebook/dispatches/{dispatch_id}/clicked")
    async def click(dispatch_id: str):
        await db.rebook_dispatches.update_one(
            {"id": dispatch_id}, {"$set": {"clicked": True, "clicked_at": _now()}})
        return {"ok": True}

    @router.get("/rebook/token/{token}")
    async def resolve_token(token: str):
        d = await db.rebook_dispatches.find_one({"token": token}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Invalid token")
        await db.rebook_dispatches.update_one(
            {"token": token}, {"$set": {"clicked": True, "clicked_at": _now()}})
        return {
            "property_id": d["property_id"],
            "guest_email": d["guest_email"],
            "guest_name": d["guest_name"],
            "preselect_room_type": d.get("last_room_type", ""),
            "loyalty_discount_pct": d.get("loyalty_discount_pct", 0),
            "coupon_code": d.get("coupon_code", ""),
        }

    router.run_sweep_internal = _sweep_core
    return router
