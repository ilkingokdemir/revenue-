"""
Preventive Maintenance Scheduler (P1).
Recurring maintenance tasks with frequency (daily/weekly/monthly/quarterly/annual).
Automatically generates due instances and flags overdue items.
Compared to reactive `maintenance` (work orders), these are *planned*.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

FREQUENCIES = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 90,
    "semiannual": 182,
    "annual": 365,
}


def create_preventive_maintenance_router(db, require_roles):
    router = APIRouter()

    @router.get("/preventive-maintenance/{property_id}")
    async def list_plans(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "maintenance"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        rows = await db.preventive_maintenance.find(q, {"_id": 0}).sort("next_due", 1).to_list(500)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        overdue = [r for r in rows if r.get("next_due", "") < today and r.get("active", True)]
        due_soon = [r for r in rows if today <= r.get("next_due", "") <= (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")]
        return {
            "plans": rows,
            "overdue_count": len(overdue),
            "due_soon_count": len(due_soon),
            "total": len(rows),
        }

    @router.post("/preventive-maintenance")
    async def create_plan(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Create a recurring PM plan.
        Body: {property_id, name, frequency, category, location, instructions, first_due, assigned_to}
        """
        frequency = data.get("frequency", "monthly")
        if frequency not in FREQUENCIES:
            raise HTTPException(status_code=400, detail=f"frequency must be one of {list(FREQUENCIES)}")

        first_due = data.get("first_due") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        plan = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": (data.get("name") or "").strip(),
            "category": data.get("category", "general"),  # hvac, plumbing, electrical, fire_safety, general
            "location": (data.get("location") or "").strip(),  # e.g. "Room 201 / Building A / Rooftop"
            "instructions": (data.get("instructions") or "").strip(),
            "frequency": frequency,
            "frequency_days": FREQUENCIES[frequency],
            "next_due": first_due,
            "last_completed": None,
            "assigned_to": data.get("assigned_to", ""),
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
            "completion_log": [],
        }
        if not plan["name"]:
            raise HTTPException(status_code=400, detail="name required")
        await db.preventive_maintenance.insert_one(plan)
        plan.pop("_id", None)
        return plan

    @router.post("/preventive-maintenance/{plan_id}/complete")
    async def complete(plan_id: str, data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager", "maintenance"))):
        """Mark a PM as done. Advances next_due by frequency_days and logs the completion."""
        plan = await db.preventive_maintenance.find_one({"id": plan_id}, {"_id": 0})
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        next_due = (datetime.strptime(plan.get("next_due", today_str), "%Y-%m-%d")
                    + timedelta(days=plan.get("frequency_days", 30))).strftime("%Y-%m-%d")
        # If we're way overdue, snap next_due forward from today instead
        if plan.get("next_due", today_str) < today_str:
            next_due = (now + timedelta(days=plan.get("frequency_days", 30))).strftime("%Y-%m-%d")

        log_entry = {
            "at": now.isoformat(),
            "by": current_user.get("name", ""),
            "notes": (data.get("notes") or "").strip(),
            "cost": float(data.get("cost") or 0),
            "parts_used": (data.get("parts_used") or "").strip(),
        }
        await db.preventive_maintenance.update_one(
            {"id": plan_id},
            {"$set": {"last_completed": today_str, "next_due": next_due},
             "$push": {"completion_log": log_entry}}
        )
        return {"status": "completed", "next_due": next_due}

    @router.put("/preventive-maintenance/{plan_id}")
    async def update_plan(plan_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        updates = {k: v for k, v in data.items() if k not in ("id", "_id", "created_at", "completion_log")}
        if "frequency" in updates and updates["frequency"] in FREQUENCIES:
            updates["frequency_days"] = FREQUENCIES[updates["frequency"]]
        await db.preventive_maintenance.update_one({"id": plan_id}, {"$set": updates})
        return await db.preventive_maintenance.find_one({"id": plan_id}, {"_id": 0})

    @router.delete("/preventive-maintenance/{plan_id}")
    async def delete_plan(plan_id: str,
                          current_user: dict = Depends(require_roles("admin"))):
        await db.preventive_maintenance.delete_one({"id": plan_id})
        return {"status": "deleted"}

    return router
