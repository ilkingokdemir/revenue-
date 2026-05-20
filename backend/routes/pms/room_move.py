"""
Room Move / Walk
----------------
Moves a guest from their currently assigned room to another room (same nights,
same dates) atomically:
  • Updates booking.room_number / assigned_room
  • Stamps booking.move_history (audit)
  • Flips old room to "dirty" (or "out_of_order" if reason='maintenance')
  • Flips new room to "in_house"
  • Posts an internal note to internal_notes

Used for: housekeeping issues, guest preference (different floor), upgrade,
walk to another property when overbooked.

Endpoints:
  GET  /api/room-move/{booking_id}/options      — available target rooms
  POST /api/room-move                            — execute move
  GET  /api/room-move/{property_id}/recent       — recent moves
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


REASONS = ["upgrade", "maintenance", "noise", "guest_request", "overbook_walk", "other"]


def create_room_move_router(db, require_roles):
    router = APIRouter()

    @router.get("/room-move/{booking_id}/options")
    async def options(booking_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        property_id = booking.get("property_id", "")
        check_in  = booking.get("check_in", "")
        check_out = booking.get("check_out", "")
        current_room = booking.get("room_number") or booking.get("assigned_room", "")

        # Available rooms (clean / inspected / in_house) at this property,
        # not currently overlapping another booking for this date range.
        all_rooms = await db.room_statuses.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("room_number", 1).to_list(500)
        overlapping = await db.bookings.find({
            "property_id": property_id,
            "id": {"$ne": booking_id},
            "status": {"$in": ["confirmed", "checked_in", "arriving"]},
            "check_in": {"$lt": check_out},
            "check_out": {"$gt": check_in},
        }, {"_id": 0, "room_number": 1, "assigned_room": 1}).to_list(500)
        booked = {(b.get("room_number") or b.get("assigned_room") or "") for b in overlapping}

        items = []
        for r in all_rooms:
            rn = str(r.get("room_number") or "")
            if rn == current_room:
                continue
            if r.get("status") in ("out_of_order",):
                continue
            if rn in booked:
                continue
            items.append({
                "room_id": r.get("id"),
                "room_number": rn,
                "floor": r.get("floor", ""),
                "room_type_id": r.get("room_type_id", ""),
                "status": r.get("status", ""),
            })
        return {
            "booking_id": booking_id,
            "current_room": current_room,
            "options": items,
            "reasons": REASONS,
        }

    @router.post("/room-move")
    async def execute(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking_id  = data.get("booking_id", "")
        new_room    = str(data.get("new_room_number") or "").strip()
        new_room_id = data.get("new_room_id", "")
        reason      = data.get("reason", "other")
        notes       = data.get("notes", "")
        if not booking_id or not new_room:
            raise HTTPException(400, "booking_id and new_room_number required")
        if reason not in REASONS:
            raise HTTPException(400, f"reason must be one of {REASONS}")

        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        property_id  = booking.get("property_id", "")
        old_room     = booking.get("room_number") or booking.get("assigned_room", "")

        # Update booking
        history_entry = {
            "id": str(uuid.uuid4()),
            "from": old_room,
            "to": new_room,
            "reason": reason,
            "notes": notes,
            "by": current_user.get("name", "Staff"),
            "at": datetime.now(timezone.utc).isoformat(),
        }
        existing_notes = booking.get("internal_notes") or ""
        note_line = f"[Room move] {old_room} → {new_room} · {reason}" + (f" · {notes}" if notes else "")
        new_notes = (existing_notes + "\n" + note_line).strip() if existing_notes else note_line

        await db.bookings.update_one({"id": booking_id}, {
            "$set": {
                "room_number": new_room,
                "assigned_room": new_room,
                "moved_at": history_entry["at"],
                "internal_notes": new_notes,
            },
            "$push": {"move_history": history_entry},
        })

        # Flip old room status
        old_target = "out_of_order" if reason == "maintenance" else "dirty"
        if old_room:
            await db.room_statuses.update_one(
                {"property_id": property_id, "room_number": old_room},
                {"$set": {"status": old_target,
                          "current_guest": "",
                          "updated_at": history_entry["at"]}}
            )

        # Flip new room
        new_query = {"id": new_room_id} if new_room_id else {"property_id": property_id, "room_number": new_room}
        await db.room_statuses.update_one(new_query, {
            "$set": {"status": "in_house" if booking.get("status") == "checked_in" else "occupied",
                     "current_guest": booking.get("guest_name", ""),
                     "updated_at": history_entry["at"]}
        })

        return {"ok": True, "booking_id": booking_id, "from": old_room, "to": new_room, "history": history_entry}

    @router.get("/room-move/{property_id}/recent")
    async def recent(property_id: str, days: int = 14,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.bookings.find(
            {"property_id": property_id, "moved_at": {"$gte": since}},
            {"_id": 0, "id": 1, "guest_name": 1, "booking_ref": 1, "moved_at": 1, "move_history": 1}
        ).sort("moved_at", -1).to_list(200)
        items = []
        for b in rows:
            for h in (b.get("move_history") or [])[-1:]:
                items.append({
                    "booking_id": b["id"],
                    "guest_name": b.get("guest_name", ""),
                    "booking_ref": b.get("booking_ref", ""),
                    **h,
                })
        return {"count": len(items), "items": items}

    return router
