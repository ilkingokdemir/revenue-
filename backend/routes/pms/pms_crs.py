"""
PMS ↔ CRS Two-way Sync (P0 #27)
-------------------------------
Internal Central Reservation System index that mirrors PMS bookings across
properties so a chain operator can search/move/upsell across the portfolio.

This is *not* a third-party CRS connector. It is the in-house pivot that
also acts as a queue for any future CRS bridge (SiteMinder, Synxis, Cloudbeds).

Concept:
  PMS booking lives in `bookings`.
  CRS index lives in `crs_index` — one record per booking, hash-tracked so
  changes either side trigger a queue entry into `crs_sync_queue`.

Endpoints
---------
POST /pms-crs/sync/push                   Push PMS bookings into CRS index (full or delta)
POST /pms-crs/sync/pull                   Pull CRS records into PMS (delta apply)
POST /pms-crs/sync/run                    One-button bidirectional reconcile
GET  /pms-crs/index/{property_id}         Read CRS view (chain wide if `all`)
GET  /pms-crs/queue                       List sync queue entries
GET  /pms-crs/status                      Health / counters
GET  /pms-crs/conflicts                   Show records where PMS & CRS diverge
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import hashlib
import json
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_doc(doc: dict) -> str:
    fields = ["guest_name", "check_in", "check_out", "room_type", "room_number",
               "total_price", "nights", "status", "adults", "children"]
    snap = {k: doc.get(k) for k in fields}
    return hashlib.md5(json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest()


def _project(doc: dict) -> dict:
    """CRS view of a PMS booking. Drops sensitive PII like card refs."""
    return {
        "booking_id": doc.get("id"),
        "property_id": doc.get("property_id"),
        "guest_name": doc.get("guest_name", ""),
        "guest_email": doc.get("guest_email", ""),
        "channel": doc.get("source", "direct"),
        "check_in": doc.get("check_in"),
        "check_out": doc.get("check_out"),
        "nights": doc.get("nights", 0),
        "adults": doc.get("adults", 0),
        "children": doc.get("children", 0),
        "room_type": doc.get("room_type", ""),
        "room_number": doc.get("room_number", ""),
        "total_price": float(doc.get("total_price") or 0),
        "currency": doc.get("currency", "GBP"),
        "status": doc.get("status", "confirmed"),
    }


def create_pms_crs_router(db, require_roles):
    router = APIRouter()

    @router.post("/pms-crs/sync/push")
    async def push_to_crs(data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """PMS → CRS. Hash-diff each booking; only writes changed/new records."""
        property_id = data.get("property_id", "")
        delta_minutes = int(data.get("delta_minutes") or 0)
        q: Dict = {} if not property_id else {"property_id": property_id}
        if delta_minutes:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=delta_minutes)).isoformat()
            q["updated_at"] = {"$gte": cutoff}
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(20000)
        created = 0
        updated = 0
        unchanged = 0
        for b in bookings:
            view = _project(b)
            view["pms_hash"] = _hash_doc(b)
            existing = await db.crs_index.find_one({"booking_id": b["id"]}, {"_id": 0})
            if not existing:
                view.update({"first_synced": _now(), "last_synced": _now(), "rev": 1})
                await db.crs_index.insert_one(dict(view))
                await db.crs_sync_queue.insert_one({
                    "id": str(uuid.uuid4()), "direction": "pms_to_crs", "op": "create",
                    "booking_id": b["id"], "property_id": b.get("property_id", ""),
                    "queued_at": _now(), "status": "applied",
                })
                created += 1
            elif existing.get("pms_hash") != view["pms_hash"]:
                view.update({"last_synced": _now(), "rev": (existing.get("rev") or 1) + 1})
                await db.crs_index.update_one({"booking_id": b["id"]}, {"$set": view})
                await db.crs_sync_queue.insert_one({
                    "id": str(uuid.uuid4()), "direction": "pms_to_crs", "op": "update",
                    "booking_id": b["id"], "property_id": b.get("property_id", ""),
                    "queued_at": _now(), "status": "applied",
                })
                updated += 1
            else:
                unchanged += 1
        await db.crs_sync_runs.insert_one({
            "id": str(uuid.uuid4()), "direction": "push", "property_id": property_id,
            "scanned": len(bookings), "created": created, "updated": updated, "unchanged": unchanged,
            "ran_at": _now(), "ran_by": current_user.get("name", "Staff"),
        })
        return {"ok": True, "scanned": len(bookings), "created": created,
                 "updated": updated, "unchanged": unchanged}

    @router.post("/pms-crs/sync/pull")
    async def pull_from_crs(data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """CRS → PMS. Apply CRS-side staged edits (e.g. moves between properties)
        back into bookings collection."""
        property_id = data.get("property_id", "")
        q: Dict = {"crs_dirty": True}
        if property_id:
            q["property_id"] = property_id
        crs_rows = await db.crs_index.find(q, {"_id": 0}).to_list(2000)
        applied = 0
        for r in crs_rows:
            updates = {k: r[k] for k in ("guest_name", "check_in", "check_out", "room_type",
                                            "room_number", "total_price", "status", "currency",
                                            "adults", "children", "nights") if k in r}
            updates["updated_at"] = _now()
            await db.bookings.update_one({"id": r["booking_id"]}, {"$set": updates})
            await db.crs_index.update_one({"booking_id": r["booking_id"]}, {"$set": {"crs_dirty": False, "last_synced": _now()}})
            await db.crs_sync_queue.insert_one({
                "id": str(uuid.uuid4()), "direction": "crs_to_pms", "op": "update",
                "booking_id": r["booking_id"], "property_id": r.get("property_id", ""),
                "queued_at": _now(), "status": "applied",
            })
            applied += 1
        await db.crs_sync_runs.insert_one({
            "id": str(uuid.uuid4()), "direction": "pull", "property_id": property_id,
            "scanned": len(crs_rows), "applied": applied,
            "ran_at": _now(), "ran_by": current_user.get("name", "Staff"),
        })
        return {"ok": True, "scanned": len(crs_rows), "applied": applied}

    @router.post("/pms-crs/sync/run")
    async def full_run(data: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        push_res = await push_to_crs(data, current_user)  # type: ignore[arg-type]
        pull_res = await pull_from_crs(data, current_user)  # type: ignore[arg-type]
        return {"ok": True, "push": push_res, "pull": pull_res}

    @router.get("/pms-crs/index/{property_id}")
    async def index(property_id: str, status: str = "", limit: int = 200,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: Dict = {} if property_id == "all" else {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.crs_index.find(q, {"_id": 0}).sort("check_in", 1).to_list(limit)
        return {"items": rows, "count": len(rows)}

    @router.get("/pms-crs/queue")
    async def queue(property_id: str = "", limit: int = 100,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {}
        if property_id:
            q["property_id"] = property_id
        rows = await db.crs_sync_queue.find(q, {"_id": 0}).sort("queued_at", -1).to_list(limit)
        return {"items": rows, "count": len(rows)}

    @router.get("/pms-crs/status")
    async def status(property_id: str = "",
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {} if not property_id else {"property_id": property_id}
        last_run = await db.crs_sync_runs.find_one(q, {"_id": 0}, sort=[("ran_at", -1)])
        idx_count = await db.crs_index.count_documents(q)
        pms_count = await db.bookings.count_documents(q)
        dirty = await db.crs_index.count_documents({**q, "crs_dirty": True})
        return {
            "pms_bookings": pms_count, "crs_records": idx_count,
            "drift": pms_count - idx_count, "crs_dirty_pending_pull": dirty,
            "last_run": last_run, "checked_at": _now(),
        }

    @router.get("/pms-crs/conflicts")
    async def conflicts(property_id: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bookings whose hash differs from the CRS view but neither side is marked dirty —
        i.e. there's an unflagged divergence (network blip, partial sync)."""
        q: Dict = {} if not property_id else {"property_id": property_id}
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(20000)
        # CRS index'i tek sorguda çek (N+1 yerine — iter 378)
        crs_map = {c["booking_id"]: c async for c in db.crs_index.find(
            {}, {"_id": 0}) if c.get("booking_id")}
        conflicts: List[dict] = []
        for b in bookings:
            crs = crs_map.get(b["id"])
            if not crs:
                conflicts.append({"booking_id": b["id"], "kind": "missing_in_crs"})
                continue
            if crs.get("pms_hash") != _hash_doc(b):
                conflicts.append({
                    "booking_id": b["id"], "kind": "hash_drift",
                    "pms_status": b.get("status"), "crs_status": crs.get("status"),
                    "pms_total": b.get("total_price"), "crs_total": crs.get("total_price"),
                })
        return {"items": conflicts[:200], "count": len(conflicts)}

    return router
