"""
No-Show Auto-Charge Workflow
----------------------------
Industry standard: bookings still in "confirmed" status past 23:59 on their
check-in date are auto-flipped to "no_show" and a cancellation fee equal to
the first night is posted to the folio (or charged to the saved card).

Endpoints:
  GET  /api/no-show/{property_id}/candidates   — bookings eligible for no-show
  POST /api/no-show/{booking_id}/mark           — manual single mark
  POST /api/no-show/{property_id}/run           — bulk run (idempotent)
  GET  /api/no-show/{property_id}/policy        — fee policy
  POST /api/no-show/{property_id}/policy
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


def create_no_show_router(db, require_roles):
    router = APIRouter()

    DEFAULT_POLICY = {
        "fee_type": "first_night",     # first_night | percent_total | flat
        "fee_pct": 100.0,
        "flat_amount": 0.0,
        "grace_hour": 23,              # cut-off hour on check-in date
        "auto_run_enabled": True,
    }

    async def _policy(property_id: str) -> dict:
        doc = await db.no_show_policy.find_one({"property_id": property_id}, {"_id": 0}) or {}
        return {**DEFAULT_POLICY, **doc}

    def _fee_for_booking(b: dict, policy: dict) -> float:
        nights = max(1, int(b.get("nights") or 1))
        total = float(b.get("total_price") or 0)
        rate = total / nights if nights else 0
        if policy["fee_type"] == "flat":
            return round(float(policy["flat_amount"]), 2)
        if policy["fee_type"] == "percent_total":
            return round(total * float(policy["fee_pct"]) / 100, 2)
        # first_night
        return round(rate, 2)

    @router.get("/no-show/{property_id}/policy")
    async def get_policy(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await _policy(property_id)

    @router.post("/no-show/{property_id}/policy")
    async def save_policy(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        update = {
            "property_id": property_id,
            "fee_type": data.get("fee_type", DEFAULT_POLICY["fee_type"]),
            "fee_pct": float(data.get("fee_pct", DEFAULT_POLICY["fee_pct"])),
            "flat_amount": float(data.get("flat_amount", DEFAULT_POLICY["flat_amount"])),
            "grace_hour": int(data.get("grace_hour", DEFAULT_POLICY["grace_hour"])),
            "auto_run_enabled": bool(data.get("auto_run_enabled", True)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.no_show_policy.update_one({"property_id": property_id}, {"$set": update}, upsert=True)
        return {"ok": True, "policy": await _policy(property_id)}

    @router.get("/no-show/{property_id}/candidates")
    async def candidates(property_id: str, on_date: Optional[str] = None,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        target_date = on_date or date.today().isoformat()
        bookings = await db.bookings.find({
            "property_id": property_id,
            "status": {"$in": ["confirmed", "pending"]},
            "check_in": {"$lte": target_date},
            "check_out": {"$gt": target_date},
        }, {"_id": 0}).to_list(500)
        policy = await _policy(property_id)
        items = []
        for b in bookings:
            items.append({
                "id": b.get("id"),
                "booking_ref": b.get("booking_ref", ""),
                "guest_name": b.get("guest_name", ""),
                "check_in": b.get("check_in", ""),
                "check_out": b.get("check_out", ""),
                "channel": b.get("channel", ""),
                "total_price": float(b.get("total_price") or 0),
                "fee": _fee_for_booking(b, policy),
                "currency": b.get("currency", "GBP"),
            })
        return {"target_date": target_date, "policy": policy, "items": items, "count": len(items)}

    @router.post("/no-show/{booking_id}/mark")
    async def mark(booking_id: str, data: Optional[Dict] = None,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        if booking.get("status") not in ("confirmed", "pending"):
            raise HTTPException(400, f"Booking status is '{booking.get('status')}', cannot mark no-show")

        property_id = booking.get("property_id", "")
        policy = await _policy(property_id)
        fee_override = (data or {}).get("fee_override")
        fee = round(float(fee_override), 2) if fee_override is not None else _fee_for_booking(booking, policy)

        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "status": "no_show",
            "no_show_at": datetime.now(timezone.utc).isoformat(),
            "no_show_by": current_user.get("name", "Staff"),
            "no_show_fee": fee,
        }})

        if fee > 0:
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "property_id": property_id,
                "type": "charge",
                "category": "no_show_fee",
                "description": "No-show fee",
                "amount": fee,
                "currency": booking.get("currency", "GBP"),
                "posted_by": current_user.get("name", "Staff"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        return {"ok": True, "booking_id": booking_id, "fee": fee}

    @router.post("/no-show/{property_id}/run")
    async def run_bulk(property_id: str, data: Optional[Dict] = None,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        target_date = (data or {}).get("on_date") or date.today().isoformat()
        policy = await _policy(property_id)

        cands = await db.bookings.find({
            "property_id": property_id,
            "status": {"$in": ["confirmed", "pending"]},
            "check_in": {"$lt": target_date},  # check-in date already past
        }, {"_id": 0}).to_list(500)

        marked = 0
        total_fee = 0.0
        for b in cands:
            fee = _fee_for_booking(b, policy)
            await db.bookings.update_one({"id": b["id"]}, {"$set": {
                "status": "no_show",
                "no_show_at": datetime.now(timezone.utc).isoformat(),
                "no_show_by": "auto",
                "no_show_fee": fee,
            }})
            if fee > 0:
                await db.folio_items.insert_one({
                    "id": str(uuid.uuid4()),
                    "booking_id": b["id"],
                    "property_id": property_id,
                    "type": "charge",
                    "category": "no_show_fee",
                    "description": "No-show fee (auto)",
                    "amount": fee,
                    "currency": b.get("currency", "GBP"),
                    "posted_by": "auto",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            marked += 1
            total_fee += fee

        await db.no_show_runs.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "ran_by": current_user.get("name", "Staff"),
            "target_date": target_date,
            "marked": marked,
            "total_fee": round(total_fee, 2),
        })
        return {"ok": True, "marked": marked, "total_fee": round(total_fee, 2), "target_date": target_date}

    return router
