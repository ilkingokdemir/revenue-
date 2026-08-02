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
from datetime import datetime, timezone
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


async def _mark_paid(db, session_id: str, extra: dict):
    res = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid",
                  "updated_at": datetime.now(timezone.utc).isoformat(), **extra}})
    if res.modified_count:
        tx = await db.payment_transactions.find_one({"session_id": session_id})
        if tx and tx.get("booking_id"):
            await db.bookings.update_one({"id": tx["booking_id"]},
                                         {"$set": {"payment_status": "paid"}})
            booking = await db.bookings.find_one({"id": tx["booking_id"]}, {"_id": 0, "guest_name": 1, "booking_ref": 1})
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
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px">
          <h2 style="color:#1c1917">{hotel}</h2>
          <p>Dear {booking.get('guest_name', 'Guest')},</p>
          <p>Please use the secure link below to complete your payment of
             <b>{sym}{body.amount:.2f}</b> for your stay
             ({booking.get('check_in')} → {booking.get('check_out')}).</p>
          <p style="margin:28px 0;text-align:center">
            <a href="{body.checkout_url}" style="background:#4f46e5;color:#fff;padding:12px 28px;
               border-radius:8px;text-decoration:none;font-weight:bold">Pay Securely</a>
          </p>
          <p style="color:#78716c;font-size:12px">Payment is processed securely by Stripe.</p>
        </div>"""
        api_key = os.environ.get("RESEND_API_KEY", "")
        mocked = not api_key or api_key == "re_123456789"
        if not mocked:
            resend.api_key = api_key
            try:
                await asyncio.to_thread(resend.Emails.send, {
                    "from": os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
                    "to": [email],
                    "subject": f"{hotel} — Payment request {sym}{body.amount:.2f}",
                    "html": html})
            except Exception as e:
                logger.warning(f"pay-link email failed: {e}")
                mocked = True
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
