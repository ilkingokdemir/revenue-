"""Market Robot bölümü — core fabrikasından faz-2'de ayrıldı. register(router, db, require_roles, resend, S) çağrılır; bölümler arası paylaşım S (SimpleNamespace) üzerinden."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Tuple
import uuid
import re
import asyncio
import logging
import os
import httpx

from .state import (SCRAPE_LOCKS, SCRAPE_LOCKS_GEO, MAX_CONCURRENT_SCANS,
                    AUTO_SCAN_MAX_DAYS)
from .gap_logic import _internal_close_gap
from .geo_utils import (_count_booking_cards, _osm_hotel_count, _google_places_hotel_count,
                        _radius_based_property_count, _price_stats)

logger = logging.getLogger(__name__)

def register(router, db, require_roles, resend, S):

    # Standard hotel-industry monthly seasonality multipliers (Northern
    # Hemisphere / urban-leisure mix). Multiplying by these gives the
    # per-month deviation from the annual mean (which averages to ~1.0).
    # Indexes: 0 = January … 11 = December.
    _MONTH_SEASONALITY = [
        0.78,  # Jan — post-NYE lull
        0.82,  # Feb — short month, mid-low season
        0.92,  # Mar — spring shoulder
        1.02,  # Apr — Easter pickup
        1.08,  # May — high shoulder
        1.18,  # Jun — early summer peak
        1.25,  # Jul — peak summer
        1.22,  # Aug — peak summer
        1.05,  # Sep — late shoulder
        0.98,  # Oct — autumn shoulder
        0.88,  # Nov — pre-holiday lull
        0.92,  # Dec — Christmas/NYE bump
    ]

    def _build_expense_category_breakdown(items: List[Dict], annual_total: float) -> List[Dict]:
        """Group expense items by category → return ordered list of
        {category, annual_amount, share_pct, item_count} for pie/bar charts."""
        from utils.yoy_parser import classify_expense
        buckets: Dict[str, Dict] = {}
        for x in items:
            label = str(x.get("label") or "")
            cat = str(x.get("category") or "").strip() or classify_expense(label)
            amt = float(x.get("amount") or 0)
            if amt <= 0:
                continue
            annual_amt = amt * 12 if str(x.get("period", "annual")).lower() == "monthly" else amt
            b = buckets.setdefault(cat, {"category": cat, "annual_amount": 0.0, "item_count": 0})
            b["annual_amount"] += annual_amt
            b["item_count"] += 1
        out = []
        for b in buckets.values():
            b["annual_amount"] = round(b["annual_amount"], 2)
            b["share_pct"] = round((b["annual_amount"] / annual_total) * 100, 1) if annual_total > 0 else 0
            out.append(b)
        out.sort(key=lambda r: r["annual_amount"], reverse=True)
        return out

    def _build_annual_revenue_forecast(*, base_rate: float, total_rooms: int,
                                       occupancy_factor: float, start_date,
                                       monthly_adr_overrides: Optional[Dict[str, float]] = None,
                                       horizon_months: int = 12,
                                       last_minute: Optional[Dict] = None) -> dict:
        """Forward-looking N-month room revenue projection (default 12 months).

        Optional last-minute discount layer: `last_minute = {enabled, discount_pct, share_pct}`.
        When enabled, `share_pct` of nights are assumed sold at `discount_pct` off →
        applied to both monthly rows and annual total so operators see the
        true after-discount forecast.

        Methodology (same maths as Hotel Revenue Lab's "Sadece Oda" mode):
            monthly_revenue = ADR_for_month × rooms × days_in_month × occupancy × season_mult
        Per-month ADR priority:
            1. Booking.com scraped price for that exact YYYY-MM (if available
               in `monthly_adr_overrides`) — highest fidelity, real market data.
            2. Otherwise the global `base_rate` (manual_adr or room_types avg).
        Returns enough metadata for the frontend to render a bar chart + KPI tiles.
        """
        import calendar as _cal
        monthly: List[Dict] = []
        annual_total = 0.0   # First 12 months
        biennial_total = 0.0  # Full horizon (typically 24)
        scraped_months = 0
        # Normalise last-minute discount config
        lm_enabled = bool(last_minute and last_minute.get("enabled"))
        lm_disc = max(0.0, min(50.0, float((last_minute or {}).get("discount_pct") or 0))) / 100.0
        lm_share = max(0.0, min(100.0, float((last_minute or {}).get("share_pct") or 0))) / 100.0
        lm_factor = 1.0 - (lm_disc * lm_share) if lm_enabled else 1.0
        annual_lm_savings = 0.0
        cur_y = start_date.year
        cur_m = start_date.month
        for i in range(horizon_months):
            y = cur_y + (cur_m - 1 + i) // 12
            m = (cur_m - 1 + i) % 12 + 1
            month_key = f"{y:04d}-{m:02d}"
            days_in_month = _cal.monthrange(y, m)[1]
            season_mult = _MONTH_SEASONALITY[m - 1]
            scraped_adr = (monthly_adr_overrides or {}).get(month_key) if monthly_adr_overrides else None
            if scraped_adr and scraped_adr > 0:
                adr_used = float(scraped_adr)
                adr_origin = "scraped"
                scraped_months += 1
            else:
                adr_used = base_rate
                adr_origin = "estimated"
            gross_revenue = adr_used * total_rooms * days_in_month * occupancy_factor * season_mult
            month_revenue = round(gross_revenue * lm_factor, 2)
            month_lm_discount = round(gross_revenue - month_revenue, 2)
            annual_lm_savings += month_lm_discount
            biennial_total += month_revenue
            if i < 12:
                annual_total += month_revenue
            monthly.append({
                "year": y,
                "month": m,
                "month_key": month_key,
                "label": f"{_cal.month_abbr[m]} {str(y)[2:]}",
                "days": days_in_month,
                "season_multiplier": season_mult,
                "occupancy_pct": round(occupancy_factor * season_mult * 100, 1),
                "adr": round(adr_used, 2),
                "adr_origin": adr_origin,
                "revenue": month_revenue,
                "gross_revenue": round(gross_revenue, 2),
                "last_minute_discount": month_lm_discount,
            })
        # Effective ADR = ağırlıklı ortalama oda gecesi başına ücret (gross, LM
        # iskontosu uygulanmadan önce). base_rate sadece scrape edilmemiş aylar
        # için fallback; gerçek yıllık ortalama scrape'lenen aylarla çok daha
        # yüksek olabilir, bu yüzden room-nights ile ağırlıklandırıyoruz.
        annual_gross = sum(m["gross_revenue"] for m in monthly[:12])
        total_room_nights_sold_12 = sum(
            total_rooms * m["days"] * (m["occupancy_pct"] / 100.0) for m in monthly[:12]
        )
        effective_adr_gross = (annual_gross / total_room_nights_sold_12) if total_room_nights_sold_12 > 0 else float(base_rate)
        effective_adr_net = (annual_total / total_room_nights_sold_12) if total_room_nights_sold_12 > 0 else float(base_rate)
        # RevPAR = total revenue / total available room nights (rooms × 365)
        revpar_gross = annual_gross / (total_rooms * 365) if total_rooms else 0
        revpar_net = annual_total / (total_rooms * 365) if total_rooms else 0
        avg_occupancy = sum(m["occupancy_pct"] for m in monthly[:12]) / 12.0 if monthly else 0
        return {
            "annual_revenue": round(annual_total, 2),
            "annual_gross_revenue": round(annual_gross, 2),
            "biennial_revenue": round(biennial_total, 2),
            "horizon_months": horizon_months,
            "monthly": monthly,
            # Hero ADR = effective gross ADR (room-nights ile ağırlıklı). Eski
            # davranış (base_rate'i echo) RevPAR > ADR çelişkisine yol açıyordu.
            "adr": round(effective_adr_gross, 2),
            "adr_net": round(effective_adr_net, 2),
            "adr_base_rate": round(base_rate, 2),  # rate-card / fallback ADR
            "revpar": round(revpar_gross, 2),
            "revpar_net": round(revpar_net, 2),
            "avg_occupancy_pct": round(avg_occupancy, 1),
            "total_rooms": total_rooms,
            "scraped_months_count": scraped_months,
            "last_minute": {
                "enabled": lm_enabled,
                "discount_pct": round(lm_disc * 100, 1),
                "share_pct": round(lm_share * 100, 1),
                "annual_savings": round(annual_lm_savings if horizon_months >= 12 else (annual_lm_savings * 12 / max(horizon_months, 1)), 2),
                "total_savings": round(annual_lm_savings, 2),
                "factor": round(lm_factor, 4),
            },
            "methodology": "ADR × oda × günler × doluluk × sezonalite" + (f" · {scraped_months}/{horizon_months} ay canlı Booking.com fiyatlarıyla" if scraped_months else "") + (f" · -%{round(lm_disc*100)} last-minute iskontosu (gecelerin %{round(lm_share*100)}'inde)" if lm_enabled else ""),
        }


    @router.get("/revenue/market-robot/{property_id}/performance")
    async def get_performance_report(property_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Scanner Performance Report — ROI, revenue impact, pricing adjustments breakdown."""
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        month_start = now.replace(day=1).strftime("%Y-%m-%d")

        # Property currency (for frontend formatting) + room inventory (for accurate revenue estimates)
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "currency": 1, "name": 1,
             "booking_room_count": 1, "booking_room_count_scanned_at": 1,
             "manual_room_count": 1, "manual_room_count_set_at": 1,
             "manual_adr": 1, "manual_adr_set_at": 1,
             "manual_occupancy": 1, "manual_occupancy_set_at": 1,
             "last_minute_discount": 1}
        )
        property_currency = (prop.get("currency") if prop else None) or "GBP"

        # Get all room types — base rate + inventory
        room_types_list = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        # Only types with a real base_rate contribute to the average — otherwise
        # types that are missing the rate field dilute the mean to near-zero
        # (which then makes every rate-override look like a £100+ uplift).
        rated_types = [r for r in room_types_list if float(r.get("base_rate", 0) or 0) > 0]
        # ADR priority: operator-supplied manual_adr > scraped Booking.com
        # monthly average (real market price for THIS property) > average of
        # room-type base rates > 100 fallback. Manual ADR exists so operators
        # can correct cases where their *real* sold ADR differs from what's
        # in room_types (commission-net vs gross, channel mix, etc.).
        manual_adr = (prop or {}).get("manual_adr") if prop else None
        # Pre-fetch scraped per-month ADRs so we can use them BOTH as the
        # base_rate (when no manual override) AND as per-month overrides
        # inside the annual forecast.
        scraped_rows = await db.property_monthly_prices.find(
            {"property_id": property_id, "adr": {"$gt": 0}},
            {"_id": 0, "month_key": 1, "adr": 1},
        ).to_list(24)
        scraped_avg_adr = (sum(float(r["adr"]) for r in scraped_rows) / len(scraped_rows)) if scraped_rows else 0
        if isinstance(manual_adr, (int, float)) and float(manual_adr) > 0:
            base_rate = float(manual_adr)
            adr_source = "manual"
        elif scraped_avg_adr > 0:
            base_rate = round(scraped_avg_adr, 2)
            adr_source = "booking_com_scraped"
        elif rated_types:
            base_rate = sum(float(r.get("base_rate", 0)) for r in rated_types) / len(rated_types)
            adr_source = "room_types"
        else:
            base_rate = 100.0
            adr_source = "fallback"
        # Room count priority: manual override (operator-set) > Booking.com auto-scan
        # > local room_types sum > 10-room fallback. The manual override exists so
        # operators can correct cases where Booking.com only exposes a subset of
        # available units for a given date.
        manual_rc = (prop or {}).get("manual_room_count") if prop else None
        booking_room_count = (prop or {}).get("booking_room_count") if prop else None
        total_rooms_local = sum(int(r.get("total_rooms", 0) or 0) for r in room_types_list)
        if isinstance(manual_rc, (int, float)) and int(manual_rc) > 0:
            total_rooms = int(manual_rc)
            room_count_source = "manual"
        elif booking_room_count and int(booking_room_count) > 0:
            total_rooms = int(booking_room_count)
            room_count_source = "booking_com"
        elif total_rooms_local > 0:
            total_rooms = total_rooms_local
            room_count_source = "room_types"
        else:
            total_rooms = 10
            room_count_source = "fallback"
        # Real occupancy from the last 30 days — parallel count of bookings overlapping each day.
        # If the property has no booking history we fall back to a 70 % industry average.
        last_30_dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 31)]
        per_day_counts = await asyncio.gather(*[
            db.bookings.count_documents({
                "property_id": property_id,
                "check_in": {"$lte": d},
                "check_out": {"$gt": d},
                "status": {"$nin": ["cancelled"]},
            }) for d in last_30_dates
        ])
        total_occupied_rn = sum(per_day_counts)
        available_rn = total_rooms * len(last_30_dates)
        # Occupancy priority: manual_occupancy (operator-set) > actual 30-day
        # bookings > 70 % industry-average fallback. Manual lets owners feed in
        # their real long-run occupancy when bookings history is sparse.
        manual_occ = (prop or {}).get("manual_occupancy") if prop else None
        if isinstance(manual_occ, (int, float)) and 0 < float(manual_occ) <= 1.0:
            occupancy_factor = float(manual_occ)
            occupancy_basis = "manual"
        elif available_rn > 0 and total_occupied_rn > 0:
            occupancy_factor = max(0.05, min(1.0, total_occupied_rn / available_rn))
            occupancy_basis = "actual_30d"
        else:
            occupancy_factor = 0.7
            occupancy_basis = "industry_avg_fallback"

        # Get rate overrides set by robot/scanner/dynamic-pricing within the
        # ACTIVE optimization horizon — today through today+90 days. This is
        # the window the auto-scanner actively maintains; older or far-future
        # overrides are stale and would inflate the numbers without reflecting
        # the robot's current performance. Bounding the range here is what
        # turns "Days Optimized: 491 / +£95,554" (cumulative noise) into the
        # honest "current robot impact" figures the user asked for.
        horizon_end = (now + timedelta(days=90)).strftime("%Y-%m-%d")
        all_overrides = await db.rate_overrides.find(
            {
                "property_id": property_id,
                "set_by": {"$in": ["auto-scanner", "market-robot", "ai-dynamic-pricing", "event-intelligence"]},
                "date": {"$gte": today_str, "$lte": horizon_end},
            },
            {"_id": 0},
        ).sort("date", 1).to_list(2000)

        # Deduplicate per (date, room_type) — only the LATEST override applies
        # (the robot rewrites the same date multiple times as the market shifts).
        # Then collapse to one entry per DATE by averaging across room types so a
        # property with 3-4 room types doesn't get its uplift counted 3-4 times.
        # This is the fix for the inflated "491 days / £95,554" figures the user
        # reported — those came from naïvely summing every historical write.
        by_date_room: Dict[str, Dict] = {}
        for ov in all_overrides:
            key = f"{ov.get('date','')}::{ov.get('room_type_id','')}"
            existing = by_date_room.get(key)
            if not existing or (ov.get("updated_at", "") > existing.get("updated_at", "")):
                by_date_room[key] = ov
        # Now group per date — averaging custom_rate across room types
        per_date: Dict[str, Dict] = {}
        for ov in by_date_room.values():
            d = ov.get("date", "")
            if not d:
                continue
            slot = per_date.setdefault(d, {
                "rates": [], "reasons": [], "sources": [], "updated_at": ov.get("updated_at", "")
            })
            slot["rates"].append(float(ov.get("custom_rate", base_rate)))
            slot["reasons"].append(ov.get("reason", ""))
            slot["sources"].append(ov.get("set_by", "unknown"))
            if ov.get("updated_at", "") > slot["updated_at"]:
                slot["updated_at"] = ov.get("updated_at", "")

        # Calculate revenue uplift
        total_uplift = 0
        total_days_adjusted = 0
        increases = 0
        decreases = 0
        event_boosts = 0
        event_uplift = 0
        market_adjustments = 0
        by_source = {"auto-scanner": 0, "market-robot": 0, "ai-dynamic-pricing": 0, "event-intelligence": 0}
        daily_impact = []
        monthly_impact = {}

        for ov_date, slot in per_date.items():
            # Average rate across room types for the date → one figure per day
            avg_rate = sum(slot["rates"]) / len(slot["rates"]) if slot["rates"] else base_rate
            diff = avg_rate - base_rate
            diff_pct = round((diff / base_rate) * 100, 1) if base_rate > 0 else 0
            # Source/reason from the most recent room-type override on that day
            source = slot["sources"][-1] if slot["sources"] else "unknown"
            reason = slot["reasons"][-1] if slot["reasons"] else ""

            if avg_rate != base_rate:
                total_days_adjusted += 1
                total_uplift += diff
                if diff > 0:
                    increases += 1
                else:
                    decreases += 1

                if source in by_source:
                    by_source[source] += diff

                if "Event" in reason or "event" in reason:
                    event_boosts += 1
                    event_uplift += diff

                if "market" in reason.lower() or source == "market-robot":
                    market_adjustments += 1

            # Month grouping
            month_key = ov_date[:7] if ov_date else "unknown"
            if month_key not in monthly_impact:
                monthly_impact[month_key] = {"uplift": 0, "days": 0, "increases": 0, "decreases": 0, "events": 0}
            monthly_impact[month_key]["uplift"] += diff
            monthly_impact[month_key]["days"] += 1
            if diff > 0:
                monthly_impact[month_key]["increases"] += 1
            elif diff < 0:
                monthly_impact[month_key]["decreases"] += 1
            if "Event" in reason or "event" in reason:
                monthly_impact[month_key]["events"] += 1

            # Daily (last 14 days)
            if ov_date >= (now - timedelta(days=14)).strftime("%Y-%m-%d") and ov_date <= today_str:
                daily_impact.append({
                    "date": ov_date,
                    "base_rate": base_rate,
                    "robot_rate": round(avg_rate, 2),
                    "uplift": round(diff, 2),
                    "uplift_pct": diff_pct,
                    "source": source,
                    "has_event": "Event" in reason or "event" in reason,
                })

        # Get scan counts
        total_scans = await db.market_robot_logs.count_documents({"property_id": property_id})
        scans_this_month = await db.market_robot_logs.count_documents(
            {"property_id": property_id, "scanned_at": {"$gte": month_start}}
        )

        # Events detected
        total_events = await db.market_events.count_documents({"property_id": property_id})
        mega_events = await db.market_events.count_documents({"property_id": property_id, "impact": "mega"})
        large_events = await db.market_events.count_documents({"property_id": property_id, "impact": "large"})

        # Real Booking.com scraped per-month ADRs (already fetched above for
        # base_rate calculation). When present these override the global
        # `base_rate` per matching month in the annual forecast, giving us
        # actual market-priced revenue projections.
        # IMPORTANT: when the operator has set a manual_adr explicitly, that
        # value is sovereign — we do NOT let scraped monthly overrides win,
        # otherwise changing the manual ADR has no visible effect on the hero
        # tile (effective ADR stays dominated by scraped data). User mental
        # model is: "I typed X → show X → recompute RevPAR from X".
        if adr_source == "manual":
            monthly_adr_overrides = {}
        else:
            monthly_adr_overrides = {r["month_key"]: float(r["adr"]) for r in scraped_rows if r.get("adr")}
        # Sample-size metadata so the UI can show "based on N days" tooltips.
        scraped_meta_by_key = {r["month_key"]: {
            "sample_size": int(r.get("sample_size") or 0),
            "sample_dates": r.get("sample_dates") or [],
            "min_price": r.get("min_price"),
            "max_price": r.get("max_price"),
            "source": r.get("source"),
            "scraped_at": r.get("scraped_at"),
        } for r in scraped_rows}

        # If we're on the aggregate "all" view (no property-specific scraped
        # prices), aggregate scraped ADRs across all configured properties
        # using a simple average per month_key. This is what gives sensible
        # "All Branches" ADR (£200-£300 in London) instead of falling back
        # to the £100 default when the user hasn't selected a single property.
        if not monthly_adr_overrides and property_id in ("all", "default"):
            agg_rows = await db.property_monthly_prices.find(
                {}, {"_id": 0, "month_key": 1, "adr": 1}
            ).to_list(2000)
            by_month: Dict[str, List[float]] = {}
            for r in agg_rows:
                a = float(r.get("adr") or 0)
                k = r.get("month_key")
                if a > 0 and k:
                    by_month.setdefault(k, []).append(a)
            if by_month:
                monthly_adr_overrides = {k: round(sum(v) / len(v), 2) for k, v in by_month.items()}
                # Also lift the base_rate to the overall scraped average so
                # the headline ADR figure isn't the £100 fallback either.
                base_rate = round(sum(monthly_adr_overrides.values()) / len(monthly_adr_overrides), 2)
                adr_source = "aggregated_branches"

        # Estimated revenue impact = per-room uplift × inventory × occupancy
        avg_rooms = max(round(total_rooms * occupancy_factor), 1)
        estimated_rev_uplift = round(total_uplift * avg_rooms, 2)
        monthly_rev_uplift = round(sum(m["uplift"] for k, m in monthly_impact.items() if k >= month_start[:7]) * avg_rooms, 2)

        # Monthly sorted
        monthly_sorted = []
        for mk in sorted(monthly_impact.keys()):
            mi = monthly_impact[mk]
            monthly_sorted.append({
                "month": mk,
                "month_label": datetime.strptime(mk + "-01", "%Y-%m-%d").strftime("%b %Y") if mk != "unknown" else "Unknown",
                "uplift_per_room": round(mi["uplift"], 2),
                "est_revenue_uplift": round(mi["uplift"] * avg_rooms, 2),
                "days_adjusted": mi["days"],
                "increases": mi["increases"],
                "decreases": mi["decreases"],
                "event_days": mi["events"],
            })

        # Last-minute discount config (operator-set; defaults to disabled).
        lm_cfg = (prop or {}).get("last_minute_discount") or {}

        # Build annual forecast first so we can attach YoY comparison alongside it
        annual_forecast = _build_annual_revenue_forecast(
            base_rate=base_rate,
            total_rooms=total_rooms,
            occupancy_factor=occupancy_factor,
            start_date=now.date(),
            monthly_adr_overrides=monthly_adr_overrides,
            last_minute=lm_cfg,
        )
        # Attach scrape provenance to each forecast month so the UI can display
        # "ADR averaged from N days" tooltips and audit data origin.
        for fm in annual_forecast["monthly"]:
            meta = scraped_meta_by_key.get(fm["month_key"])
            if meta and meta.get("sample_size"):
                fm["scrape_meta"] = meta

        # ────────────────────────────────────────────────────────────────
        # YoY Comparison — last year ACTUAL revenue vs this year FORECAST
        # ────────────────────────────────────────────────────────────────
        # For each forecast month we look up the SAME calendar month one
        # year earlier and aggregate the actual paid bookings. This lets
        # owners/investors see whether the forecast is ahead or behind
        # historical realised performance.
        prev_rev_by_key: Dict[str, float] = {}
        try:
            # Window: 13 months back from "first forecast month - 1y" through
            # "last forecast month - 1y" to fully cover the 12 needed months.
            first_fc = annual_forecast["monthly"][0]
            last_fc = annual_forecast["monthly"][-1]
            window_start = datetime(first_fc["year"] - 1, first_fc["month"], 1, tzinfo=timezone.utc)
            # End is exclusive — start of the month *after* last forecast month a year ago
            last_y = last_fc["year"] - 1
            last_m = last_fc["month"]
            end_y = last_y + (1 if last_m == 12 else 0)
            end_m = 1 if last_m == 12 else last_m + 1
            window_end = datetime(end_y, end_m, 1, tzinfo=timezone.utc)
            bookings_prev = await db.bookings.find(
                {
                    "property_id": property_id,
                    "status": {"$nin": ["cancelled", "no_show"]},
                    "check_in": {"$lt": window_end.isoformat()},
                    "check_out": {"$gt": window_start.isoformat()},
                },
                {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1},
            ).to_list(20000)
            for b in bookings_prev:
                try:
                    ci = datetime.fromisoformat(str(b["check_in"]).replace("Z", "+00:00"))
                    co = datetime.fromisoformat(str(b["check_out"]).replace("Z", "+00:00"))
                except Exception:
                    continue
                total_nights = max(1, (co.date() - ci.date()).days)
                per_night = float(b.get("total_price", 0) or 0) / total_nights
                d = ci
                while d < co:
                    key = f"{d.year:04d}-{d.month:02d}"
                    prev_rev_by_key[key] = prev_rev_by_key.get(key, 0.0) + per_night
                    d += timedelta(days=1)
        except Exception as e:
            logger.warning("YoY prev-year aggregation failed for %s: %s", property_id, e)

        # Merge uploaded historical revenue (from PDF/JPG/Excel uploads).
        # Upload takes priority over bookings for the same month — operators
        # upload these when their PMS booking history is incomplete or only
        # exists in external systems.
        try:
            uploaded = await db.property_yoy_history.find(
                {"property_id": property_id}, {"_id": 0, "month_key": 1, "revenue": 1}
            ).to_list(120)
            for u in uploaded:
                key = u.get("month_key")
                rev = float(u.get("revenue") or 0)
                if key and rev > 0:
                    # Override (uploads are explicit operator input → highest trust)
                    prev_rev_by_key[key] = rev
        except Exception as e:
            logger.warning("YoY uploaded-history merge failed for %s: %s", property_id, e)

        # ── Operator-uploaded expense items → drive Net Profit calculation ──
        expense_rows: List[Dict] = []
        annual_expense_total = 0.0
        monthly_expense_total = 0.0
        try:
            expense_rows = await db.property_yoy_expenses.find(
                {"property_id": property_id}, {"_id": 0}
            ).sort("label", 1).to_list(50)
            for x in expense_rows:
                amt = float(x.get("amount") or 0)
                if amt <= 0:
                    continue
                if str(x.get("period", "annual")).lower() == "monthly":
                    annual_expense_total += amt * 12
                    monthly_expense_total += amt
                else:
                    annual_expense_total += amt
                    monthly_expense_total += amt / 12
        except Exception as e:
            logger.warning("YoY expenses load failed for %s: %s", property_id, e)
        annual_expense_total = round(annual_expense_total, 2)
        monthly_expense_total = round(monthly_expense_total, 2)

        # Decorate forecast months with prev-year revenue & delta %
        prev_year_total = 0.0
        forecast_total_comparable = 0.0  # forecast SUM but only for months where prev-year exists
        for fm in annual_forecast["monthly"]:
            prev_key = f"{fm['year'] - 1:04d}-{fm['month']:02d}"
            prev_rev = round(prev_rev_by_key.get(prev_key, 0.0), 2)
            fm["prev_year_revenue"] = prev_rev
            fm["prev_year_month_key"] = prev_key
            if prev_rev > 0:
                fm["yoy_delta_pct"] = round(((fm["revenue"] - prev_rev) / prev_rev) * 100, 1)
                forecast_total_comparable += float(fm["revenue"])
            else:
                fm["yoy_delta_pct"] = None
            prev_year_total += prev_rev
        prev_year_total = round(prev_year_total, 2)
        forecast_total_comparable = round(forecast_total_comparable, 2)
        months_with_history = sum(1 for fm in annual_forecast["monthly"] if fm["prev_year_revenue"] > 0)
        # Apples-to-apples: only compare forecast for months that have prev-year
        # data. Otherwise a property with 2 months of history would show a
        # nonsense +71,000% delta against a 12-month forecast.
        if prev_year_total > 0 and forecast_total_comparable > 0:
            yoy_total_delta_pct = round(
                ((forecast_total_comparable - prev_year_total) / prev_year_total) * 100, 1
            )
        else:
            yoy_total_delta_pct = None
        annual_forecast["yoy_comparison"] = {
            "prev_year_total_revenue": prev_year_total,
            "this_year_forecast_revenue": forecast_total_comparable,
            "delta_revenue": round(forecast_total_comparable - prev_year_total, 2),
            "delta_pct": yoy_total_delta_pct,
            "months_with_history": months_with_history,
            "horizon_months": annual_forecast.get("horizon_months", 12),
            "comparable": True,  # signals FE that totals are aligned to matching months only
            "full_year_forecast": annual_forecast["annual_revenue"],
        }

        # ── Net Profit block: per-month and annual net (forecast - expenses) ──
        annual_gross = annual_forecast["annual_revenue"]
        annual_net = round(annual_gross - annual_expense_total, 2)
        # Decorate each forecast month with its monthly expense allocation + net
        for fm in annual_forecast["monthly"]:
            fm["expense"] = monthly_expense_total
            fm["net_revenue"] = round(float(fm.get("revenue", 0)) - monthly_expense_total, 2)
            # Prev-year net = prev-year actual − same monthly expense (best-effort assumption)
            fm["prev_year_net"] = round(float(fm.get("prev_year_revenue", 0)) - monthly_expense_total, 2) \
                if fm.get("prev_year_revenue", 0) > 0 else 0
        annual_forecast["expenses"] = {
            "items": expense_rows,
            "annual_total": annual_expense_total,
            "monthly_avg": monthly_expense_total,
            "annual_net_revenue": annual_net,
            "net_margin_pct": round((annual_net / annual_gross) * 100, 1) if annual_gross > 0 else 0,
            "by_category": _build_expense_category_breakdown(expense_rows, annual_expense_total),
        }

        return {
            "kpis": {
                "total_days_adjusted": total_days_adjusted,
                "total_rate_uplift": round(total_uplift, 2),
                "avg_uplift_per_day": round(total_uplift / max(total_days_adjusted, 1), 2),
                "estimated_revenue_uplift": estimated_rev_uplift,
                "monthly_revenue_uplift": monthly_rev_uplift,
                "increases": increases,
                "decreases": decreases,
                "event_boost_days": event_boosts,
                "event_revenue_uplift": round(event_uplift * avg_rooms, 2),
                "total_scans": total_scans,
                "scans_this_month": scans_this_month,
                "total_events_detected": total_events,
                "mega_events": mega_events,
                "large_events": large_events,
            },
            "by_source": {
                "auto_scanner": round(by_source.get("auto-scanner", 0) * avg_rooms, 2),
                "market_robot": round(by_source.get("market-robot", 0) * avg_rooms, 2),
                "ai_dynamic_pricing": round(by_source.get("ai-dynamic-pricing", 0) * avg_rooms, 2),
                "event_intelligence": round(by_source.get("event-intelligence", 0) * avg_rooms, 2),
            },
            "daily_impact": sorted(daily_impact, key=lambda x: x["date"], reverse=True),
            "monthly_impact": monthly_sorted,
            "property_currency": property_currency,
            "total_rooms": total_rooms,
            "room_count_source": room_count_source,
            "base_rate": round(base_rate, 2),
            "adr_source": adr_source,
            "occupancy_assumption": occupancy_factor,
            "occupancy_basis": occupancy_basis,
            "annual_forecast": annual_forecast,
        }

    S._MONTH_SEASONALITY = _MONTH_SEASONALITY
    S._build_annual_revenue_forecast = _build_annual_revenue_forecast
    S._build_expense_category_breakdown = _build_expense_category_breakdown
    S.get_performance_report = get_performance_report
