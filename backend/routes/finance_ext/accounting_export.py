"""
Accounting Export — QuickBooks Online / Xero compatible CSVs for offline import.

Most small PMSes lack this. Saves accountants 4-8 hours / month vs manual entry.

Endpoints:
- GET /api/accounting/export/{property_id}/sales?from=&to=&format=quickbooks|xero
- GET /api/accounting/export/{property_id}/payments?from=&to=&format=quickbooks|xero

Formats:
  quickbooks  → Sales Receipt / General Journal CSV
  xero        → Sales Invoice CSV
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict
import csv
import io
import logging

logger = logging.getLogger(__name__)


def create_accounting_export_router(db, require_roles):
    router = APIRouter()

    DEFAULT_MAPPING = {
        "ar_account":      "Accounts Receivable",
        "revenue_account": "Room Revenue",
        "cash_account":    "Cash",
        "xero_revenue_code": "200",
        "xero_payment_code": "200",
        "xero_tax_type":     "Tax on Sales",
    }

    async def _mapping(property_id: str) -> dict:
        doc = await db.accounting_mapping.find_one({"property_id": property_id}, {"_id": 0}) or {}
        return {**DEFAULT_MAPPING, **doc}

    @router.get("/accounting/mapping/{property_id}")
    async def get_mapping(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _mapping(property_id)

    @router.post("/accounting/mapping/{property_id}")
    async def save_mapping(property_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        update = {"property_id": property_id, **{k: v for k, v in data.items() if k in DEFAULT_MAPPING}}
        await db.accounting_mapping.update_one(
            {"property_id": property_id}, {"$set": update}, upsert=True
        )
        return {"ok": True, "mapping": await _mapping(property_id)}

    def _csv(rows: List[List], headers: List[str], filename: str) -> StreamingResponse:
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    async def _bookings_in_window(property_id: str, frm: str, to: str) -> List[Dict]:
        return await db.bookings.find({
            "property_id": property_id,
            "check_in":  {"$lte": to},
            "check_out": {"$gt":  frm},
            "status":    {"$nin": ["cancelled"]},
        }, {"_id": 0}).to_list(5000)

    @router.get("/accounting/export/{property_id}/sales")
    async def export_sales(property_id: str,
                            from_: str = "", to: str = "",
                            format: str = "quickbooks",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Export bookings as journal entries / invoices for the date window."""
        if not from_ or not to:
            today = datetime.now(timezone.utc).date()
            first = today.replace(day=1)
            from_ = from_ or first.isoformat()
            to = to or today.isoformat()
        try:
            date.fromisoformat(from_); date.fromisoformat(to)
        except Exception:
            raise HTTPException(400, "from/to must be YYYY-MM-DD")

        bookings = await _bookings_in_window(property_id, from_, to)
        fname_base = f"sales_{property_id}_{from_}_to_{to}"
        mp = await _mapping(property_id)

        if format == "xero":
            # Xero Sales Invoice CSV columns
            headers = [
                "*ContactName", "EmailAddress", "*InvoiceNumber", "Reference",
                "*InvoiceDate", "*DueDate", "*Description", "*Quantity",
                "*UnitAmount", "*AccountCode", "*TaxType",
            ]
            rows = []
            for b in bookings:
                ci = b.get("check_in", "")[:10]
                co = b.get("check_out", "")[:10]
                desc = f"Room: {b.get('room_type','Standard')} · {ci} → {co}"
                rows.append([
                    (b.get("guest_name") or "Walk-in")[:80],
                    b.get("guest_email") or "",
                    b.get("booking_ref") or b.get("id", "")[:18],
                    f"{property_id}-{b.get('source','direct')}",
                    ci, co, desc, 1,
                    round(float(b.get("total_price") or 0), 2),
                    mp["xero_revenue_code"],
                    mp["xero_tax_type"],
                ])
            return _csv(rows, headers, f"{fname_base}_xero.csv")

        # QuickBooks General Journal CSV
        headers = [
            "Date", "Journal No.", "Account",
            "Debits", "Credits", "Description", "Name", "Class",
        ]
        rows = []
        for b in bookings:
            jno = b.get("booking_ref") or b.get("id", "")[:8]
            ci = b.get("check_in", "")[:10]
            total = round(float(b.get("total_price") or 0), 2)
            name = (b.get("guest_name") or "Walk-in")[:80]
            klass = b.get("source", "direct")
            rows.append([ci, jno, mp["ar_account"],      total, "",     f"Booking {jno} {ci}", name, klass])
            rows.append([ci, jno, mp["revenue_account"], "",    total,  f"Booking {jno} {ci}", name, klass])
        return _csv(rows, headers, f"{fname_base}_quickbooks.csv")

    @router.get("/accounting/export/{property_id}/payments")
    async def export_payments(property_id: str,
                               from_: str = "", to: str = "",
                               format: str = "quickbooks",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Export payment receipts."""
        if not from_ or not to:
            today = datetime.now(timezone.utc).date()
            first = today.replace(day=1)
            from_ = from_ or first.isoformat()
            to = to or today.isoformat()

        payments = await db.payments.find({
            "property_id": property_id,
            "created_at": {"$gte": from_, "$lte": to + "T23:59:59Z"},
            "status": {"$in": ["paid", "succeeded", "captured", "completed"]},
        }, {"_id": 0}).to_list(5000)

        fname_base = f"payments_{property_id}_{from_}_to_{to}"
        mp = await _mapping(property_id)
        if format == "xero":
            headers = ["*Date", "*Amount", "*Reference", "*Account", "*Description", "ContactName"]
            rows = []
            for p in payments:
                d = p.get("created_at", "")[:10]
                rows.append([
                    d,
                    round(float(p.get("amount") or 0), 2),
                    p.get("id", "")[:24],
                    mp["xero_payment_code"],
                    f"Payment {p.get('method','card')} · {p.get('booking_id','')[:8]}",
                    p.get("guest_name", ""),
                ])
            return _csv(rows, headers, f"{fname_base}_xero.csv")

        # QB
        headers = ["Date", "Reference", "Account", "Debits", "Credits", "Description", "Name"]
        rows = []
        for p in payments:
            d = p.get("created_at", "")[:10]
            amt = round(float(p.get("amount") or 0), 2)
            ref = p.get("id", "")[:18]
            name = p.get("guest_name", "")
            rows.append([d, ref, mp["cash_account"],     amt, "",  f"Payment {p.get('method','card')}", name])
            rows.append([d, ref, mp["ar_account"],       "",  amt, f"Payment {p.get('method','card')}", name])
        return _csv(rows, headers, f"{fname_base}_quickbooks.csv")

    @router.get("/accounting/export/{property_id}/summary")
    async def export_summary(property_id: str,
                              from_: str = "", to: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """JSON summary of what would be exported (for the UI preview)."""
        if not from_ or not to:
            today = datetime.now(timezone.utc).date()
            first = today.replace(day=1)
            from_ = from_ or first.isoformat()
            to = to or today.isoformat()
        bookings = await _bookings_in_window(property_id, from_, to)
        payments = await db.payments.count_documents({
            "property_id": property_id,
            "created_at": {"$gte": from_, "$lte": to + "T23:59:59Z"},
            "status": {"$in": ["paid", "succeeded", "captured", "completed"]},
        })
        total_revenue = sum(float(b.get("total_price") or 0) for b in bookings)
        return {
            "from": from_, "to": to,
            "bookings_count": len(bookings),
            "total_revenue": round(total_revenue, 2),
            "payments_count": payments,
            "by_source": {},
        }

    return router
