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
    stripe_api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY", "")

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

        property_id = booking.get('property_id', '')
        success_url = f"{origin_url}/book?property={property_id}&payment=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin_url}/book?property={property_id}&payment=cancelled"

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
            return {"status": "complete", "payment_status": "paid", "amount": tx.get("amount"), "type": tx.get("type"), "booking_ref": tx.get("reference_number", "")}

        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)

        try:
            import stripe as _stripe
            _stripe.api_key = stripe_api_key
            _s = _stripe.checkout.Session.retrieve(session_id)
            class _St: pass
            status = _St()
            status.payment_status = _s.payment_status
            status.status = _s.status
            status.amount_total = _s.amount_total
            status.currency = getattr(_s, "currency", "gbp")
            m = _s.metadata
            status.metadata = m.to_dict() if hasattr(m, "to_dict") else {}
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
            "booking_ref": tx.get("reference_number", "") if tx else "",
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
                # No-show depozito isteği ödendiyse işaretle (rezervasyon güvenceli olur)
                try:
                    from routes.hotel_ops.deposit_rule import mark_deposit_paid
                    await mark_deposit_paid(db, event.session_id)
                except Exception as _dep_ex:
                    logger.warning(f"deposit webhook mark error: {_dep_ex}")
                tx = await db.payment_transactions.find_one({"session_id": event.session_id}, {"_id": 0})
                if tx and tx.get("payment_status") != "paid":
                    await db.payment_transactions.update_one(
                        {"session_id": event.session_id},
                        {"$set": {"payment_status": "paid", "status": "complete",
                                  "paid_at": datetime.now(timezone.utc).isoformat()}}
                    )
                    # Auto-confirm booking + send confirmation email when payment lands
                    if tx.get("type") == "booking" and tx.get("reference_id"):
                        booking_id = tx["reference_id"]
                        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
                        if booking:
                            await db.bookings.update_one(
                                {"id": booking_id},
                                {"$set": {
                                    "status": "confirmed",
                                    "payment_status": "paid",
                                    "paid_at": datetime.now(timezone.utc).isoformat(),
                                }},
                            )
                            # Send confirmation email — currently mocked (Resend integration
                            # ships once user provides RESEND_API_KEY). Logged so admin can
                            # verify the trigger fires from the booking_email_log collection.
                            await db.booking_email_log.insert_one({
                                "id": str(uuid.uuid4()),
                                "booking_id": booking_id,
                                "booking_ref": booking.get("booking_ref", ""),
                                "to": booking.get("guest_email", ""),
                                "subject": f"Booking confirmed · {booking.get('booking_ref', '')}",
                                "type": "booking_confirmation",
                                "status": "MOCKED",
                                "sent_at": datetime.now(timezone.utc).isoformat(),
                            })
                            logger.info(
                                "📧 Booking confirmation email MOCKED — booking %s, guest %s",
                                booking.get("booking_ref"), booking.get("guest_email"),
                            )
                # Metadata fallback: booking_id direkt metadata'da olabilir (eski akış)
                meta = event.metadata or {}
                if meta.get("booking_id"):
                    await db.bookings.update_one(
                        {"id": meta["booking_id"], "payment_status": {"$ne": "paid"}},
                        {"$set": {"payment_status": "paid", "status": "confirmed",
                                  "paid_at": datetime.now(timezone.utc).isoformat()}}
                    )
                # Tip ödemesi ise tips koleksiyonunu güncelle
                if meta.get("type") == "tip":
                    await db.tips.update_one(
                        {"session_id": event.session_id},
                        {"$set": {"status": "paid",
                                  "paid_at": datetime.now(timezone.utc).isoformat()}}
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

    # ==================== IYZICO VIRTUAL CHECKOUT ====================

    @router.post("/payments/iyzico-checkout")
    async def create_iyzico_checkout(data: Dict, request: Request):
        """Create iyzico checkout session for a booking (Turkey)"""
        booking_id = data.get("booking_id")
        origin_url = data.get("origin_url", "")

        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        amount = float(booking.get("total_price", 0))
        if amount <= 0:
            raise HTTPException(400, "Invalid amount")

        currency = data.get("currency", "TRY")
        installments = data.get("installments", 1)

        # Get iyzico credentials
        settings = await db.terminal_settings.find_one({"property_id": booking.get("property_id")}, {"_id": 0})
        iyzico_key = settings.get("iyzico_api_key", "") if settings else ""
        iyzico_secret = settings.get("iyzico_secret_key", "") if settings else ""

        session_token = str(uuid.uuid4())
        host_url = str(request.base_url).rstrip("/")
        base_url = data.get("origin_url") or os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))

        # Create transaction record
        tx = {
            "id": str(uuid.uuid4()),
            "session_id": f"iyzico_{session_token}",
            "type": "booking",
            "reference_id": booking_id,
            "reference_number": booking.get("booking_ref", ""),
            "property_id": booking.get("property_id", ""),
            "amount": amount,
            "currency": currency,
            "guest_name": booking.get("guest_name", ""),
            "guest_email": booking.get("guest_email", ""),
            "payment_method": "iyzico",
            "payment_status": "initiated",
            "installments": installments,
            "metadata": {
                "type": "booking", "booking_id": booking_id,
                "booking_ref": booking.get("booking_ref", ""),
                "provider": "iyzico",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(tx)

        if iyzico_key and iyzico_secret and iyzico_key != "test_iyzico_key":
            # Real iyzico Checkout Form API
            try:
                import httpx, hashlib, base64
                iyzico_base = settings.get("iyzico_base_url", "https://sandbox-api.iyzipay.com")
                random_str = str(uuid.uuid4())[:8]
                hash_str = f"{iyzico_key}{random_str}{iyzico_secret}"
                pki_hash = hashlib.sha1(hash_str.encode()).digest()
                auth_header = f"IYZWS {iyzico_key}:{base64.b64encode(pki_hash).decode()}"

                checkout_data = {
                    "locale": "tr", "conversationId": session_token,
                    "price": str(amount), "paidPrice": str(amount),
                    "currency": currency, "installment": installments,
                    "basketId": booking_id,
                    "paymentGroup": "PRODUCT",
                    "callbackUrl": f"{host_url}/api/payments/iyzico-callback?token={session_token}",
                    "enabledInstallments": [1, 2, 3, 6, 9, 12],
                    "buyer": {
                        "id": booking.get("guest_email", "guest"),
                        "name": booking.get("guest_name", "Guest").split(" ")[0],
                        "surname": " ".join(booking.get("guest_name", "Guest").split(" ")[1:]) or "Guest",
                        "email": booking.get("guest_email", "guest@hotel.com"),
                        "identityNumber": "11111111111",
                        "registrationAddress": "Hotel Address",
                        "city": "Istanbul", "country": "Turkey",
                        "ip": "85.34.78.112",
                    },
                    "billingAddress": {"contactName": booking.get("guest_name", "Guest"), "city": "Istanbul", "country": "Turkey", "address": "Hotel"},
                    "basketItems": [{"id": booking_id, "name": f"Room Booking {booking.get('booking_ref','')}", "category1": "Accommodation", "itemType": "VIRTUAL", "price": str(amount)}],
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(f"{iyzico_base}/payment/iyzipos/checkoutform/initialize/auth/ecom",
                        json=checkout_data,
                        headers={"Authorization": auth_header, "Content-Type": "application/json", "x-iyzi-rnd": random_str},
                        timeout=15)
                    result = resp.json()
                    if result.get("status") == "success" and result.get("paymentPageUrl"):
                        return {"url": result["paymentPageUrl"], "session_id": f"iyzico_{session_token}", "provider": "iyzico"}
            except Exception as e:
                logger.error(f"iyzico checkout error: {e}")

        # Demo/sandbox mode — redirect to our own demo checkout page
        checkout_url = f"{base_url}/turkish-pay?provider=iyzico&token={session_token}&amount={amount}&currency={currency}&ref={booking.get('booking_ref','')}&name={booking.get('guest_name','')}&installments={installments}"
        return {"url": checkout_url, "session_id": f"iyzico_{session_token}", "provider": "iyzico", "mode": "demo"}

    # ==================== PAYTR VIRTUAL CHECKOUT ====================

    @router.post("/payments/paytr-checkout")
    async def create_paytr_checkout(data: Dict, request: Request):
        """Create PayTR checkout session for a booking (Turkey)"""
        booking_id = data.get("booking_id")
        origin_url = data.get("origin_url", "")

        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        amount = float(booking.get("total_price", 0))
        if amount <= 0:
            raise HTTPException(400, "Invalid amount")

        currency = data.get("currency", "TRY")
        installments = data.get("installments", 1)

        settings = await db.terminal_settings.find_one({"property_id": booking.get("property_id")}, {"_id": 0})
        paytr_id = settings.get("paytr_merchant_id", "") if settings else ""
        paytr_key = settings.get("paytr_merchant_key", "") if settings else ""
        paytr_salt = settings.get("paytr_merchant_salt", "") if settings else ""

        session_token = str(uuid.uuid4())
        host_url = str(request.base_url).rstrip("/")
        base_url = data.get("origin_url") or os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))

        tx = {
            "id": str(uuid.uuid4()),
            "session_id": f"paytr_{session_token}",
            "type": "booking",
            "reference_id": booking_id,
            "reference_number": booking.get("booking_ref", ""),
            "property_id": booking.get("property_id", ""),
            "amount": amount,
            "currency": currency,
            "guest_name": booking.get("guest_name", ""),
            "guest_email": booking.get("guest_email", ""),
            "payment_method": "paytr",
            "payment_status": "initiated",
            "installments": installments,
            "metadata": {"type": "booking", "booking_id": booking_id, "booking_ref": booking.get("booking_ref", ""), "provider": "paytr"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(tx)

        if paytr_id and paytr_key and paytr_salt and paytr_id != "test_paytr_merchant":
            # Real PayTR iFrame Token API
            try:
                import httpx, hashlib, base64
                amount_cents = int(amount * 100)
                basket_json = base64.b64encode(f'[["Room Booking","{amount}","1"]]'.encode()).decode()
                hash_str = f"{paytr_id}{origin_url or host_url}{booking_id}{amount_cents}{basket_json}0{installments}{currency}test{booking.get('guest_email','guest@hotel.com')}{paytr_salt}"
                paytr_token = base64.b64encode(hashlib.sha256(hash_str.encode()).digest()).decode()

                async with httpx.AsyncClient() as client:
                    resp = await client.post("https://www.paytr.com/odeme/api/get-token", data={
                        "merchant_id": paytr_id, "user_ip": "85.34.78.112",
                        "merchant_oid": booking_id, "email": booking.get("guest_email", ""),
                        "payment_amount": amount_cents, "paytr_token": paytr_token,
                        "user_basket": basket_json, "debug_on": "1",
                        "no_installment": "0" if installments > 1 else "1",
                        "max_installment": str(installments), "currency": currency,
                        "test_mode": "1",
                        "merchant_ok_url": f"{base_url}/book?property={booking.get('property_id','')}&payment=success",
                        "merchant_fail_url": f"{base_url}/book?property={booking.get('property_id','')}&payment=cancelled",
                    }, timeout=15)
                    result = resp.json()
                    if result.get("status") == "success" and result.get("token"):
                        iframe_url = f"https://www.paytr.com/odeme/guvenli/{result['token']}"
                        return {"url": iframe_url, "session_id": f"paytr_{session_token}", "provider": "paytr", "iframe_token": result["token"]}
            except Exception as e:
                logger.error(f"PayTR checkout error: {e}")

        # Demo/sandbox mode
        checkout_url = f"{base_url}/turkish-pay?provider=paytr&token={session_token}&amount={amount}&currency={currency}&ref={booking.get('booking_ref','')}&name={booking.get('guest_name','')}&installments={installments}"
        return {"url": checkout_url, "session_id": f"paytr_{session_token}", "provider": "paytr", "mode": "demo"}

    # ==================== TURKISH PAYMENT CALLBACK ====================

    @router.post("/payments/iyzico-callback")
    async def iyzico_callback(request: Request):
        """iyzico checkout callback"""
        form = await request.form()
        token = form.get("token") or request.query_params.get("token", "")
        session_id = f"iyzico_{token}"
        status = form.get("status", "")
        if status == "success":
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}}
            )
        return {"status": "ok"}

    @router.post("/payments/paytr-callback")
    async def paytr_callback(request: Request):
        """PayTR payment callback"""
        form = await request.form()
        merchant_oid = form.get("merchant_oid", "")
        status = form.get("status", "")
        if status == "success":
            tx = await db.payment_transactions.find_one({"reference_id": merchant_oid}, {"_id": 0})
            if tx:
                await db.payment_transactions.update_one(
                    {"id": tx["id"]},
                    {"$set": {"payment_status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}}
                )
        return {"status": "OK"}

    # ==================== TURKISH DEMO PAYMENT CONFIRM ====================

    @router.post("/payments/turkish-demo-confirm")
    async def turkish_demo_confirm(data: Dict):
        """Confirm a demo Turkish payment (used in sandbox/demo mode)"""
        session_token = data.get("token", "")
        provider = data.get("provider", "iyzico")
        session_id = f"{provider}_{session_token}"

        tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not tx:
            raise HTTPException(404, "Transaction not found")

        now = datetime.now(timezone.utc).isoformat()
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": "paid", "paid_at": now, "demo_mode": True}}
        )

        # Update the booking
        if tx.get("type") == "booking" and tx.get("reference_id"):
            await db.bookings.update_one(
                {"id": tx["reference_id"]},
                {"$set": {"payment_status": "paid", "payment_method": provider, "paid_at": now}}
            )

        return {
            "status": "paid",
            "provider": provider,
            "amount": tx.get("amount", 0),
            "currency": tx.get("currency", "TRY"),
            "booking_ref": tx.get("reference_number", ""),
            "demo_mode": True,
        }

    return router
