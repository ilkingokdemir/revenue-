"""
Cancel-Save Autopilot (iter 409) — automatically sends retention vouchers to
high cancellation-risk bookings before they cancel. Max 1 offer per booking.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional

from fastapi import APIRouter, Depends

from routes.ai.ai_predictions import _score_cancel_risk, _days_between
from routes.ai.upsell_autopilot import _send_email

logger = logging.getLogger(__name__)

RISK_THRESHOLD = 65  # high band
DISCOUNT_PCT = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _email_html(guest_name: str, check_in: str, voucher: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#292524;">
      <h2 style="color:#0e7490;">Sizi ağırlamak için sabırsızlanıyoruz 💙</h2>
      <p>Merhaba {guest_name or 'değerli misafirimiz'},</p>
      <p>{check_in} tarihli rezervasyonunuz yaklaşıyor. Konaklamanıza küçük bir jest eklemek istedik:</p>
      <div style="background:#ecfeff;border:1px dashed #06b6d4;border-radius:12px;padding:18px;margin:18px 0;text-align:center;">
        <div style="font-size:13px;color:#57534e;">Konaklama ekstralarında geçerli</div>
        <div style="font-size:22px;font-weight:bold;color:#0e7490;">%{DISCOUNT_PCT} indirim kuponu</div>
        <div style="font-size:16px;font-weight:bold;letter-spacing:2px;margin-top:6px;">{voucher}</div>
      </div>
      <p style="font-size:13px;">Planlarınızda değişiklik mi var? İptal etmeden önce bize yazın —
      tarih değişikliğini ücretsiz yapalım.</p>
    </div>
    """


def create_cancel_save_router(db, require_roles):
    router = APIRouter()

    async def _sweep_core(property_id: str = "") -> dict:
        today = date.today()
        start = (today + timedelta(days=3)).isoformat()
        horizon = (today + timedelta(days=45)).isoformat()
        pq: Dict = {} if not property_id or property_id == "all" else {"property_id": property_id}
        bookings = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "pending_payment"]},
             "check_in": {"$gte": start, "$lte": horizon},
             "save_offer_sent_at": {"$exists": False}},
            {"_id": 0}).to_list(2000)

        # avg rate for price-deviation signal
        past = await db.bookings.find(
            {**pq, "status": {"$in": ["checked_out", "checked_in"]}},
            {"_id": 0, "total_price": 1, "check_in": 1, "check_out": 1}).limit(200).to_list(200)
        rev = sum(float(p.get("total_price") or 0) for p in past)
        nts = sum(max(1, _days_between(p.get("check_in", ""), p.get("check_out", ""))) for p in past)
        avg_rate = rev / nts if nts else 0

        scanned, sent = len(bookings), 0
        for b in bookings:
            guest = await db.guest_profiles.find_one({"id": b.get("guest_id")}, {"_id": 0}) or {}
            r = _score_cancel_risk(b, guest, avg_rate)
            if r["score"] < RISK_THRESHOLD:
                continue
            voucher = f"STAY-{b['id'][:6].upper()}"
            email_result = "no_email"
            if b.get("guest_email"):
                email_result = await _send_email(
                    b["guest_email"],
                    "Konaklamanıza özel bir jest hazırladık 🎁",
                    _email_html(b.get("guest_name", ""), b.get("check_in", ""), voucher))
            now = _now()
            await db.save_offers.insert_one({
                "id": voucher, "booking_id": b["id"], "property_id": b.get("property_id"),
                "guest_name": b.get("guest_name"), "guest_email": b.get("guest_email"),
                "discount_pct": DISCOUNT_PCT, "risk_score": r["score"],
                "status": "sent" if email_result in ("sent", "mock") else "queued",
                "voucher_code": voucher, "source": "autopilot",
                "email_result": email_result, "created_at": now, "created_by": "autopilot"})
            await db.bookings.update_one(
                {"id": b["id"]},
                {"$set": {"save_offer_sent_at": now, "save_offer_code": voucher}})
            sent += 1
        return {"ok": True, "scanned": scanned, "offers_sent": sent,
                "threshold": RISK_THRESHOLD}

    @router.post("/ai-predictions/cancel-save/run")
    async def run_sweep(data: Optional[Dict] = None,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _sweep_core((data or {}).get("property_id", ""))

    @router.get("/ai-predictions/cancel-save/stats/{property_id}")
    async def stats(property_id: str, days: int = 30,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"source": "autopilot", "created_at": {"$gte": since}}
        if property_id != "all":
            q["property_id"] = property_id
        offers = await db.save_offers.find(q, {"_id": 0}).to_list(2000)
        saved = pending = lost = 0
        saved_revenue = 0.0
        today = date.today().isoformat()
        for o in offers:
            b = await db.bookings.find_one({"id": o["booking_id"]},
                                           {"_id": 0, "status": 1, "check_in": 1, "total_price": 1})
            if not b:
                continue
            if b.get("status") == "cancelled":
                lost += 1
            elif b.get("status") in ("checked_in", "checked_out") or (b.get("check_in") or "") <= today:
                saved += 1
                saved_revenue += float(b.get("total_price") or 0)
            else:
                pending += 1
        total = len(offers)
        return {"property_id": property_id, "days": days, "offers_sent": total,
                "saved": saved, "pending": pending, "cancelled_anyway": lost,
                "saved_revenue": round(saved_revenue, 2),
                "save_rate": round(saved * 100 / max(saved + lost, 1), 1)}

    router.run_cancel_save_internal = _sweep_core
    return router
