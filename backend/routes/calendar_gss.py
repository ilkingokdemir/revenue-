"""
Real-time Availability Calendar & Guest Satisfaction Score Routes
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def create_calendar_gss_router(db, require_roles):
    """Factory function for availability calendar and GSS routes"""
    router = APIRouter()

    @router.get("/availability/calendar/{property_id}")
    async def availability_calendar(
        property_id: str,
        month: str = "",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        """Real-time availability calendar — rooms available per day for a month"""
        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")

        year, m = month.split("-")
        y, m = int(year), int(m)

        # Calculate month boundaries
        start_date = f"{y}-{str(m).zfill(2)}-01"
        if m == 12:
            end_date = f"{y+1}-01-01"
        else:
            end_date = f"{y}-{str(m+1).zfill(2)}-01"

        # Days in month
        if m in [1, 3, 5, 7, 8, 10, 12]:
            days_in_month = 31
        elif m in [4, 6, 9, 11]:
            days_in_month = 30
        elif y % 4 == 0 and (y % 100 != 0 or y % 400 == 0):
            days_in_month = 29
        else:
            days_in_month = 28

        # Get room types for this property
        prop_filter = {"property_id": property_id} if property_id != "all" else {}
        room_types = await db.room_types.find({**prop_filter, "is_active": True}, {"_id": 0}).to_list(100)

        total_inventory = {}
        room_type_info = []
        for rt in room_types:
            rt_id = rt.get("id", "")
            inv = rt.get("total_inventory", 0)
            total_inventory[rt_id] = inv
            room_type_info.append({
                "id": rt_id,
                "name": rt.get("name", ""),
                "total_rooms": inv,
                "base_price": rt.get("base_price", 0),
                "max_guests": rt.get("max_guests", 2),
            })

        # Get bookings overlapping this month
        bookings = await db.bookings.find({
            **prop_filter,
            "status": {"$nin": ["cancelled"]},
            "$or": [
                {"check_in": {"$gte": start_date, "$lt": end_date}},
                {"check_out": {"$gt": start_date, "$lte": end_date}},
                {"check_in": {"$lt": start_date}, "check_out": {"$gt": end_date}},
            ]
        }, {"_id": 0, "check_in": 1, "check_out": 1, "room_type_id": 1, "guest_name": 1, "booking_ref": 1, "status": 1}).to_list(1000)

        # Build day-by-day availability
        days = {}
        for d in range(1, days_in_month + 1):
            date_str = f"{y}-{str(m).zfill(2)}-{str(d).zfill(2)}"
            occupied_by_type = {}
            day_bookings = []

            for b in bookings:
                ci = b.get("check_in", "")
                co = b.get("check_out", "")
                # Guest occupies room from check_in to check_out-1
                if ci <= date_str < co:
                    rt = b.get("room_type_id", "unknown")
                    occupied_by_type[rt] = occupied_by_type.get(rt, 0) + 1
                    day_bookings.append({
                        "guest": b.get("guest_name", ""),
                        "ref": b.get("booking_ref", ""),
                        "room_type": rt,
                        "check_in": ci,
                        "check_out": co,
                        "status": b.get("status", ""),
                    })

            total_rooms_all = sum(total_inventory.values())
            total_occupied = sum(occupied_by_type.values())
            total_available = max(0, total_rooms_all - total_occupied)

            room_availability = []
            for rt_id, inv in total_inventory.items():
                occ = occupied_by_type.get(rt_id, 0)
                room_availability.append({
                    "room_type_id": rt_id,
                    "total": inv,
                    "occupied": occ,
                    "available": max(0, inv - occ),
                })

            occupancy_pct = round((total_occupied / total_rooms_all * 100) if total_rooms_all > 0 else 0, 1)

            days[date_str] = {
                "date": date_str,
                "total_rooms": total_rooms_all,
                "occupied": total_occupied,
                "available": total_available,
                "occupancy_pct": occupancy_pct,
                "rooms": room_availability,
                "bookings": day_bookings[:10],  # Limit to 10 per day
                "bookings_count": len(day_bookings),
            }

        # Month summary
        occ_values = [d["occupancy_pct"] for d in days.values()]
        avg_occupancy = round(sum(occ_values) / len(occ_values), 1) if occ_values else 0
        peak_day = max(days.values(), key=lambda d: d["occupancy_pct"]) if days else None
        lowest_day = min(days.values(), key=lambda d: d["occupancy_pct"]) if days else None

        return {
            "month": month,
            "days_in_month": days_in_month,
            "room_types": room_type_info,
            "days": days,
            "summary": {
                "avg_occupancy": avg_occupancy,
                "peak_day": peak_day["date"] if peak_day else "",
                "peak_occupancy": peak_day["occupancy_pct"] if peak_day else 0,
                "lowest_day": lowest_day["date"] if lowest_day else "",
                "lowest_occupancy": lowest_day["occupancy_pct"] if lowest_day else 0,
                "total_bookings": len(bookings),
            }
        }

    @router.get("/gss/{property_id}")
    async def guest_satisfaction_score(
        property_id: str,
        days: int = 30,
        current_user: dict = Depends(require_roles("admin", "manager"))
    ):
        """Guest Satisfaction Score — composite KPI from reviews, messaging, and response times"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        prop_filter = {"property_id": property_id} if property_id != "all" else {}

        # === 1. Review Score (0-100) ===
        review_pipeline = [
            {"$match": {**prop_filter, "created_at": {"$gte": cutoff}}},
            {"$group": {
                "_id": None,
                "avg_rating": {"$avg": "$rating"},
                "count": {"$sum": 1},
                "five_star": {"$sum": {"$cond": [{"$eq": ["$rating", 5]}, 1, 0]}},
                "four_star": {"$sum": {"$cond": [{"$eq": ["$rating", 4]}, 1, 0]}},
                "three_star": {"$sum": {"$cond": [{"$eq": ["$rating", 3]}, 1, 0]}},
                "two_star": {"$sum": {"$cond": [{"$eq": ["$rating", 2]}, 1, 0]}},
                "one_star": {"$sum": {"$cond": [{"$eq": ["$rating", 1]}, 1, 0]}},
            }}
        ]
        review_data = None
        async for doc in db.reviews.aggregate(review_pipeline):
            review_data = doc

        if review_data and review_data["count"] > 0:
            review_score = round((review_data["avg_rating"] / 5) * 100, 1)
            review_count = review_data["count"]
            avg_rating = round(review_data["avg_rating"], 2)
            rating_dist = {
                "5": review_data["five_star"],
                "4": review_data["four_star"],
                "3": review_data["three_star"],
                "2": review_data["two_star"],
                "1": review_data["one_star"],
            }
        else:
            review_score = 0
            review_count = 0
            avg_rating = 0
            rating_dist = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}

        # All-time avg for comparison
        all_time_pipeline = [
            {"$match": prop_filter} if prop_filter else {"$match": {}},
            {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}}
        ]
        all_time_data = None
        async for doc in db.reviews.aggregate(all_time_pipeline):
            all_time_data = doc
        all_time_avg = round(all_time_data["avg"], 2) if all_time_data and all_time_data["count"] > 0 else 0

        # === 2. Messaging Sentiment Score (0-100) ===
        msg_filter = {**prop_filter} if prop_filter else {}
        total_convs = await db.conversations.count_documents(msg_filter)
        positive_convs = await db.conversations.count_documents({**msg_filter, "sentiment": "positive"})
        neutral_convs = await db.conversations.count_documents({**msg_filter, "sentiment": "neutral"})
        negative_convs = await db.conversations.count_documents({**msg_filter, "sentiment": "negative"})

        if total_convs > 0:
            # Positive=100, Neutral=60, Negative=20, Unknown=50
            scored_convs = positive_convs + neutral_convs + negative_convs
            if scored_convs > 0:
                sentiment_score = round(
                    (positive_convs * 100 + neutral_convs * 60 + negative_convs * 20) / scored_convs, 1
                )
            else:
                sentiment_score = 50  # No sentiment data
        else:
            sentiment_score = 0

        # === 3. Response Efficiency Score (0-100) ===
        resolved = await db.conversations.count_documents({**msg_filter, "status": "resolved"})
        open_convs = await db.conversations.count_documents({**msg_filter, "status": {"$in": ["new", "in_progress", "waiting"]}})
        resolution_rate = round((resolved / total_convs * 100) if total_convs > 0 else 0, 1)

        # Staff response data
        staff_msgs = await db.messages.find(
            {"sender_type": "staff", "created_at": {"$gte": cutoff}},
            {"_id": 0, "conversation_id": 1, "created_at": 1}
        ).to_list(500)

        response_times = []
        for msg in staff_msgs[:100]:  # Sample for performance
            conv_id = msg["conversation_id"]
            # Find last guest message before this staff reply
            guest_msg = await db.messages.find_one(
                {"conversation_id": conv_id, "sender_type": "guest", "created_at": {"$lt": msg["created_at"]}},
                {"_id": 0, "created_at": 1},
                sort=[("created_at", -1)]
            )
            if guest_msg:
                try:
                    gt = datetime.fromisoformat(guest_msg["created_at"].replace("Z", "+00:00"))
                    st = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
                    diff_min = (st - gt).total_seconds() / 60
                    if 0 < diff_min < 1440:
                        response_times.append(diff_min)
                except (ValueError, TypeError):
                    pass

        avg_response_min = round(sum(response_times) / len(response_times), 1) if response_times else 0

        # Response efficiency: 100 if < 5min, 80 if < 15min, 60 if < 30min, 40 if < 60min, 20 if > 60min
        if avg_response_min == 0:
            response_score = 0
        elif avg_response_min < 5:
            response_score = 100
        elif avg_response_min < 15:
            response_score = 80
        elif avg_response_min < 30:
            response_score = 65
        elif avg_response_min < 60:
            response_score = 45
        else:
            response_score = max(20, round(100 - avg_response_min))

        # === Composite GSS ===
        # Weights: Reviews 50%, Sentiment 25%, Response Efficiency 25%
        active_components = 0
        weighted_sum = 0
        if review_count > 0:
            weighted_sum += review_score * 50
            active_components += 50
        if total_convs > 0:
            weighted_sum += sentiment_score * 25
            active_components += 25
        if len(response_times) > 0:
            weighted_sum += response_score * 25
            active_components += 25

        gss = round(weighted_sum / active_components, 1) if active_components > 0 else 0

        # GSS rating label
        if gss >= 90:
            gss_label = "Exceptional"
        elif gss >= 80:
            gss_label = "Excellent"
        elif gss >= 70:
            gss_label = "Very Good"
        elif gss >= 60:
            gss_label = "Good"
        elif gss >= 50:
            gss_label = "Average"
        else:
            gss_label = "Needs Improvement"

        # === Trend: compare to previous period ===
        prev_cutoff = (datetime.now(timezone.utc) - timedelta(days=days * 2)).isoformat()
        prev_review_pipeline = [
            {"$match": {**prop_filter, "created_at": {"$gte": prev_cutoff, "$lt": cutoff}}},
            {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}, "count": {"$sum": 1}}}
        ]
        prev_review = None
        async for doc in db.reviews.aggregate(prev_review_pipeline):
            prev_review = doc
        prev_avg = round(prev_review["avg_rating"], 2) if prev_review and prev_review["count"] > 0 else 0
        prev_score = round((prev_avg / 5) * 100, 1) if prev_avg > 0 else 0
        trend = round(gss - prev_score, 1) if prev_score > 0 else 0

        return {
            "gss": gss,
            "gss_label": gss_label,
            "trend": trend,
            "period_days": days,
            "components": {
                "review_score": review_score,
                "sentiment_score": sentiment_score,
                "response_score": response_score,
            },
            "reviews": {
                "avg_rating": avg_rating,
                "all_time_avg": all_time_avg,
                "count": review_count,
                "distribution": rating_dist,
            },
            "messaging": {
                "total_conversations": total_convs,
                "positive": positive_convs,
                "neutral": neutral_convs,
                "negative": negative_convs,
                "resolved": resolved,
                "open": open_convs,
                "resolution_rate": resolution_rate,
            },
            "response": {
                "avg_response_min": avg_response_min,
                "responses_measured": len(response_times),
            },
        }

    return router
