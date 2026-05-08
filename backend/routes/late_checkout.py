"""
Late Check-out Quote Engine
---------------------------
Most PMSes either ship blanket late check-out fees or rely on staff judgement.
We auto-quote based on:
  • Requested checkout hour (relative to standard 11:00)
  • Next arrival's check-in time on the same room → blocks if turnaround < 90 min
  • Property occupancy tonight (lower occupancy = softer pricing)
  • Tier: loyalty/VIP guests get a discount
  • Configurable bands per property

Once quoted and accepted, posts a folio charge automatically.

Endpoints:
  GET  /api/late-checkout/{property_id}/policy
  POST /api/late-checkout/{property_id}/policy
  POST /api/late-checkout/quote                      (body: booking_id, requested_hour)
  POST /api/late-checkout/{booking_id}/accept        (body: requested_hour, fee, new_checkout)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


def create_late_checkout_router(db, require_roles):
    router = APIRouter()

    DEFAULT_POLICY = {
        "free_until_hour":  11,    # complimentary up to this hour
        "half_until_hour":  14,    # half-night fee 11–14
        "full_after_hour":  16,    # full nightly rate 16+
        "vip_free_until":   13,    # loyalty/VIP grace
        "min_turnaround_min": 90,  # housekeeping buffer
        "currency": "GBP",
    }

    async def _policy(property_id: str) -> dict:
        doc = await db.late_checkout_policy.find_one({"property_id": property_id}, {"_id": 0}) or {}
        return {**DEFAULT_POLICY, **doc}

    @router.get("/late-checkout/{property_id}/policy")
    async def get_policy(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await _policy(property_id)

    @router.post("/late-checkout/{property_id}/policy")
    async def save_policy(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        update = {
            "property_id": property_id,
            "free_until_hour":  int(data.get("free_until_hour",  DEFAULT_POLICY["free_until_hour"])),
            "half_until_hour":  int(data.get("half_until_hour",  DEFAULT_POLICY["half_until_hour"])),
            "full_after_hour":  int(data.get("full_after_hour",  DEFAULT_POLICY["full_after_hour"])),
            "vip_free_until":   int(data.get("vip_free_until",   DEFAULT_POLICY["vip_free_until"])),
            "min_turnaround_min": int(data.get("min_turnaround_min", DEFAULT_POLICY["min_turnaround_min"])),
            "currency": data.get("currency", DEFAULT_POLICY["currency"]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.late_checkout_policy.update_one({"property_id": property_id}, {"$set": update}, upsert=True)
        return {"ok": True, "policy": await _policy(property_id)}

    @router.post("/late-checkout/quote")
    async def quote(data: Dict,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking_id = data.get("booking_id", "")
        requested_hour = int(data.get("requested_hour") or 0)
        if not booking_id or requested_hour < 8 or requested_hour > 23:
            raise HTTPException(400, "booking_id and requested_hour (8-23) required")

        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        property_id = booking.get("property_id", "")
        policy = await _policy(property_id)

        # Nightly rate from booking
        nights = max(1, int(booking.get("nights") or 1))
        nightly = float(booking.get("total_price") or 0) / nights
        if nightly <= 0:
            nightly = 100.0  # safety floor

        # Next arrival check (same room)
        room_number = booking.get("room_number") or booking.get("assigned_room")
        checkout_date = booking.get("check_out") or booking.get("check_out_date") or ""
        block_reason = ""
        if room_number and checkout_date:
            next_arr = await db.bookings.find_one({
                "property_id": property_id,
                "$or": [{"room_number": room_number}, {"assigned_room": room_number}],
                "check_in": checkout_date,
                "id": {"$ne": booking_id},
                "status": {"$in": ["confirmed", "checked_in", "arriving"]},
            }, {"_id": 0})
            if next_arr:
                # turnaround = next checkin (default 15:00) - requested_hour
                turnaround_min = (15 - requested_hour) * 60
                if turnaround_min < policy["min_turnaround_min"]:
                    block_reason = f"Next arrival on this room — minimum {policy['min_turnaround_min']} min turnaround needed."

        # Loyalty / VIP detection
        is_vip = bool(booking.get("vip") or booking.get("loyalty_tier") in ["gold", "platinum"])
        free_cap = policy["vip_free_until"] if is_vip else policy["free_until_hour"]

        # Pricing band
        if requested_hour <= free_cap:
            fee, band = 0.0, "free"
        elif requested_hour <= policy["half_until_hour"]:
            fee, band = round(nightly * 0.50, 2), "half_night"
        elif requested_hour < policy["full_after_hour"]:
            fee, band = round(nightly * 0.75, 2), "three_quarter_night"
        else:
            fee, band = round(nightly, 2), "full_night"

        # Property-wide occupancy tonight → discount on quiet nights
        today_str = date.today().isoformat()
        occupied = await db.bookings.count_documents({
            "property_id": property_id,
            "check_in": {"$lte": today_str},
            "check_out": {"$gt": today_str},
            "status": {"$in": ["confirmed", "checked_in"]},
        })
        room_count = await db.room_statuses.count_documents({"property_id": property_id})
        occ_pct = (occupied / room_count * 100) if room_count else 50
        if occ_pct < 50 and band != "free":
            fee = round(fee * 0.7, 2)
            band += "_quiet_night"

        return {
            "booking_id": booking_id,
            "guest_name": booking.get("guest_name", ""),
            "room_number": room_number,
            "current_checkout": checkout_date,
            "requested_hour": requested_hour,
            "new_checkout_time": f"{requested_hour:02d}:00",
            "nightly_rate": round(nightly, 2),
            "fee": fee,
            "band": band,
            "currency": policy["currency"],
            "is_vip": is_vip,
            "occupancy_pct": round(occ_pct, 1),
            "available": not block_reason,
            "block_reason": block_reason,
            "policy": policy,
        }

    @router.post("/late-checkout/{booking_id}/accept")
    async def accept(booking_id: str, data: Dict,
                      current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        requested_hour = int(data.get("requested_hour") or 0)
        fee = float(data.get("fee") or 0)
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        new_checkout_time = f"{requested_hour:02d}:00"
        record = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "property_id": booking.get("property_id", ""),
            "room_number": booking.get("room_number") or booking.get("assigned_room"),
            "guest_name": booking.get("guest_name", ""),
            "fee": fee,
            "requested_hour": requested_hour,
            "new_checkout_time": new_checkout_time,
            "approved_by": current_user.get("name", "Staff"),
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.late_checkouts.insert_one(dict(record))
        record.pop("_id", None)

        # Update booking with late checkout flag
        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "late_checkout_hour": requested_hour,
            "late_checkout_fee": fee,
            "late_checkout_time": new_checkout_time,
        }})

        # Post folio charge
        if fee > 0:
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "property_id": booking.get("property_id", ""),
                "type": "charge",
                "category": "late_checkout",
                "description": f"Late checkout — until {new_checkout_time}",
                "amount": fee,
                "currency": booking.get("currency", "GBP"),
                "posted_by": current_user.get("name", "Staff"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        return {"ok": True, "record": record}

    @router.get("/late-checkout/{property_id}/list")
    async def list_recent(property_id: str, days: int = 30,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        docs = await db.late_checkouts.find(
            {"property_id": property_id, "approved_at": {"$gte": since}},
            {"_id": 0},
        ).sort("approved_at", -1).to_list(200)
        total_revenue = sum(float(d.get("fee") or 0) for d in docs)
        return {"items": docs, "total_revenue": round(total_revenue, 2), "count": len(docs)}

    return router
