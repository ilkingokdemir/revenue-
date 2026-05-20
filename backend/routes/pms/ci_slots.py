"""
Dynamic Check-in Time Slots (P1)
--------------------------------
Lets a guest pick a check-in time slot rather than landing whenever. Slots
are generated for a date based on:
  * configurable opening hour, closing hour, and slot duration
  * housekeeping capacity (number of rooms ready per slot)
  * an explicit reservation count (one guest per slot * capacity)

Endpoints
---------
POST /ci-slots/config                       Save policy
GET  /ci-slots/{property_id}/config
GET  /ci-slots/{property_id}/{date}/availability
POST /ci-slots/reserve                      Public — guest picks a slot
DELETE /ci-slots/reservations/{id}          Free a slot
GET  /ci-slots/{property_id}/{date}/reservations
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict, List, Optional
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slots_for(start_h: int, end_h: int, slot_min: int):
    out: List[str] = []
    cur = start_h * 60
    end = end_h * 60
    while cur < end:
        h, m = divmod(cur, 60)
        out.append(f"{h:02d}:{m:02d}")
        cur += slot_min
    return out


def create_ci_slots_router(db, require_roles):
    router = APIRouter()

    @router.post("/ci-slots/config")
    async def upsert(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        if not property_id:
            raise HTTPException(400, "property_id required")
        record = {
            "property_id": property_id,
            "start_hour": int(data.get("start_hour") or 14),     # 14:00 default
            "end_hour": int(data.get("end_hour") or 22),
            "slot_minutes": int(data.get("slot_minutes") or 30),
            "capacity_per_slot": int(data.get("capacity_per_slot") or 4),
            "early_ci_fee": float(data.get("early_ci_fee") or 25.0),
            "early_ci_threshold_hour": int(data.get("early_ci_threshold_hour") or 14),
            "enabled": bool(data.get("enabled", True)),
            "updated_at": _now(),
        }
        await db.ci_slots_config.update_one({"property_id": property_id}, {"$set": record}, upsert=True)
        return {"ok": True, "config": record}

    @router.get("/ci-slots/{property_id}/config")
    async def get_cfg(property_id: str):
        return await db.ci_slots_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "property_id": property_id, "start_hour": 14, "end_hour": 22,
            "slot_minutes": 30, "capacity_per_slot": 4,
            "early_ci_fee": 25.0, "early_ci_threshold_hour": 14, "enabled": True,
        }

    @router.get("/ci-slots/{property_id}/{the_date}/availability")
    async def availability(property_id: str, the_date: str):
        cfg = await db.ci_slots_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "start_hour": 14, "end_hour": 22, "slot_minutes": 30, "capacity_per_slot": 4,
            "early_ci_fee": 25.0, "early_ci_threshold_hour": 14,
        }
        slots = _slots_for(cfg["start_hour"], cfg["end_hour"], cfg["slot_minutes"])
        # Optionally include early slots (08:00-14:00)
        early_slots = _slots_for(8, cfg["start_hour"], cfg["slot_minutes"])
        reservations = await db.ci_slot_reservations.find({"property_id": property_id, "date": the_date}, {"_id": 0}).to_list(2000)
        taken: Dict[str, int] = {}
        for r in reservations:
            taken[r["slot"]] = taken.get(r["slot"], 0) + 1
        cap = int(cfg["capacity_per_slot"])
        out = []
        for s in slots:
            out.append({"slot": s, "free_seats": max(cap - taken.get(s, 0), 0),
                         "is_early": False, "fee": 0})
        for s in early_slots:
            out.append({"slot": s, "free_seats": max(cap - taken.get(s, 0), 0),
                         "is_early": True, "fee": float(cfg["early_ci_fee"])})
        out.sort(key=lambda x: x["slot"])
        return {"date": the_date, "slots": out, "capacity_per_slot": cap}

    @router.post("/ci-slots/reserve")
    async def reserve(data: Dict):
        property_id = (data.get("property_id") or "").strip()
        booking_id = (data.get("booking_id") or "").strip()
        the_date = (data.get("date") or "")[:10]
        slot = (data.get("slot") or "").strip()
        if not (property_id and booking_id and the_date and slot):
            raise HTTPException(400, "property_id, booking_id, date, slot required")
        cfg = await db.ci_slots_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "capacity_per_slot": 4, "early_ci_fee": 25.0, "early_ci_threshold_hour": 14,
        }
        existing = await db.ci_slot_reservations.find_one({"booking_id": booking_id, "date": the_date}, {"_id": 0})
        if existing:
            await db.ci_slot_reservations.update_one(
                {"id": existing["id"]}, {"$set": {"slot": slot, "updated_at": _now()}}
            )
            return {"ok": True, "id": existing["id"], "updated": True}
        # Capacity check
        cnt = await db.ci_slot_reservations.count_documents({"property_id": property_id, "date": the_date, "slot": slot})
        if cnt >= int(cfg.get("capacity_per_slot") or 4):
            raise HTTPException(409, "Slot full")
        # Early CI fee
        try:
            slot_hour = int(slot.split(":")[0])
        except (ValueError, IndexError):
            raise HTTPException(400, "Invalid slot format (HH:MM)")
        is_early = slot_hour < int(cfg.get("early_ci_threshold_hour") or 14)
        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "booking_id": booking_id,
            "date": the_date,
            "slot": slot,
            "is_early": is_early,
            "fee_due": float(cfg["early_ci_fee"]) if is_early else 0.0,
            "guest_name": data.get("guest_name", ""),
            "created_at": _now(),
        }
        await db.ci_slot_reservations.insert_one(dict(record))
        if record["fee_due"] > 0:
            await db.folio_charges.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "category": "early_checkin",
                "description": f"Early check-in slot {slot}",
                "amount": record["fee_due"],
                "currency": "GBP",
                "posted_at": _now(),
                "posted_by": "ci-slot-engine",
            })
        return {"ok": True, "reservation": record}

    @router.delete("/ci-slots/reservations/{rid}")
    async def cancel(rid: str):
        result = await db.ci_slot_reservations.delete_one({"id": rid})
        return {"ok": True, "deleted": result.deleted_count}

    @router.get("/ci-slots/{property_id}/{the_date}/reservations")
    async def list_res(property_id: str, the_date: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.ci_slot_reservations.find(
            {"property_id": property_id, "date": the_date}, {"_id": 0}
        ).sort("slot", 1).to_list(500)
        return {"items": rows, "count": len(rows)}

    return router
