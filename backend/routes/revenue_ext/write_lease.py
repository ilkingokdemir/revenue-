"""
Kira & Çit (Lease/Fencing) Yazım Kilidi — RevenueIQ gap P1.
Aynı fiyat hücresine (property × oda tipi × gece) iki otomatik yazıcı aynı anda giremez.
Her yazım sahiplik kirası (lease) + aktör imzası taşır; kira süresi dolunca hücre serbest kalır.
Operatör egemendir: manuel yazım robot kiralarını iptal eder (force-release).
Collection: rate_cell_leases {property_id, room_type_id, date, owner, token, acquired_at, expires_at}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid


def _now():
    return datetime.now(timezone.utc)


async def acquire_lease(db, pid: str, rt_id: str, date: str, owner: str,
                        ttl_seconds: int = 900) -> str | None:
    """Hücre kirası al. Başka aktif sahibi varsa None döner (çit). Aynı sahip yeniler."""
    now = _now()
    await db.rate_cell_leases.delete_many({"expires_at": {"$lt": now.isoformat()}})
    existing = await db.rate_cell_leases.find_one(
        {"property_id": pid, "room_type_id": rt_id, "date": date}, {"_id": 0})
    if existing and existing["owner"] != owner and existing["expires_at"] > now.isoformat():
        return None
    token = str(uuid.uuid4())
    await db.rate_cell_leases.update_one(
        {"property_id": pid, "room_type_id": rt_id, "date": date},
        {"$set": {"owner": owner, "token": token, "acquired_at": now.isoformat(),
                  "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat()}},
        upsert=True)
    return token


async def lease_holder(db, pid: str, rt_id: str, date: str) -> str | None:
    doc = await db.rate_cell_leases.find_one(
        {"property_id": pid, "room_type_id": rt_id, "date": date,
         "expires_at": {"$gt": _now().isoformat()}}, {"_id": 0})
    return doc["owner"] if doc else None


async def release_lease(db, pid: str, rt_id: str, date: str, owner: str):
    await db.rate_cell_leases.delete_one(
        {"property_id": pid, "room_type_id": rt_id, "date": date, "owner": owner})


async def force_release(db, pid: str, rt_id: str = None, date: str = None) -> int:
    """Operatör egemenliği: robot kiralarını iptal eder."""
    q = {"property_id": pid}
    if rt_id is not None:
        q["room_type_id"] = rt_id
    if date:
        q["date"] = date
    r = await db.rate_cell_leases.delete_many(q)
    return r.deleted_count


def create_write_lease_router(db, require_roles):
    router = APIRouter(prefix="/write-lease", tags=["write-lease"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def list_leases(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        now = _now().isoformat()
        await db.rate_cell_leases.delete_many({"expires_at": {"$lt": now}})
        q = {} if pid == "all" else {"property_id": pid}
        leases = await db.rate_cell_leases.find(q, {"_id": 0}).sort("date", 1).to_list(200)
        owners = {}
        for l in leases:
            owners[l["owner"]] = owners.get(l["owner"], 0) + 1
        return {"leases": leases, "owners": owners, "total": len(leases)}

    @router.post("/{pid}/force-release")
    async def force_rel(pid: str, data: Dict = None, u: dict = Depends(require_roles(*ROLES))):
        data = data or {}
        n = await force_release(db, pid, data.get("room_type_id"), data.get("date"))
        return {"ok": True, "released": n,
                "by": u.get("name") or u.get("email", ""), "note": "Operatör egemenliği — robot kiraları iptal edildi"}

    @router.post("/{pid}/test-acquire")
    async def test_acquire(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        """Tatbikat: bir hücre için kira dene — çitin çalıştığını gösterir."""
        if not data.get("date"):
            raise HTTPException(422, "date zorunlu")
        token = await acquire_lease(db, pid, data.get("room_type_id", ""), data["date"],
                                    data.get("owner", "test-writer"), int(data.get("ttl", 300)))
        holder = await lease_holder(db, pid, data.get("room_type_id", ""), data["date"])
        return {"acquired": token is not None, "token": token, "current_holder": holder}

    return router
