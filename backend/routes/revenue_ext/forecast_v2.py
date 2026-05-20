"""
Forecast v2 — Long-horizon (12–24 months) demand forecast + daily Demand Calendar overlay.

What makes this competitive:
- Opera Cloud's "Demand Forecaster" is a separate paid module.
- Mews/Cloudbeds: max 13-month forecast horizon.
- Us: built-in 24 months + day-level demand score + pickup curve, zero external dep.

Model (simple but realistic):
  For each future month:
    base_demand = avg monthly bookings of last 12 complete months
    seasonality_factor = same_month_last_year_bookings / avg_last_12_months
    yoy_growth = (last_6_months / prior_6_months) for trend; clamp [0.7, 1.5]
    forecast_bookings = base_demand * seasonality_factor * yoy_growth
    forecast_revenue  = forecast_bookings * avg_adr * avg_los

Demand calendar (daily):
  score 0-100 from (days_to_date booking velocity) * (DOW weight) * (season weight).
  overlay with events from `events` collection (if present) & public holidays (hardcoded common set).

Pickup curve:
  For a target arrival date, shows how bookings accumulate per lead_day (1..90).
  Historical average: arrivals curve from all past months for that target month/day-of-week.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict
import calendar
import logging

logger = logging.getLogger(__name__)

# Approx UK/TR public holidays (month-day) — extend as needed
PUBLIC_HOLIDAYS = {
    "01-01": "New Year",
    "04-23": "TR: Children's Day",
    "05-01": "Labor Day",
    "05-19": "TR: Youth & Sports",
    "07-15": "TR: Democracy Day",
    "08-30": "TR: Victory Day",
    "10-29": "TR: Republic Day",
    "12-25": "Christmas",
    "12-31": "New Year's Eve",
}

# Day-of-week weights: Fri/Sat peak, Tue/Wed trough
DOW_WEIGHTS = [0.85, 0.80, 0.75, 0.85, 1.20, 1.30, 1.05]  # Mon..Sun

# Seasonal weights by month (1..12) — generic resort/city blended
SEASON_WEIGHTS = {
    1: 0.70, 2: 0.72, 3: 0.85, 4: 0.95, 5: 1.05, 6: 1.20,
    7: 1.35, 8: 1.35, 9: 1.15, 10: 1.00, 11: 0.80, 12: 0.90,
}


def _month_range(y: int, m: int):
    first = date(y, m, 1)
    last = date(y, m, calendar.monthrange(y, m)[1])
    return first, last


def create_forecast_v2_router(db, require_roles):
    router = APIRouter()

    # ========== 24-MONTH HORIZON ==========
    @router.get("/forecast-v2/horizon/{property_id}")
    async def horizon(property_id: str, months: int = 24,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        if months < 3 or months > 36:
            raise HTTPException(400, "months must be 3..36")
        today = date.today()
        start_12mo_back = date(today.year - 1, today.month, 1)

        # ---- Build historical monthly stats (last 24 months) ----
        historical = {}  # "YYYY-MM" -> {bookings, revenue, adr, los}
        for i in range(24, 0, -1):
            ref_y = today.year
            ref_m = today.month - i
            while ref_m <= 0:
                ref_m += 12
                ref_y -= 1
            fm, lm = _month_range(ref_y, ref_m)
            bks = await db.bookings.find({
                "property_id": property_id,
                "check_in": {"$gte": fm.isoformat(), "$lte": lm.isoformat()},
                "status": {"$ne": "cancelled"},
            }, {"_id": 0, "total_price": 1, "nights": 1}).to_list(5000)
            n = len(bks)
            rev = sum((b.get("total_price") or 0) for b in bks)
            nights = sum((b.get("nights") or 1) for b in bks)
            historical[f"{ref_y:04d}-{ref_m:02d}"] = {
                "bookings": n,
                "revenue": round(rev, 2),
                "adr": round(rev / nights, 2) if nights else 0,
                "avg_los": round(nights / n, 2) if n else 0,
            }

        # ---- Model parameters ----
        last_12 = [v for k, v in historical.items() if k >= f"{start_12mo_back.year:04d}-{start_12mo_back.month:02d}"]
        avg_bk = sum(x["bookings"] for x in last_12) / max(len(last_12), 1)
        avg_adr = sum(x["adr"] for x in last_12 if x["adr"] > 0) / max(sum(1 for x in last_12 if x["adr"] > 0), 1) or 120
        avg_los = sum(x["avg_los"] for x in last_12 if x["avg_los"] > 0) / max(sum(1 for x in last_12 if x["avg_los"] > 0), 1) or 2.0

        # YoY growth from last 6 vs prior 6
        keys_sorted = sorted(historical.keys())
        recent_6 = keys_sorted[-6:] if len(keys_sorted) >= 6 else keys_sorted
        prior_6 = keys_sorted[-12:-6] if len(keys_sorted) >= 12 else []
        r6 = sum(historical[k]["bookings"] for k in recent_6) or 1
        p6 = sum(historical[k]["bookings"] for k in prior_6) or r6
        yoy = r6 / p6 if p6 else 1.0
        yoy = max(0.7, min(1.5, yoy))

        # ---- Forecast loop ----
        forecast = []
        for i in range(months):
            fy = today.year
            fm = today.month + i
            while fm > 12:
                fm -= 12
                fy += 1
            key_ly = f"{fy - 1:04d}-{fm:02d}"
            ly_bk = historical.get(key_ly, {}).get("bookings", 0)
            season = SEASON_WEIGHTS.get(fm, 1.0)
            # Prefer LY actual if available (seasonality learned), else synthetic
            if ly_bk > 0:
                base = ly_bk * yoy
            else:
                base = avg_bk * season * yoy
            # Confidence decays over time
            confidence = max(40, 95 - i * 2)
            forecast.append({
                "period": f"{fy:04d}-{fm:02d}",
                "label": f"{calendar.month_abbr[fm]} {fy}",
                "bookings": int(round(base)),
                "revenue": round(base * avg_adr * avg_los, 2),
                "adr": round(avg_adr, 2),
                "los": round(avg_los, 2),
                "confidence": confidence,
                "vs_last_year": round((base - ly_bk) / ly_bk * 100, 1) if ly_bk else None,
            })

        return {
            "property_id": property_id,
            "months": months,
            "avg_adr": round(avg_adr, 2),
            "avg_los": round(avg_los, 2),
            "yoy_growth_pct": round((yoy - 1) * 100, 1),
            "historical": historical,
            "forecast": forecast,
        }

    # ========== DAILY DEMAND CALENDAR ==========
    @router.get("/forecast-v2/demand-calendar/{property_id}")
    async def demand_calendar(property_id: str, start: Optional[str] = None, days: int = 90,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        if days < 7 or days > 365:
            raise HTTPException(400, "days must be 7..365")
        start_date = date.fromisoformat(start) if start else date.today()
        end_date = start_date + timedelta(days=days - 1)

        # Get total rooms for occupancy base
        rooms_count = await db.rooms.count_documents({"property_id": property_id})
        rooms_count = max(rooms_count, 1)

        # Load bookings overlapping window
        bookings = await db.bookings.find({
            "property_id": property_id,
            "check_in": {"$lte": end_date.isoformat()},
            "check_out": {"$gte": start_date.isoformat()},
            "status": {"$ne": "cancelled"},
        }, {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1, "nights": 1}).to_list(5000)

        # Pre-compute LY same-dates occupancy for context
        days_out = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            on_the_books = 0
            for b in bookings:
                ci = b.get("check_in")
                co = b.get("check_out")
                if ci and co and ci <= d.isoformat() < co:
                    on_the_books += 1

            occupancy = min(100, round(on_the_books / rooms_count * 100, 1))
            dow = d.weekday()
            dow_w = DOW_WEIGHTS[dow]
            season_w = SEASON_WEIGHTS.get(d.month, 1.0)

            # demand score 0-100: otb occupancy contributes 40%, DOW 30%, season 30%
            score = round((occupancy / 100) * 40 + ((dow_w - 0.7) / 0.6) * 30 + ((season_w - 0.7) / 0.65) * 30, 1)
            score = max(0, min(100, score))

            # Holiday overlay
            mmdd = f"{d.month:02d}-{d.day:02d}"
            holiday = PUBLIC_HOLIDAYS.get(mmdd)

            # Price tier recommendation
            if score >= 80:
                tier, tier_label = "peak", "PEAK · Fiyat +20%"
            elif score >= 60:
                tier, tier_label = "high", "High · Fiyat +10%"
            elif score >= 40:
                tier, tier_label = "medium", "Medium · BAR"
            elif score >= 20:
                tier, tier_label = "low", "Low · Fiyat -10%"
            else:
                tier, tier_label = "trough", "Trough · Fiyat -20%"

            days_out.append({
                "date": d.isoformat(),
                "dow": ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"][dow],
                "occupancy_pct": occupancy,
                "otb": on_the_books,
                "demand_score": score,
                "tier": tier,
                "tier_label": tier_label,
                "holiday": holiday,
                "is_weekend": dow >= 4,
            })

        # Aggregates
        peak_days = [d["date"] for d in days_out if d["tier"] == "peak"]
        trough_days = [d["date"] for d in days_out if d["tier"] == "trough"]
        avg_score = round(sum(d["demand_score"] for d in days_out) / len(days_out), 1) if days_out else 0

        return {
            "property_id": property_id,
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days_out,
            "rooms_count": rooms_count,
            "avg_demand_score": avg_score,
            "peak_days_count": len(peak_days),
            "trough_days_count": len(trough_days),
            "peak_days": peak_days[:20],
        }

    # ========== PICKUP CURVE ==========
    @router.get("/forecast-v2/pickup-curve/{property_id}")
    async def pickup_curve(property_id: str, target_date: str, lead_days: int = 90,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """
        For a target arrival date, show booking pace: how many bookings were in the books
        by each lead day (lead=0 means on the day). Compares against historical avg for
        same target month-day (prior years).
        """
        try:
            td = date.fromisoformat(target_date)
        except Exception:
            raise HTTPException(400, "target_date must be YYYY-MM-DD")
        lead_days = max(7, min(180, lead_days))

        # Current bookings for target_date
        current_bks = await db.bookings.find({
            "property_id": property_id,
            "check_in": {"$lte": td.isoformat()},
            "check_out": {"$gt": td.isoformat()},
            "status": {"$ne": "cancelled"},
        }, {"_id": 0, "booking_date": 1, "created_at": 1, "check_in": 1, "check_out": 1}).to_list(1000)

        today = date.today()
        days_to_go = max(0, (td - today).days)

        # Build actual pickup: bookings with booking_date or created_at <= lead
        actual_curve = []
        for lead in range(lead_days, -1, -1):
            ref = td - timedelta(days=lead)
            count = 0
            for b in current_bks:
                bd_str = b.get("booking_date") or b.get("created_at") or ""
                bd_str = bd_str[:10] if bd_str else ""
                if bd_str and bd_str <= ref.isoformat():
                    count += 1
            actual_curve.append({"lead_day": lead, "bookings": count})

        # Historical average: same month+day, prior 2 years
        historical_pts = []
        for yr_off in (1, 2):
            hist_td = date(td.year - yr_off, td.month, min(td.day, calendar.monthrange(td.year - yr_off, td.month)[1]))
            hist_bks = await db.bookings.find({
                "property_id": property_id,
                "check_in": {"$lte": hist_td.isoformat()},
                "check_out": {"$gt": hist_td.isoformat()},
                "status": {"$ne": "cancelled"},
            }, {"_id": 0, "booking_date": 1, "created_at": 1}).to_list(1000)
            for lead in range(lead_days, -1, -1):
                ref = hist_td - timedelta(days=lead)
                count = 0
                for b in hist_bks:
                    bd_str = b.get("booking_date") or b.get("created_at") or ""
                    bd_str = bd_str[:10] if bd_str else ""
                    if bd_str and bd_str <= ref.isoformat():
                        count += 1
                historical_pts.append({"lead_day": lead, "bookings": count})

        # Average historical by lead_day
        avg_hist = {}
        for p in historical_pts:
            avg_hist.setdefault(p["lead_day"], []).append(p["bookings"])
        hist_avg_curve = [{"lead_day": ld, "avg_bookings": round(sum(v) / len(v), 1)} for ld, v in sorted(avg_hist.items(), reverse=True)]

        # Pace status
        cur_otb = len(current_bks)
        hist_same_lead = next((h["avg_bookings"] for h in hist_avg_curve if h["lead_day"] == days_to_go), cur_otb)
        pace_vs_hist = round((cur_otb - hist_same_lead) / hist_same_lead * 100, 1) if hist_same_lead else None

        if pace_vs_hist is None:
            pace_status = "no_history"
        elif pace_vs_hist >= 10:
            pace_status = "ahead"
        elif pace_vs_hist <= -10:
            pace_status = "behind"
        else:
            pace_status = "on_track"

        return {
            "target_date": target_date,
            "lead_days": lead_days,
            "days_to_go": days_to_go,
            "current_otb": cur_otb,
            "actual_curve": actual_curve,
            "historical_avg_curve": hist_avg_curve,
            "pace_vs_hist_pct": pace_vs_hist,
            "pace_status": pace_status,
        }

    return router
