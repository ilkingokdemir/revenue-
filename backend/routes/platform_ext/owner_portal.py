"""
Owner Portal — for REIT / fractional / condo-hotel owners to see unit performance.

Each owner is linked to one or more rooms. Statements are auto-generated monthly:
  - Revenue from their unit(s)
  - Operating costs allocated
  - Management fee deducted
  - Net distribution amount

Endpoints:
  GET   /api/owners                              — list owners (admin)
  POST  /api/owners                              — create owner profile
  GET   /api/owners/{owner_id}                   — owner detail
  GET   /api/owners/{owner_id}/units             — units assigned
  POST  /api/owners/{owner_id}/units             — assign units (rooms)
  GET   /api/owners/{owner_id}/statement         — monthly statement
  GET   /api/owners/{owner_id}/statement.pdf     — monthly statement PDF
  GET   /api/owners/{owner_id}/performance       — YTD performance dashboard
"""
from datetime import datetime, timezone
import io
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class OwnerIn(BaseModel):
    name: str
    email: str
    phone: str = ""
    company: str = ""
    management_fee_percent: float = 25.0
    notes: str = ""


def create_owner_portal_router(db, require_roles):
    router = APIRouter(prefix="/owners")

    @router.get("")
    async def list_owners(_: dict = Depends(require_roles("admin", "manager"))):
        owners = await db.unit_owners.find({}, {"_id": 0}).sort("name", 1).to_list(200)
        for o in owners:
            o["unit_count"] = await db.unit_assignments.count_documents({"owner_id": o["id"]})
        return {"owners": owners, "count": len(owners)}

    @router.post("")
    async def create_owner(body: OwnerIn,
                           current_user: dict = Depends(require_roles("admin"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), **body.dict(),
               "created_by": current_user.get("name", ""), "created_at": now}
        await db.unit_owners.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/{owner_id}")
    async def get_owner(owner_id: str,
                        _: dict = Depends(require_roles("admin", "manager"))):
        o = await db.unit_owners.find_one({"id": owner_id}, {"_id": 0})
        if not o:
            raise HTTPException(404, "Owner not found")
        units = await db.unit_assignments.find({"owner_id": owner_id}, {"_id": 0}).to_list(100)
        o["units"] = units
        return o

    @router.post("/{owner_id}/units")
    async def assign_units(owner_id: str, body: dict,
                           current_user: dict = Depends(require_roles("admin"))):
        """body: {room_ids: [...], property_id: 'default', share_percent: 100}"""
        room_ids = body.get("room_ids") or []
        if not room_ids:
            raise HTTPException(400, "room_ids required")
        now = datetime.now(timezone.utc).isoformat()
        docs = [{"id": str(uuid.uuid4()), "owner_id": owner_id, "room_id": rid,
                 "property_id": body.get("property_id", ""),
                 "share_percent": float(body.get("share_percent", 100)),
                 "assigned_by": current_user.get("name", ""), "assigned_at": now}
                for rid in room_ids]
        await db.unit_assignments.insert_many(docs)
        return {"assigned": len(docs)}

    @router.get("/{owner_id}/statement")
    async def get_statement(owner_id: str, month: str = "",
                            _: dict = Depends(require_roles("admin", "manager"))):
        """Generate a monthly statement (YYYY-MM)."""
        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        owner = await db.unit_owners.find_one({"id": owner_id}, {"_id": 0})
        if not owner:
            raise HTTPException(404, "Owner not found")
        units = await db.unit_assignments.find({"owner_id": owner_id}, {"_id": 0}).to_list(100)
        room_ids = [u["room_id"] for u in units]
        bookings = await db.bookings.find({
            "room_id": {"$in": room_ids},
            "check_in": {"$regex": f"^{month}"},
            "status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]},
        }, {"_id": 0}).to_list(500)
        gross_revenue = sum(float(b.get("total_price", 0)) for b in bookings)
        nights = sum(int(b.get("nights", 1)) for b in bookings)
        # Apply share_percent
        if units:
            avg_share = sum(u.get("share_percent", 100) for u in units) / len(units) / 100.0
        else:
            avg_share = 1.0
        owner_share_gross = round(gross_revenue * avg_share, 2)
        mgmt_fee = round(owner_share_gross * owner.get("management_fee_percent", 25) / 100, 2)
        # Estimated operating costs (housekeeping, utilities) — simplified 12% of revenue
        opex = round(owner_share_gross * 0.12, 2)
        net_distribution = round(owner_share_gross - mgmt_fee - opex, 2)
        return {
            "owner_id": owner_id, "owner_name": owner["name"], "month": month,
            "unit_count": len(units),
            "bookings_count": len(bookings),
            "nights_sold": nights,
            "gross_revenue": round(gross_revenue, 2),
            "owner_share_gross": owner_share_gross,
            "management_fee_percent": owner.get("management_fee_percent", 25),
            "management_fee": mgmt_fee,
            "operating_costs_est": opex,
            "net_distribution": net_distribution,
            "bookings": [{k: b.get(k) for k in ["booking_ref", "check_in",
                                                 "check_out", "total_price", "nights"]} for b in bookings[:50]],
        }

    @router.get("/{owner_id}/performance")
    async def get_performance(owner_id: str, year: str = "",
                              _: dict = Depends(require_roles("admin", "manager"))):
        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        owner = await db.unit_owners.find_one({"id": owner_id}, {"_id": 0})
        if not owner:
            raise HTTPException(404, "Owner not found")
        months = [{"month": f"{year}-{m:02d}"} for m in range(1, 13)]
        for mo in months:
            st = await get_statement(owner_id, mo["month"])
            mo["revenue"] = st["gross_revenue"]
            mo["net"] = st["net_distribution"]
            mo["nights"] = st["nights_sold"]
        total = {
            "revenue": sum(m["revenue"] for m in months),
            "net": sum(m["net"] for m in months),
            "nights": sum(m["nights"] for m in months),
        }
        return {"owner_id": owner_id, "year": year, "months": months, "total": total}

    @router.get("/{owner_id}/statement.pdf")
    async def get_statement_pdf(owner_id: str, month: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate a printable monthly statement PDF for the owner."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

        st = await get_statement(owner_id, month)
        owner = await db.unit_owners.find_one({"id": owner_id}, {"_id": 0})
        period = st["month"]

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm,
            title=f"Owner Statement {period} — {st['owner_name']}",
        )
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                            fontSize=16, leading=18, textColor=colors.HexColor("#0c0a09"))
        small = ParagraphStyle("small", parent=styles["Normal"],
                               fontSize=9, leading=11, textColor=colors.HexColor("#525252"))
        muted = ParagraphStyle("muted", parent=styles["Normal"],
                               fontSize=8, textColor=colors.HexColor("#737373"))
        story = []

        story.append(Paragraph("OWNER DISTRIBUTION STATEMENT", h1))
        story.append(Paragraph(
            f"<b>{st['owner_name']}</b> · {owner.get('company','') or '—'} · {owner.get('email','')}", small))
        story.append(Paragraph(
            f"Period: <b>{period}</b> · Units: <b>{st['unit_count']}</b> · "
            f"Issued: {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M')} UTC · "
            f"By: {current_user.get('name', '-')}", small))
        story.append(Spacer(1, 6 * mm))

        # Summary table
        summary = [
            ["Description", "Amount (£)"],
            ["Gross Revenue (all units)", f"{st['gross_revenue']:.2f}"],
            ["Owner Share (Gross)", f"{st['owner_share_gross']:.2f}"],
            [f"Less: Management Fee ({st['management_fee_percent']}%)", f"-{st['management_fee']:.2f}"],
            ["Less: Operating Costs (est. 12%)", f"-{st['operating_costs_est']:.2f}"],
            ["NET DISTRIBUTION", f"{st['net_distribution']:.2f}"],
        ]
        tbl = Table(summary, colWidths=[110 * mm, 50 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0c0a09")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcfce7")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 11),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a8a29e")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6 * mm))

        # Performance metrics
        story.append(Paragraph(
            f"<b>Performance:</b> {st['bookings_count']} reservations · "
            f"{st['nights_sold']} room-nights sold", small))
        story.append(Spacer(1, 6 * mm))

        # Bookings detail
        if st["bookings"]:
            story.append(Paragraph("<b>Reservations contributing to this period:</b>", small))
            story.append(Spacer(1, 2 * mm))
            detail = [["Ref", "Check-in", "Check-out", "Nights", "Total (£)"]]
            for b in st["bookings"][:30]:
                detail.append([
                    b.get("booking_ref", "—"),
                    b.get("check_in", ""),
                    b.get("check_out", ""),
                    str(b.get("nights", 1)),
                    f"{float(b.get('total_price', 0)):.2f}",
                ])
            dtbl = Table(detail, colWidths=[34*mm, 30*mm, 30*mm, 20*mm, 30*mm])
            dtbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f4")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#d6d3d1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#fafaf9")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(dtbl)

        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(
            "Operating costs above are estimated at 12% of unit-revenue for indicative reporting only. "
            "Final reconciliation will be issued with the year-end audited accounts. "
            "Please contact the management office for any queries regarding this statement.",
            muted))

        doc.build(story)
        buf.seek(0)
        filename = f"owner_statement_{owner_id[:8]}_{period}.pdf"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return router
