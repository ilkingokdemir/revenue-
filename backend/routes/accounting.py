"""
Hotel Accounting Routes
Income, expenses, P&L, budgets, department cost centers
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import asyncio
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)


def create_accounting_router(db, require_roles):
    router = APIRouter()

    # === Income ===

    @router.get("/accounting/income/{property_id}")
    async def list_income(property_id: str, month: str = "", category: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if month: query["date"] = {"$regex": f"^{month}"}
        if category: query["category"] = category
        docs = await db.income_entries.find(query, {"_id": 0}).sort("date", -1).to_list(500)
        return docs

    @router.post("/accounting/income")
    async def create_income(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import IncomeEntry
        data["created_by"] = current_user.get("name", "Admin")
        entry = IncomeEntry(**data)
        doc = entry.model_dump()
        await db.income_entries.insert_one(doc)
        doc.pop("_id", None)
        await log_sync(db, "accounting", "internal", "success", f"Income: £{doc['amount']} - {doc['category']}", doc["id"])
        return doc

    @router.put("/accounting/income/{entry_id}")
    async def update_income(entry_id: str, updates: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.income_entries.update_one({"id": entry_id}, {"$set": updates})
        doc = await db.income_entries.find_one({"id": entry_id}, {"_id": 0})
        return doc

    @router.delete("/accounting/income/{entry_id}")
    async def delete_income(entry_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.income_entries.delete_one({"id": entry_id})
        return {"status": "deleted"}

    # === Expenses ===

    @router.get("/accounting/expenses/{property_id}")
    async def list_expenses(property_id: str, month: str = "", category: str = "", department: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if month: query["date"] = {"$regex": f"^{month}"}
        if category: query["category"] = category
        if department: query["department"] = department
        docs = await db.expense_entries.find(query, {"_id": 0}).sort("date", -1).to_list(500)
        return docs

    @router.post("/accounting/expenses")
    async def create_expense(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import ExpenseEntry
        data["created_by"] = current_user.get("name", "Admin")
        entry = ExpenseEntry(**data)
        doc = entry.model_dump()
        await db.expense_entries.insert_one(doc)
        doc.pop("_id", None)
        await log_sync(db, "accounting", "internal", "success", f"Expense: £{doc['amount']} - {doc['category']}", doc["id"])
        return doc

    @router.put("/accounting/expenses/{entry_id}")
    async def update_expense(entry_id: str, updates: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.expense_entries.update_one({"id": entry_id}, {"$set": updates})
        doc = await db.expense_entries.find_one({"id": entry_id}, {"_id": 0})
        return doc

    @router.delete("/accounting/expenses/{entry_id}")
    async def delete_expense(entry_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.expense_entries.delete_one({"id": entry_id})
        return {"status": "deleted"}

    # === P&L Statement ===

    @router.get("/accounting/pnl/{property_id}")
    async def profit_and_loss(property_id: str, period: str = "", year: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate P&L statement. period=YYYY-MM for monthly, year=YYYY for annual"""
        if not period and not year:
            period = datetime.now(timezone.utc).strftime("%Y-%m")

        income_query = {"property_id": property_id}
        expense_query = {"property_id": property_id}
        if period:
            income_query["date"] = {"$regex": f"^{period}"}
            expense_query["date"] = {"$regex": f"^{period}"}
        elif year:
            income_query["date"] = {"$regex": f"^{year}"}
            expense_query["date"] = {"$regex": f"^{year}"}

        # Income by category
        income_pipeline = [
            {"$match": income_query},
            {"$group": {"_id": "$category", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
        ]
        income_by_cat = {}
        total_income = 0
        async for doc in db.income_entries.aggregate(income_pipeline):
            income_by_cat[doc["_id"] or "other"] = {"total": round(doc["total"], 2), "count": doc["count"]}
            total_income += doc["total"]

        # Auto-pull booking revenue if no manual room_revenue
        if "room_revenue" not in income_by_cat:
            booking_query = {"property_id": property_id, "status": {"$ne": "cancelled"}}
            if period:
                booking_query["created_at"] = {"$regex": f"^{period}"}
            elif year:
                booking_query["created_at"] = {"$regex": f"^{year}"}
            rev_pipeline = [
                {"$match": booking_query},
                {"$group": {"_id": None, "total": {"$sum": "$total_price"}, "count": {"$sum": 1}}}
            ]
            async for doc in db.bookings.aggregate(rev_pipeline):
                if doc["total"] > 0:
                    income_by_cat["room_revenue"] = {"total": round(doc["total"], 2), "count": doc["count"], "source": "auto_booking_engine"}
                    total_income += doc["total"]

        # Expenses by category
        expense_pipeline = [
            {"$match": expense_query},
            {"$group": {"_id": "$category", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}
        ]
        expense_by_cat = {}
        total_expenses = 0
        async for doc in db.expense_entries.aggregate(expense_pipeline):
            expense_by_cat[doc["_id"] or "other"] = {"total": round(doc["total"], 2), "count": doc["count"]}
            total_expenses += doc["total"]

        # Department breakdown
        dept_income_pipeline = [
            {"$match": income_query},
            {"$group": {"_id": "$department", "total": {"$sum": "$amount"}}}
        ]
        dept_expense_pipeline = [
            {"$match": expense_query},
            {"$group": {"_id": "$department", "total": {"$sum": "$amount"}}}
        ]
        dept_income = {}
        async for doc in db.income_entries.aggregate(dept_income_pipeline):
            dept_income[doc["_id"] or "other"] = round(doc["total"], 2)
        dept_expense = {}
        async for doc in db.expense_entries.aggregate(dept_expense_pipeline):
            dept_expense[doc["_id"] or "other"] = round(doc["total"], 2)

        all_depts = set(list(dept_income.keys()) + list(dept_expense.keys()))
        departments = {}
        for d in all_depts:
            inc = dept_income.get(d, 0)
            exp = dept_expense.get(d, 0)
            departments[d] = {"income": inc, "expenses": exp, "net": round(inc - exp, 2)}

        net_profit = round(total_income - total_expenses, 2)
        margin = round((net_profit / total_income * 100) if total_income > 0 else 0, 1)

        return {
            "period": period or year,
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "net_profit": net_profit,
            "profit_margin": margin,
            "income_breakdown": income_by_cat,
            "expense_breakdown": expense_by_cat,
            "departments": departments,
        }

    # === Budget vs Actual ===

    @router.get("/accounting/budgets/{property_id}")
    async def list_budgets(property_id: str, month: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if month: query["month"] = month
        docs = await db.budgets.find(query, {"_id": 0}).sort("month", -1).to_list(200)
        return docs

    @router.post("/accounting/budgets")
    async def create_budget(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import Budget
        budget = Budget(**data)
        doc = budget.model_dump()
        await db.budgets.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/accounting/budgets/{budget_id}")
    async def update_budget(budget_id: str, updates: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.budgets.update_one({"id": budget_id}, {"$set": updates})
        doc = await db.budgets.find_one({"id": budget_id}, {"_id": 0})
        return doc

    @router.get("/accounting/budget-vs-actual/{property_id}")
    async def budget_vs_actual(property_id: str, month: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        budgets = await db.budgets.find({"property_id": property_id, "month": month}, {"_id": 0}).to_list(100)

        # Get actuals
        exp_pipeline = [
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{month}"}}},
            {"$group": {"_id": {"department": "$department", "category": "$category"}, "actual": {"$sum": "$amount"}}}
        ]
        actuals = {}
        async for doc in db.expense_entries.aggregate(exp_pipeline):
            key = f"{doc['_id']['department']}:{doc['_id']['category']}"
            actuals[key] = round(doc["actual"], 2)

        results = []
        for b in budgets:
            key = f"{b['department']}:{b['category']}"
            actual = actuals.get(key, 0)
            variance = round(b["budgeted_amount"] - actual, 2)
            variance_pct = round((variance / b["budgeted_amount"] * 100) if b["budgeted_amount"] > 0 else 0, 1)
            results.append({
                **b,
                "actual_amount": actual,
                "variance": variance,
                "variance_pct": variance_pct,
                "status": "under_budget" if variance >= 0 else "over_budget",
            })
        return results

    # === Sync Booking Revenue ===

    @router.post("/accounting/sync-revenue/{property_id}")
    async def sync_booking_revenue(property_id: str, month: str = "",
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Auto-import booking revenue as income entries"""
        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        existing = await db.income_entries.count_documents({"property_id": property_id, "source": "booking_engine", "date": {"$regex": f"^{month}"}})
        if existing > 0:
            return {"message": f"Revenue already synced for {month}", "entries": existing}

        bookings = await db.bookings.find(
            {"property_id": property_id, "status": {"$ne": "cancelled"}, "created_at": {"$regex": f"^{month}"}},
            {"_id": 0}
        ).to_list(2000)

        from models import IncomeEntry
        created = 0
        for b in bookings:
            if b.get("total_price", 0) > 0:
                entry = IncomeEntry(
                    property_id=property_id, category="room_revenue",
                    amount=b["total_price"], currency=b.get("currency", "GBP"),
                    description=f"Booking {b.get('booking_ref', '')} - {b.get('guest_name', '')}",
                    department="rooms", date=b.get("created_at", "")[:10],
                    source="booking_engine", reference=b.get("booking_ref", ""),
                )
                doc = entry.model_dump()
                await db.income_entries.insert_one(doc)
                created += 1

        await log_sync(db, "accounting", "internal", "success", f"Synced {created} booking revenue entries for {month}", property_id)
        return {"message": f"Synced {created} booking entries for {month}", "entries": created}

    # === Dashboard Stats ===

    @router.get("/accounting/stats/{property_id}")
    async def accounting_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        prev_month_dt = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
        prev_month = prev_month_dt.strftime("%Y-%m")

        # Current month
        inc_pipeline = [
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{current_month}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        exp_pipeline = [
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{current_month}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        cur_income = 0
        async for doc in db.income_entries.aggregate(inc_pipeline):
            cur_income = round(doc["total"], 2)
        cur_expense = 0
        async for doc in db.expense_entries.aggregate(exp_pipeline):
            cur_expense = round(doc["total"], 2)

        # Previous month
        prev_inc_pipeline = [
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{prev_month}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        prev_exp_pipeline = [
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{prev_month}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        prev_income = 0
        async for doc in db.income_entries.aggregate(prev_inc_pipeline):
            prev_income = round(doc["total"], 2)
        prev_expense = 0
        async for doc in db.expense_entries.aggregate(prev_exp_pipeline):
            prev_expense = round(doc["total"], 2)

        # Auto-add booking revenue
        booking_rev_pipeline = [
            {"$match": {"property_id": property_id, "status": {"$ne": "cancelled"}, "created_at": {"$regex": f"^{current_month}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
        ]
        booking_rev = 0
        async for doc in db.bookings.aggregate(booking_rev_pipeline):
            booking_rev = round(doc["total"], 2)

        total_income = cur_income + booking_rev
        net = round(total_income - cur_expense, 2)

        return {
            "current_month": current_month,
            "income": total_income,
            "manual_income": cur_income,
            "booking_revenue": booking_rev,
            "expenses": cur_expense,
            "net_profit": net,
            "margin": round((net / total_income * 100) if total_income > 0 else 0, 1),
            "prev_month": {"income": prev_income, "expenses": prev_expense, "net": round(prev_income - prev_expense, 2)},
            "total_income_entries": await db.income_entries.count_documents({"property_id": property_id}),
            "total_expense_entries": await db.expense_entries.count_documents({"property_id": property_id}),
        }

    return router
