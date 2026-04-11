"""
Staff Performance Dashboard Routes
Tracks response times, resolution rates, and messaging volumes per agent.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def create_staff_performance_router(db, require_roles):
    """Factory function that creates staff performance routes with injected dependencies"""
    router = APIRouter()

    @router.get("/staff-performance/{property_id}")
    async def staff_performance_overview(
        property_id: str,
        days: int = 30,
        current_user: dict = Depends(require_roles("admin", "manager"))
    ):
        """Comprehensive staff performance metrics"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        prop_filter = {"property_id": property_id} if property_id != "all" else {}

        # --- Get all staff members who sent messages ---
        staff_msg_pipeline = [
            {"$match": {**prop_filter, "sender_type": "staff", "created_at": {"$gte": cutoff}} if prop_filter else {"sender_type": "staff", "created_at": {"$gte": cutoff}}},
            {"$group": {
                "_id": "$sender_name",
                "total_messages": {"$sum": 1},
                "conversations": {"$addToSet": "$conversation_id"},
            }}
        ]
        # We need to join with conversations for the property filter
        msg_match = {"sender_type": "staff", "created_at": {"$gte": cutoff}}
        staff_msg_pipeline = [
            {"$match": msg_match},
            {"$group": {
                "_id": "$sender_name",
                "total_messages": {"$sum": 1},
                "conversations": {"$addToSet": "$conversation_id"},
            }}
        ]

        staff_data = {}
        async for doc in db.messages.aggregate(staff_msg_pipeline):
            name = doc["_id"] or "Unknown"
            if not name or name == "Unknown":
                continue
            staff_data[name] = {
                "name": name,
                "total_messages": doc["total_messages"],
                "conversation_ids": doc["conversations"],
                "conversations_count": len(doc["conversations"]),
            }

        # --- Get conversations assigned to each agent ---
        conv_pipeline = [
            {"$match": {**prop_filter, "assigned_name": {"$ne": ""}}},
            {"$group": {
                "_id": "$assigned_name",
                "assigned_total": {"$sum": 1},
                "resolved": {"$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}},
                "in_progress": {"$sum": {"$cond": [{"$eq": ["$status", "in_progress"]}, 1, 0]}},
                "waiting": {"$sum": {"$cond": [{"$eq": ["$status", "waiting"]}, 1, 0]}},
                "new": {"$sum": {"$cond": [{"$eq": ["$status", "new"]}, 1, 0]}},
            }}
        ]
        async for doc in db.conversations.aggregate(conv_pipeline):
            name = doc["_id"]
            if name not in staff_data:
                staff_data[name] = {
                    "name": name,
                    "total_messages": 0,
                    "conversation_ids": [],
                    "conversations_count": 0,
                }
            staff_data[name]["assigned_total"] = doc["assigned_total"]
            staff_data[name]["resolved"] = doc["resolved"]
            staff_data[name]["in_progress"] = doc["in_progress"]
            staff_data[name]["waiting"] = doc["waiting"]
            staff_data[name]["new_convs"] = doc["new"]
            total = doc["assigned_total"]
            staff_data[name]["resolution_rate"] = round((doc["resolved"] / total * 100) if total > 0 else 0, 1)

        # --- Channel breakdown per agent ---
        channel_pipeline = [
            {"$match": {"sender_type": "staff", "created_at": {"$gte": cutoff}}},
            {"$group": {
                "_id": {"sender": "$sender_name", "channel": "$channel"},
                "count": {"$sum": 1}
            }}
        ]
        async for doc in db.messages.aggregate(channel_pipeline):
            name = doc["_id"]["sender"]
            channel = doc["_id"]["channel"] or "internal"
            if name in staff_data:
                if "channels" not in staff_data[name]:
                    staff_data[name]["channels"] = {}
                staff_data[name]["channels"][channel] = doc["count"]

        # --- Calculate average response times ---
        # For each staff member, find their response times by looking at
        # guest->staff message pairs in conversations they participated in
        for name, data in staff_data.items():
            conv_ids = data.get("conversation_ids", [])
            if not conv_ids:
                data["avg_response_min"] = 0
                data["fastest_response_min"] = 0
                data["slowest_response_min"] = 0
                continue

            # Sample up to 50 conversations for performance
            sample_ids = conv_ids[:50]
            response_times = []
            for conv_id in sample_ids:
                msgs = await db.messages.find(
                    {"conversation_id": conv_id},
                    {"_id": 0, "sender_type": 1, "sender_name": 1, "created_at": 1}
                ).sort("created_at", 1).to_list(100)

                last_guest_time = None
                for msg in msgs:
                    if msg["sender_type"] == "guest":
                        last_guest_time = msg.get("created_at", "")
                    elif msg["sender_type"] == "staff" and msg.get("sender_name") == name and last_guest_time:
                        try:
                            gt = datetime.fromisoformat(last_guest_time.replace("Z", "+00:00"))
                            st = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
                            diff_min = (st - gt).total_seconds() / 60
                            if 0 < diff_min < 1440:  # Only count if within 24 hours
                                response_times.append(round(diff_min, 1))
                        except (ValueError, TypeError):
                            pass
                        last_guest_time = None

            if response_times:
                data["avg_response_min"] = round(sum(response_times) / len(response_times), 1)
                data["fastest_response_min"] = min(response_times)
                data["slowest_response_min"] = max(response_times)
                data["response_count"] = len(response_times)
            else:
                data["avg_response_min"] = 0
                data["fastest_response_min"] = 0
                data["slowest_response_min"] = 0
                data["response_count"] = 0

        # Clean up internal fields and build leaderboard
        agents = []
        for name, data in staff_data.items():
            data.pop("conversation_ids", None)
            if "channels" not in data:
                data["channels"] = {}
            if "assigned_total" not in data:
                data["assigned_total"] = 0
                data["resolved"] = 0
                data["in_progress"] = 0
                data["waiting"] = 0
                data["new_convs"] = 0
                data["resolution_rate"] = 0
            # Score: weighted by messages (40%), resolution rate (30%), response time (30%)
            msg_score = min(data["total_messages"] / 10, 10)  # max 10 pts
            res_score = data["resolution_rate"] / 10  # max 10 pts
            rt_score = max(0, 10 - data["avg_response_min"] / 6) if data["avg_response_min"] > 0 else 5  # max 10 pts
            data["performance_score"] = round(msg_score * 0.4 + res_score * 0.3 + rt_score * 0.3, 1)
            agents.append(data)

        # Sort by performance score
        agents.sort(key=lambda x: x["performance_score"], reverse=True)

        # Add rank
        for i, agent in enumerate(agents):
            agent["rank"] = i + 1

        # --- Daily activity trend (last N days) ---
        daily_pipeline = [
            {"$match": {"sender_type": "staff", "created_at": {"$gte": cutoff}}},
            {"$project": {
                "day": {"$substr": ["$created_at", 0, 10]},
                "sender_name": 1
            }},
            {"$group": {
                "_id": {"day": "$day", "sender": "$sender_name"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.day": 1}}
        ]
        daily_data = {}
        async for doc in db.messages.aggregate(daily_pipeline):
            day = doc["_id"]["day"]
            sender = doc["_id"]["sender"]
            if day not in daily_data:
                daily_data[day] = {}
            daily_data[day][sender] = doc["count"]

        # --- Team totals ---
        total_messages = sum(a["total_messages"] for a in agents)
        total_conversations = sum(a["conversations_count"] for a in agents)
        total_resolved = sum(a.get("resolved", 0) for a in agents)
        total_assigned = sum(a.get("assigned_total", 0) for a in agents)
        avg_response = round(sum(a["avg_response_min"] for a in agents if a["avg_response_min"] > 0) / max(1, len([a for a in agents if a["avg_response_min"] > 0])), 1) if agents else 0
        team_resolution_rate = round((total_resolved / total_assigned * 100) if total_assigned > 0 else 0, 1)

        return {
            "agents": agents,
            "team_summary": {
                "total_agents": len(agents),
                "total_messages": total_messages,
                "total_conversations": total_conversations,
                "total_resolved": total_resolved,
                "team_resolution_rate": team_resolution_rate,
                "avg_response_min": avg_response,
            },
            "daily_trend": daily_data,
            "period_days": days,
        }

    return router
