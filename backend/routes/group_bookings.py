"""
Group Bookings & Allotments — tour operators, weddings, conferences.

A `GroupBlock` reserves N rooms for a date range with a negotiated rate.
A `RoomingList` ties individual guest names to rooms within the block.
Cut-off date releases unsold inventory back to general pool automatically.

Endpoints:
  GET   /api/groups                            — list group blocks
  POST  /api/groups                            — create group block (allotment)
  PATCH /api/groups/{id}                       — update / release
  POST  /api/groups/{id}/rooming-list          — bulk add rooming list
  GET   /api/groups/{id}/rooming-list          — get rooming list
  POST  /api/groups/{id}/release               — manual release before cut-off
  GET   /api/groups/calendar                   — calendar view (all blocks)
"""
from datetime import datetime, timezone, timedelta
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class GroupBlockIn(BaseModel):
    name: str
    property_id: str
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    organisation: str = ""
    block_type: str = "tour"      # tour | wedding | conference | corporate | other
    rooms_blocked: int = 1
    room_type_id: str = ""
    check_in: str
    check_out: str
    negotiated_rate: float = 0
    cut_off_date: str = ""        # YYYY-MM-DD; auto-release unsold after
    notes: str = ""


class RoomingEntry(BaseModel):
    guest_name: str
    guest_email: str = ""
    guest_phone: str = ""
    room_number: str = ""
    special_requests: str = ""


def create_groups_router(db, require_roles):
    router = APIRouter(prefix="/groups")

    @router.get("")
    async def list_groups(property_id: str = "", status: str = "",
                          _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        if status:
            q["status"] = status
        groups = await db.group_blocks.find(q, {"_id": 0}).sort("check_in", -1).to_list(200)
        # Enrich with rooming count
        for g in groups:
            g["rooming_count"] = await db.group_rooming.count_documents({"group_id": g["id"]})
            g["fill_rate"] = round(g["rooming_count"] / max(1, g.get("rooms_blocked", 1)), 2)
        return {"groups": groups, "count": len(groups)}

    @router.post("")
    async def create_group(body: GroupBlockIn,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        if body.check_out <= body.check_in:
            raise HTTPException(400, "check_out must be after check_in")
        # Default cut-off: 14 days before check_in
        cut_off = body.cut_off_date
        if not cut_off:
            try:
                ci = datetime.strptime(body.check_in, "%Y-%m-%d")
                cut_off = (ci - timedelta(days=14)).strftime("%Y-%m-%d")
            except Exception:
                cut_off = body.check_in
        now = datetime.now(timezone.utc).isoformat()
        nights = (datetime.strptime(body.check_out, "%Y-%m-%d")
                  - datetime.strptime(body.check_in, "%Y-%m-%d")).days
        total_value = body.negotiated_rate * body.rooms_blocked * max(1, nights)
        doc = {"id": str(uuid.uuid4()), **body.dict(),
               "cut_off_date": cut_off, "status": "active",
               "nights": nights, "total_value": round(total_value, 2),
               "created_by": current_user.get("name", ""), "created_at": now}
        await db.group_blocks.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/{group_id}")
    async def patch_group(group_id: str, body: dict,
                          _: dict = Depends(require_roles("admin", "manager"))):
        body["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.group_blocks.update_one({"id": group_id}, {"$set": body})
        if r.matched_count == 0:
            raise HTTPException(404, "Group not found")
        return {"updated": True}

    @router.post("/{group_id}/rooming-list")
    async def add_rooming(group_id: str, entries: List[RoomingEntry],
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        grp = await db.group_blocks.find_one({"id": group_id}, {"_id": 0})
        if not grp:
            raise HTTPException(404, "Group not found")
        existing = await db.group_rooming.count_documents({"group_id": group_id})
        capacity = grp["rooms_blocked"]
        if existing + len(entries) > capacity:
            raise HTTPException(400, f"Exceeds block capacity ({capacity} rooms)")
        now = datetime.now(timezone.utc).isoformat()
        docs = [{"id": str(uuid.uuid4()), "group_id": group_id, **e.dict(),
                 "added_by": current_user.get("name", ""), "added_at": now}
                for e in entries]
        await db.group_rooming.insert_many(docs)
        return {"added": len(docs), "total": existing + len(docs)}

    @router.get("/{group_id}/rooming-list")
    async def get_rooming(group_id: str,
                          _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        entries = await db.group_rooming.find({"group_id": group_id}, {"_id": 0}) \
                                        .sort("guest_name", 1).to_list(500)
        return {"group_id": group_id, "entries": entries, "count": len(entries)}

    @router.post("/{group_id}/release")
    async def release_unsold(group_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        grp = await db.group_blocks.find_one({"id": group_id}, {"_id": 0})
        if not grp:
            raise HTTPException(404, "Group not found")
        sold = await db.group_rooming.count_documents({"group_id": group_id})
        released = max(0, grp.get("rooms_blocked", 0) - sold)
        await db.group_blocks.update_one({"id": group_id},
            {"$set": {"rooms_blocked": sold, "released_rooms": released,
                      "released_at": datetime.now(timezone.utc).isoformat(),
                      "released_by": current_user.get("name", ""),
                      "status": "released" if sold == 0 else "partially-released"}})
        return {"released": released, "remaining": sold}

    @router.get("/calendar")
    async def calendar_view(start_date: str = "", days: int = 90,
                            _: dict = Depends(require_roles("admin", "manager"))):
        if not start_date:
            start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        end = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
        groups = await db.group_blocks.find(
            {"check_in": {"$lt": end}, "check_out": {"$gt": start_date},
             "status": {"$ne": "cancelled"}},
            {"_id": 0}
        ).to_list(200)
        return {"start_date": start_date, "days": days, "groups": groups}

    return router
