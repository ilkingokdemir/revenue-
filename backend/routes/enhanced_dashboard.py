"""
Enhanced Dashboard API — Financial overview, staff on duty, HK completion,
daily revenue chart, reservations widget with YoY comparison.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def create_enhanced_dashboard_router(db, require_roles):
    router = APIRouter()

    @router.get("/dashboard/enhanced/{property_id}")
    async def get_enhanced_dashboard(property_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Full enhanced dashboard with financial overview, staff, HK, revenue chart."""
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        bk_query = {"status": {"$nin": ["cancelled"]}}
        if property_id != "all":
            bk_query["property_id"] = property_id

        # Total rooms
        total_rooms = 0
        if property_id != "all":
            total_rooms = await db.rooms.count_documents({"property_id": property_id})
        if total_rooms == 0:
            q = {} if property_id == "all" else {"property_id": property_id}
            total_rooms = max(await db.room_types.count_documents(q) * 3, 10)

        # Today's in-house
        in_house = await db.bookings.find(
            {**bk_query, "check_in": {"$lte": today}, "check_out": {"$gt": today}},
            {"_id": 0, "rate_per_night": 1, "total_price": 1, "guest_name": 1, "source": 1, "status": 1, "check_in": 1, "check_out": 1, "nights": 1, "room_type_id": 1}
        ).to_list(500)
        in_house_count = sum(1 for b in in_house if b.get("status") == "checked_in")
        occ_pct = round((len(in_house) / max(total_rooms, 1)) * 100)
        daily_income = round(sum(float(b.get("rate_per_night", 0) or 0) for b in in_house), 2)

        arrivals_today = await db.bookings.count_documents({**bk_query, "check_in": today})
        departures_today = await db.bookings.count_documents({**bk_query, "check_out": today})

        # === FINANCIAL OVERVIEW (This Month vs Previous vs Next) ===
        this_month_start = now.replace(day=1).strftime("%Y-%m-%d")
        if now.month == 12:
            next_month_start = f"{now.year + 1}-01-01"
        else:
            next_month_start = f"{now.year}-{now.month + 1:02d}-01"
        prev_month_end = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")
        if now.month == 12:
            next_month_end = f"{now.year + 1}-01-31"
        else:
            import calendar
            nm = now.month + 1 if now.month < 12 else 1
            ny = now.year if now.month < 12 else now.year + 1
            last_day = calendar.monthrange(ny, nm)[1]
            next_month_end = f"{ny}-{nm:02d}-{last_day}"

        async def month_revenue(start, end):
            bks = await db.bookings.find(
                {**bk_query, "check_in": {"$gte": start, "$lte": end}},
                {"_id": 0, "total_price": 1, "rate_per_night": 1, "nights": 1, "source": 1}
            ).to_list(2000)
            gross = sum(float(b.get("total_price", 0) or 0) for b in bks)
            room_rev = gross
            count = len(bks)
            room_nights = sum(int(b.get("nights", 1) or 1) for b in bks)
            adr = round(room_rev / max(room_nights, 1), 2)
            commission = round(gross * 0.15, 2)
            net = round(gross - commission, 2)
            return {"gross": round(gross, 2), "room_revenue": round(room_rev, 2), "adr": adr, "commission": commission, "net": net, "bookings": count, "room_nights": room_nights}

        this_month = await month_revenue(this_month_start, next_month_start)
        prev_month = await month_revenue(prev_month_start, prev_month_end)
        next_month = await month_revenue(next_month_start, next_month_end)

        # YoY comparison (same month last year)
        last_year_start = f"{now.year - 1}-{now.month:02d}-01"
        if now.month == 12:
            last_year_end = f"{now.year}-01-01"
        else:
            last_year_end = f"{now.year - 1}-{now.month + 1:02d}-01"
        last_year = await month_revenue(last_year_start, last_year_end)

        # === Last 3 Years (36 months ending today) ===
        three_yr_start = f"{now.year - 3}-{now.month:02d}-01"
        last_3y = await month_revenue(three_yr_start, today)

        # === 7-DAY REVENUE CHART ===
        daily_revenue = []
        total_7d = 0
        for i in range(6, -1, -1):
            d = now - timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            day_bks = await db.bookings.find(
                {**bk_query, "check_in": {"$lte": ds}, "check_out": {"$gt": ds}},
                {"_id": 0, "rate_per_night": 1}
            ).to_list(500)
            rev = round(sum(float(b.get("rate_per_night", 0) or 0) for b in day_bks), 2)
            total_7d += rev
            daily_revenue.append({"date": ds, "dow": d.strftime("%a"), "revenue": rev, "bookings": len(day_bks)})

        # === STAFF ON DUTY ===
        staff = await db.users.find(
            {"role": {"$in": ["receptionist", "housekeeper", "maintenance"]}},
            {"_id": 0, "name": 1, "role": 1, "email": 1}
        ).to_list(20)
        staff_on_duty = [{"name": s.get("name", ""), "role": s.get("role", ""), "email": s.get("email", "")} for s in staff[:8]]

        # === HOUSEKEEPING WIDGET ===
        hk_query = {"property_id": property_id} if property_id != "all" else {}
        rooms_all = await db.rooms.find(hk_query, {"_id": 0, "housekeeping": 1}).to_list(200)
        hk_clean = sum(1 for r in rooms_all if r.get("housekeeping") in ["clean", "inspected"])
        hk_dirty = sum(1 for r in rooms_all if r.get("housekeeping") == "dirty")
        hk_total = len(rooms_all) or total_rooms
        hk_pct = round((hk_clean / max(hk_total, 1)) * 100)

        # === RECENT BOOKINGS (Last 24h) ===
        yesterday = (now - timedelta(hours=24)).isoformat()
        recent = await db.bookings.find(
            {"created_at": {"$gte": yesterday}},
            {"_id": 0, "id": 1, "guest_name": 1, "check_in": 1, "check_out": 1, "nights": 1, "total_price": 1, "source": 1, "status": 1, "room_type_id": 1}
        ).sort("created_at", -1).to_list(20)

        # === PENDING PAYMENTS ===
        pending_payment = await db.bookings.count_documents({**bk_query, "payment_status": {"$in": ["pending", "partial"]}})

        return {
            "date": today,
            "kpis": {
                "in_house_guests": in_house_count,
                "occupancy_pct": occ_pct,
                "arrivals_today": arrivals_today,
                "departures_today": departures_today,
                "daily_income": daily_income,
                "total_rooms": total_rooms,
                "pending_payment": pending_payment,
            },
            "financial_overview": {
                "this_month": this_month,
                "previous_month": prev_month,
                "next_month": next_month,
                "same_month_last_year": last_year,
                "last_3_years": last_3y,
            },
            "daily_revenue_7d": daily_revenue,
            "total_7d_revenue": round(total_7d, 2),
            "avg_daily_revenue": round(total_7d / 7, 2),
            "staff_on_duty": staff_on_duty,
            "housekeeping": {
                "clean": hk_clean,
                "dirty": hk_dirty,
                "total": hk_total,
                "completion_pct": hk_pct,
            },
            "recent_bookings": recent[:10],
            "stayovers": len(in_house) - arrivals_today,
        }

    @router.get("/dashboard/financial-history")
    async def financial_history(
        property_id: str = "all",
        range: str = "last_12m",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist")),
    ):
        """Historical monthly revenue / commission / expenses / payroll / net-profit trend.

        Windows: last_month | last_3m | last_6m | last_12m | ytd | last_3y | last_5y
        """
        now = datetime.now(timezone.utc)
        today = now.date()

        window_months = {
            "last_month": 1, "last_3m": 3, "last_6m": 6,
            "last_12m": 12, "ytd": today.month, "last_3y": 36, "last_5y": 60,
        }.get(range, 12)

        # Build month boundaries going back N months (inclusive of current month)
        from calendar import monthrange

        def month_start(y, m):
            return datetime(y, m, 1, tzinfo=timezone.utc)

        def add_months(dt, delta):
            m = dt.month - 1 + delta
            y = dt.year + m // 12
            m = m % 12 + 1
            return month_start(y, m)

        start_dt = add_months(month_start(today.year, today.month), -(window_months - 1))

        # Query bookings that checked_in during the window
        bk_query = {
            "status": {"$nin": ["cancelled"]},
            "check_in": {"$gte": start_dt.strftime("%Y-%m-%d"), "$lte": today.isoformat()},
        }
        if property_id != "all":
            bk_query["property_id"] = property_id

        bookings = await db.bookings.find(
            bk_query,
            {"_id": 0, "check_in": 1, "total_price": 1, "source": 1, "nights": 1, "property_id": 1},
        ).to_list(length=50000)

        # Query expenses + payroll for same window
        exp_query = {"date": {"$gte": start_dt.strftime("%Y-%m-%d"), "$lte": today.isoformat()}}
        if property_id != "all":
            exp_query["property_id"] = property_id
        expenses = await db.expenses.find(exp_query, {"_id": 0, "date": 1, "amount": 1}).to_list(length=20000)

        pay_query = {"pay_period_end": {"$gte": start_dt.strftime("%Y-%m-%d"), "$lte": today.isoformat()}}
        payroll = await db.payroll_runs.find(pay_query, {"_id": 0, "pay_period_end": 1, "total_gross": 1, "total_net": 1}).to_list(length=5000)

        # Commission rates (same as Profit OS defaults)
        COMM = {
            "Booking.com": 0.15, "Expedia": 0.18, "Airbnb": 0.03, "Agoda": 0.17,
            "Hotelbeds": 0.22, "Google": 0.12, "Affiliate": 0.08, "Hotels.com": 0.15,
        }

        # Aggregate by month key YYYY-MM
        months_map = {}
        cursor = start_dt
        while cursor.date() <= today.replace(day=1):
            k = cursor.strftime("%Y-%m")
            months_map[k] = {
                "month": k,
                "label": cursor.strftime("%b %Y"),
                "gross_revenue": 0.0, "commission": 0.0, "net_revenue": 0.0,
                "expenses": 0.0, "payroll": 0.0, "net_profit": 0.0, "bookings": 0,
            }
            cursor = add_months(cursor, 1)

        for b in bookings:
            ci = b.get("check_in") or ""
            if len(ci) < 7:
                continue
            mk = ci[:7]
            if mk not in months_map:
                continue
            gross = float(b.get("total_price") or 0)
            src = b.get("source") or ""
            comm = gross * COMM.get(src, 0.0)
            months_map[mk]["gross_revenue"] += gross
            months_map[mk]["commission"] += comm
            months_map[mk]["net_revenue"] += (gross - comm)
            months_map[mk]["bookings"] += 1

        for e in expenses:
            ed = e.get("date") or ""
            if len(ed) < 7:
                continue
            mk = ed[:7]
            if mk in months_map:
                months_map[mk]["expenses"] += float(e.get("amount") or 0)

        for p in payroll:
            pd = p.get("pay_period_end") or ""
            if len(pd) < 7:
                continue
            mk = pd[:7]
            if mk in months_map:
                months_map[mk]["payroll"] += float(p.get("total_gross") or p.get("total_net") or 0)

        # Compute net_profit + round
        series = []
        for k in sorted(months_map.keys()):
            m = months_map[k]
            m["net_profit"] = m["net_revenue"] - m["expenses"] - m["payroll"]
            for f in ["gross_revenue", "commission", "net_revenue", "expenses", "payroll", "net_profit"]:
                m[f] = round(m[f], 2)
            series.append(m)

        # Totals
        totals = {
            "gross_revenue": round(sum(m["gross_revenue"] for m in series), 2),
            "commission":    round(sum(m["commission"] for m in series), 2),
            "net_revenue":   round(sum(m["net_revenue"] for m in series), 2),
            "expenses":      round(sum(m["expenses"] for m in series), 2),
            "payroll":       round(sum(m["payroll"] for m in series), 2),
            "net_profit":    round(sum(m["net_profit"] for m in series), 2),
            "bookings":      sum(m["bookings"] for m in series),
        }

        # Previous period comparison (same length window before start_dt)
        prev_end = start_dt - timedelta(days=1)
        prev_start = add_months(month_start(prev_end.year, prev_end.month), -(window_months - 1))
        prev_bk_query = {
            "status": {"$nin": ["cancelled"]},
            "check_in": {"$gte": prev_start.strftime("%Y-%m-%d"), "$lte": prev_end.strftime("%Y-%m-%d")},
        }
        if property_id != "all":
            prev_bk_query["property_id"] = property_id
        prev_bookings = await db.bookings.find(prev_bk_query, {"_id": 0, "total_price": 1, "source": 1}).to_list(length=50000)
        prev_gross = sum(float(b.get("total_price") or 0) for b in prev_bookings)
        prev_comm = sum(float(b.get("total_price") or 0) * COMM.get(b.get("source", ""), 0.0) for b in prev_bookings)
        prev_net = prev_gross - prev_comm
        yoy_pct = ((totals["net_revenue"] - prev_net) / prev_net * 100.0) if prev_net else 0.0

        return {
            "range": range,
            "window_months": window_months,
            "start": start_dt.strftime("%Y-%m-%d"),
            "end": today.isoformat(),
            "series": series,
            "totals": totals,
            "prev_period": {
                "gross_revenue": round(prev_gross, 2),
                "net_revenue":   round(prev_net, 2),
                "bookings":      len(prev_bookings),
            },
            "delta": {
                "net_revenue_pct": round(yoy_pct, 2),
                "net_revenue_abs": round(totals["net_revenue"] - prev_net, 2),
            },
        }

    return router
