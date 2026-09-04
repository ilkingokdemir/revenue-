"""
My Tasks — Personalized daily dashboard aggregating shifts, handover notes, routines, maintenance
"""
from fastapi import APIRouter, Depends, HTTPException
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

        # 6.5 Today's housekeeping tasks assigned to me (urgent first)
        uid = current_user.get("id", "")
        hk_tasks = await db.housekeeping_tasks.find(
            {"due_date": today, "status": {"$in": ["pending", "in_progress"]},
             "assigned_to": {"$in": [v for v in (uid, user_email, user_name) if v]}},
            {"_id": 0}).to_list(50)
        hk_tasks.sort(key=lambda t: (t.get("priority") != "urgent", t.get("created_at", "")))

        # 6.6 Personal to-dos
        personal = await db.personal_tasks.find(
            {"user_email": user_email, "done": {"$ne": True}}, {"_id": 0}
        ).sort("created_at", -1).to_list(30)

        # 7. Notifications count
        notif_q = {"read": False, "$or": [{"target_user": user_email}, {"target_user": ""}, {"target_role": user_role}]}
        unread_notifs = await db.notifications.count_documents(notif_q)

        rc_q = {"source": "root_cause", "status": {"$nin": ["done", "resolved", "completed", "closed"]}}
        root_cause_tasks = await db.staff_tasks.find(rc_q, {"_id": 0}).sort("created_at", -1).to_list(20)

        return {
            "root_cause_tasks": root_cause_tasks,
            "user": {"name": user_name, "role": user_role, "email": user_email},
            "date": today,
            "today_shifts": shifts,
            "week_shifts": week_shifts,
            "handover_notes": handovers,
            "routines": routines,
            "maintenance": maint,
            "compliance": compliance,
            "hk_tasks": hk_tasks,
            "personal_tasks": personal,
            "unread_notifications": unread_notifs,
            "summary": {
                "shifts_today": len(shifts),
                "shifts_this_week": len(week_shifts),
                "pending_handovers": len(handovers),
                "active_routines": len(routines),
                "open_maintenance": len(maint),
                "upcoming_compliance": len(compliance),
                "hk_open": len(hk_tasks),
                "hk_urgent": sum(1 for t in hk_tasks if t.get("priority") == "urgent"),
            }
        }

    @router.put("/my-tasks/staff-task/{task_id}/complete")
    async def complete_staff_task(task_id: str, body: Dict = None, current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "staff"))):
        now = datetime.now(timezone.utc).isoformat()
        r = await db.staff_tasks.update_one({"id": task_id}, {"$set": {"status": "done", "completed_at": now, "updated_at": now,
                                                                       "completed_by": current_user.get("name", current_user.get("email", "")),
                                                                       "completion_notes": str((body or {}).get("notes") or "")[:500]}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"ok": True, "status": "done", "completed_at": now}

    @router.post("/my-tasks/personal")
    async def add_personal_task(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        text = (data.get("text") or "").strip()
        if not text:
            return {"ok": False, "error": "text required"}
        import uuid
        doc = {"id": str(uuid.uuid4()), "user_email": current_user.get("email", ""),
               "text": text[:300], "done": False,
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.personal_tasks.insert_one({**doc})
        return {"ok": True, "task": doc}

    @router.put("/my-tasks/personal/{task_id}")
    async def toggle_personal_task(task_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        await db.personal_tasks.update_one(
            {"id": task_id, "user_email": current_user.get("email", "")},
            {"$set": {"done": bool(data.get("done", True)),
                      "done_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True}

    return router
