"""
Banquet Event Order (BEO) — auto-generated PDF for conference / banquet events.

A BEO is the canonical document the F&B, banquet, AV, housekeeping and front office
teams use on event day. It is generated from a structured record so it stays in sync
with last-minute changes (vs Word docs that drift).

Optionally linked to a conference proposal (`proposal_id`) so the sales-to-ops
handoff is one click.

Endpoints
---------
GET    /banquet-orders/{property_id}            list (filter by date range, status)
POST   /banquet-orders                          create
GET    /banquet-orders/{id}                     single
PUT    /banquet-orders/{id}                     update
DELETE /banquet-orders/{id}                     remove
GET    /banquet-orders/{id}/pdf                 download PDF

Status: draft | confirmed | completed | cancelled.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional
import io
import uuid

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)


VALID_STATUSES = {"draft", "confirmed", "completed", "cancelled"}
VALID_SETUP_STYLES = {"theatre", "classroom", "u-shape", "boardroom", "banquet", "cabaret", "cocktail", "hollow-square", "custom"}


class MenuCourse(BaseModel):
    name: str                        # e.g. "Starter"
    items: List[str] = []            # ["Tomato bisque", "Garden salad"]
    notes: Optional[str] = None


class BeverageItem(BaseModel):
    name: str
    qty: Optional[str] = None        # "Open bar 18:00-22:00"
    notes: Optional[str] = None


class AvItem(BaseModel):
    name: str                        # "Wireless mic", "LED screen 4x3m"
    qty: int = 1
    notes: Optional[str] = None


class Contact(BaseModel):
    name: str
    role: Optional[str] = None       # "Client", "Banquet captain"
    phone: Optional[str] = None
    email: Optional[str] = None


class BeoCreateReq(BaseModel):
    property_id: str
    proposal_id: Optional[str] = None
    event_name: str
    event_date: str                       # YYYY-MM-DD
    start_time: str                       # HH:MM
    end_time: str                         # HH:MM
    venue_room: str
    guest_count: int = Field(0, ge=0)
    setup_style: str = "banquet"
    menu: List[MenuCourse] = []
    beverages: List[BeverageItem] = []
    av: List[AvItem] = []
    decoration: Optional[str] = None
    special_requests: Optional[str] = None
    billing_instructions: Optional[str] = None
    contacts: List[Contact] = []
    status: str = "draft"
    notes: Optional[str] = None


class BeoUpdateReq(BeoCreateReq):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate(req) -> None:
    if req.status not in VALID_STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(VALID_STATUSES)}")
    if req.setup_style not in VALID_SETUP_STYLES:
        raise HTTPException(400, f"setup_style must be one of {sorted(VALID_SETUP_STYLES)}")


def _render_pdf(doc_data: dict) -> bytes:
    """Return PDF bytes for a BEO."""
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=15 * mm, leftMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#1c1917"), spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#3f3f46"), spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, textColor=colors.HexColor("#27272a"), leading=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.HexColor("#6b7280"))

    elements = []
    # Header
    elements.append(Paragraph("<b>BANQUET EVENT ORDER</b>", h1))
    elements.append(Paragraph(f"BEO #{doc_data.get('ref', doc_data['id'][:8])} · Status: <b>{doc_data['status'].upper()}</b>",
                              small))
    elements.append(Spacer(1, 6))

    # Event summary table
    summary_rows = [
        ["Event", doc_data.get("event_name", "")],
        ["Date", f"{doc_data.get('event_date','')} · {doc_data.get('start_time','')} → {doc_data.get('end_time','')}"],
        ["Venue", doc_data.get("venue_room", "")],
        ["Setup", doc_data.get("setup_style", "")],
        ["Guests", str(doc_data.get("guest_count", 0))],
    ]
    if doc_data.get("proposal_id"):
        summary_rows.append(["Proposal Ref", doc_data["proposal_id"][:8]])
    summary = Table(summary_rows, colWidths=[35 * mm, 130 * mm])
    summary.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#71717a")),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e4e4e7")),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(summary)

    # ----- F&B MENU -----
    if doc_data.get("menu"):
        elements.append(Paragraph("F&amp;B MENU", h2))
        for course in doc_data["menu"]:
            elements.append(Paragraph(f"<b>{course.get('name','')}</b>", body))
            for it in course.get("items", []):
                elements.append(Paragraph(f"&nbsp;&nbsp;• {it}", body))
            if course.get("notes"):
                elements.append(Paragraph(f"<i>Note: {course['notes']}</i>", small))

    # ----- BEVERAGES -----
    if doc_data.get("beverages"):
        elements.append(Paragraph("BEVERAGES", h2))
        bev_rows = [["Item", "Qty / Window", "Notes"]]
        for b in doc_data["beverages"]:
            bev_rows.append([b.get("name",""), b.get("qty","") or "—", b.get("notes","") or ""])
        bev = Table(bev_rows, colWidths=[60*mm, 50*mm, 55*mm])
        bev.setStyle(_grid_style())
        elements.append(bev)

    # ----- AV / EQUIPMENT -----
    if doc_data.get("av"):
        elements.append(Paragraph("AV &amp; EQUIPMENT", h2))
        av_rows = [["Item", "Qty", "Notes"]]
        for a in doc_data["av"]:
            av_rows.append([a.get("name",""), str(a.get("qty",1)), a.get("notes","") or ""])
        av = Table(av_rows, colWidths=[80*mm, 20*mm, 65*mm])
        av.setStyle(_grid_style())
        elements.append(av)

    # ----- DECORATION & SPECIAL REQUESTS -----
    if doc_data.get("decoration") or doc_data.get("special_requests"):
        elements.append(Paragraph("DECORATION &amp; SPECIAL REQUESTS", h2))
        if doc_data.get("decoration"):
            elements.append(Paragraph(f"<b>Decoration:</b> {doc_data['decoration']}", body))
        if doc_data.get("special_requests"):
            elements.append(Paragraph(f"<b>Special:</b> {doc_data['special_requests']}", body))

    # ----- BILLING -----
    if doc_data.get("billing_instructions"):
        elements.append(Paragraph("BILLING", h2))
        elements.append(Paragraph(doc_data["billing_instructions"], body))

    # ----- CONTACTS -----
    if doc_data.get("contacts"):
        elements.append(Paragraph("KEY CONTACTS", h2))
        c_rows = [["Name", "Role", "Phone", "Email"]]
        for c in doc_data["contacts"]:
            c_rows.append([c.get("name",""), c.get("role","") or "", c.get("phone","") or "", c.get("email","") or ""])
        ct = Table(c_rows, colWidths=[40*mm, 35*mm, 35*mm, 55*mm])
        ct.setStyle(_grid_style())
        elements.append(ct)

    # ----- FOOTER NOTES -----
    if doc_data.get("notes"):
        elements.append(Paragraph("OPS NOTES", h2))
        elements.append(Paragraph(doc_data["notes"], body))

    elements.append(Spacer(1, 12))
    elements.append(Paragraph(
        f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"BEO ID {doc_data['id']} · property {doc_data['property_id']}",
        small,
    ))

    pdf.build(elements)
    return buf.getvalue()


def _grid_style() -> TableStyle:
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#3f3f46")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#a1a1aa")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e4e4e7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])


def create_banquet_orders_router(db, require_roles):
    router = APIRouter()

    @router.get("/banquet-orders/{property_id}")
    async def list_beos(property_id: str,
                        from_date: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
                        to_date: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
                        status: Optional[str] = None,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q = {"property_id": property_id}
        if from_date or to_date:
            q["event_date"] = {}
            if from_date:
                q["event_date"]["$gte"] = from_date
            if to_date:
                q["event_date"]["$lte"] = to_date
        if status:
            if status not in VALID_STATUSES:
                raise HTTPException(400, f"status must be one of {sorted(VALID_STATUSES)}")
            q["status"] = status
        items = await db.banquet_orders.find(q, {"_id": 0}).sort("event_date", 1).to_list(500)
        return {"items": items, "count": len(items)}

    @router.post("/banquet-orders")
    async def create_beo(req: BeoCreateReq,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        _validate(req)
        # Auto-incremented daily ref like BEO-260428-XXXX
        today_ref = datetime.now(timezone.utc).strftime("%y%m%d")
        random_suffix = uuid.uuid4().hex[:4].upper()
        ref = f"BEO-{today_ref}-{random_suffix}"

        doc = req.model_dump()
        doc.update({
            "id": str(uuid.uuid4()),
            "ref": ref,
            "menu": [m for m in doc["menu"]],
            "beverages": [b for b in doc["beverages"]],
            "av": [a for a in doc["av"]],
            "contacts": [c for c in doc["contacts"]],
            "created_at": _now(),
            "created_by": current_user.get("email"),
            "updated_at": _now(),
        })
        await db.banquet_orders.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/banquet-orders/single/{beo_id}")
    async def get_beo(beo_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        beo = await db.banquet_orders.find_one({"id": beo_id}, {"_id": 0})
        if not beo:
            raise HTTPException(404, "not found")
        return beo

    @router.put("/banquet-orders/{beo_id}")
    async def update_beo(beo_id: str, req: BeoUpdateReq,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        _validate(req)
        existing = await db.banquet_orders.find_one({"id": beo_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "not found")
        patch = req.model_dump()
        patch.update({"updated_at": _now(), "updated_by": current_user.get("email")})
        await db.banquet_orders.update_one({"id": beo_id}, {"$set": patch})
        merged = {**existing, **patch}
        merged.pop("_id", None)
        return merged

    @router.delete("/banquet-orders/{beo_id}")
    async def delete_beo(beo_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await db.banquet_orders.delete_one({"id": beo_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "not found")
        return {"deleted": beo_id}

    @router.get("/banquet-orders/{beo_id}/pdf")
    async def generate_pdf(beo_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        beo = await db.banquet_orders.find_one({"id": beo_id}, {"_id": 0})
        if not beo:
            raise HTTPException(404, "not found")
        pdf_bytes = _render_pdf(beo)
        filename = f"{beo.get('ref', beo_id[:8])}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/banquet-orders/dashboard/{property_id}")
    async def dashboard(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        items = await db.banquet_orders.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        upcoming_7d = []
        from datetime import timedelta
        cutoff_7 = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
        counts = {s: 0 for s in VALID_STATUSES}
        for it in items:
            counts[it.get("status", "draft")] = counts.get(it.get("status", "draft"), 0) + 1
            d = it.get("event_date", "")
            if today <= d <= cutoff_7 and it.get("status") in ("draft", "confirmed"):
                upcoming_7d.append(it)
        upcoming_7d.sort(key=lambda x: (x.get("event_date", ""), x.get("start_time", "")))
        total_guests_7d = sum(it.get("guest_count", 0) for it in upcoming_7d)
        return {
            "total": len(items),
            "by_status": counts,
            "upcoming_7d_count": len(upcoming_7d),
            "upcoming_7d_guests": total_guests_7d,
            "upcoming_7d": upcoming_7d[:10],
        }

    return router
