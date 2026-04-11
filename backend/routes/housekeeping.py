"""
Housekeeping Management Routes
Room status board, task assignment, maintenance requests
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def create_housekeeping_router(db, require_roles):
    router = APIRouter()

    # === Room Status Board ===

    @router.get("/housekeeping/rooms/{property_id}")
    async def get_room_statuses(property_id: str, floor: str = "", status: str = "",
                                 current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {"property_id": property_id}
        if floor: query["floor"] = floor
        if status: query["status"] = status
        docs = await db.room_statuses.find(query, {"_id": 0}).sort("room_number", 1).to_list(500)
        return docs

    @router.put("/housekeeping/rooms/{room_id}/status")
    async def update_room_status(room_id: str, updates: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        if updates.get("status") == "clean":
            updates["last_cleaned_at"] = datetime.now(timezone.utc).isoformat()
            updates["last_cleaned_by"] = current_user.get("name", "Staff")
        await db.room_statuses.update_one({"id": room_id}, {"$set": updates})
        doc = await db.room_statuses.find_one({"id": room_id}, {"_id": 0})
        return doc

    @router.get("/housekeeping/rooms/{property_id}/stats")
    async def room_status_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        total = await db.room_statuses.count_documents({"property_id": property_id})
        clean = await db.room_statuses.count_documents({"property_id": property_id, "status": "clean"})
        dirty = await db.room_statuses.count_documents({"property_id": property_id, "status": "dirty"})
        inspected = await db.room_statuses.count_documents({"property_id": property_id, "status": "inspected"})
        in_progress = await db.room_statuses.count_documents({"property_id": property_id, "status": "in_progress"})
        out_of_order = await db.room_statuses.count_documents({"property_id": property_id, "status": "out_of_order"})
        return {"total": total, "clean": clean, "dirty": dirty, "inspected": inspected,
                "in_progress": in_progress, "out_of_order": out_of_order}

    @router.post("/housekeeping/rooms/seed/{property_id}")
    async def seed_room_statuses(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.room_statuses.count_documents({"property_id": property_id})
        if existing > 0:
            return {"message": f"Already has {existing} rooms", "count": existing}
        from models import RoomStatus
        room_types = await db.room_types.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(20)
        count = 0
        floor_num = 1
        room_num = 101
        statuses = ["clean", "clean", "clean", "dirty", "dirty", "inspected", "clean", "dirty"]
        for rt in room_types:
            inv = rt.get("total_inventory", 0) or 3
            for i in range(inv):
                rs = RoomStatus(
                    property_id=property_id,
                    room_number=str(room_num),
                    room_type_id=rt.get("id", ""),
                    floor=str(floor_num),
                    status=statuses[count % len(statuses)],
                )
                doc = rs.model_dump()
                await db.room_statuses.insert_one(doc)
                count += 1
                room_num += 1
                if room_num % 100 >= 20:
                    floor_num += 1
                    room_num = floor_num * 100 + 1
        return {"message": f"Seeded {count} rooms", "count": count}

    # === Housekeeping Tasks ===

    @router.get("/housekeeping/tasks/{property_id}")
    async def get_tasks(property_id: str, status: str = "", assigned_to: str = "",
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {"property_id": property_id}
        if status: query["status"] = status
        if assigned_to: query["assigned_to"] = assigned_to
        docs = await db.housekeeping_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    @router.post("/housekeeping/tasks")
    async def create_task(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        from models import HousekeepingTask
        task = HousekeepingTask(**data)
        doc = task.model_dump()
        await db.housekeeping_tasks.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/housekeeping/tasks/{task_id}")
    async def update_task(task_id: str, updates: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        if updates.get("status") == "completed":
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
        await db.housekeeping_tasks.update_one({"id": task_id}, {"$set": updates})
        doc = await db.housekeeping_tasks.find_one({"id": task_id}, {"_id": 0})
        return doc

    @router.delete("/housekeeping/tasks/{task_id}")
    async def delete_task(task_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.housekeeping_tasks.delete_one({"id": task_id})
        return {"status": "deleted"}

    # === Maintenance Requests ===

    @router.get("/housekeeping/maintenance/{property_id}")
    async def get_maintenance(property_id: str, status: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {"property_id": property_id}
        if status: query["status"] = status
        docs = await db.maintenance_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/housekeeping/maintenance")
    async def create_maintenance(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        from models import MaintenanceRequest
        req = MaintenanceRequest(**data, reported_by=current_user.get("name", "Staff"))
        doc = req.model_dump()
        await db.maintenance_requests.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/housekeeping/maintenance/{req_id}")
    async def update_maintenance(req_id: str, updates: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        if updates.get("status") == "resolved":
            updates["resolved_at"] = datetime.now(timezone.utc).isoformat()
        await db.maintenance_requests.update_one({"id": req_id}, {"$set": updates})
        doc = await db.maintenance_requests.find_one({"id": req_id}, {"_id": 0})
        return doc

    return router
