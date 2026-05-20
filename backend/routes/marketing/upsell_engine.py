"""
AI Upsell Engine — Automatically suggests room upgrades, early check-in,
late checkout, and add-ons based on guest profile and availability.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import os
import random
import logging

logger = logging.getLogger(__name__)


def create_upsell_router(db, require_roles, LlmChat, UserMessage):
    router = APIRouter()

    @router.get("/revenue/upsell/{booking_id}")
    async def get_upsell_suggestions(booking_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Generate upsell suggestions for a specific booking."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            return {"error": "Booking not found"}

        pid = booking.get("property_id", "")
        ci = booking.get("check_in", "")
        co = booking.get("check_out", "")
        current_rate = float(booking.get("rate_per_night", 0) or 0)
        current_rt_id = booking.get("room_type_id", "")
        nights = int(booking.get("nights", 1) or 1)

        # Get all room types for upgrade options
        room_types = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
        rt_map = {rt.get("id", ""): rt for rt in room_types}
        current_rt = rt_map.get(current_rt_id, {})

        suggestions = []

        # 1. ROOM UPGRADE — Find higher-tier rooms with availability
        for rt in room_types:
            rt_id = rt.get("id", "")
            if rt_id == current_rt_id:
                continue
            rt_rate = float(rt.get("base_rate") or current_rate * 1.3)
            if rt_rate <= current_rate:
                continue

            # Check availability
            rt_rooms = await db.rooms.find({"property_id": pid, "room_type_id": rt_id}, {"_id": 0}).to_list(10)
            available = 0
            for room in rt_rooms:
                conflict = await db.bookings.find_one({
                    "room_id": room.get("id"), "status": {"$nin": ["cancelled"]},
                    "check_in": {"$lt": co}, "check_out": {"$gt": ci}
                })
                if not conflict:
                    available += 1

            if available > 0:
                upgrade_cost = round((rt_rate - current_rate) * nights, 2)
                suggestions.append({
                    "id": str(uuid.uuid4()),
                    "type": "room_upgrade",
                    "title": f"Upgrade to {rt.get('name', 'Premium Room')}",
                    "description": f"Move from {current_rt.get('name', 'Current Room')} to {rt.get('name', 'Premium Room')} — {available} available",
                    "price": upgrade_cost,
                    "price_label": f"+£{upgrade_cost:.0f} for {nights} night{'s' if nights > 1 else ''}",
                    "per_night": round(rt_rate - current_rate, 2),
                    "availability": available,
                    "priority": "high" if upgrade_cost < 50 else "medium",
                    "target_room_type": rt_id,
                })

        # 2. EARLY CHECK-IN
        suggestions.append({
            "id": str(uuid.uuid4()),
            "type": "early_checkin",
            "title": "Early Check-In (from 12pm)",
            "description": "Arrive 2 hours early and go straight to your room",
            "price": round(current_rate * 0.25, 2),
            "price_label": f"£{current_rate * 0.25:.0f}",
            "priority": "medium",
        })

        # 3. LATE CHECKOUT
        suggestions.append({
            "id": str(uuid.uuid4()),
            "type": "late_checkout",
            "title": "Late Check-Out (until 2pm)",
            "description": "Enjoy an extra 2 hours before departure",
            "price": round(current_rate * 0.3, 2),
            "price_label": f"£{current_rate * 0.3:.0f}",
            "priority": "medium",
        })

        # 4. ADD-ONS
        addons = [
            {"name": "Breakfast Package", "desc": "Full English breakfast for all guests", "pct": 0.15, "per": "night"},
            {"name": "Airport Transfer", "desc": "Private car to/from airport", "flat": 45, "per": "trip"},
            {"name": "Welcome Hamper", "desc": "Champagne, chocolates & local treats", "flat": 35, "per": "stay"},
            {"name": "Parking Space", "desc": "Secure on-site parking", "flat": 12, "per": "night"},
            {"name": "Spa Access", "desc": "Full-day access to spa facilities", "flat": 25, "per": "night"},
        ]
        for addon in addons:
            price = addon.get("flat", round(current_rate * addon.get("pct", 0.1), 2))
            total = price * nights if addon["per"] == "night" else price
            suggestions.append({
                "id": str(uuid.uuid4()),
                "type": "addon",
                "title": addon["name"],
                "description": addon["desc"],
                "price": round(total, 2),
                "price_label": f"£{price:.0f}/{addon['per']}" + (f" (£{total:.0f} total)" if addon["per"] == "night" and nights > 1 else ""),
                "priority": "low",
            })

        # Calculate total upsell potential
        total_potential = round(sum(s["price"] for s in suggestions), 2)

        return {
            "booking_id": booking_id,
            "guest_name": booking.get("guest_name", ""),
            "current_room": current_rt.get("name", ""),
            "current_rate": current_rate,
            "nights": nights,
            "suggestions": suggestions,
            "total_potential": total_potential,
        }

    @router.post("/revenue/upsell/{booking_id}/accept")
    async def accept_upsell(booking_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Accept an upsell — add charge to folio and update booking if needed."""
        suggestion_type = data.get("type", "")
        price = float(data.get("price", 0))
        description = data.get("description", "")
        target_room_type = data.get("target_room_type", "")

        # Add to folio
        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "charge",
            "category": "upsell",
            "description": description or f"Upsell: {suggestion_type}",
            "quantity": 1,
            "unit_price": price,
            "amount": price,
            "currency": "GBP",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", "AI Upsell"),
        }
        await db.folio_items.insert_one(dict(item))

        # If room upgrade, update booking room type
        if suggestion_type == "room_upgrade" and target_room_type:
            await db.bookings.update_one({"id": booking_id}, {"$set": {
                "room_type_id": target_room_type,
                "upgraded": True,
                "upgrade_from": data.get("current_room_type", ""),
            }})

        # Log the upsell
        await db.upsell_log.insert_one({
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": suggestion_type,
            "revenue": price,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "accepted_by": current_user.get("name", ""),
        })

        return {"status": "accepted", "type": suggestion_type, "revenue_added": price}

    @router.get("/revenue/upsell/stats/{property_id}")
    async def upsell_stats(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Upsell performance stats."""
        logs = await db.upsell_log.find({}, {"_id": 0}).to_list(500)
        total_revenue = round(sum(float(log.get("revenue", 0)) for log in logs), 2)
        by_type = {}
        for log in logs:
            t = log.get("type", "other")
            by_type.setdefault(t, {"count": 0, "revenue": 0})
            by_type[t]["count"] += 1
            by_type[t]["revenue"] += float(log.get("revenue", 0))

        return {
            "total_upsells": len(logs),
            "total_revenue": total_revenue,
            "by_type": [{
                "type": k, "count": v["count"], "revenue": round(v["revenue"], 2)
            } for k, v in sorted(by_type.items(), key=lambda x: -x[1]["revenue"])],
        }

    return router
