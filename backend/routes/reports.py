"""
Reports Centre — Consolidated PDF/Excel export across all modules
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
from typing import Dict
import io
import csv
import logging

logger = logging.getLogger(__name__)


def create_reports_router(db, require_roles):
    router = APIRouter()

    # ==================== REPORT DATA ====================

    @router.get("/reports/summary/{property_id}")
    async def report_summary(property_id: str, period: str = "month",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get consolidated summary across all modules"""
        query = {} if property_id == "all" else {"property_id": property_id}
        now = datetime.now(timezone.utc)

        if period == "week":
            start = (now - timedelta(days=7)).isoformat()
        elif period == "month":
            start = (now - timedelta(days=30)).isoformat()
        elif period == "quarter":
            start = (now - timedelta(days=90)).isoformat()
        else:
            start = (now - timedelta(days=365)).isoformat()

        date_q = {**query, "created_at": {"$gte": start}}

        # Bookings
        total_bookings = await db.bookings.count_documents({**query})
        confirmed = await db.bookings.count_documents({**query, "status": "confirmed"})
        booking_rev_pipeline = [{"$match": query}, {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$total", 0]}}}}]
        booking_rev = 0
        async for d in db.bookings.aggregate(booking_rev_pipeline):
            booking_rev = d.get("total", 0)

        # Maintenance
        maint_total = await db.maintenance_issues.count_documents(date_q)
        maint_open = await db.maintenance_issues.count_documents({**date_q, "status": {"$in": ["open", "acknowledged", "in_progress"]}})
        maint_resolved = await db.maintenance_issues.count_documents({**date_q, "status": {"$in": ["resolved", "closed"]}})
        maint_overdue = await db.maintenance_issues.count_documents({**date_q, "sla_breached": True})
        maint_cost_pipeline = [{"$match": date_q}, {"$group": {"_id": None, "total": {"$sum": "$actual_cost"}}}]
        maint_cost = 0
        async for d in db.maintenance_issues.aggregate(maint_cost_pipeline):
            maint_cost = d.get("total", 0)

        # Guest Journey
        reg_total = await db.guest_registrations.count_documents(date_q)
        reg_completed = await db.guest_registrations.count_documents({**date_q, "status": "completed"})

        # Satisfaction
        sat_total = await db.satisfaction_checks.count_documents(date_q)
        sat_happy = await db.satisfaction_checks.count_documents({**date_q, "response": "all_good"})
        sat_help = await db.satisfaction_checks.count_documents({**date_q, "response": "need_help"})

        # POS
        pos_pipeline = [{"$match": date_q}, {"$group": {"_id": None, "total": {"$sum": "$total"}, "count": {"$sum": 1}}}]
        pos_rev, pos_count = 0, 0
        async for d in db.pos_orders.aggregate(pos_pipeline):
            pos_rev = d.get("total", 0)
            pos_count = d.get("count", 0)

        # Loyalty
        loyalty_members = await db.loyalty.count_documents(query)

        return {
            "period": period,
            "bookings": {"total": total_bookings, "confirmed": confirmed, "revenue": booking_rev},
            "maintenance": {"total": maint_total, "open": maint_open, "resolved": maint_resolved, "overdue": maint_overdue, "cost": maint_cost},
            "guest_journey": {"registrations": reg_total, "completed": reg_completed, "completion_rate": round((reg_completed / max(reg_total, 1)) * 100, 1)},
            "satisfaction": {"total": sat_total, "happy": sat_happy, "need_help": sat_help, "satisfaction_rate": round((sat_happy / max(sat_total, 1)) * 100, 1)},
            "pos": {"orders": pos_count, "revenue": pos_rev},
            "loyalty": {"members": loyalty_members},
        }

    # ==================== CSV EXPORT ====================

    @router.get("/reports/export/{property_id}/{report_type}")
    async def export_csv(property_id: str, report_type: str, period: str = "month",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """Export report as CSV"""
        query = {} if property_id == "all" else {"property_id": property_id}
        now = datetime.now(timezone.utc)
        if period == "week":
            start = (now - timedelta(days=7)).isoformat()
        elif period == "month":
            start = (now - timedelta(days=30)).isoformat()
        elif period == "quarter":
            start = (now - timedelta(days=90)).isoformat()
        else:
            start = (now - timedelta(days=365)).isoformat()
        date_q = {**query, "created_at": {"$gte": start}}

        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == "bookings":
            writer.writerow(["Booking Ref", "Guest", "Email", "Check-In", "Check-Out", "Rooms", "Room Type", "Total", "Status", "Created"])
            async for doc in db.bookings.find(query, {"_id": 0}).sort("created_at", -1).limit(500):
                writer.writerow([doc.get("booking_ref", ""), doc.get("guest_name", ""), doc.get("guest_email", ""), doc.get("check_in", ""), doc.get("check_out", ""), doc.get("rooms", ""), doc.get("room_type", ""), doc.get("total", 0), doc.get("status", ""), doc.get("created_at", "")])

        elif report_type == "maintenance":
            writer.writerow(["Title", "Category", "Priority", "Status", "Location", "Assigned To", "Reported By", "SLA Hours", "SLA Breached", "Est Cost", "Actual Cost", "Created", "Resolved"])
            async for doc in db.maintenance_issues.find(date_q, {"_id": 0}).sort("created_at", -1).limit(500):
                writer.writerow([doc.get("title", ""), doc.get("category", ""), doc.get("priority", ""), doc.get("status", ""), doc.get("location", ""), doc.get("assigned_to", ""), doc.get("reported_by", ""), doc.get("sla_hours", ""), doc.get("sla_breached", False), doc.get("estimated_cost", 0), doc.get("actual_cost", 0), doc.get("created_at", ""), doc.get("resolved_at", "")])

        elif report_type == "registrations":
            writer.writerow(["Guest", "Email", "Booking Ref", "Status", "ID Uploaded", "Terms Accepted", "Created", "Completed"])
            async for doc in db.guest_registrations.find(date_q, {"_id": 0}).sort("created_at", -1).limit(500):
                writer.writerow([doc.get("guest_name", ""), doc.get("guest_email", ""), doc.get("booking_ref", ""), doc.get("status", ""), doc.get("id_uploaded", False), doc.get("terms_accepted", False), doc.get("created_at", ""), doc.get("completed_at", "")])

        elif report_type == "pos":
            writer.writerow(["Order ID", "Items", "Total", "Payment", "Status", "Created By", "Created"])
            async for doc in db.pos_orders.find(date_q, {"_id": 0}).sort("created_at", -1).limit(500):
                items_str = ", ".join([f"{i.get('name','')} x{i.get('quantity',1)}" for i in doc.get("items", [])])
                writer.writerow([doc.get("id", ""), items_str, doc.get("total", 0), doc.get("payment_method", ""), doc.get("status", ""), doc.get("created_by", ""), doc.get("created_at", "")])

        elif report_type == "satisfaction":
            writer.writerow(["Guest", "Booking Ref", "Response", "Message", "Created"])
            async for doc in db.satisfaction_checks.find(date_q, {"_id": 0}).sort("created_at", -1).limit(500):
                writer.writerow([doc.get("guest_name", ""), doc.get("booking_ref", ""), doc.get("response", ""), doc.get("message", ""), doc.get("created_at", "")])
        else:
            raise HTTPException(400, "Unknown report type")

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={report_type}_{period}_{datetime.now().strftime('%Y%m%d')}.csv"}
        )

    return router
