"""
Mobile Companion API — Lightweight endpoints for the mobile dashboard.
Returns summary data optimized for mobile screens.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


def create_mobile_router(db, require_roles):
    router = APIRouter()

    @router.get("/mobile/dashboard/{property_id}")
    async def mobile_dashboard(property_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Mobile-optimized dashboard with today's KPIs."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

        bk_query = {"status": {"$nin": ["cancelled"]}}
        if property_id != "all":
            bk_query["property_id"] = property_id

        # Rooms count
        total_rooms = 0
        if property_id != "all":
            total_rooms = await db.rooms.count_documents({"property_id": property_id})
        if total_rooms == 0:
            q = {} if property_id == "all" else {"property_id": property_id}
            rt_count = await db.room_types.count_documents(q)
            total_rooms = rt_count * 3

        # Today's occupancy
        booked = await db.bookings.count_documents({
            **bk_query, "check_in": {"$lte": today}, "check_out": {"$gt": today}
        })
        occ = round((booked / max(total_rooms, 1)) * 100)

        # Today's revenue
        today_bks = await db.bookings.find(
            {**bk_query, "check_in": {"$lte": today}, "check_out": {"$gt": today}},
            {"_id": 0, "rate_per_night": 1}
        ).to_list(500)
        revenue = round(sum(float(b.get("rate_per_night", 0) or 0) for b in today_bks), 2)
        adr = round(revenue / max(len(today_bks), 1), 2)

        # Arrivals / Departures
        arrivals = await db.bookings.count_documents({**bk_query, "check_in": today})
        departures = await db.bookings.count_documents({**bk_query, "check_out": today})
        in_house = await db.bookings.count_documents({
            **bk_query, "check_in": {"$lte": today}, "check_out": {"$gt": today}, "status": "checked_in"
        })

        # Tomorrow preview
        tmr_booked = await db.bookings.count_documents({
            **bk_query, "check_in": {"$lte": tomorrow}, "check_out": {"$gt": tomorrow}
        })
        tmr_occ = round((tmr_booked / max(total_rooms, 1)) * 100)
        tmr_arrivals = await db.bookings.count_documents({**bk_query, "check_in": tomorrow})

        # Unread notifications
        unread = await db.notifications.count_documents({"read": False})

        # Pending reviews
        pending_reviews = await db.reviews.count_documents({"response_status": "pending"})

        # Housekeeping
        dirty_rooms = await db.rooms.count_documents({"housekeeping": "dirty"})

        # Recent alerts (price intel)
        alerts = await db.notifications.find(
            {"category": "price_intelligence", "read": False},
            {"_id": 0, "title": 1, "severity": 1, "sub_type": 1}
        ).sort("created_at", -1).to_list(5)

        return {
            "date": today,
            "property_id": property_id,
            "today": {
                "occupancy_pct": occ,
                "booked_rooms": booked,
                "total_rooms": total_rooms,
                "available": max(0, total_rooms - booked),
                "revenue": revenue,
                "adr": adr,
                "arrivals": arrivals,
                "departures": departures,
                "in_house": in_house,
            },
            "tomorrow": {
                "occupancy_pct": tmr_occ,
                "arrivals": tmr_arrivals,
            },
            "action_items": {
                "unread_notifications": unread,
                "pending_reviews": pending_reviews,
                "dirty_rooms": dirty_rooms,
                "price_alerts": len(alerts),
            },
            "recent_alerts": [{"title": a["title"], "severity": a.get("severity", "medium"), "type": a.get("sub_type", "")} for a in alerts],
        }

    @router.get("/mobile/arrivals/{property_id}")
    async def mobile_arrivals(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Today's arrivals for mobile quick check-in."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query = {"check_in": today, "status": {"$in": ["confirmed", "pending"]}}
        if property_id != "all":
            query["property_id"] = property_id

        arrivals = await db.bookings.find(query, {"_id": 0}).to_list(50)
        return {
            "date": today,
            "count": len(arrivals),
            "guests": [{
                "id": a.get("id", ""),
                "name": a.get("guest_name", ""),
                "room_type": a.get("room_type_id", ""),
                "room_id": a.get("room_id", ""),
                "nights": a.get("nights", 1),
                "status": a.get("status", ""),
                "total": a.get("total_price", 0),
                "source": a.get("source", ""),
                "registration": a.get("registration_completed", False),
            } for a in arrivals],
        }

    @router.get("/mobile/housekeeping/{property_id}")
    async def mobile_housekeeping(property_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Housekeeping status for mobile."""
        query = {"property_id": property_id} if property_id != "all" else {}
        rooms = await db.rooms.find(query, {"_id": 0}).to_list(200)
        by_status = {"clean": [], "dirty": [], "inspected": []}
        for r in rooms:
            hk = r.get("housekeeping", "clean")
            by_status.setdefault(hk, []).append({
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "floor": r.get("floor", 1),
            })
        return {
            "total": len(rooms),
            "clean": len(by_status.get("clean", [])),
            "dirty": len(by_status.get("dirty", [])),
            "inspected": len(by_status.get("inspected", [])),
            "rooms": by_status,
        }

    return router
