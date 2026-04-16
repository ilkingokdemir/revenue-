"""
Online Booking Widget — Public booking form for hotel websites
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_booking_widget_router(db, require_roles):
    router = APIRouter()

    # ==================== PUBLIC: PROPERTY INFO ====================

    @router.get("/booking-widget/info/{property_id}")
    async def widget_info(property_id: str):
        """Public: Get property info and room types for booking widget"""
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")

        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not rooms:
            rooms = [
                {"id": "standard", "name": "Standard Room", "base_rate": 100, "max_occupancy": 2, "description": "Comfortable room with all essentials", "photo": "https://images.unsplash.com/photo-1631048730670-ff5cd0d08f15?w=600&q=75"},
                {"id": "deluxe", "name": "Deluxe Room", "base_rate": 150, "max_occupancy": 2, "description": "Spacious room with premium amenities", "photo": "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=600&q=75"},
                {"id": "suite", "name": "Suite", "base_rate": 250, "max_occupancy": 4, "description": "Luxurious suite with separate living area", "photo": "https://images.unsplash.com/photo-1631049307305-1ceea96fb0e1?w=600&q=75"},
            ]

        # Default room photos by index
        default_photos = [
            "https://images.unsplash.com/photo-1631048730670-ff5cd0d08f15?w=600&q=75",
            "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=600&q=75",
            "https://images.unsplash.com/photo-1631049307305-1ceea96fb0e1?w=600&q=75",
            "https://images.unsplash.com/photo-1631048835184-3f0ceda91b75?w=600&q=75",
            "https://images.pexels.com/photos/97083/pexels-photo-97083.jpeg?auto=compress&cs=tinysrgb&w=600",
        ]

        # Get rate plans for dynamic pricing
        plans = await db.rate_plans.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(20)

        # Get reviews
        reviews = await db.guest_reviews.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
        if not reviews:
            reviews = [
                {"guest_name": "Sarah M.", "country": "United Kingdom", "rating": 9.4, "title": "Wonderful stay!", "comment": "Beautiful rooms, amazing staff. The location was perfect and the breakfast was excellent. Would definitely come back!", "date": "March 2026"},
                {"guest_name": "Thomas L.", "country": "Germany", "rating": 9.1, "title": "Great value", "comment": "Clean, comfortable, and well-located. The staff went above and beyond to help with our requests. Highly recommended.", "date": "February 2026"},
                {"guest_name": "Maria G.", "country": "Spain", "rating": 9.6, "title": "Exceptional", "comment": "From check-in to check-out, everything was perfect. The room was spacious and immaculately clean. Best hotel experience in London.", "date": "January 2026"},
                {"guest_name": "James W.", "country": "United States", "rating": 8.8, "title": "Very comfortable", "comment": "Great location, friendly staff. The room was exactly as pictured. The only minor thing was the lift was slow during peak times.", "date": "March 2026"},
                {"guest_name": "Yuki T.", "country": "Japan", "rating": 9.7, "title": "Perfect in every way", "comment": "Absolutely loved our stay. The attention to detail was remarkable. Will definitely be our go-to hotel when visiting London.", "date": "February 2026"},
                {"guest_name": "Ahmed K.", "country": "UAE", "rating": 9.2, "title": "Premium quality", "comment": "Excellent service and beautiful property. The suite was luxurious with a stunning city view. Great breakfast selection too.", "date": "January 2026"},
            ]
        avg_rating = round(sum(r.get("rating", 0) for r in reviews) / max(len(reviews), 1), 1) if reviews else 0

        # Widget theme config
        wconfig = await db.booking_widget_config.find_one({"property_id": property_id}, {"_id": 0})
        theme = {
            "accent_color": (wconfig or {}).get("accent_color", "#1a3c5e"),
            "hero_image": (wconfig or {}).get("hero_image", "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1920&q=80"),
            "tagline": (wconfig or {}).get("tagline", "Premium Accommodation"),
            "subtitle": (wconfig or {}).get("subtitle", "Experience exceptional hospitality with our best rate guarantee when you book direct"),
        }

        return {
            "hotel_name": hotel_name,
            "property_id": property_id,
            "logo_url": ts.get("logo_url", ""),
            "rooms": [{"id": r.get("id", ""), "name": r.get("name", ""), "base_rate": r.get("base_rate", 0), "max_occupancy": r.get("max_occupancy", 2), "description": r.get("description", ""), "amenities": r.get("amenities", []), "photo": r.get("photo", "") or default_photos[i % len(default_photos)]} for i, r in enumerate(rooms)],
            "currency": ts.get("currency", "GBP"),
            "has_rate_plans": len(plans) > 0,
            "reviews": reviews,
            "avg_rating": avg_rating,
            "review_count": len(reviews),
            "theme": theme,
        }

    # ==================== PUBLIC: CHECK AVAILABILITY ====================

    @router.post("/booking-widget/check-availability")
    async def check_availability(data: Dict):
        """Public: Check room availability for dates"""
        property_id = data.get("property_id", "")
        check_in = data.get("check_in", "")
        check_out = data.get("check_out", "")

        if not all([property_id, check_in, check_out]):
            raise HTTPException(400, "property_id, check_in, check_out required")

        # Get all room types
        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not rooms:
            rooms = [
                {"id": "standard", "name": "Standard Room", "base_rate": 100, "total_rooms": 10, "max_occupancy": 2},
                {"id": "deluxe", "name": "Deluxe Room", "base_rate": 150, "total_rooms": 5, "max_occupancy": 2},
                {"id": "suite", "name": "Suite", "base_rate": 250, "total_rooms": 2, "max_occupancy": 4},
            ]

        # Check existing bookings for overlap
        available = []
        for room in rooms:
            booked = await db.bookings.count_documents({
                "property_id": property_id,
                "room_type": room.get("name", ""),
                "status": {"$in": ["confirmed", "checked_in"]},
                "check_in": {"$lt": check_out},
                "check_out": {"$gt": check_in},
            })
            total = room.get("total_rooms", 10)
            avail = max(total - booked, 0)
            if avail > 0:
                # Calculate nights
                try:
                    ci = datetime.strptime(check_in, "%Y-%m-%d")
                    co = datetime.strptime(check_out, "%Y-%m-%d")
                    nights = (co - ci).days
                except Exception:
                    nights = 1

                rate = room.get("base_rate", 100)
                default_photos = [
                    "https://images.unsplash.com/photo-1631048730670-ff5cd0d08f15?w=600&q=75",
                    "https://images.unsplash.com/photo-1629140727571-9b5c6f6267b4?w=600&q=75",
                    "https://images.unsplash.com/photo-1631049307305-1ceea96fb0e1?w=600&q=75",
                    "https://images.unsplash.com/photo-1631048835184-3f0ceda91b75?w=600&q=75",
                    "https://images.pexels.com/photos/97083/pexels-photo-97083.jpeg?auto=compress&cs=tinysrgb&w=600",
                ]
                idx = rooms.index(room) if room in rooms else 0
                available.append({
                    "room_type_id": room.get("id", ""),
                    "name": room.get("name", ""),
                    "photo": room.get("photo", "") or default_photos[idx % len(default_photos)],
                    "base_rate": rate,
                    "total_rate": round(rate * nights, 2),
                    "nights": nights,
                    "available": avail,
                    "max_occupancy": room.get("max_occupancy", 2),
                    "description": room.get("description", ""),
                    "amenities": room.get("amenities", []),
                })
        return {"available_rooms": available, "check_in": check_in, "check_out": check_out}

    # ==================== PUBLIC: CREATE BOOKING ====================

    @router.post("/booking-widget/book")
    async def create_widget_booking(data: Dict):
        """Public: Guest creates booking from widget"""
        required = ["property_id", "room_type", "check_in", "check_out", "guest_name", "guest_email"]
        for f in required:
            if not data.get(f):
                raise HTTPException(400, f"{f} is required")

        now = datetime.now(timezone.utc).isoformat()
        booking_ref = f"WEB-{uuid.uuid4().hex[:8].upper()}"

        try:
            ci = datetime.strptime(data["check_in"], "%Y-%m-%d")
            co = datetime.strptime(data["check_out"], "%Y-%m-%d")
            nights = (co - ci).days
        except Exception:
            nights = 1

        rate = data.get("rate", 0)
        total = round(rate * nights, 2)

        booking = {
            "id": str(uuid.uuid4()),
            "booking_ref": booking_ref,
            "property_id": data["property_id"],
            "guest_name": data["guest_name"],
            "guest_email": data["guest_email"],
            "guest_phone": data.get("guest_phone", ""),
            "check_in": data["check_in"],
            "check_out": data["check_out"],
            "rooms": data.get("rooms", 1),
            "room_type": data["room_type"],
            "rate": rate,
            "total": total,
            "nights": nights,
            "currency": data.get("currency", "GBP"),
            "status": "confirmed",
            "source": "website_widget",
            "special_requests": data.get("special_requests", ""),
            "guests": data.get("guests", 1),
            "created_at": now,
        }
        await db.bookings.insert_one(booking)
        booking.pop("_id", None)
        return {"status": "confirmed", "booking_ref": booking_ref, "booking": booking}

    # ==================== ADMIN: WIDGET CONFIG ====================

    @router.get("/booking-widget/config/{property_id}")
    async def get_widget_config(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        config = await db.booking_widget_config.find_one({"property_id": property_id}, {"_id": 0})
        if not config:
            return {"property_id": property_id, "enabled": True, "accent_color": "#1e3a5f", "show_rates": True}
        return config

    @router.put("/booking-widget/config/{property_id}")
    async def update_widget_config(property_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        data["property_id"] = property_id
        await db.booking_widget_config.update_one({"property_id": property_id}, {"$set": data}, upsert=True)
        return {"status": "saved"}

    return router
