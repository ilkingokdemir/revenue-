"""
Guest Stay Preferences Memory
-----------------------------
Stores per-guest preferences (pillow firmness, floor preference, allergies,
dietary, anniversary, AC temperature, special requests text) and exposes a
single endpoint that copies the preferences onto a new booking — front-desk
sees them at check-in, housekeeping sees them on the cleaning round, and
the booking notes inherit them automatically.

Endpoints:
  GET  /api/guest-prefs/{guest_id}                    — read
  POST /api/guest-prefs/{guest_id}                    — upsert
  GET  /api/guest-prefs/booking/{booking_id}          — read prefs for booking's guest
  POST /api/guest-prefs/apply-to-booking/{booking_id} — copy guest prefs onto booking
  GET  /api/guest-prefs/{property_id}/today-arrivals  — listing for arrivals desk
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date
from typing import Dict, Optional
import uuid


PREF_FIELDS = {
    "pillow_firmness":   "soft|medium|firm",
    "floor_preference":  "low|mid|high",
    "bed_type":          "king|twin|double",
    "smoking":           "smoking|non_smoking",
    "ac_temperature":    "celsius int 18-26",
    "wake_up_call":      "HH:MM",
    "newspaper":         "title or empty",
    "extra_blanket":     "boolean",
    "dietary":           "free text (vegan/halal/kosher/gluten_free)",
    "allergies":         "free text",
    "favourite_room":    "free text",
    "occasion":          "free text (anniversary, birthday)",
    "occasion_date":     "YYYY-MM-DD",
    "language":          "ISO 639-1",
    "transport":         "free text (taxi, EV charge, parking)",
    "notes":             "free text",
}


def create_guest_prefs_router(db, require_roles):
    router = APIRouter()

    async def _guest_id_for_booking(booking: dict) -> Optional[str]:
        if booking.get("guest_id"):
            return booking["guest_id"]
        # Fallback: look up by email
        email = booking.get("guest_email")
        if email:
            g = await db.guest_profiles.find_one({"email": email}, {"_id": 0, "id": 1})
            if g:
                return g["id"]
        return None

    @router.get("/guest-prefs/{guest_id}")
    async def get_prefs(guest_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping"))):
        doc = await db.guest_preferences.find_one({"guest_id": guest_id}, {"_id": 0})
        if not doc:
            return {"guest_id": guest_id, "prefs": {}, "fields_meta": PREF_FIELDS}
        return {**doc, "fields_meta": PREF_FIELDS}

    @router.post("/guest-prefs/{guest_id}")
    async def upsert_prefs(guest_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        prefs = {k: v for k, v in (data.get("prefs") or data).items() if k in PREF_FIELDS}
        update = {
            "guest_id": guest_id,
            "prefs": prefs,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("name", "Staff"),
        }
        await db.guest_preferences.update_one({"guest_id": guest_id}, {"$set": update}, upsert=True)
        return {"ok": True, "guest_id": guest_id, "prefs": prefs}

    @router.get("/guest-prefs/booking/{booking_id}")
    async def for_booking(booking_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping"))):
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        gid = await _guest_id_for_booking(booking)
        if not gid:
            return {"booking_id": booking_id, "guest_id": None, "prefs": {}, "match": "no_profile"}
        doc = await db.guest_preferences.find_one({"guest_id": gid}, {"_id": 0}) or {}
        return {
            "booking_id": booking_id,
            "guest_id": gid,
            "prefs": doc.get("prefs", {}),
            "fields_meta": PREF_FIELDS,
            "match": "found" if doc else "empty",
        }

    @router.post("/guest-prefs/apply-to-booking/{booking_id}")
    async def apply(booking_id: str,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        gid = await _guest_id_for_booking(booking)
        if not gid:
            return {"applied": False, "reason": "no guest profile linked"}
        doc = await db.guest_preferences.find_one({"guest_id": gid}, {"_id": 0}) or {}
        prefs = doc.get("prefs", {})
        if not prefs:
            return {"applied": False, "reason": "no preferences set"}

        # Translate prefs into guest-facing booking notes + tags
        notes_lines = []
        for k, v in prefs.items():
            if not v:
                continue
            if k == "ac_temperature":
                notes_lines.append(f"AC: {v}°C")
            elif k == "extra_blanket" and v in (True, "true", 1, "1"):
                notes_lines.append("Extra blanket")
            elif k == "wake_up_call":
                notes_lines.append(f"Wake-up call: {v}")
            elif k == "occasion":
                date_str = prefs.get("occasion_date") or ""
                notes_lines.append(f"Occasion: {v}{(' (' + date_str + ')') if date_str else ''}")
            elif k == "occasion_date":
                continue
            else:
                notes_lines.append(f"{k.replace('_', ' ').title()}: {v}")

        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "guest_preferences": prefs,
            "guest_preferences_applied_at": datetime.now(timezone.utc).isoformat(),
        }, "$addToSet": {
            "tags": {"$each": ["has_preferences"] + (["vip"] if prefs.get("occasion") else [])}
        }})

        # Append to internal notes (preserve existing)
        existing_notes = booking.get("internal_notes") or ""
        new_block = "Guest preferences:\n  • " + "\n  • ".join(notes_lines)
        if existing_notes and "Guest preferences:" not in existing_notes:
            combined = existing_notes.rstrip() + "\n\n" + new_block
        elif "Guest preferences:" in existing_notes:
            combined = existing_notes  # already applied
        else:
            combined = new_block
        await db.bookings.update_one({"id": booking_id}, {"$set": {"internal_notes": combined}})

        return {"applied": True, "booking_id": booking_id, "prefs": prefs, "lines": notes_lines}

    @router.get("/guest-prefs/{property_id}/today-arrivals")
    async def today_arrivals(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        today_str = date.today().isoformat()
        bookings = await db.bookings.find({
            "property_id": property_id,
            "check_in": today_str,
            "status": {"$in": ["confirmed", "checked_in", "arriving"]},
        }, {"_id": 0}).to_list(200)

        items = []
        for b in bookings:
            gid = await _guest_id_for_booking(b)
            prefs = {}
            if gid:
                doc = await db.guest_preferences.find_one({"guest_id": gid}, {"_id": 0}) or {}
                prefs = doc.get("prefs", {})
            items.append({
                "booking_id": b.get("id"),
                "guest_name": b.get("guest_name", ""),
                "room_number": b.get("room_number") or b.get("assigned_room", ""),
                "guest_id": gid,
                "has_prefs": bool(prefs),
                "pref_count": len([k for k, v in prefs.items() if v]),
                "prefs": prefs,
            })
        return {"date": today_str, "count": len(items), "items": items}

    return router
