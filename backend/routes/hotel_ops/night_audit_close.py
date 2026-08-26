"""
Night Audit · Close-Day Lock (P0)
Locks the folio/payment activity for a given business date. Once closed, folio_items
for that day cannot be edited. Produces a signed close-day record that serves as the
end-of-day regulatory document in many jurisdictions.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_night_audit_close_router(db, require_roles):
    router = APIRouter()

    async def _is_closed(property_id: str, business_date: str) -> bool:
        row = await db.night_audit_closes.find_one({"property_id": property_id, "business_date": business_date}, {"_id": 0})
        return bool(row and row.get("status") == "closed")

    @router.get("/night-audit/close-status/{property_id}")
    async def close_status(property_id: str, business_date: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Is a given business date already closed?"""
        if not business_date:
            business_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = await db.night_audit_closes.find_one({"property_id": property_id, "business_date": business_date}, {"_id": 0})
        return {
            "property_id": property_id,
            "business_date": business_date,
            "closed": bool(row and row.get("status") == "closed"),
            "close_record": row,
        }

    @router.get("/night-audit/close-history/{property_id}")
    async def close_history(property_id: str, limit: int = 30,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Last N close-day records for this property."""
        rows = await db.night_audit_closes.find({"property_id": property_id}, {"_id": 0})\
            .sort("business_date", -1).to_list(int(limit))
        return rows

    @router.post("/night-audit/close-day/{property_id}")
    async def close_day(property_id: str, data: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Lock a business date. Captures totals snapshot at the moment of closure
        so the number is immutable even if underlying data is later edited."""
        business_date = data.get("business_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        if await _is_closed(property_id, business_date):
            raise HTTPException(status_code=409, detail=f"Business date {business_date} is already closed")

        # Snapshot: folio activity on this date
        day_items = await db.folio_items.find({
            "created_at": {"$gte": business_date, "$lte": business_date + "T99:99:99"},
        }, {"_id": 0}).to_list(20000)

        booking_ids_today = [i.get("booking_id") for i in day_items if i.get("booking_id")]
        bookings_scoped = []
        if booking_ids_today:
            bookings_scoped = await db.bookings.find(
                {"id": {"$in": booking_ids_today}, "property_id": property_id}, {"_id": 0, "id": 1}
            ).to_list(20000)
        booking_ids_prop = {b["id"] for b in bookings_scoped}
        day_items = [i for i in day_items if i.get("booking_id") in booking_ids_prop]

        total_charges = sum(float(i.get("amount", 0) or 0) for i in day_items if i.get("type") == "charge")
        total_payments = sum(float(i.get("amount", 0) or 0) for i in day_items if i.get("type") == "payment")
        total_adjustments = sum(float(i.get("amount", 0) or 0) for i in day_items if i.get("type") == "adjustment")

        # Arrivals/departures for the day (regulatory field on many close reports)
        arrivals = await db.bookings.count_documents({
            "property_id": property_id, "check_in": business_date,
            "status": {"$nin": ["cancelled"]}
        })
        departures = await db.bookings.count_documents({
            "property_id": property_id, "check_out": business_date,
            "status": {"$nin": ["cancelled"]}
        })
        in_house = await db.bookings.count_documents({
            "property_id": property_id, "status": "checked_in"
        })

        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "business_date": business_date,
            "status": "closed",
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "closed_by": current_user.get("name", ""),
            "closed_by_id": current_user.get("id") or current_user.get("email", ""),
            "totals": {
                "charges": round(total_charges, 2),
                "payments": round(total_payments, 2),
                "adjustments": round(total_adjustments, 2),
                "net": round(total_charges - total_payments + total_adjustments, 2),
            },
            "counts": {
                "arrivals": arrivals,
                "departures": departures,
                "in_house": in_house,
                "folio_items": len(day_items),
            },
            "notes": (data.get("notes") or "").strip(),
        }
        await db.night_audit_closes.insert_one(record)
        record.pop("_id", None)
        # Gün Sonu Raporu: kapanış sonrası otomatik e-posta (arka planda)
        try:
            import asyncio as _aio
            from routes.hotel_ops.eod_report import send_eod
            _aio.create_task(send_eod(db, property_id, business_date))
        except Exception:
            pass
        return record

    @router.post("/night-audit/reopen-day/{property_id}")
    async def reopen_day(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin"))):
        """Admin-only override to reopen a previously closed day (audit-logged)."""
        business_date = data.get("business_date")
        if not business_date:
            raise HTTPException(status_code=400, detail="business_date required")
        res = await db.night_audit_closes.update_one(
            {"property_id": property_id, "business_date": business_date, "status": "closed"},
            {"$set": {"status": "reopened", "reopened_at": datetime.now(timezone.utc).isoformat(),
                      "reopened_by": current_user.get("name", ""), "reopen_reason": (data.get("reason") or "").strip()}}
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="No closed record found for that date")
        return {"status": "reopened", "business_date": business_date}

    return router
