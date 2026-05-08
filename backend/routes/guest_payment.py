"""
Guest Payment Portal — Cloudbeds-style guest-facing payment page
Send payment links, view folio, pay via Stripe Checkout
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid
import os
import asyncio
import logging
import resend

from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

logger = logging.getLogger(__name__)

SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')


class SendPaymentLinkRequest(BaseModel):
    booking_id: str
    extra_charges: list = []  # [{description, amount, category}]
    notes: str = ""
    custom_amount: Optional[float] = None


class AddChargeRequest(BaseModel):
    description: str
    amount: float
    category: str = "other"  # room, minibar, restaurant, spa, laundry, parking, other


def create_guest_payment_router(db, require_roles):
    router = APIRouter()
    stripe_api_key = os.environ.get("STRIPE_API_KEY", "")

    # ==================== SEND PAYMENT LINK ====================

    @router.post("/guest-payment/send-link")
    async def send_payment_link(data: SendPaymentLinkRequest, request: Request, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Admin: Send a payment link to a guest for their booking"""
        booking = await db.bookings.find_one({"id": data.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        # Check for existing active link
        existing = await db.payment_links.find_one({
            "booking_id": data.booking_id, "status": "pending"
        }, {"_id": 0})
        if existing:
            # Cancel old link
            await db.payment_links.update_one(
                {"id": existing["id"]}, {"$set": {"status": "cancelled"}}
            )

        # Calculate total: room charge + extra charges
        room_amount = float(booking.get("total_price", 0))
        extra_total = sum(float(c.get("amount", 0)) for c in data.extra_charges)
        total_amount = data.custom_amount if data.custom_amount is not None else (room_amount + extra_total)

        # Get POS charges for this booking (room charges)
        pos_charges = await db.pos_orders.find({
            "property_id": booking.get("property_id", ""),
            "room_number": booking.get("booking_ref", ""),
            "payment_status": {"$ne": "paid"}
        }, {"_id": 0}).to_list(50)

        pos_total = sum(float(o.get("total", 0)) for o in pos_charges)
        total_amount += pos_total

        # Already paid amount
        paid_txns = await db.payment_transactions.find({
            "reference_id": data.booking_id, "payment_status": "paid"
        }, {"_id": 0}).to_list(10)
        already_paid = sum(float(t.get("amount", 0)) for t in paid_txns)

        outstanding = max(0, total_amount - already_paid)

        from models import PaymentLink
        link = PaymentLink(
            booking_id=data.booking_id,
            booking_ref=booking.get("booking_ref", ""),
            property_id=booking.get("property_id", ""),
            guest_name=booking.get("guest_name", ""),
            guest_email=booking.get("guest_email", ""),
            amount=round(outstanding, 2),
            currency=booking.get("currency", "GBP"),
            extra_charges=data.extra_charges,
            notes=data.notes,
            created_by=current_user.get("email", ""),
        )
        doc = link.model_dump()
        await db.payment_links.insert_one(doc)
        doc.pop("_id", None)

        # Get property name for email
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": booking.get("property_id", "")}, {"_id": 0}) or {}
        prop_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")

        # Send email in background
        host_url = str(request.base_url).rstrip("/")
        base_url = os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))
        asyncio.create_task(_send_payment_email(doc, prop_name, base_url))

        return {
            "status": "sent",
            "payment_link_id": doc["id"],
            "token": doc["token"],
            "amount": doc["amount"],
            "url": f"{base_url}/pay/{doc['token']}",
        }

    # ==================== VIEW FOLIO (PUBLIC) ====================

    @router.get("/guest-payment/folio/{token}")
    async def get_guest_folio(token: str):
        """Public: Guest views their folio via payment link"""
        link = await db.payment_links.find_one({"token": token}, {"_id": 0})
        if not link:
            raise HTTPException(404, "Payment link not found or expired")

        if link.get("status") == "paid":
            return {"status": "paid", "message": "This invoice has already been paid", "paid_at": link.get("paid_at", "")}

        if link.get("status") in ("expired", "cancelled"):
            raise HTTPException(410, "This payment link has expired")

        # Check expiry
        if link.get("expires_at") and link["expires_at"] < datetime.now(timezone.utc).isoformat():
            await db.payment_links.update_one({"token": token}, {"$set": {"status": "expired"}})
            raise HTTPException(410, "This payment link has expired")

        # Get booking details
        booking = await db.bookings.find_one({"id": link["booking_id"]}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        # Get room type
        room = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0})

        # Get property info
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": booking.get("property_id", "")}, {"_id": 0}) or {}
        prop_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")

        # Calculate nights
        try:
            ci = datetime.fromisoformat(booking["check_in"])
            co = datetime.fromisoformat(booking["check_out"])
            nights = max(1, (co - ci).days)
        except (ValueError, KeyError):
            nights = 1

        # Build folio items
        folio_items = []
        room_name = room.get("name", "Room") if room else "Room"
        room_rate = float(booking.get("total_price", 0)) / max(nights * booking.get("rooms", 1), 1)

        for n in range(nights):
            folio_items.append({
                "description": f"{room_name} — Night {n+1}",
                "category": "room",
                "amount": round(room_rate * booking.get("rooms", 1), 2),
            })

        # Extra charges from the link
        for charge in link.get("extra_charges", []):
            folio_items.append({
                "description": charge.get("description", "Extra charge"),
                "category": charge.get("category", "other"),
                "amount": float(charge.get("amount", 0)),
            })

        # POS charges billed to room
        pos_orders = await db.pos_orders.find({
            "property_id": booking.get("property_id", ""),
            "room_number": booking.get("booking_ref", ""),
            "payment_status": {"$ne": "paid"}
        }, {"_id": 0}).to_list(50)

        for order in pos_orders:
            folio_items.append({
                "description": f"Restaurant — {order.get('outlet_name', 'POS')} (#{order.get('order_number', '')})",
                "category": "restaurant",
                "amount": float(order.get("total", 0)),
            })

        # Previous payments
        paid_txns = await db.payment_transactions.find({
            "reference_id": link["booking_id"], "payment_status": "paid"
        }, {"_id": 0}).to_list(10)
        payments_made = [{
            "date": t.get("paid_at", t.get("created_at", "")),
            "method": t.get("payment_method", ""),
            "amount": float(t.get("amount", 0)),
        } for t in paid_txns]

        total_charges = sum(item["amount"] for item in folio_items)
        total_paid = sum(p["amount"] for p in payments_made)
        balance_due = round(max(0, total_charges - total_paid), 2)

        return {
            "status": "pending",
            "token": token,
            "hotel_name": prop_name,
            "hotel_logo": ts.get("logo_url", ""),
            "hotel_address": ts.get("address", (prop or {}).get("address", "")),
            "hotel_phone": ts.get("contact_phone", ""),
            "hotel_email": ts.get("contact_email", ""),
            "booking": {
                "booking_ref": booking.get("booking_ref", ""),
                "guest_name": booking.get("guest_name", ""),
                "guest_email": booking.get("guest_email", ""),
                "check_in": booking.get("check_in", ""),
                "check_out": booking.get("check_out", ""),
                "nights": nights,
                "rooms": booking.get("rooms", 1),
                "adults": booking.get("adults", 1),
                "children": booking.get("children", 0),
                "room_name": room_name,
                "payment_status": booking.get("payment_status", "pending"),
            },
            "folio_items": folio_items,
            "payments_made": payments_made,
            "total_charges": round(total_charges, 2),
            "total_paid": round(total_paid, 2),
            "balance_due": balance_due,
            "currency": link.get("currency", "GBP"),
            "notes": link.get("notes", ""),
            "expires_at": link.get("expires_at", ""),
        }

    # ==================== PAY VIA STRIPE (PUBLIC) ====================

    @router.post("/guest-payment/pay/{token}")
    async def pay_guest_folio(token: str, request: Request):
        """Public: Guest initiates Stripe payment for their folio"""
        link = await db.payment_links.find_one({"token": token}, {"_id": 0})
        if not link:
            raise HTTPException(404, "Payment link not found")
        if link.get("status") == "paid":
            raise HTTPException(400, "This invoice has already been paid")
        if link.get("status") in ("expired", "cancelled"):
            raise HTTPException(410, "This payment link has expired")

        # Recalculate balance
        folio = await get_guest_folio(token)
        amount = folio["balance_due"]

        if amount <= 0:
            # Mark as paid if nothing owed
            await db.payment_links.update_one(
                {"token": token},
                {"$set": {"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}}
            )
            return {"status": "already_paid", "message": "No balance due"}

        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)

        base_url = os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))
        success_url = f"{base_url}/pay/{token}?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/pay/{token}?payment=cancelled"

        checkout_req = CheckoutSessionRequest(
            amount=amount,
            currency=link.get("currency", "gbp").lower(),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "guest_folio",
                "booking_id": link["booking_id"],
                "booking_ref": link.get("booking_ref", ""),
                "guest_name": link.get("guest_name", ""),
                "guest_email": link.get("guest_email", ""),
                "property_id": link.get("property_id", ""),
                "payment_link_id": link["id"],
            }
        )

        session = await stripe_checkout.create_checkout_session(checkout_req)

        # Create payment transaction record
        tx = {
            "id": str(uuid.uuid4()),
            "session_id": session.session_id,
            "type": "guest_folio",
            "reference_id": link["booking_id"],
            "reference_number": link.get("booking_ref", ""),
            "property_id": link.get("property_id", ""),
            "amount": amount,
            "currency": link.get("currency", "GBP"),
            "guest_name": link.get("guest_name", ""),
            "guest_email": link.get("guest_email", ""),
            "payment_method": "stripe",
            "payment_status": "initiated",
            "payment_link_id": link["id"],
            "metadata": checkout_req.metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(tx)

        return {"url": session.url, "session_id": session.session_id}

    # ==================== CHECK PAYMENT STATUS (PUBLIC) ====================

    @router.get("/guest-payment/status/{token}")
    async def check_folio_payment_status(token: str, session_id: str = "", request: Request = None):
        """Public: Check if the folio payment was completed"""
        link = await db.payment_links.find_one({"token": token}, {"_id": 0})
        if not link:
            raise HTTPException(404, "Payment link not found")

        if link.get("status") == "paid":
            return {"status": "paid", "paid_at": link.get("paid_at", "")}

        if session_id:
            # Check Stripe session
            tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            if tx and tx.get("payment_status") == "paid":
                # Mark payment link as paid
                await db.payment_links.update_one(
                    {"token": token},
                    {"$set": {"status": "paid", "paid_at": tx.get("paid_at", datetime.now(timezone.utc).isoformat())}}
                )
                await db.bookings.update_one(
                    {"id": link["booking_id"]},
                    {"$set": {"payment_status": "paid", "payment_method": "stripe"}}
                )
                return {"status": "paid", "paid_at": tx.get("paid_at", "")}

            # Try polling Stripe
            if stripe_api_key:
                try:
                    host_url = str(request.base_url).rstrip("/")
                    webhook_url = f"{host_url}/api/webhook/stripe"
                    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
                    status = await stripe_checkout.get_checkout_status(session_id)

                    if status.payment_status == "paid":
                        now = datetime.now(timezone.utc).isoformat()
                        await db.payment_transactions.update_one(
                            {"session_id": session_id},
                            {"$set": {"payment_status": "paid", "paid_at": now}}
                        )
                        await db.payment_links.update_one(
                            {"token": token},
                            {"$set": {"status": "paid", "paid_at": now}}
                        )
                        await db.bookings.update_one(
                            {"id": link["booking_id"]},
                            {"$set": {"payment_status": "paid", "payment_method": "stripe"}}
                        )
                        return {"status": "paid", "paid_at": now}

                    return {"status": status.status, "payment_status": status.payment_status}
                except Exception as e:
                    logger.error(f"Stripe status check: {e}")

        return {"status": link.get("status", "pending")}

    # ==================== ADMIN: LIST PAYMENT LINKS ====================

    @router.get("/guest-payment/links/{property_id}")
    async def list_payment_links(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Admin: List all payment links for a property"""
        docs = await db.payment_links.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
        return docs

    # ==================== ADMIN: ADD EXTRA CHARGE ====================

    @router.post("/guest-payment/add-charge/{link_id}")
    async def add_extra_charge(link_id: str, charge: AddChargeRequest, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Admin: Add an extra charge to a payment link"""
        link = await db.payment_links.find_one({"id": link_id}, {"_id": 0})
        if not link:
            raise HTTPException(404, "Payment link not found")
        if link.get("status") != "pending":
            raise HTTPException(400, "Cannot add charges to a paid/expired link")

        charge_doc = {"description": charge.description, "amount": charge.amount, "category": charge.category}
        new_amount = round(link.get("amount", 0) + charge.amount, 2)

        await db.payment_links.update_one(
            {"id": link_id},
            {"$push": {"extra_charges": charge_doc}, "$set": {"amount": new_amount}}
        )
        return {"status": "added", "new_amount": new_amount}

    # ==================== EMAIL HELPER ====================

    async def _send_payment_email(link: dict, hotel_name: str, base_url: str):
        """Send payment link email to guest"""
        if not resend.api_key or resend.api_key == 're_123456789':
            logger.info("No Resend API key, skipping payment link email")
            return

        pay_url = f"{base_url}/pay/{link['token']}"
        currency_symbol = "£" if link.get("currency", "GBP") == "GBP" else "$" if link.get("currency") == "USD" else "€" if link.get("currency") == "EUR" else link.get("currency", "")

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
          <div style="background:linear-gradient(135deg,#1e3a5f,#2d5f8a);color:#fff;padding:32px;text-align:center;">
            <h1 style="margin:0;font-size:22px;">{hotel_name}</h1>
            <p style="margin:8px 0 0;opacity:0.8;font-size:14px;">Payment Request</p>
          </div>
          <div style="padding:28px;">
            <p style="font-size:15px;color:#333;">Dear {link.get('guest_name', 'Guest')},</p>
            <p style="font-size:14px;color:#555;line-height:1.6;">
              Please find your payment details below for booking <strong>{link.get('booking_ref', '')}</strong>.
              You can review your folio and complete your payment securely online.
            </p>
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:24px 0;text-align:center;">
              <p style="margin:0;font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;">Amount Due</p>
              <p style="margin:8px 0;font-size:36px;font-weight:bold;color:#1e3a5f;">{currency_symbol}{link.get('amount', 0):.2f}</p>
              <p style="margin:0;font-size:12px;color:#94a3b8;">Booking Ref: {link.get('booking_ref', '')}</p>
            </div>
            {f'<p style="font-size:13px;color:#666;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:12px;">Note: {link.get("notes", "")}</p>' if link.get('notes') else ''}
            <a href="{pay_url}" style="display:block;background:#1e3a5f;color:#fff;text-decoration:none;padding:16px;border-radius:8px;text-align:center;font-size:16px;font-weight:600;margin:24px 0;">
              View Folio & Pay Now
            </a>
            <p style="font-size:11px;color:#94a3b8;text-align:center;">This link expires in 7 days. Payments are processed securely via Stripe.</p>
          </div>
          <div style="background:#f8fafc;padding:16px;text-align:center;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;">
            <p style="margin:0;">Powered by MyHotelBox — Secure Guest Payments</p>
          </div>
        </div>
        """

        try:
            await asyncio.to_thread(resend.Emails.send, {
                "from": SENDER_EMAIL,
                "to": [link.get("guest_email", "")],
                "subject": f"Payment Request — {link.get('booking_ref', '')} — {hotel_name}",
                "html": html,
            })
            # Update sent_at
            await db.payment_links.update_one(
                {"id": link["id"]},
                {"$set": {"sent_at": datetime.now(timezone.utc).isoformat()}}
            )
            logger.info(f"Payment link email sent to {link.get('guest_email')} for {link.get('booking_ref')}")
        except Exception as e:
            logger.error(f"Failed to send payment email: {e}")

    # ==================== PAYMENT REMINDER EMAIL ====================

    async def _send_reminder_email(link: dict, booking: dict, hotel_name: str, base_url: str, hours_until_checkout: int):
        """Send a payment reminder email to guest before checkout"""
        if not resend.api_key or resend.api_key == 're_123456789':
            logger.info("No Resend API key, skipping reminder email")
            return

        pay_url = f"{base_url}/pay/{link['token']}"
        currency_symbol = "£" if link.get("currency", "GBP") == "GBP" else "$" if link.get("currency") == "USD" else "€" if link.get("currency") == "EUR" else link.get("currency", "")

        try:
            co_date = datetime.fromisoformat(booking.get("check_out", "")).strftime("%A, %d %B")
        except Exception:
            co_date = booking.get("check_out", "")

        urgency_text = "tomorrow" if hours_until_checkout <= 24 else f"in {hours_until_checkout // 24} days"

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">
          <div style="background:linear-gradient(135deg,#92400e,#b45309);color:#fff;padding:32px;text-align:center;">
            <h1 style="margin:0;font-size:22px;">{hotel_name}</h1>
            <p style="margin:8px 0 0;opacity:0.9;font-size:14px;">Payment Reminder</p>
          </div>
          <div style="padding:28px;">
            <p style="font-size:15px;color:#333;">Dear {link.get('guest_name', 'Guest')},</p>
            <p style="font-size:14px;color:#555;line-height:1.6;">
              This is a friendly reminder that your checkout date (<strong>{co_date}</strong>) is {urgency_text}.
              You have an outstanding balance for booking <strong>{link.get('booking_ref', '')}</strong>.
            </p>
            <div style="background:#fffbeb;border:2px solid #f59e0b;border-radius:12px;padding:24px;margin:24px 0;text-align:center;">
              <p style="margin:0;font-size:12px;color:#92400e;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Outstanding Balance</p>
              <p style="margin:8px 0;font-size:36px;font-weight:bold;color:#92400e;">{currency_symbol}{link.get('amount', 0):.2f}</p>
              <p style="margin:0;font-size:12px;color:#b45309;">Booking Ref: {link.get('booking_ref', '')}</p>
            </div>
            <p style="font-size:14px;color:#555;line-height:1.6;">
              To ensure a smooth checkout, please settle your balance online before you leave.
              It only takes a minute.
            </p>
            <a href="{pay_url}" style="display:block;background:#b45309;color:#fff;text-decoration:none;padding:16px;border-radius:8px;text-align:center;font-size:16px;font-weight:600;margin:24px 0;">
              Pay Now — {currency_symbol}{link.get('amount', 0):.2f}
            </a>
            <p style="font-size:12px;color:#78716c;text-align:center;">
              If you've already settled this payment, please disregard this message.
              <br/>For any questions, please contact our front desk.
            </p>
          </div>
          <div style="background:#f8fafc;padding:16px;text-align:center;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;">
            <p style="margin:0;">Powered by MyHotelBox — Secure Guest Payments</p>
          </div>
        </div>
        """

        try:
            await asyncio.to_thread(resend.Emails.send, {
                "from": SENDER_EMAIL,
                "to": [link.get("guest_email", "")],
                "subject": f"Payment Reminder — {link.get('booking_ref', '')} — {hotel_name}",
                "html": html,
            })
            logger.info(f"Reminder email sent to {link.get('guest_email')} for {link.get('booking_ref')}")
        except Exception as e:
            logger.error(f"Failed to send reminder: {e}")

    # ==================== REMINDER SETTINGS ====================

    @router.get("/guest-payment/reminder-settings/{property_id}")
    async def get_reminder_settings(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Admin: Get payment reminder settings"""
        doc = await db.payment_reminder_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            default = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "enabled": True,
                "first_reminder_hours": 24,
                "second_reminder_hours": 6,
                "auto_send_on_checkout_day": True,
                "send_to_unpaid_bookings": True,
                "max_reminders_per_booking": 3,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.payment_reminder_settings.insert_one(default)
            default.pop("_id", None)
            return default
        return doc

    @router.put("/guest-payment/reminder-settings/{property_id}")
    async def update_reminder_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Admin: Update payment reminder settings"""
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.payment_reminder_settings.update_one(
            {"property_id": property_id}, {"$set": updates}, upsert=True
        )
        doc = await db.payment_reminder_settings.find_one({"property_id": property_id}, {"_id": 0})
        return doc

    # ==================== SEND REMINDERS (MANUAL OR AUTO) ====================

    @router.post("/guest-payment/send-reminders/{property_id}")
    async def send_payment_reminders(property_id: str, request: Request, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Admin: Trigger payment reminders for all unpaid bookings approaching checkout"""
        settings_doc = await db.payment_reminder_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not settings_doc or not settings_doc.get("enabled", True):
            return {"sent": 0, "message": "Reminders are disabled"}

        first_hours = settings_doc.get("first_reminder_hours", 24)
        max_reminders = settings_doc.get("max_reminders_per_booking", 3)

        from datetime import timedelta
        now = datetime.now(timezone.utc)
        # Find unpaid bookings with checkout within the reminder window
        cutoff = (now + timedelta(hours=first_hours)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")

        unpaid_bookings = await db.bookings.find({
            "property_id": property_id,
            "payment_status": {"$ne": "paid"},
            "status": {"$nin": ["cancelled"]},
            "check_out": {"$gte": today, "$lte": cutoff},
        }, {"_id": 0}).to_list(200)

        host_url = str(request.base_url).rstrip("/")
        base_url = os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))

        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")

        sent = 0
        skipped = 0
        results = []

        for booking in unpaid_bookings:
            booking_id = booking.get("id", "")
            booking_ref = booking.get("booking_ref", "")

            # Check how many reminders already sent
            reminder_count = await db.payment_reminders_log.count_documents({
                "booking_id": booking_id
            })
            if reminder_count >= max_reminders:
                skipped += 1
                results.append({"booking_ref": booking_ref, "status": "max_reached", "reminders_sent": reminder_count})
                continue

            # Find existing payment link or create one
            link = await db.payment_links.find_one({
                "booking_id": booking_id, "status": "pending"
            }, {"_id": 0})

            if not link:
                # Auto-create a payment link for this booking
                from models import PaymentLink
                new_link = PaymentLink(
                    booking_id=booking_id,
                    booking_ref=booking_ref,
                    property_id=property_id,
                    guest_name=booking.get("guest_name", ""),
                    guest_email=booking.get("guest_email", ""),
                    amount=float(booking.get("total_price", 0)),
                    currency=booking.get("currency", "GBP"),
                    notes="Auto-generated reminder",
                    created_by="system",
                )
                link_doc = new_link.model_dump()
                await db.payment_links.insert_one(link_doc)
                link_doc.pop("_id", None)
                link = link_doc

            if not link.get("guest_email"):
                skipped += 1
                results.append({"booking_ref": booking_ref, "status": "no_email"})
                continue

            # Calculate hours until checkout
            try:
                co = datetime.fromisoformat(booking["check_out"])
                if co.tzinfo is None:
                    co = datetime(co.year, co.month, co.day, 11, 0, tzinfo=timezone.utc)
                hours_left = max(0, int((co - now).total_seconds() / 3600))
            except Exception:
                hours_left = 24

            # Send reminder
            asyncio.create_task(_send_reminder_email(link, booking, hotel_name, base_url, hours_left))

            # Log the reminder
            await db.payment_reminders_log.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "booking_ref": booking_ref,
                "property_id": property_id,
                "guest_email": link.get("guest_email", ""),
                "guest_name": link.get("guest_name", ""),
                "amount": link.get("amount", 0),
                "hours_until_checkout": hours_left,
                "reminder_number": reminder_count + 1,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })

            sent += 1
            results.append({
                "booking_ref": booking_ref,
                "guest_name": link.get("guest_name", ""),
                "guest_email": link.get("guest_email", ""),
                "amount": link.get("amount", 0),
                "hours_left": hours_left,
                "reminder_number": reminder_count + 1,
                "status": "sent",
            })

        return {
            "sent": sent,
            "skipped": skipped,
            "total_unpaid": len(unpaid_bookings),
            "results": results,
            "message": f"Sent {sent} reminder(s), skipped {skipped}",
        }

    # ==================== REMINDER HISTORY ====================

    @router.get("/guest-payment/reminder-history/{property_id}")
    async def get_reminder_history(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Admin: View reminder send history"""
        docs = await db.payment_reminders_log.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("sent_at", -1).to_list(100)
        return docs

    return router
