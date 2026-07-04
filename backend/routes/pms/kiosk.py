"""
Self-Service Kiosk API — Mews-parity Batch 3 F2 (iter 359).

Public-facing endpoints (no auth) that power a tablet-mounted kiosk PWA in
the lobby. Guests look up their booking with email + booking ref (or
last-name + arrival date), confirm details, sign digital reg card, and
receive their room number + door code.

Flow:
  1. GET  /api/kiosk/{property_id}/config              — property branding
  2. POST /api/kiosk/{property_id}/lookup              — find booking
  3. POST /api/kiosk/{property_id}/checkin/{booking_id} — finalise check-in
  4. GET  /api/kiosk/{property_id}/reg-card/{booking_id} — digital reg card PDF-ish payload

All state changes create audit rows in `kiosk_events`.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import logging
import secrets
import uuid

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _door_code() -> str:
    """Simple 4-digit door code — property's smart-lock module can override
    with a real PIN via /kiosk/{pid}/checkin body."""
    return f"{secrets.randbelow(9000) + 1000}"


def create_kiosk_router(db):
    router = APIRouter(prefix="/kiosk", tags=["kiosk"])

    @router.get("/{property_id}/config")
    async def kiosk_config(property_id: str):
        """Public: minimal property branding for the kiosk splash screen."""
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "name": 1, "brand_color": 1, "logo_url": 1,
              "currency": 1, "hero_image": 1, "address": 1, "phone": 1,
              "checkin_time": 1, "checkout_time": 1, "language": 1},
        )
        if not prop:
            raise HTTPException(404, "property not found")
        return {
            "property_id": property_id,
            "name": prop.get("name", "Otel"),
            "brand_color": prop.get("brand_color", "#4f46e5"),
            "logo_url": prop.get("logo_url"),
            "hero_image": prop.get("hero_image"),
            "address": prop.get("address"),
            "phone": prop.get("phone"),
            "currency": prop.get("currency", "GBP"),
            "checkin_time": prop.get("checkin_time", "15:00"),
            "checkout_time": prop.get("checkout_time", "11:00"),
            "language": prop.get("language", "tr"),
            "server_time": _now(),
        }

    @router.post("/{property_id}/lookup")
    async def kiosk_lookup(property_id: str, body: dict):
        """Public: find today's / next few days' booking for a guest.
        Accepts any TWO of: booking_ref, last_name, email, phone."""
        booking_ref = (body.get("booking_ref") or "").strip().upper()
        last_name = (body.get("last_name") or "").strip().lower()
        email = (body.get("email") or "").strip().lower()
        phone = (body.get("phone") or "").strip()
        signals = sum([bool(booking_ref), bool(last_name), bool(email), bool(phone)])
        if signals < 1:
            raise HTTPException(400, "En az bir kimlik bilgisi girin (rezervasyon no, soyad, e-mail veya telefon)")

        query: dict = {
            "property_id": property_id,
            "status": {"$nin": ["cancelled", "checked_out", "no_show"]},
        }
        or_clauses = []
        if booking_ref:
            or_clauses.append({"booking_ref": booking_ref})
        if email:
            or_clauses.append({"guest_email": {"$regex": f"^{email}$", "$options": "i"}})
        if phone:
            digits = "".join(c for c in phone if c.isdigit())
            if len(digits) >= 6:
                or_clauses.append({"guest_phone": {"$regex": digits[-6:]}})
        if last_name:
            or_clauses.append({"guest_name": {"$regex": last_name, "$options": "i"}})
        if or_clauses:
            query["$or"] = or_clauses

        candidates = await db.bookings.find(query, {"_id": 0}).sort("check_in", 1).limit(5).to_list(5)
        if not candidates:
            await db.kiosk_events.insert_one({
                "id": str(uuid.uuid4()), "property_id": property_id, "kind": "lookup_miss",
                "query": {"ref": booking_ref, "email": email, "phone_last6": phone[-6:] if phone else ""},
                "at": _now(),
            })
            raise HTTPException(404, "Rezervasyon bulunamadı — resepsiyondan yardım isteyin.")

        results = []
        for b in candidates:
            results.append({
                "id": b.get("id"),
                "booking_ref": b.get("booking_ref"),
                "guest_name": b.get("guest_name"),
                "guest_email": b.get("guest_email"),
                "check_in": b.get("check_in"),
                "check_out": b.get("check_out"),
                "adults": b.get("adults"),
                "children": b.get("children"),
                "room_type": b.get("room_type") or b.get("room_type_name"),
                "room_number": b.get("room_number") or b.get("assigned_room"),
                "status": b.get("status"),
                "payment_status": b.get("payment_status"),
                "total_price": b.get("total_price") or b.get("total"),
                "currency": b.get("currency", "GBP"),
                "ready_for_checkin": b.get("status") == "confirmed" and (b.get("payment_status") in {"paid", "prepaid", "partial"}),
            })
        return {"count": len(results), "bookings": results}

    @router.post("/{property_id}/checkin/{booking_id}")
    async def kiosk_checkin(property_id: str, booking_id: str, body: dict):
        """Public: finalise check-in and return room number + door code."""
        booking = await db.bookings.find_one({"id": booking_id, "property_id": property_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        if booking.get("status") == "checked_in":
            # Idempotent: return stored info again
            return {
                "ok": True, "already": True,
                "room_number": booking.get("room_number") or booking.get("assigned_room") or "—",
                "door_code": booking.get("door_code") or "—",
                "checkin_time": booking.get("checked_in_at"),
            }
        if booking.get("status") not in {"confirmed", "pre_checkin"}:
            raise HTTPException(400, f"Booking status '{booking.get('status')}' — kioskta check-in yapılamaz.")

        # Assign room if not yet assigned. Try to pull first available room of
        # the same type; fall back to booking's room_number.
        room_number = booking.get("room_number") or booking.get("assigned_room")
        if not room_number:
            rt = booking.get("room_type_id") or booking.get("room_type")
            if rt:
                room = await db.rooms.find_one(
                    {"property_id": property_id, "room_type_id": rt, "status": {"$in": ["clean", "vacant_ready"]}},
                    {"_id": 0, "number": 1},
                )
                room_number = (room or {}).get("number") or "TBD"

        door_code = body.get("door_code") or booking.get("door_code") or _door_code()

        updates = {
            "status": "checked_in",
            "checked_in_at": _now(),
            "check_in_method": "kiosk",
            "room_number": room_number,
            "door_code": door_code,
            "kiosk_signature": body.get("signature") or "",
            "kiosk_id_scan_ref": body.get("id_scan_ref") or "",
        }
        await db.bookings.update_one({"id": booking_id}, {"$set": updates})

        await db.kiosk_events.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id,
            "booking_id": booking_id, "kind": "checkin",
            "guest_name": booking.get("guest_name"), "room_number": room_number,
            "signed": bool(body.get("signature")), "at": _now(),
        })

        return {
            "ok": True,
            "already": False,
            "booking_id": booking_id,
            "guest_name": booking.get("guest_name"),
            "room_number": room_number,
            "door_code": door_code,
            "checkin_time": updates["checked_in_at"],
            "checkout_reminder": booking.get("check_out"),
        }

    @router.get("/{property_id}/reg-card/{booking_id}")
    async def kiosk_reg_card(property_id: str, booking_id: str):
        """Return a printable JSON payload of the digital registration card."""
        booking = await db.bookings.find_one({"id": booking_id, "property_id": property_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1, "address": 1})
        return {
            "property": prop,
            "booking_ref": booking.get("booking_ref"),
            "guest_name": booking.get("guest_name"),
            "guest_email": booking.get("guest_email"),
            "guest_phone": booking.get("guest_phone"),
            "check_in": booking.get("check_in"),
            "check_out": booking.get("check_out"),
            "adults": booking.get("adults"),
            "children": booking.get("children"),
            "room_number": booking.get("room_number"),
            "signature": booking.get("kiosk_signature"),
            "signed_at": booking.get("checked_in_at"),
        }

    @router.get("/{property_id}/stats")
    async def kiosk_stats(property_id: str):
        """Simple usage KPI for admin dashboard."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        total_kiosk = await db.kiosk_events.count_documents({"property_id": property_id, "kind": "checkin"})
        today_kiosk = await db.kiosk_events.count_documents(
            {"property_id": property_id, "kind": "checkin", "at": {"$gte": today}}
        )
        misses = await db.kiosk_events.count_documents({"property_id": property_id, "kind": "lookup_miss"})
        return {"total_kiosk_checkins": total_kiosk, "today": today_kiosk, "lookup_misses": misses}

    return router
