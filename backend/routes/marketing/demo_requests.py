"""
Web sitesi demo talepleri — public landing page'den gelen "Request Demo"
formu kayıtları. Public POST + admin liste/durum yönetimi.
Collection: demo_requests {id, name, email, hotel_name, room_count, message,
  status(new|contacted|closed), created_at, updated_at}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import re
import uuid
import logging

logger = logging.getLogger(__name__)

STATUSES = ("new", "contacted", "closed")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _iso():
    return datetime.now(timezone.utc).isoformat()


def create_demo_requests_router(db, require_roles):
    router = APIRouter()

    @router.post("/public/demo-requests")
    async def submit_demo_request(payload: Dict):
        name = (payload.get("name") or "").strip()[:120]
        email = (payload.get("email") or "").strip().lower()[:200]
        hotel_name = (payload.get("hotel_name") or "").strip()[:200]
        if not name or not hotel_name:
            raise HTTPException(400, "name and hotel_name are required")
        if not EMAIL_RE.match(email):
            raise HTTPException(400, "valid email is required")
        recent = await db.demo_requests.count_documents(
            {"email": email, "status": "new"})
        if recent >= 3:
            raise HTTPException(429, "Too many pending requests for this email")
        doc = {"id": str(uuid.uuid4()), "name": name, "email": email,
               "hotel_name": hotel_name,
               "product": payload.get("product") if payload.get("product") in ("pms", "rms") else "pms",
               "room_count": (payload.get("room_count") or "")[:40],
               "message": (payload.get("message") or "").strip()[:1000],
               "status": "new", "created_at": _iso(), "updated_at": _iso()}
        await db.demo_requests.insert_one(dict(doc))
        doc.pop("_id", None)
        logger.info(f"New demo request from {email} ({hotel_name})")
        return {"ok": True, "id": doc["id"]}

    @router.get("/demo-requests")
    async def list_demo_requests(
        status: str = "",
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        q = {"status": status} if status in STATUSES else {}
        items = await db.demo_requests.find(q, {"_id": 0}).sort(
            "created_at", -1).to_list(500)
        counts = {s: await db.demo_requests.count_documents({"status": s})
                  for s in STATUSES}
        return {"items": items,
                "summary": {**counts, "total": sum(counts.values())}}

    @router.patch("/demo-requests/{req_id}")
    async def update_demo_request(
        req_id: str, payload: Dict,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        status = payload.get("status", "")
        if status not in STATUSES:
            raise HTTPException(400, f"status must be one of {STATUSES}")
        res = await db.demo_requests.update_one(
            {"id": req_id}, {"$set": {"status": status, "updated_at": _iso()}})
        if res.matched_count == 0:
            raise HTTPException(404, "Demo request not found")
        return {"ok": True, "status": status}

    @router.delete("/demo-requests/{req_id}")
    async def delete_demo_request(
        req_id: str,
        current_user: dict = Depends(require_roles("admin")),
    ):
        res = await db.demo_requests.delete_one({"id": req_id})
        if res.deleted_count == 0:
            raise HTTPException(404, "Demo request not found")
        return {"ok": True}

    return router
