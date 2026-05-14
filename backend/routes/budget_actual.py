"""
Budget vs Actual Reports — monthly budget input and YoY comparison.

Endpoints:
  GET   /api/budget/{property_id}/{year}        — annual budget grid
  PUT   /api/budget/{property_id}/{year}        — bulk update monthly budgets
  GET   /api/budget/{property_id}/variance      — actual vs budget variance
  GET   /api/budget/{property_id}/yoy           — year-over-year comparison
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends


def create_budget_router(db, require_roles):
    router = APIRouter(prefix="/budget")

    # NOTE: More specific routes (variance, yoy) must be defined BEFORE the generic /{property_id}/{year}
    # to avoid FastAPI matching "variance" or "yoy" as the year parameter.

    @router.get("/{property_id}/variance")
    async def get_variance(property_id: str, year: str = "",
                           _: dict = Depends(require_roles("admin", "manager"))):
        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        budgets = await db.budget_monthly.find(
            {"property_id": property_id, "year": year},
            {"_id": 0}
        ).to_list(20)
        budget_map = {b["month"]: b for b in budgets}
        # Actuals from bookings
        rows = []
        for m in range(1, 13):
            month_key = f"{m:02d}"
            prefix = f"{year}-{month_key}"
            bookings = await db.bookings.find(
                {"property_id": property_id,
                 "check_in": {"$regex": f"^{prefix}"},
                 "status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]}},
                {"_id": 0, "total_price": 1, "nights": 1}
            ).to_list(2000)
            actual_revenue = round(sum(float(b.get("total_price", 0)) for b in bookings), 2)
            actual_nights = sum(int(b.get("nights", 1)) for b in bookings)
            actual_adr = round(actual_revenue / max(1, actual_nights), 2)
            b = budget_map.get(month_key, {})
            rev_budget = float(b.get("revenue_budget", 0))
            rows.append({
                "month": month_key,
                "revenue_budget": rev_budget,
                "revenue_actual": actual_revenue,
                "revenue_variance": round(actual_revenue - rev_budget, 2),
                "revenue_variance_pct": round((actual_revenue - rev_budget) / max(1, rev_budget) * 100, 1) if rev_budget else 0,
                "nights_actual": actual_nights,
                "rooms_budget": int(b.get("rooms_budget", 0)),
                "adr_actual": actual_adr,
                "adr_budget": float(b.get("adr_budget", 0)),
            })
        totals = {
            "revenue_budget": round(sum(r["revenue_budget"] for r in rows), 2),
            "revenue_actual": round(sum(r["revenue_actual"] for r in rows), 2),
            "nights_actual": sum(r["nights_actual"] for r in rows),
        }
        totals["revenue_variance"] = round(totals["revenue_actual"] - totals["revenue_budget"], 2)
        return {"property_id": property_id, "year": year, "rows": rows, "totals": totals}

    @router.get("/{property_id}/yoy")
    async def year_over_year(property_id: str,
                             _: dict = Depends(require_roles("admin", "manager"))):
        this_year = datetime.now(timezone.utc).strftime("%Y")
        last_year = str(int(this_year) - 1)
        rows = []
        for m in range(1, 13):
            month_key = f"{m:02d}"
            this = await db.bookings.aggregate([
                {"$match": {"property_id": property_id,
                            "check_in": {"$regex": f"^{this_year}-{month_key}"},
                            "status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]}}},
                {"$group": {"_id": None, "revenue": {"$sum": "$total_price"}, "n": {"$sum": 1}}},
            ]).to_list(1)
            last = await db.bookings.aggregate([
                {"$match": {"property_id": property_id,
                            "check_in": {"$regex": f"^{last_year}-{month_key}"},
                            "status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]}}},
                {"$group": {"_id": None, "revenue": {"$sum": "$total_price"}, "n": {"$sum": 1}}},
            ]).to_list(1)
            this_rev = round((this[0]["revenue"] if this else 0), 2)
            last_rev = round((last[0]["revenue"] if last else 0), 2)
            rows.append({
                "month": month_key, "this_year": this_rev, "last_year": last_rev,
                "delta": round(this_rev - last_rev, 2),
                "delta_pct": round((this_rev - last_rev) / max(1, last_rev) * 100, 1) if last_rev else 0,
            })
        return {"property_id": property_id, "this_year": this_year, "last_year": last_year, "rows": rows}

    # Generic routes with path parameters must come AFTER specific routes
    @router.get("/{property_id}/{year}")
    async def get_budget(property_id: str, year: str,
                         _: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.budget_monthly.find(
            {"property_id": property_id, "year": year},
            {"_id": 0}
        ).sort("month", 1).to_list(20)
        # Fill missing months
        existing = {r["month"]: r for r in rows}
        full = []
        for m in range(1, 13):
            month_key = f"{m:02d}"
            row = existing.get(month_key, {
                "property_id": property_id, "year": year, "month": month_key,
                "revenue_budget": 0, "rooms_budget": 0, "adr_budget": 0,
                "expense_budget": 0, "noi_budget": 0,
            })
            full.append(row)
        return {"property_id": property_id, "year": year, "rows": full}

    @router.put("/{property_id}/{year}")
    async def update_budget(property_id: str, year: str, body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """body: {rows: [{month: '01', revenue_budget: 50000, ...}, ...]}"""
        rows = body.get("rows") or []
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            month = row.get("month")
            if not month:
                continue
            await db.budget_monthly.update_one(
                {"property_id": property_id, "year": year, "month": month},
                {"$set": {**row, "property_id": property_id, "year": year, "month": month,
                          "updated_by": current_user.get("name", ""), "updated_at": now}},
                upsert=True,
            )
        return {"updated": len(rows)}

    return router
