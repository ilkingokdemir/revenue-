"""
Deposit / Advance-payment liability ledger (P0).
Shows unearned revenue — payments made by guests for bookings that have not yet
checked in. Regulatory disclosure in many jurisdictions; financial hygiene
measure for hoteliers to know how much of their cash is actually "earned".
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def create_deposit_ledger_router(db, require_roles):
    router = APIRouter()

    @router.get("/deposit-ledger/{property_id}")
    async def deposit_ledger(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Total deposits held against future bookings, broken down by arrival month."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        pq = {} if property_id == "all" else {"property_id": property_id}
        # Future + current (not yet departed) bookings
        bookings = await db.bookings.find({
            **pq,
            "check_out": {"$gt": today},
            "status": {"$nin": ["cancelled", "no_show"]},
        }, {"_id": 0}).to_list(20000)

        if not bookings:
            return {"total_liability": 0, "count": 0, "by_month": [], "by_booking": []}

        booking_ids = [b["id"] for b in bookings]
        # Aggregate payments per booking
        pipeline = [
            {"$match": {"booking_id": {"$in": booking_ids}, "type": "payment"}},
            {"$group": {"_id": "$booking_id", "paid": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}}}},
        ]
        paid_map = {}
        async for row in db.folio_items.aggregate(pipeline):
            paid_map[row["_id"]] = float(row["paid"])

        by_booking = []
        by_month = {}
        total = 0.0
        for b in bookings:
            paid = round(paid_map.get(b["id"], 0), 2)
            if paid <= 0:
                continue
            total_price = float(b.get("total_price") or 0)
            # Liability = min(paid, total_price). Amounts above total_price aren't "deposit liability".
            liability = round(min(paid, total_price), 2)
            if liability <= 0:
                continue
            arrival = b.get("check_in", "")
            month = arrival[:7] if arrival else "unknown"

            by_booking.append({
                "id": b["id"],
                "booking_ref": b.get("booking_ref", ""),
                "guest_name": b.get("guest_name", ""),
                "check_in": arrival,
                "check_out": b.get("check_out", ""),
                "total_price": round(total_price, 2),
                "paid": paid,
                "liability": liability,
                "source": b.get("source", ""),
                "status": b.get("status", ""),
            })

            by_month.setdefault(month, {"month": month, "count": 0, "liability": 0.0})
            by_month[month]["count"] += 1
            by_month[month]["liability"] += liability
            total += liability

        for m in by_month.values():
            m["liability"] = round(m["liability"], 2)
        by_month_out = sorted(by_month.values(), key=lambda r: r["month"])
        by_booking.sort(key=lambda r: r["check_in"])

        return {
            "total_liability": round(total, 2),
            "count": len(by_booking),
            "by_month": by_month_out,
            "by_booking": by_booking[:500],
            "as_of": today,
        }

    return router
