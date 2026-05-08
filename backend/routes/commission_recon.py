"""
Commission Reconciliation (P0)
Reconciles uploaded OTA commission invoices (Booking.com / Expedia / etc) against our
internal ledger. A statement contains line items like {booking_ref, commission, channel, month}.
We match each line to our booking and flag discrepancies. Uses the payment_method='channel_collection'
+ channel field from folio_items (Iter 154) to cross-check collected amounts.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, List
import uuid
import logging

logger = logging.getLogger(__name__)


def create_commission_recon_router(db, require_roles):
    router = APIRouter()

    @router.get("/commission-recon/statements/{property_id}")
    async def list_statements(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.commission_statements.find({"property_id": property_id}, {"_id": 0})\
            .sort("uploaded_at", -1).to_list(100)
        return rows

    @router.post("/commission-recon/upload/{property_id}")
    async def upload_statement(property_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Accept a pasted/parsed OTA statement and reconcile.
        Body: { channel: "Booking.com", period: "2026-01", lines: [{booking_ref, nights, commission, gross}] }
        """
        channel = (data.get("channel") or "").strip()
        period = (data.get("period") or "").strip()  # YYYY-MM
        lines: List[Dict] = data.get("lines") or []
        if not channel or not lines:
            raise HTTPException(status_code=400, detail="channel and lines[] required")

        # Match each line against our bookings + folio_items
        reconciled = []
        total_stmt_comm = 0.0
        total_stmt_gross = 0.0
        matched_count = 0
        unmatched_count = 0
        variance_count = 0

        for line in lines:
            ref = str(line.get("booking_ref") or "").strip()
            stmt_commission = float(line.get("commission") or 0)
            stmt_gross = float(line.get("gross") or 0)
            total_stmt_comm += stmt_commission
            total_stmt_gross += stmt_gross

            booking = None
            if ref:
                booking = await db.bookings.find_one(
                    {"property_id": property_id, "booking_ref": ref}, {"_id": 0}
                )
            status = "unmatched"
            variance = 0.0
            our_gross = 0.0
            our_commission_paid = 0.0
            booking_id = ""
            if booking:
                booking_id = booking.get("id", "")
                our_gross = float(booking.get("total_price") or 0)
                # What we've recorded as this channel collecting
                channel_payments = await db.folio_items.find({
                    "booking_id": booking_id,
                    "type": "payment",
                    "payment_method": "channel_collection",
                    "channel": channel,
                }, {"_id": 0}).to_list(50)
                our_commission_paid = sum(float(p.get("amount", 0)) for p in channel_payments)
                variance = round(our_gross - stmt_gross, 2)
                if abs(variance) < 0.01:
                    status = "match"
                    matched_count += 1
                else:
                    status = "variance"
                    variance_count += 1
            else:
                unmatched_count += 1

            reconciled.append({
                "booking_ref": ref,
                "booking_id": booking_id,
                "guest_name": (booking or {}).get("guest_name", ""),
                "check_in": (booking or {}).get("check_in", ""),
                "statement_gross": round(stmt_gross, 2),
                "our_gross": round(our_gross, 2),
                "statement_commission": round(stmt_commission, 2),
                "channel_collected_on_file": round(our_commission_paid, 2),
                "variance": variance,
                "status": status,
            })

        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "channel": channel,
            "period": period,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "uploaded_by": current_user.get("name", ""),
            "summary": {
                "lines_total": len(lines),
                "matched": matched_count,
                "variance": variance_count,
                "unmatched": unmatched_count,
                "statement_gross": round(total_stmt_gross, 2),
                "statement_commission": round(total_stmt_comm, 2),
            },
            "lines": reconciled,
            "status": "reconciled",
        }
        await db.commission_statements.insert_one(record)
        record.pop("_id", None)
        return record

    @router.delete("/commission-recon/statements/{statement_id}")
    async def delete_statement(statement_id: str,
                               current_user: dict = Depends(require_roles("admin"))):
        res = await db.commission_statements.delete_one({"id": statement_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    return router
