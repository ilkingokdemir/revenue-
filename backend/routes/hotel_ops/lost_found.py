"""
Lost & Found — Track lost items, guest matching, claim process
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_lost_found_router(db, require_roles):
    router = APIRouter()

    @router.get("/lost-found/{property_id}")
    async def list_items(property_id: str, status: str = "", category: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        if status:
            pq["status"] = status
        if category:
            pq["category"] = category
        docs = await db.lost_found.find(pq, {"_id": 0}).sort("found_date", -1).to_list(200)
        stats = {
            "total": await db.lost_found.count_documents(pq),
            "unclaimed": await db.lost_found.count_documents({**pq, "status": "unclaimed"}),
            "claimed": await db.lost_found.count_documents({**pq, "status": "claimed"}),
            "disposed": await db.lost_found.count_documents({**pq, "status": "disposed"}),
        }
        return {"items": docs, "stats": stats}

    @router.post("/lost-found")
    async def create_item(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "item_name": data.get("item_name", ""),
            "description": data.get("description", ""),
            "category": data.get("category", "personal"),
            "found_location": data.get("found_location", ""),
            "found_by": data.get("found_by", current_user.get("name", "")),
            "found_date": data.get("found_date", now[:10]),
            "storage_location": data.get("storage_location", ""),
            "guest_name": data.get("guest_name", ""),
            "guest_room": data.get("guest_room", ""),
            "guest_contact": data.get("guest_contact", ""),
            "status": "unclaimed",
            "claimed_by": "", "claimed_date": "", "disposed_date": "",
            "notes": data.get("notes", ""),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.lost_found.insert_one(item)
        item.pop("_id", None)
        return item

    @router.put("/lost-found/{item_id}")
    async def update_item(item_id: str, updates: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        now = datetime.now(timezone.utc).isoformat()
        if updates.get("status") == "claimed":
            updates["claimed_date"] = now
        if updates.get("status") == "disposed":
            updates["disposed_date"] = now
        await db.lost_found.update_one({"id": item_id}, {"$set": updates})
        return await db.lost_found.find_one({"id": item_id}, {"_id": 0})

    @router.delete("/lost-found/{item_id}")
    async def delete_item(item_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.lost_found.delete_one({"id": item_id})
        return {"status": "deleted"}

    return router
