"""
City Ledger (Corporate Accounts Receivable)
-------------------------------------------
B2B deferred billing — companies and travel agents pay after stay (30/60/90-day terms).
Competitor parity: Mews, Cloudbeds, Eviivo all ship this as a core PMS module.

Collections:
- city_ledger_companies: {id, name, contact_name, email, phone, address, tax_id, credit_limit, payment_terms_days, notes, active, created_at}
- city_ledger_invoices : {id, company_id, invoice_number, booking_ids[], issue_date, due_date, amount, paid_amount, currency, status, notes, created_at, paid_at?}

Endpoints (all /api/city-ledger/*):
- GET/POST/PUT/DELETE /companies[/{id}]
- GET /companies/{id}/statement   → open invoices + aging
- GET/POST/PUT /invoices[/{id}]
- POST /invoices/{id}/pay          → record payment (partial or full)
- GET /aging                        → 0-30/31-60/61-90/90+ buckets across all companies
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import uuid

from auth import require_perm


class CompanyIn(BaseModel):
    name: str
    contact_name: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    address: Optional[str] = ""
    tax_id: Optional[str] = ""
    credit_limit: float = 0
    payment_terms_days: int = 30
    notes: Optional[str] = ""
    active: bool = True


class InvoiceIn(BaseModel):
    company_id: str
    booking_ids: List[str] = Field(default_factory=list)
    issue_date: Optional[str] = None   # ISO date; defaults to today
    due_date: Optional[str] = None     # auto = issue_date + company.payment_terms_days
    amount: float
    currency: str = "GBP"
    notes: Optional[str] = ""


class PaymentIn(BaseModel):
    amount: float
    method: Optional[str] = "bank_transfer"
    reference: Optional[str] = ""


def create_city_ledger_router(db):
    router = APIRouter(prefix="/city-ledger")

    # ------------------------------ COMPANIES ------------------------------
    @router.get("/companies")
    async def list_companies(
        active_only: bool = False,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {"active": True} if active_only else {}
        rows = await db.city_ledger_companies.find(q, {"_id": 0}).sort("name", 1).to_list(500)
        # Enrich with open balance
        for r in rows:
            invs = await db.city_ledger_invoices.find(
                {"company_id": r["id"], "status": {"$ne": "paid"}}, {"_id": 0, "amount": 1, "paid_amount": 1}
            ).to_list(1000)
            r["open_balance"] = round(sum(float(i.get("amount", 0)) - float(i.get("paid_amount", 0)) for i in invs), 2)
            r["open_invoices"] = len(invs)
        return rows

    @router.post("/companies")
    async def create_company(
        data: CompanyIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        doc = data.model_dump()
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["created_by"] = current_user.get("email", "")
        await db.city_ledger_companies.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/companies/{company_id}")
    async def update_company(
        company_id: str, data: CompanyIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        update = data.model_dump()
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.city_ledger_companies.update_one({"id": company_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Company not found")
        return {"updated": True, "id": company_id}

    @router.delete("/companies/{company_id}")
    async def delete_company(
        company_id: str,
        current_user: dict = Depends(require_perm("delete_bookings")),
    ):
        open_count = await db.city_ledger_invoices.count_documents(
            {"company_id": company_id, "status": {"$ne": "paid"}}
        )
        if open_count:
            raise HTTPException(400, f"Cannot delete — {open_count} open invoice(s)")
        r = await db.city_ledger_companies.delete_one({"id": company_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Company not found")
        return {"deleted": True}

    @router.get("/companies/{company_id}/statement")
    async def company_statement(
        company_id: str,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        company = await db.city_ledger_companies.find_one({"id": company_id}, {"_id": 0})
        if not company:
            raise HTTPException(404, "Company not found")
        invs = await db.city_ledger_invoices.find(
            {"company_id": company_id}, {"_id": 0}
        ).sort("issue_date", -1).to_list(500)
        today = datetime.now(timezone.utc).date().isoformat()
        total_open = sum(float(i.get("amount", 0)) - float(i.get("paid_amount", 0))
                         for i in invs if i.get("status") != "paid")
        total_overdue = sum(float(i.get("amount", 0)) - float(i.get("paid_amount", 0))
                            for i in invs if i.get("status") != "paid" and (i.get("due_date") or "") < today)
        return {
            "company": company,
            "invoices": invs,
            "summary": {
                "total_open": round(total_open, 2),
                "total_overdue": round(total_overdue, 2),
                "invoice_count": len(invs),
                "open_count": sum(1 for i in invs if i.get("status") != "paid"),
            },
        }

    # ------------------------------ INVOICES ------------------------------
    @router.get("/invoices")
    async def list_invoices(
        status: str = "",
        company_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {}
        if status: q["status"] = status
        if company_id: q["company_id"] = company_id
        rows = await db.city_ledger_invoices.find(q, {"_id": 0}).sort("issue_date", -1).to_list(500)
        # enrich with company name
        ids = list({r["company_id"] for r in rows if r.get("company_id")})
        if ids:
            comps = await db.city_ledger_companies.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
            name_by_id = {c["id"]: c["name"] for c in comps}
            for r in rows:
                r["company_name"] = name_by_id.get(r.get("company_id"), "—")
        today = datetime.now(timezone.utc).date().isoformat()
        for r in rows:
            if r.get("status") != "paid" and (r.get("due_date") or "") < today:
                r["is_overdue"] = True
                try:
                    r["days_overdue"] = (datetime.fromisoformat(today) - datetime.fromisoformat(r["due_date"])).days
                except Exception:
                    r["days_overdue"] = 0
            else:
                r["is_overdue"] = False
                r["days_overdue"] = 0
            r["balance"] = round(float(r.get("amount", 0)) - float(r.get("paid_amount", 0)), 2)
        return rows

    @router.post("/invoices")
    async def create_invoice(
        data: InvoiceIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        company = await db.city_ledger_companies.find_one({"id": data.company_id}, {"_id": 0})
        if not company:
            raise HTTPException(404, "Company not found")
        now = datetime.now(timezone.utc)
        issue = data.issue_date or now.date().isoformat()
        # Auto due date = issue + company.payment_terms_days
        if data.due_date:
            due = data.due_date
        else:
            terms = int(company.get("payment_terms_days", 30))
            try:
                due = (datetime.fromisoformat(issue) + timedelta(days=terms)).date().isoformat()
            except Exception:
                due = (now + timedelta(days=terms)).date().isoformat()

        # Invoice number — sequential per year
        year = now.year
        count = await db.city_ledger_invoices.count_documents({"invoice_number": {"$regex": f"^CL-{year}-"}})
        invoice_number = f"CL-{year}-{count + 1:05d}"

        doc = {
            "id": str(uuid.uuid4()),
            "invoice_number": invoice_number,
            "company_id": data.company_id,
            "booking_ids": data.booking_ids,
            "issue_date": issue,
            "due_date": due,
            "amount": float(data.amount),
            "paid_amount": 0.0,
            "currency": data.currency,
            "status": "open",
            "notes": data.notes,
            "created_at": now.isoformat(),
            "created_by": current_user.get("email", ""),
        }
        await db.city_ledger_invoices.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/invoices/{invoice_id}")
    async def update_invoice(
        invoice_id: str, data: InvoiceIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        update = data.model_dump(exclude_unset=True)
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.city_ledger_invoices.update_one({"id": invoice_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Invoice not found")
        return {"updated": True, "id": invoice_id}

    @router.post("/invoices/{invoice_id}/pay")
    async def record_payment(
        invoice_id: str, data: PaymentIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        inv = await db.city_ledger_invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        if data.amount <= 0:
            raise HTTPException(400, "Amount must be positive")
        new_paid = round(float(inv.get("paid_amount", 0)) + float(data.amount), 2)
        amount = float(inv.get("amount", 0))
        status = "paid" if new_paid + 0.001 >= amount else "partial"
        now_iso = datetime.now(timezone.utc).isoformat()
        update = {
            "paid_amount": new_paid,
            "status": status,
            "updated_at": now_iso,
        }
        if status == "paid":
            update["paid_at"] = now_iso
        await db.city_ledger_invoices.update_one({"id": invoice_id}, {
            "$set": update,
            "$push": {"payments": {
                "ts": now_iso, "amount": float(data.amount),
                "method": data.method, "reference": data.reference,
                "recorded_by": current_user.get("email", ""),
            }},
        })
        return {"ok": True, "status": status, "paid_amount": new_paid, "balance": round(amount - new_paid, 2)}

    @router.delete("/invoices/{invoice_id}")
    async def delete_invoice(
        invoice_id: str,
        current_user: dict = Depends(require_perm("delete_bookings")),
    ):
        r = await db.city_ledger_invoices.delete_one({"id": invoice_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Invoice not found")
        return {"deleted": True}

    # ------------------------------ AGING REPORT ------------------------------
    @router.get("/aging")
    async def aging_report(
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """Classic 0-30 / 31-60 / 61-90 / 90+ aging buckets for all open AR."""
        today = datetime.now(timezone.utc).date()
        invs = await db.city_ledger_invoices.find(
            {"status": {"$ne": "paid"}}, {"_id": 0}
        ).to_list(2000)
        comps = await db.city_ledger_companies.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
        name_by_id = {c["id"]: c["name"] for c in comps}

        buckets = {"current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "over90": 0.0}
        by_company = {}

        for inv in invs:
            balance = round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)
            if balance <= 0:
                continue
            try:
                due = datetime.fromisoformat(inv.get("due_date", today.isoformat())).date()
            except Exception:
                due = today
            days_late = (today - due).days
            if days_late <= 0:
                bucket = "current"
            elif days_late <= 30:
                bucket = "d30"
            elif days_late <= 60:
                bucket = "d60"
            elif days_late <= 90:
                bucket = "d90"
            else:
                bucket = "over90"
            buckets[bucket] = round(buckets[bucket] + balance, 2)

            cid = inv.get("company_id", "")
            if cid not in by_company:
                by_company[cid] = {
                    "company_id": cid,
                    "company_name": name_by_id.get(cid, "—"),
                    "current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "over90": 0.0,
                    "total": 0.0,
                }
            by_company[cid][bucket] = round(by_company[cid][bucket] + balance, 2)
            by_company[cid]["total"] = round(by_company[cid]["total"] + balance, 2)

        total = round(sum(buckets.values()), 2)
        rows = sorted(by_company.values(), key=lambda r: r["total"], reverse=True)
        return {"buckets": buckets, "total": total, "by_company": rows, "as_of": today.isoformat()}

    return router
