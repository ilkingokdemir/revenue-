"""
Reports Hub — Revenue Report, Occupancy Report, Commission Report
with chart data, breakdowns by category/source/branch.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import calendar
import logging

logger = logging.getLogger(__name__)


def create_reports_hub_router(db, require_roles):
    router = APIRouter()

    async def _get_bookings(db, property_id, start, end):
        q = {"status": {"$nin": ["cancelled"]}, "check_in": {"$gte": start, "$lt": end}}
        if property_id != "all":
            q["property_id"] = property_id
        return await db.bookings.find(q, {"_id": 0}).to_list(5000)

    async def _total_rooms(db, property_id):
        if property_id != "all":
            c = await db.rooms.count_documents({"property_id": property_id})
            if c:
                return c
        q = {} if property_id == "all" else {"property_id": property_id}
        return max(await db.room_types.count_documents(q) * 3, 10)

    @router.get("/reports/overview/{property_id}")
    async def reports_overview(property_id: str, start: str = "", end: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if not start:
            start = now.replace(day=1).strftime("%Y-%m-%d")
        if not end:
            last_day = calendar.monthrange(now.year, now.month)[1]
            end = f"{now.year}-{now.month:02d}-{last_day}"

        bookings = await _get_bookings(db, property_id, start, end)
        total_rooms = await _total_rooms(db, property_id)

        s_dt = datetime.strptime(start, "%Y-%m-%d")
        e_dt = datetime.strptime(end, "%Y-%m-%d")
        num_days = max((e_dt - s_dt).days, 1)

        room_revenue = round(sum(float(b.get("total_price", 0) or 0) for b in bookings), 2)
        room_nights = sum(int(b.get("nights", 1) or 1) for b in bookings)
        adr = round(room_revenue / max(room_nights, 1), 2)
        occ = round((room_nights / max(total_rooms * num_days, 1)) * 100, 1)
        commission = round(room_revenue * 0.15, 2)

        # By source
        by_source = defaultdict(float)
        for b in bookings:
            by_source[b.get("source", "Direct")] += float(b.get("total_price", 0) or 0)
        source_breakdown = [{"source": k, "revenue": round(v, 2)} for k, v in sorted(by_source.items(), key=lambda x: -x[1])]

        # By room type
        by_type = defaultdict(lambda: {"revenue": 0, "nights": 0, "count": 0})
        rt_names = {}
        rts = await db.room_types.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
        for rt in rts:
            rt_names[rt.get("id", "")] = rt.get("name", "")
        for b in bookings:
            rtid = b.get("room_type_id", "other")
            by_type[rtid]["revenue"] += float(b.get("total_price", 0) or 0)
            by_type[rtid]["nights"] += int(b.get("nights", 1) or 1)
            by_type[rtid]["count"] += 1
        type_breakdown = [{"room_type": rt_names.get(k, k), "revenue": round(v["revenue"], 2), "nights": v["nights"], "bookings": v["count"]} for k, v in sorted(by_type.items(), key=lambda x: -x[1]["revenue"])]

        # Availability by category
        avail_by_cat = []
        for rt in rts:
            rtid = rt.get("id", "")
            rt_rooms = await db.rooms.count_documents({"room_type_id": rtid})
            if rt_rooms == 0:
                rt_rooms = 3
            rt_nights = by_type.get(rtid, {}).get("nights", 0) if rtid in by_type else 0
            rt_occ = round((rt_nights / max(rt_rooms * num_days, 1)) * 100, 1)
            avail_by_cat.append({"category": rt.get("name", rtid), "occupancy_pct": rt_occ, "total_nights": rt_rooms * num_days, "sold": rt_nights})

        return {
            "period": {"start": start, "end": end, "days": num_days},
            "kpis": {"room_revenue": room_revenue, "sold_room_nights": room_nights, "occupancy_rate": occ, "adr": adr, "total_commission": commission},
            "revenue_by_source": source_breakdown,
            "revenue_by_category": type_breakdown,
            "availability_by_category": avail_by_cat,
            "room_availability": {"total": total_rooms * num_days, "sold": room_nights, "available": max(0, total_rooms * num_days - room_nights)},
        }

    @router.get("/reports/revenue/{property_id}")
    async def revenue_report(property_id: str, start: str = "", end: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if not start:
            start = now.replace(day=1).strftime("%Y-%m-%d")
        if not end:
            last_day = calendar.monthrange(now.year, now.month)[1]
            end = f"{now.year}-{now.month:02d}-{last_day}"

        bookings = await _get_bookings(db, property_id, start, end)

        s_dt = datetime.strptime(start, "%Y-%m-%d")
        e_dt = datetime.strptime(end, "%Y-%m-%d")
        num_days = max((e_dt - s_dt).days, 1)

        room_revenue = round(sum(float(b.get("total_price", 0) or 0) for b in bookings), 2)
        avg_period = round(room_revenue / max(num_days, 1), 2)

        # Top source
        by_source = defaultdict(float)
        for b in bookings:
            by_source[b.get("source", "Direct")] += float(b.get("total_price", 0) or 0)
        top_source = max(by_source, key=by_source.get) if by_source else "N/A"
        top_source_rev = round(by_source.get(top_source, 0), 2)

        # Daily timeline
        daily = []
        for i in range(num_days + 1):
            d = s_dt + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            day_bks = [b for b in bookings if b.get("check_in", "") <= ds and (b.get("check_out", "") or "9999") > ds]
            rev = round(sum(float(b.get("rate_per_night", 0) or 0) for b in day_bks), 2)
            daily.append({"date": ds, "dow": d.strftime("%a"), "revenue": rev, "bookings": len(day_bks)})

        # By category
        by_type = defaultdict(float)
        rt_names = {}
        rts = await db.room_types.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
        for rt in rts:
            rt_names[rt.get("id", "")] = rt.get("name", "")
        for b in bookings:
            by_type[b.get("room_type_id", "other")] += float(b.get("total_price", 0) or 0)
        category_breakdown = [{"category": rt_names.get(k, k), "revenue": round(v, 2)} for k, v in sorted(by_type.items(), key=lambda x: -x[1])]
        source_breakdown = [{"source": k, "revenue": round(v, 2)} for k, v in sorted(by_source.items(), key=lambda x: -x[1])]

        return {
            "period": {"start": start, "end": end, "days": num_days},
            "kpis": {"room_revenue": room_revenue, "avg_period": avg_period, "top_source": top_source, "top_source_revenue": top_source_rev},
            "daily_timeline": daily,
            "revenue_by_category": category_breakdown,
            "revenue_by_source": source_breakdown,
        }

    @router.get("/reports/occupancy/{property_id}")
    async def occupancy_report(property_id: str, start: str = "", end: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if not start:
            start = now.replace(day=1).strftime("%Y-%m-%d")
        if not end:
            last_day = calendar.monthrange(now.year, now.month)[1]
            end = f"{now.year}-{now.month:02d}-{last_day}"

        total_rooms = await _total_rooms(db, property_id)
        s_dt = datetime.strptime(start, "%Y-%m-%d")
        e_dt = datetime.strptime(end, "%Y-%m-%d")
        num_days = max((e_dt - s_dt).days, 1)

        bk_query = {"status": {"$nin": ["cancelled"]}}
        if property_id != "all":
            bk_query["property_id"] = property_id

        daily = []
        total_sold = 0
        peak_occ = 0
        peak_date = ""

        for i in range(num_days + 1):
            d = s_dt + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            booked = await db.bookings.count_documents({
                **bk_query, "check_in": {"$lte": ds}, "check_out": {"$gt": ds}
            })
            occ = round((booked / max(total_rooms, 1)) * 100, 1)
            total_sold += booked
            if occ > peak_occ:
                peak_occ = occ
                peak_date = ds
            daily.append({"date": ds, "dow": d.strftime("%a"), "total_rooms": total_rooms, "sold": booked, "occupancy_pct": occ})

        avg_occ = round(total_sold / max(num_days * total_rooms, 1) * 100, 1)
        available = max(0, total_rooms * num_days - total_sold)

        # By category
        rts = await db.room_types.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
        by_cat = []
        for rt in rts:
            rtid = rt.get("id", "")
            rt_rooms = await db.rooms.count_documents({"room_type_id": rtid})
            if rt_rooms == 0:
                rt_rooms = 3
            q2 = {**bk_query, "room_type_id": rtid, "check_in": {"$gte": start, "$lt": end}}
            rt_nights = sum(int(b.get("nights", 1) or 1) for b in await db.bookings.find(q2, {"_id": 0, "nights": 1}).to_list(500))
            rt_occ = round((rt_nights / max(rt_rooms * num_days, 1)) * 100, 1)
            by_cat.append({"category": rt.get("name", rtid), "occupancy_pct": rt_occ, "sold": rt_nights, "capacity": rt_rooms * num_days})

        return {
            "period": {"start": start, "end": end, "days": num_days},
            "kpis": {"avg_occupancy": avg_occ, "sold_room_nights": total_sold, "available_nights": available, "peak_day": peak_date, "peak_occupancy": peak_occ},
            "daily": daily,
            "by_category": by_cat,
            "availability": {"total_capacity": total_rooms * num_days, "sold": total_sold, "available": available},
        }

    @router.get("/reports/commission/{property_id}")
    async def commission_report(property_id: str, start: str = "", end: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if not start:
            start = now.replace(day=1).strftime("%Y-%m-%d")
        if not end:
            last_day = calendar.monthrange(now.year, now.month)[1]
            end = f"{now.year}-{now.month:02d}-{last_day}"

        bookings = await _get_bookings(db, property_id, start, end)

        # Commission rates per source (default 18% for OTAs, 0% for direct)
        ota_sources = {"Booking.com", "Expedia", "Hotels.com", "Agoda", "CTrip", "Airbnb", "Hotelbeds"}
        comm_rates = {}
        for s in ota_sources:
            comm_rates[s] = 0.18
        comm_rates["Direct"] = 0
        comm_rates["Walk-in"] = 0
        comm_rates["Phone"] = 0
        comm_rates["Website"] = 0

        by_source = defaultdict(lambda: {"gross": 0, "bookings": 0})
        for b in bookings:
            src = b.get("source", "Direct")
            by_source[src]["gross"] += float(b.get("total_price", 0) or 0)
            by_source[src]["bookings"] += 1

        source_summary = []
        total_gross = 0
        total_commission = 0
        total_net = 0
        for src, data in sorted(by_source.items(), key=lambda x: -x[1]["gross"]):
            rate = comm_rates.get(src, 0.18 if src in ota_sources else 0)
            gross = round(data["gross"], 2)
            comm = round(gross * rate, 2)
            net = round(gross - comm, 2)
            total_gross += gross
            total_commission += comm
            total_net += net
            source_summary.append({
                "source": src, "gross": gross, "rate_pct": round(rate * 100, 1),
                "commission": comm, "paid": 0, "pending": comm, "net": net, "bookings": data["bookings"],
            })

        return {
            "period": {"start": start, "end": end},
            "kpis": {"gross_bookings": round(total_gross, 2), "net_after_commission": round(total_net, 2), "total_commission": round(total_commission, 2), "pending": round(total_commission, 2), "collection_rate": 0},
            "by_source": source_summary,
        }

    return router
