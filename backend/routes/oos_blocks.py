"""
Room Out-of-Service / Maintenance Blocks
Simple CRUD — staff mark rooms unavailable for a date range with a reason.
Renders on the calendar as grey striped bars so nobody double-books a room that's being painted.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
import uuid

from auth import require_perm


class OOSBlockIn(BaseModel):
    room_id: str
    start: str  # ISO date
    end: str    # ISO date (exclusive)
    reason: str
    property_id: Optional[str] = None


def create_oos_router(db):
    router = APIRouter()

    @router.get("/rooms/oos-blocks")
    async def list_blocks(
        property_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {}
        if property_id:
            q["property_id"] = property_id
        rows = await db.oos_blocks.find(q, {"_id": 0}).sort("start", 1).to_list(2000)
        return rows

    @router.post("/rooms/oos-blocks")
    async def create_block(
        payload: OOSBlockIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        if payload.end <= payload.start:
            raise HTTPException(400, "end must be after start")
        doc = {
            "id": str(uuid.uuid4()),
            "room_id": payload.room_id,
            "property_id": payload.property_id or "",
            "start": payload.start,
            "end": payload.end,
            "reason": payload.reason.strip() or "Out of Service",
            "created_by": current_user.get("email"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.oos_blocks.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/rooms/oos-blocks/{block_id}")
    async def delete_block(
        block_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        r = await db.oos_blocks.delete_one({"id": block_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Block not found")
        return {"deleted": True}

    return router
