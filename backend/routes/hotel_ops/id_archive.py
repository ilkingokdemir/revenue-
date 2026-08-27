"""Misafir Kimlik Arşivi — rezervasyona bağlı kimlik belgeleri + KVKK saklama süresi ve imha."""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException

DEFAULT_RETENTION_DAYS = 365


def _now():
    return datetime.now(timezone.utc)


def create_id_archive_router(db, require_roles):
    router = APIRouter(prefix="/id-archive", tags=["id-archive"])
    ROLES = ("admin", "manager")

    async def _retention() -> int:
        cfg = await db.id_archive_config.find_one({}, {"_id": 0})
        return int((cfg or {}).get("retention_days", DEFAULT_RETENTION_DAYS))

    @router.get("")
    async def archive(property_id: str = "all",
                      _u: dict = Depends(require_roles(*ROLES))):
        retention = await _retention()
        q = {"id_uploaded": True}
        if property_id != "all":
            q["property_id"] = property_id
        regs = await db.guest_registrations.find(
            q, {"_id": 0, "id": 1, "booking_id": 1, "property_id": 1,
                "guest_name": 1, "id_file_path": 1, "id_filename": 1,
                "id_purged": 1, "id_purged_at": 1}).to_list(500)
        bids = [r["booking_id"] for r in regs if r.get("booking_id")]
        bookings = {b["id"]: b async for b in db.bookings.find(
            {"id": {"$in": bids}},
            {"_id": 0, "id": 1, "check_in": 1, "check_out": 1, "status": 1})}
        today = _now().date().isoformat()
        items = []
        for r in regs:
            b = bookings.get(r.get("booking_id"), {})
            co = (b.get("check_out") or "")[:10]
            expires = ""
            if co:
                try:
                    expires = (datetime.strptime(co, "%Y-%m-%d")
                               + timedelta(days=retention)).date().isoformat()
                except Exception:
                    pass
            purged = bool(r.get("id_purged"))
            status = ("imha edildi" if purged
                      else "imha bekliyor" if expires and expires < today
                      else "saklamada")
            fname = os.path.basename(r.get("id_file_path") or "")
            items.append({"registration_id": r["id"], "booking_id": r.get("booking_id"),
                          "property_id": r.get("property_id"),
                          "guest_name": r.get("guest_name", ""),
                          "original_filename": r.get("id_filename", ""),
                          "url": f"/api/uploads/ids/{fname}" if fname and not purged else None,
                          "check_out": co, "expires_at": expires, "status": status,
                          "purged_at": r.get("id_purged_at")})
        items.sort(key=lambda x: (x["status"] != "imha bekliyor", x["expires_at"] or "9999"))
        pending = sum(1 for i in items if i["status"] == "imha bekliyor")
        return {"retention_days": retention, "items": items,
                "total": len(items), "pending_purge": pending,
                "note": f"KVKK: kimlik belgeleri çıkış tarihinden itibaren {retention} gün saklanır, süre dolunca imha edilmelidir. İmha edilen dosyalara erişim kalıcı olarak kapanır (410)."}

    @router.put("/config")
    async def put_config(data: Dict, u: dict = Depends(require_roles("admin"))):
        days = max(30, min(int(data.get("retention_days", DEFAULT_RETENTION_DAYS) or DEFAULT_RETENTION_DAYS), 3650))
        await db.id_archive_config.update_one(
            {}, {"$set": {"retention_days": days, "updated_at": _now().isoformat(),
                          "updated_by": u.get("name") or u.get("email", "")}}, upsert=True)
        return {"ok": True, "retention_days": days}

    @router.post("/purge-expired")
    async def purge_expired(u: dict = Depends(require_roles("admin"))):
        retention = await _retention()
        regs = await db.guest_registrations.find(
            {"id_uploaded": True, "id_purged": {"$ne": True}},
            {"_id": 0, "id": 1, "booking_id": 1, "id_file_path": 1}).to_list(500)
        today = _now().date()
        purged = 0
        for r in regs:
            b = await db.bookings.find_one({"id": r.get("booking_id")},
                                           {"_id": 0, "check_out": 1})
            co = ((b or {}).get("check_out") or "")[:10]
            if not co:
                continue
            try:
                expires = datetime.strptime(co, "%Y-%m-%d").date() + timedelta(days=retention)
            except Exception:
                continue
            if expires >= today:
                continue
            path = r.get("id_file_path") or ""
            fname = os.path.basename(path)
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
            if fname:
                await db.upload_blocklist.update_one(
                    {"path": f"ids/{fname}"},
                    {"$set": {"reason": "KVKK imha", "by": u.get("name", ""),
                              "created_at": _now().isoformat()}}, upsert=True)
            await db.guest_registrations.update_one(
                {"id": r["id"]},
                {"$set": {"id_purged": True, "id_purged_at": _now().isoformat()}})
            purged += 1
        await db.id_archive_purge_log.insert_one({
            "id": str(uuid.uuid4()), "purged": purged,
            "by": u.get("name") or u.get("email", ""), "created_at": _now().isoformat()})
        return {"ok": True, "purged": purged}

    return router
