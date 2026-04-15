"""
Shift Scheduler — Weekly calendar, staff scheduling, payroll tracking, bulk actions
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_shifts_router(db, require_roles):
    router = APIRouter()

    # ==================== STAFF MEMBERS ====================

    @router.get("/shifts/staff/{property_id}")
    async def list_staff(property_id: str, role: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if role:
            query["role"] = role
        docs = await db.shift_staff.find(query, {"_id": 0}).sort("name", 1).to_list(200)
        return docs

    @router.post("/shifts/staff")
    async def create_staff(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        member = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": data.get("name", ""),
            "role": data.get("role", "housekeeper"),
            "pay_type": data.get("pay_type", "daily"),
            "pay_rate": data.get("pay_rate", 0),
            "currency": data.get("currency", "GBP"),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "is_active": True,
            "created_at": now,
        }
        await db.shift_staff.insert_one(member)
        member.pop("_id", None)
        return member

    @router.put("/shifts/staff/{staff_id}")
    async def update_staff(staff_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.shift_staff.update_one({"id": staff_id}, {"$set": updates})
        return await db.shift_staff.find_one({"id": staff_id}, {"_id": 0})

    @router.delete("/shifts/staff/{staff_id}")
    async def delete_staff(staff_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.shift_staff.delete_one({"id": staff_id})
        return {"status": "deleted"}

    # ==================== SHIFT ENTRIES ====================

    @router.get("/shifts/entries/{property_id}")
    async def list_shifts(property_id: str, week_start: str = "", status: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if week_start:
            query["week_start"] = week_start
        if status:
            query["status"] = status
        docs = await db.shift_entries.find(query, {"_id": 0}).sort("date", 1).to_list(500)
        return docs

    @router.post("/shifts/entries")
    async def create_shift(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "staff_id": data.get("staff_id", ""),
            "staff_name": data.get("staff_name", ""),
            "role": data.get("role", ""),
            "date": data.get("date", ""),
            "week_start": data.get("week_start", ""),
            "start_time": data.get("start_time", "09:00"),
            "end_time": data.get("end_time", "17:00"),
            "status": data.get("status", "planned"),
            "notes": data.get("notes", ""),
            "pay_type": data.get("pay_type", "daily"),
            "pay_rate": data.get("pay_rate", 0),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.shift_entries.insert_one(entry)
        entry.pop("_id", None)
        return entry

    @router.put("/shifts/entries/{shift_id}")
    async def update_shift(shift_id: str, updates: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.shift_entries.update_one({"id": shift_id}, {"$set": updates})
        return await db.shift_entries.find_one({"id": shift_id}, {"_id": 0})

    @router.delete("/shifts/entries/{shift_id}")
    async def delete_shift(shift_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.shift_entries.delete_one({"id": shift_id})
        return {"status": "deleted"}

    # ==================== BULK ACTIONS ====================

    @router.post("/shifts/bulk/copy-week")
    async def copy_week(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        source_week = data.get("source_week", "")
        target_week = data.get("target_week", "")
        property_id = data.get("property_id", "")
        if not source_week or not target_week:
            raise HTTPException(400, "source_week and target_week required")
        query = {"week_start": source_week}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        source_shifts = await db.shift_entries.find(query, {"_id": 0}).to_list(500)
        src_date = datetime.strptime(source_week, "%Y-%m-%d")
        tgt_date = datetime.strptime(target_week, "%Y-%m-%d")
        delta = (tgt_date - src_date).days
        now = datetime.now(timezone.utc).isoformat()
        new_shifts = []
        for s in source_shifts:
            ns = {**s}
            ns["id"] = str(uuid.uuid4())
            ns["week_start"] = target_week
            old_date = datetime.strptime(s["date"], "%Y-%m-%d")
            ns["date"] = (old_date + timedelta(days=delta)).strftime("%Y-%m-%d")
            ns["status"] = "planned"
            ns["created_at"] = now
            new_shifts.append(ns)
        if new_shifts:
            await db.shift_entries.insert_many(new_shifts)
            for ns in new_shifts:
                ns.pop("_id", None)
        return {"copied": len(new_shifts)}

    @router.post("/shifts/bulk/clear-week")
    async def clear_week(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"week_start": week_start}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        result = await db.shift_entries.delete_many(query)
        return {"deleted": result.deleted_count}

    @router.post("/shifts/bulk/publish-all")
    async def publish_all(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"week_start": week_start, "status": {"$in": ["draft", "planned"]}}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        result = await db.shift_entries.update_many(query, {"$set": {"status": "published"}})
        return {"published": result.modified_count}

    @router.post("/shifts/bulk/mark-completed")
    async def mark_completed(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"week_start": week_start, "status": {"$in": ["published", "planned"]}}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        result = await db.shift_entries.update_many(query, {"$set": {"status": "completed"}})
        return {"completed": result.modified_count}

    @router.post("/shifts/bulk/approve-completed")
    async def approve_completed(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"week_start": week_start, "status": "completed"}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        result = await db.shift_entries.update_many(query, {"$set": {"status": "approved"}})
        return {"approved": result.modified_count}

    # ==================== PAYROLL SUMMARY ====================

    @router.get("/shifts/payroll/{property_id}")
    async def payroll_summary(property_id: str, week_start: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if week_start:
            query["week_start"] = week_start
        shifts = await db.shift_entries.find(query, {"_id": 0}).to_list(500)
        staff_totals = {}
        for s in shifts:
            sid = s.get("staff_id", "")
            if sid not in staff_totals:
                staff_totals[sid] = {"staff_id": sid, "staff_name": s.get("staff_name", ""), "role": s.get("role", ""),
                                     "total_shifts": 0, "total_hours": 0, "total_pay": 0, "currency": s.get("currency", "GBP")}
            staff_totals[sid]["total_shifts"] += 1
            try:
                start = datetime.strptime(s.get("start_time", "09:00"), "%H:%M")
                end = datetime.strptime(s.get("end_time", "17:00"), "%H:%M")
                hours = (end - start).seconds / 3600
            except Exception:
                hours = 8
            staff_totals[sid]["total_hours"] += hours
            pay_type = s.get("pay_type", "daily")
            pay_rate = s.get("pay_rate", 0)
            if pay_type == "hourly":
                staff_totals[sid]["total_pay"] += hours * pay_rate
            else:
                staff_totals[sid]["total_pay"] += pay_rate
        return list(staff_totals.values())

    return router
