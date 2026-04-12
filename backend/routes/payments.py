"""
Hotel Payment Gateway — Cloudbeds-level payment processing
Stripe checkout for Bookings + POS, payment transactions, refunds, payment dashboard
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Dict
from collections import defaultdict
import uuid
import os
import logging

from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
from routes.helpers import log_sync

logger = logging.getLogger(__name__)


def create_payments_router(db, require_roles):
    router = APIRouter()
    stripe_api_key = os.environ.get("STRIPE_API_KEY", "")

    # ==================== BOOKING CHECKOUT ====================

    @router.post("/payments/booking-checkout")
    async def create_booking_checkout(data: Dict, request: Request):
        """Create Stripe checkout session for a booking"""
        booking_id = data.get("booking_id")
        origin_url = data.get("origin_url", "")

        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        amount = float(booking.get("total_price", 0))
        if amount <= 0:
            raise HTTPException(400, "Invalid booking amount")

        currency = booking.get("currency", "gbp").lower()

        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)

        success_url = f"{origin_url}/booking-confirmation?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin_url}/booking/{booking.get('property_id', '')}"

        checkout_req = CheckoutSessionRequest(
            amount=amount,
            currency=currency,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "booking",
                "booking_id": booking_id,
                "booking_ref": booking.get("booking_ref", ""),
                "guest_name": booking.get("guest_name", ""),
                "guest_email": booking.get("guest_email", ""),
                "property_id": booking.get("property_id", ""),
            }
        )

        session = await stripe_checkout.create_checkout_session(checkout_req)

        # Create payment transaction record
        tx = {
            "id": str(uuid.uuid4()),
            "session_id": session.session_id,
            "type": "booking",
            "reference_id": booking_id,
            "reference_number": booking.get("booking_ref", ""),
            "property_id": booking.get("property_id", ""),
            "amount": amount,
            "currency": currency,
            "guest_name": booking.get("guest_name", ""),
            "guest_email": booking.get("guest_email", ""),
            "payment_method": "stripe",
            "payment_status": "initiated",
            "metadata": checkout_req.metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(tx)

        return {"url": session.url, "session_id": session.session_id}

    # ==================== POS CHECKOUT ====================

    @router.post("/payments/pos-checkout")
    async def create_pos_checkout(data: Dict, request: Request):
        """Create Stripe checkout session for a POS order"""
        order_id = data.get("order_id")
        origin_url = data.get("origin_url", "")

        order = await db.pos_orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Order not found")

        amount = float(order.get("total", 0))
        tip = float(data.get("tip", 0))
        total = round(amount + tip, 2)

        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)

        success_url = f"{origin_url}/pos-payment-success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin_url}/"

        checkout_req = CheckoutSessionRequest(
            amount=total,
            currency="gbp",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "pos",
                "order_id": order_id,
                "order_number": order.get("order_number", ""),
                "outlet_name": order.get("outlet_name", ""),
                "tip": str(tip),
                "property_id": order.get("property_id", ""),
            }
        )

        session = await stripe_checkout.create_checkout_session(checkout_req)

        tx = {
            "id": str(uuid.uuid4()),
            "session_id": session.session_id,
            "type": "pos",
            "reference_id": order_id,
            "reference_number": order.get("order_number", ""),
            "property_id": order.get("property_id", ""),
            "amount": total,
            "currency": "gbp",
            "guest_name": order.get("guest_name", ""),
            "tip": tip,
            "payment_method": "stripe",
            "payment_status": "initiated",
            "metadata": checkout_req.metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(tx)

        return {"url": session.url, "session_id": session.session_id}

    # ==================== CHECK PAYMENT STATUS ====================

    @router.get("/payments/status/{session_id}")
    async def check_payment_status(session_id: str, request: Request):
        """Poll Stripe for payment status and update transaction"""
        # Check if already processed
        tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if tx and tx.get("payment_status") == "paid":
            return {"status": "complete", "payment_status": "paid", "amount": tx.get("amount"), "type": tx.get("type")}

        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)

        try:
            status = await stripe_checkout.get_checkout_status(session_id)
        except Exception as e:
            logger.error(f"Stripe status check error: {e}")
            return {"status": "error", "payment_status": "unknown", "error": str(e)[:200]}

        new_status = status.payment_status
        update = {"payment_status": new_status, "stripe_status": status.status, "updated_at": datetime.now(timezone.utc).isoformat()}

        if new_status == "paid" and tx and tx.get("payment_status") != "paid":
            update["paid_at"] = datetime.now(timezone.utc).isoformat()

            # Process successful payment
            if tx.get("type") == "booking":
                await db.bookings.update_one(
                    {"id": tx["reference_id"]},
                    {"$set": {"payment_status": "paid", "payment_method": "stripe", "paid_at": update["paid_at"]}}
                )
                # Create income entry
                booking = await db.bookings.find_one({"id": tx["reference_id"]}, {"_id": 0})
                if booking:
                    from models import IncomeEntry
                    income = IncomeEntry(
                        property_id=booking.get("property_id", ""),
                        category="room_revenue",
                        amount=tx["amount"],
                        currency=tx.get("currency", "GBP").upper(),
                        description=f"Booking {booking.get('booking_ref', '')} — Stripe",
                        department="rooms",
                        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        source="stripe",
                        reference=session_id,
                    )
                    inc_doc = income.model_dump()
                    await db.income_entries.insert_one(inc_doc)

            elif tx.get("type") == "pos":
                tip = float(tx.get("tip", 0))
                await db.pos_orders.update_one(
                    {"id": tx["reference_id"]},
                    {"$set": {"payment_status": "paid", "payment_method": "stripe", "tip": tip, "paid_at": update["paid_at"]}}
                )
                order = await db.pos_orders.find_one({"id": tx["reference_id"]}, {"_id": 0})
                if order:
                    from models import IncomeEntry
                    income = IncomeEntry(
                        property_id=order.get("property_id", ""),
                        category="food_beverage",
                        amount=order.get("total", 0),
                        currency="GBP",
                        description=f"POS {order.get('order_number', '')} — Stripe",
                        department="food_beverage",
                        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        source="stripe_pos",
                        reference=session_id,
                    )
                    inc_doc = income.model_dump()
                    await db.income_entries.insert_one(inc_doc)

            await log_sync(db, "payments", "stripe", "success", f"Payment completed: {tx.get('type')} {tx.get('reference_number')} — £{tx.get('amount')}", session_id)

        elif status.status == "expired":
            update["payment_status"] = "expired"

        await db.payment_transactions.update_one({"session_id": session_id}, {"$set": update})

        return {
            "status": status.status,
            "payment_status": new_status,
            "amount": status.amount_total / 100 if status.amount_total else 0,
            "currency": status.currency,
            "type": tx.get("type") if tx else "unknown",
        }

    # ==================== STRIPE WEBHOOK ====================

    @router.post("/webhook/stripe")
    async def stripe_webhook(request: Request):
        body = await request.body()
        sig = request.headers.get("Stripe-Signature", "")

        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)

        try:
            event = await stripe_checkout.handle_webhook(body, sig)
            if event.payment_status == "paid":
                tx = await db.payment_transactions.find_one({"session_id": event.session_id}, {"_id": 0})
                if tx and tx.get("payment_status") != "paid":
                    await db.payment_transactions.update_one(
                        {"session_id": event.session_id},
                        {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}}
                    )
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return {"status": "error"}

    # ==================== PAYMENT TRANSACTIONS LIST ====================

    @router.get("/payments/transactions/{property_id}")
    async def list_transactions(property_id: str, status: str = "", type: str = "",
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if status:
            query["payment_status"] = status
        if type:
            query["type"] = type
        docs = await db.payment_transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    # ==================== PAYMENT DASHBOARD ====================

    @router.get("/payments/dashboard/{property_id}")
    async def payment_dashboard(property_id: str, period: str = "30d",
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        txns = await db.payment_transactions.find(
            {"property_id": property_id, "created_at": {"$gte": cutoff}}, {"_id": 0}
        ).to_list(1000)

        total_processed = sum(t.get("amount", 0) for t in txns if t.get("payment_status") == "paid")
        total_pending = sum(t.get("amount", 0) for t in txns if t.get("payment_status") in ("initiated", "pending"))
        total_failed = sum(t.get("amount", 0) for t in txns if t.get("payment_status") in ("expired", "failed"))

        by_type = defaultdict(lambda: {"count": 0, "amount": 0})
        for t in txns:
            if t.get("payment_status") == "paid":
                by_type[t.get("type", "other")]["count"] += 1
                by_type[t.get("type", "other")]["amount"] += t.get("amount", 0)

        by_method = defaultdict(lambda: {"count": 0, "amount": 0})
        for t in txns:
            if t.get("payment_status") == "paid":
                by_method[t.get("payment_method", "unknown")]["count"] += 1
                by_method[t.get("payment_method", "unknown")]["amount"] += t.get("amount", 0)

        # Daily trend
        daily = defaultdict(float)
        for t in txns:
            if t.get("payment_status") == "paid":
                day = t.get("paid_at", t.get("created_at", ""))[:10]
                daily[day] += t.get("amount", 0)
        daily_trend = [{"date": k, "amount": round(v, 2)} for k, v in sorted(daily.items())]

        paid_count = sum(1 for t in txns if t.get("payment_status") == "paid")
        success_rate = round((paid_count / len(txns)) * 100, 1) if txns else 0

        return {
            "period_days": days,
            "total_transactions": len(txns),
            "total_processed": round(total_processed, 2),
            "total_pending": round(total_pending, 2),
            "total_failed": round(total_failed, 2),
            "success_rate": success_rate,
            "by_type": {k: {"count": v["count"], "amount": round(v["amount"], 2)} for k, v in by_type.items()},
            "by_method": {k: {"count": v["count"], "amount": round(v["amount"], 2)} for k, v in by_method.items()},
            "daily_trend": daily_trend,
        }

    # ==================== PAYMENT SETTINGS ====================

    @router.get("/payments/settings/{property_id}")
    async def get_payment_settings(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.payment_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            default = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "stripe_enabled": True,
                "pay_at_hotel_enabled": True,
                "room_charge_enabled": True,
                "cash_enabled": True,
                "contactless_enabled": True,
                "accepted_cards": ["visa", "mastercard", "amex"],
                "default_currency": "GBP",
                "auto_capture": True,
                "tipping_enabled": True,
                "tip_percentages": [10, 15, 20],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.payment_settings.insert_one(default)
            default.pop("_id", None)
            return default
        return doc

    @router.put("/payments/settings/{property_id}")
    async def update_payment_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.payment_settings.update_one({"property_id": property_id}, {"$set": updates}, upsert=True)
        doc = await db.payment_settings.find_one({"property_id": property_id}, {"_id": 0})
        return doc

    return router
