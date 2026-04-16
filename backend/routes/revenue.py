"""
Revenue Management — Dashboard, Occupancy Heatmap, YOY Analysis, Rate Calendar,
Price Chart, Pricing Strategy (Rooms Setup, Day-of-Week, Monthly, Occupancy)
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import calendar
import logging

logger = logging.getLogger(__name__)


def create_revenue_router(db, require_roles):
    router = APIRouter()

    # ==================== DASHBOARD KPIs ====================

    @router.get("/revenue/dashboard/{property_id}")
    async def revenue_dashboard(property_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await db.properties.find({}, {"_id": 0}).to_list(50) if property_id == "all" else [await db.properties.find_one({"id": property_id}, {"_id": 0})]
        props = [p for p in props if p]

        async def month_stats(year, month, props_list):
            first = f"{year}-{month:02d}-01"
            last_day = calendar.monthrange(year, month)[1]
            last = f"{year}-{month:02d}-{last_day}"
            total_rev = 0
            total_nights = 0
            total_capacity = 0
            for p in props_list:
                pid = p.get("id", "")
                bks = await db.bookings.find({"property_id": pid, "check_in": {"$lte": last}, "check_out": {"$gte": first}}, {"_id": 0}).to_list(500)
                rev = sum(float(b.get("total_price", 0) or 0) for b in bks)
                total_rev += rev
                nights = sum(max(1, int(b.get("nights", 1) or 1)) for b in bks)
                total_nights += nights
                rooms = await db.rooms.count_documents({"property_id": pid})
                total_capacity += rooms * last_day
            occ = round((total_nights / max(total_capacity, 1)) * 100) if total_capacity > 0 else 0
            adr = round(total_rev / max(total_nights, 1), 2) if total_nights > 0 else 0
            return {"revenue": round(total_rev, 2), "occupancy": occ, "adr": adr, "nights_sold": total_nights, "capacity": total_capacity}

        # Current month
        cm = await month_stats(now.year, now.month, props)
        # Last month
        lm_date = now.replace(day=1) - timedelta(days=1)
        lm = await month_stats(lm_date.year, lm_date.month, props)
        # Next month
        if now.month == 12:
            nm = await month_stats(now.year + 1, 1, props)
        else:
            nm = await month_stats(now.year, now.month + 1, props)
        # YOY
        cm_ly = await month_stats(now.year - 1, now.month, props)
        lm_ly = await month_stats(lm_date.year - 1, lm_date.month, props)
        nm_month = now.month + 1 if now.month < 12 else 1
        nm_year = now.year if now.month < 12 else now.year + 1
        nm_ly = await month_stats(nm_year - 1, nm_month, props)

        def yoy(curr, prev):
            if prev <= 0: return 0
            return round(((curr - prev) / prev) * 100, 1)

        return {
            "last_month": {**lm, "label": lm_date.strftime("%B"), "yoy": yoy(lm["revenue"], lm_ly["revenue"])},
            "current_month": {**cm, "label": now.strftime("%B (MTD)"), "yoy": yoy(cm["revenue"], cm_ly["revenue"])},
            "next_month": {**nm, "label": (datetime(nm_year, nm_month, 1)).strftime("%B"), "yoy": yoy(nm["revenue"], nm_ly["revenue"])},
            "properties_count": len(props),
        }

    # ==================== OCCUPANCY HEATMAP ====================

    @router.get("/revenue/heatmap")
    async def occupancy_heatmap(days: int = 30, view: str = "occupancy",
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await db.properties.find({}, {"_id": 0}).to_list(50)
        dates = []
        for i in range(days):
            d = now + timedelta(days=i)
            dates.append(d.strftime("%Y-%m-%d"))

        result = []
        for p in props:
            pid = p.get("id", "")
            pname = p.get("name", pid)
            total_rooms = await db.rooms.count_documents({"property_id": pid})
            if total_rooms == 0:
                total_rooms = 10
            daily = []
            for dt in dates:
                booked = await db.bookings.count_documents({
                    "property_id": pid, "check_in": {"$lte": dt}, "check_out": {"$gt": dt},
                    "status": {"$ne": "cancelled"}
                })
                occ = min(100, round((booked / total_rooms) * 100))
                bks = await db.bookings.find({"property_id": pid, "check_in": {"$lte": dt}, "check_out": {"$gt": dt}}, {"_id": 0, "total_price": 1, "nights": 1}).to_list(100)
                rev = sum(float(b.get("total_price", 0) or 0) / max(int(b.get("nights", 1) or 1), 1) for b in bks)
                adr = round(rev / max(booked, 1), 2) if booked > 0 else 0
                daily.append({"date": dt, "occupancy": occ, "adr": adr, "booked": booked, "available": max(0, total_rooms - booked)})
            result.append({"property_id": pid, "name": pname, "total_rooms": total_rooms, "daily": daily})

        return {"dates": dates, "properties": result}

    # ==================== YOY PROPERTY TABLES ====================

    @router.get("/revenue/yoy-tables")
    async def yoy_tables(current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        props = await db.properties.find({}, {"_id": 0}).to_list(50)
        tables = []
        for p in props:
            pid = p.get("id", "")
            total_rooms = await db.rooms.count_documents({"property_id": pid}) or 10
            months = []
            for m in range(1, 7):
                # Current year
                first = f"{now.year}-{m:02d}-01"
                last_day = calendar.monthrange(now.year, m)[1]
                last = f"{now.year}-{m:02d}-{last_day}"
                bks = await db.bookings.find({"property_id": pid, "check_in": {"$lte": last}, "check_out": {"$gte": first}}, {"_id": 0}).to_list(500)
                rev = sum(float(b.get("total_price", 0) or 0) for b in bks)
                nights = sum(max(1, int(b.get("nights", 1) or 1)) for b in bks)
                occ = min(100, round((nights / max(total_rooms * last_day, 1)) * 100))
                adr = round(rev / max(nights, 1), 2) if nights > 0 else 0
                # Last year
                first_ly = f"{now.year - 1}-{m:02d}-01"
                last_ly = f"{now.year - 1}-{m:02d}-{last_day}"
                bks_ly = await db.bookings.find({"property_id": pid, "check_in": {"$lte": last_ly}, "check_out": {"$gte": first_ly}}, {"_id": 0}).to_list(500)
                rev_ly = sum(float(b.get("total_price", 0) or 0) for b in bks_ly)
                var_pct = round(((rev - rev_ly) / max(rev_ly, 1)) * 100, 1) if rev_ly > 0 else (100 if rev > 0 else 0)
                months.append({
                    "month": calendar.month_name[m],
                    "prev_rev": round(rev_ly, 2),
                    "curr_occ": occ,
                    "curr_adr": adr,
                    "curr_rev": round(rev, 2),
                    "variance": var_pct,
                    "is_current": m == now.month,
                })
            tables.append({"property_id": pid, "name": p.get("name", pid), "total_rooms": total_rooms, "months": months})
        return tables

    # ==================== RATE CALENDAR (like RoomPriceGenie) ====================

    @router.get("/revenue/rate-calendar/{property_id}")
    async def rate_calendar(property_id: str, year: int = 0, month: int = 0, room_type: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if year == 0: year = now.year
        if month == 0: month = now.month
        last_day = calendar.monthrange(year, month)[1]

        total_rooms = await db.rooms.count_documents({"property_id": property_id}) or 10
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if room_type and room_types:
            rt = next((r for r in room_types if r.get("id") == room_type), room_types[0] if room_types else None)
        else:
            rt = room_types[0] if room_types else {"id": "default", "name": "Standard", "base_rate": 100}

        # Monthly performance
        first = f"{year}-{month:02d}-01"
        last = f"{year}-{month:02d}-{last_day}"
        bks = await db.bookings.find({"property_id": property_id, "check_in": {"$lte": last}, "check_out": {"$gte": first}}, {"_id": 0}).to_list(500)
        total_nights = sum(max(1, int(b.get("nights", 1) or 1)) for b in bks)
        month_occ = min(100, round((total_nights / max(total_rooms * last_day, 1)) * 100))
        today_idx = now.day if year == now.year and month == now.month else last_day
        expected_occ = min(100, round((total_nights / max(total_rooms * today_idx, 1)) * 100))

        days = []
        for d in range(1, last_day + 1):
            dt = f"{year}-{month:02d}-{d:02d}"
            booked = await db.bookings.count_documents({"property_id": property_id, "check_in": {"$lte": dt}, "check_out": {"$gt": dt}, "status": {"$ne": "cancelled"}})
            occ = min(100, round((booked / max(total_rooms, 1)) * 100))
            base = float(rt.get("base_rate", 100) or 100)
            # Simple dynamic pricing based on occupancy
            if occ >= 90: recommended = round(base * 1.4, 2)
            elif occ >= 75: recommended = round(base * 1.2, 2)
            elif occ >= 50: recommended = round(base * 1.0, 2)
            elif occ >= 25: recommended = round(base * 0.85, 2)
            else: recommended = round(base * 0.7, 2)
            is_full = occ >= 100
            is_today = dt == now.strftime("%Y-%m-%d")
            dow = datetime(year, month, d).strftime("%a")
            days.append({
                "date": dt, "day": d, "dow": dow, "occupancy": occ, "booked": booked,
                "available": max(0, total_rooms - booked), "is_full": is_full, "is_today": is_today,
                "base_rate": base, "recommended_rate": recommended, "pms_rate": base,
            })

        return {
            "year": year, "month": month, "month_name": calendar.month_name[month],
            "room_type": rt, "room_types": [{"id": r.get("id",""), "name": r.get("name","")} for r in room_types],
            "total_rooms": total_rooms,
            "performance": {"occupancy": month_occ, "expected_by_today": expected_occ, "target": 60},
            "days": days,
        }

    # ==================== PRICING STRATEGY ====================

    @router.get("/revenue/pricing-strategy/{property_id}")
    async def get_pricing_strategy(property_id: str,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        strategy = await db.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0})
        if not strategy:
            strategy = {"property_id": property_id, "dow_adjustments": {}, "monthly_adjustments": {}, "occupancy_rules": []}
        rooms_setup = []
        ref_room = room_types[0] if room_types else None
        for i, rt in enumerate(room_types):
            base = float(rt.get("base_rate", 100) or 100)
            ref_base = float(ref_room.get("base_rate", 100) or 100) if ref_room else base
            deriv = round(base - ref_base, 2) if i > 0 else 0
            rooms_setup.append({
                "id": rt.get("id", ""), "name": rt.get("name", ""), "room_in_pms": rt.get("category", ""),
                "rate_in_pms": "Base Rate", "number_of_rooms": rt.get("count", 0) or (await db.rooms.count_documents({"property_id": property_id, "room_type": rt.get("id", "")})) or 5,
                "reference_derived": "Reference" if i == 0 else "Derived",
                "base_price": base, "derivation": deriv if i > 0 else None,
                "min_price": round(base * 0.7, 2), "max_price": round(base * 2, 2),
            })
        return {"rooms_setup": rooms_setup, "strategy": strategy}

    @router.put("/revenue/pricing-strategy/{property_id}")
    async def update_pricing_strategy(property_id: str, data: Dict,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        data.pop("_id", None)
        data["property_id"] = property_id
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.pricing_strategy.update_one({"property_id": property_id}, {"$set": data}, upsert=True)
        return await db.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0})

    @router.get("/revenue/pricing-strategy-full/{property_id}")
    async def get_full_pricing_strategy(property_id: str,
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get full pricing strategy including lead time, min stay, surge protection, target occupancy."""
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        strategy = await db.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0})
        if not strategy:
            strategy = {
                "property_id": property_id,
                "dow_adjustments": {},
                "monthly_adjustments": {},
                "occupancy_rules": [],
                "lead_time_adjustments": {},
                "target_occupancy": {},
                "aggressiveness": 1.0,
                "min_stay_settings": {"min_stay": 1, "orphan_gap_enabled": False, "fixed_override": False, "room_types": []},
                "surge_protection": {"enabled": False, "booking_threshold": 100, "days_to_go": 30, "recipients": []},
            }
        rooms_setup = []
        ref_room = room_types[0] if room_types else None
        for i, rt in enumerate(room_types):
            base = float(rt.get("base_rate", 100) or 100)
            ref_base = float(ref_room.get("base_rate", 100) or 100) if ref_room else base
            deriv = round(base - ref_base, 2) if i > 0 else 0
            count = rt.get("count", 0) or await db.rooms.count_documents({"property_id": property_id, "room_type": rt.get("id", "")}) or 5
            rooms_setup.append({
                "id": rt.get("id", ""), "name": rt.get("name", ""),
                "room_in_pms": rt.get("category", rt.get("name", "")),
                "rate_in_pms": "Base Rate",
                "number_of_rooms": count,
                "reference_derived": "Reference" if i == 0 else "Derived",
                "base_price": base,
                "derivation": deriv if i > 0 else None,
                "min_price": float(rt.get("min_price", 0) or 0) or round(base * 0.7, 2),
                "max_price": float(rt.get("max_price", 0) or 0) or round(base * 2, 2),
            })
        return {
            "rooms_setup": rooms_setup,
            "strategy": strategy,
            "room_types": [{"id": r.get("id", ""), "name": r.get("name", "")} for r in room_types],
        }

    return router
