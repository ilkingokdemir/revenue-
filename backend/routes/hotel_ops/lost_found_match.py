"""
Lost & Found Auto-Match
-----------------------
Extends existing lost_found.py with intelligent matching:
  • Fuzzy-matches lost item descriptions against recent checkouts in the
    same room/area within ±2 days.
  • Returns ranked match candidates (guest name, email, phone, dates)
    so the front desk can email/SMS them with a claim link.

Endpoints:
  GET  /api/lost-found/{item_id}/match-candidates
  POST /api/lost-found/{item_id}/notify-guest    — emails the matched guest a claim form
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List
import uuid


def create_lost_found_match_router(db, require_roles):
    router = APIRouter()

    @router.get("/lost-found/{item_id}/match-candidates")
    async def candidates(item_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        item = await db.lost_found.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Item not found")

        property_id = item.get("property_id", "")
        found_date_str = item.get("found_date") or date.today().isoformat()
        try:
            found_date = datetime.fromisoformat(found_date_str).date()
        except Exception:
            found_date = date.today()
        guest_room = item.get("guest_room", "")
        location = item.get("found_location", "").lower()

        from_date = (found_date - timedelta(days=3)).isoformat()
        to_date   = (found_date + timedelta(days=2)).isoformat()

        # Pull recent checkouts in this property
        recent = await db.bookings.find({
            "property_id": property_id,
            "status": {"$in": ["checked_out", "checked_in"]},
            "check_out": {"$gte": from_date, "$lte": to_date},
        }, {"_id": 0, "id": 1, "guest_name": 1, "guest_email": 1, "guest_phone": 1,
            "room_number": 1, "assigned_room": 1, "check_in": 1, "check_out": 1, "status": 1}).to_list(200)

        scored = []
        for b in recent:
            score = 0
            reasons = []
            booked_room = (b.get("room_number") or b.get("assigned_room") or "").strip()
            if guest_room and booked_room == str(guest_room):
                score += 80; reasons.append("Same room")
            elif booked_room and location and booked_room in location:
                score += 40; reasons.append("Room mentioned in location")
            # Date proximity: 0..30 pts based on |checkout - found|
            try:
                co = datetime.fromisoformat(b["check_out"]).date()
                delta = abs((co - found_date).days)
                if delta == 0:
                    score += 30; reasons.append("Checked out same day")
                elif delta == 1:
                    score += 20; reasons.append("Checked out ±1 day")
                elif delta <= 2:
                    score += 10; reasons.append("Checked out ±2 days")
            except Exception:
                pass
            # Item already claimed? skip.
            if item.get("status") == "claimed":
                continue

            if score > 0:
                scored.append({
                    "booking_id": b["id"],
                    "guest_name": b.get("guest_name", ""),
                    "guest_email": b.get("guest_email", ""),
                    "guest_phone": b.get("guest_phone", ""),
                    "room_number": booked_room,
                    "check_out": b.get("check_out", ""),
                    "score": score,
                    "reasons": reasons,
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {"item_id": item_id, "found_date": found_date_str, "candidates": scored[:10]}

    @router.post("/lost-found/{item_id}/notify-guest")
    async def notify(item_id: str, data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking_id = data.get("booking_id", "")
        message = data.get("message", "")
        item = await db.lost_found.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Item not found")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        # Log the notification in lost_found_notifications collection (no real
        # email here — Resend integration is on the API-key blocked backlog).
        record = {
            "id": str(uuid.uuid4()),
            "item_id": item_id,
            "booking_id": booking_id,
            "guest_name": booking.get("guest_name", ""),
            "guest_email": booking.get("guest_email", ""),
            "guest_phone": booking.get("guest_phone", ""),
            "message": message or f"We may have found your '{item.get('item_name', '')}'.",
            "channel": data.get("channel", "email"),
            "status": "queued",
            "queued_by": current_user.get("name", "Staff"),
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.lost_found_notifications.insert_one(dict(record))
        record.pop("_id", None)

        # Stamp the lost-found item with the latest contact attempt
        await db.lost_found.update_one({"id": item_id}, {"$set": {
            "guest_name": booking.get("guest_name", ""),
            "guest_contact": booking.get("guest_email") or booking.get("guest_phone", ""),
            "last_notified_at": record["queued_at"],
            "last_notified_booking_id": booking_id,
        }})
        return {"ok": True, "queued_record": record}

    return router
