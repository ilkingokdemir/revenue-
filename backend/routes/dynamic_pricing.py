"""
AI Dynamic Pricing Engine — Combines market supply, competitor data, occupancy,
DOW/monthly adjustments, lead time, and demand patterns to calculate optimal
prices for every day across 90 days. Auto-applies to Rate Calendar.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import math
import logging

logger = logging.getLogger(__name__)


def create_dynamic_pricing_router(db, require_roles):
    router = APIRouter()

    def _impact_rank(impact):
        return {"mega": 4, "large": 3, "medium": 2, "small": 1}.get(impact, 0)

    async def _get_props(property_id):
        if property_id == "all":
            return await db.properties.find({}, {"_id": 0}).to_list(50)
        p = await db.properties.find_one({"id": property_id}, {"_id": 0})
        return [p] if p else []

    async def _total_rooms(props):
        t = 0
        for p in props:
            t += await db.rooms.count_documents({"property_id": p.get("id", "")}) or 10
        return max(t, 1)

    async def _calculate_ai_price(
        base_rate, date_obj, days_ahead, strategy, supply_snap, our_occ, total_rooms, competitor_avg, event_data=None, historical_floor=None
    ):
        """
        AI pricing algorithm combining all data sources (10 factors).
        Returns (final_price, breakdown_dict)
        """
        breakdown = {"base": base_rate}
        price = base_rate

        # 1. DAY-OF-WEEK adjustment
        dow_adj = strategy.get("dow_adjustments", {})
        dow_key = date_obj.strftime("%a").lower()[:3]
        dow_pct = float(dow_adj.get(dow_key, 0))
        if dow_pct != 0:
            price *= (1 + dow_pct / 100)
            breakdown["dow"] = f"{'+' if dow_pct > 0 else ''}{dow_pct}%"

        # 2. MONTHLY adjustment
        monthly_adj = strategy.get("monthly_adjustments", {})
        month_key = date_obj.strftime("%b").lower()[:3]
        month_pct = float(monthly_adj.get(month_key, 0))
        if month_pct != 0:
            price *= (1 + month_pct / 100)
            breakdown["monthly"] = f"{'+' if month_pct > 0 else ''}{month_pct}%"

        # 3. LEAD TIME adjustment
        lt_adj = strategy.get("lead_time_adjustments", {})
        lt_pct = 0
        lt_label = ""
        if days_ahead <= 1:
            lt_pct = float(lt_adj.get("last_day", 0))
            lt_label = "Last Day"
        elif days_ahead <= 3:
            lt_pct = float(lt_adj.get("2_3_days", 0))
            lt_label = "2-3 Days"
        elif days_ahead <= 7:
            lt_pct = float(lt_adj.get("4_7_days", 0))
            lt_label = "4-7 Days"
        elif days_ahead <= 14:
            lt_pct = float(lt_adj.get("1_2_weeks", 0))
            lt_label = "1-2 Weeks"
        elif days_ahead <= 28:
            lt_pct = float(lt_adj.get("2_4_weeks", 0))
            lt_label = "2-4 Weeks"
        elif days_ahead <= 42:
            lt_pct = float(lt_adj.get("4_6_weeks", 0))
            lt_label = "4-6 Weeks"
        elif days_ahead <= 90:
            lt_pct = float(lt_adj.get("1_5_3_months", 0))
            lt_label = "1.5-3 Months"
        else:
            lt_pct = float(lt_adj.get("3_months_plus", 0))
            lt_label = "3 Months+"
        if lt_pct != 0:
            price *= (1 + lt_pct / 100)
            breakdown["lead_time"] = f"{'+' if lt_pct > 0 else ''}{lt_pct}% ({lt_label})"

        # 4. OUR OCCUPANCY adjustment
        occ_pct = 0
        if our_occ >= 90:
            occ_pct = 40
        elif our_occ >= 75:
            occ_pct = 20
        elif our_occ >= 50:
            occ_pct = 0
        elif our_occ >= 25:
            occ_pct = -15
        else:
            occ_pct = -30
        if occ_pct != 0:
            price *= (1 + occ_pct / 100)
            breakdown["our_occupancy"] = f"{'+' if occ_pct > 0 else ''}{occ_pct}% (occ={our_occ}%)"

        # 5. MARKET SUPPLY adjustment (from Market Robot)
        market_pct = 0
        if supply_snap and supply_snap.get("scraped"):
            unavail = supply_snap.get("unavailable_pct", 50)
            if unavail >= 90:
                market_pct = 35
            elif unavail >= 80:
                market_pct = 25
            elif unavail >= 70:
                market_pct = 15
            elif unavail >= 60:
                market_pct = 8
            elif unavail >= 40:
                market_pct = 0
            elif unavail >= 25:
                market_pct = -8
            elif unavail >= 10:
                market_pct = -15
            else:
                market_pct = -25
            if market_pct != 0:
                price *= (1 + market_pct / 100)
                breakdown["market_supply"] = f"{'+' if market_pct > 0 else ''}{market_pct}% ({unavail}% unavail)"

        # 6. COMPETITOR POSITIONING
        if competitor_avg and competitor_avg > 0:
            # Position ourselves relative to competitor average
            diff_pct = ((competitor_avg - price) / price) * 100
            # If competitors are much higher, we can push up
            if diff_pct > 20:
                comp_adj = min(15, diff_pct * 0.3)
                price *= (1 + comp_adj / 100)
                breakdown["competitor"] = f"+{round(comp_adj)}% (comps {round(diff_pct)}% higher)"
            elif diff_pct < -20:
                comp_adj = max(-10, diff_pct * 0.2)
                price *= (1 + comp_adj / 100)
                breakdown["competitor"] = f"{round(comp_adj)}% (comps {round(abs(diff_pct))}% lower)"

        # 7. EVENT INTELLIGENCE adjustment
        if event_data:
            impact = event_data.get("impact", "")
            event_name = event_data.get("name", "Event")
            attendance = event_data.get("estimated_attendance", 0)
            if impact == "mega":
                event_pct = 40
            elif impact == "large":
                event_pct = 25
            elif impact == "medium":
                event_pct = 12
            elif impact == "small":
                event_pct = 5
            else:
                event_pct = 0
            if event_pct > 0:
                price *= (1 + event_pct / 100)
                breakdown["event"] = f"+{event_pct}% ({event_name}, {attendance:,})"

        # 8. AGGRESSIVENESS multiplier
        agg = float(strategy.get("aggressiveness", 1.0))
        if agg != 1.0:
            price *= agg
            breakdown["aggressiveness"] = f"{agg}x"

        # 9. HISTORICAL FLOOR — never price below proven historical minimum
        if historical_floor and historical_floor > 0 and price < historical_floor:
            old_price = price
            price = historical_floor
            breakdown["historical_floor"] = f"Floor £{historical_floor} (was £{round(old_price, 2)})"

        # 10. GUARDRAILS - min/max
        min_price = round(base_rate * 0.5, 2)
        max_price = round(base_rate * 3.0, 2)
        final = round(max(min_price, min(max_price, price)), 2)
        if final != round(price, 2):
            breakdown["guardrails"] = f"Clamped [{min_price}-{max_price}]"

        return final, breakdown

    @router.post("/revenue/dynamic-pricing/{property_id}/calculate")
    async def calculate_dynamic_prices(property_id: str, data: Dict = {},
                                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Calculate AI dynamic prices for all 90 days without applying."""
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)
        days_count = int(data.get("days", 90))

        # Get strategy
        strategy = await db.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0}) or {}

        # Get room types
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if not room_types:
            room_types = [{"id": "default", "name": "Standard", "base_rate": 100}]

        # Get ALL market supply data
        supply_map = {}
        supply_docs = await db.market_supply.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("scanned_at", -1).to_list(500)
        for s in supply_docs:
            if s["date"] not in supply_map:
                supply_map[s["date"]] = s

        # Get competitor prices
        competitors = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)
        comp_price_map = {}
        for comp in competitors:
            for p in (comp.get("prices") or []):
                if p.get("scraped") and p.get("lowest_price"):
                    if p["date"] not in comp_price_map:
                        comp_price_map[p["date"]] = []
                    comp_price_map[p["date"]].append(p["lowest_price"])

        # Get events for event-based pricing
        events_list = await db.market_events.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        event_map = {}
        for ev in events_list:
            ev_date = ev.get("date", "")
            ev_end = ev.get("end_date", ev_date)
            try:
                start_d = datetime.strptime(ev_date, "%Y-%m-%d")
                end_d = datetime.strptime(ev_end, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            # Map event to its dates + 1 day buffer before/after
            d = start_d - timedelta(days=1)
            while d <= end_d + timedelta(days=1):
                ds_key = d.strftime("%Y-%m-%d")
                # Keep the highest impact event per date
                if ds_key not in event_map or _impact_rank(ev.get("impact", "")) > _impact_rank(event_map[ds_key].get("impact", "")):
                    event_map[ds_key] = ev
                d += timedelta(days=1)

        # Get historical price floors from strategy
        price_floors = strategy.get("price_floors", {})

        # Build historical monthly floor map
        historical_floor_map = {}
        for month_str, floor_data in price_floors.items():
            try:
                historical_floor_map[int(month_str)] = float(floor_data.get("min_price", 0))
            except (ValueError, TypeError):
                pass

        # If no floors in strategy, compute from historical data
        if not historical_floor_map:
            hist_data = await db.historical_prices.find(
                {"property_id": property_id}, {"_id": 0, "month": 1, "sold_rate": 1}
            ).to_list(800)
            if hist_data:
                monthly_rates = {}
                for h in hist_data:
                    m = h.get("month")
                    if m not in monthly_rates:
                        monthly_rates[m] = []
                    monthly_rates[m].append(h["sold_rate"])
                for m, rates in monthly_rates.items():
                    sorted_rates = sorted(rates)
                    p25 = sorted_rates[len(sorted_rates) // 4]
                    historical_floor_map[m] = round(p25 * 0.95, 2)

        # Calculate prices for every day
        results = []
        for rt in room_types[:5]:
            base = float(rt.get("base_rate", 100) or 100)
            rt_prices = []

            for i in range(days_count):
                d = now + timedelta(days=i)
                ds = d.strftime("%Y-%m-%d")

                # Our occupancy for this date
                booked = 0
                for p in props:
                    booked += await db.bookings.count_documents({
                        "property_id": p.get("id", ""), "check_in": {"$lte": ds},
                        "check_out": {"$gt": ds}, "status": {"$ne": "cancelled"}
                    })
                our_occ = min(100, round((booked / total_rooms) * 100))

                # Supply snapshot for this date
                supply_snap = supply_map.get(ds)

                # Competitor average for this date
                comp_prices = comp_price_map.get(ds, [])
                comp_avg = round(sum(comp_prices) / len(comp_prices), 2) if comp_prices else None

                # Event for this date
                event_for_day = event_map.get(ds)

                # Historical floor for this month
                hist_floor = historical_floor_map.get(d.month, 0)

                final_price, breakdown = await _calculate_ai_price(
                    base, d, i, strategy, supply_snap, our_occ, total_rooms, comp_avg, event_for_day, hist_floor
                )

                # Get current override if any
                override = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": ds}, {"_id": 0}
                )
                current_rate = float(override.get("custom_rate", 0)) if override and override.get("custom_rate") else base
                change = round(((final_price - current_rate) / current_rate) * 100, 1) if current_rate > 0 else 0

                rt_prices.append({
                    "date": ds,
                    "day": d.day,
                    "dow": d.strftime("%a"),
                    "days_ahead": i,
                    "base_rate": base,
                    "current_rate": current_rate,
                    "ai_price": final_price,
                    "change_pct": change,
                    "our_occupancy": our_occ,
                    "market_unavail": supply_snap.get("unavailable_pct") if supply_snap else None,
                    "competitor_avg": comp_avg,
                    "event": event_for_day.get("name") if event_for_day else None,
                    "event_impact": event_for_day.get("impact") if event_for_day else None,
                    "breakdown": breakdown,
                    "is_today": i == 0,
                })

            results.append({
                "room_type_id": rt.get("id", ""),
                "room_type_name": rt.get("name", "Standard"),
                "base_rate": base,
                "prices": rt_prices,
            })

        # Summary stats
        all_prices = [p for r in results for p in r["prices"]]
        increases = sum(1 for p in all_prices if p["change_pct"] > 0)
        decreases = sum(1 for p in all_prices if p["change_pct"] < 0)
        avg_change = round(sum(p["change_pct"] for p in all_prices) / max(len(all_prices), 1), 1)
        avg_price = round(sum(p["ai_price"] for p in all_prices) / max(len(all_prices), 1), 2)

        event_days = sum(1 for p in all_prices if p.get("event"))

        return {
            "room_types": results,
            "summary": {
                "total_days": days_count,
                "total_room_types": len(results),
                "increases": increases,
                "decreases": decreases,
                "unchanged": len(all_prices) - increases - decreases,
                "avg_change_pct": avg_change,
                "avg_ai_price": avg_price,
                "event_days": event_days,
            },
            "data_sources": {
                "market_supply_dates": len(supply_map),
                "competitors_with_prices": len(comp_price_map),
                "strategy_configured": bool(strategy.get("dow_adjustments") or strategy.get("monthly_adjustments")),
                "events_loaded": len(event_map),
                "historical_floors": len(historical_floor_map),
            },
        }

    @router.post("/revenue/dynamic-pricing/{property_id}/apply")
    async def apply_dynamic_prices(property_id: str, data: Dict = {},
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Apply AI dynamic prices to the Rate Calendar for all 90 days."""
        now = datetime.now(timezone.utc)
        props = await _get_props(property_id)
        total_rooms = await _total_rooms(props)
        days_count = int(data.get("days", 90))
        strategy = await db.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0}) or {}

        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if not room_types:
            room_types = [{"id": "default", "name": "Standard", "base_rate": 100}]

        supply_map = {}
        supply_docs = await db.market_supply.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("scanned_at", -1).to_list(500)
        for s in supply_docs:
            if s["date"] not in supply_map:
                supply_map[s["date"]] = s

        competitors = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)
        comp_price_map = {}
        for comp in competitors:
            for p in (comp.get("prices") or []):
                if p.get("scraped") and p.get("lowest_price"):
                    if p["date"] not in comp_price_map:
                        comp_price_map[p["date"]] = []
                    comp_price_map[p["date"]].append(p["lowest_price"])

        # Get events
        events_list = await db.market_events.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        event_map_apply = {}
        for ev in events_list:
            ev_date = ev.get("date", "")
            ev_end = ev.get("end_date", ev_date)
            try:
                start_d = datetime.strptime(ev_date, "%Y-%m-%d")
                end_d = datetime.strptime(ev_end, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            d_iter = start_d - timedelta(days=1)
            while d_iter <= end_d + timedelta(days=1):
                ds_key = d_iter.strftime("%Y-%m-%d")
                if ds_key not in event_map_apply or _impact_rank(ev.get("impact", "")) > _impact_rank(event_map_apply[ds_key].get("impact", "")):
                    event_map_apply[ds_key] = ev
                d_iter += timedelta(days=1)

        # Get historical floors
        price_floors_apply = strategy.get("price_floors", {})
        hist_floor_map_apply = {}
        for month_str, floor_data in price_floors_apply.items():
            try:
                hist_floor_map_apply[int(month_str)] = float(floor_data.get("min_price", 0))
            except (ValueError, TypeError):
                pass
        if not hist_floor_map_apply:
            hist_data = await db.historical_prices.find(
                {"property_id": property_id}, {"_id": 0, "month": 1, "sold_rate": 1}
            ).to_list(800)
            if hist_data:
                monthly_rates = {}
                for h in hist_data:
                    m = h.get("month")
                    if m not in monthly_rates:
                        monthly_rates[m] = []
                    monthly_rates[m].append(h["sold_rate"])
                for m, rates in monthly_rates.items():
                    sorted_rates = sorted(rates)
                    p25 = sorted_rates[len(sorted_rates) // 4]
                    hist_floor_map_apply[m] = round(p25 * 0.95, 2)

        applied_count = 0
        for rt in room_types:
            base = float(rt.get("base_rate", 100) or 100)
            rt_id = rt.get("id", "")

            for i in range(days_count):
                d = now + timedelta(days=i)
                ds = d.strftime("%Y-%m-%d")

                booked = 0
                for p in props:
                    booked += await db.bookings.count_documents({
                        "property_id": p.get("id", ""), "check_in": {"$lte": ds},
                        "check_out": {"$gt": ds}, "status": {"$ne": "cancelled"}
                    })
                our_occ = min(100, round((booked / total_rooms) * 100))
                supply_snap = supply_map.get(ds)
                comp_prices = comp_price_map.get(ds, [])
                comp_avg = round(sum(comp_prices) / len(comp_prices), 2) if comp_prices else None

                event_for_day = event_map_apply.get(ds)
                hist_floor = hist_floor_map_apply.get(d.month, 0)
                final_price, breakdown = await _calculate_ai_price(
                    base, d, i, strategy, supply_snap, our_occ, total_rooms, comp_avg, event_for_day, hist_floor
                )

                # Apply to rate overrides
                reasons = [f"{k}: {v}" for k, v in breakdown.items() if k != "base"]
                reason_str = " | ".join(reasons) if reasons else "AI Dynamic Pricing"

                await db.rate_overrides.update_one(
                    {"property_id": property_id, "date": ds, "room_type_id": rt_id},
                    {"$set": {
                        "property_id": property_id,
                        "room_type_id": rt_id,
                        "date": ds,
                        "custom_rate": final_price,
                        "set_by": "ai-dynamic-pricing",
                        "reason": reason_str,
                        "breakdown": breakdown,
                        "updated_at": now.isoformat(),
                    }},
                    upsert=True
                )
                applied_count += 1

        return {
            "message": f"AI Dynamic Pricing applied to {applied_count} rate entries across {days_count} days",
            "applied": applied_count,
            "days": days_count,
            "room_types": len(room_types),
        }

    return router
