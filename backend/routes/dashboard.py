"""
Dashboard, Concierge Analytics, and Space Bookings Admin Routes
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def create_dashboard_router(db, require_roles):
    """Factory function that creates dashboard routes with injected dependencies"""
    router = APIRouter()

    # --- AI Concierge Analytics ---

    @router.get("/concierge/analytics/{property_id}")
    async def concierge_analytics(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        total_chats = len(await db.concierge_chats.distinct("session_id", {"property_id": property_id}))
        total_msgs = await db.concierge_chats.count_documents({"property_id": property_id})
        user_msgs = await db.concierge_chats.count_documents({"property_id": property_id, "role": "user"})
        pipeline = [
            {"$match": {"property_id": property_id, "role": "user"}},
            {"$sort": {"created_at": -1}},
            {"$group": {"_id": "$session_id", "first_message": {"$last": "$content"}, "last_active": {"$first": "$created_at"}, "msg_count": {"$sum": 1}}},
            {"$sort": {"last_active": -1}},
            {"$limit": 20}
        ]
        sessions = []
        async for doc in db.concierge_chats.aggregate(pipeline):
            sessions.append({"session_id": doc["_id"], "first_message": doc["first_message"][:80], "last_active": doc["last_active"], "messages": doc["msg_count"]})
        return {
            "total_sessions": total_chats, "total_messages": total_msgs,
            "user_messages": user_msgs, "ai_messages": total_msgs - user_msgs,
            "recent_sessions": sessions
        }

    # --- Space Bookings Admin ---

    @router.get("/spaces/admin/bookings/{property_id}")
    async def admin_space_bookings(property_id: str, date: str = "", status: str = "", current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {"property_id": property_id}
        if date:
            query["booking_date"] = date
        if status:
            query["status"] = status
        docs = await db.space_bookings.find(query, {"_id": 0}).sort("booking_date", -1).to_list(200)
        return docs

    @router.get("/spaces/admin/stats/{property_id}")
    async def space_booking_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        total = await db.space_bookings.count_documents({"property_id": property_id})
        confirmed = await db.space_bookings.count_documents({"property_id": property_id, "status": "confirmed"})
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_count = await db.space_bookings.count_documents({"property_id": property_id, "booking_date": today})
        pipeline = [
            {"$match": {"property_id": property_id, "status": "confirmed"}},
            {"$group": {"_id": None, "total_revenue": {"$sum": "$total_price"}, "total_hours": {"$sum": "$hours"}}}
        ]
        rev = None
        async for doc in db.space_bookings.aggregate(pipeline):
            rev = doc
        spaces_count = await db.property_spaces.count_documents({"property_id": property_id, "is_active": True})
        return {
            "total_bookings": total, "confirmed": confirmed, "today": today_count,
            "total_revenue": rev["total_revenue"] if rev else 0,
            "total_hours": rev["total_hours"] if rev else 0,
            "spaces_count": spaces_count
        }

    @router.put("/spaces/admin/bookings/{booking_id}/status")
    async def update_space_booking_status(booking_id: str, status: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        await db.space_bookings.update_one({"id": booking_id}, {"$set": {"status": status}})
        return {"status": "updated"}

    # --- Dashboard Home ---

    @router.get("/dashboard/overview/{property_id}")
    async def dashboard_overview(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Comprehensive dashboard overview for hotel managers"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")

        prop_filter = {"property_id": property_id} if property_id != "all" else {}
        booking_filter = {**prop_filter, "status": {"$ne": "cancelled"}}

        today_checkins = await db.bookings.count_documents({**booking_filter, "check_in": today})
        today_checkouts = await db.bookings.count_documents({**booking_filter, "check_out": today})
        current_guests = await db.bookings.count_documents({**booking_filter, "check_in": {"$lte": today}, "check_out": {"$gte": today}})
        tomorrow_checkins = await db.bookings.count_documents({**booking_filter, "check_in": tomorrow})
        total_bookings = await db.bookings.count_documents(booking_filter)

        revenue_pipeline = [
            {"$match": {**booking_filter, "created_at": {"$gte": month_start}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_price"}, "count": {"$sum": 1}}}
        ]
        month_rev = None
        async for doc in db.bookings.aggregate(revenue_pipeline):
            month_rev = doc

        week_pipeline = [
            {"$match": {**booking_filter, "created_at": {"$gte": week_ago}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_price"}, "count": {"$sum": 1}}}
        ]
        week_rev = None
        async for doc in db.bookings.aggregate(week_pipeline):
            week_rev = doc

        total_rooms = 0
        room_types = await db.room_types.find({**prop_filter}, {"_id": 0, "total_inventory": 1}).to_list(100)
        for rt in room_types:
            total_rooms += rt.get("total_inventory", 0)
        occupancy = round((current_guests / total_rooms * 100) if total_rooms > 0 else 0, 1)

        msg_filter = {"property_id": property_id} if property_id != "all" else {}
        unread_msgs = await db.conversations.count_documents({**msg_filter, "unread_count": {"$gt": 0}})
        open_convs = await db.conversations.count_documents({**msg_filter, "status": {"$in": ["new", "in_progress"]}})
        total_convs = await db.conversations.count_documents(msg_filter)

        total_reviews = await db.reviews.count_documents(prop_filter)
        pending_reviews = await db.reviews.count_documents({**prop_filter, "status": "pending"})
        avg_pipeline = [
            {"$match": prop_filter},
            {"$group": {"_id": None, "avg": {"$avg": "$rating"}}}
        ]
        avg_rating = 0
        async for doc in db.reviews.aggregate(avg_pipeline):
            avg_rating = round(doc["avg"], 1)

        auto_filter = {"property_id": property_id} if property_id != "all" else {}
        auto_sent_today = await db.automation_logs.count_documents({**auto_filter, "created_at": {"$gte": today}})
        auto_failed = await db.automation_logs.count_documents({**auto_filter, "status": "failed", "created_at": {"$gte": today}})

        recent_bookings = await db.bookings.find(booking_filter, {"_id": 0, "guest_name": 1, "booking_ref": 1, "check_in": 1, "check_out": 1, "total_price": 1, "created_at": 1, "room_type_id": 1}).sort("created_at", -1).to_list(5)
        recent_messages = await db.conversations.find({**msg_filter, "unread_count": {"$gt": 0}}, {"_id": 0, "id": 1, "guest_name": 1, "channel": 1, "last_message_preview": 1, "last_message_at": 1, "priority": 1}).sort("last_message_at", -1).to_list(5)
        recent_reviews_list = await db.reviews.find(prop_filter, {"_id": 0, "guest_name": 1, "rating": 1, "platform": 1, "review_text": 1, "created_at": 1, "status": 1}).sort("created_at", -1).to_list(5)

        return {
            "bookings": {
                "today_checkins": today_checkins,
                "today_checkouts": today_checkouts,
                "current_guests": current_guests,
                "tomorrow_checkins": tomorrow_checkins,
                "total": total_bookings,
                "total_rooms": total_rooms,
                "occupancy": occupancy,
            },
            "revenue": {
                "month_total": month_rev["total"] if month_rev else 0,
                "month_bookings": month_rev["count"] if month_rev else 0,
                "week_total": week_rev["total"] if week_rev else 0,
                "week_bookings": week_rev["count"] if week_rev else 0,
            },
            "messaging": {
                "unread": unread_msgs,
                "open": open_convs,
                "total": total_convs,
            },
            "reviews": {
                "total": total_reviews,
                "pending": pending_reviews,
                "avg_rating": avg_rating,
            },
            "automation": {
                "sent_today": auto_sent_today,
                "failed_today": auto_failed,
            },
            "recent": {
                "bookings": recent_bookings,
                "messages": recent_messages,
                "reviews": recent_reviews_list,
            }
        }

    return router
