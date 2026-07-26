"""
Displacement Analysis — Evaluates group booking requests vs holding rooms
for potentially higher-paying individual guests.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_displacement_router(db, require_roles):
    router = APIRouter()

    @router.post("/revenue/displacement/analyze")
    async def analyze_displacement(data: Dict,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Analyze whether to accept a group booking or hold for individuals."""
        property_id = data.get("property_id", "all")
        check_in = data.get("check_in", "")
        check_out = data.get("check_out", "")
        rooms_requested = int(data.get("rooms_requested", 5))
        group_rate = float(data.get("group_rate", 80))
        group_name = data.get("group_name", "Group Booking")

        if not check_in or not check_out:
            return {"error": "check_in and check_out required"}

        ci = datetime.strptime(check_in, "%Y-%m-%d")
        co = datetime.strptime(check_out, "%Y-%m-%d")
        nights = max(1, (co - ci).days)

        # Get total rooms
        if property_id == "all":
            props = await db.properties.find({}, {"_id": 0}).to_list(50)
            pid = props[0].get("id", "default") if props else "default"
        else:
            pid = property_id

        total_rooms = 0
        for rt in await db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1}).to_list(50):
            total_rooms += int(rt.get("total_rooms", 0))
        if total_rooms == 0:
            total_rooms = await db.rooms.count_documents({"property_id": pid})
        if total_rooms == 0:
            rt_count = await db.room_types.count_documents({"property_id": pid})
            total_rooms = rt_count * 3

        # Calculate group revenue
        group_total_revenue = group_rate * rooms_requested * nights
        group_adr = group_rate

        # Estimate individual revenue using historical data
        bookings = await db.bookings.find(
            {"room_id": {"$exists": True, "$ne": ""}, "rate_per_night": {"$gt": 0}},
            {"_id": 0, "rate_per_night": 1, "nights": 1, "check_in": 1}
        ).to_list(500)

        if bookings:
            avg_individual_rate = sum(b["rate_per_night"] for b in bookings) / len(bookings)
            avg_individual_nights = sum(b.get("nights", 1) for b in bookings) / len(bookings)
        else:
            avg_individual_rate = group_rate * 1.3
            avg_individual_nights = 2

        # Get demand data for the requested dates
        supply_docs = await db.market_supply.find(
            {"$or": [{"property_id": pid}, {"property_id": "all"}]},
            {"_id": 0}
        ).to_list(500)
        supply_map = {}
        for s in supply_docs:
            if s["date"] not in supply_map:
                supply_map[s["date"]] = s

        demand_scores = []
        for i in range(nights):
            d = ci + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            sup = supply_map.get(ds, {})
            demand = sup.get("unavailable_pct", 50)
            demand_scores.append(demand)

        avg_demand = sum(demand_scores) / max(len(demand_scores), 1)

        # Estimate fill probability based on demand
        fill_probability = min(95, max(20, avg_demand * 1.1))

        # Calculate displacement revenue (what we'd earn from individuals)
        expected_individual_rooms = rooms_requested * (fill_probability / 100)
        individual_total_revenue = round(expected_individual_rooms * avg_individual_rate * avg_individual_nights, 2)

        # Net displacement cost
        displacement_cost = round(individual_total_revenue - group_total_revenue, 2)

        # Decision score (positive = accept group, negative = reject)
        if displacement_cost > 0:
            recommendation = "REJECT"
            reason = f"Holding rooms for individuals is expected to generate £{displacement_cost:.0f} MORE revenue"
            confidence = min(95, int(fill_probability))
        elif displacement_cost < -group_total_revenue * 0.1:
            recommendation = "ACCEPT"
            reason = f"Group booking generates £{abs(displacement_cost):.0f} MORE than expected individual bookings"
            confidence = min(95, int(100 - fill_probability))
        else:
            recommendation = "NEUTRAL"
            reason = "Revenue difference is minimal — consider strategic factors (relationship, F&B spend, low season)"
            confidence = 50

        # Daily breakdown
        daily_analysis = []
        for i in range(nights):
            d = ci + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            demand = demand_scores[i] if i < len(demand_scores) else 50
            daily_analysis.append({
                "date": ds,
                "dow": d.strftime("%a"),
                "demand": round(demand),
                "group_revenue": round(group_rate * rooms_requested, 2),
                "est_individual_revenue": round(avg_individual_rate * expected_individual_rooms, 2),
                "fill_prob": round(min(95, demand * 1.1)),
            })

        # Risk factors
        risks = []
        if fill_probability < 40:
            risks.append({"type": "low_demand", "text": "Low demand period — group booking provides guaranteed revenue", "impact": "positive"})
        if fill_probability > 75:
            risks.append({"type": "high_demand", "text": "High demand period — individual bookings likely at premium rates", "impact": "negative"})
        if rooms_requested > total_rooms * 0.3 and total_rooms > 0:
            risks.append({"type": "capacity", "text": f"Group would consume {round(rooms_requested/total_rooms*100)}% of total capacity", "impact": "warning"})
        if nights >= 5:
            risks.append({"type": "long_stay", "text": "Long group stay reduces flexibility for other bookings", "impact": "warning"})
        if group_rate < avg_individual_rate * 0.7:
            risks.append({"type": "deep_discount", "text": f"Group rate is {round((1-group_rate/avg_individual_rate)*100)}% below avg individual rate", "impact": "negative"})

        # ── Blended-rate optimization (FLYR Groups parity) ──
        room_nights = rooms_requested * nights
        breakeven_rate = round(individual_total_revenue / room_nights, 2) if room_nights else 0.0
        recommended_rate = round(breakeven_rate * 1.08, 2)
        lrv_floor = 0.0
        try:
            from routes.revenue_ext.hurdle_lrv import compute_lrv_floor
            today = datetime.now(timezone.utc).date()
            horizon = min(max((co.date() - today).days + 1, 1), 90)
            lrv_map = await compute_lrv_floor(db, pid, horizon)
            floors = [float(lrv_map.get((ci + timedelta(days=i)).strftime("%Y-%m-%d")) or 0) for i in range(nights)]
            lrv_floor = round(max(floors or [0.0]), 2)
        except Exception as ex:
            logger.warning("LRV floor lookup failed: %s", ex)
        if avg_individual_rate:
            recommended_rate = min(recommended_rate, round(avg_individual_rate, 2))
        if lrv_floor:
            recommended_rate = max(recommended_rate, lrv_floor)
        recommended_rate = round(recommended_rate, 2)

        # Forecast impact: occupancy before/after accepting the group
        occ_counts = []
        for i in range(nights):
            ds = (ci + timedelta(days=i)).strftime("%Y-%m-%d")
            booked = await db.bookings.count_documents({
                "property_id": pid, "status": {"$in": ["confirmed", "checked_in"]},
                "check_in": {"$lte": ds}, "check_out": {"$gt": ds}})
            occ_counts.append(booked)
        avg_booked = sum(occ_counts) / max(len(occ_counts), 1)
        occ_before_pct = round(avg_booked / total_rooms * 100, 1) if total_rooms else 0.0
        occ_after_pct = round(min((avg_booked + rooms_requested) / total_rooms * 100, 100), 1) if total_rooms else 0.0

        # Blended ADR after accepting group (kalan odalar bireysel satılır varsayımı)
        remaining = max(total_rooms - int(avg_booked) - rooms_requested, 0)
        expected_ind_sold = remaining * (fill_probability / 100)
        blended_denom = rooms_requested + expected_ind_sold
        blended_adr = round((group_rate * rooms_requested + avg_individual_rate * expected_ind_sold) / blended_denom, 2) if blended_denom else group_rate

        blended = {
            "breakeven_rate": breakeven_rate,
            "recommended_rate": recommended_rate,
            "lrv_floor": lrv_floor,
            "requested_rate": group_rate,
            "rate_verdict": "above" if group_rate >= recommended_rate else ("near" if group_rate >= breakeven_rate else "below"),
            "uplift_if_recommended": round(max(recommended_rate - group_rate, 0) * room_nights, 2),
            "blended_adr_after": blended_adr,
            "occ_before_pct": occ_before_pct,
            "occ_after_pct": occ_after_pct,
        }

        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "reason": reason,
            "group_name": group_name,
            "group": {
                "rooms": rooms_requested,
                "rate": group_rate,
                "nights": nights,
                "total_revenue": group_total_revenue,
                "adr": group_adr,
            },
            "individual": {
                "avg_rate": round(avg_individual_rate, 2),
                "avg_nights": round(avg_individual_nights, 1),
                "expected_fill_rooms": round(expected_individual_rooms, 1),
                "fill_probability": round(fill_probability),
                "total_revenue": individual_total_revenue,
            },
            "displacement_cost": displacement_cost,
            "blended": blended,
            "avg_demand": round(avg_demand),
            "total_rooms": total_rooms,
            "daily_analysis": daily_analysis,
            "risks": risks,
        }

    @router.get("/revenue/displacement/history")
    async def displacement_history(current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get past displacement analyses."""
        history = await db.displacement_analyses.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"analyses": history}

    @router.post("/revenue/displacement/save")
    async def save_analysis(data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Save a displacement analysis decision."""
        record = {
            "id": str(uuid.uuid4()),
            "group_name": data.get("group_name", ""),
            "recommendation": data.get("recommendation", ""),
            "decision": data.get("decision", ""),
            "group_revenue": data.get("group_revenue", 0),
            "displacement_cost": data.get("displacement_cost", 0),
            "notes": data.get("notes", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.displacement_analyses.insert_one(record)
        record.pop("_id", None)
        return record

    return router
