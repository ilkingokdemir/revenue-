"""
PDF Invoice Generation, Enhanced Dashboard KPIs, Guest Profile Timeline
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
from typing import Dict
from collections import defaultdict
import uuid
import io
import logging

logger = logging.getLogger(__name__)


def create_enhanced_features_router(db, require_roles):
    router = APIRouter()

    # ==================== PDF INVOICE GENERATION ====================

    @router.get("/accounting/invoices/{invoice_id}/pdf")
    async def generate_invoice_pdf(invoice_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        inv = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")

        ts = await db.template_settings.find_one({"property_id": inv.get("property_id", "")}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name", inv.get("property_id", "Hotel"))
        hotel_address = ts.get("address", "")
        hotel_phone = ts.get("phone", "")
        hotel_email = ts.get("email", "")

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('InvTitle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#1e293b'), spaceAfter=4)
        subtitle_style = ParagraphStyle('InvSub', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#64748b'))
        header_style = ParagraphStyle('InvHeader', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#334155'), spaceBefore=16, spaceAfter=8)

        elements = []

        # Header
        elements.append(Paragraph(hotel_name, title_style))
        if hotel_address:
            elements.append(Paragraph(hotel_address, subtitle_style))
        details = []
        if hotel_phone:
            details.append(hotel_phone)
        if hotel_email:
            details.append(hotel_email)
        if details:
            elements.append(Paragraph(" | ".join(details), subtitle_style))
        elements.append(Spacer(1, 10*mm))

        # Invoice Details
        inv_type_label = "INVOICE" if inv.get("invoice_type") == "receivable" else "PURCHASE INVOICE"
        elements.append(Paragraph(inv_type_label, ParagraphStyle('InvType', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#4f46e5'))))
        elements.append(Spacer(1, 4*mm))

        info_data = [
            ["Invoice Number:", inv.get("invoice_number", ""), "Date:", inv.get("created_at", "")[:10]],
            ["Bill To:", inv.get("counterparty", ""), "Due Date:", inv.get("due_date", "")],
            ["Status:", inv.get("status", "pending").upper(), "Currency:", inv.get("currency", "GBP")],
        ]
        info_table = Table(info_data, colWidths=[80, 170, 70, 150])
        info_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#64748b')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#64748b')),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 8*mm))

        # Items Table
        elements.append(Paragraph("Line Items", header_style))
        items = inv.get("items", [])
        table_data = [["Description", "Qty", "Unit Price", "VAT %", "VAT", "Total"]]
        for item in items:
            qty = item.get("quantity", 1)
            price = item.get("unit_price", 0)
            vat_rate = item.get("vat_rate", 20)
            line_total = round(qty * price, 2)
            line_vat = round(line_total * vat_rate / 100, 2)
            table_data.append([
                item.get("description", ""),
                str(qty),
                f"£{price:,.2f}",
                f"{vat_rate}%",
                f"£{line_vat:,.2f}",
                f"£{line_total:,.2f}",
            ])

        items_table = Table(table_data, colWidths=[180, 40, 80, 50, 60, 80])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 6*mm))

        # Totals
        subtotal = inv.get("subtotal", 0)
        vat_amount = inv.get("vat_amount", 0)
        total = inv.get("total", 0)
        paid = inv.get("amount_paid", 0) or 0
        balance = round(total - paid, 2)

        totals_data = [
            ["", "", "", "", "Subtotal:", f"£{subtotal:,.2f}"],
            ["", "", "", "", "VAT:", f"£{vat_amount:,.2f}"],
            ["", "", "", "", "Total:", f"£{total:,.2f}"],
        ]
        if paid > 0:
            totals_data.append(["", "", "", "", "Paid:", f"£{paid:,.2f}"])
            totals_data.append(["", "", "", "", "Balance Due:", f"£{balance:,.2f}"])

        totals_table = Table(totals_data, colWidths=[180, 40, 80, 50, 60, 80])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (4, 0), (4, -1), colors.HexColor('#64748b')),
            ('FONTNAME', (5, -1), (5, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (5, -1), (5, -1), 11),
            ('LINEABOVE', (4, -1), (-1, -1), 1, colors.HexColor('#334155')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(totals_table)
        elements.append(Spacer(1, 15*mm))

        # Footer
        elements.append(Paragraph("Thank you for your business.", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748b'), alignment=1)))
        elements.append(Paragraph(f"Generated by {hotel_name} • MyHotelBox", ParagraphStyle('FooterSmall', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#94a3b8'), alignment=1)))

        doc.build(elements)
        buffer.seek(0)

        filename = f"{inv.get('invoice_number', 'invoice')}.pdf"
        return StreamingResponse(buffer, media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment; filename={filename}"})

    # ==================== ENHANCED DASHBOARD KPIS ====================

    @router.get("/dashboard/financial-kpis/{property_id}")
    async def financial_kpis(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Financial KPIs for dashboard: RevPAR, ADR, Occupancy, NPS, AR Outstanding"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month = datetime.now(timezone.utc).strftime("%Y-%m")

        # Total rooms
        total_rooms = 0
        if property_id != "all":
            rts = await db.room_types.find({"property_id": property_id}, {"_id": 0, "total_rooms": 1}).to_list(100)
            total_rooms = sum(rt.get("total_rooms", 0) for rt in rts)
        else:
            rts = await db.room_types.find({}, {"_id": 0, "total_rooms": 1}).to_list(500)
            total_rooms = sum(rt.get("total_rooms", 0) for rt in rts)

        # Month bookings
        bk_filter = {"status": {"$ne": "cancelled"}, "created_at": {"$regex": f"^{month}"}}
        if property_id != "all":
            bk_filter["property_id"] = property_id
        month_bookings = await db.bookings.find(bk_filter, {"_id": 0}).to_list(1000)
        month_revenue = sum(b.get("total_price", 0) for b in month_bookings)
        room_nights = sum(max(1, (datetime.strptime(b.get("check_out", today), "%Y-%m-%d") - datetime.strptime(b.get("check_in", today), "%Y-%m-%d")).days) for b in month_bookings if b.get("check_in") and b.get("check_out"))

        # Days in month so far
        day_of_month = int(today.split("-")[2])
        available_room_nights = total_rooms * day_of_month if total_rooms else 1

        # ADR (Average Daily Rate)
        adr = round(month_revenue / room_nights, 2) if room_nights else 0

        # RevPAR (Revenue Per Available Room)
        revpar = round(month_revenue / available_room_nights, 2) if available_room_nights else 0

        # Occupancy
        occupancy = round((room_nights / available_room_nights) * 100, 1) if available_room_nights else 0

        # NPS (latest survey data)
        nps_score = 0
        nps_responses = 0
        prop_filter = {"property_id": property_id} if property_id != "all" else {}
        nps_data = await db.survey_responses.find(prop_filter, {"_id": 0, "nps_score": 1}).to_list(500)
        if nps_data:
            scores = [r["nps_score"] for r in nps_data]
            promoters = sum(1 for s in scores if s >= 9)
            detractors = sum(1 for s in scores if s < 7)
            nps_score = round(((promoters - detractors) / len(scores)) * 100) if scores else 0
            nps_responses = len(scores)

        # AR Outstanding
        ar_total = 0
        inv_filter = {"invoice_type": "receivable", "status": {"$ne": "paid"}}
        if property_id != "all":
            inv_filter["property_id"] = property_id
        async for doc in db.invoices.aggregate([
            {"$match": inv_filter},
            {"$group": {"_id": None, "total": {"$sum": "$total"}}}
        ]):
            ar_total = round(doc["total"], 2)

        # Month expenses
        exp_filter = {"date": {"$regex": f"^{month}"}}
        if property_id != "all":
            exp_filter["property_id"] = property_id
        month_expenses = 0
        async for doc in db.expense_entries.aggregate([
            {"$match": exp_filter},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            month_expenses = round(doc["total"], 2)

        return {
            "month": month,
            "adr": adr,
            "revpar": revpar,
            "occupancy": min(occupancy, 100),
            "month_revenue": round(month_revenue, 2),
            "month_expenses": month_expenses,
            "month_profit": round(month_revenue - month_expenses, 2),
            "nps_score": nps_score,
            "nps_responses": nps_responses,
            "ar_outstanding": ar_total,
            "total_rooms": total_rooms,
            "room_nights_sold": room_nights,
            "month_bookings": len(month_bookings),
        }

    # ==================== GUEST PROFILE TIMELINE ====================

    @router.get("/guests/timeline/{guest_email}")
    async def guest_timeline(guest_email: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Full activity timeline for a guest: bookings, messages, surveys, reviews, payments"""
        timeline = []

        # Bookings
        bookings = await db.bookings.find(
            {"guest_email": guest_email}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        for b in bookings:
            timeline.append({
                "type": "booking",
                "date": b.get("created_at", "")[:10],
                "title": f"Booking {b.get('booking_ref', '')}",
                "subtitle": f"{b.get('check_in', '')} — {b.get('check_out', '')}",
                "detail": f"£{b.get('total_price', 0)} · {b.get('status', '')}",
                "icon": "bed",
                "color": "blue",
            })

        # Conversations
        convs = await db.conversations.find(
            {"guest_email": guest_email}, {"_id": 0}
        ).sort("created_at", -1).to_list(20)
        for c in convs:
            msg_count = await db.messages.count_documents({"conversation_id": c["id"]})
            timeline.append({
                "type": "conversation",
                "date": c.get("created_at", "")[:10],
                "title": f"Chat via {c.get('channel', 'internal')}",
                "subtitle": f"{msg_count} messages · {c.get('status', '')}",
                "detail": c.get("last_message_preview", "")[:60],
                "icon": "chat",
                "color": "green",
            })

        # Survey Responses
        responses = await db.survey_responses.find(
            {"guest_email": guest_email}, {"_id": 0}
        ).sort("created_at", -1).to_list(10)
        for r in responses:
            timeline.append({
                "type": "survey",
                "date": r.get("created_at", "")[:10],
                "title": f"NPS Survey: {r.get('nps_score', 0)}/10",
                "subtitle": r.get("nps_category", ""),
                "detail": (r.get("comment", "") or "")[:60],
                "icon": "star",
                "color": "amber" if r.get("nps_score", 0) < 7 else "emerald",
            })

        # Reviews
        reviews = await db.reviews.find(
            {"$or": [{"guest_email": guest_email}, {"guest_name": {"$regex": guest_email.split("@")[0], "$options": "i"}}]},
            {"_id": 0}
        ).sort("created_at", -1).to_list(10)
        for r in reviews:
            timeline.append({
                "type": "review",
                "date": r.get("created_at", "")[:10] if r.get("created_at") else "",
                "title": f"{r.get('rating', 0)}/5 on {r.get('platform', 'Direct')}",
                "subtitle": r.get("response_status", "pending"),
                "detail": (r.get("review_text", "") or "")[:60],
                "icon": "review",
                "color": "purple" if r.get("rating", 5) >= 4 else "red",
            })

        # Payments
        payments = await db.payments.find(
            {"counterparty": {"$regex": guest_email.split("@")[0], "$options": "i"}},
            {"_id": 0}
        ).sort("date", -1).to_list(20)
        for p in payments:
            timeline.append({
                "type": "payment",
                "date": p.get("date", ""),
                "title": f"Payment {'received' if p.get('payment_type') == 'received' else 'made'}",
                "subtitle": f"£{p.get('amount', 0)} via {p.get('method', 'unknown').replace('_', ' ')}",
                "detail": p.get("reference", ""),
                "icon": "payment",
                "color": "teal",
            })

        # Sort by date descending
        timeline.sort(key=lambda x: x.get("date", ""), reverse=True)

        # Guest profile summary
        profile = await db.guest_profiles.find_one({"email": guest_email}, {"_id": 0})

        return {
            "guest_email": guest_email,
            "profile": profile,
            "timeline": timeline[:50],
            "counts": {
                "bookings": len(bookings),
                "conversations": len(convs),
                "surveys": len(responses),
                "reviews": len(reviews),
                "payments": len(payments),
            }
        }

    return router
