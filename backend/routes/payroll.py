"""
Payroll Management — Monthly runs, adjustments (bonus/deduction), cash advances,
earned salary auto-computation from worked shifts.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict
import uuid
import logging
import calendar

logger = logging.getLogger(__name__)

ADJ_TYPES = ("bonus", "overtime", "commission", "deduction", "tax", "benefit", "other")


def _month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start, end


def create_payroll_router(db, require_roles):
    from auth import require_perm
    router = APIRouter()

    # ==================== EARNED SALARIES ====================
    @router.get("/payroll/earnings/{property_id}")
    async def earned_salaries(property_id: str, year: int = 0, month: int = 0,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if year == 0: year = now.year
        if month == 0: month = now.month
        start, end = _month_bounds(year, month)

        # Pull all shifts in this month
        shift_query = {"date": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
        shifts = await db.shifts.find(shift_query, {"_id": 0}).to_list(5000)

        # Role-based daily rate (mirrors ROLE_RATES in shift_scheduler)
        ROLE_RATES = {"receptionist": 50, "housekeeper": 80, "maintenance": 100, "manager": 120, "admin": 150}

        # Index users by id/email
        users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1, "role": 1, "department": 1}).to_list(200)
        u_index = {}
        for u in users:
            if u.get("id"): u_index[u["id"]] = u
            if u.get("email"): u_index[u["email"]] = u

        # Aggregate by staff
        by_staff = {}
        for s in shifts:
            sid = s.get("staff_id", "")
            by_staff.setdefault(sid, {"days": 0, "shifts": []})
            by_staff[sid]["days"] += 1
            by_staff[sid]["shifts"].append(s)

        rows = []
        grand_total = 0.0
        for sid, agg in by_staff.items():
            u = u_index.get(sid, {})
            role = u.get("role", "receptionist")
            daily = ROLE_RATES.get(role, 50)
            gross = agg["days"] * daily

            # Apply adjustments for this staff + month
            adjustments = await db.payroll_adjustments.find(
                {"staff_id": sid, "year": year, "month": month}, {"_id": 0}
            ).to_list(50)
            adj_total = sum(a.get("amount", 0) if a.get("type") != "deduction" and a.get("type") != "tax" else -a.get("amount", 0) for a in adjustments)

            # Outstanding advances (repayments)
            advances = await db.cash_advances.find(
                {"staff_id": sid, "status": "approved", "repaid": False}, {"_id": 0}
            ).to_list(20)
            advance_total = sum(a.get("amount", 0) for a in advances)

            net = gross + adj_total - advance_total
            grand_total += net

            rows.append({
                "staff_id": sid,
                "name": u.get("name", sid),
                "role": role,
                "department": u.get("department", ""),
                "days_worked": agg["days"],
                "daily_rate": daily,
                "gross": round(gross, 2),
                "adjustments": round(adj_total, 2),
                "advances": round(advance_total, 2),
                "net": round(net, 2),
                "adjustment_count": len(adjustments),
            })

        rows.sort(key=lambda x: x["name"])
        return {
            "year": year, "month": month,
            "period": f"{calendar.month_name[month]} {year}",
            "total_staff": len(rows),
            "total_gross": round(sum(r["gross"] for r in rows), 2),
            "total_adjustments": round(sum(r["adjustments"] for r in rows), 2),
            "total_advances": round(sum(r["advances"] for r in rows), 2),
            "grand_total": round(grand_total, 2),
            "rows": rows,
        }

    # ==================== RUNS ====================
    @router.get("/payroll/runs/{property_id}")
    async def list_runs(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        runs = await db.payroll_runs.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"runs": runs}

    @router.post("/payroll/runs/{property_id}")
    async def create_run(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        year = int(data.get("year") or datetime.now(timezone.utc).year)
        month = int(data.get("month") or datetime.now(timezone.utc).month)
        existing = await db.payroll_runs.find_one({"property_id": property_id, "year": year, "month": month}, {"_id": 0})
        if existing:
            raise HTTPException(400, f"Run for {calendar.month_name[month]} {year} already exists")

        # Compute earnings now and snapshot
        earnings_resp = await earned_salaries(property_id, year, month, current_user)
        now = datetime.now(timezone.utc).isoformat()
        run = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "year": year,
            "month": month,
            "period": earnings_resp["period"],
            "status": "draft",
            "total_staff": earnings_resp["total_staff"],
            "total_gross": earnings_resp["total_gross"],
            "total_adjustments": earnings_resp["total_adjustments"],
            "total_advances": earnings_resp["total_advances"],
            "grand_total": earnings_resp["grand_total"],
            "rows": earnings_resp["rows"],
            "created_at": now,
            "created_by": current_user.get("name", ""),
            "approved_at": "",
            "paid_at": "",
        }
        await db.payroll_runs.insert_one({**run})
        return run

    @router.post("/payroll/runs/{property_id}/{run_id}/approve")
    async def approve_run(property_id: str, run_id: str,
                          current_user: dict = Depends(require_perm("approve_payroll_runs"))):
        now = datetime.now(timezone.utc).isoformat()
        r = await db.payroll_runs.update_one(
            {"id": run_id}, {"$set": {"status": "approved", "approved_at": now, "approved_by": current_user.get("name", "")}}
        )
        if r.matched_count == 0: raise HTTPException(404, "Run not found")
        return {"ok": True}

    @router.post("/payroll/runs/{property_id}/{run_id}/mark-paid")
    async def mark_paid(property_id: str, run_id: str,
                        current_user: dict = Depends(require_perm("approve_payroll_runs"))):
        now = datetime.now(timezone.utc).isoformat()
        r = await db.payroll_runs.update_one(
            {"id": run_id}, {"$set": {"status": "paid", "paid_at": now, "paid_by": current_user.get("name", "")}}
        )
        if r.matched_count == 0: raise HTTPException(404, "Run not found")
        # Auto-mark linked advances as repaid
        run = await db.payroll_runs.find_one({"id": run_id}, {"_id": 0})
        if run:
            staff_ids = [row.get("staff_id") for row in run.get("rows", []) if row.get("advances", 0) > 0]
            if staff_ids:
                await db.cash_advances.update_many(
                    {"staff_id": {"$in": staff_ids}, "status": "approved", "repaid": False},
                    {"$set": {"repaid": True, "repaid_at": now}}
                )
        return {"ok": True}

    @router.delete("/payroll/runs/{property_id}/{run_id}")
    async def delete_run(property_id: str, run_id: str,
                         current_user: dict = Depends(require_perm("delete_payroll_runs"))):
        run = await db.payroll_runs.find_one({"id": run_id}, {"_id": 0})
        if not run: raise HTTPException(404, "Run not found")
        if run.get("status") == "paid": raise HTTPException(400, "Cannot delete paid run")
        await db.payroll_runs.delete_one({"id": run_id})
        return {"deleted": True}

    # ==================== ADJUSTMENTS ====================
    @router.get("/payroll/adjustments/{property_id}")
    async def list_adjustments(property_id: str, year: int = 0, month: int = 0,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {}
        if year > 0: query["year"] = year
        if month > 0: query["month"] = month
        adj = await db.payroll_adjustments.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"adjustments": adj}

    @router.post("/payroll/adjustments/{property_id}")
    async def create_adjustment(property_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        staff_id = data.get("staff_id", "")
        if not staff_id: raise HTTPException(400, "staff_id required")
        typ = data.get("type", "bonus")
        if typ not in ADJ_TYPES: typ = "bonus"
        now = datetime.now(timezone.utc)
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "staff_id": staff_id,
            "staff_name": data.get("staff_name", ""),
            "type": typ,
            "amount": float(data.get("amount", 0)),
            "reason": (data.get("reason") or "").strip(),
            "year": int(data.get("year") or now.year),
            "month": int(data.get("month") or now.month),
            "created_at": now.isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.payroll_adjustments.insert_one({**doc})
        return doc

    @router.delete("/payroll/adjustments/{property_id}/{adj_id}")
    async def delete_adjustment(property_id: str, adj_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.payroll_adjustments.delete_one({"id": adj_id})
        if r.deleted_count == 0: raise HTTPException(404, "Not found")
        return {"deleted": True}

    # ==================== CASH ADVANCES ====================
    @router.get("/payroll/advances/{property_id}")
    async def list_advances(property_id: str, status: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {}
        if status: query["status"] = status
        rows = await db.cash_advances.find(query, {"_id": 0}).sort("requested_at", -1).to_list(200)
        kpis = {"pending": 0, "approved": 0, "rejected": 0, "repaid": 0, "total_outstanding": 0.0}
        for a in await db.cash_advances.find({}, {"_id": 0}).to_list(500):
            s = a.get("status", "pending")
            if s in kpis: kpis[s] += 1
            if s == "approved" and not a.get("repaid"):
                kpis["total_outstanding"] += float(a.get("amount", 0))
        kpis["total_outstanding"] = round(kpis["total_outstanding"], 2)
        return {"advances": rows, "kpis": kpis}

    @router.post("/payroll/advances/{property_id}")
    async def request_advance(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        staff_id = data.get("staff_id") or current_user.get("id") or current_user.get("email", "")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "staff_id": staff_id,
            "staff_name": data.get("staff_name", current_user.get("name", "")),
            "amount": float(data.get("amount", 0)),
            "reason": (data.get("reason") or "").strip(),
            "status": "pending",
            "repaid": False,
            "requested_at": now,
            "requested_by": current_user.get("name", ""),
            "approved_at": "",
            "approved_by": "",
            "repaid_at": "",
        }
        await db.cash_advances.insert_one({**doc})
        return doc

    @router.post("/payroll/advances/{property_id}/{adv_id}/approve")
    async def approve_advance(property_id: str, adv_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        r = await db.cash_advances.update_one(
            {"id": adv_id}, {"$set": {"status": "approved", "approved_at": now, "approved_by": current_user.get("name", "")}}
        )
        if r.matched_count == 0: raise HTTPException(404, "Not found")
        return {"ok": True}

    @router.post("/payroll/advances/{property_id}/{adv_id}/reject")
    async def reject_advance(property_id: str, adv_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.cash_advances.update_one(
            {"id": adv_id}, {"$set": {"status": "rejected"}}
        )
        if r.matched_count == 0: raise HTTPException(404, "Not found")
        return {"ok": True}

    @router.post("/payroll/advances/{property_id}/{adv_id}/mark-repaid")
    async def mark_advance_repaid(property_id: str, adv_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        r = await db.cash_advances.update_one(
            {"id": adv_id}, {"$set": {"status": "repaid", "repaid": True, "repaid_at": now}}
        )
        if r.matched_count == 0: raise HTTPException(404, "Not found")
        return {"ok": True}

    return router
