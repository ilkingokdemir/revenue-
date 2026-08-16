"""Kullanıcı bazlı UI tercihleri (tur görüldü bayrakları vb.)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends


def create_ui_prefs_router(db, require_roles):
    router = APIRouter(prefix="/ui-prefs", tags=["ui-prefs"])
    ROLES = ("admin", "manager", "staff")

    @router.get("")
    async def get_prefs(_u: dict = Depends(require_roles(*ROLES))):
        uid = str(_u.get("id") or _u.get("email") or "anon")
        doc = await db.ui_prefs.find_one({"user_id": uid}, {"_id": 0}) or {}
        return {"user_id": uid, "prefs": doc.get("prefs", {})}

    @router.put("")
    async def set_pref(data: dict, _u: dict = Depends(require_roles(*ROLES))):
        uid = str(_u.get("id") or _u.get("email") or "anon")
        key = (data.get("key") or "").strip()[:80]
        if not key:
            return {"ok": False}
        await db.ui_prefs.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, f"prefs.{key}": bool(data.get("value", True)),
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "key": key}

    return router
