"""
Guest Services — Digital Check-in Registration, Invoice/Folio Management, Scheduled Reports.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import io
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Module-level helpers (so other routers — e.g. bookings.py auto-email on
# checkout — can build & email folio PDFs without duplicating the layout).
# ============================================================================

async def build_folio_pdf_bytes(db, booking_id, sub_folio_id=None):
    """Build the Folio Receipt PDF as bytes. Returns (pdf_bytes, guest_name, guest_email, inv_num, balance, cur_sym).
    Raises HTTPException(404) if booking missing.

    If `sub_folio_id` is provided, only items in that sub-folio are included.
    Use "primary" to render only the Primary (untagged) items."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet

    booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    room_type = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0})
    room = await db.rooms.find_one({"id": booking.get("room_id", "")}, {"_id": 0})
    prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0})
    items = await db.folio_items.find({"booking_id": booking_id}, {"_id": 0}).sort("created_at", 1).to_list(200)

    if not items:
        nights = int(booking.get("nights", 1) or 1)
        rate = float(booking.get("rate_per_night", 0) or 0)
        total = float(booking.get("total_price", 0) or 0) or (rate * nights)
        room_charge = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "charge",
            "category": "room",
            "description": f"Room: {room_type.get('name', 'Room') if room_type else 'Room'} x {nights} night{'s' if nights > 1 else ''}",
            "quantity": nights,
            "unit_price": rate,
            "amount": total,
            "currency": booking.get("currency", "GBP"),
            "created_at": booking.get("created_at", datetime.now(timezone.utc).isoformat()),
            "created_by": "System",
        }
        await db.folio_items.insert_one(dict(room_charge))
        items.append(room_charge)

    # Filter to a specific sub-folio if requested
    sub_folio_name = None
    if sub_folio_id:
        if sub_folio_id == "primary":
            items = [i for i in items if not i.get("sub_folio_id")]
            sub_folio_name = "Primary"
        else:
            sf = await db.sub_folios.find_one({"id": sub_folio_id, "booking_id": booking_id}, {"_id": 0})
            if not sf:
                raise HTTPException(404, "Sub-folio not found")
            items = [i for i in items if i.get("sub_folio_id") == sub_folio_id]
            sub_folio_name = sf["name"]

    charges = sum(i["amount"] for i in items if i.get("type") == "charge")
    payments = sum(i["amount"] for i in items if i.get("type") == "payment")
    adjustments = sum(i["amount"] for i in items if i.get("type") == "adjustment")
    balance = round(charges - payments + adjustments, 2)
    cur_sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(booking.get("currency", "GBP"), "£")
    inv_num = f"FOL-{booking_id[:8].upper()}"
    if sub_folio_name:
        inv_num = f"{inv_num}-{sub_folio_name.upper().replace(' ', '-')[:16]}"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    story = []

    prop_name = prop.get("name", "HOTEL") if prop else "HOTEL"
    story.append(Paragraph(f"<para align='left'><font size='9' color='#78716c'>{prop_name}</font></para>", styles["Normal"]))
    title_suffix = f" · {sub_folio_name}" if sub_folio_name else ""
    story.append(Paragraph(f"<para align='left'><font size='20' color='#1c1917'><b>FOLIO · {inv_num}{title_suffix}</b></font></para>", styles["Normal"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#1c1917"), spaceBefore=4, spaceAfter=10))

    meta = Table([
        ["Guest", booking.get("guest_name", "—"), "Booking", booking.get("booking_ref") or booking_id[:8].upper()],
        ["Check-In", booking.get("check_in", "—"), "Check-Out", booking.get("check_out", "—")],
        ["Room", (room.get("name", "—") if room else "—"), "Room Type", (room_type.get("name", "—") if room_type else "—")],
    ], colWidths=[22 * mm, 60 * mm, 22 * mm, 60 * mm])
    meta.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9), ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#78716c")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#78716c")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta)
    story.append(Spacer(1, 12))

    data = [["Date", "Description", "Qty", "Unit", "Amount"]]
    for it in items:
        dt = (it.get("created_at") or "")[:10]
        amt = it.get("amount", 0)
        prefix = "-" if it.get("type") == "payment" else ("" if it.get("type") == "charge" else "±")
        data.append([dt, it.get("description", ""), str(it.get("quantity") or 1),
                     f"{cur_sym}{it.get('unit_price', 0):.2f}" if it.get("type") == "charge" else "—",
                     f"{prefix}{cur_sym}{amt:.2f}"])
    tbl = Table(data, colWidths=[22 * mm, 85 * mm, 14 * mm, 22 * mm, 27 * mm])
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#78716c")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#1c1917")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e7e5e4")),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 14))

    tot_rows = [["Charges", f"{cur_sym}{charges:.2f}"]]
    if payments:
        tot_rows.append(["Payments", f"-{cur_sym}{payments:.2f}"])
    if adjustments:
        tot_rows.append(["Adjustments", f"{cur_sym}{adjustments:.2f}"])
    tot_rows.append(["BALANCE DUE", f"{cur_sym}{balance:.2f}"])
    tot = Table(tot_rows, colWidths=[140 * mm, 30 * mm])
    tot.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -2), "Helvetica", 10),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 12),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#059669") if balance <= 0 else colors.HexColor("#dc2626")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#1c1917")),
        ("TOPPADDING", (0, -1), (-1, -1), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
    ]))
    story.append(tot)

    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d6d3d1")))
    story.append(Paragraph(
        f"<para align='center'><font size='7' color='#a8a29e'>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · {inv_num} · Thank you for your stay</font></para>",
        styles["Normal"]))
    doc.build(story)

    return buf.getvalue(), (booking.get("guest_name") or "guest"), (booking.get("guest_email") or ""), inv_num, balance, cur_sym


async def send_folio_email(db, resend_lib, booking_id, to_list=None, sent_by="system:checkout-auto"):
    """Build + email the folio PDF to the guest. Returns dict with send status.
    Used by both the /email-document endpoint and the auto-send-on-checkout hook.
    Failures are raised as HTTPException; callers can catch & log."""
    import os
    import base64

    if not resend_lib or not os.environ.get("RESEND_API_KEY"):
        raise HTTPException(503, "Email service not configured")

    pdf_bytes, guest_name, fallback_email, inv_num, balance, cur_sym = await build_folio_pdf_bytes(db, booking_id)

    if not to_list:
        to_list = [fallback_email] if fallback_email else []
    if isinstance(to_list, str):
        to_list = [x.strip() for x in to_list.split(",") if x.strip()]
    to_list = [x for x in (to_list or []) if x]
    if not to_list:
        raise HTTPException(400, "Guest has no email on file")

    bal_line = (
        f"Your outstanding balance is <b>{cur_sym}{balance:.2f}</b>."
        if balance > 0 else "Your account is fully settled. Thank you!"
    )
    body_html = f"""<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;max-width:600px;margin:auto;padding:24px;color:#1f2937;'>
<h2 style='color:#1c1917;margin:0 0 8px 0;'>Folio Receipt · {inv_num}</h2>
<p style='color:#6b7280;font-size:13px;'>Attached: your itemised folio</p>
<div style='font-size:14px;line-height:1.6;'>
Dear {guest_name or 'guest'},<br><br>
Thank you for staying with us. Please find your itemised folio attached.<br>{bal_line}<br><br>
We hope to welcome you back soon.
</div>
<p style='color:#9ca3af;font-size:11px;margin-top:24px;'>This email may contain confidential information — please do not forward.</p>
</div>"""

    sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
    filename = f"folio-{booking_id[:8]}.pdf"

    try:
        resend_lib.Emails.send({
            "from": sender,
            "to": to_list,
            "subject": f"Your folio receipt — {inv_num}",
            "html": body_html,
            "attachments": [{
                "filename": filename,
                "content": base64.b64encode(pdf_bytes).decode(),
            }],
        })
    except Exception as e:
        logger.error(f"send_folio_email failed: {e}")
        raise HTTPException(502, f"Email send failed: {str(e)[:160]}")

    # Audit log
    await db.bookings.update_one(
        {"id": booking_id},
        {"$push": {"email_log": {
            "document_type": "folio",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "sent_by": sent_by,
            "to": to_list,
            "subject": f"Your folio receipt — {inv_num}",
            "filename": filename,
        }}}
    )
    return {"ok": True, "sent_to": to_list, "filename": filename, "inv_num": inv_num}


def create_guest_services_router(db, require_roles, resend_lib=None):
    router = APIRouter()

    # ===========================
    # 1. DIGITAL CHECK-IN / REGISTRATION CARD
    # ===========================

    @router.get("/guest-checkin/{booking_id}")
    async def get_checkin_form(booking_id: str):
        """Public endpoint — guest accesses via link (no auth required)."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        reg = await db.guest_registrations.find_one({"booking_id": booking_id}, {"_id": 0})

        room_type = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0})
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0})

        return {
            "booking": {
                "id": booking["id"],
                "guest_name": booking.get("guest_name", ""),
                "guest_email": booking.get("guest_email", ""),
                "guest_phone": booking.get("guest_phone", ""),
                "check_in": booking.get("check_in", ""),
                "check_out": booking.get("check_out", ""),
                "nights": booking.get("nights", 1),
                "adults": booking.get("adults", 1),
                "children": booking.get("children", 0),
                "room_type": room_type.get("name", "") if room_type else "",
                "status": booking.get("status", ""),
            },
            "property": {
                "name": prop.get("name", "") if prop else "",
                "id": prop.get("id", "") if prop else "",
            },
            "registration": reg,
            "completed": reg is not None and reg.get("status") == "completed",
        }

    @router.post("/guest-checkin/{booking_id}")
    async def submit_checkin(booking_id: str, data: Dict):
        """Public endpoint — guest submits registration form."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        now_iso = datetime.now(timezone.utc).isoformat()
        reg = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "property_id": booking.get("property_id", ""),
            "guest_name": data.get("guest_name", booking.get("guest_name", "")),
            "email": data.get("email", booking.get("guest_email", "")),
            "phone": data.get("phone", booking.get("guest_phone", "")),
            "nationality": data.get("nationality", ""),
            "passport_number": data.get("passport_number", ""),
            "id_type": data.get("id_type", "passport"),
            "id_number": data.get("id_number", ""),
            "date_of_birth": data.get("date_of_birth", ""),
            "address": data.get("address", ""),
            "city": data.get("city", ""),
            "country": data.get("country", ""),
            "postcode": data.get("postcode", ""),
            "emergency_contact_name": data.get("emergency_contact_name", ""),
            "emergency_contact_phone": data.get("emergency_contact_phone", ""),
            "special_requests": data.get("special_requests", ""),
            "arrival_time": data.get("arrival_time", ""),
            "vehicle_reg": data.get("vehicle_reg", ""),
            "signature": data.get("signature", ""),
            "terms_accepted": data.get("terms_accepted", False),
            "marketing_consent": data.get("marketing_consent", False),
            "status": "completed",
            "submitted_at": now_iso,
        }

        await db.guest_registrations.update_one(
            {"booking_id": booking_id}, {"$set": reg}, upsert=True
        )

        # Update booking with registration data
        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "registration_completed": True,
            "registration_at": now_iso,
        }})

        return {"status": "completed", "registration_id": reg["id"]}

    @router.get("/guest-registrations/{property_id}")
    async def list_registrations(property_id: str, limit: int = 50,
                                 current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Admin view — all guest registrations for a property."""
        query = {} if property_id == "all" else {"property_id": property_id}
        regs = await db.guest_registrations.find(query, {"_id": 0}).sort("submitted_at", -1).to_list(limit)
        total = await db.guest_registrations.count_documents(query)
        completed = await db.guest_registrations.count_documents({**query, "status": "completed"})
        return {"registrations": regs, "total": total, "completed": completed}

    @router.post("/guest-checkin/send-link/{booking_id}")
    async def send_checkin_link(booking_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Send check-in link to guest via notification log."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        link = f"/checkin/{booking_id}"
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "type": "info",
            "title": f"Check-in link sent to {booking.get('guest_name', 'Guest')}",
            "message": f"Digital registration link sent for booking {booking_id[:8]}. Check-in: {booking.get('check_in', '')}",
            "category": "guest_checkin",
            "target_user": "", "target_role": "",
            "link_to": link,
            "priority": "normal",
            "read": False,
            "created_by": current_user.get("name", "System"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {"status": "sent", "link": link, "guest_email": booking.get("guest_email", "")}

    # ===========================
    # 2. INVOICE / FOLIO MANAGEMENT
    # ===========================

    @router.get("/folio/{booking_id}")
    async def get_folio(booking_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Get full folio for a booking."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        room_type = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0})
        room = await db.rooms.find_one({"id": booking.get("room_id", "")}, {"_id": 0})
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0})

        # Get folio items (charges + payments)
        items = await db.folio_items.find({"booking_id": booking_id}, {"_id": 0}).sort("created_at", 1).to_list(100)

        # Auto-generate room charge if no items exist
        if not items:
            nights = int(booking.get("nights", 1) or 1)
            rate = float(booking.get("rate_per_night", 0) or 0)
            total = float(booking.get("total_price", 0) or 0)
            if not total and rate:
                total = rate * nights

            room_charge = {
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "type": "charge",
                "category": "room",
                "description": f"Room: {room_type.get('name', 'Room') if room_type else 'Room'} x {nights} night{'s' if nights > 1 else ''}",
                "quantity": nights,
                "unit_price": rate,
                "amount": total,
                "currency": booking.get("currency", "GBP"),
                "created_at": booking.get("created_at", datetime.now(timezone.utc).isoformat()),
                "created_by": "System",
            }
            await db.folio_items.insert_one(dict(room_charge))
            items.append(room_charge)

        total_charges = sum(i["amount"] for i in items if i.get("type") == "charge")
        total_payments = sum(i["amount"] for i in items if i.get("type") == "payment")
        total_adjustments = sum(i["amount"] for i in items if i.get("type") == "adjustment")
        balance = round(total_charges - total_payments + total_adjustments, 2)

        # Invoice number
        inv_num = f"INV-{booking_id[:8].upper()}"

        return {
            "invoice_number": inv_num,
            "booking": {
                "id": booking["id"],
                "guest_name": booking.get("guest_name", ""),
                "guest_email": booking.get("guest_email", ""),
                "check_in": booking.get("check_in", ""),
                "check_out": booking.get("check_out", ""),
                "nights": booking.get("nights", 1),
                "status": booking.get("status", ""),
                "source": booking.get("source", ""),
                "payment_status": booking.get("payment_status", "pending"),
            },
            "property": {
                "name": prop.get("name", "") if prop else "",
                "id": prop.get("id", "") if prop else "",
            },
            "room": {
                "type": room_type.get("name", "") if room_type else "",
                "name": room.get("name", "") if room else "",
                "floor": room.get("floor", "") if room else "",
            },
            "items": items,
            "totals": {
                "charges": round(total_charges, 2),
                "payments": round(total_payments, 2),
                "adjustments": round(total_adjustments, 2),
                "balance_due": balance,
            },
            "currency": booking.get("currency", "GBP"),
        }

    @router.post("/folio/{booking_id}/add-charge")
    async def add_folio_charge(booking_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Add a charge to the folio (minibar, room service, etc)."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        qty = int(data.get("quantity", 1))
        unit = float(data.get("unit_price", 0))
        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "charge",
            "category": data.get("category", "extra"),
            "description": data.get("description", "Additional charge"),
            "quantity": qty,
            "unit_price": unit,
            "amount": round(qty * unit, 2),
            "currency": booking.get("currency", "GBP"),
            "sub_folio_id": data.get("sub_folio_id") or None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.folio_items.insert_one(item)
        item.pop("_id", None)
        return item

    @router.post("/folio/{booking_id}/add-payment")
    async def add_folio_payment(booking_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Record a payment against the folio."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "payment",
            "category": data.get("method", "card"),
            "description": data.get("description", f"Payment ({data.get('method', 'card')})"),
            "quantity": 1,
            "unit_price": float(data.get("amount", 0)),
            "amount": float(data.get("amount", 0)),
            "currency": booking.get("currency", "GBP"),
            "reference": data.get("reference", ""),
            "sub_folio_id": data.get("sub_folio_id") or None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.folio_items.insert_one(item)
        item.pop("_id", None)

        # Update booking payment status
        folio_items = await db.folio_items.find({"booking_id": booking_id}, {"_id": 0}).to_list(100)
        total_charges = sum(i["amount"] for i in folio_items if i.get("type") == "charge")
        total_payments = sum(i["amount"] for i in folio_items if i.get("type") == "payment")
        new_status = "paid" if total_payments >= total_charges else "partial"
        await db.bookings.update_one({"id": booking_id}, {"$set": {"payment_status": new_status}})

        return item

    @router.post("/folio/{booking_id}/adjust")
    async def add_folio_adjustment(booking_id: str, data: Dict,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Add an adjustment (discount, refund, correction)."""
        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "adjustment",
            "category": data.get("reason", "discount"),
            "description": data.get("description", "Adjustment"),
            "quantity": 1,
            "unit_price": float(data.get("amount", 0)),
            "amount": float(data.get("amount", 0)),
            "currency": data.get("currency", "GBP"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.folio_items.insert_one(item)
        item.pop("_id", None)
        return item

    # ===========================
    # 3. SCHEDULED REPORTS
    # ===========================

    @router.get("/scheduled-reports/{property_id}")
    async def get_scheduled_reports(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """List all scheduled report configs."""
        query = {} if property_id == "all" else {"property_id": property_id}
        reports = await db.scheduled_reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"reports": reports}

    @router.post("/scheduled-reports/{property_id}")
    async def create_scheduled_report(property_id: str, data: Dict,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Create a new scheduled report."""
        now_iso = datetime.now(timezone.utc).isoformat()
        report = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "name": data.get("name", "Daily Report"),
            "type": data.get("type", "daily_summary"),
            "frequency": data.get("frequency", "daily"),
            "time": data.get("time", "08:00"),
            "recipients": data.get("recipients", []),
            "sections": data.get("sections", ["occupancy", "revenue", "arrivals", "departures"]),
            "enabled": data.get("enabled", True),
            "format": data.get("format", "pdf"),
            "created_by": current_user.get("name", ""),
            "created_at": now_iso,
            "last_sent": None,
        }
        await db.scheduled_reports.insert_one(report)
        report.pop("_id", None)
        return report

    @router.put("/scheduled-reports/{property_id}/{report_id}")
    async def update_scheduled_report(property_id: str, report_id: str, data: Dict,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update a scheduled report."""
        update = {k: v for k, v in data.items() if k in [
            "name", "type", "frequency", "time", "recipients", "sections", "enabled", "format"
        ]}
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.scheduled_reports.update_one({"id": report_id}, {"$set": update})
        return {"status": "updated", "id": report_id}

    @router.delete("/scheduled-reports/{property_id}/{report_id}")
    async def delete_scheduled_report(property_id: str, report_id: str,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.scheduled_reports.delete_one({"id": report_id})
        return {"status": "deleted"}

    @router.post("/scheduled-reports/{property_id}/generate-now/{report_id}")
    async def generate_report_now(property_id: str, report_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate and return a report preview immediately."""
        report_config = await db.scheduled_reports.find_one({"id": report_id}, {"_id": 0})
        if not report_config:
            raise HTTPException(status_code=404, detail="Report not found")

        report_data = await _generate_report_data(db, property_id, report_config)

        await db.scheduled_reports.update_one(
            {"id": report_id},
            {"$set": {"last_sent": datetime.now(timezone.utc).isoformat()}}
        )

        return report_data

    @router.post("/scheduled-reports/{property_id}/preview")
    async def preview_report(property_id: str, data: Dict = {},
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate a quick preview with default sections."""
        config = {
            "type": data.get("type", "daily_summary"),
            "sections": data.get("sections", ["occupancy", "revenue", "arrivals", "departures", "housekeeping"]),
        }
        return await _generate_report_data(db, property_id, config)

    # ===========================
    # 3. PRINTABLE PDFs — Registration Card + Folio Receipt (+ Email)
    # (Competitor parity: Mews/Cloudbeds/Eviivo — reg card legally required in EU/UK)
    # ===========================

    def _build_simple_pdf(title, property_name, sections):
        """Build a simple key/value PDF (used by reg card). Returns bytes."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=18 * mm, rightMargin=18 * mm,
                                topMargin=16 * mm, bottomMargin=16 * mm)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph(
            f"<para align='left'><font size='9' color='#78716c'>{property_name or 'HOTEL'}</font></para>",
            styles["Normal"]))
        story.append(Paragraph(
            f"<para align='left'><font size='20' color='#1c1917'><b>{title}</b></font></para>",
            styles["Normal"]))
        story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#1c1917"),
                                spaceBefore=4, spaceAfter=10))
        for heading, rows in sections:
            if heading:
                story.append(Paragraph(
                    f"<para><font size='9' color='#a8a29e'><b>{heading.upper()}</b></font></para>",
                    styles["Normal"]))
                story.append(Spacer(1, 3))
            if rows:
                tbl = Table(rows, colWidths=[50 * mm, 110 * mm])
                tbl.setStyle(TableStyle([
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#57534e")),
                    ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1c1917")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#e7e5e4")),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 10))
        story.append(Spacer(1, 16))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d6d3d1")))
        story.append(Paragraph(
            f"<para align='center'><font size='7' color='#a8a29e'>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · Powered by My Hotel Box</font></para>",
            styles["Normal"]))
        doc.build(story)
        return buf.getvalue()

    async def _reg_card_bytes(booking_id):
        """Build the Registration Card PDF as bytes. Raises 404 if booking missing."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        reg = await db.guest_registrations.find_one({"booking_id": booking_id}, {"_id": 0}) or {}
        room_type = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0})
        room = await db.rooms.find_one({"id": booking.get("room_id", "")}, {"_id": 0})
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0})

        def _v(*keys):
            for k in keys:
                val = reg.get(k) or booking.get(k)
                if val:
                    return str(val)
            return "—"

        sections = [
            ("Booking", [
                ["Booking Ref", booking.get("booking_ref") or booking.get("id", "")[:8].upper()],
                ["Status", booking.get("status", "—").replace("_", " ").title()],
                ["Source", booking.get("source", "Direct")],
            ]),
            ("Guest", [
                ["Full Name", _v("guest_name")],
                ["Email", _v("email", "guest_email")],
                ["Phone", _v("phone", "guest_phone")],
                ["Nationality", reg.get("nationality", "—") or "—"],
                ["Date of Birth", reg.get("date_of_birth", "—") or "—"],
                ["ID Type / Number",
                 f"{(reg.get('id_type') or 'Passport').title()} — {reg.get('id_number') or reg.get('passport_number') or '—'}"],
                ["Address",
                 ", ".join(filter(None, [reg.get("address", ""), reg.get("city", ""),
                                         reg.get("postcode", ""), reg.get("country", "")])) or "—"],
            ]),
            ("Stay", [
                ["Check-In", booking.get("check_in", "—")],
                ["Check-Out", booking.get("check_out", "—")],
                ["Nights", str(booking.get("nights", 1))],
                ["Guests", f"{booking.get('adults', 1)} adult(s)" + (f", {booking.get('children', 0)} child(ren)" if booking.get("children") else "")],
                ["Room Type", room_type.get("name", "—") if room_type else "—"],
                ["Room", room.get("name", "—") if room else "—"],
                ["Arrival Time", reg.get("arrival_time", "—") or "—"],
                ["Vehicle Reg", reg.get("vehicle_reg", "—") or "—"],
            ]),
            ("Emergency Contact", [
                ["Name", reg.get("emergency_contact_name", "—") or "—"],
                ["Phone", reg.get("emergency_contact_phone", "—") or "—"],
            ]),
        ]
        pdf_bytes = _build_simple_pdf(
            title="GUEST REGISTRATION CARD",
            property_name=prop.get("name", "") if prop else "",
            sections=sections,
        )
        guest_email = _v("email", "guest_email")
        return pdf_bytes, (booking.get("guest_name") or "guest"), guest_email

    async def _folio_bytes(booking_id):
        """Delegates to module-level helper for DRY."""
        return await build_folio_pdf_bytes(db, booking_id)

    @router.get("/bookings/{booking_id}/registration-card.pdf")
    async def registration_card_pdf(
        booking_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Printable guest Registration Card PDF (legal requirement in EU/UK/TR)."""
        pdf_bytes, _name, _email = await _reg_card_bytes(booking_id)
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="reg-card-{booking_id[:8]}.pdf"'},
        )

    @router.get("/folio/{booking_id}/pdf")
    async def folio_pdf(
        booking_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Printable Folio receipt PDF (itemised stay invoice)."""
        pdf_bytes, _name, _email, _inv, _bal, _cur = await _folio_bytes(booking_id)
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="folio-{booking_id[:8]}.pdf"'},
        )

    # -------- Email the PDF to the guest (Resend) --------
    @router.post("/bookings/{booking_id}/email-document")
    async def email_document(
        booking_id: str,
        data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Email the Registration Card or Folio Receipt PDF to the guest (or custom recipient).

        Body: { "document_type": "reg_card" | "folio", "to"?: "a@b.com" | ["a@b.com"], "subject"?, "message"? }
        """
        import os
        import base64

        if not resend_lib or not os.environ.get("RESEND_API_KEY"):
            raise HTTPException(503, "Email service not configured")

        doc_type = (data.get("document_type") or "").strip()
        if doc_type not in ("reg_card", "folio"):
            raise HTTPException(400, "document_type must be 'reg_card' or 'folio'")

        # Build the requested PDF
        if doc_type == "reg_card":
            pdf_bytes, guest_name, fallback_email = await _reg_card_bytes(booking_id)
            label = "Registration Card"
            filename = f"reg-card-{booking_id[:8]}.pdf"
            default_subject = f"Your registration card — booking {booking_id[:8].upper()}"
            default_message = (
                "Dear guest,<br><br>"
                "Please find your registration card attached. Kindly review, sign, "
                "and keep a copy for your records.<br><br>We look forward to your stay."
            )
        else:
            pdf_bytes, guest_name, fallback_email, inv_num, balance, cur_sym = await _folio_bytes(booking_id)
            label = "Folio Receipt"
            filename = f"folio-{booking_id[:8]}.pdf"
            default_subject = f"Your folio receipt — {inv_num}"
            bal_line = (
                f"Your outstanding balance is <b>{cur_sym}{balance:.2f}</b>."
                if balance > 0 else "Your account is fully settled. Thank you!"
            )
            default_message = (
                f"Dear {guest_name or 'guest'},<br><br>"
                f"Please find your itemised folio attached.<br>{bal_line}<br><br>"
                "Thank you for choosing us — we hope to welcome you again soon."
            )

        # Recipients
        raw_to = data.get("to") or fallback_email
        if isinstance(raw_to, str):
            to_list = [x.strip() for x in raw_to.split(",") if x.strip()]
        elif isinstance(raw_to, list):
            to_list = [x for x in raw_to if x]
        else:
            to_list = []
        if not to_list:
            raise HTTPException(400, "Guest has no email on file — please supply 'to'")

        subject = (data.get("subject") or default_subject).strip()
        message = (data.get("message") or default_message).strip()
        sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

        body_html = f"""<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;max-width:600px;margin:auto;padding:24px;color:#1f2937;'>
<h2 style='color:#1c1917;margin:0 0 8px 0;'>{label}</h2>
<p style='color:#6b7280;font-size:13px;'>Sent by {current_user.get('name', 'Reception')} · 1 attachment</p>
<div style='font-size:14px;line-height:1.6;'>{message}</div>
<p style='color:#9ca3af;font-size:11px;margin-top:24px;'>This email may contain confidential information — please do not forward.</p>
</div>"""

        try:
            resend_lib.Emails.send({
                "from": sender,
                "to": to_list,
                "subject": subject,
                "html": body_html,
                "attachments": [{
                    "filename": filename,
                    "content": base64.b64encode(pdf_bytes).decode(),
                }],
            })
        except Exception as e:
            logger.error(f"Resend email failed: {e}")
            raise HTTPException(502, f"Email send failed: {str(e)[:160]}")

        # Audit log on the booking
        await db.bookings.update_one(
            {"id": booking_id},
            {"$push": {"email_log": {
                "document_type": doc_type,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_by": current_user.get("name", current_user.get("email", "")),
                "to": to_list,
                "subject": subject,
                "filename": filename,
            }}}
        )
        return {"ok": True, "sent_to": to_list, "document_type": doc_type, "filename": filename}

    # ============================================================================
    # 4. SPLIT FOLIO / SUB-FOLIOS
    # (Mews/Cloudbeds parity) Multiple sub-folios per booking — business traveller
    # pays room on company card, personal extras on personal card, etc.
    # Each folio_item can be tagged with `sub_folio_id`; no tag = "Primary".
    # ============================================================================

    @router.get("/folio/{booking_id}/sub-folios")
    async def list_sub_folios(
        booking_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """List all sub-folios for a booking (always includes 'Primary' virtual).

        Returns each sub-folio with its items + running balance so the UI can
        show tabs with per-folio totals at a glance."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        subs = await db.sub_folios.find({"booking_id": booking_id}, {"_id": 0}).sort("created_at", 1).to_list(50)
        # Always include virtual "Primary" first
        result = [{"id": "primary", "booking_id": booking_id, "name": "Primary",
                   "created_at": booking.get("created_at", ""), "is_default": True}]
        result.extend(subs)

        items = await db.folio_items.find({"booking_id": booking_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
        cur_sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(booking.get("currency", "GBP"), "£")

        for sf in result:
            sf_items = [i for i in items
                        if (i.get("sub_folio_id") or "primary") == sf["id"]]
            charges = sum(i["amount"] for i in sf_items if i.get("type") == "charge")
            payments = sum(i["amount"] for i in sf_items if i.get("type") == "payment")
            adjustments = sum(i["amount"] for i in sf_items if i.get("type") == "adjustment")
            sf["items"] = sf_items
            sf["totals"] = {
                "charges": round(charges, 2),
                "payments": round(payments, 2),
                "adjustments": round(adjustments, 2),
                "balance": round(charges - payments + adjustments, 2),
            }
            sf["currency_symbol"] = cur_sym
            sf["item_count"] = len(sf_items)

        return {"booking_id": booking_id, "sub_folios": result,
                "currency_symbol": cur_sym, "currency": booking.get("currency", "GBP")}

    @router.post("/folio/{booking_id}/sub-folios")
    async def create_sub_folio(
        booking_id: str, data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Create a new sub-folio (e.g., 'Company Card', 'Personal', 'Guest 2')."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "Name required")
        if name.lower() == "primary":
            raise HTTPException(400, "'Primary' is reserved — pick another name")

        doc = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "name": name,
            "notes": data.get("notes", ""),
            "payer_name": data.get("payer_name", ""),
            "payer_email": data.get("payer_email", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.sub_folios.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/folio/{booking_id}/sub-folios/{sub_folio_id}")
    async def update_sub_folio(
        booking_id: str, sub_folio_id: str, data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        if sub_folio_id == "primary":
            raise HTTPException(400, "Primary folio cannot be renamed")
        update = {k: v for k, v in data.items()
                  if k in ("name", "notes", "payer_name", "payer_email")}
        if not update:
            raise HTTPException(400, "No updatable fields")
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.sub_folios.update_one({"id": sub_folio_id, "booking_id": booking_id},
                                            {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Sub-folio not found")
        return {"updated": True, "id": sub_folio_id}

    @router.delete("/folio/{booking_id}/sub-folios/{sub_folio_id}")
    async def delete_sub_folio(
        booking_id: str, sub_folio_id: str,
        move_items_to: str = "primary",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Delete a sub-folio. Items in it are moved to `move_items_to` (default: primary)."""
        if sub_folio_id == "primary":
            raise HTTPException(400, "Cannot delete Primary folio")
        sf = await db.sub_folios.find_one({"id": sub_folio_id, "booking_id": booking_id}, {"_id": 0})
        if not sf:
            raise HTTPException(404, "Sub-folio not found")

        # Move items
        target = None if move_items_to == "primary" else move_items_to
        if target and target != sub_folio_id:
            # Validate target exists
            t_exists = await db.sub_folios.find_one({"id": target, "booking_id": booking_id}, {"_id": 0})
            if not t_exists:
                raise HTTPException(404, "Target sub-folio not found")
        await db.folio_items.update_many(
            {"booking_id": booking_id, "sub_folio_id": sub_folio_id},
            {"$set": {"sub_folio_id": target}} if target else {"$unset": {"sub_folio_id": ""}},
        )
        await db.sub_folios.delete_one({"id": sub_folio_id, "booking_id": booking_id})
        return {"deleted": True, "moved_to": target or "primary"}

    @router.put("/folio/items/{item_id}/move")
    async def move_folio_item(
        item_id: str, data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Move a folio item (charge / payment / adjustment) to a different sub-folio."""
        item = await db.folio_items.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Item not found")
        target = data.get("sub_folio_id") or ""
        if target == "primary" or not target:
            await db.folio_items.update_one({"id": item_id}, {"$unset": {"sub_folio_id": ""}})
            return {"ok": True, "moved_to": "primary"}
        # Validate target
        t = await db.sub_folios.find_one({"id": target, "booking_id": item["booking_id"]}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Target sub-folio not found")
        await db.folio_items.update_one({"id": item_id}, {"$set": {"sub_folio_id": target}})
        return {"ok": True, "moved_to": target}

    @router.get("/folio/{booking_id}/sub-folios/{sub_folio_id}/pdf")
    async def sub_folio_pdf(
        booking_id: str, sub_folio_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Print only the items in a specific sub-folio (primary or any named one)."""
        pdf_bytes, _name, _email, inv_num, _bal, _cur = await build_folio_pdf_bytes(db, booking_id, sub_folio_id)
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{inv_num}.pdf"'},
        )

    @router.post("/folio/{booking_id}/sub-folios/{sub_folio_id}/email")
    async def email_sub_folio(
        booking_id: str, sub_folio_id: str, data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Email only the items in a specific sub-folio to a user-composed recipient.
        Body: {to, subject, message} — all user-written."""
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

        pdf_bytes, _name, _email, inv_num, _bal, _cur = await build_folio_pdf_bytes(
            db, booking_id, sub_folio_id
        )
        sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

        body_html = (
            "<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;"
            "max-width:640px;margin:auto;padding:24px;color:#1f2937;'>"
            f"<h2 style='color:#1c1917;margin:0 0 8px 0;'>Folio · {inv_num}</h2>"
            f"<p style='color:#6b7280;font-size:13px;'>Sent by {current_user.get('name', 'Reception')}</p>"
            f"<div style='font-size:14px;line-height:1.6;'>{message.replace(chr(10), '<br>')}</div>"
            "<p style='color:#9ca3af;font-size:11px;margin-top:24px;'>A PDF copy of the folio is attached.</p>"
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

        await db.bookings.update_one(
            {"id": booking_id},
            {"$push": {"email_log": {
                "document_type": "sub_folio",
                "sub_folio_id": sub_folio_id,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_by": current_user.get("email", ""),
                "to": to_list,
                "subject": subject,
                "filename": f"{inv_num}.pdf",
            }}}
        )
        return {"ok": True, "sent_to": to_list, "invoice_number": inv_num}

    return router


async def _generate_report_data(db, property_id, config):
    """Generate report data based on config sections."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sections = config.get("sections", [])

    props_query = {} if property_id == "all" else {"id": property_id}
    props = await db.properties.find(props_query, {"_id": 0}).to_list(50)
    prop_ids = [p.get("id", "") for p in props]
    prop_name = props[0].get("name", "Hotel") if props else "Hotel"

    result = {
        "report_type": config.get("type", "daily_summary"),
        "property": prop_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": today,
        "sections": {},
    }

    bk_query = {"status": {"$nin": ["cancelled"]}}
    if property_id != "all":
        bk_query["property_id"] = property_id

    if "occupancy" in sections:
        total_rooms = 0
        for pid in prop_ids:
            total_rooms += await db.rooms.count_documents({"property_id": pid})
        if total_rooms == 0:
            for pid in prop_ids:
                rt_count = await db.room_types.count_documents({"property_id": pid})
                total_rooms += rt_count * 3

        booked_today = await db.bookings.count_documents({
            **bk_query, "check_in": {"$lte": today}, "check_out": {"$gt": today}
        })
        occ = round((booked_today / max(total_rooms, 1)) * 100)
        result["sections"]["occupancy"] = {
            "total_rooms": total_rooms, "booked": booked_today,
            "available": max(0, total_rooms - booked_today), "occupancy_pct": occ,
        }

    if "revenue" in sections:
        bookings = await db.bookings.find(
            {**bk_query, "check_in": {"$lte": today}, "check_out": {"$gt": today}},
            {"_id": 0, "total_price": 1, "rate_per_night": 1}
        ).to_list(500)
        total_rev = sum(float(b.get("rate_per_night", 0) or 0) for b in bookings)
        avg_rate = round(total_rev / max(len(bookings), 1), 2)
        result["sections"]["revenue"] = {
            "todays_revenue": round(total_rev, 2), "avg_daily_rate": avg_rate,
            "bookings_count": len(bookings),
        }

    if "arrivals" in sections:
        arrivals = await db.bookings.find(
            {**bk_query, "check_in": today}, {"_id": 0, "guest_name": 1, "room_type_id": 1, "nights": 1, "status": 1}
        ).to_list(100)
        result["sections"]["arrivals"] = {
            "count": len(arrivals),
            "guests": [{"name": a.get("guest_name", ""), "nights": a.get("nights", 1), "status": a.get("status", "")} for a in arrivals[:20]],
        }

    if "departures" in sections:
        departures = await db.bookings.find(
            {**bk_query, "check_out": today}, {"_id": 0, "guest_name": 1, "status": 1}
        ).to_list(100)
        result["sections"]["departures"] = {
            "count": len(departures),
            "guests": [{"name": d.get("guest_name", ""), "status": d.get("status", "")} for d in departures[:20]],
        }

    if "housekeeping" in sections:
        dirty = await db.rooms.count_documents({"housekeeping": "dirty"})
        clean = await db.rooms.count_documents({"housekeeping": "clean"})
        inspected = await db.rooms.count_documents({"housekeeping": "inspected"})
        result["sections"]["housekeeping"] = {
            "clean": clean, "dirty": dirty, "inspected": inspected,
        }

    return result
