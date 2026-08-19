"""Web Sitesi Oluşturucu — şablonlu otel sitesi, tek tık yayınlama (Cloudbeds Websites paritesi)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

TEMPLATES = [
    {"id": "classic", "name": "Klasik", "desc": "Sıcak tonlar, geleneksel otel havası"},
    {"id": "modern", "name": "Modern", "desc": "Koyu zemin, keskin tipografi"},
    {"id": "boutique", "name": "Butik", "desc": "Zarif, minimal, yüksek beyaz alan"},
]


def create_site_builder_router(db, require_roles):
    router = APIRouter(prefix="/site-builder", tags=["site-builder"])
    ROLES = ("admin", "manager")

    @router.get("/templates")
    async def templates(_u: dict = Depends(require_roles(*ROLES))):
        return {"templates": TEMPLATES}

    @router.get("/{pid}")
    async def get_site(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0}) or {"property_id": pid, "template": "classic", "published": False, "content": {}}
        return {"site": cfg, "templates": TEMPLATES}

    @router.post("/{pid}")
    async def save_site(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        tpl = data.get("template", "classic")
        if tpl not in {t["id"] for t in TEMPLATES}:
            raise HTTPException(422, "Geçersiz şablon")
        content = data.get("content") or {}
        if isinstance(content.get("amenities"), list):
            content["amenities"] = ", ".join(str(x) for x in content["amenities"])
        for k in ("headline", "about", "amenities", "phone", "email", "address"):
            if k in content and not isinstance(content[k], str):
                content[k] = str(content[k])
        upd = {"property_id": pid, "template": tpl, "content": content,
               "published": bool(data.get("published")),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.hotel_sites.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, "published": upd["published"], "url": f"/site/{pid}"}

    @router.get("/public/site/{pid}")
    async def public_site(pid: str):
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0})
        if not cfg or not cfg.get("published"):
            raise HTTPException(404, "Site yayında değil")
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1, "city": 1, "country": 1}) or {}
        rts = await db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1, "base_rate": 1, "base_price": 1}).to_list(20)
        return {"site": cfg, "property": prop, "room_types": rts}

    return router
