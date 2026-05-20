"""
Digital SOPs Library (Standard Operating Procedures).

Flexkeeping-style SOP management:
  - Managers create step-by-step SOPs for any task
  - Assign SOPs to roles/departments
  - Staff can browse, acknowledge ("read & understood"), and reference SOPs
  - Versioning so updates are tracked
  - Categories: housekeeping, maintenance, fnb, front-office, safety, etc.

Endpoints:
  GET    /api/sops                                   — list SOPs (filtered)
  POST   /api/sops                                   — create
  GET    /api/sops/{sop_id}                          — full detail
  PATCH  /api/sops/{sop_id}                          — update (creates new version if steps changed)
  DELETE /api/sops/{sop_id}                          — admin
  POST   /api/sops/{sop_id}/publish                  — publish draft
  POST   /api/sops/{sop_id}/acknowledge              — user acks current version
  GET    /api/sops/{sop_id}/acknowledgements         — manager view of who's read what
  GET    /api/sops/categories/list                   — list categories
"""
from datetime import datetime, timezone
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


CATEGORIES = {
    "housekeeping", "maintenance", "front-office", "fnb",
    "safety", "security", "compliance", "guest-service", "other"
}


class SopStep(BaseModel):
    order: int
    text: str
    image_url: str = ""
    estimated_minutes: Optional[int] = None


class SopIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: str = "other"
    description: str = ""
    target_roles: List[str] = []         # e.g. ["housekeeping", "manager"]
    property_id: str = "all"
    steps: List[SopStep] = []
    tags: List[str] = []
    estimated_minutes: Optional[int] = None
    required: bool = False               # if true, all target_roles must acknowledge


class SopPatch(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    target_roles: Optional[List[str]] = None
    property_id: Optional[str] = None
    steps: Optional[List[SopStep]] = None
    tags: Optional[List[str]] = None
    estimated_minutes: Optional[int] = None
    required: Optional[bool] = None
    status: Optional[str] = None         # draft | published | archived


def create_sops_router(db, require_roles):
    router = APIRouter()

    @router.get("/sops")
    async def list_sops(
        property_id: str = "",
        category: str = "",
        role: str = "",
        status: str = "",
        q: str = "",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        query: dict = {}
        if property_id and property_id != "all":
            query["$or"] = [{"property_id": property_id}, {"property_id": "all"}]
        if category:
            query["category"] = category
        if role:
            query["target_roles"] = role
        if status:
            query["status"] = status
        if q:
            query["$and"] = [
                {"$or": [
                    {"title": {"$regex": q, "$options": "i"}},
                    {"description": {"$regex": q, "$options": "i"}},
                    {"tags": {"$regex": q, "$options": "i"}},
                ]}
            ]
        # Non-managers only see published
        if current_user.get("role") not in {"admin", "manager"}:
            query["status"] = "published"
        sops = await db.sops.find(query, {"_id": 0, "steps": 0}).sort([("category", 1), ("title", 1)]).to_list(500)
        uid = current_user.get("id") or current_user.get("email") or "anon"
        for s in sops:
            acks = s.get("acknowledged_by", []) or []
            s["acknowledged_by_me"] = uid in acks
            s["ack_count"] = len(acks)
        return {"sops": sops, "count": len(sops)}

    @router.get("/sops/categories/list")
    async def list_categories(_: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance"))):
        return {"categories": sorted(CATEGORIES)}

    @router.get("/sops/{sop_id}")
    async def get_sop(
        sop_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        sop = await db.sops.find_one({"id": sop_id}, {"_id": 0})
        if not sop:
            raise HTTPException(404, "SOP not found")
        if sop.get("status") != "published" and current_user.get("role") not in {"admin", "manager"}:
            raise HTTPException(403, "SOP not published")
        uid = current_user.get("id") or current_user.get("email") or "anon"
        sop["acknowledged_by_me"] = uid in (sop.get("acknowledged_by") or [])
        sop["ack_count"] = len(sop.get("acknowledged_by") or [])
        return sop

    @router.post("/sops")
    async def create_sop(
        body: SopIn,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        if body.category not in CATEGORIES:
            raise HTTPException(400, f"category must be one of {CATEGORIES}")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            **body.dict(),
            "version": 1,
            "status": "draft",
            "created_by": current_user.get("name") or current_user.get("email") or "",
            "created_at": now,
            "updated_at": now,
            "published_at": "",
            "acknowledged_by": [],
        }
        await db.sops.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/sops/{sop_id}")
    async def patch_sop(
        sop_id: str, patch: SopPatch,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        sop = await db.sops.find_one({"id": sop_id}, {"_id": 0})
        if not sop:
            raise HTTPException(404, "SOP not found")
        update = {k: v for k, v in patch.dict().items() if v is not None}
        if "category" in update and update["category"] not in CATEGORIES:
            raise HTTPException(400, "Invalid category")
        if "status" in update and update["status"] not in {"draft", "published", "archived"}:
            raise HTTPException(400, "Invalid status")
        # Bump version + clear acks if steps changed
        if "steps" in update and update["steps"] != sop.get("steps"):
            update["version"] = (sop.get("version") or 1) + 1
            update["acknowledged_by"] = []
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Convert SopStep to dict if needed
        if "steps" in update and update["steps"]:
            update["steps"] = [s.dict() if hasattr(s, "dict") else s for s in update["steps"]]
        await db.sops.update_one({"id": sop_id}, {"$set": update})
        return {"updated": True, "version": update.get("version", sop.get("version"))}

    @router.delete("/sops/{sop_id}")
    async def delete_sop(
        sop_id: str,
        current_user: dict = Depends(require_roles("admin")),
    ):
        result = await db.sops.delete_one({"id": sop_id})
        return {"deleted": result.deleted_count}

    @router.post("/sops/{sop_id}/publish")
    async def publish_sop(
        sop_id: str,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        now = datetime.now(timezone.utc).isoformat()
        result = await db.sops.update_one(
            {"id": sop_id},
            {"$set": {"status": "published", "published_at": now, "updated_at": now}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "SOP not found")
        return {"published": True}

    @router.post("/sops/{sop_id}/acknowledge")
    async def acknowledge_sop(
        sop_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance")),
    ):
        uid = current_user.get("id") or current_user.get("email") or "anon"
        result = await db.sops.update_one(
            {"id": sop_id, "status": "published"},
            {"$addToSet": {"acknowledged_by": uid},
             "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "SOP not found or not published")
        return {"acknowledged": True, "by": uid}

    @router.get("/sops/{sop_id}/acknowledgements")
    async def list_acks(
        sop_id: str,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        sop = await db.sops.find_one({"id": sop_id}, {"_id": 0, "acknowledged_by": 1, "version": 1})
        if not sop:
            raise HTTPException(404, "SOP not found")
        ack_ids = sop.get("acknowledged_by") or []
        users = await db.users.find(
            {"$or": [{"id": {"$in": ack_ids}}, {"email": {"$in": ack_ids}}]},
            {"_id": 0, "id": 1, "email": 1, "name": 1, "role": 1}
        ).to_list(500)
        return {"version": sop.get("version"), "ack_count": len(ack_ids), "users": users}

    return router
