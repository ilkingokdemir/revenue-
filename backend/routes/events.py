"""
Event & Meeting Room Management — Room booking, capacity, equipment, catering
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_events_router(db, require_roles):
    router = APIRouter()

    # ==================== MEETING ROOMS ====================

    @router.get("/events/rooms/{property_id}")
    async def list_rooms(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.event_rooms.find(pq, {"_id": 0}).sort("name", 1).to_list(50)
        return docs

    @router.post("/events/rooms")
    async def create_room(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        room = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": data.get("name", ""),
            "capacity": int(data.get("capacity", 0)),
            "floor": data.get("floor", ""),
            "equipment": data.get("equipment", []),
            "hourly_rate": float(data.get("hourly_rate", 0)),
            "half_day_rate": float(data.get("half_day_rate", 0)),
            "full_day_rate": float(data.get("full_day_rate", 0)),
            "amenities": data.get("amenities", []),
            "status": "available",
            "created_at": now,
        }
        await db.event_rooms.insert_one(room)
        room.pop("_id", None)
        return room

    @router.put("/events/rooms/{room_id}")
    async def update_room(room_id: str, updates: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.event_rooms.update_one({"id": room_id}, {"$set": updates})
        return await db.event_rooms.find_one({"id": room_id}, {"_id": 0})

    @router.delete("/events/rooms/{room_id}")
    async def delete_room(room_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.event_rooms.delete_one({"id": room_id})
        return {"status": "deleted"}

    # ==================== EVENT BOOKINGS ====================

    @router.get("/events/bookings/{property_id}")
    async def list_bookings(property_id: str, status: str = "", date: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        if status:
            pq["status"] = status
        if date:
            pq["date"] = date
        docs = await db.event_bookings.find(pq, {"_id": 0}).sort("date", -1).to_list(200)
        return docs

    @router.post("/events/bookings")
    async def create_booking(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        now = datetime.now(timezone.utc).isoformat()
        booking = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "room_id": data.get("room_id", ""),
            "room_name": data.get("room_name", ""),
            "event_name": data.get("event_name", ""),
            "organizer": data.get("organizer", ""),
            "contact_email": data.get("contact_email", ""),
            "contact_phone": data.get("contact_phone", ""),
            "date": data.get("date", ""),
            "start_time": data.get("start_time", "09:00"),
            "end_time": data.get("end_time", "17:00"),
            "attendees": int(data.get("attendees", 0)),
            "setup_type": data.get("setup_type", "theater"),
            "equipment_needed": data.get("equipment_needed", []),
            "catering": data.get("catering", "none"),
            "catering_notes": data.get("catering_notes", ""),
            "special_requests": data.get("special_requests", ""),
            "total_cost": float(data.get("total_cost", 0)),
            "payment_status": data.get("payment_status", "pending"),
            "status": data.get("status", "confirmed"),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.event_bookings.insert_one(booking)
        booking.pop("_id", None)
        return booking

    @router.put("/events/bookings/{booking_id}")
    async def update_booking(booking_id: str, updates: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.event_bookings.update_one({"id": booking_id}, {"$set": updates})
        return await db.event_bookings.find_one({"id": booking_id}, {"_id": 0})

    @router.delete("/events/bookings/{booking_id}")
    async def delete_booking(booking_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.event_bookings.delete_one({"id": booking_id})
        return {"status": "deleted"}

    # ==================== CATERING PACKAGES ====================

    @router.get("/events/catering")
    async def list_catering(current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        docs = await db.event_catering.find({}, {"_id": 0}).sort("name", 1).to_list(50)
        if not docs:
            defaults = [
                {"id": str(uuid.uuid4()), "name": "Tea & Coffee", "price_per_person": 5, "items": ["Tea", "Coffee", "Water", "Biscuits"], "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "name": "Morning Break", "price_per_person": 12, "items": ["Tea", "Coffee", "Pastries", "Fruit", "Juice"], "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "name": "Working Lunch", "price_per_person": 25, "items": ["Sandwiches", "Salads", "Soft Drinks", "Dessert"], "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "name": "Full Day Package", "price_per_person": 45, "items": ["Morning Break", "Lunch", "Afternoon Break", "Unlimited Beverages"], "created_at": datetime.now(timezone.utc).isoformat()},
            ]
            await db.event_catering.insert_many(defaults)
            for d in defaults:
                d.pop("_id", None)
            docs = defaults
        return docs

    return router
