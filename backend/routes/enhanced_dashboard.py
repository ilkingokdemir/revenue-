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

    return router
