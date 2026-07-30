"""
Department Shortcuts — her departman için kenar çubuğu görev/kısayol listesi.
Admin/manager ekleyip çıkarır; o departmandaki kullanıcılar sidebar'da hazır görür.

Collection: department_shortcuts { department, items: [menu ids], updated_at, updated_by }

Endpoints (/api/department-shortcuts/*):
- GET  /                → tüm departmanların listeleri (defaults dahil)
- GET  /{department}    → tek departman
- PUT  /{department}    → {items: [...]} kaydet (edit_users yetkisi)
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_perm
from models import VALID_DEPARTMENTS

DEFAULT_SHORTCUTS = {
    "front_desk": ["arrivals", "walkin", "unified-inbox", "calendar", "logbook"],
    "management": ["dashboard", "tier1-dashboard", "revenue", "finance", "analytics", "team"],
    "housekeeping": ["housekeeping", "hk-dispatch", "my-tasks", "lost-found"],
    "food_beverage": ["pos", "kds", "menu-engineering", "events"],
    "maintenance": ["ops-v2", "ops-quick", "asset-register", "my-tasks"],
    "spa_wellness": ["spa-activities", "timeslots", "my-tasks"],
    "concierge": ["concierge-inbox", "guest-profiles", "messaging", "my-tasks"],
}


class ShortcutsIn(BaseModel):
    items: List[str]


def create_department_shortcuts_router(db):
    router = APIRouter(prefix="/department-shortcuts")

    async def _get(department: str) -> dict:
        doc = await db.department_shortcuts.find_one({"department": department}, {"_id": 0})
        if doc:
            return doc
        return {"department": department, "items": DEFAULT_SHORTCUTS.get(department, []), "is_default": True}

    @router.get("")
    async def list_all(current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        return [await _get(d) for d in VALID_DEPARTMENTS]

    @router.get("/{department}")
    async def get_one(department: str,
                      current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        if department not in VALID_DEPARTMENTS:
            raise HTTPException(400, f"Invalid department. Valid: {VALID_DEPARTMENTS}")
        return await _get(department)

    @router.put("/{department}")
    async def save(department: str, body: ShortcutsIn,
                   current_user: dict = Depends(require_perm("edit_users"))):
        if department not in VALID_DEPARTMENTS:
            raise HTTPException(400, f"Invalid department. Valid: {VALID_DEPARTMENTS}")
        items = [s.strip() for s in body.items if s and s.strip()][:15]
        await db.department_shortcuts.update_one(
            {"department": department},
            {"$set": {"department": department, "items": items,
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("email", "")}},
            upsert=True,
        )
        return {"ok": True, "department": department, "items": items}

    @router.get("/badges/{property_id}")
    async def badges(property_id: str,
                     current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Canlı rozet sayıları — mobil görev kartları için."""
        today = datetime.now(timezone.utc).date().isoformat()
        q_prop = {} if property_id in ("all", "") else {"property_id": property_id}
        arrivals = await db.bookings.count_documents(
            {**q_prop, "check_in": today, "status": {"$nin": ["cancelled", "checked_in", "checked_out"]}})
        dirty = await db.hk_turnover.count_documents({**q_prop, "state": "vacant_dirty"})
        open_tasks = await db.staff_tasks.count_documents(
            {**q_prop, "status": {"$nin": ["done", "completed", "cancelled"]}})
        return {"arrivals": arrivals, "housekeeping": dirty, "hk-dispatch": dirty, "my-tasks": open_tasks}

    return router
