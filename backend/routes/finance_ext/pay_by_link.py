"""
Pay-by-Link — Stripe hosted checkout ile rezervasyon bakiyesi tahsilatı.
Resepsiyon tek tıkla ödeme linki üretir; misafir linkten öder; sistem folioyu günceller.

Endpoints:
- POST /api/pay-links/create {booking_id, amount?, origin_url} (staff)
- GET  /api/pay-links/{booking_id} (staff) — geçmiş linkler
- GET  /api/pay-links/status/{session_id} (public, poll)
- POST /api/stripe/webhook
"""
import os
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import resend
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import require_perm

logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


class PayLinkIn(BaseModel):
    booking_id: str
    amount: Optional[float] = None
    origin_url: str


class SendLinkIn(BaseModel):
    booking_id: str
    checkout_url: str
    amount: float
    currency: str = "GBP"


def _link_email_html(booking: dict, hotel: str, checkout_url: str, amount: float,
                     currency: str, reminder: bool = False) -> str:
    sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(currency.upper(), currency.upper() + " ")
    note = ("<p style='color:#b45309'>This is a friendly reminder — your payment is still pending.</p>"
            if reminder else "")
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px">
      <h2 style="color:#1c1917">{hotel}</h2>
      <p>Dear {booking.get('guest_name', 'Guest')},</p>
      {note}
      <p>Please use the secure link below to complete your payment of
         <b>{sym}{amount:.2f}</b> for your stay
         ({booking.get('check_in')} → {booking.get('check_out')}).</p>
      <p style="margin:28px 0;text-align:center">
        <a href="{checkout_url}" style="background:#4f46e5;color:#fff;padding:12px 28px;
           border-radius:8px;text-decoration:none;font-weight:bold">Pay Securely</a>
      </p>
      <p style="color:#78716c;font-size:12px">Payment is processed securely by Stripe.</p>
    </div>"""


async def _deliver_email(to: str, subject: str, html: str) -> bool:
    """Returns True if actually sent, False if mocked/failed."""
    import resend
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key or api_key == "re_123456789":
        return False
    resend.api_key = api_key
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
            "to": [to], "subject": subject, "html": html})
        return True
    except Exception as e:
        logger.warning(f"pay-link email failed: {e}")
        return False


async def run_pay_link_reminders(db, property_id: str = "") -> dict:
    """24 saatten eski, ödenmemiş pay-by-link'ler için yeni Stripe linki üretip hatırlatma e-postası gönderir."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()
    q = {"kind": "pay_by_link", "payment_status": "pending",
         "created_at": {"$lt": cutoff}, "reminder_sent": {"$ne": True}}
    if property_id and property_id != "all":
        q["property_id"] = property_id
    txs = await db.payment_transactions.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
    base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
    sent = skipped = 0
    seen_bookings = set()
    for tx in txs:
        bid = tx.get("booking_id")
        if not bid or bid in seen_bookings:
            skipped += 1
            continue
        seen_bookings.add(bid)
        booking = await db.bookings.find_one({"id": bid}, {"_id": 0})
        if not booking or booking.get("payment_status") == "paid" or not booking.get("guest_email"):
            await db.payment_transactions.update_one(
                {"session_id": tx["session_id"]},
                {"$set": {"reminder_sent": True, "reminder_skipped": True}})
            skipped += 1
            continue
        amount = float(tx.get("amount") or 0)
        currency = (tx.get("currency") or "gbp").lower()
        try:
            session = stripe.checkout.Session.create(
                line_items=[{"price_data": {
                    "currency": currency,
                    "unit_amount": int(round(amount * 100)),
                    "product_data": {"name": f"Konaklama ödemesi — {booking.get('guest_name', '')} ({booking.get('check_in')} → {booking.get('check_out')})"},
                }, "quantity": 1}],
                mode="payment",
                success_url=f"{base}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{base}/payment/cancel",
                metadata={"booking_id": bid, "kind": "pay_by_link", "reminder": "true"})
        except stripe.error.StripeError as e:
            logger.warning(f"reminder session create failed: {e}")
            skipped += 1
            continue
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.payment_transactions.insert_one({
            "session_id": session.id, "booking_id": bid,
            "property_id": booking.get("property_id"), "kind": "pay_by_link",
            "amount": amount, "currency": currency,
            "status": "initiated", "payment_status": "pending",
            "reminder_of": tx["session_id"],
            "created_by": "auto_reminder",
            "created_at": now_iso, "updated_at": now_iso})
        await db.payment_transactions.update_one(
            {"session_id": tx["session_id"]},
            {"$set": {"reminder_sent": True, "reminder_at": now_iso,
                      "superseded_by": session.id}})
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0, "name": 1})
        hotel = (prop or {}).get("name", "Hotel")
        html = _link_email_html(booking, hotel, session.url, amount, currency.upper(), reminder=True)
        delivered = await _deliver_email(booking["guest_email"],
                                         f"{hotel} — Payment reminder", html)
        await db.payment_transactions.update_one(
            {"session_id": session.id},
            {"$set": {"emailed_to": booking["guest_email"], "emailed_at": now_iso,
                      "email_mocked": not delivered}})
        sent += 1
    return {"ok": True, "reminders_sent": sent, "skipped": skipped}


async def _mark_paid(db, session_id: str, extra: dict):
    res = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid",
                  "updated_at": datetime.now(timezone.utc).isoformat(), **extra}})
    if res.modified_count:
        tx = await db.payment_transactions.find_one({"session_id": session_id})
        if tx and tx.get("booking_id"):
            booking = await db.bookings.find_one(
                {"id": tx["booking_id"]}, {"_id": 0, "guest_name": 1, "booking_ref": 1, "total_price": 1})
            paid_txs = await db.payment_transactions.find(
                {"booking_id": tx["booking_id"], "kind": "pay_by_link", "payment_status": "paid"},
                {"_id": 0, "amount": 1}).to_list(50)
            paid_total = sum(float(t.get("amount") or 0) for t in paid_txs)
            total_price = float((booking or {}).get("total_price") or 0)
            new_status = "paid" if paid_total >= total_price * 0.99 else "partial"
            await db.bookings.update_one({"id": tx["booking_id"]},
                                         {"$set": {"payment_status": new_status}})
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()), "booking_id": tx["booking_id"],
                "property_id": tx.get("property_id"),
                "type": "payment", "category": "card",
                "description": f"Stripe Pay-by-Link tahsilatı ({(booking or {}).get('booking_ref', '')})",
                "quantity": 1, "unit_price": float(tx.get("amount") or 0),
                "amount": float(tx.get("amount") or 0),
                "currency": (tx.get("currency") or "gbp").upper(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "Stripe Pay-by-Link"})


def create_pay_by_link_router(db):
    router = APIRouter()

    @router.post("/pay-links/create")
    async def create_link(body: PayLinkIn,
                          current_user: dict = Depends(require_perm("edit_bookings"))):
        booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        amount = float(body.amount if body.amount else booking.get("total_price") or 0)
        if amount <= 0:
            raise HTTPException(400, "Tutar 0'dan büyük olmalı")
        currency = (booking.get("currency") or "GBP").lower()
        origin = body.origin_url.rstrip("/")
        kwargs = dict(
            line_items=[{"price_data": {
                "currency": currency,
                "unit_amount": int(round(amount * 100)),
                "product_data": {"name": f"Konaklama ödemesi — {booking.get('guest_name', '')} ({booking.get('check_in')} → {booking.get('check_out')})"},
            }, "quantity": 1}],
            mode="payment",
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/payment/cancel",
            metadata={"booking_id": body.booking_id, "kind": "pay_by_link"},
        )
        try:
            session = stripe.checkout.Session.create(
                **kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
        except stripe.error.InvalidRequestError:
            session = stripe.checkout.Session.create(**kwargs)
        await db.payment_transactions.insert_one({
            "session_id": session.id, "booking_id": body.booking_id,
            "property_id": booking.get("property_id"), "kind": "pay_by_link",
            "amount": amount, "currency": currency,
            "status": "initiated", "payment_status": "pending",
            "created_by": current_user.get("email", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"checkout_url": session.url, "session_id": session.id, "amount": amount, "currency": currency}

    @router.post("/pay-links/send")
    async def send_link_email(body: SendLinkIn,
                              current_user: dict = Depends(require_perm("edit_bookings"))):
        booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        email = booking.get("guest_email")
        if not email:
            raise HTTPException(400, "Rezervasyonda misafir e-postası yok")
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0, "name": 1})
        hotel = (prop or {}).get("name", "Hotel")
        sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(body.currency.upper(), body.currency.upper() + " ")
        html = _link_email_html(booking, hotel, body.checkout_url, body.amount, body.currency)
        delivered = await _deliver_email(email, f"{hotel} — Payment request {sym}{body.amount:.2f}", html)
        mocked = not delivered
        last_tx = await db.payment_transactions.find_one(
            {"booking_id": body.booking_id, "kind": "pay_by_link"},
            sort=[("created_at", -1)])
        if last_tx:
            await db.payment_transactions.update_one(
                {"session_id": last_tx["session_id"]},
                {"$set": {"emailed_to": email, "emailed_at": datetime.now(timezone.utc).isoformat(),
                          "email_mocked": mocked}})
        return {"status": "mocked" if mocked else "sent", "to": email}

    @router.get("/pay-links/{booking_id}")
    async def list_links(booking_id: str,
                         current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        return await db.payment_transactions.find(
            {"booking_id": booking_id, "kind": "pay_by_link"}, {"_id": 0}
        ).sort("created_at", -1).to_list(20)

    @router.get("/pay-links/status/{session_id}")
    async def payment_status(session_id: str):
        rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Transaction not found")
        if rec.get("payment_status") != "paid":
            try:
                s = stripe.checkout.Session.retrieve(session_id)
                if s.payment_status == "paid" or s.status == "complete":
                    await _mark_paid(db, session_id, {"stripe_payment_intent_id": s.payment_intent})
                    rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            except stripe.error.StripeError:
                pass
        return {"session_id": rec["session_id"], "status": rec["status"],
                "payment_status": rec["payment_status"]}

    @router.post("/stripe/webhook")
    async def stripe_webhook(request: Request):
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except Exception:
            raise HTTPException(400, "Invalid signature")
        obj, t = event["data"]["object"], event["type"]
        if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            await _mark_paid(db, obj["id"], {"stripe_payment_intent_id": obj.get("payment_intent")})
        elif t in ("checkout.session.async_payment_failed", "checkout.session.expired"):
            await db.payment_transactions.update_one(
                {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                {"$set": {"status": "failed" if "failed" in t else "expired",
                          "payment_status": "failed" if "failed" in t else "expired",
                          "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"status": "ok"}

    return router
