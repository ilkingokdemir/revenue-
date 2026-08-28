"""Modül Yöneticisi — menü modüllerini bölümler arası taşıma / gizleme (admin)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user


def create_menu_manager_router(db, require_roles):
    router = APIRouter(tags=["menu-manager"])

    @router.get("/menu-overrides")
    async def get_overrides(current_user: dict = Depends(get_current_user)):
        doc = await db.menu_overrides.find_one({"id": "global"}, {"_id": 0})
        return {"overrides": (doc or {}).get("overrides", {})}

    @router.put("/menu-overrides/{module_id}")
    async def set_override(module_id: str, data: dict,
                           current_user: dict = Depends(require_roles("admin"))):
        section = data.get("section")
        hidden = bool(data.get("hidden", False))
        ov = {}
        if section:
            ov["section"] = str(section)[:60]
        if hidden:
            ov["hidden"] = True
        if not ov:
            # Boş override = varsayılana dön (ör. {hidden:false} ile gizleme kaldırma)
            await db.menu_overrides.update_one(
                {"id": "global"},
                {"$unset": {f"overrides.{module_id}": ""},
                 "$set": {"updated_at": datetime.now(timezone.utc).isoformat(),
                          "updated_by": current_user.get("email", "")}})
            return {"ok": True, "module_id": module_id, "override": None}
        await db.menu_overrides.update_one(
            {"id": "global"},
            {"$set": {f"overrides.{module_id}": ov,
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("email", "")}},
            upsert=True)
        await db.menu_override_log.insert_one({
            "id": str(uuid.uuid4()), "module_id": module_id, "override": ov,
            "by": current_user.get("email", ""), "at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "module_id": module_id, "override": ov}

    @router.delete("/menu-overrides/{module_id}")
    async def remove_override(module_id: str,
                              current_user: dict = Depends(require_roles("admin"))):
        await db.menu_overrides.update_one(
            {"id": "global"},
            {"$unset": {f"overrides.{module_id}": ""},
             "$set": {"updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("email", "")}})
        return {"ok": True, "module_id": module_id}

    @router.post("/menu-overrides/reset")
    async def reset_overrides(current_user: dict = Depends(require_roles("admin"))):
        await db.menu_overrides.update_one(
            {"id": "global"},
            {"$set": {"overrides": {},
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("email", "")}},
            upsert=True)
        return {"ok": True}

    return router
