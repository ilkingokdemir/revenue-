"""Yetki Matrisi (kim / hangi tesis / hangi izin) + değişiklik geçmişi + tesis geocode."""
import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response

from routes.platform_ext.admin import DEFAULT_PERMISSIONS, MODULES, ACTIONS, REVIEW_ACTIONS

ALL_ACTIONS = ACTIONS + REVIEW_ACTIONS


async def log_perm_change(db, actor: dict, target: dict, field: str, before, after, property_id: str = ""):
    if before == after:
        return
    await db.permission_changes.insert_one({
        "id": str(uuid.uuid4()), "actor_id": str((actor or {}).get("id") or (actor or {}).get("_id") or ""),
        "actor_name": (actor or {}).get("name") or (actor or {}).get("email") or "system",
        "target_id": str((target or {}).get("id") or (target or {}).get("_id") or ""),
        "target_name": (target or {}).get("name") or (target or {}).get("email") or "",
        "field": field, "before": before, "after": after, "property_id": property_id,
        "created_at": datetime.now(timezone.utc).isoformat()})


def _effective(user: dict, custom_roles: Dict[str, dict], property_id: Optional[str]) -> dict:
    """{module: [actions]} — has_permission ile aynı öncelik: custom_permissions > tesis rolü > genel rol."""
    pr = user.get("property_roles") or {}
    if user.get("custom_permissions") and not (property_id and property_id in pr):
        return {"role": "custom", "perms": user["custom_permissions"]}
    role = pr.get(property_id) if property_id else None
    role = role or user.get("role", "")
    perms = DEFAULT_PERMISSIONS.get(role) or (custom_roles.get(role) or {}).get("permissions") or {}
    return {"role": role, "perms": perms}


def create_permission_matrix_router(db, require_roles):
    router = APIRouter()

    async def _matrix(property_id: str):
        props = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(200)
        pids = [p["id"] for p in props] if property_id in ("", "all") else [property_id]
        custom_roles = {r["id"]: r for r in await db.custom_roles.find({}, {"_id": 0}).to_list(100)}
        rows = []
        async for u in db.users.find({}, {"password": 0, "password_hash": 0}):
            uid = str(u.get("id") or u.get("_id"))
            per_prop = {}
            for pid in pids:
                if u.get("property_access") and pid not in u["property_access"] and u.get("role") != "admin":
                    per_prop[pid] = {"role": "—", "perms": {}, "no_access": True}
                    continue
                per_prop[pid] = _effective(u, custom_roles, pid)
            rows.append({"user_id": uid, "name": u.get("name", ""), "email": u.get("email", ""), "role": u.get("role", ""),
                         "property_roles": u.get("property_roles") or {}, "has_custom": bool(u.get("custom_permissions")),
                         "sso": u.get("sso_provider") or "", "per_property": per_prop})
        rows.sort(key=lambda r: (r["role"] != "admin", r["name"].lower()))
        return {"properties": [p for p in props if p["id"] in pids], "modules": MODULES, "actions": ALL_ACTIONS,
                "roles": list(DEFAULT_PERMISSIONS.keys()) + list(custom_roles.keys()), "rows": rows,
                "generated_at": datetime.now(timezone.utc).isoformat()}

    @router.get("/admin/permission-matrix")
    async def permission_matrix(property_id: str = "all", _u: dict = Depends(require_roles("admin"))):
        return await _matrix(property_id)

    @router.get("/admin/permission-matrix.csv")
    async def permission_matrix_csv(property_id: str = "all", _u: dict = Depends(require_roles("admin"))):
        m = await _matrix(property_id)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["user", "email", "global_role", "property", "effective_role"] + MODULES)
        for r in m["rows"]:
            for p in m["properties"]:
                e = r["per_property"].get(p["id"], {})
                w.writerow([r["name"], r["email"], r["role"], p["name"], e.get("role", "")] +
                           ["|".join(e.get("perms", {}).get(mod) or []) for mod in MODULES])
        fn = f"permission-matrix-{datetime.now(timezone.utc).date().isoformat()}.csv"
        return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{fn}"'})

    @router.get("/admin/permission-changes")
    async def permission_changes(limit: int = 50, user_id: str = "", _u: dict = Depends(require_roles("admin"))):
        q = {"target_id": user_id} if user_id else {}
        return {"items": await db.permission_changes.find(q, {"_id": 0}).sort("created_at", -1).to_list(max(1, min(500, limit)))}

    # ---------------- TESİS KONUMU (Google Hotel Ads için) ----------------
    @router.post("/properties/{pid}/geocode")
    async def geocode(pid: str, data: Dict, _u: dict = Depends(require_roles("admin", "manager"))):
        prop = await db.properties.find_one({"id": pid}, {"_id": 0})
        if not prop:
            raise HTTPException(404, "Tesis yok")
        site = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0, "content.address": 1}) or {}
        q = (data.get("query") or "").strip() or ", ".join(x for x in [prop.get("address") or (site.get("content") or {}).get("address"), prop.get("city"), prop.get("country")] if x)
        if not q:
            raise HTTPException(422, "Adres yok — sorgu metni girin")
        try:
            async with httpx.AsyncClient(timeout=12, headers={"User-Agent": "MyHotelBox/1.0 (geocode)"}) as c:
                r = await c.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "json", "limit": 1})
            hits = r.json() if r.status_code == 200 else []
        except Exception as e:
            raise HTTPException(502, f"Geocode servisi yanıt vermedi: {str(e)[:80]}")
        if not hits:
            raise HTTPException(404, "Adres bulunamadı — haritadan manuel girin")
        lat, lon = round(float(hits[0]["lat"]), 6), round(float(hits[0]["lon"]), 6)
        return {"query": q, "latitude": lat, "longitude": lon, "display_name": hits[0].get("display_name", "")}

    @router.put("/properties/{pid}/location")
    async def set_location(pid: str, data: Dict, _u: dict = Depends(require_roles("admin", "manager"))):
        try:
            lat, lon = float(data.get("latitude")), float(data.get("longitude"))
        except (TypeError, ValueError):
            raise HTTPException(422, "latitude/longitude sayı olmalı")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise HTTPException(422, "Koordinat aralık dışı")
        upd = {"latitude": round(lat, 6), "longitude": round(lon, 6), "location_updated_at": datetime.now(timezone.utc).isoformat()}
        for k in ("address", "city", "country", "country_code", "postcode", "phone"):
            if data.get(k):
                upd[k] = str(data[k])[:120]
        r = await db.properties.update_one({"id": pid}, {"$set": upd})
        if not r.matched_count:
            raise HTTPException(404, "Tesis yok")
        return {"ok": True, **upd}

    @router.get("/properties/{pid}/location")
    async def get_location(pid: str, _u: dict = Depends(require_roles("admin", "manager"))):
        p = await db.properties.find_one({"id": pid}, {"_id": 0, "latitude": 1, "longitude": 1, "address": 1, "city": 1, "country": 1, "country_code": 1, "postcode": 1, "phone": 1, "name": 1})
        if not p:
            raise HTTPException(404, "Tesis yok")
        return p

    return router
