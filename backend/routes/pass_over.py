"""
Pass Over Duties — Shift handover notes with priorities, mentions, acknowledgements.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

PRIORITIES = ("low", "normal", "high", "critical")
CATEGORIES = ("general", "maintenance", "guest", "housekeeping", "reception", "finance")


def create_pass_over_router(db, require_roles):
    router = APIRouter()

    @router.get("/operations/pass-over/{property_id}")
    async def list_pass_overs(property_id: str, status: str = "", priority: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        query = {}
        if property_id != "all":
            query["property_id"] = property_id
        if status in ("open", "acknowledged", "archived"):
            query["status"] = status
        if priority in PRIORITIES:
            query["priority"] = priority

        items = await db.pass_overs.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)

        counts = {"open": 0, "acknowledged": 0, "archived": 0, "critical": 0, "high": 0}
        for i in items:
            s = i.get("status", "open")
            if s in counts:
                counts[s] += 1
            p = i.get("priority", "normal")
            if p in counts:
                counts[p] += 1

        return {"items": items, "counts": counts, "total": len(items)}

    @router.post("/operations/pass-over/{property_id}")
    async def create_pass_over(property_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        title = (data.get("title") or "").strip()
        if not title:
            raise HTTPException(400, "Title required")

        priority = data.get("priority", "normal")
        if priority not in PRIORITIES:
            priority = "normal"
        category = data.get("category", "general")
        if category not in CATEGORIES:
            category = "general"

        mentions = data.get("mentions", [])
        if not isinstance(mentions, list):
            mentions = []

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "title": title,
            "message": (data.get("message") or "").strip(),
            "priority": priority,
            "category": category,
            "shift": data.get("shift", ""),          # morning / afternoon / evening / night
            "from_user": current_user.get("name", current_user.get("email", "")),
            "from_role": current_user.get("role", ""),
            "mentions": mentions,                     # list of staff names / ids
            "status": "open",                          # open / acknowledged / archived
            "acknowledgements": [],                    # [{user, role, at}]
            "created_at": now,
            "updated_at": now,
        }
        await db.pass_overs.insert_one({**item})

        # Fan-out in-app notifications (high / urgent priority, or @mentions)
        try:
            targets = []  # list of (target_user_email, target_role)
            if mentions:
                # Resolve mentions (names OR ids OR emails) to user emails
                mentioned_users = await db.users.find(
                    {"$or": [{"email": {"$in": mentions}}, {"id": {"$in": mentions}}, {"name": {"$in": mentions}}]},
                    {"_id": 0, "email": 1, "role": 1}
                ).to_list(100)
                for u in mentioned_users:
                    if u.get("email"):
                        targets.append((u["email"], ""))
            elif priority in ("high", "critical"):
                # Broadcast to operational roles at this property
                for role in ["manager", "receptionist", "housekeeper", "maintenance"]:
                    targets.append(("", role))

            notif_title = f"🚨 URGENT: {title}" if priority == "critical" else f"🔔 Pass-over: {title}"
            for target_email, target_role in targets:
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()),
                    "type": "pass_over",
                    "title": notif_title,
                    "message": item["message"][:200],
                    "category": category,
                    "target_user": target_email,
                    "target_role": target_role,
                    "link_to": f"/pass-over/{item['id']}",
                    "priority": "high" if priority in ("high", "critical") else "normal",
                    "read": False,
                    "created_by": item["from_user"],
                    "created_at": now,
                })
        except Exception:
            pass  # best-effort — do not fail the pass-over creation

        return item

    @router.post("/operations/pass-over/{property_id}/{item_id}/acknowledge")
    async def acknowledge(property_id: str, item_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        ack = {
            "user": current_user.get("name", current_user.get("email", "")),
            "role": current_user.get("role", ""),
            "at": datetime.now(timezone.utc).isoformat(),
        }
        result = await db.pass_overs.update_one(
            {"id": item_id},
            {"$push": {"acknowledgements": ack}, "$set": {"status": "acknowledged", "updated_at": ack["at"]}},
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Pass over not found")
        doc = await db.pass_overs.find_one({"id": item_id}, {"_id": 0})
        return doc

    @router.post("/operations/pass-over/{property_id}/{item_id}/archive")
    async def archive(property_id: str, item_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await db.pass_overs.update_one(
            {"id": item_id},
            {"$set": {"status": "archived", "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Pass over not found")
        return {"archived": True}

    @router.delete("/operations/pass-over/{property_id}/{item_id}")
    async def delete_pass_over(property_id: str, item_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await db.pass_overs.delete_one({"id": item_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Pass over not found")
        return {"deleted": True}

    return router
