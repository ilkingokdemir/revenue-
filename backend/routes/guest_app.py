"""
Guest App / Digital Directory Routes
Branded guest-facing page with hotel info, services, WiFi, recommendations
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import asyncio
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)

DEFAULT_SERVICES = [
    {"name": "Room Service", "description": "Available 24/7. Browse our in-room dining menu.", "hours": "24/7", "category": "dining", "icon": "utensils"},
    {"name": "Spa & Wellness", "description": "Relax with our range of spa treatments and therapies.", "hours": "09:00 - 21:00", "category": "wellness", "icon": "spa"},
    {"name": "Fitness Centre", "description": "Fully equipped gym with cardio and weights.", "hours": "06:00 - 22:00", "category": "wellness", "icon": "dumbbell"},
    {"name": "Laundry Service", "description": "Same-day laundry and dry cleaning available.", "hours": "08:00 - 18:00", "category": "services", "icon": "shirt"},
    {"name": "Airport Transfer", "description": "Pre-book your airport pickup or drop-off.", "hours": "On request", "category": "transport", "icon": "car"},
    {"name": "Concierge", "description": "Our team can help with tours, tickets, and recommendations.", "hours": "08:00 - 22:00", "category": "services", "icon": "bell"},
]

DEFAULT_RECOMMENDATIONS = [
    {"name": "Tower of London", "type": "attraction", "distance": "1.2 km", "description": "Historic castle and World Heritage Site."},
    {"name": "Borough Market", "type": "food", "distance": "2.5 km", "description": "Famous food market with artisan stalls."},
    {"name": "The Sky Garden", "type": "attraction", "distance": "0.8 km", "description": "Free rooftop garden with panoramic city views."},
    {"name": "Dishoom", "type": "restaurant", "distance": "1.5 km", "description": "Award-winning Bombay-style cafe."},
]


def create_guest_app_router(db, require_roles):
    router = APIRouter()

    # === Admin: Manage Directory ===

    @router.get("/guest-app/directory/{property_id}")
    async def get_directory(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.guest_directories.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            from models import GuestDirectory
            gd = GuestDirectory(
                property_id=property_id,
                services=DEFAULT_SERVICES,
                local_recommendations=DEFAULT_RECOMMENDATIONS,
                welcome_message="Welcome to our hotel! We're delighted to have you as our guest.",
            )
            d = gd.model_dump()
            await db.guest_directories.insert_one(d)
            d.pop("_id", None)
            return d
        return doc

    @router.put("/guest-app/directory/{property_id}")
    async def update_directory(property_id: str, updates: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.guest_directories.update_one(
            {"property_id": property_id}, {"$set": updates}, upsert=True
        )
        doc = await db.guest_directories.find_one({"property_id": property_id}, {"_id": 0})
        asyncio.create_task(fire_webhooks(db, "directory.updated", {"property_id": property_id}))
        await log_sync(db, "guest-app", "internal", "success", f"Guest directory updated for {property_id}", property_id)
        return doc

    # === Public: Guest-facing endpoints ===

    @router.get("/guest-app/public/{property_id}")
    async def public_directory(property_id: str):
        """Public guest app page — no auth required"""
        doc = await db.guest_directories.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            from models import GuestDirectory
            gd = GuestDirectory(
                property_id=property_id,
                services=DEFAULT_SERVICES,
                local_recommendations=DEFAULT_RECOMMENDATIONS,
                welcome_message="Welcome! We're delighted to have you.",
            )
            d = gd.model_dump()
            await db.guest_directories.insert_one(d)
            d.pop("_id", None)
            doc = d

        # Get property info
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        hotel_name = prop.get("name", property_id.replace("-", " ").title()) if prop else property_id.replace("-", " ").title()

        # Get branding
        branding = await db.branding.find_one({}, {"_id": 0}) or {}

        return {
            "hotel_name": hotel_name,
            "branding": {
                "logo_url": branding.get("logo_url", ""),
                "primary_color": branding.get("primary_color", "#3E5245"),
            },
            "directory": doc,
        }

    @router.get("/guest-app/public/{property_id}/booking/{booking_ref}")
    async def guest_app_with_booking(property_id: str, booking_ref: str):
        """Guest app with booking context — shows personalized info"""
        base = await public_directory(property_id)
        booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
        if booking:
            base["booking"] = {
                "guest_name": booking.get("guest_name", ""),
                "room_type": booking.get("room_type_id", ""),
                "check_in": booking.get("check_in", ""),
                "check_out": booking.get("check_out", ""),
                "booking_ref": booking_ref,
            }
        return base

    return router
