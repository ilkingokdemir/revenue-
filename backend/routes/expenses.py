"""
Expense Management — Categories with budgets, one-off expenses, recurring expense templates.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date, timedelta
from typing import Dict
import uuid
import logging
import calendar

logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    {"id": "utilities",  "name": "Utilities",       "color": "#f59e0b", "icon": "zap"},
    {"id": "supplies",   "name": "Supplies",        "color": "#10b981", "icon": "package"},
    {"id": "maintenance","name": "Maintenance",     "color": "#ef4444", "icon": "wrench"},
    {"id": "marketing",  "name": "Marketing",       "color": "#8b5cf6", "icon": "megaphone"},
    {"id": "salaries",   "name": "Salaries",        "color": "#3b82f6", "icon": "users"},
    {"id": "rent",       "name": "Rent & Leases",   "color": "#06b6d4", "icon": "home"},
    {"id": "food",       "name": "Food & Beverage", "color": "#ec4899", "icon": "utensils"},
    {"id": "tech",       "name": "Technology",      "color": "#6366f1", "icon": "cpu"},
    {"id": "other",      "name": "Other",           "color": "#78716c", "icon": "more"},
]

FREQUENCIES = ("weekly", "biweekly", "monthly", "quarterly", "annual")


def _next_due(last: str, freq: str) -> str:
    try:
        d = datetime.strptime(last, "%Y-%m-%d").date()
    except Exception:
        d = date.today()
    if freq == "weekly":     d = d + timedelta(days=7)
    elif freq == "biweekly": d = d + timedelta(days=14)
    elif freq == "monthly":
        ny, nm = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        last_day = calendar.monthrange(ny, nm)[1]
        d = date(ny, nm, min(d.day, last_day))
    elif freq == "quarterly":
        m = d.month + 3
        ny = d.year + (m - 1) // 12
        nm = ((m - 1) % 12) + 1
        last_day = calendar.monthrange(ny, nm)[1]
        d = date(ny, nm, min(d.day, last_day))
    elif freq == "annual":
        d = date(d.year + 1, d.month, d.day)
    return d.isoformat()


def create_expenses_router(db, require_roles):
    router = APIRouter()

    # ==================== CATEGORIES ====================
    @router.get("/expenses/categories/{property_id}")
    async def list_categories(property_id: str, year: int = 0, month: int = 0,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if year == 0: year = now.year
        if month == 0: month = now.month

        custom = await db.expense_categories.find({}, {"_id": 0}).to_list(100)
        cats = DEFAULT_CATEGORIES + [c for c in custom if c.get("id") not in {x["id"] for x in DEFAULT_CATEGORIES}]

        start = date(year, month, 1).isoformat()
        end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        q = {"date": {"$gte": start, "$lte": end}}
        if property_id != "all":
            q["property_id"] = property_id
        spent_by_cat = {}
        async for e in db.expenses.find(q, {"_id": 0, "category": 1, "amount": 1}):
            c = e.get("category", "other")
            spent_by_cat[c] = spent_by_cat.get(c, 0) + float(e.get("amount", 0))

        # Budgets stored in expense_budgets: {property_id, category, year, month, amount}
        budget_q = {"year": year, "month": month}
        if property_id != "all":
            budget_q["property_id"] = property_id
        budgets = await db.expense_budgets.find(budget_q, {"_id": 0}).to_list(200)
        budget_by_cat = {b["category"]: float(b.get("amount", 0)) for b in budgets}

        out = []
        for c in cats:
            spent = round(spent_by_cat.get(c["id"], 0), 2)
            budget = budget_by_cat.get(c["id"], 0)
            usage = round((spent / budget * 100) if budget > 0 else 0, 1)
            out.append({**c, "spent": spent, "budget": budget, "usage_pct": usage})
        return {"categories": out, "year": year, "month": month}

    @router.put("/expenses/categories/{property_id}/{category_id}/budget")
    async def set_budget(property_id: str, category_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        year = int(data.get("year") or datetime.now(timezone.utc).year)
        month = int(data.get("month") or datetime.now(timezone.utc).month)
        amount = float(data.get("amount", 0))
        await db.expense_budgets.update_one(
            {"property_id": property_id, "category": category_id, "year": year, "month": month},
            {"$set": {"property_id": property_id, "category": category_id, "year": year, "month": month, "amount": amount,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"ok": True, "amount": amount}

    # ==================== EXPENSES ====================
    @router.get("/expenses/{property_id}")
    async def list_expenses(property_id: str, year: int = 0, month: int = 0, category: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if year == 0: year = now.year
        if month == 0: month = now.month
        start = date(year, month, 1).isoformat()
        end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        query = {"date": {"$gte": start, "$lte": end}}
        if property_id != "all": query["property_id"] = property_id
        if category: query["category"] = category

        rows = await db.expenses.find(query, {"_id": 0}).sort("date", -1).to_list(500)

        total = round(sum(float(r.get("amount", 0)) for r in rows), 2)
        by_cat = {}
        for r in rows:
            c = r.get("category", "other")
            by_cat[c] = by_cat.get(c, 0) + float(r.get("amount", 0))
        return {
            "expenses": rows,
            "kpis": {"total": total, "count": len(rows), "avg": round(total / len(rows), 2) if rows else 0},
            "by_category": {k: round(v, 2) for k, v in by_cat.items()},
            "year": year, "month": month,
        }

    @router.post("/expenses/{property_id}")
    async def create_expense(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        amount = float(data.get("amount", 0))
        if amount <= 0: raise HTTPException(400, "Amount must be positive")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "vendor": (data.get("vendor") or "").strip(),
            "category": data.get("category", "other"),
            "description": (data.get("description") or "").strip(),
            "amount": round(amount, 2),
            "date": data.get("date", now[:10]),
            "payment_method": data.get("payment_method", "bank"),
            "receipt_url": data.get("receipt_url", ""),
            "reference": data.get("reference", ""),
            "notes": (data.get("notes") or "").strip(),
            "recurring_id": data.get("recurring_id", ""),
            "created_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.expenses.insert_one({**doc})
        return doc

    @router.put("/expenses/{property_id}/{exp_id}")
    async def update_expense(property_id: str, exp_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"vendor", "category", "description", "amount", "date", "payment_method", "receipt_url", "reference", "notes"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if "amount" in updates: updates["amount"] = round(float(updates["amount"]), 2)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.expenses.update_one({"id": exp_id}, {"$set": updates})
        if r.matched_count == 0: raise HTTPException(404, "Not found")
        doc = await db.expenses.find_one({"id": exp_id}, {"_id": 0})
        return doc

    @router.delete("/expenses/{property_id}/{exp_id}")
    async def delete_expense(property_id: str, exp_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.expenses.delete_one({"id": exp_id})
        if r.deleted_count == 0: raise HTTPException(404, "Not found")
        return {"deleted": True}

    # ==================== LAUNDRY COST AGGREGATE (permission-gated) ====================
    @router.get("/expenses/laundry-summary/{property_id}")
    async def laundry_summary(property_id: str, year: int = 0, month: int = 0,
                              current_user: dict = Depends(require_roles(
                                  "admin", "manager", "accountant",
                                  "receptionist", "housekeeper", "laundry_staff", "maintenance",
                              ))):
        # Honour admin-configured `view_laundry_costs` permission (Roles & Permissions panel).
        # Legacy admin bypasses. All other roles must have the permission on their role doc.
        if current_user.get("role") != "admin":
            from auth import get_user_permissions
            perms = await get_user_permissions(current_user)
            if "view_laundry_costs" not in perms:
                raise HTTPException(403, "view_laundry_costs permission required")
        """Aggregate all laundry-related costs for the month: dispatches sent, deliveries paid,
        stock transactions (disposal/write-off). Also returns active contract count & total
        monthly flat fees for admin visibility."""
        now = datetime.now(timezone.utc)
        if year == 0: year = now.year
        if month == 0: month = now.month
        start = date(year, month, 1).isoformat()
        end = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        prop_q = {} if property_id == "all" else {"property_id": property_id}

        # Dispatches sent in month
        disp = await db.laundry_dispatches.find(
            {**prop_q, "sent_date": {"$gte": start, "$lte": end}}, {"_id": 0}
        ).to_list(1000)
        dispatch_cost = round(sum(float(d.get("total_cost") or 0) for d in disp), 2)
        dispatch_count = len(disp)
        dispatch_pieces = sum(int(i.get("qty_sent") or 0) for d in disp for i in d.get("items", []))

        # Deliveries paid in month (net_payable)
        deliv = await db.laundry_deliveries.find(
            {**prop_q, "delivery_date": {"$gte": start, "$lte": end}}, {"_id": 0}
        ).to_list(1000)
        delivery_net = round(sum(float(d.get("net_payable") or 0) for d in deliv), 2)
        delivery_gross = round(sum(float(d.get("gross_amount") or 0) for d in deliv), 2)
        delivery_deductions = round(sum(float(d.get("deduction_amount") or 0) for d in deliv), 2)

        # Stock transactions: disposal/write-off are losses
        stx = await db.laundry_stock_transactions.find(
            {**prop_q, "transaction_date": {"$gte": start, "$lte": end}}, {"_id": 0}
        ).to_list(500)
        loss_cost = round(sum(
            float(s.get("total_cost") or 0)
            for s in stx if s.get("tx_type") in ("disposal", "write_off", "maintenance")
        ), 2)
        loss_pieces = sum(
            int(s.get("quantity") or 0)
            for s in stx if s.get("tx_type") in ("disposal", "write_off", "maintenance")
        )

        # Active contracts with monthly obligation
        contracts = await db.laundry_contracts.find(
            {**prop_q, "active": True}, {"_id": 0}
        ).to_list(200)
        monthly_flat = round(sum(
            float(c.get("flat_amount") or 0)
            for c in contracts if c.get("pricing_model") in ("flat_rate", "hybrid")
            and (c.get("billing_period") or "monthly") == "monthly"
        ), 2)

        total = round(dispatch_cost + delivery_net + loss_cost, 2)

        return {
            "year": year, "month": month, "start": start, "end": end,
            "total": total,
            "breakdown": [
                {"key": "dispatches", "label": "Dispatches Sent", "amount": dispatch_cost,
                 "count": dispatch_count, "pieces": dispatch_pieces},
                {"key": "deliveries", "label": "Deliveries Paid (Net)", "amount": delivery_net,
                 "count": len(deliv), "gross": delivery_gross, "deductions": delivery_deductions},
                {"key": "losses", "label": "Losses (Disposal/Write-off/Maintenance)", "amount": loss_cost,
                 "count": sum(1 for s in stx if s.get("tx_type") in ("disposal", "write_off", "maintenance")),
                 "pieces": loss_pieces},
            ],
            "contracts": {"active": len(contracts), "monthly_flat_fees": monthly_flat},
        }

    # ==================== RECURRING ====================
    @router.get("/expenses/recurring/{property_id}")
    async def list_recurring(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        rows = await db.recurring_expenses.find(query, {"_id": 0}).sort("next_due", 1).to_list(100)
        today = date.today().isoformat()
        due_count = sum(1 for r in rows if r.get("enabled", True) and r.get("next_due", "9999") <= today)
        return {"recurring": rows, "due_count": due_count}

    @router.post("/expenses/recurring/{property_id}")
    async def create_recurring(property_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        amount = float(data.get("amount", 0))
        if amount <= 0: raise HTTPException(400, "Amount must be positive")
        freq = data.get("frequency", "monthly")
        if freq not in FREQUENCIES: freq = "monthly"
        next_due = data.get("next_due", date.today().isoformat())
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "vendor": (data.get("vendor") or "").strip(),
            "category": data.get("category", "other"),
            "description": (data.get("description") or "").strip(),
            "amount": round(amount, 2),
            "frequency": freq,
            "next_due": next_due,
            "payment_method": data.get("payment_method", "bank"),
            "enabled": True,
            "auto_post": bool(data.get("auto_post", False)),
            "last_run": "",
            "total_posted": 0,
            "created_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.recurring_expenses.insert_one({**doc})
        return doc

    @router.put("/expenses/recurring/{property_id}/{rec_id}")
    async def update_recurring(property_id: str, rec_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"vendor", "category", "description", "amount", "frequency", "next_due", "payment_method", "enabled", "auto_post"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if "amount" in updates: updates["amount"] = round(float(updates["amount"]), 2)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.recurring_expenses.update_one({"id": rec_id}, {"$set": updates})
        if r.matched_count == 0: raise HTTPException(404, "Not found")
        doc = await db.recurring_expenses.find_one({"id": rec_id}, {"_id": 0})
        return doc

    @router.delete("/expenses/recurring/{property_id}/{rec_id}")
    async def delete_recurring(property_id: str, rec_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.recurring_expenses.delete_one({"id": rec_id})
        if r.deleted_count == 0: raise HTTPException(404, "Not found")
        return {"deleted": True}

    @router.post("/expenses/recurring/{property_id}/{rec_id}/post")
    async def post_recurring(property_id: str, rec_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        rec = await db.recurring_expenses.find_one({"id": rec_id}, {"_id": 0})
        if not rec: raise HTTPException(404, "Not found")
        now = datetime.now(timezone.utc).isoformat()
        exp = {
            "id": str(uuid.uuid4()),
            "property_id": rec.get("property_id", property_id),
            "vendor": rec.get("vendor", ""),
            "category": rec.get("category", "other"),
            "description": rec.get("description", "") + " (recurring)",
            "amount": float(rec.get("amount", 0)),
            "date": rec.get("next_due", now[:10]),
            "payment_method": rec.get("payment_method", "bank"),
            "receipt_url": "", "reference": "", "notes": "",
            "recurring_id": rec_id,
            "created_at": now,
            "created_by": current_user.get("name", "") + " (auto)",
        }
        await db.expenses.insert_one({**exp})
        # Advance next due
        new_next = _next_due(rec.get("next_due", now[:10]), rec.get("frequency", "monthly"))
        await db.recurring_expenses.update_one(
            {"id": rec_id},
            {"$set": {"last_run": now, "next_due": new_next}, "$inc": {"total_posted": 1}}
        )
        return exp

    @router.post("/expenses/recurring/{property_id}/run-due")
    async def run_due(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        today = date.today().isoformat()
        query = {"enabled": True, "next_due": {"$lte": today}}
        if property_id != "all": query["property_id"] = property_id
        due = await db.recurring_expenses.find(query, {"_id": 0}).to_list(200)
        posted = 0
        for rec in due:
            await post_recurring(rec.get("property_id", property_id), rec["id"], current_user)
            posted += 1
        return {"posted": posted}

    return router
