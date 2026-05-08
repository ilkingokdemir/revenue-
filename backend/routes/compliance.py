"""
Compliance Register — Track regulatory/safety/licensing items.
Categories (fire safety, food hygiene, H&S, licensing, insurance, data protection, staff training).
Items have due dates, evidence links, status tracking, and overdue detection.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    {"id": "fire",      "name": "Fire Safety",      "icon": "flame",    "color": "#ef4444"},
    {"id": "food",      "name": "Food Hygiene",     "icon": "utensils", "color": "#f59e0b"},
    {"id": "hs",        "name": "Health & Safety",  "icon": "shield",   "color": "#10b981"},
    {"id": "license",   "name": "Licensing",        "icon": "award",    "color": "#3b82f6"},
    {"id": "insurance", "name": "Insurance",        "icon": "umbrella", "color": "#8b5cf6"},
    {"id": "gdpr",      "name": "Data Protection",  "icon": "lock",     "color": "#06b6d4"},
    {"id": "training",  "name": "Staff Training",   "icon": "book",     "color": "#ec4899"},
]

STATUSES = ("compliant", "action_needed", "overdue", "expiring_soon", "not_applicable")


def _compute_status(item: dict) -> str:
    due = item.get("due_date", "")
    current = item.get("status", "")
    if current == "not_applicable":
        return "not_applicable"
    if not due:
        return current or "action_needed"
    try:
        d = datetime.strptime(due, "%Y-%m-%d").date()
    except Exception:
        return current or "action_needed"
    today = date.today()
    days = (d - today).days
    if days < 0:
        return "overdue"
    if days <= 30:
        return "expiring_soon"
    return current or "compliant"


def create_compliance_router(db, require_roles):
    router = APIRouter()

    @router.get("/compliance/categories/{property_id}")
    async def get_categories(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        # Overlay counts by category
        items = await db.compliance_items.find({}, {"_id": 0}).to_list(1000)
        # Optional custom categories saved in DB
        custom = await db.compliance_categories.find({}, {"_id": 0}).to_list(100)
        cats = DEFAULT_CATEGORIES + [c for c in custom if c.get("id") not in {x["id"] for x in DEFAULT_CATEGORIES}]
        out = []
        for c in cats:
            matched = [i for i in items if i.get("category") == c["id"]]
            overdue = sum(1 for i in matched if _compute_status(i) == "overdue")
            expiring = sum(1 for i in matched if _compute_status(i) == "expiring_soon")
            out.append({**c, "total": len(matched), "overdue": overdue, "expiring_soon": expiring})
        return {"categories": out}

    @router.get("/compliance/items/{property_id}")
    async def list_items(property_id: str, category: str = "", status: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        query = {}
        if property_id != "all":
            query["property_id"] = property_id
        if category:
            query["category"] = category
        raw = await db.compliance_items.find(query, {"_id": 0}).sort("due_date", 1).to_list(500)
        for i in raw:
            i["computed_status"] = _compute_status(i)
        if status:
            raw = [i for i in raw if i["computed_status"] == status]

        # Summary KPIs
        all_items = await db.compliance_items.find({} if property_id == "all" else {"property_id": property_id}, {"_id": 0}).to_list(1000)
        kpis = {"total": len(all_items), "compliant": 0, "overdue": 0, "expiring_soon": 0, "action_needed": 0}
        for i in all_items:
            s = _compute_status(i)
            if s in kpis:
                kpis[s] += 1
        return {"items": raw, "kpis": kpis}

    @router.post("/compliance/items/{property_id}")
    async def create_item(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        title = (data.get("title") or "").strip()
        if not title:
            raise HTTPException(400, "Title required")
        category = data.get("category", "hs")
        if category not in {c["id"] for c in DEFAULT_CATEGORIES} and not await db.compliance_categories.find_one({"id": category}):
            category = "hs"

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "title": title,
            "category": category,
            "description": (data.get("description") or "").strip(),
            "due_date": data.get("due_date", ""),
            "last_checked": data.get("last_checked", ""),
            "status": data.get("status", "compliant"),
            "assigned_to": data.get("assigned_to", ""),
            "evidence_url": data.get("evidence_url", ""),
            "frequency": data.get("frequency", "annual"),  # weekly/monthly/quarterly/annual/once
            "notes": (data.get("notes") or "").strip(),
            "created_at": now,
            "updated_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.compliance_items.insert_one({**item})
        return item

    @router.put("/compliance/items/{property_id}/{item_id}")
    async def update_item(property_id: str, item_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"title", "category", "description", "due_date", "last_checked", "status", "assigned_to", "evidence_url", "frequency", "notes"}
        updates = {k: v for k, v in data.items() if k in allowed}
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await db.compliance_items.update_one({"id": item_id}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Item not found")
        doc = await db.compliance_items.find_one({"id": item_id}, {"_id": 0})
        doc["computed_status"] = _compute_status(doc)
        return doc

    @router.post("/compliance/items/{property_id}/{item_id}/check")
    async def mark_checked(property_id: str, item_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        today = date.today().isoformat()
        updates = {"last_checked": today, "status": "compliant", "updated_at": datetime.now(timezone.utc).isoformat(), "checked_by": current_user.get("name", "")}
        result = await db.compliance_items.update_one({"id": item_id}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Item not found")
        return {"ok": True, "last_checked": today}

    @router.delete("/compliance/items/{property_id}/{item_id}")
    async def delete_item(property_id: str, item_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.compliance_items.delete_one({"id": item_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Item not found")
        return {"deleted": True}

    return router
