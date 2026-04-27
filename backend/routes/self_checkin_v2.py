"""
Self Check-in v2 — end-to-end pre-arrival flow.

Flow:
  1. Admin/scheduler → POST /self-checkin-v2/token/{booking_id}
     Generates uuid token + email link (returned) that guest clicks.
  2. Guest opens /selfcheckin-v2/{token}
     → GET /self-checkin-v2/verify/{token}  (booking+property data)
  3. Guest fills reg-card + uploads ID + signs
     → POST /self-checkin-v2/reg-card/{token}  (saves fields, captures signature SVG)
  4. Guest picks arrival slot
     → POST /self-checkin-v2/slot/{token}
  5. On actual check-in day receptionist sees "completed - fast track" badge.

The token is a short uuid; the link has a 72h expiry by default.
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict
from pydantic import BaseModel
import uuid
import logging

logger = logging.getLogger(__name__)


class RegCardSubmission(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    id_doc_type: Optional[str] = None  # passport | id_card | driving_license
    id_doc_no: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    id_doc_image_b64: Optional[str] = None   # base64 jpg/png
    signature_svg: Optional[str] = None       # signed canvas SVG or base64 PNG
    marketing_consent: bool = False
    extra_guests: Optional[List[Dict]] = None


class SlotSelection(BaseModel):
    arrival_slot: str  # e.g. "14:00"
    estimated_arrival: Optional[str] = None  # ISO datetime


DEFAULT_SLOTS = [
    "10:00-11:00", "11:00-12:00", "12:00-13:00", "13:00-14:00",
    "14:00-15:00", "15:00-16:00", "16:00-17:00", "17:00-18:00",
    "18:00-19:00", "19:00-20:00", "20:00-21:00",
]


def create_self_checkin_v2_router(db, require_roles):
    router = APIRouter()

    # ---- Admin: generate token ----

    @router.post("/self-checkin-v2/token/{booking_id}")
    async def generate_token(booking_id: str, expiry_hours: int = 72,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")

        token = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=expiry_hours)
        doc = {
            "id": str(uuid.uuid4()),
            "token": token,
            "booking_id": booking_id,
            "property_id": b.get("property_id"),
            "guest_name": b.get("guest_name"),
            "guest_email": b.get("guest_email"),
            "created_at": now.isoformat(),
            "created_by": current_user.get("email"),
            "expires_at": expires.isoformat(),
            "status": "issued",  # issued -> started -> reg_card_filled -> slot_booked -> completed
        }
        await db.self_checkin_tokens.insert_one(doc)
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"self_checkin_v2_token": token, "self_checkin_v2_issued_at": now.isoformat()}}
        )
        # Build link (frontend will handle)
        link = f"/selfcheckin-v2/{token}"
        return {
            "token": token,
            "link": link,
            "expires_at": expires.isoformat(),
            "booking_id": booking_id,
            "guest_email": b.get("guest_email"),
            "email_send_note": "Email dispatch requires RESEND_API_KEY (queued only).",
        }

    # ---- Guest: verify token ----

    @router.get("/self-checkin-v2/verify/{token}")
    async def verify_token(token: str):
        t = await db.self_checkin_tokens.find_one({"token": token}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Token not found")
        try:
            exp = datetime.fromisoformat(t["expires_at"].replace("Z", "+00:00"))
            if not exp.tzinfo:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                raise HTTPException(410, "Token expired")
        except Exception:
            pass

        # Update status if still 'issued'
        if t.get("status") == "issued":
            await db.self_checkin_tokens.update_one(
                {"token": token},
                {"$set": {"status": "started", "started_at": datetime.now(timezone.utc).isoformat()}}
            )

        booking = await db.bookings.find_one({"id": t["booking_id"]}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        property_doc = await db.properties.find_one(
            {"id": booking.get("property_id")}, {"_id": 0}
        ) or {}

        # Strip sensitive fields
        booking_public = {
            "id": booking.get("id"),
            "guest_name": booking.get("guest_name"),
            "check_in": booking.get("check_in"),
            "check_out": booking.get("check_out"),
            "room_type_name": booking.get("room_type_name"),
            "total_price": booking.get("total_price"),
            "currency": booking.get("currency"),
        }
        property_public = {
            "id": property_doc.get("id"),
            "name": property_doc.get("name"),
            "address": property_doc.get("address"),
            "phone": property_doc.get("phone"),
            "check_in_time": property_doc.get("check_in_time", "15:00"),
            "check_out_time": property_doc.get("check_out_time", "11:00"),
            "logo_url": property_doc.get("logo_url"),
        }
        return {
            "token": token,
            "status": t.get("status"),
            "booking": booking_public,
            "property": property_public,
            "default_slots": DEFAULT_SLOTS,
            "reg_card_filled": bool(t.get("reg_card_filled_at")),
            "slot_booked": bool(t.get("slot_booked_at")),
        }

    # ---- Guest: submit reg-card ----

    @router.post("/self-checkin-v2/reg-card/{token}")
    async def submit_reg_card(token: str, data: RegCardSubmission):
        t = await db.self_checkin_tokens.find_one({"token": token}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Token not found")
        now = datetime.now(timezone.utc).isoformat()

        reg_card_doc = {
            "id": str(uuid.uuid4()),
            "token": token,
            "booking_id": t["booking_id"],
            "property_id": t["property_id"],
            **data.dict(),
            "submitted_at": now,
        }
        await db.self_checkin_reg_cards.insert_one(reg_card_doc)

        # Update guest_profile if exists
        booking = await db.bookings.find_one({"id": t["booking_id"]}, {"_id": 0}) or {}
        guest_id = booking.get("guest_id")
        if guest_id:
            patch = {
                "first_name": data.first_name,
                "last_name": data.last_name,
                "id_doc_type": data.id_doc_type,
                "id_doc_no": data.id_doc_no,
                "nationality": data.nationality,
                "phone": data.phone,
                "date_of_birth": data.date_of_birth,
                "address": data.address,
                "marketing_consent": data.marketing_consent,
                "updated_at": now,
            }
            await db.guest_profiles.update_one(
                {"id": guest_id}, {"$set": {k: v for k, v in patch.items() if v is not None}}
            )

        await db.self_checkin_tokens.update_one(
            {"token": token},
            {"$set": {
                "status": "reg_card_filled",
                "reg_card_filled_at": now,
                "has_signature": bool(data.signature_svg),
                "has_id_photo": bool(data.id_doc_image_b64),
            }}
        )
        await db.bookings.update_one(
            {"id": t["booking_id"]},
            {"$set": {"self_checkin_v2_reg_card_at": now, "self_checkin_v2_has_signature": bool(data.signature_svg)}}
        )

        return {"status": "reg_card_filled", "submitted_at": now}

    # ---- Guest: pick slot ----

    @router.post("/self-checkin-v2/slot/{token}")
    async def book_slot(token: str, sel: SlotSelection):
        t = await db.self_checkin_tokens.find_one({"token": token}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Token not found")
        if sel.arrival_slot not in DEFAULT_SLOTS:
            raise HTTPException(400, "Invalid slot")

        now = datetime.now(timezone.utc).isoformat()
        await db.self_checkin_tokens.update_one(
            {"token": token},
            {"$set": {
                "arrival_slot": sel.arrival_slot,
                "estimated_arrival": sel.estimated_arrival,
                "slot_booked_at": now,
                "status": "completed",
            }}
        )
        await db.bookings.update_one(
            {"id": t["booking_id"]},
            {"$set": {
                "arrival_slot": sel.arrival_slot,
                "self_checkin_v2_completed_at": now,
                "fast_track_enabled": True,
            }}
        )
        return {"status": "completed", "arrival_slot": sel.arrival_slot, "completed_at": now}

    # ---- Admin: pipeline dashboard ----

    @router.get("/self-checkin-v2/pipeline/{property_id}")
    async def pipeline(property_id: str, days_ahead: int = 14,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        bookings = await db.bookings.find({
            "property_id": property_id,
            "check_in": {"$gte": today, "$lte": horizon},
            "status": {"$in": ["confirmed", "pending_payment"]},
        }, {"_id": 0}).limit(300).to_list(300)

        rows = []
        for b in bookings:
            token = b.get("self_checkin_v2_token")
            tok = await db.self_checkin_tokens.find_one({"token": token}, {"_id": 0}) if token else None
            rows.append({
                "booking_id": b.get("id"),
                "guest_name": b.get("guest_name"),
                "guest_email": b.get("guest_email"),
                "check_in": b.get("check_in"),
                "room_type_name": b.get("room_type_name"),
                "token_issued": bool(tok),
                "reg_card_filled": bool(tok and tok.get("reg_card_filled_at")),
                "has_signature": bool(tok and tok.get("has_signature")),
                "has_id_photo": bool(tok and tok.get("has_id_photo")),
                "slot_booked": bool(tok and tok.get("slot_booked_at")),
                "arrival_slot": tok.get("arrival_slot") if tok else None,
                "fast_track": bool(b.get("fast_track_enabled")),
                "status": (tok or {}).get("status", "not_issued"),
                "token": token,
            })

        # Aggregates
        total = len(rows)
        issued = sum(1 for r in rows if r["token_issued"])
        completed = sum(1 for r in rows if r["status"] == "completed")
        reg_filled = sum(1 for r in rows if r["reg_card_filled"])

        return {
            "rows": rows,
            "count": total,
            "issued": issued,
            "reg_card_filled": reg_filled,
            "completed": completed,
            "completion_pct": round(completed / total * 100, 1) if total else 0,
        }

    @router.get("/self-checkin-v2/reg-card/{token}")
    async def get_reg_card(token: str,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Admin view of submitted reg card (for receptionist at check-in)."""
        doc = await db.self_checkin_reg_cards.find_one({"token": token}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Reg card not submitted")
        return doc

    return router
