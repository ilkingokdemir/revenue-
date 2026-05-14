"""
Meeting & Events Sales (MICE) — Tier-1 banquet/wedding/conference sales pipeline.

Differs from existing /conference-sc (which is operational floor management):
this module is the SALES funnel — RFPs, quotes, conversions, BEO (Banquet Event Order)
sign-off, and conversion analytics that revenue managers need.

Pipeline stages:
  inquiry → site_visit → proposal_sent → negotiating → confirmed → invoiced → completed
  (or → lost at any stage with reason)

Endpoints:
  GET   /api/meetings                          — list (with stage filter)
  POST  /api/meetings                          — create RFP / lead
  GET   /api/meetings/{id}                     — detail with line items
  PATCH /api/meetings/{id}                     — update / move stage / mark lost
  POST  /api/meetings/{id}/items               — add line item (rooms, F&B, AV, space)
  DELETE /api/meetings/{id}/items/{item_id}    — remove line item
  GET   /api/meetings/{id}/proposal.pdf        — branded proposal PDF for client
  GET   /api/meetings/pipeline                 — pipeline view (Kanban data)
  GET   /api/meetings/analytics                — conversion funnel + revenue
"""
from datetime import datetime, timezone, timedelta
import io
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


STAGES = ["inquiry", "site_visit", "proposal_sent", "negotiating",
          "confirmed", "invoiced", "completed", "lost"]
EVENT_TYPES = ["wedding", "corporate_meeting", "conference", "gala",
               "birthday", "association", "training", "other"]
ITEM_KINDS = ["room_block", "fnb", "av_tech", "meeting_space", "decor", "misc"]


class MeetingIn(BaseModel):
    name: str
    event_type: str = "wedding"
    property_id: str
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    company: str = ""
    event_date: str            # YYYY-MM-DD
    end_date: str = ""
    guests_count: int = 0
    rooms_required: int = 0
    spaces_required: List[str] = []
    budget_estimate: float = 0
    notes: str = ""
    source: str = "direct"     # direct | referral | website | ota | sales-rep


class LineItemIn(BaseModel):
    kind: str = "fnb"
    label: str
    qty: float = 1
    unit_price: float = 0
    notes: str = ""


def create_meetings_router(db, require_roles):
    router = APIRouter(prefix="/meetings")

    @router.get("")
    async def list_meetings(stage: str = "", property_id: str = "",
                            from_date: str = "", to_date: str = "",
                            _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if stage:
            q["stage"] = stage
        if property_id and property_id != "all":
            q["property_id"] = property_id
        if from_date or to_date:
            dq: dict = {}
            if from_date:
                dq["$gte"] = from_date
            if to_date:
                dq["$lte"] = to_date
            q["event_date"] = dq
        rows = await db.meeting_sales.find(q, {"_id": 0}).sort("event_date", 1).to_list(500)
        # Sum totals lazily
        for r in rows:
            items = await db.meeting_sale_items.find({"meeting_id": r["id"]},
                                                      {"_id": 0, "qty": 1, "unit_price": 1}).to_list(100)
            r["total_estimate"] = round(sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items), 2)
            r["items_count"] = len(items)
        return {"meetings": rows, "count": len(rows), "stages": STAGES}

    @router.post("")
    async def create_meeting(body: MeetingIn,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        if body.event_type not in EVENT_TYPES:
            raise HTTPException(400, f"Invalid event_type; use one of {EVENT_TYPES}")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            **body.dict(),
            "stage": "inquiry",
            "stage_history": [{"stage": "inquiry", "at": now, "by": current_user.get("name", "")}],
            "owner_sales_rep": current_user.get("name", ""),
            "created_at": now,
            "lost_reason": None,
        }
        await db.meeting_sales.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/pipeline")
    async def pipeline(property_id: str = "",
                       _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.meeting_sales.find(q, {"_id": 0}).to_list(1000)
        # Group by stage
        by_stage: dict = {s: [] for s in STAGES}
        for r in rows:
            stage = r.get("stage", "inquiry")
            if stage in by_stage:
                items = await db.meeting_sale_items.find({"meeting_id": r["id"]},
                                                          {"_id": 0, "qty": 1, "unit_price": 1}).to_list(100)
                r["total_estimate"] = round(sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items), 2)
                by_stage[stage].append(r)
        # Sort each lane by event_date ascending
        for s in by_stage:
            by_stage[s].sort(key=lambda m: m.get("event_date", ""))
        # Pipeline value (excl lost & completed)
        active_value = sum(r["total_estimate"] for s in STAGES if s not in ("lost", "completed")
                           for r in by_stage[s])
        return {"by_stage": by_stage, "active_value": round(active_value, 2),
                "stages": STAGES}

    @router.get("/analytics")
    async def analytics(property_id: str = "", days: int = 90,
                        _: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: dict = {"created_at": {"$gte": since}}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.meeting_sales.find(q, {"_id": 0}).to_list(2000)
        funnel = {s: 0 for s in STAGES}
        for r in rows:
            funnel[r.get("stage", "inquiry")] = funnel.get(r.get("stage", "inquiry"), 0) + 1
        total = len(rows)
        confirmed_or_better = funnel["confirmed"] + funnel["invoiced"] + funnel["completed"]
        win_rate = round(confirmed_or_better / max(1, total - funnel["lost"]) * 100, 1)
        # Revenue from confirmed+
        won = [r for r in rows if r.get("stage") in ("confirmed", "invoiced", "completed")]
        won_revenue = 0.0
        for r in won:
            items = await db.meeting_sale_items.find({"meeting_id": r["id"]},
                                                      {"_id": 0, "qty": 1, "unit_price": 1}).to_list(100)
            won_revenue += sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items)
        # Lost reasons
        lost = [r for r in rows if r.get("stage") == "lost"]
        lost_reasons: dict = {}
        for lm in lost:
            r = lm.get("lost_reason") or "unspecified"
            lost_reasons[r] = lost_reasons.get(r, 0) + 1
        return {
            "period_days": days,
            "total_inquiries": total,
            "funnel": funnel,
            "win_rate_pct": win_rate,
            "won_count": len(won),
            "won_revenue_estimate": round(won_revenue, 2),
            "avg_deal_size": round(won_revenue / max(1, len(won)), 2),
            "lost_count": len(lost),
            "lost_reasons": lost_reasons,
        }

    @router.get("/{meeting_id}")
    async def get_meeting(meeting_id: str,
                          _: dict = Depends(require_roles("admin", "manager"))):
        m = await db.meeting_sales.find_one({"id": meeting_id}, {"_id": 0})
        if not m:
            raise HTTPException(404, "Meeting not found")
        items = await db.meeting_sale_items.find({"meeting_id": meeting_id}, {"_id": 0}).to_list(200)
        m["items"] = items
        m["total_estimate"] = round(sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items), 2)
        return m

    @router.patch("/{meeting_id}")
    async def patch_meeting(meeting_id: str, body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        m = await db.meeting_sales.find_one({"id": meeting_id}, {"_id": 0})
        if not m:
            raise HTTPException(404, "Meeting not found")
        update: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
        # Stage transition tracked in history
        new_stage = body.get("stage")
        if new_stage and new_stage != m.get("stage"):
            if new_stage not in STAGES:
                raise HTTPException(400, f"Invalid stage; use {STAGES}")
            history = m.get("stage_history", [])
            history.append({"stage": new_stage,
                            "at": datetime.now(timezone.utc).isoformat(),
                            "by": current_user.get("name", "")})
            update["stage"] = new_stage
            update["stage_history"] = history
            if new_stage == "lost":
                update["lost_reason"] = body.get("lost_reason", "unspecified")
        # Free-form fields
        for k in ("name", "contact_name", "contact_email", "contact_phone", "company",
                  "event_date", "end_date", "guests_count", "rooms_required",
                  "budget_estimate", "notes", "owner_sales_rep"):
            if k in body:
                update[k] = body[k]
        await db.meeting_sales.update_one({"id": meeting_id}, {"$set": update})
        return {"updated": True, "fields": list(update.keys())}

    @router.post("/{meeting_id}/items")
    async def add_item(meeting_id: str, body: LineItemIn,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        m = await db.meeting_sales.find_one({"id": meeting_id}, {"_id": 0, "id": 1})
        if not m:
            raise HTTPException(404, "Meeting not found")
        if body.kind not in ITEM_KINDS:
            raise HTTPException(400, f"Invalid kind; use {ITEM_KINDS}")
        doc = {
            "id": str(uuid.uuid4()),
            "meeting_id": meeting_id,
            **body.dict(),
            "subtotal": round(body.qty * body.unit_price, 2),
            "added_by": current_user.get("name", ""),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.meeting_sale_items.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/{meeting_id}/items/{item_id}")
    async def delete_item(meeting_id: str, item_id: str,
                          _: dict = Depends(require_roles("admin", "manager"))):
        r = await db.meeting_sale_items.delete_one({"id": item_id, "meeting_id": meeting_id})
        return {"deleted": r.deleted_count}

    @router.get("/{meeting_id}/proposal.pdf")
    async def proposal_pdf(meeting_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Branded PDF proposal for the prospect — itemised quote, totals, T&Cs."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

        m = await db.meeting_sales.find_one({"id": meeting_id}, {"_id": 0})
        if not m:
            raise HTTPException(404, "Meeting not found")
        items = await db.meeting_sale_items.find({"meeting_id": meeting_id}, {"_id": 0}).to_list(200)
        prop = await db.properties.find_one({"id": m.get("property_id")}, {"_id": 0}) or {}
        property_name = prop.get("name") or m.get("property_id") or "Hotel"
        currency = prop.get("currency") or "GBP"
        sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(currency, currency + " ")
        # Compute totals
        subtotal = sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items)
        # Group by kind
        kind_labels = {
            "room_block": "Accommodation", "fnb": "Food & Beverage",
            "av_tech": "Audio-Visual / Tech", "meeting_space": "Meeting Spaces",
            "decor": "Decor & Styling", "misc": "Other",
        }

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=20 * mm, bottomMargin=18 * mm,
            title=f"Event Proposal — {m.get('name')}",
        )
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                            fontSize=18, leading=22, textColor=colors.HexColor("#0c0a09"))
        h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                            fontSize=12, leading=14, textColor=colors.HexColor("#0c0a09"),
                            spaceBefore=8, spaceAfter=4)
        body_st = ParagraphStyle("body", parent=styles["Normal"],
                                 fontSize=10, leading=14, textColor=colors.HexColor("#27272a"))
        small = ParagraphStyle("small", parent=styles["Normal"],
                               fontSize=9, leading=11, textColor=colors.HexColor("#525252"))
        muted = ParagraphStyle("muted", parent=styles["Normal"],
                               fontSize=8, leading=10, textColor=colors.HexColor("#737373"))
        story = []

        # Header
        story.append(Paragraph(f"<b>{property_name.upper()}</b>", h1))
        story.append(Paragraph("EVENT PROPOSAL", small))
        story.append(Spacer(1, 6 * mm))

        # Client + event details box
        hdr_table = Table([
            [Paragraph("<b>PREPARED FOR</b>", small),
             Paragraph("<b>EVENT DETAILS</b>", small)],
            [Paragraph(
                f"{m.get('contact_name') or '—'}<br/>"
                f"{m.get('company') or ''}<br/>"
                f"{m.get('contact_email') or ''}<br/>"
                f"{m.get('contact_phone') or ''}",
                body_st),
             Paragraph(
                f"<b>{m.get('name')}</b><br/>"
                f"Type: {(m.get('event_type') or '').replace('_', ' ').title()}<br/>"
                f"Date: {m.get('event_date')}"
                + (f" → {m.get('end_date')}" if m.get('end_date') else "") + "<br/>"
                f"Guests: {m.get('guests_count', 0)}<br/>"
                f"Rooms: {m.get('rooms_required', 0)}",
                body_st)],
        ], colWidths=[85 * mm, 85 * mm])
        hdr_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f4")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#a8a29e")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6d3d1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(hdr_table)
        story.append(Spacer(1, 6 * mm))

        # Itemised quote — group by kind
        story.append(Paragraph("ITEMISED QUOTE", h2))
        data = [["#", "Item", "Description", "Qty", f"Unit ({sym})", f"Total ({sym})"]]
        idx = 1
        for kind, lbl in kind_labels.items():
            kind_items = [i for i in items if i.get("kind") == kind]
            if not kind_items:
                continue
            # Section header row
            data.append(["", f"{lbl}".upper(), "", "", "", ""])
            for i in kind_items:
                data.append([
                    str(idx),
                    "",
                    i.get("label", ""),
                    f"{i.get('qty', 0):g}",
                    f"{i.get('unit_price', 0):.2f}",
                    f"{i.get('subtotal', i.get('qty', 0) * i.get('unit_price', 0)):.2f}",
                ])
                idx += 1
        # Totals
        vat_rate = 0.20
        vat = round(subtotal * vat_rate, 2)
        grand = round(subtotal + vat, 2)
        data.append(["", "", "", "", "Subtotal", f"{subtotal:.2f}"])
        data.append(["", "", "", "", "VAT (20%)", f"{vat:.2f}"])
        data.append(["", "", "", "", "TOTAL", f"{grand:.2f}"])

        col_widths = [10 * mm, 36 * mm, 56 * mm, 16 * mm, 24 * mm, 28 * mm]
        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        # Find row indices of section headers (label in col 1, no qty/price)
        section_rows = [r for r, row in enumerate(data) if row[1] and not row[0] and not row[4]]
        styles_list = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0c0a09")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -4), 0.25, colors.HexColor("#d6d3d1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            # Totals block
            ("FONTNAME", (4, -3), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE", (4, -3), (-1, -3), 0.5, colors.HexColor("#a8a29e")),
            ("BACKGROUND", (4, -1), (-1, -1), colors.HexColor("#dcfce7")),
            ("FONTSIZE", (4, -1), (-1, -1), 11),
            ("TEXTCOLOR", (4, -1), (-1, -1), colors.HexColor("#166534")),
        ]
        for sr in section_rows:
            styles_list.append(("BACKGROUND", (0, sr), (-1, sr), colors.HexColor("#fafaf9")))
            styles_list.append(("FONTNAME", (0, sr), (-1, sr), "Helvetica-Bold"))
        tbl.setStyle(TableStyle(styles_list))
        story.append(tbl)
        story.append(Spacer(1, 8 * mm))

        # Terms & conditions
        story.append(Paragraph("TERMS & CONDITIONS", h2))
        story.append(Paragraph(
            "1. <b>Validity</b>: This proposal is valid for 14 days from the issue date.<br/>"
            "2. <b>Deposit</b>: A non-refundable deposit of 30% is required to confirm the booking. "
            "The balance is payable 14 days before the event date.<br/>"
            "3. <b>Cancellation</b>: Cancellations within 30 days of the event are subject to 50% of total. "
            "Within 14 days: 100% of total. Force-majeure exceptions apply.<br/>"
            "4. <b>Final numbers</b>: Final guest count must be confirmed 7 days prior to the event. "
            "Charges will be based on the confirmed number or actual attendance, whichever is higher.<br/>"
            "5. <b>Menu changes</b>: Menu adjustments are accepted up to 14 days prior. "
            "Dietary requirements must be communicated 7 days in advance.<br/>"
            "6. <b>VAT</b>: Prices include 20% VAT where applicable. Service charge not included.",
            small))
        story.append(Spacer(1, 8 * mm))

        # Signature
        sig_table = Table([
            [Paragraph("<b>PROPOSED BY</b>", small),
             "",
             Paragraph("<b>ACCEPTED BY (CLIENT)</b>", small)],
            ["", "", ""],
            ["_______________________________________", "",
             "_______________________________________"],
            [Paragraph(
                f"{current_user.get('name', '-')}<br/>"
                f"{property_name}<br/>"
                f"Date: {datetime.now(timezone.utc).strftime('%d %b %Y')}",
                small),
             "",
             Paragraph("Name: __________________________<br/>"
                       "Signature & Date: __________________", small)],
        ], colWidths=[78 * mm, 14 * mm, 78 * mm], rowHeights=[6*mm, 16*mm, 6*mm, 18*mm])
        sig_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(sig_table)
        story.append(Spacer(1, 6 * mm))

        # Footer
        story.append(Paragraph(
            f"Proposal ref: {meeting_id[:8]} · Issued {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M')} UTC · "
            f"{property_name}", muted))

        doc.build(story)
        buf.seek(0)
        safe_name = "".join(c if c.isalnum() else "_" for c in (m.get("name") or "proposal"))[:30]
        filename = f"proposal_{safe_name}_{meeting_id[:8]}.pdf"
        # Auto-advance stage if currently 'inquiry' or 'site_visit' — PDF generation implies a proposal went out
        if m.get("stage") in ("inquiry", "site_visit"):
            history = m.get("stage_history", [])
            history.append({"stage": "proposal_sent",
                            "at": datetime.now(timezone.utc).isoformat(),
                            "by": current_user.get("name", "")})
            await db.meeting_sales.update_one(
                {"id": meeting_id},
                {"$set": {"stage": "proposal_sent", "stage_history": history,
                          "proposal_sent_at": datetime.now(timezone.utc).isoformat()}}
            )
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return router
