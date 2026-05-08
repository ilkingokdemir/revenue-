"""
Spaces — Multi-Product Inventory
--------------------------------
Single bookable-resource engine for non-room sellable items: parking spots,
EV charge slots, meeting rooms, bicycles, lockers, kayaks, bicycles, cabanas.
Inspired by Mews "Spaces" but lighter — full hourly or daily resolution.

Endpoints:
  GET  /api/spaces/{property_id}                          — list
  POST /api/spaces/{property_id}                           — upsert
  DELETE /api/spaces/{property_id}/{space_id}
  GET  /api/spaces/{property_id}/{space_id}/availability?from&to
  POST /api/space-bookings                                 — book
  GET  /api/space-bookings/{property_id}                   — list bookings
  POST /api/space-bookings/{id}/cancel
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


SPACE_KINDS = ["parking", "ev_charger", "meeting_room", "bicycle", "locker", "cabana", "kayak", "other"]


def create_spaces_router(db, require_roles):
    router = APIRouter()

    @router.get("/spaces/{property_id}")
    async def list_spaces(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        rows = await db.spaces.find(
            {"property_id": property_id, "active": {"$ne": False}}, {"_id": 0}
        ).sort("kind", 1).to_list(200)
        return rows

    @router.post("/spaces/{property_id}")
    async def upsert(property_id: str, data: Dict,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        sid = data.get("id") or str(uuid.uuid4())
        kind = data.get("kind", "other")
        if kind not in SPACE_KINDS:
            kind = "other"
        unit = data.get("unit_minutes")  # null = daily, int = hourly grain
        if unit is not None:
            try:
                unit = max(15, int(unit))
            except Exception:
                unit = None
        update = {
            "id": sid,
            "property_id": property_id,
            "kind": kind,
            "name": data.get("name", "Untitled space"),
            "code": data.get("code", ""),
            "capacity": int(data.get("capacity") or 1),
            "rate_per_unit": float(data.get("rate_per_unit") or 0),
            "currency": data.get("currency", "GBP"),
            "unit_minutes": unit,        # None = day-rate
            "open_hour":  int(data.get("open_hour", 0)),
            "close_hour": int(data.get("close_hour", 24)),
            "active": bool(data.get("active", True)),
            "description": data.get("description", ""),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.spaces.update_one(
            {"id": sid}, {"$set": update, "$setOnInsert": {"created_at": update["updated_at"]}}, upsert=True
        )
        doc = await db.spaces.find_one({"id": sid}, {"_id": 0})
        return {"ok": True, "space": doc}

    @router.delete("/spaces/{property_id}/{space_id}")
    async def deactivate(property_id: str, space_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.spaces.update_one({"id": space_id, "property_id": property_id}, {"$set": {"active": False}})
        return {"ok": True}

    @router.get("/spaces/{property_id}/{space_id}/availability")
    async def availability(property_id: str, space_id: str,
                            from_dt: Optional[str] = None, to_dt: Optional[str] = None,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        space = await db.spaces.find_one({"id": space_id}, {"_id": 0})
        if not space:
            raise HTTPException(404, "Space not found")
        f = from_dt or datetime.now(timezone.utc).isoformat()
        t = to_dt or (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        bookings = await db.space_bookings.find({
            "space_id": space_id,
            "status": {"$ne": "cancelled"},
            "$or": [
                {"start": {"$lt": t}, "end": {"$gt": f}},
            ],
        }, {"_id": 0}).sort("start", 1).to_list(500)
        return {"space": space, "from": f, "to": t, "bookings": bookings, "capacity": space.get("capacity", 1)}

    @router.post("/space-bookings")
    async def book(data: Dict,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        space_id = data.get("space_id", "")
        start    = (data.get("start") or "").strip()
        end      = (data.get("end") or "").strip()
        guest    = (data.get("guest_name") or "").strip()
        if not space_id or not start or not end or not guest:
            raise HTTPException(400, "space_id, start, end, guest_name required")

        space = await db.spaces.find_one({"id": space_id}, {"_id": 0})
        if not space:
            raise HTTPException(404, "Space not found")

        # Concurrency check (overlap + capacity)
        overlap = await db.space_bookings.count_documents({
            "space_id": space_id, "status": {"$ne": "cancelled"},
            "start": {"$lt": end}, "end": {"$gt": start},
        })
        if overlap >= space.get("capacity", 1):
            raise HTTPException(409, "Space at capacity for this window")

        # Pricing
        try:
            sd = datetime.fromisoformat(start); ed = datetime.fromisoformat(end)
        except Exception:
            raise HTTPException(400, "invalid start/end ISO datetimes")
        unit_min = space.get("unit_minutes")
        if unit_min:  # hourly grain
            units = max(1, round((ed - sd).total_seconds() / 60 / unit_min))
        else:  # daily
            days = max(1, (ed.date() - sd.date()).days)
            units = days
        price = round(units * float(space.get("rate_per_unit") or 0), 2)
        if "price_override" in data and data["price_override"] is not None:
            price = round(float(data["price_override"]), 2)

        record = {
            "id": str(uuid.uuid4()),
            "property_id": space["property_id"],
            "space_id": space_id,
            "space_name": space["name"],
            "kind": space["kind"],
            "guest_name": guest,
            "guest_email": data.get("guest_email", ""),
            "booking_id": data.get("booking_id", ""),
            "room_number": data.get("room_number", ""),
            "start": start, "end": end, "units": units,
            "price": price, "currency": space.get("currency", "GBP"),
            "charge_to": data.get("charge_to", "room"),
            "notes": data.get("notes", ""),
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", "Staff"),
        }
        await db.space_bookings.insert_one(dict(record))
        record.pop("_id", None)

        if record["charge_to"] == "room" and record["booking_id"] and price > 0:
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": record["booking_id"],
                "property_id": record["property_id"],
                "type": "charge",
                "category": space["kind"],
                "description": f"{space['name']} · {start[:16]} → {end[:16]}",
                "amount": price,
                "currency": record["currency"],
                "posted_by": current_user.get("name", "Staff"),
                "created_at": record["created_at"],
            })
        return {"ok": True, "booking": record}

    @router.get("/space-bookings/{property_id}")
    async def list_bookings(property_id: str, days: int = 14, kind: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        from_dt = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        to_dt   = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "start": {"$gte": from_dt, "$lte": to_dt}}
        if kind:
            q["kind"] = kind
        rows = await db.space_bookings.find(q, {"_id": 0}).sort("start", 1).to_list(500)
        return rows

    @router.post("/space-bookings/{booking_id}/cancel")
    async def cancel(booking_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        await db.space_bookings.update_one({"id": booking_id}, {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancelled_by": current_user.get("name", "Staff"),
        }})
        return {"ok": True}

    return router
