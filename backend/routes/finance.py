"""
Finance Hub — Dashboard, Earned Salaries, Payroll Runs, Adjustments, Cash Advances,
Adjustment Categories, Expenses, Recurring Expenses
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_finance_router(db, require_roles):
    router = APIRouter()

    # ==================== 1. FINANCE DASHBOARD ====================

    @router.get("/finance/dashboard/{property_id}")
    async def finance_dashboard(property_id: str, from_date: str = "", to_date: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if not from_date:
            from_date = now.replace(day=1).strftime("%Y-%m-%d")
        if not to_date:
            import calendar
            last_day = calendar.monthrange(now.year, now.month)[1]
            to_date = now.replace(day=last_day).strftime("%Y-%m-%d")

        pq = {} if property_id == "all" else {"property_id": property_id}

        # Room revenue from bookings
        bookings = await db.bookings.find(
            {**pq, "check_in": {"$lte": to_date}, "check_out": {"$gte": from_date}}, {"_id": 0}
        ).to_list(500)
        room_revenue = sum(float(b.get("total_price", 0) or 0) for b in bookings)
        room_count = len([b for b in bookings if float(b.get("total_price", 0) or 0) > 0])
        nights_sold = sum(max(1, int(b.get("nights", 1) or 1)) for b in bookings) if bookings else 0
        adr = round(room_revenue / max(nights_sold, 1), 2)

        # Expenses
        expenses = await db.finance_expenses.find(
            {**pq, "date": {"$gte": from_date, "$lte": to_date}}, {"_id": 0}
        ).to_list(500)
        total_expenses = sum(float(e.get("amount", 0) or 0) for e in expenses if e.get("category") != "commission")
        total_commission = sum(float(e.get("amount", 0) or 0) for e in expenses if e.get("category") == "commission")

        # Payroll from earned salaries (includes shift-synced entries)
        salaries = await db.finance_earned_salaries.find(
            {**pq, "date": {"$gte": from_date, "$lte": to_date}}, {"_id": 0}
        ).to_list(1000)
        total_payroll = sum(float(s.get("amount", 0) or 0) for s in salaries)

        # Also check shifts directly for any not yet synced
        shift_payroll = await db.shift_entries.find(
            {**pq, "date": {"$gte": from_date, "$lte": to_date}, "status": {"$in": ["completed", "approved"]}}, {"_id": 0}
        ).to_list(500)
        synced_shift_ids = set(s.get("shift_id", "") for s in salaries if s.get("shift_id"))
        unsynced_shift_pay = sum(
            float(s.get("earned_amount", 0) or 0)
            for s in shift_payroll
            if s.get("id", "") not in synced_shift_ids and float(s.get("earned_amount", 0) or 0) > 0
        )
        total_payroll += unsynced_shift_pay

        gross = room_revenue + total_commission
        total_costs = total_expenses + total_payroll + total_commission
        net = gross - total_costs

        # Operating costs breakdown
        cost_items = []
        expense_cats = {}
        for e in expenses:
            cat = e.get("category", "other")
            expense_cats.setdefault(cat, {"category": cat, "count": 0, "total": 0, "status": "paid"})
            expense_cats[cat]["count"] += 1
            expense_cats[cat]["total"] += float(e.get("amount", 0) or 0)
        cost_items = list(expense_cats.values())

        # Revenue by source
        source_rev = {}
        for b in bookings:
            src = b.get("source", "Direct")
            source_rev.setdefault(src, {"source": src, "count": 0, "revenue": 0})
            source_rev[src]["count"] += 1
            source_rev[src]["revenue"] += float(b.get("total_price", 0) or 0)
        revenue_sources = sorted(source_rev.values(), key=lambda x: x["revenue"], reverse=True)

        margin = round((net / max(gross, 1)) * 100, 2) if gross > 0 else 0

        return {
            "period": {"from": from_date, "to": to_date},
            "overview": {
                "gross": round(gross, 2), "room_revenue": round(room_revenue, 2),
                "adr": adr, "commission": round(total_commission, 2),
                "expenses": round(total_expenses, 2), "payroll": round(total_payroll, 2),
                "total_costs": round(total_costs, 2), "net": round(net, 2), "margin": margin,
            },
            "operating_costs": cost_items,
            "revenue_sources": revenue_sources,
            "bookings_count": len(bookings),
            "expense_details": [{"id": e.get("id",""), "date": e.get("date",""), "category": e.get("category",""), "vendor": e.get("vendor",""), "details": e.get("details",""), "amount": float(e.get("amount",0)), "status": e.get("status","pending")} for e in expenses],
        }

    @router.get("/finance/dashboard-history/{property_id}")
    async def finance_history(property_id: str, months: int = 6,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """6-month financial overview for chart"""
        import calendar as cal_mod
        now = datetime.now(timezone.utc)
        pq = {} if property_id == "all" else {"property_id": property_id}
        history = []
        for i in range(months - 1, -1, -1):
            dt = now.replace(day=1) - timedelta(days=i * 30)
            y, m = dt.year, dt.month
            first = f"{y}-{m:02d}-01"
            last_day = cal_mod.monthrange(y, m)[1]
            last = f"{y}-{m:02d}-{last_day}"
            month_label = dt.strftime("%b %Y")

            bks = await db.bookings.find(
                {**pq, "check_in": {"$lte": last}, "check_out": {"$gte": first}}, {"_id": 0, "total_price": 1}
            ).to_list(500)
            rev = sum(float(b.get("total_price", 0) or 0) for b in bks)

            exps = await db.finance_expenses.find(
                {**pq, "date": {"$gte": first, "$lte": last}}, {"_id": 0, "amount": 1}
            ).to_list(500)
            costs = sum(float(e.get("amount", 0) or 0) for e in exps)

            history.append({"month": month_label, "revenue": round(rev, 2), "costs": round(costs, 2), "profit": round(rev - costs, 2)})
        return history

    # ==================== 2. EARNED SALARIES ====================

    @router.get("/finance/earned-salaries/{property_id}")
    async def list_earned_salaries(property_id: str, from_date: str = "", to_date: str = "",
                                   staff_id: str = "",
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        if from_date:
            pq["date"] = {"$gte": from_date}
        if to_date:
            pq.setdefault("date", {})["$lte"] = to_date
        if staff_id:
            pq["staff_id"] = staff_id
        docs = await db.finance_earned_salaries.find(pq, {"_id": 0}).sort("date", 1).to_list(2000)

        # Aggregate stats
        staff_set = set()
        total_earned = 0
        dates_set = set()
        for d in docs:
            staff_set.add(d.get("staff_id", ""))
            total_earned += float(d.get("amount", 0) or 0)
            dates_set.add(d.get("date", ""))

        return {
            "entries": docs,
            "stats": {
                "staff_count": len(staff_set),
                "working_days": len(dates_set),
                "total_rows": len(docs),
                "total_earned": round(total_earned, 2),
            }
        }

    @router.post("/finance/earned-salaries")
    async def create_earned_salary(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "staff_id": data.get("staff_id", ""),
            "staff_name": data.get("staff_name", ""),
            "role": data.get("role", ""),
            "date": data.get("date", ""),
            "amount": float(data.get("amount", 0) or 0),
            "notes": data.get("notes", ""),
            "created_at": now,
        }
        await db.finance_earned_salaries.insert_one(entry)
        entry.pop("_id", None)
        return entry

    # ==================== 3. PAYROLL RUNS ====================

    @router.get("/finance/payroll-runs/{property_id}")
    async def list_payroll_runs(property_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.finance_payroll_runs.find(pq, {"_id": 0}).sort("created_at", -1).to_list(100)
        # Get automation config
        config = await db.finance_payroll_config.find_one(
            {"property_id": property_id} if property_id != "all" else {}, {"_id": 0}
        )
        return {"runs": docs, "config": config or {"mode": "pause", "frequency": "monthly", "next_run": ""}}

    @router.post("/finance/payroll-runs")
    async def create_payroll_run(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        run = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "period_start": data.get("period_start", ""),
            "period_end": data.get("period_end", ""),
            "staff_count": int(data.get("staff_count", 0)),
            "gross_total": float(data.get("gross_total", 0)),
            "deductions": float(data.get("deductions", 0)),
            "net_total": float(data.get("net_total", 0)),
            "status": data.get("status", "draft"),
            "source": data.get("source", "manual"),
            "notes": data.get("notes", ""),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.finance_payroll_runs.insert_one(run)
        run.pop("_id", None)
        return run

    @router.put("/finance/payroll-runs/{run_id}")
    async def update_payroll_run(run_id: str, updates: Dict,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.finance_payroll_runs.update_one({"id": run_id}, {"$set": updates})
        return await db.finance_payroll_runs.find_one({"id": run_id}, {"_id": 0})

    @router.put("/finance/payroll-config/{property_id}")
    async def update_payroll_config(property_id: str, data: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        data.pop("_id", None)
        data["property_id"] = property_id
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.finance_payroll_config.update_one(
            {"property_id": property_id}, {"$set": data}, upsert=True
        )
        return await db.finance_payroll_config.find_one({"property_id": property_id}, {"_id": 0})

    # ==================== 4. PAYROLL ADJUSTMENTS ====================

    @router.get("/finance/adjustments/{property_id}")
    async def list_adjustments(property_id: str, adj_type: str = "", status: str = "",
                               employee: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        if adj_type:
            pq["type"] = adj_type
        if status:
            pq["status"] = status
        if employee:
            pq["employee_id"] = employee
        docs = await db.finance_adjustments.find(pq, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    @router.post("/finance/adjustments")
    async def create_adjustment(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        adj = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "employee_id": data.get("employee_id", ""),
            "employee_name": data.get("employee_name", ""),
            "type": data.get("type", "addition"),
            "category": data.get("category", "bonus"),
            "amount": float(data.get("amount", 0)),
            "schedule": data.get("schedule", "one-time"),
            "status": data.get("status", "active"),
            "effective_date": data.get("effective_date", ""),
            "notes": data.get("notes", ""),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.finance_adjustments.insert_one(adj)
        adj.pop("_id", None)
        return adj

    @router.put("/finance/adjustments/{adj_id}")
    async def update_adjustment(adj_id: str, updates: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.finance_adjustments.update_one({"id": adj_id}, {"$set": updates})
        return await db.finance_adjustments.find_one({"id": adj_id}, {"_id": 0})

    @router.delete("/finance/adjustments/{adj_id}")
    async def delete_adjustment(adj_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.finance_adjustments.delete_one({"id": adj_id})
        return {"status": "deleted"}

    # ==================== 5. CASH ADVANCES ====================

    @router.get("/finance/cash-advances/{property_id}")
    async def list_cash_advances(property_id: str, status: str = "", employee: str = "",
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        if status:
            pq["status"] = status
        if employee:
            pq["employee_id"] = employee
        docs = await db.finance_cash_advances.find(pq, {"_id": 0}).sort("created_at", -1).to_list(200)
        total_pending = sum(float(d.get("amount", 0)) for d in docs if d.get("status") == "pending")
        total_deducted = sum(float(d.get("amount", 0)) for d in docs if d.get("status") == "deducted")
        total_cancelled = sum(float(d.get("amount", 0)) for d in docs if d.get("status") == "cancelled")
        return {
            "advances": docs,
            "stats": {"total_pending": round(total_pending, 2), "total_deducted": round(total_deducted, 2),
                      "total_cancelled": round(total_cancelled, 2)}
        }

    @router.post("/finance/cash-advances")
    async def create_cash_advance(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        adv = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "employee_id": data.get("employee_id", ""),
            "employee_name": data.get("employee_name", ""),
            "amount": float(data.get("amount", 0)),
            "date": data.get("date", now[:10]),
            "status": "pending",
            "notes": data.get("notes", ""),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.finance_cash_advances.insert_one(adv)
        adv.pop("_id", None)
        return adv

    @router.put("/finance/cash-advances/{adv_id}")
    async def update_cash_advance(adv_id: str, updates: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.finance_cash_advances.update_one({"id": adv_id}, {"$set": updates})
        return await db.finance_cash_advances.find_one({"id": adv_id}, {"_id": 0})

    @router.delete("/finance/cash-advances/{adv_id}")
    async def delete_cash_advance(adv_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.finance_cash_advances.delete_one({"id": adv_id})
        return {"status": "deleted"}

    # ==================== 6. ADJUSTMENT CATEGORIES ====================

    @router.get("/finance/adjustment-categories")
    async def list_categories(current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.finance_adj_categories.find({}, {"_id": 0}).sort("order", 1).to_list(50)
        if not docs:
            # Seed defaults
            defaults = [
                {"code": "bonus", "name": "Bonus", "calc_type": "fixed", "type": "addition", "is_system": True, "status": "active", "order": 1},
                {"code": "transport", "name": "Transport Allowance", "calc_type": "fixed", "type": "addition", "is_system": False, "status": "active", "order": 2},
                {"code": "meal", "name": "Meal Allowance", "calc_type": "fixed", "type": "addition", "is_system": False, "status": "active", "order": 3},
                {"code": "accommodation", "name": "Accommodation Allowance", "calc_type": "fixed", "type": "addition", "is_system": False, "status": "active", "order": 4},
                {"code": "phone", "name": "Phone Allowance", "calc_type": "fixed", "type": "addition", "is_system": False, "status": "active", "order": 5},
                {"code": "overtime", "name": "Overtime Pay", "calc_type": "fixed", "type": "addition", "is_system": True, "status": "active", "order": 6},
                {"code": "holiday", "name": "Holiday Pay", "calc_type": "fixed", "type": "addition", "is_system": True, "status": "active", "order": 7},
                {"code": "tips", "name": "Tips / Gratuity", "calc_type": "fixed", "type": "addition", "is_system": False, "status": "active", "order": 8},
            ]
            for d in defaults:
                d["id"] = str(uuid.uuid4())
                d["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.finance_adj_categories.insert_many(defaults)
            for d in defaults:
                d.pop("_id", None)
            docs = defaults
        return docs

    @router.post("/finance/adjustment-categories")
    async def create_category(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        cat = {
            "id": str(uuid.uuid4()),
            "code": data.get("code", ""),
            "name": data.get("name", ""),
            "calc_type": data.get("calc_type", "fixed"),
            "type": data.get("type", "addition"),
            "is_system": False,
            "status": "active",
            "order": data.get("order", 99),
            "created_at": now,
        }
        await db.finance_adj_categories.insert_one(cat)
        cat.pop("_id", None)
        return cat

    @router.put("/finance/adjustment-categories/{cat_id}")
    async def update_category(cat_id: str, updates: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.finance_adj_categories.update_one({"id": cat_id}, {"$set": updates})
        return await db.finance_adj_categories.find_one({"id": cat_id}, {"_id": 0})

    @router.delete("/finance/adjustment-categories/{cat_id}")
    async def delete_category(cat_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        cat = await db.finance_adj_categories.find_one({"id": cat_id}, {"_id": 0})
        if cat and cat.get("is_system"):
            raise HTTPException(400, "Cannot delete system category")
        await db.finance_adj_categories.delete_one({"id": cat_id})
        return {"status": "deleted"}

    # ==================== 7. EXPENSES ====================

    @router.get("/finance/expenses/{property_id}")
    async def list_expenses(property_id: str, from_date: str = "", to_date: str = "",
                            category: str = "", status: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        if from_date:
            pq["date"] = {"$gte": from_date}
        if to_date:
            pq.setdefault("date", {})["$lte"] = to_date
        if category:
            pq["category"] = category
        if status:
            pq["status"] = status
        docs = await db.finance_expenses.find(pq, {"_id": 0}).sort("date", -1).to_list(500)
        return docs

    @router.post("/finance/expenses")
    async def create_expense(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        exp = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "date": data.get("date", now[:10]),
            "category": data.get("category", "other"),
            "details": data.get("details", ""),
            "vendor": data.get("vendor", ""),
            "amount": float(data.get("amount", 0)),
            "status": data.get("status", "pending"),
            "notes": data.get("notes", ""),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.finance_expenses.insert_one(exp)
        exp.pop("_id", None)
        return exp

    @router.put("/finance/expenses/{exp_id}")
    async def update_expense(exp_id: str, updates: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.finance_expenses.update_one({"id": exp_id}, {"$set": updates})
        return await db.finance_expenses.find_one({"id": exp_id}, {"_id": 0})

    @router.delete("/finance/expenses/{exp_id}")
    async def delete_expense(exp_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.finance_expenses.delete_one({"id": exp_id})
        return {"status": "deleted"}

    # ==================== 8. RECURRING EXPENSES ====================

    @router.get("/finance/recurring-expenses/{property_id}")
    async def list_recurring(property_id: str, status: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        pq = {} if property_id == "all" else {"property_id": property_id}
        if status:
            pq["status"] = status
        docs = await db.finance_recurring_expenses.find(pq, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/finance/recurring-expenses")
    async def create_recurring(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        rec = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": data.get("name", ""),
            "amount": float(data.get("amount", 0)),
            "frequency": data.get("frequency", "monthly"),
            "category": data.get("category", "other"),
            "next_run": data.get("next_run", ""),
            "started": data.get("started", now[:7]),
            "status": "active",
            "mode": "play",
            "notes": data.get("notes", ""),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.finance_recurring_expenses.insert_one(rec)
        rec.pop("_id", None)
        return rec

    @router.put("/finance/recurring-expenses/{rec_id}")
    async def update_recurring(rec_id: str, updates: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.finance_recurring_expenses.update_one({"id": rec_id}, {"$set": updates})
        return await db.finance_recurring_expenses.find_one({"id": rec_id}, {"_id": 0})

    @router.delete("/finance/recurring-expenses/{rec_id}")
    async def delete_recurring(rec_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.finance_recurring_expenses.delete_one({"id": rec_id})
        return {"status": "deleted"}

    return router
