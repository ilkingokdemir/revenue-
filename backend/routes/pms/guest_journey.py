"""
Guest Journey — Pre-arrival registration, ID upload, welcome pack, satisfaction checks
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import uuid
import secrets
import os
import base64
import asyncio
import logging
import resend

logger = logging.getLogger(__name__)
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
UPLOAD_DIR = "/app/backend/uploads/ids"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_guest_journey_router(db, require_roles):
    router = APIRouter()

    # ==================== SEND REGISTRATION LINK ====================

    @router.post("/guest-journey/send-registration/{booking_id}")
    async def send_registration_link(booking_id: str, request: Request, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Send pre-arrival registration link to guest"""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        token = secrets.token_urlsafe(32)
        reg = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "booking_ref": booking.get("booking_ref", ""),
            "property_id": booking.get("property_id", ""),
            "guest_name": booking.get("guest_name", ""),
            "guest_email": booking.get("guest_email", ""),
            "guest_phone": booking.get("guest_phone", ""),
            "token": token,
            "status": "pending",  # pending, completed
            "form_data": {},
            "id_uploaded": False,
            "id_file_path": "",
            "terms_accepted": False,
            "signature": "",
            "welcome_sent": False,
            "satisfaction_check_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": "",
        }
        await db.guest_registrations.insert_one(reg)
        reg.pop("_id", None)

        host_url = str(request.base_url).rstrip("/")
        base_url = os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))
        reg_url = f"{base_url}/register/{token}"

        # Get property info
        prop = await db.properties.find_one({"id": booking.get("property_id")}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": booking.get("property_id")}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")

        # Send email
        asyncio.create_task(_send_registration_email(reg, hotel_name, reg_url, booking))

        return {"status": "sent", "token": token, "url": reg_url}

    # ==================== SHARE REGISTRATION LINK ====================

    @router.post("/guest-journey/share-link/{registration_id}")
    async def share_registration_link(registration_id: str, data: Dict, request: Request, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Share registration link via email, SMS, or WhatsApp"""
        reg = await db.guest_registrations.find_one({"id": registration_id}, {"_id": 0})
        if not reg:
            raise HTTPException(404, "Registration not found")

        channel = data.get("channel", "email")  # email, sms, whatsapp
        phone = data.get("phone", reg.get("guest_phone", ""))
        email_addr = data.get("email", reg.get("guest_email", ""))

        host_url = str(request.base_url).rstrip("/")
        base_url = os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))
        reg_url = f"{base_url}/register/{reg['token']}"

        prop = await db.properties.find_one({"id": reg.get("property_id")}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": reg.get("property_id")}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")
        booking = await db.bookings.find_one({"id": reg.get("booking_id")}, {"_id": 0}) or {}

        if channel == "email":
            asyncio.create_task(_send_registration_email(reg, hotel_name, reg_url, booking))
            return {"status": "sent", "channel": "email"}

        message = f"{hotel_name} — Complete your pre-arrival registration here: {reg_url}"

        if channel == "sms":
            settings = await db.channel_settings.find_one({"property_id": reg.get("property_id")}, {"_id": 0}) or {}
            account_sid = settings.get("twilio_account_sid", "")
            auth_token = settings.get("twilio_auth_token", "")
            from_number = settings.get("twilio_phone_number", "")
            if not all([account_sid, auth_token, from_number, phone]):
                return {"status": "skipped", "channel": "sms", "reason": "SMS not configured or no phone number"}
            try:
                import httpx
                async with httpx.AsyncClient() as client_http:
                    resp = await client_http.post(
                        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                        auth=(account_sid, auth_token),
                        data={"From": from_number, "To": phone, "Body": message},
                    )
                    if resp.status_code in (200, 201):
                        return {"status": "sent", "channel": "sms"}
                    return {"status": "failed", "channel": "sms", "reason": resp.text}
            except Exception as e:
                logger.error(f"SMS send error: {e}")
                return {"status": "failed", "channel": "sms", "reason": str(e)}

        if channel == "whatsapp":
            settings = await db.channel_settings.find_one({"property_id": reg.get("property_id")}, {"_id": 0}) or {}
            access_token = settings.get("whatsapp_access_token", "")
            phone_id = settings.get("whatsapp_phone_number_id", "")
            if not all([access_token, phone_id, phone]):
                return {"status": "skipped", "channel": "whatsapp", "reason": "WhatsApp not configured or no phone number"}
            try:
                import httpx
                wa_phone = phone.replace("+", "").replace(" ", "")
                async with httpx.AsyncClient() as client_http:
                    resp = await client_http.post(
                        f"https://graph.facebook.com/v18.0/{phone_id}/messages",
                        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                        json={"messaging_product": "whatsapp", "to": wa_phone, "type": "text", "text": {"body": message}},
                    )
                    if resp.status_code == 200:
                        return {"status": "sent", "channel": "whatsapp"}
                    return {"status": "failed", "channel": "whatsapp", "reason": resp.text}
            except Exception as e:
                logger.error(f"WhatsApp send error: {e}")
                return {"status": "failed", "channel": "whatsapp", "reason": str(e)}

        return {"status": "error", "reason": "Unknown channel"}

    # ==================== GET REGISTRATION FORM (PUBLIC) ====================

    @router.get("/guest-journey/registration/{token}")
    async def get_registration(token: str):
        """Public: Guest views their registration form"""
        reg = await db.guest_registrations.find_one({"token": token}, {"_id": 0})
        if not reg:
            raise HTTPException(404, "Registration link not found")

        booking = await db.bookings.find_one({"id": reg["booking_id"]}, {"_id": 0})
        prop = await db.properties.find_one({"id": reg.get("property_id")}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": reg.get("property_id")}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")

        # Hotel policies
        module_settings = await db.module_settings.find_one({"module": "bookings", "property_id": reg.get("property_id")}, {"_id": 0}) or {}

        return {
            "status": reg.get("status"),
            "token": token,
            "hotel_name": hotel_name,
            "hotel_logo": ts.get("logo_url", ""),
            "hotel_address": ts.get("address", (prop or {}).get("address", "")),
            "booking": {
                "booking_ref": booking.get("booking_ref", "") if booking else "",
                "guest_name": booking.get("guest_name", "") if booking else "",
                "guest_email": booking.get("guest_email", "") if booking else "",
                "check_in": booking.get("check_in", "") if booking else "",
                "check_out": booking.get("check_out", "") if booking else "",
                "rooms": booking.get("rooms", 1) if booking else 1,
            },
            "form_data": reg.get("form_data", {}),
            "id_uploaded": reg.get("id_uploaded", False),
            "terms_accepted": reg.get("terms_accepted", False),
            "policies": {
                "check_in_time": module_settings.get("check_in_time", "15:00"),
                "check_out_time": module_settings.get("check_out_time", "11:00"),
                "cancellation_hours": module_settings.get("cancellation_hours", 24),
            },
        }

    # ==================== SUBMIT REGISTRATION (PUBLIC) ====================

    @router.post("/guest-journey/registration/{token}")
    async def submit_registration(token: str, data: Dict):
        """Public: Guest submits their registration form"""
        reg = await db.guest_registrations.find_one({"token": token}, {"_id": 0})
        if not reg:
            raise HTTPException(404, "Registration not found")

        form_data = data.get("form_data", {})
        terms = data.get("terms_accepted", False)
        signature = data.get("signature", "")

        updates = {
            "form_data": form_data,
            "terms_accepted": terms,
            "signature": signature,
            "status": "completed" if terms else "pending",
            "completed_at": datetime.now(timezone.utc).isoformat() if terms else "",
        }
        await db.guest_registrations.update_one({"token": token}, {"$set": updates})

        # Update booking with guest details
        if form_data:
            booking_updates = {}
            if form_data.get("nationality"): booking_updates["nationality"] = form_data["nationality"]
            if form_data.get("date_of_birth"): booking_updates["date_of_birth"] = form_data["date_of_birth"]
            if form_data.get("address"): booking_updates["guest_address"] = form_data["address"]
            if booking_updates:
                await db.bookings.update_one({"id": reg["booking_id"]}, {"$set": booking_updates})

        # Send welcome pack if completed
        if terms:
            prop = await db.properties.find_one({"id": reg.get("property_id")}, {"_id": 0})
            ts = await db.template_settings.find_one({"property_id": reg.get("property_id")}, {"_id": 0}) or {}
            hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")
            booking = await db.bookings.find_one({"id": reg["booking_id"]}, {"_id": 0}) or {}
            asyncio.create_task(_send_welcome_pack(reg, hotel_name, booking))
            await db.guest_registrations.update_one({"token": token}, {"$set": {"welcome_sent": True}})

        return {"status": "submitted", "completed": terms}

    # ==================== UPLOAD ID (PUBLIC) ====================

    @router.post("/guest-journey/upload-id/{token}")
    async def upload_guest_id(token: str, file: UploadFile = File(...)):
        """Public: Guest uploads their ID document"""
        reg = await db.guest_registrations.find_one({"token": token}, {"_id": 0})
        if not reg:
            raise HTTPException(404, "Registration not found")

        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
        filename = f"{reg['id']}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        await db.guest_registrations.update_one(
            {"token": token},
            {"$set": {"id_uploaded": True, "id_file_path": filepath, "id_filename": file.filename}}
        )
        return {"status": "uploaded", "filename": file.filename}

    # ==================== RECEPTION: UPLOAD ID FOR GUEST ====================

    @router.post("/guest-journey/reception-upload-id/{booking_id}")
    async def reception_upload_id(booking_id: str, file: UploadFile = File(...), current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Reception: Upload guest ID during check-in"""
        reg = await db.guest_registrations.find_one({"booking_id": booking_id}, {"_id": 0})
        if not reg:
            # Create registration record
            booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
            if not booking:
                raise HTTPException(404, "Booking not found")
            reg = {
                "id": str(uuid.uuid4()), "booking_id": booking_id,
                "booking_ref": booking.get("booking_ref", ""), "property_id": booking.get("property_id", ""),
                "guest_name": booking.get("guest_name", ""), "guest_email": booking.get("guest_email", ""),
                "token": secrets.token_urlsafe(32), "status": "completed",
                "form_data": {}, "id_uploaded": False, "terms_accepted": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.guest_registrations.insert_one(reg)
            reg.pop("_id", None)

        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
        filename = f"{reg['id']}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        await db.guest_registrations.update_one(
            {"id": reg["id"]},
            {"$set": {"id_uploaded": True, "id_file_path": filepath, "id_filename": file.filename, "uploaded_by": current_user.get("email", "")}}
        )
        return {"status": "uploaded", "filename": file.filename}

    # ==================== LIST REGISTRATIONS ====================

    @router.get("/guest-journey/registrations/{property_id}")
    async def list_registrations(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.guest_registrations.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    # ==================== KIOSK: PROPERTY INFO (PUBLIC) ====================

    @router.get("/guest-journey/kiosk-info/{property_id}")
    async def kiosk_info(property_id: str):
        """Public: Get property name and branding for kiosk display.
        When property_id='all', returns a generic kiosk header so a single tablet
        can serve walk-ins across multiple properties (lookup will span all)."""
        if property_id == "all":
            # Multi-property mode: pick first property as the default visual brand,
            # or fall back to a generic name.
            ts = await db.template_settings.find_one({"property_id": "all"}, {"_id": 0}) or {}
            if ts.get("hotel_name"):
                return {"hotel_name": ts["hotel_name"], "logo_url": ts.get("logo_url", "")}
            first_prop = await db.properties.find_one({}, {"_id": 0, "name": 1})
            return {
                "hotel_name": (first_prop or {}).get("name") or "Self Check-In",
                "logo_url": "",
            }
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")
        return {"hotel_name": hotel_name, "logo_url": ts.get("logo_url", "")}

    # ==================== KIOSK: LOOKUP BOOKING (PUBLIC) ====================

    @router.get("/guest-journey/kiosk-lookup/{property_id}")
    async def kiosk_lookup(property_id: str, q: str = ""):
        """Public: Look up booking by ref or guest name for kiosk check-in.
        property_id='all' searches across every property."""
        if not q or len(q) < 2:
            return []
        query = {
            "status": {"$in": ["confirmed", "pending", "checked_in"]},
            "$or": [
                {"booking_ref": {"$regex": q, "$options": "i"}},
                {"guest_name": {"$regex": q, "$options": "i"}},
                {"guest_email": {"$regex": q, "$options": "i"}},
            ]
        }
        if property_id != "all":
            query["property_id"] = property_id
        bookings = await db.bookings.find(query, {"_id": 0}).sort("check_in", 1).to_list(20)
        results = []
        for b in bookings:
            reg = await db.guest_registrations.find_one({"booking_id": b["id"]}, {"_id": 0})
            results.append({
                "booking_id": b["id"],
                "booking_ref": b.get("booking_ref", ""),
                "guest_name": b.get("guest_name", ""),
                "guest_email": b.get("guest_email", ""),
                "check_in": b.get("check_in", ""),
                "check_out": b.get("check_out", ""),
                "rooms": b.get("rooms", 1),
                "property_id": b.get("property_id", ""),
                "registration_token": reg.get("token") if reg else None,
                "registration_status": reg.get("status") if reg else None,
            })
        return results

    # ==================== KIOSK: CREATE WALK-IN REGISTRATION (PUBLIC) ====================

    @router.post("/guest-journey/kiosk-register/{property_id}")
    async def kiosk_register(property_id: str, data: Dict):
        """Public: Create registration for walk-in guest at kiosk"""
        booking_id = data.get("booking_id")
        if not booking_id:
            raise HTTPException(400, "booking_id required")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        existing = await db.guest_registrations.find_one({"booking_id": booking_id}, {"_id": 0})
        if existing and existing.get("token"):
            return {"token": existing["token"], "status": existing.get("status", "pending")}

        token = secrets.token_urlsafe(32)
        # Always store the registration against the booking's REAL property,
        # never the URL placeholder ("all" for multi-property kiosks).
        real_prop_id = booking.get("property_id") or property_id
        reg = {
            "id": str(uuid.uuid4()), "booking_id": booking_id,
            "booking_ref": booking.get("booking_ref", ""), "property_id": real_prop_id,
            "guest_name": booking.get("guest_name", ""), "guest_email": booking.get("guest_email", ""),
            "guest_phone": booking.get("guest_phone", ""), "token": token,
            "status": "pending", "form_data": {}, "id_uploaded": False,
            "terms_accepted": False, "signature": "", "welcome_sent": False,
            "satisfaction_check_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(), "completed_at": "",
        }
        await db.guest_registrations.insert_one(reg)
        return {"token": token, "status": "pending"}

    @router.get("/guest-journey/kiosk-complete/{token}")
    async def kiosk_check_complete(token: str):
        """Public: Polled by kiosk wrapper to detect when the inner registration
        iframe has completed. When status='completed', returns the assigned room
        + QR code payload so the kiosk can show a 'Welcome, here's your room' screen.
        """
        reg = await db.guest_registrations.find_one({"token": token}, {"_id": 0})
        if not reg:
            raise HTTPException(404, "Registration not found")
        status = reg.get("status", "pending")
        if status != "completed":
            return {"status": status, "completed": False}

        booking = await db.bookings.find_one({"id": reg["booking_id"]}, {"_id": 0}) or {}
        room = await db.rooms.find_one({"id": booking.get("room_id", "")}, {"_id": 0}) or {}
        room_type = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0}) or {}

        # QR payload — enough info for a smart-lock integration to validate access,
        # but opaque enough that QR scanners outside our system can't abuse it.
        qr_payload = {
            "booking_id": reg["booking_id"],
            "booking_ref": reg.get("booking_ref", ""),
            "room_id": booking.get("room_id", ""),
            "token": token[:24],
        }
        import json
        import urllib.parse
        qr_text = urllib.parse.quote(json.dumps(qr_payload), safe="")
        # Use an external QR service so the kiosk stays lightweight (no server-side PNG generation)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=280x280&data={qr_text}"

        return {
            "status": "completed",
            "completed": True,
            "guest_name": booking.get("guest_name", ""),
            "room_name": room.get("name", "—"),
            "room_type": room_type.get("name", "Room"),
            "check_in": booking.get("check_in", ""),
            "check_out": booking.get("check_out", ""),
            "qr_url": qr_url,
        }

    # ==================== WELCOME INFO SETTINGS ====================

    @router.get("/guest-journey/welcome-info/{property_id}")
    async def get_welcome_info(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        info = await db.welcome_info.find_one({"property_id": property_id}, {"_id": 0})
        if not info:
            return {
                "property_id": property_id,
                "hotel_policies": ["Check-in: from 3:00 PM", "Check-out: by 11:00 AM", "WiFi: Available in all areas (password at reception)", "Breakfast: 7:00 AM - 10:30 AM", "Parking: Available on request"],
                "city_info": ["Nearest tube/metro: 5 min walk", "Airport shuttle available on request", "Ask reception for restaurant recommendations", "City tour bookings at front desk"],
                "custom_message": "",
            }
        return info

    @router.put("/guest-journey/welcome-info/{property_id}")
    async def update_welcome_info(property_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        update = {
            "property_id": property_id,
            "hotel_policies": data.get("hotel_policies", []),
            "city_info": data.get("city_info", []),
            "custom_message": data.get("custom_message", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.welcome_info.update_one({"property_id": property_id}, {"$set": update}, upsert=True)
        return {"status": "saved"}

    # ==================== SATISFACTION CHECK ====================

    @router.post("/guest-journey/send-satisfaction-check/{property_id}")
    async def send_satisfaction_checks(property_id: str, request: Request, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Send satisfaction check to guests after first night"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        # Find guests who checked in yesterday (first night completed)
        bookings = await db.bookings.find({
            "property_id": property_id,
            "check_in": yesterday,
            "status": {"$in": ["confirmed", "checked_in"]},
        }, {"_id": 0}).to_list(100)

        host_url = str(request.base_url).rstrip("/")
        base_url = os.environ.get("BASE_URL", os.environ.get("REACT_APP_BACKEND_URL", host_url))
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")

        sent = 0
        for booking in bookings:
            # Check if already sent
            reg = await db.guest_registrations.find_one({"booking_id": booking["id"]}, {"_id": 0})
            if reg and reg.get("satisfaction_check_sent"):
                continue

            token = secrets.token_urlsafe(16)
            feedback_url = f"{base_url}/feedback/{token}"

            # Save feedback token
            await db.satisfaction_checks.insert_one({
                "id": str(uuid.uuid4()), "token": token,
                "booking_id": booking["id"], "booking_ref": booking.get("booking_ref", ""),
                "property_id": property_id, "guest_name": booking.get("guest_name", ""),
                "guest_email": booking.get("guest_email", ""),
                "status": "sent", "response": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            # Mark as sent
            if reg:
                await db.guest_registrations.update_one({"id": reg["id"]}, {"$set": {"satisfaction_check_sent": True}})

            asyncio.create_task(_send_satisfaction_email(booking, hotel_name, feedback_url))

            # Also try SMS and WhatsApp
            phone = booking.get("guest_phone", "")
            if phone:
                sms_msg = f"{hotel_name}: How's your stay? Everything OK? Tap here: {feedback_url}?r=all_good or need help? {feedback_url}?r=need_help"
                asyncio.create_task(_send_satisfaction_sms(property_id, phone, sms_msg))
                asyncio.create_task(_send_satisfaction_whatsapp(property_id, phone, sms_msg))

            sent += 1

        return {"sent": sent, "total_eligible": len(bookings)}

    # ==================== GUEST FEEDBACK RESPONSE (PUBLIC) ====================

    @router.get("/guest-journey/feedback/{token}")
    async def get_feedback_form(token: str):
        check = await db.satisfaction_checks.find_one({"token": token}, {"_id": 0})
        if not check:
            raise HTTPException(404, "Not found")
        prop = await db.properties.find_one({"id": check.get("property_id")}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": check.get("property_id")}, {"_id": 0}) or {}
        return {
            "token": token, "status": check.get("status"),
            "guest_name": check.get("guest_name"), "booking_ref": check.get("booking_ref"),
            "hotel_name": ts.get("hotel_name") or (prop or {}).get("name", "Hotel"),
        }

    @router.post("/guest-journey/feedback/{token}")
    async def submit_feedback(token: str, data: Dict):
        check = await db.satisfaction_checks.find_one({"token": token}, {"_id": 0})
        if not check:
            raise HTTPException(404, "Not found")
        response = data.get("response", "")  # "all_good" or "need_help"
        message = data.get("message", "")

        await db.satisfaction_checks.update_one({"token": token}, {"$set": {
            "status": "responded", "response": response, "message": message,
            "responded_at": datetime.now(timezone.utc).isoformat(),
        }})

        # If guest needs help, create a logbook entry
        if response == "need_help":
            await db.logbook_entries.insert_one({
                "id": str(uuid.uuid4()), "property_id": check.get("property_id"),
                "type": "request", "title": f"Guest needs help — {check.get('guest_name')}",
                "content": message or "Guest indicated they need assistance via satisfaction check",
                "priority": "high", "room_number": "", "guest_name": check.get("guest_name"),
                "shift": "", "status": "open",
                "created_by": "System (Satisfaction Check)",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "follow_up_required": True,
            })

        return {"status": "submitted", "response": response}

    # ==================== LIST SATISFACTION CHECKS ====================

    @router.get("/guest-journey/satisfaction-checks/{property_id}")
    async def list_satisfaction_checks(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.satisfaction_checks.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    # ==================== EMAIL HELPERS ====================

    async def _send_registration_email(reg, hotel_name, reg_url, booking):
        if not resend.api_key or resend.api_key == 're_123456789':
            logger.info("No Resend key, skip registration email")
            return
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
          <div style="background:linear-gradient(135deg,#1e3a5f,#2d5f8a);color:#fff;padding:32px;text-align:center;">
            <h1 style="margin:0;font-size:22px;">{hotel_name}</h1>
            <p style="margin:8px 0 0;opacity:0.8;">Pre-Arrival Registration</p>
          </div>
          <div style="padding:28px;">
            <p>Dear {reg.get('guest_name', 'Guest')},</p>
            <p>We're looking forward to welcoming you on <strong>{booking.get('check_in', '')}</strong>!</p>
            <p>To ensure a smooth check-in, please complete your registration before arrival:</p>
            <a href="{reg_url}" style="display:block;background:#1e3a5f;color:#fff;text-decoration:none;padding:16px;border-radius:8px;text-align:center;font-size:16px;font-weight:600;margin:24px 0;">
              Complete Registration
            </a>
            <p style="font-size:13px;color:#666;">This includes your personal details, ID upload, and hotel terms acceptance.</p>
          </div>
        </div>"""
        try:
            await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [reg.get("guest_email", "")], "subject": f"Complete Your Registration — {hotel_name}", "html": html})
        except Exception as e:
            logger.error(f"Registration email error: {e}")

    async def _send_welcome_pack(reg, hotel_name, booking):
        if not resend.api_key or resend.api_key == 're_123456789':
            return
        # Load configurable welcome info
        info = await db.welcome_info.find_one({"property_id": reg.get("property_id")}, {"_id": 0})
        policies = (info or {}).get("hotel_policies", ["Check-in: from 3:00 PM", "Check-out: by 11:00 AM", "WiFi: Available in all areas (password at reception)", "Breakfast: 7:00 AM - 10:30 AM", "Parking: Available on request"])
        city_info = (info or {}).get("city_info", ["Nearest tube/metro: 5 min walk", "Airport shuttle available on request", "Ask reception for restaurant recommendations", "City tour bookings at front desk"])
        custom_msg = (info or {}).get("custom_message", "")

        policy_html = "".join(f"<li>{p}</li>" for p in policies)
        city_html = "".join(f"<li>{c}</li>" for c in city_info)
        custom_block = f'<div style="background:#f0fdf4;border-radius:12px;padding:20px;margin:16px 0;"><p style="margin:0;color:#166534;font-size:14px;">{custom_msg}</p></div>' if custom_msg else ""

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
          <div style="background:linear-gradient(135deg,#2C4C3B,#4a7c5c);color:#fff;padding:32px;text-align:center;">
            <h1 style="margin:0;font-size:22px;">Welcome to {hotel_name}!</h1>
          </div>
          <div style="padding:28px;">
            <p>Dear {reg.get('guest_name', 'Guest')},</p>
            <p>Thank you for completing your registration. Here's everything you need for your stay:</p>
            {custom_block}
            <div style="background:#f8fafc;border-radius:12px;padding:20px;margin:16px 0;">
              <h3 style="margin:0 0 12px;color:#1e3a5f;">Hotel Information</h3>
              <ul style="margin:0;padding:0 0 0 16px;color:#555;font-size:14px;">{policy_html}</ul>
            </div>
            <div style="background:#fffbeb;border-radius:12px;padding:20px;margin:16px 0;">
              <h3 style="margin:0 0 12px;color:#92400e;">Explore the Area</h3>
              <ul style="margin:0;padding:0 0 0 16px;color:#555;font-size:14px;">{city_html}</ul>
            </div>
            <p style="color:#666;font-size:13px;">We look forward to seeing you on {booking.get('check_in', '')}!</p>
          </div>
        </div>"""
        try:
            await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [reg.get("guest_email", "")], "subject": f"Welcome Pack — {hotel_name}", "html": html})
        except Exception as e:
            logger.error(f"Welcome pack email error: {e}")

    async def _send_satisfaction_email(booking, hotel_name, feedback_url):
        if not resend.api_key or resend.api_key == 're_123456789':
            return
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
          <div style="background:#2C4C3B;color:#fff;padding:28px;text-align:center;">
            <h1 style="margin:0;font-size:20px;">{hotel_name}</h1>
            <p style="margin:6px 0 0;opacity:0.8;">How's your stay?</p>
          </div>
          <div style="padding:28px;text-align:center;">
            <p style="font-size:16px;color:#333;">Hi {booking.get('guest_name', 'Guest')},</p>
            <p style="color:#666;">We hope you're enjoying your stay. Is there anything we can help with?</p>
            <div style="margin:24px 0;">
              <a href="{feedback_url}?r=all_good" style="display:inline-block;background:#22c55e;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-size:15px;font-weight:600;margin:4px;">Everything's Great!</a>
              <a href="{feedback_url}?r=need_help" style="display:inline-block;background:#f59e0b;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-size:15px;font-weight:600;margin:4px;">I Need Help</a>
            </div>
          </div>
        </div>"""
        try:
            await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [booking.get("guest_email", "")], "subject": f"How's your stay? — {hotel_name}", "html": html})
        except Exception as e:
            logger.error(f"Satisfaction email error: {e}")

    async def _send_satisfaction_sms(property_id, phone, message):
        try:
            settings = await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
            account_sid = settings.get("twilio_account_sid", "")
            auth_token = settings.get("twilio_auth_token", "")
            from_number = settings.get("twilio_phone_number", "")
            if not all([account_sid, auth_token, from_number]):
                return
            import httpx
            async with httpx.AsyncClient() as client_http:
                await client_http.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                    auth=(account_sid, auth_token),
                    data={"From": from_number, "To": phone, "Body": message},
                )
        except Exception as e:
            logger.error(f"Satisfaction SMS error: {e}")

    async def _send_satisfaction_whatsapp(property_id, phone, message):
        try:
            settings = await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
            access_token = settings.get("whatsapp_access_token", "")
            phone_id = settings.get("whatsapp_phone_number_id", "")
            if not all([access_token, phone_id]):
                return
            import httpx
            wa_phone = phone.replace("+", "").replace(" ", "")
            async with httpx.AsyncClient() as client_http:
                await client_http.post(
                    f"https://graph.facebook.com/v18.0/{phone_id}/messages",
                    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                    json={"messaging_product": "whatsapp", "to": wa_phone, "type": "text", "text": {"body": message}},
                )
        except Exception as e:
            logger.error(f"Satisfaction WhatsApp error: {e}")

    return router
