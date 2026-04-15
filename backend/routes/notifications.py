"""
Notifications — In-app alert centre for SLA breaches, routine updates, handover notes, shift changes
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_notifications_router(db, require_roles):
    router = APIRouter()

    @router.get("/notifications")
    async def list_notifications(limit: int = 50, unread_only: str = "",
                                 current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        user_email = current_user.get("email", "")
        query = {"$or": [{"target_user": user_email}, {"target_user": ""}, {"target_role": current_user.get("role", "")}]}
        if unread_only == "true":
            query["read"] = False
        docs = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
        unread_count = await db.notifications.count_documents({**query, "read": False})
        return {"notifications": docs, "unread_count": unread_count}

    @router.post("/notifications")
    async def create_notification(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        notif = {
            "id": str(uuid.uuid4()),
            "type": data.get("type", "info"),
            "title": data.get("title", ""),
            "message": data.get("message", ""),
            "category": data.get("category", "general"),
            "target_user": data.get("target_user", ""),
            "target_role": data.get("target_role", ""),
            "link_to": data.get("link_to", ""),
            "priority": data.get("priority", "normal"),
            "read": False,
            "created_by": current_user.get("name", "System"),
            "created_at": now,
        }
        await db.notifications.insert_one(notif)
        notif.pop("_id", None)
        return notif

    @router.put("/notifications/{notif_id}/read")
    async def mark_read(notif_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        await db.notifications.update_one({"id": notif_id}, {"$set": {"read": True}})
        return {"status": "read"}

    @router.put("/notifications/read-all")
    async def mark_all_read(current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        user_email = current_user.get("email", "")
        query = {"$or": [{"target_user": user_email}, {"target_user": ""}, {"target_role": current_user.get("role", "")}]}
        result = await db.notifications.update_many({**query, "read": False}, {"$set": {"read": True}})
        return {"marked": result.modified_count}

    @router.delete("/notifications/{notif_id}")
    async def delete_notification(notif_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.notifications.delete_one({"id": notif_id})
        return {"status": "deleted"}

    # === AUTO-GENERATE NOTIFICATIONS ===

    @router.post("/notifications/generate-check")
    async def generate_check(current_user: dict = Depends(require_roles("admin", "manager"))):
        """Check for conditions that should trigger notifications"""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        generated = 0

        # 1. SLA breach: Maintenance requests open > 24 hours
        day_ago = (now - __import__('datetime').timedelta(hours=24)).isoformat()
        overdue_maintenance = await db.maintenance_requests.find(
            {"status": {"$in": ["open", "in_progress"]}, "created_at": {"$lt": day_ago}}, {"_id": 0}
        ).to_list(20)
        for m in overdue_maintenance:
            existing = await db.notifications.find_one({"category": "sla_breach", "link_to": m.get("id", "")})
            if not existing:
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "type": "warning", "title": "SLA Breach - Maintenance Overdue",
                    "message": f"Issue '{m.get('issue', 'Unknown')}' has been open for over 24 hours",
                    "category": "sla_breach", "target_user": "", "target_role": "manager",
                    "link_to": m.get("id", ""), "priority": "high", "read": False,
                    "created_by": "System", "created_at": now_iso,
                })
                generated += 1

        # 2. Pending handover notes
        pending_handovers = await db.shift_handover.count_documents({"status": "pending", "priority": {"$in": ["high", "critical"]}})
        if pending_handovers > 0:
            recent = await db.notifications.find_one({"category": "handover_alert", "created_at": {"$gt": day_ago}})
            if not recent:
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "type": "info", "title": "Pending Handover Notes",
                    "message": f"{pending_handovers} high/critical handover note(s) need attention",
                    "category": "handover_alert", "target_user": "", "target_role": "",
                    "link_to": "operations-hub", "priority": "normal", "read": False,
                    "created_by": "System", "created_at": now_iso,
                })
                generated += 1

        # 3. Compliance checks due soon
        tomorrow = (now + __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
        due_checks = await db.compliance_checks.find(
            {"status": "scheduled", "scheduled_date": {"$lte": tomorrow}}, {"_id": 0}
        ).to_list(10)
        for c in due_checks:
            existing = await db.notifications.find_one({"category": "compliance_due", "link_to": c.get("id", "")})
            if not existing:
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "type": "warning", "title": "Compliance Check Due",
                    "message": f"'{c.get('title', 'Check')}' is due by {c.get('scheduled_date', 'soon')}",
                    "category": "compliance_due", "target_user": "", "target_role": "manager",
                    "link_to": c.get("id", ""), "priority": "high", "read": False,
                    "created_by": "System", "created_at": now_iso,
                })
                generated += 1

        # 4. Incomplete routines
        incomplete_routines = await db.routine_history.count_documents({"status": "in_progress"})
        if incomplete_routines > 3:
            recent = await db.notifications.find_one({"category": "routine_alert", "created_at": {"$gt": day_ago}})
            if not recent:
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "type": "info", "title": "Incomplete Routines",
                    "message": f"{incomplete_routines} routine(s) still in progress",
                    "category": "routine_alert", "target_user": "", "target_role": "",
                    "link_to": "operations-hub", "priority": "normal", "read": False,
                    "created_by": "System", "created_at": now_iso,
                })
                generated += 1

        return {"generated": generated}

    return router
