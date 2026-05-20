"""
My Tasks — Personalized daily dashboard aggregating shifts, handover notes, routines, maintenance
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def create_my_tasks_router(db, require_roles):
    router = APIRouter()

    @router.get("/my-tasks")
    async def get_my_tasks(current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        user_name = current_user.get("name", "")
        user_email = current_user.get("email", "")
        user_role = current_user.get("role", "")
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        week_start_dt = now - timedelta(days=now.weekday())
        week_start = week_start_dt.strftime("%Y-%m-%d")

        # 1. Today's shifts
        shifts = await db.shift_entries.find(
            {"staff_name": user_name, "date": today}, {"_id": 0}
        ).to_list(10)

        # 2. This week's shifts
        week_shifts = await db.shift_entries.find(
            {"staff_name": user_name, "week_start": week_start}, {"_id": 0}
        ).sort("date", 1).to_list(50)

        # 3. Pending handover notes (assigned to user or their role)
        handover_q = {"status": "pending", "$or": [
            {"owner": {"$regex": user_name, "$options": "i"}},
            {"role_target": user_role},
            {"role_target": ""},
        ]}
        handovers = await db.shift_handover.find(handover_q, {"_id": 0}).sort("created_at", -1).to_list(20)

        # 4. In-progress routines (started by user or unassigned)
        routines = await db.routine_history.find(
            {"status": "in_progress", "$or": [{"user": user_name}, {"user": {"$regex": "shared|unassigned", "$options": "i"}}]},
            {"_id": 0}
        ).sort("created_at", -1).to_list(10)

        # 5. Assigned maintenance requests
        maint = await db.maintenance_requests.find(
            {"status": {"$in": ["open", "in_progress"]}, "$or": [
                {"assignees": {"$elemMatch": {"$regex": user_name, "$options": "i"}}},
                {"assigned_to": {"$regex": user_name, "$options": "i"}},
            ]}, {"_id": 0}
        ).sort("created_at", -1).to_list(20)

        # 6. Upcoming compliance checks (for managers)
        compliance = []
        if user_role in ("admin", "manager"):
            tomorrow = (now + timedelta(days=7)).strftime("%Y-%m-%d")
            compliance = await db.compliance_checks.find(
                {"status": "scheduled", "scheduled_date": {"$lte": tomorrow}}, {"_id": 0}
            ).to_list(10)

        # 7. Notifications count
        notif_q = {"read": False, "$or": [{"target_user": user_email}, {"target_user": ""}, {"target_role": user_role}]}
        unread_notifs = await db.notifications.count_documents(notif_q)

        return {
            "user": {"name": user_name, "role": user_role, "email": user_email},
            "date": today,
            "today_shifts": shifts,
            "week_shifts": week_shifts,
            "handover_notes": handovers,
            "routines": routines,
            "maintenance": maint,
            "compliance": compliance,
            "unread_notifications": unread_notifs,
            "summary": {
                "shifts_today": len(shifts),
                "shifts_this_week": len(week_shifts),
                "pending_handovers": len(handovers),
                "active_routines": len(routines),
                "open_maintenance": len(maint),
                "upcoming_compliance": len(compliance),
            }
        }

    return router
