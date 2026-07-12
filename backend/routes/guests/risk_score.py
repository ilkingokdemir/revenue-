"""
Guest Risk Score (iter 406) — flags risky guests (no-show / cancellation /
chargeback history) on upcoming arrivals so front desk can request deposits.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
import logging
import os
import uuid

from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

from routes.ai.upsell_autopilot import _send_email

logger = logging.getLogger(__name__)


def _stripe(base: str) -> StripeCheckout:
    return StripeCheckout(api_key=os.environ.get("STRIPE_API_KEY"),
                          webhook_url=f"{base}/api/webhook/stripe")


def _level(score: int) -> str:
    return "high" if score >= 60 else "medium" if score >= 30 else "low"


def _action(level: str) -> str:
    return {"high": "Ön ödeme veya kart pre-auth zorunlu tutun",
            "medium": "Depozito / kart bilgisi isteyin",
            "low": "Standart işlem"}[level]


def create_guest_risk_router(db, require_roles):
    router = APIRouter()

    async def _risk_for(email: str) -> dict:
        email = (email or "").lower()
        if not email:
            return {"score": 0, "level": "low", "reasons": [], "action": _action("low")}
        hist = await db.bookings.find(
            {"guest_email": email},
            {"_id": 0, "id": 1, "status": 1, "no_show_collected": 1, "no_show_charged": 1}).to_list(500)
        no_shows = sum(1 for b in hist if b.get("status") == "no_show")
        cancels = sum(1 for b in hist if b.get("status") == "cancelled")
        completed = sum(1 for b in hist if b.get("status") in ("checked_out", "completed"))
        unpaid_ns = sum(1 for b in hist if b.get("no_show_charged") and not b.get("no_show_collected"))
        bids = [b["id"] for b in hist]
        chargebacks = await db.chargebacks.count_documents({"booking_id": {"$in": bids}}) if bids else 0

        score = min(no_shows * 30, 60) + min(cancels * 10, 30) + min(chargebacks * 30, 60) + min(unpaid_ns * 10, 20)
        score = max(0, min(100, score - min(completed * 5, 20)))
        reasons = []
        if no_shows:
            reasons.append(f"{no_shows} no-show")
        if cancels:
            reasons.append(f"{cancels} iptal")
        if chargebacks:
            reasons.append(f"{chargebacks} chargeback")
        if unpaid_ns:
            reasons.append(f"{unpaid_ns} tahsil edilememiş no-show ücreti")
        if completed:
            reasons.append(f"{completed} sorunsuz konaklama")
        lvl = _level(score)
        return {"score": score, "level": lvl, "reasons": reasons, "action": _action(lvl),
                "history": {"no_shows": no_shows, "cancellations": cancels,
                            "chargebacks": chargebacks, "completed_stays": completed}}

    @router.get("/guests/risk/arrivals/{property_id}")
    async def risk_arrivals(property_id: str, days_ahead: int = 14,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        days_ahead = min(max(days_ahead, 1), 60)
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        pq = {} if property_id == "all" else {"property_id": property_id}
        arrivals = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "pending_payment", "pending"]},
             "check_in": {"$gte": today, "$lte": horizon}},
            {"_id": 0, "id": 1, "booking_ref": 1, "guest_name": 1, "guest_email": 1,
             "check_in": 1, "check_out": 1, "total_price": 1, "room_type_name": 1,
             "deposit_requested": 1, "deposit_paid": 1}).to_list(1000)
        rows = []
        cache = {}
        for b in arrivals:
            email = (b.get("guest_email") or "").lower()
            if email not in cache:
                cache[email] = await _risk_for(email)
            r = cache[email]
            rows.append({**{k: b.get(k) for k in ["id", "booking_ref", "guest_name", "guest_email",
                                                  "check_in", "check_out", "total_price", "room_type_name",
                                                  "deposit_requested", "deposit_paid"]},
                         **r})
        rows.sort(key=lambda x: -x["score"])
        summary = {"high": 0, "medium": 0, "low": 0}
        for r in rows:
            summary[r["level"]] += 1
        value_at_risk = round(sum(float(r.get("total_price") or 0) for r in rows if r["level"] != "low"), 2)
        return {"property_id": property_id, "days_ahead": days_ahead,
                "rows": rows[:100], "summary": summary, "value_at_risk": value_at_risk}

    @router.get("/guests/risk/{guest_email}")
    async def guest_risk(guest_email: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return {"guest_email": guest_email.lower(), **(await _risk_for(guest_email))}

    @router.post("/guests/risk/{booking_id}/request-deposit")
    async def request_deposit(booking_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await _request_deposit_core(booking_id, current_user.get("email", "system"))

    async def _request_deposit_core(booking_id: str, actor: str) -> dict:
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        if b.get("deposit_requested"):
            return {"ok": True, "already": True}
        total = float(b.get("total_price") or 0)
        nights = max(int(b.get("nights") or 1), 1)
        amount = round(total / nights, 2) if total > 0 else 50.0
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        try:
            sess = await _stripe(base).create_checkout_session(CheckoutSessionRequest(
                amount=float(amount), currency="gbp",
                success_url=f"{base}/?deposit=paid&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{base}/?deposit=cancelled",
                metadata={"booking_id": booking_id, "purpose": "risk_deposit"}))
        except Exception as e:
            raise HTTPException(502, f"Stripe error: {e}")
        req_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.deposit_requests.insert_one({
            "id": req_id, "booking_id": booking_id, "property_id": b.get("property_id"),
            "amount": amount, "currency": "GBP", "checkout_session_id": sess.session_id,
            "checkout_url": sess.url, "status": "sent",
            "created_at": now, "created_by": actor})
        await db.payment_transactions.insert_one({
            "id": str(uuid.uuid4()), "session_id": sess.session_id,
            "booking_id": booking_id, "property_id": b.get("property_id"),
            "amount": amount, "currency": "gbp", "type": "risk_deposit",
            "payment_status": "pending", "metadata": {"booking_id": booking_id},
            "created_at": now})
        email_result = "no_email"
        if b.get("guest_email"):
            email_result = await _send_email(
                b["guest_email"], "Rezervasyonunuz için depozito talebi",
                f"""
                <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#292524;">
                  <h2 style="color:#292524;">Rezervasyonunuzu güvence altına alın</h2>
                  <p>Merhaba {b.get('guest_name') or 'değerli misafirimiz'},</p>
                  <p>{b.get('check_in', '')} tarihli rezervasyonunuz için <b>£{amount:.0f}</b> depozito rica ediyoruz.</p>
                  <p style="text-align:center;margin:20px 0;">
                    <a href="{sess.url}" style="background:#292524;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block;">
                      Güvenli Ödeme — £{amount:.0f}
                    </a>
                  </p>
                  <p style="font-size:12px;color:#78716c;">Ödeme Stripe güvencesiyle alınır ve konaklama ücretinizden düşülür.</p>
                </div>
                """)
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"deposit_requested": True, "deposit_requested_at": now}})
        return {"ok": True, "request_id": req_id, "amount": amount,
                "checkout_url": sess.url, "email_result": email_result}

    @router.post("/guests/risk/{booking_id}/deposit-status")
    async def deposit_status(booking_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        req = await db.deposit_requests.find_one(
            {"booking_id": booking_id}, {"_id": 0}, sort=[("created_at", -1)])
        if not req:
            raise HTTPException(404, "Deposit request not found")
        if req.get("status") == "paid":
            return {"ok": True, "status": "paid", "amount": req["amount"]}
        # webhook-driven first, then best-effort poll
        tx = await db.payment_transactions.find_one(
            {"session_id": req["checkout_session_id"]}, {"_id": 0, "payment_status": 1})
        paid = bool(tx and tx.get("payment_status") == "paid")
        if not paid:
            base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
            try:
                status = await _stripe(base).get_checkout_status(req["checkout_session_id"])
                paid = status.payment_status == "paid"
            except Exception:
                paid = False  # proxy may not support retrieval; webhook will confirm
        if paid:
            now = datetime.now(timezone.utc).isoformat()
            already = await db.deposit_requests.find_one({"id": req["id"], "status": "paid"})
            if not already:
                await db.deposit_requests.update_one(
                    {"id": req["id"]}, {"$set": {"status": "paid", "paid_at": now}})
                await db.payment_transactions.update_one(
                    {"session_id": req["checkout_session_id"]},
                    {"$set": {"payment_status": "paid", "paid_at": now}})
                await db.folio_items.insert_one({
                    "id": str(uuid.uuid4()), "booking_id": booking_id,
                    "property_id": req.get("property_id"),
                    "type": "payment", "category": "deposit",
                    "description": "Depozito ödemesi (Stripe Checkout)",
                    "quantity": 1, "unit_price": req["amount"], "amount": req["amount"],
                    "currency": "GBP", "reference": req["checkout_session_id"],
                    "created_at": now, "created_by": "deposit-link"})
                await db.bookings.update_one(
                    {"id": booking_id}, {"$set": {"deposit_paid": True, "deposit_paid_at": now}})
        return {"ok": True, "status": "paid" if paid else "pending", "amount": req["amount"]}

    async def _deposit_autopilot_core(property_id: str = "") -> dict:
        """Auto-request deposits from HIGH risk (score>=60) arrivals within 14 days."""
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=14)).isoformat()
        pq = {} if not property_id or property_id == "all" else {"property_id": property_id}
        arrivals = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "pending_payment", "pending"]},
             "check_in": {"$gte": today, "$lte": horizon},
             "deposit_requested": {"$ne": True},
             "guest_email": {"$nin": [None, ""]}},
            {"_id": 0, "id": 1, "guest_email": 1}).to_list(1000)
        scanned, requested = len(arrivals), 0
        total_requested = 0.0
        cache = {}
        for b in arrivals:
            email = (b.get("guest_email") or "").lower()
            if email not in cache:
                cache[email] = await _risk_for(email)
            if cache[email]["level"] != "high":
                continue
            try:
                r = await _request_deposit_core(b["id"], "deposit-autopilot")
                if r.get("ok") and not r.get("already"):
                    requested += 1
                    total_requested += float(r.get("amount") or 0)
            except Exception as e:
                logger.warning(f"deposit autopilot {b['id']}: {e}")
        return {"ok": True, "scanned": scanned, "requested": requested,
                "total_requested": round(total_requested, 2)}

    @router.post("/guests/risk/deposit-autopilot/run")
    async def run_deposit_autopilot(data: dict = None,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _deposit_autopilot_core((data or {}).get("property_id", ""))

    router.run_deposit_autopilot_internal = _deposit_autopilot_core
    return router
