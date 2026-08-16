"""Mükerrer oda tipi kayıtlarını güvenli birleştirme (dry-run + merge, denetim loglu)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

REF_COLLECTIONS = ("bookings", "rooms", "rate_overrides")


async def _find_dup_groups(db, pid: str):
    q = {"property_id": pid} if pid and pid != "all" else {}
    rows = await db.room_types.find(q, {"_id": 0, "id": 1, "property_id": 1,
                                        "name": 1, "base_rate": 1}).to_list(500)
    groups = {}
    for r in rows:
        key = (r.get("property_id"), (r.get("name") or "").strip().lower())
        groups.setdefault(key, []).append(r)
    out = []
    for (prop, name), members in groups.items():
        if len(members) < 2:
            continue
        for m in members:
            m["booking_refs"] = await db.bookings.count_documents({"room_type_id": m["id"]})
        members.sort(key=lambda x: -x["booking_refs"])
        out.append({"property_id": prop, "name": name,
                    "keeper": members[0], "duplicates": members[1:]})
    return out


def create_data_cleanup_router(db, require_roles):
    router = APIRouter(prefix="/data-cleanup", tags=["data-cleanup"])

    @router.get("/room-types/{pid}")
    async def dry_run(pid: str, _u: dict = Depends(require_roles("admin", "manager"))):
        groups = await _find_dup_groups(db, pid)
        total = await db.room_types.count_documents(
            {"property_id": pid} if pid != "all" else {})
        return {"property_id": pid, "total_room_types": total,
                "duplicate_groups": groups, "clean": len(groups) == 0,
                "note": "Birleştirmede en çok rezervasyon referansı olan kayıt korunur; bookings/rooms/rate_overrides referansları ona taşınır."}

    @router.post("/room-types/{pid}/merge")
    async def merge(pid: str, _u: dict = Depends(require_roles("admin"))):
        groups = await _find_dup_groups(db, pid)
        merged, remapped = 0, 0
        now = datetime.now(timezone.utc).isoformat()
        for g in groups:
            keeper_id = g["keeper"]["id"]
            for dup in g["duplicates"]:
                for col in REF_COLLECTIONS:
                    r = await db[col].update_many(
                        {"room_type_id": dup["id"]}, {"$set": {"room_type_id": keeper_id}})
                    remapped += r.modified_count
                await db.pms_rate_mapping.update_many(
                    {"rms_room_id": dup["id"]}, {"$set": {"rms_room_id": keeper_id}})
                await db.room_types.delete_one({"id": dup["id"]})
                merged += 1
                await db.data_cleanup_log.insert_one({
                    "type": "room_type_merge", "property_id": g["property_id"],
                    "kept": keeper_id, "removed": dup["id"], "name": g["name"],
                    "by": str(_u.get("email") or ""), "at": now})
        return {"ok": True, "merged": merged, "references_remapped": remapped,
                "remaining_groups": 0 if merged else len(groups)}

    return router
