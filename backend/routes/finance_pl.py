"""
Finance P&L Dashboard — Operating ledger (costs vs revenue),
profit/loss with margin, 6-month financial trend, recurring expenses.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict
import uuid
import calendar
import logging

logger = logging.getLogger(__name__)


def create_finance_pl_router(db, require_roles):
    router = APIRouter()

    @router.get("/finance/pl/{property_id}")
    async def get_pl_dashboard(property_id: str, month: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Profit & Loss dashboard with operating ledger."""
        now = datetime.now(timezone.utc)
        if month:
            year, mon = int(month[:4]), int(month[5:7])
        else:
            year, mon = now.year, now.month

        last_day = calendar.monthrange(year, mon)[1]
        start = f"{year}-{mon:02d}-01"
        end = f"{year}-{mon:02d}-{last_day}"

        bk_query = {"status": {"$nin": ["cancelled"]}, "check_in": {"$gte": start, "$lte": end}}
        if property_id != "all":
            bk_query["property_id"] = property_id

        bookings = await db.bookings.find(bk_query, {"_id": 0}).to_list(5000)
        total_rooms = 0
        if property_id != "all":
            total_rooms = await db.rooms.count_documents({"property_id": property_id})
        if total_rooms == 0:
            q = {} if property_id == "all" else {"property_id": property_id}
            total_rooms = max(await db.room_types.count_documents(q) * 3, 10)

        # Revenue by source
        by_source = defaultdict(lambda: {"revenue": 0, "count": 0})
        gross = 0
        room_nights = 0
        for b in bookings:
            src = b.get("source", "Direct")
            rev = float(b.get("total_price", 0) or 0)
            by_source[src]["revenue"] += rev
            by_source[src]["count"] += 1
            gross += rev
            room_nights += int(b.get("nights", 1) or 1)

        room_revenue = round(gross, 2)
        adr = round(room_revenue / max(room_nights, 1), 2)
        commission = round(gross * 0.15, 2)

        revenue_items = [{"source": k, "revenue": round(v["revenue"], 2), "bookings": v["count"]} for k, v in sorted(by_source.items(), key=lambda x: -x[1]["revenue"])]

        # Operating costs from expenses collection
        expenses = await db.expenses.find(
            {"month": f"{year}-{mon:02d}"} if await db.expenses.count_documents({"month": f"{year}-{mon:02d}"}) > 0
            else {},
            {"_id": 0}
        ).to_list(200)

        # Generate sample operating costs if none exist
        if not expenses:
            cost_items = [
                {"category": "Rent", "description": "Property Rent", "amount": round(total_rooms * 250, 2), "status": "paid"},
                {"category": "Laundry", "description": "Laundry Services", "amount": round(room_nights * 5, 2), "status": "paid"},
                {"category": "Utilities", "description": "Electricity, Gas, Water", "amount": round(total_rooms * 40, 2), "status": "paid"},
                {"category": "Commission", "description": "OTA Commissions", "amount": commission, "status": "accrued"},
                {"category": "Cleaning", "description": "Cleaning Supplies", "amount": round(total_rooms * 15, 2), "status": "paid"},
                {"category": "Insurance", "description": "Property Insurance", "amount": round(total_rooms * 20, 2), "status": "paid"},
                {"category": "Maintenance", "description": "Repairs & Maintenance", "amount": round(total_rooms * 25, 2), "status": "paid"},
            ]
        else:
            cost_items = [{"category": e.get("category", "Other"), "description": e.get("description", ""), "amount": float(e.get("amount", 0)), "status": e.get("status", "paid")} for e in expenses]

        total_costs = round(sum(c["amount"] for c in cost_items), 2)
        operating_profit = round(gross - total_costs, 2)
        margin = round((operating_profit / max(gross, 1)) * 100, 1)

        return {
            "month": f"{year}-{mon:02d}",
            "period": {"start": start, "end": end},
            "kpis": {
                "gross": round(gross, 2),
                "room_revenue": room_revenue,
                "adr": adr,
                "commission": commission,
                "total_costs": total_costs,
                "payroll": 0,
                "operating_profit": operating_profit,
                "margin_pct": margin,
            },
            "revenue_items": revenue_items,
            "cost_items": cost_items,
        }

    @router.get("/finance/pl/{property_id}/trend")
    async def get_pl_trend(property_id: str, months: int = 6,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """6-month financial trend chart."""
        now = datetime.now(timezone.utc)
        trend = []

        for i in range(months - 1, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1

            last_day = calendar.monthrange(y, m)[1]
            start = f"{y}-{m:02d}-01"
            end = f"{y}-{m:02d}-{last_day}"

            bk_query = {"status": {"$nin": ["cancelled"]}, "check_in": {"$gte": start, "$lte": end}}
            if property_id != "all":
                bk_query["property_id"] = property_id

            bookings = await db.bookings.find(bk_query, {"_id": 0, "total_price": 1, "nights": 1}).to_list(5000)
            revenue = round(sum(float(b.get("total_price", 0) or 0) for b in bookings), 2)
            room_nights = sum(int(b.get("nights", 1) or 1) for b in bookings)

            # Estimate costs
            total_rooms = 10
            if property_id != "all":
                total_rooms = await db.rooms.count_documents({"property_id": property_id}) or 10
            costs = round(total_rooms * 350 + revenue * 0.15 + room_nights * 5, 2)
            profit = round(revenue - costs, 2)

            month_label = datetime(y, m, 1).strftime("%b %Y")
            trend.append({"month": f"{y}-{m:02d}", "label": month_label, "revenue": revenue, "costs": costs, "profit": profit})

        return {"trend": trend, "months": months}

    @router.get("/finance/expenses/{property_id}")
    async def get_expenses(property_id: str, month: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Monthly expenses list."""
        now = datetime.now(timezone.utc)
        if not month:
            month = f"{now.year}-{now.month:02d}"

        expenses = await db.expenses.find({"month": month}, {"_id": 0}).sort("created_at", -1).to_list(200)
        total = round(sum(float(e.get("amount", 0)) for e in expenses), 2)
        paid = round(sum(float(e.get("amount", 0)) for e in expenses if e.get("status") == "paid"), 2)
        pending = round(total - paid, 2)

        return {"month": month, "expenses": expenses, "total": total, "paid": paid, "pending": pending}

    @router.post("/finance/expenses/{property_id}")
    async def add_expense(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Add an expense."""
        now = datetime.now(timezone.utc)
        expense = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "category": data.get("category", "Other"),
            "description": data.get("description", ""),
            "amount": float(data.get("amount", 0)),
            "status": data.get("status", "pending"),
            "month": data.get("month", now.strftime("%Y-%m")),
            "recurring": data.get("recurring", False),
            "created_at": now.isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.expenses.insert_one(dict(expense))
        return expense

    return router
