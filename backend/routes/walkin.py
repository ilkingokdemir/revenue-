"""
Walk-in Express Check-in
------------------------
A 60-90 second walk-in flow:
  • Search availability for tonight (or N nights) by room type
  • Get a quick rate quote (with all applicable taxes / fees from tax_config)
  • Create the booking + auto-check-in + room assignment + folio init
  • Optional: collect deposit through existing terminal

This is a single thin orchestrator — it composes the existing booking,
tax_config and folio infrastructure rather than reinventing.

Endpoints:
  POST /api/walkin/availability       (body: property_id, check_in, nights, guests)
  POST /api/walkin/create             (body: property_id, room_type_id, room_number, nights,
                                              guest{name,email,phone,id_doc}, payment_method, source)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List
import uuid
import logging

logger = logging.getLogger(__name__)


def create_walkin_router(db, require_roles):
    router = APIRouter()

    @router.post("/walkin/availability")
    async def availability(data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        property_id = data.get("property_id", "").strip()
        nights = max(1, int(data.get("nights") or 1))
        guests = max(1, int(data.get("guests") or 1))
        check_in_str = (data.get("check_in") or date.today().isoformat()).strip()
        try:
            check_in_dt = datetime.fromisoformat(check_in_str).date()
        except Exception:
            raise HTTPException(400, "invalid check_in (YYYY-MM-DD)")
        if not property_id:
            raise HTTPException(400, "property_id required")

        check_out_dt = check_in_dt + timedelta(days=nights)
        check_out_str = check_out_dt.isoformat()

        # Pull room types
        room_types = await db.room_types.find(
            {"property_id": property_id, "is_active": {"$ne": False}}, {"_id": 0}
        ).to_list(50)

        # Active tax profile (for breakdown)
        tax_profile = await db.tax_profiles.find_one(
            {"property_id": property_id, "active": True}, {"_id": 0}
        )

        # Available rooms (status_clean / inspected) per type
        clean_rooms = await db.room_statuses.find(
            {"property_id": property_id, "status": {"$in": ["clean", "inspected"]}},
            {"_id": 0, "id": 1, "room_number": 1, "room_type_id": 1, "floor": 1}
        ).to_list(500)

        # Filter out rooms already booked for this date range
        overlapping = await db.bookings.find({
            "property_id": property_id,
            "status": {"$in": ["confirmed", "checked_in", "arriving"]},
            "check_in": {"$lt": check_out_str},
            "check_out": {"$gt": check_in_str},
        }, {"_id": 0, "room_number": 1, "assigned_room": 1}).to_list(500)
        booked_set = {(b.get("room_number") or b.get("assigned_room") or "") for b in overlapping}

        offerings: List[Dict] = []
        for rt in room_types:
            rt_clean_rooms = [
                r for r in clean_rooms
                if r.get("room_type_id") == rt.get("id")
                and str(r.get("room_number")) not in booked_set
            ]
            if not rt_clean_rooms:
                continue
            base_rate = float(rt.get("base_price") or rt.get("price_per_night") or 0)
            base_total = round(base_rate * nights, 2)

            taxes_added, taxes_included, applied = 0.0, 0.0, []
            if tax_profile and base_rate > 0:
                from routes.finance_ext.tax_config import _calculate_taxes
                breakdown = _calculate_taxes(tax_profile, base_total, nights, guests, "", "room")
                taxes_added = breakdown["taxes_added"]
                taxes_included = breakdown["taxes_included"]
                applied = breakdown["applied"]

            offerings.append({
                "room_type_id": rt.get("id"),
                "room_type_name": rt.get("name") or rt.get("type"),
                "base_rate": base_rate,
                "base_total": base_total,
                "taxes_added": taxes_added,
                "taxes_included": taxes_included,
                "grand_total": round(base_total + taxes_added, 2),
                "tax_breakdown": applied,
                "available_rooms": [
                    {"room_id": r.get("id"), "room_number": str(r.get("room_number")), "floor": r.get("floor", "")}
                    for r in rt_clean_rooms
                ],
                "available_count": len(rt_clean_rooms),
            })

        offerings.sort(key=lambda o: o["base_rate"])
        return {
            "property_id": property_id,
            "check_in": check_in_str,
            "check_out": check_out_str,
            "nights": nights,
            "guests": guests,
            "offerings": offerings,
            "tax_profile": {"id": tax_profile["id"], "name": tax_profile["name"]} if tax_profile else None,
        }

    @router.post("/walkin/create")
    async def create_walkin(data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        required = ("property_id", "room_type_id", "room_number", "nights", "guest")
        for k in required:
            if not data.get(k):
                raise HTTPException(400, f"{k} required")
        guest = data.get("guest") or {}
        if not guest.get("name"):
            raise HTTPException(400, "guest.name required")

        property_id = data["property_id"]
        room_number = str(data["room_number"])
        nights = max(1, int(data.get("nights") or 1))
        guests_count = max(1, int(data.get("guests") or 1))
        check_in_str = (data.get("check_in") or date.today().isoformat())
        check_in_dt  = datetime.fromisoformat(check_in_str).date()
        check_out_dt = check_in_dt + timedelta(days=nights)
        check_out_str = check_out_dt.isoformat()

        # Pull room type for rate
        rt = await db.room_types.find_one({"id": data["room_type_id"]}, {"_id": 0})
        if not rt:
            raise HTTPException(404, "Room type not found")
        base_rate = float(data.get("rate") or rt.get("base_price") or rt.get("price_per_night") or 0)
        base_total = round(base_rate * nights, 2)

        # Tax breakdown
        tax_profile = await db.tax_profiles.find_one(
            {"property_id": property_id, "active": True}, {"_id": 0}
        )
        taxes_added = 0.0
        applied: List[Dict] = []
        if tax_profile:
            from routes.finance_ext.tax_config import _calculate_taxes
            breakdown = _calculate_taxes(tax_profile, base_total, nights, guests_count, "", "room")
            taxes_added = breakdown["taxes_added"]
            applied = breakdown["applied"]

        grand_total = round(base_total + taxes_added, 2)
        booking_id = str(uuid.uuid4())
        booking_ref = f"WK-{datetime.now(timezone.utc).strftime('%y%m%d')}-{booking_id[:6].upper()}"

        booking_doc = {
            "id": booking_id,
            "property_id": property_id,
            "booking_ref": booking_ref,
            "channel": "walk_in",
            "source": "walk_in",
            "guest_name": guest.get("name", ""),
            "guest_email": guest.get("email", ""),
            "guest_phone": guest.get("phone", ""),
            "id_document": guest.get("id_doc", ""),
            "id_type": guest.get("id_type", ""),
            "room_type_id": data["room_type_id"],
            "room_type_name": rt.get("name") or rt.get("type"),
            "room_number": room_number,
            "assigned_room": room_number,
            "check_in": check_in_str,
            "check_out": check_out_str,
            "nights": nights,
            "guests": guests_count,
            "rate_per_night": base_rate,
            "subtotal": base_total,
            "taxes": taxes_added,
            "tax_breakdown": applied,
            "total_price": grand_total,
            "currency": rt.get("currency", "GBP"),
            "status": "checked_in",
            "checked_in_at": datetime.now(timezone.utc).isoformat(),
            "checked_in_by": current_user.get("name", "Staff"),
            "payment_method": data.get("payment_method", "cash"),
            "deposit_paid": float(data.get("deposit_paid") or 0),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", "Staff"),
        }
        await db.bookings.insert_one(dict(booking_doc))
        booking_doc.pop("_id", None)

        # Folio open + room charges
        await db.folio_items.insert_one({
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "property_id": property_id,
            "type": "charge",
            "category": "room",
            "description": f"Room {room_number} × {nights} night(s)",
            "amount": base_total,
            "currency": booking_doc["currency"],
            "posted_by": current_user.get("name", "Staff"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        for tax in applied:
            if tax.get("included_in_rate"):
                continue
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "property_id": property_id,
                "type": "charge",
                "category": tax.get("kind", "tax"),
                "description": tax.get("label", "Tax"),
                "amount": tax.get("amount", 0),
                "currency": booking_doc["currency"],
                "posted_by": current_user.get("name", "Staff"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        # Deposit payment posted as credit
        deposit = float(data.get("deposit_paid") or 0)
        if deposit > 0:
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "property_id": property_id,
                "type": "payment",
                "category": data.get("payment_method", "cash"),
                "description": "Walk-in deposit",
                "amount": deposit,
                "currency": booking_doc["currency"],
                "posted_by": current_user.get("name", "Staff"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        # Update room status to in_house
        await db.room_statuses.update_one(
            {"property_id": property_id, "room_number": room_number},
            {"$set": {"status": "in_house", "current_guest": guest.get("name", ""),
                       "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

        # Sync any existing guest profile (preferences carry over)
        if guest.get("email"):
            await db.guest_profiles.update_one(
                {"email": guest["email"]},
                {"$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "name": guest.get("name", ""),
                    "email": guest["email"],
                    "phone": guest.get("phone", ""),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }, "$inc": {"total_stays": 1}, "$addToSet": {"properties": property_id}},
                upsert=True,
            )

        return {
            "ok": True,
            "booking": booking_doc,
            "balance_due": round(grand_total - deposit, 2),
        }

    return router
