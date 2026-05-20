"""
Physical Card Terminal Integration
Stripe Terminal + iyzico (Turkey) + Generic Terminal Support
Auto-sends amount to card reader — no manual entry needed
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
from typing import Dict
import uuid
import os
import logging

from routes.helpers import log_sync

logger = logging.getLogger(__name__)


def create_terminal_router(db, require_roles):
    router = APIRouter()
    stripe_api_key = os.environ.get("STRIPE_API_KEY", "")

    # ==================== TERMINAL DEVICES ====================

    @router.get("/terminal/devices/{property_id}")
    async def list_devices(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.terminal_devices.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        return docs

    @router.post("/terminal/devices")
    async def register_device(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        device = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "name": data.get("name", "Card Reader 1"),
            "provider": data.get("provider", "stripe"),
            "provider_device_id": data.get("provider_device_id", ""),
            "location": data.get("location", ""),
            "outlet_id": data.get("outlet_id", ""),
            "status": "active",
            "last_used": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.terminal_devices.insert_one(device)
        device.pop("_id", None)
        return device

    @router.put("/terminal/devices/{device_id}")
    async def update_device(device_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.terminal_devices.update_one({"id": device_id}, {"$set": updates})
        doc = await db.terminal_devices.find_one({"id": device_id}, {"_id": 0})
        return doc

    @router.delete("/terminal/devices/{device_id}")
    async def delete_device(device_id: str, current_user: dict = Depends(require_roles("admin"))):
        await db.terminal_devices.delete_one({"id": device_id})
        return {"status": "deleted"}

    # ==================== STRIPE TERMINAL: SEND TO READER ====================

    @router.post("/terminal/stripe/create-payment")
    async def stripe_create_terminal_payment(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """
        Creates a PaymentIntent and sends it to the Stripe Terminal reader.
        The reader displays the amount — guest inserts/taps card — payment processed automatically.
        """
        amount = data.get("amount", 0)
        currency = data.get("currency", "gbp").lower()
        reader_id = data.get("reader_id", "")
        reference_type = data.get("reference_type", "pos")
        reference_id = data.get("reference_id", "")
        description = data.get("description", "")
        tip = data.get("tip", 0)
        total = round(amount + tip, 2)
        amount_cents = int(total * 100)

        if not reader_id:
            raise HTTPException(400, "Reader ID required")
        if amount_cents <= 0:
            raise HTTPException(400, "Invalid amount")

        try:
            import httpx
            headers = {"Authorization": f"Bearer {stripe_api_key}", "Content-Type": "application/x-www-form-urlencoded"}

            # Step 1: Create PaymentIntent
            async with httpx.AsyncClient() as client:
                pi_resp = await client.post("https://api.stripe.com/v1/payment_intents", headers=headers, data={
                    "amount": amount_cents,
                    "currency": currency,
                    "capture_method": "automatic",
                    "payment_method_types[]": "card_present",
                    "description": description or f"Terminal payment — {reference_type} {reference_id}",
                    "metadata[reference_type]": reference_type,
                    "metadata[reference_id]": reference_id,
                }, timeout=15)

                if pi_resp.status_code != 200:
                    error_data = pi_resp.json()
                    raise HTTPException(400, f"Stripe error: {error_data.get('error', {}).get('message', 'Unknown')}")

                pi = pi_resp.json()
                payment_intent_id = pi["id"]

                # Step 2: Send to reader (collect payment method)
                collect_resp = await client.post(
                    f"https://api.stripe.com/v1/terminal/readers/{reader_id}/process_payment_intent",
                    headers=headers,
                    data={"payment_intent": payment_intent_id},
                    timeout=15
                )

                reader_status = "sent_to_reader"
                if collect_resp.status_code != 200:
                    reader_status = "reader_error"
                    error_msg = collect_resp.json().get("error", {}).get("message", "Reader error")
                    logger.error(f"Stripe Terminal reader error: {error_msg}")

            # Record transaction
            tx = {
                "id": str(uuid.uuid4()),
                "payment_intent_id": payment_intent_id,
                "property_id": data.get("property_id", ""),
                "type": reference_type,
                "reference_id": reference_id,
                "amount": total,
                "currency": currency,
                "tip": tip,
                "reader_id": reader_id,
                "provider": "stripe_terminal",
                "status": reader_status,
                "payment_status": "pending",
                "created_by": current_user.get("name", "Staff"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.terminal_payments.insert_one(tx)
            tx.pop("_id", None)

            # Update device last_used
            await db.terminal_devices.update_one({"provider_device_id": reader_id}, {"$set": {"last_used": datetime.now(timezone.utc).isoformat()}})

            return {
                "status": reader_status,
                "payment_intent_id": payment_intent_id,
                "amount": total,
                "currency": currency,
                "message": "Amount sent to card reader. Waiting for guest to tap/insert card." if reader_status == "sent_to_reader" else "Failed to send to reader. Check reader connection.",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Stripe Terminal error: {e}")
            raise HTTPException(500, f"Terminal error: {str(e)[:200]}")

    @router.get("/terminal/stripe/payment-status/{payment_intent_id}")
    async def stripe_check_terminal_payment(payment_intent_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Check if the terminal payment has been completed"""
        try:
            import httpx
            headers = {"Authorization": f"Bearer {stripe_api_key}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}", headers=headers, timeout=10)
                if resp.status_code != 200:
                    return {"status": "error", "payment_status": "unknown"}
                pi = resp.json()
                status = pi.get("status", "unknown")

                # Update local record
                payment_status = "paid" if status == "succeeded" else ("pending" if status in ("requires_payment_method", "requires_confirmation", "processing") else "failed")
                await db.terminal_payments.update_one(
                    {"payment_intent_id": payment_intent_id},
                    {"$set": {"payment_status": payment_status, "stripe_status": status, "updated_at": datetime.now(timezone.utc).isoformat()}}
                )

                # If paid, update the referenced order/booking
                if payment_status == "paid":
                    tx = await db.terminal_payments.find_one({"payment_intent_id": payment_intent_id}, {"_id": 0})
                    if tx:
                        if tx.get("type") == "pos":
                            await db.pos_orders.update_one({"id": tx["reference_id"]}, {"$set": {
                                "payment_status": "paid", "payment_method": "card_terminal",
                                "tip": tx.get("tip", 0), "paid_at": datetime.now(timezone.utc).isoformat()
                            }})
                        elif tx.get("type") == "booking":
                            await db.bookings.update_one({"id": tx["reference_id"]}, {"$set": {
                                "payment_status": "paid", "payment_method": "card_terminal",
                                "paid_at": datetime.now(timezone.utc).isoformat()
                            }})
                        # Income entry
                        from models import IncomeEntry
                        cat = "food_beverage" if tx.get("type") == "pos" else "room_revenue"
                        income = IncomeEntry(
                            property_id=tx.get("property_id", ""),
                            category=cat, amount=tx["amount"], currency=tx.get("currency", "GBP").upper(),
                            description=f"Terminal {tx.get('type','')} {tx.get('reference_id','')}",
                            department="rooms" if tx.get("type") == "booking" else "food_beverage",
                            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                            source="card_terminal", reference=payment_intent_id,
                        )
                        await db.income_entries.insert_one(income.model_dump())
                        await log_sync(db, "terminal", "stripe", "success", f"Terminal payment £{tx['amount']} completed", payment_intent_id)

                return {"status": status, "payment_status": payment_status, "amount": pi.get("amount", 0) / 100}
        except Exception as e:
            return {"status": "error", "payment_status": "unknown", "error": str(e)[:200]}

    # ==================== IYZICO (TURKEY) TERMINAL ====================

    @router.post("/terminal/iyzico/create-payment")
    async def iyzico_create_payment(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Create iyzico payment for Turkish card terminals"""
        amount = data.get("amount", 0)
        currency = data.get("currency", "TRY")
        reference_type = data.get("reference_type", "pos")
        reference_id = data.get("reference_id", "")
        installments = data.get("installments", 1)

        # Get iyzico credentials from settings
        settings = await db.terminal_settings.find_one({"property_id": data.get("property_id")}, {"_id": 0})
        api_key = settings.get("iyzico_api_key", "") if settings else ""
        secret_key = settings.get("iyzico_secret_key", "") if settings else ""
        base_url = settings.get("iyzico_base_url", "https://sandbox-api.iyzipay.com") if settings else "https://sandbox-api.iyzipay.com"

        if not api_key or not secret_key:
            # Return sandbox response for development
            tx = {
                "id": str(uuid.uuid4()),
                "property_id": data.get("property_id", ""),
                "type": reference_type,
                "reference_id": reference_id,
                "amount": amount,
                "currency": currency,
                "installments": installments,
                "provider": "iyzico",
                "status": "sandbox",
                "payment_status": "sandbox",
                "message": "iyzico credentials not configured. Configure in Terminal Settings.",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.terminal_payments.insert_one(tx)
            tx.pop("_id", None)
            return tx

        # Real iyzico API call
        try:
            import httpx
            import hashlib
            import base64

            conversation_id = str(uuid.uuid4())[:8]
            payment_data = {
                "locale": "tr",
                "conversationId": conversation_id,
                "price": str(amount),
                "paidPrice": str(amount),
                "currency": currency,
                "installment": installments,
                "basketId": reference_id,
                "paymentChannel": "MOBILE",
                "paymentGroup": "PRODUCT",
            }

            # Create authorization header
            random_str = str(uuid.uuid4())[:8]
            hash_str = f"{api_key}{random_str}{secret_key}"
            pki_string = hashlib.sha1(hash_str.encode()).digest()
            auth_header = f"IYZWS {api_key}:{base64.b64encode(pki_string).decode()}"

            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{base_url}/payment/auth", json=payment_data,
                    headers={"Authorization": auth_header, "Content-Type": "application/json", "x-iyzi-rnd": random_str},
                    timeout=15)

                result = resp.json()

            tx = {
                "id": str(uuid.uuid4()),
                "property_id": data.get("property_id", ""),
                "type": reference_type,
                "reference_id": reference_id,
                "amount": amount,
                "currency": currency,
                "provider": "iyzico",
                "iyzico_response": result,
                "status": result.get("status", "unknown"),
                "payment_status": "paid" if result.get("status") == "success" else "failed",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.terminal_payments.insert_one(tx)
            tx.pop("_id", None)
            return tx

        except Exception as e:
            logger.error(f"iyzico error: {e}")
            raise HTTPException(500, f"iyzico error: {str(e)[:200]}")

    # ==================== TERMINAL SETTINGS ====================

    @router.get("/terminal/settings/{property_id}")
    async def get_terminal_settings(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.terminal_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            default = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "active_provider": "stripe",
                "stripe_location_id": "",
                "iyzico_api_key": "",
                "iyzico_secret_key": "",
                "iyzico_base_url": "https://sandbox-api.iyzipay.com",
                "paytr_merchant_id": "",
                "paytr_merchant_key": "",
                "paytr_merchant_salt": "",
                "auto_confirm": True,
                "enable_tipping_on_terminal": True,
                "enable_installments": False,
                "default_currency": "GBP",
                "supported_providers": ["stripe", "iyzico", "paytr"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.terminal_settings.insert_one(default)
            default.pop("_id", None)
            return default
        return doc

    @router.put("/terminal/settings/{property_id}")
    async def update_terminal_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.terminal_settings.update_one({"property_id": property_id}, {"$set": updates}, upsert=True)
        doc = await db.terminal_settings.find_one({"property_id": property_id}, {"_id": 0})
        return doc

    # ==================== TERMINAL PAYMENT HISTORY ====================

    @router.get("/terminal/payments/{property_id}")
    async def terminal_payment_history(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.terminal_payments.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    # ==================== QUICK PAY — POS ORDER TO TERMINAL ====================

    @router.post("/terminal/quick-pay/{order_id}")
    async def quick_pay_pos_order(order_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """One-click: Send POS order total to card terminal"""
        order = await db.pos_orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Order not found")

        settings = await db.terminal_settings.find_one({"property_id": order["property_id"]}, {"_id": 0})
        provider = settings.get("active_provider", "stripe") if settings else "stripe"
        reader_id = data.get("reader_id", "")
        tip = data.get("tip", 0)

        if not reader_id:
            # Get first active device
            device = await db.terminal_devices.find_one(
                {"property_id": order["property_id"], "status": "active"},
                {"_id": 0}
            )
            if device:
                reader_id = device.get("provider_device_id", "")

        if provider == "stripe":
            result = await stripe_create_terminal_payment({
                "amount": order["total"],
                "currency": "gbp",
                "reader_id": reader_id,
                "reference_type": "pos",
                "reference_id": order_id,
                "property_id": order["property_id"],
                "description": f"POS {order.get('order_number', '')} — {order.get('outlet_name', '')}",
                "tip": tip,
            }, current_user)
            return result
        else:
            return {
                "status": "sandbox",
                "message": f"Terminal provider '{provider}' — configure credentials in Terminal Settings",
                "amount": order["total"],
            }

    # ==================== QUICK PAY — BOOKING TO TERMINAL ====================

    @router.post("/terminal/quick-pay-booking/{booking_id}")
    async def quick_pay_booking(booking_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """One-click: Send booking total to card terminal"""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        reader_id = data.get("reader_id", "")
        if not reader_id:
            device = await db.terminal_devices.find_one(
                {"property_id": booking["property_id"], "status": "active"}, {"_id": 0}
            )
            if device:
                reader_id = device.get("provider_device_id", "")

        result = await stripe_create_terminal_payment({
            "amount": booking.get("total_price", 0),
            "currency": booking.get("currency", "gbp").lower(),
            "reader_id": reader_id,
            "reference_type": "booking",
            "reference_id": booking_id,
            "property_id": booking["property_id"],
            "description": f"Booking {booking.get('booking_ref', '')} — {booking.get('guest_name', '')}",
            "tip": 0,
        }, current_user)
        return result

    return router
