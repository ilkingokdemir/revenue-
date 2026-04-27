"""
Stay Extension Wizard (P1)
--------------------------
Lets reception extend an active booking by N nights:
  1. Quote — checks if the same room is available for those nights, computes
     the additional rate (using base_rate × N, with a configurable
     extension_discount_pct for early extension), and returns availability.
  2. Apply — writes the new check_out, posts a folio_charges row for the
     extra nights, increments nights, and stamps an audit row.

Endpoints
---------
POST /stay-ext/quote                         Quote an extension (no DB write)
POST /stay-ext/apply                         Apply the extension (writes booking + folio)
GET  /stay-ext/{property_id}/recent          Audit log (last 60d)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _check_room_free(db, property_id: str, room_number: str, from_date: str, to_date: str, except_booking_id: str) -> bool:
    if not room_number:
        return True
    q = {
        "property_id": property_id, "room_number": room_number,
        "id": {"$ne": except_booking_id},
        "status": {"$nin": ["cancelled", "no_show"]},
        "check_in": {"$lt": to_date},
        "check_out": {"$gt": from_date},
    }
    blocker = await db.bookings.find_one(q, {"_id": 0})
    return blocker is None


def create_stay_ext_router(db, require_roles):
    router = APIRouter()

    @router.post("/stay-ext/quote")
    async def quote(data: Dict,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking_id = (data.get("booking_id") or "").strip()
        extra_nights = int(data.get("extra_nights") or 1)
        if not booking_id or extra_nights < 1:
            raise HTTPException(400, "booking_id + extra_nights ≥ 1 required")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        old_co = (booking.get("check_out") or "")[:10]
        try:
            new_co = (date.fromisoformat(old_co) + timedelta(days=extra_nights)).isoformat()
        except ValueError:
            raise HTTPException(400, "Booking has malformed check_out date")

        avail = await _check_room_free(
            db, booking.get("property_id", ""), booking.get("room_number", ""),
            old_co, new_co, booking_id,
        )
        # Pricing: base_rate × extra_nights × (1 - discount_pct/100)
        rt = await db.room_types.find_one({"property_id": booking.get("property_id", ""), "name": booking.get("room_type", "")}, {"_id": 0}) or {}
        per_night = float(rt.get("base_rate") or 0) or float(booking.get("total_price") or 0) / max(int(booking.get("nights") or 1), 1)
        discount_pct = float(data.get("discount_pct") or 0)
        per_night_charged = round(per_night * (1 - discount_pct / 100), 2)
        total = round(per_night_charged * extra_nights, 2)

        return {
            "ok": True,
            "booking_id": booking_id,
            "current_check_out": old_co,
            "proposed_check_out": new_co,
            "extra_nights": extra_nights,
            "room_available": avail,
            "rate_per_night": per_night,
            "rate_per_night_charged": per_night_charged,
            "discount_pct": discount_pct,
            "total_extra_charge": total,
            "currency": booking.get("currency", "GBP"),
        }

    @router.post("/stay-ext/apply")
    async def apply(data: Dict,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q = await quote(data, current_user)  # type: ignore[arg-type]
        if not q["room_available"]:
            raise HTTPException(409, "Room is not available for the requested extra nights")
        booking_id = q["booking_id"]
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        new_nights = int(booking.get("nights") or 0) + q["extra_nights"]
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {
                "check_out": q["proposed_check_out"],
                "nights": new_nights,
                "total_price": round(float(booking.get("total_price") or 0) + q["total_extra_charge"], 2),
                "updated_at": _now(),
            }},
        )
        await db.folio_charges.insert_one({
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "category": "room",
            "description": f"Stay extension · +{q['extra_nights']} night(s)" + (f" ({q['discount_pct']}% off)" if q["discount_pct"] else ""),
            "amount": q["total_extra_charge"],
            "currency": q["currency"],
            "posted_at": _now(),
            "posted_by": current_user.get("name", "Staff"),
        })
        await db.stay_extensions_log.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": booking.get("property_id", ""),
            "booking_id": booking_id,
            "extra_nights": q["extra_nights"],
            "old_check_out": q["current_check_out"],
            "new_check_out": q["proposed_check_out"],
            "charge": q["total_extra_charge"],
            "discount_pct": q["discount_pct"],
            "applied_at": _now(),
            "applied_by": current_user.get("name", "Staff"),
        })
        return {"ok": True, **q}

    @router.get("/stay-ext/{property_id}/recent")
    async def recent(property_id: str, days: int = 60,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.stay_extensions_log.find(
            {"property_id": property_id, "applied_at": {"$gte": since}}, {"_id": 0}
        ).sort("applied_at", -1).to_list(500)
        total_nights = sum(r.get("extra_nights", 0) for r in rows)
        total_revenue = round(sum(float(r.get("charge") or 0) for r in rows), 2)
        return {"items": rows, "count": len(rows),
                 "extra_nights_total": total_nights, "extra_revenue": total_revenue}

    return router
