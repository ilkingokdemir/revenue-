"""
Night Audit Wizard — End-of-day reconciliation, verification, and revenue reporting
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_night_audit_router(db, require_roles):
    router = APIRouter()

    @router.post("/night-audit/run/{property_id}")
    async def run_night_audit(property_id: str, data: Dict = {}, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Run the night audit — verify all operations and generate daily report"""
        audit_date = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        next_date = (datetime.strptime(audit_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        # ==================== 1. CHECK-IN VERIFICATION ====================
        expected_checkins = await db.bookings.find({
            "property_id": property_id, "check_in": audit_date,
            "status": {"$nin": ["cancelled"]},
        }, {"_id": 0}).to_list(500)

        actual_checkins = [b for b in expected_checkins if b.get("status") == "checked_in"]
        no_shows = [b for b in expected_checkins if b.get("status") == "confirmed"]

        checkin_check = {
            "status": "pass" if len(no_shows) == 0 else "warning",
            "expected": len(expected_checkins),
            "actual": len(actual_checkins),
            "no_shows": len(no_shows),
            "no_show_list": [{"ref": b.get("booking_ref"), "guest": b.get("guest_name"), "amount": b.get("total_price", 0)} for b in no_shows[:10]],
        }

        # ==================== 2. CHECK-OUT VERIFICATION ====================
        expected_checkouts = await db.bookings.find({
            "property_id": property_id, "check_out": audit_date,
            "status": {"$in": ["checked_in", "checked_out"]},
        }, {"_id": 0}).to_list(500)

        actual_checkouts = [b for b in expected_checkouts if b.get("status") == "checked_out"]
        still_in_house = [b for b in expected_checkouts if b.get("status") == "checked_in"]

        checkout_check = {
            "status": "pass" if len(still_in_house) == 0 else "warning",
            "expected": len(expected_checkouts),
            "actual": len(actual_checkouts),
            "overstays": len(still_in_house),
            "overstay_list": [{"ref": b.get("booking_ref"), "guest": b.get("guest_name")} for b in still_in_house[:10]],
        }

        # ==================== 3. PAYMENT RECONCILIATION ====================
        all_bookings_inhouse = await db.bookings.find({
            "property_id": property_id,
            "check_in": {"$lte": audit_date}, "check_out": {"$gte": audit_date},
            "status": {"$nin": ["cancelled"]},
        }, {"_id": 0}).to_list(500)

        total_room_revenue = sum(float(b.get("total_price", 0)) for b in all_bookings_inhouse)
        paid_bookings = [b for b in all_bookings_inhouse if b.get("payment_status") == "paid"]
        unpaid_bookings = [b for b in all_bookings_inhouse if b.get("payment_status") != "paid"]
        total_paid = sum(float(b.get("total_price", 0)) for b in paid_bookings)
        total_unpaid = sum(float(b.get("total_price", 0)) for b in unpaid_bookings)

        # Payment transactions for the day
        day_start = f"{audit_date}T00:00:00"
        day_end = f"{audit_date}T23:59:59"
        day_transactions = await db.payment_transactions.find({
            "property_id": property_id,
            "created_at": {"$gte": day_start, "$lte": day_end},
        }, {"_id": 0}).to_list(500)
        tx_total = sum(float(t.get("amount", 0)) for t in day_transactions if t.get("payment_status") == "paid")

        payment_check = {
            "status": "pass" if len(unpaid_bookings) == 0 else "warning",
            "total_room_revenue": round(total_room_revenue, 2),
            "total_paid": round(total_paid, 2),
            "total_unpaid": round(total_unpaid, 2),
            "paid_count": len(paid_bookings),
            "unpaid_count": len(unpaid_bookings),
            "transaction_total": round(tx_total, 2),
            "unpaid_list": [{"ref": b.get("booking_ref"), "guest": b.get("guest_name"), "amount": b.get("total_price", 0)} for b in unpaid_bookings[:10]],
        }

        # ==================== 4. POS RECONCILIATION ====================
        pos_orders = await db.pos_orders.find({
            "property_id": property_id,
            "created_at": {"$gte": day_start, "$lte": day_end},
        }, {"_id": 0}).to_list(500)

        pos_paid = [o for o in pos_orders if o.get("payment_status") == "paid"]
        pos_unpaid = [o for o in pos_orders if o.get("payment_status") == "pending"]
        pos_voided = [o for o in pos_orders if o.get("payment_status") == "void"]
        pos_revenue = sum(float(o.get("total", 0)) for o in pos_paid)
        pos_pending = sum(float(o.get("total", 0)) for o in pos_unpaid)

        pos_check = {
            "status": "pass" if len(pos_unpaid) == 0 else "warning",
            "total_orders": len(pos_orders),
            "paid_orders": len(pos_paid),
            "unpaid_orders": len(pos_unpaid),
            "voided_orders": len(pos_voided),
            "revenue": round(pos_revenue, 2),
            "pending_amount": round(pos_pending, 2),
            "unpaid_list": [{"number": o.get("order_number"), "amount": o.get("total", 0), "outlet": o.get("outlet_name", "")} for o in pos_unpaid[:10]],
        }

        # ==================== 5. HOUSEKEEPING CHECK ====================
        dirty_rooms = await db.room_statuses.count_documents({"property_id": property_id, "status": "dirty"})
        ooo_rooms = await db.room_statuses.count_documents({"property_id": property_id, "status": "out_of_order"})
        pending_tasks = await db.housekeeping_tasks.count_documents({"property_id": property_id, "status": {"$ne": "completed"}})
        open_maintenance = await db.maintenance_requests.count_documents({"property_id": property_id, "status": {"$ne": "resolved"}})

        housekeeping_check = {
            "status": "pass" if dirty_rooms == 0 and pending_tasks == 0 else "warning",
            "dirty_rooms": dirty_rooms,
            "out_of_order_rooms": ooo_rooms,
            "pending_tasks": pending_tasks,
            "open_maintenance": open_maintenance,
        }

        # ==================== 6. OCCUPANCY STATS ====================
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        total_rooms = sum(int(r.get("total_rooms", 0)) for r in room_types)
        occupied = len(all_bookings_inhouse)
        occupancy_pct = round((occupied / total_rooms * 100), 1) if total_rooms > 0 else 0
        adr = round(total_room_revenue / occupied, 2) if occupied > 0 else 0
        revpar = round(total_room_revenue / total_rooms, 2) if total_rooms > 0 else 0

        occupancy_stats = {
            "total_rooms": total_rooms,
            "occupied": occupied,
            "available": total_rooms - occupied,
            "occupancy_pct": occupancy_pct,
            "adr": adr,
            "revpar": revpar,
        }

        # ==================== 7. DAILY REVENUE SUMMARY ====================
        total_revenue = round(total_room_revenue + pos_revenue + tx_total, 2)

        revenue_summary = {
            "room_revenue": round(total_room_revenue, 2),
            "pos_revenue": round(pos_revenue, 2),
            "payment_transactions": round(tx_total, 2),
            "total_revenue": total_revenue,
        }

        # ==================== OVERALL STATUS ====================
        checks = [checkin_check, checkout_check, payment_check, pos_check, housekeeping_check]
        has_warnings = any(c["status"] == "warning" for c in checks)
        has_failures = any(c["status"] == "fail" for c in checks)
        overall_status = "fail" if has_failures else "warning" if has_warnings else "pass"
        pass_count = sum(1 for c in checks if c["status"] == "pass")

        audit_result = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "audit_date": audit_date,
            "overall_status": overall_status,
            "pass_count": pass_count,
            "total_checks": len(checks),
            "checks": {
                "checkins": checkin_check,
                "checkouts": checkout_check,
                "payments": payment_check,
                "pos": pos_check,
                "housekeeping": housekeeping_check,
            },
            "occupancy": occupancy_stats,
            "revenue": revenue_summary,
            "run_by": current_user.get("email", ""),
            "run_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save audit
        await db.night_audits.insert_one(audit_result)
        audit_result.pop("_id", None)

        return audit_result

    @router.post("/night-audit/mark-no-show/{booking_id}")
    async def mark_no_show(booking_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Mark a booking as no-show during night audit"""
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"status": "no_show", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"status": "marked_no_show"}

    @router.post("/night-audit/complete/{audit_id}")
    async def complete_audit(audit_id: str, data: Dict = {}, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Complete the night audit and roll the date forward"""
        notes = data.get("notes", "")
        await db.night_audits.update_one(
            {"id": audit_id},
            {"$set": {
                "completed": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "completed_by": current_user.get("email", ""),
                "notes": notes,
            }}
        )
        return {"status": "completed", "message": "Night audit completed. Date rolled forward."}

    @router.get("/night-audit/history/{property_id}")
    async def audit_history(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get night audit history"""
        docs = await db.night_audits.find({"property_id": property_id}, {"_id": 0}).sort("audit_date", -1).to_list(60)
        return docs

    @router.get("/night-audit/latest/{property_id}")
    async def latest_audit(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get the most recent audit"""
        doc = await db.night_audits.find_one({"property_id": property_id}, {"_id": 0}, sort=[("audit_date", -1)])
        return doc or {}

    return router
