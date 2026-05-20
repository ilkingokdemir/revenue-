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
from typing import Optional, List, Dict
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


class InvoiceLineIn(BaseModel):
    description: str = ""
    amount: float = 0
    currency: str = "GBP"
    quantity: float = 1


class InvoiceIn(BaseModel):
    company_id: str
    booking_ids: List[str] = Field(default_factory=list)
    issue_date: Optional[str] = None   # ISO date; defaults to today
    due_date: Optional[str] = None     # auto = issue_date + company.payment_terms_days
    amount: float
    currency: str = "GBP"
    notes: Optional[str] = ""
    # Multi-currency: optional line items, each in its own currency. If provided,
    # `amount` is computed from the sum converted to the invoice's base currency.
    lines: List[InvoiceLineIn] = Field(default_factory=list)


class PaymentIn(BaseModel):
    amount: float
    method: Optional[str] = "bank_transfer"
    reference: Optional[str] = ""


def create_city_ledger_router(db, resend_lib=None):
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
        if status:
            q["status"] = status
        if company_id:
            q["company_id"] = company_id
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

        # Multi-currency line items: roll up to invoice currency using latest FX
        lines = [ln.model_dump() for ln in data.lines] if data.lines else []
        amount = float(data.amount)
        if lines:
            try:
                from routes.finance_ext.currency_fx import _get_rate_map, _convert
                rates = await _get_rate_map(db)
                rolled = 0.0
                for li in lines:
                    line_cur = (li.get("currency") or data.currency).upper()
                    line_gross = float(li.get("amount", 0)) * float(li.get("quantity", 1))
                    li["line_total_native"] = round(line_gross, 2)
                    li["line_total_invoice_cur"] = _convert(line_gross, line_cur, data.currency, rates, data.currency)
                    rolled += li["line_total_invoice_cur"]
                amount = round(rolled, 2)
            except Exception:
                # If FX module unavailable for any reason, fall back to provided amount
                pass

        doc = {
            "id": str(uuid.uuid4()),
            "invoice_number": invoice_number,
            "company_id": data.company_id,
            "booking_ids": data.booking_ids,
            "issue_date": issue,
            "due_date": due,
            "amount": amount,
            "paid_amount": 0.0,
            "currency": data.currency,
            "lines": lines,
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

    # ------------------------------ INVOICE PDF + EMAIL ------------------------------
    @router.get("/invoices/{invoice_id}/pdf")
    async def invoice_pdf(
        invoice_id: str,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """Stream the invoice as a printable A4 PDF (inline)."""
        import io
        from fastapi.responses import StreamingResponse
        pdf_bytes, inv_num, _email = await build_invoice_pdf_bytes(db, invoice_id)
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{inv_num}.pdf"'},
        )

    @router.post("/invoices/{invoice_id}/email")
    async def email_invoice(
        invoice_id: str, data: Dict,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """Manually email the invoice PDF to a recipient chosen by the user.

        Body: { "to": "a@b.com" | ["a@b.com", ...], "subject": "...", "message": "html string" }
        All three fields are composed by the user (no auto-defaults silently sent).
        """
        import os
        import base64
        if not resend_lib or not os.environ.get("RESEND_API_KEY"):
            raise HTTPException(503, "Email service not configured")

        raw_to = data.get("to") or ""
        if isinstance(raw_to, str):
            to_list = [x.strip() for x in raw_to.split(",") if x.strip()]
        elif isinstance(raw_to, list):
            to_list = [x for x in raw_to if x]
        else:
            to_list = []
        if not to_list:
            raise HTTPException(400, "At least one recipient required")

        subject = (data.get("subject") or "").strip()
        message = (data.get("message") or "").strip()
        if not subject or not message:
            raise HTTPException(400, "Subject and message are required")

        pdf_bytes, inv_num, _ = await build_invoice_pdf_bytes(db, invoice_id)
        sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

        body_html = (
            "<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;"
            "max-width:640px;margin:auto;padding:24px;color:#1f2937;'>"
            f"<h2 style='color:#1c1917;margin:0 0 8px 0;'>Invoice · {inv_num}</h2>"
            f"<p style='color:#6b7280;font-size:13px;'>Sent by {current_user.get('name', 'Accounts team')}</p>"
            f"<div style='font-size:14px;line-height:1.6;'>{message}</div>"
            "<p style='color:#9ca3af;font-size:11px;margin-top:24px;'>A PDF copy of the invoice is attached.</p>"
            "</div>"
        )

        try:
            resend_lib.Emails.send({
                "from": sender,
                "to": to_list,
                "subject": subject,
                "html": body_html,
                "attachments": [{
                    "filename": f"{inv_num}.pdf",
                    "content": base64.b64encode(pdf_bytes).decode(),
                }],
            })
        except Exception as e:
            raise HTTPException(502, f"Email send failed: {str(e)[:160]}")

        await db.city_ledger_invoices.update_one(
            {"id": invoice_id},
            {"$push": {"email_log": {
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_by": current_user.get("email", ""),
                "to": to_list,
                "subject": subject,
            }}}
        )
        return {"ok": True, "sent_to": to_list, "invoice_number": inv_num}

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


# ============================================================================
# Module-level helper: build PDF bytes for an invoice (reusable by email endpoint
# and any future GET /invoices/{id}/pdf). No side-effects.
# ============================================================================

async def build_invoice_pdf_bytes(db, invoice_id):
    """Build a simple A4 invoice PDF. Returns (bytes, invoice_number, company_email)."""
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet

    inv = await db.city_ledger_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    company = await db.city_ledger_companies.find_one({"id": inv.get("company_id", "")}, {"_id": 0}) or {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(
        "<para align='left'><font size='9' color='#78716c'>Corporate Invoice · My Hotel Box</font></para>",
        styles["Normal"]))
    story.append(Paragraph(
        f"<para align='left'><font size='20' color='#1c1917'><b>INVOICE · {inv['invoice_number']}</b></font></para>",
        styles["Normal"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#1c1917"),
                            spaceBefore=4, spaceAfter=10))

    # Bill-to
    bill_to = [
        ["Bill To", company.get("name", "—"), "Issue Date", inv.get("issue_date", "—")],
        ["Contact", company.get("contact_name", "—"), "Due Date", inv.get("due_date", "—")],
        ["Email", company.get("email", "—"), "Currency", inv.get("currency", "GBP")],
        ["Tax ID", company.get("tax_id", "—"), "Status", inv.get("status", "open").title()],
    ]
    tbl = Table(bill_to, colWidths=[22 * mm, 78 * mm, 22 * mm, 50 * mm])
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#78716c")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#78716c")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 12))

    # Amount block
    cur_sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(inv.get("currency", "GBP"), "£")
    balance = round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)

    # Optional multi-currency line items
    lines = inv.get("lines") or []
    if lines:
        story.append(Paragraph(
            "<para><font size='9' color='#57534e'><b>Line Items</b></font></para>",
            styles["Normal"]))
        story.append(Spacer(1, 4))
        line_rows = [["Description", "Qty", "Rate (native)", "Currency", f"Total ({inv.get('currency', 'GBP')})"]]
        line_cur_syms = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺", "AED": "د.إ", "JPY": "¥",
                         "CAD": "C$", "AUD": "A$", "CHF": "CHF", "INR": "₹"}
        for li in lines:
            l_cur = li.get("currency", "GBP")
            l_sym = line_cur_syms.get(l_cur, l_cur + " ")
            line_rows.append([
                li.get("description", "—"),
                f"{float(li.get('quantity', 1)):g}",
                f"{l_sym}{float(li.get('amount', 0)):.2f}",
                l_cur,
                f"{cur_sym}{float(li.get('line_total_invoice_cur', 0)):.2f}",
            ])
        lt = Table(line_rows, colWidths=[70 * mm, 14 * mm, 30 * mm, 20 * mm, 38 * mm])
        lt.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f4")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e7e5e4")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(lt)
        story.append(Spacer(1, 10))

    amount_rows = [
        ["Description", inv.get("notes") or "Corporate stays per attached bookings", f"{cur_sym}{float(inv.get('amount', 0)):.2f}"],
    ]
    if float(inv.get("paid_amount", 0)) > 0:
        amount_rows.append(["Payments received", "", f"-{cur_sym}{float(inv.get('paid_amount', 0)):.2f}"])
    amount_rows.append(["BALANCE DUE", "", f"{cur_sym}{balance:.2f}"])
    at = Table(amount_rows, colWidths=[40 * mm, 90 * mm, 42 * mm])
    at.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 12),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#e7e5e4")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#1c1917")),
        ("TEXTCOLOR", (0, -1), (-1, -1),
         colors.HexColor("#059669") if balance <= 0 else colors.HexColor("#dc2626")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(at)

    # Booking refs
    if inv.get("booking_ids"):
        story.append(Spacer(1, 12))
        story.append(Paragraph(
            f"<para><font size='8' color='#78716c'>Covered bookings: {', '.join(inv['booking_ids'])}</font></para>",
            styles["Normal"]))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d6d3d1")))
    story.append(Paragraph(
        f"<para align='center'><font size='7' color='#a8a29e'>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · Payment terms: {company.get('payment_terms_days', 30)} days · Thank you</font></para>",
        styles["Normal"]))
    doc.build(story)

    return buf.getvalue(), inv["invoice_number"], company.get("email", "")
