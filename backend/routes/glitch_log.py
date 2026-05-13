"""
Glitch Log & Shift Handover.

Flexkeeping-style daily glitch register that passes context between shifts.
Front-office, HK, and management add issues/events that the next shift must know.

Endpoints:
  GET    /api/glitch-log/{property_id}                  — list (filtered)
  POST   /api/glitch-log                                — create
  PATCH  /api/glitch-log/{glitch_id}                    — update/acknowledge
  DELETE /api/glitch-log/{glitch_id}                    — admin only
  POST   /api/glitch-log/{glitch_id}/acknowledge        — mark read by current user
  GET    /api/glitch-log/handover/{property_id}         — handover packet for a shift
"""
from datetime import datetime, timezone, timedelta
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field


SEVERITIES = {"info", "minor", "major", "critical"}
DEPARTMENTS = {"front-office", "housekeeping", "maintenance", "fnb", "management", "security", "other"}
SHIFTS = {"morning", "afternoon", "night"}


class GlitchIn(BaseModel):
    property_id: str
    title: str = Field(min_length=2, max_length=200)
    description: str = ""
    severity: str = "minor"     # info | minor | major | critical
    department: str = "other"   # front-office | housekeeping | ...
    shift: str = "morning"      # morning | afternoon | night
    date: str = ""              # YYYY-MM-DD, defaults to today
    related_booking_ref: str = ""
    related_room: str = ""
    needs_followup: bool = True
    tags: List[str] = []


class GlitchPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    department: Optional[str] = None
    shift: Optional[str] = None
    status: Optional[str] = None  # open | resolved | dismissed
    resolution: Optional[str] = None
    needs_followup: Optional[bool] = None
    tags: Optional[List[str]] = None


def create_glitch_log_router(db, require_roles):
    router = APIRouter()

    @router.get("/glitch-log/{property_id}")
    async def list_glitches(
        property_id: str,
        date: str = "",
        shift: str = "",
        status: str = "",
        severity: str = "",
        department: str = "",
        days: int = 7,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        q: dict = {} if property_id == "all" else {"property_id": property_id}
        if date:
            q["date"] = date
        else:
            since = (datetime.now(timezone.utc).date() - timedelta(days=max(1, days))).isoformat()
            q["date"] = {"$gte": since}
        if shift:
            q["shift"] = shift
        if status:
            q["status"] = status
        if severity:
            q["severity"] = severity
        if department:
            q["department"] = department
        glitches = await db.glitch_log.find(q, {"_id": 0}).sort([("date", -1), ("created_at", -1)]).to_list(500)
        # Count unread per current user
        uid = current_user.get("id") or current_user.get("email") or "anon"
        for g in glitches:
            acks = g.get("acknowledged_by", []) or []
            g["acknowledged_by_me"] = uid in acks
            g["ack_count"] = len(acks)
        return {"glitches": glitches, "count": len(glitches)}

    @router.post("/glitch-log")
    async def create_glitch(
        body: GlitchIn,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        if body.severity not in SEVERITIES:
            raise HTTPException(400, f"severity must be one of {SEVERITIES}")
        if body.department not in DEPARTMENTS:
            raise HTTPException(400, f"department must be one of {DEPARTMENTS}")
        if body.shift not in SHIFTS:
            raise HTTPException(400, f"shift must be one of {SHIFTS}")
        date = body.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            **body.dict(),
            "date": date,
            "status": "open",
            "resolution": "",
            "created_by": current_user.get("name") or current_user.get("email") or "",
            "created_by_id": current_user.get("id") or current_user.get("email") or "",
            "created_at": now,
            "updated_at": now,
            "acknowledged_by": [],
        }
        await db.glitch_log.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/glitch-log/{glitch_id}")
    async def patch_glitch(
        glitch_id: str, patch: GlitchPatch,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        update = {k: v for k, v in patch.dict().items() if v is not None}
        if not update:
            return {"updated": 0}
        if "severity" in update and update["severity"] not in SEVERITIES:
            raise HTTPException(400, "Invalid severity")
        if "department" in update and update["department"] not in DEPARTMENTS:
            raise HTTPException(400, "Invalid department")
        if "shift" in update and update["shift"] not in SHIFTS:
            raise HTTPException(400, "Invalid shift")
        if "status" in update and update["status"] not in {"open", "resolved", "dismissed"}:
            raise HTTPException(400, "Invalid status")
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        if update.get("status") in ("resolved", "dismissed"):
            update["resolved_by"] = current_user.get("name", "")
            update["resolved_at"] = update["updated_at"]
        result = await db.glitch_log.update_one({"id": glitch_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(404, "Glitch not found")
        return {"updated": result.modified_count}

    @router.delete("/glitch-log/{glitch_id}")
    async def delete_glitch(
        glitch_id: str,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        result = await db.glitch_log.delete_one({"id": glitch_id})
        return {"deleted": result.deleted_count}

    @router.post("/glitch-log/{glitch_id}/acknowledge")
    async def acknowledge_glitch(
        glitch_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        uid = current_user.get("id") or current_user.get("email") or "anon"
        await db.glitch_log.update_one(
            {"id": glitch_id},
            {"$addToSet": {"acknowledged_by": uid},
             "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"acknowledged": True, "by": uid}

    @router.get("/glitch-log/handover/{property_id}")
    async def shift_handover(
        property_id: str,
        from_shift: str = Query("", description="The shift handing over (morning|afternoon|night)"),
        date: str = "",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        """Compact handover packet: today's open glitches grouped by severity."""
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        q: dict = {"date": date, "status": "open"}
        if property_id != "all":
            q["property_id"] = property_id
        if from_shift:
            q["shift"] = from_shift
        items = await db.glitch_log.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
        grouped = {"critical": [], "major": [], "minor": [], "info": []}
        for g in items:
            grouped.setdefault(g.get("severity", "minor"), []).append(g)
        return {
            "property_id": property_id,
            "date": date,
            "from_shift": from_shift,
            "summary": {
                "total_open": len(items),
                "by_severity": {k: len(v) for k, v in grouped.items()},
            },
            "items_by_severity": grouped,
        }

    return router
