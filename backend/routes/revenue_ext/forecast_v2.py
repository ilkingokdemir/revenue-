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


SEGMENT_MAP = {
    "booking.com": "OTA", "expedia": "OTA", "agoda": "OTA", "airbnb": "OTA",
    "hotels.com": "OTA", "google": "OTA", "affiliate": "OTA",
    "direct": "Direkt", "website": "Direkt", "phone": "Direkt", "walk-in": "Direkt",
    "agency": "Acente", "corporate": "Kurumsal",
}


def _segment_of(source: str) -> str:
    s = (source or "").strip().lower()
    if s in SEGMENT_MAP:
        return SEGMENT_MAP[s]
    if "agency" in s or "travel" in s or "acente" in s:
        return "Acente"
    if "corp" in s:
        return "Kurumsal"
    return "Diğer"


async def compute_horizon(db, property_id: str, months: int = 24):
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

    # Uncertainty band: last-12 volatility (CV), horizon ile genişler
    bks_12 = [x["bookings"] for x in last_12 if x["bookings"] > 0]
    if len(bks_12) >= 3:
        mean_bk = sum(bks_12) / len(bks_12)
        var_bk = sum((b - mean_bk) ** 2 for b in bks_12) / len(bks_12)
        cv = (var_bk ** 0.5) / mean_bk if mean_bk else 0.2
    else:
        cv = 0.2
    cv = max(0.08, min(cv, 0.40))

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
        band = min(cv * (1 + i * 0.05), 0.5)
        rev = round(base * avg_adr * avg_los, 2)
        forecast.append({
            "period": f"{fy:04d}-{fm:02d}",
            "label": f"{calendar.month_abbr[fm]} {fy}",
            "bookings": int(round(base)),
            "bookings_low": int(round(base * (1 - band))),
            "bookings_high": int(round(base * (1 + band))),
            "revenue": rev,
            "revenue_low": round(rev * (1 - band), 2),
            "revenue_high": round(rev * (1 + band), 2),
            "band_pct": round(band * 100, 1),
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
        "uncertainty_cv_pct": round(cv * 100, 1),
        "historical": historical,
        "forecast": forecast,
    }


def create_forecast_v2_router(db, require_roles):
    router = APIRouter()

    # ========== SEGMENT FORECAST (Duetto-style breakdown) ==========
    @router.get("/forecast-v2/segments/{property_id}")
    async def segment_forecast(property_id: str, months: int = 6,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """12-month segment history (Direkt/OTA/Acente/Kurumsal/Diğer) + N-month forecast per segment."""
        months = min(max(months, 3), 12)
        today = datetime.now(timezone.utc).date()
        hist_start = (today.replace(day=1) - timedelta(days=370)).replace(day=1)
        pq = {} if property_id == "all" else {"property_id": property_id}
        bookings = await db.bookings.find({
            **pq, "status": {"$nin": ["cancelled", "no_show"]},
            "check_in": {"$gte": hist_start.isoformat()},
        }, {"_id": 0, "check_in": 1, "source": 1, "total_price": 1}).to_list(100000)

        # monthly history per segment
        hist = {}
        for b in bookings:
            ci = b.get("check_in", "")[:7]
            if not ci:
                continue
            seg = _segment_of(b.get("source", ""))
            key = (ci, seg)
            e = hist.setdefault(key, {"bookings": 0, "revenue": 0.0})
            e["bookings"] += 1
            e["revenue"] += float(b.get("total_price", 0) or 0)

        segments = sorted({seg for _, seg in hist.keys()}) or ["Direkt", "OTA"]
        cur_month = today.strftime("%Y-%m")
        history_months = sorted({m for m, _ in hist.keys() if m <= cur_month})[-12:]
        history = []
        for m in history_months:
            row = {"month": m, "type": "actual"}
            for seg in segments:
                e = hist.get((m, seg), {"bookings": 0, "revenue": 0.0})
                row[seg] = {"bookings": e["bookings"], "revenue": round(e["revenue"], 2)}
            history.append(row)

        # forecast: same-month-last-year × yoy trend (per segment)
        seg_recent, seg_prior = {}, {}
        for (m, seg), e in hist.items():
            idx = history_months.index(m) if m in history_months else -1
            if idx < 0:
                continue
            (seg_recent if idx >= len(history_months) - 6 else seg_prior).setdefault(seg, 0)
            if idx >= len(history_months) - 6:
                seg_recent[seg] += e["bookings"]
            else:
                seg_prior[seg] += e["bookings"]

        forecast = []
        cur = today.replace(day=1)
        for i in range(1, months + 1):
            y, mo = cur.year + (cur.month + i - 1) // 12, (cur.month + i - 1) % 12 + 1
            ms = f"{y:04d}-{mo:02d}"
            lym = f"{y-1:04d}-{mo:02d}"
            row = {"month": ms, "type": "forecast"}
            for seg in segments:
                base = hist.get((lym, seg), {}).get("bookings", 0)
                base_rev = hist.get((lym, seg), {}).get("revenue", 0.0)
                if base == 0:  # fallback: segment monthly avg
                    seg_months = [hist[(m2, seg)]["bookings"] for m2 in history_months if (m2, seg) in hist]
                    base = round(sum(seg_months) / len(seg_months)) if seg_months else 0
                    seg_revs = [hist[(m2, seg)]["revenue"] for m2 in history_months if (m2, seg) in hist]
                    base_rev = (sum(seg_revs) / len(seg_revs)) if seg_revs else 0.0
                trend = 1.0
                if seg_prior.get(seg, 0) >= 5:
                    trend = max(0.7, min(1.5, seg_recent.get(seg, 0) / seg_prior[seg]))
                fb = round(base * trend)
                fr = round(base_rev * trend, 2)
                otb = hist.get((ms, seg), {})
                fb = max(fb, otb.get("bookings", 0))
                fr = max(fr, round(otb.get("revenue", 0.0), 2))
                row[seg] = {"bookings": fb, "revenue": fr}
            forecast.append(row)

        totals = {seg: {"hist_bookings": sum(hist.get((m, seg), {}).get("bookings", 0) for m in history_months),
                        "hist_revenue": round(sum(hist.get((m, seg), {}).get("revenue", 0.0) for m in history_months), 2)}
                  for seg in segments}
        return {"property_id": property_id, "segments": segments,
                "history": history, "forecast": forecast, "totals": totals}

    # ========== 24-MONTH HORIZON ==========
    @router.get("/forecast-v2/horizon/{property_id}")
    async def horizon(property_id: str, months: int = 24,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        if months < 3 or months > 36:
            raise HTTPException(400, "months must be 3..36")
        return await compute_horizon(db, property_id, months)

    # ========== DAILY DEMAND CALENDAR ==========
    # iter 372: extended horizon to 730 days (2 years) with hybrid modeling —
    # OTB-based for near-term (< 365d), fully synthetic (season × DOW × yoy) beyond.
    @router.get("/forecast-v2/demand-calendar/{property_id}")
    async def demand_calendar(property_id: str, start: Optional[str] = None, days: int = 90,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        if days < 7 or days > 730:
            raise HTTPException(400, "days must be 7..730")
        start_date = date.fromisoformat(start) if start else date.today()
        end_date = start_date + timedelta(days=days - 1)

        # Get total rooms for occupancy base
        rooms_count = await db.rooms.count_documents({"property_id": property_id})
        rooms_count = max(rooms_count, 1)

        # ---- Historical baseline for far-future forecasting (iter 372) ----
        # Compute average daily occupancy per (month, dow) from last 12 months.
        today = date.today()
        one_yr_ago = today - timedelta(days=365)
        hist_bks = await db.bookings.find({
            "property_id": property_id,
            "check_in":  {"$gte": one_yr_ago.isoformat(), "$lte": today.isoformat()},
            "status": {"$ne": "cancelled"},
        }, {"_id": 0, "check_in": 1, "check_out": 1}).to_list(20000)

        # Build (month, dow) -> [otb counts]
        hist_bucket: dict = {}
        for i in range(365):
            d = one_yr_ago + timedelta(days=i)
            otb = 0
            for b in hist_bks:
                ci = b.get("check_in")
                co = b.get("check_out")
                if ci and co and ci <= d.isoformat() < co:
                    otb += 1
            hist_bucket.setdefault((d.month, d.weekday()), []).append(otb)
        hist_avg = {k: (sum(v) / len(v) if v else 0) for k, v in hist_bucket.items()}
        # If no history at all, fall back to modeled synthetic (rooms_count * season * dow * 0.5)
        has_history = any(hist_bucket.values())

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

            # Days-out from today — used to blend OTB with forecast baseline
            days_from_today = (d - today).days
            dow = d.weekday()
            dow_w = DOW_WEIGHTS[dow]
            season_w = SEASON_WEIGHTS.get(d.month, 1.0)

            # Baseline from historical (month, dow) bucket; synthetic if no history
            if has_history:
                baseline = hist_avg.get((d.month, dow), 0)
            else:
                baseline = rooms_count * 0.5 * season_w * dow_w

            # Forecast OTB: OTB dominates near-term; baseline dominates far-term.
            # Blend weight = 1 when d = today, linearly to 0 at day 180+.
            if days_from_today <= 0:
                blend = 1.0
            elif days_from_today >= 180:
                blend = 0.0
            else:
                blend = 1 - (days_from_today / 180.0)
            forecast_otb = round(on_the_books * blend + baseline * (1 - blend), 1)

            # occupancy fields: 'occupancy_pct' remains OTB-based for compatibility.
            occupancy = min(100, round(on_the_books / rooms_count * 100, 1))
            forecast_occupancy_pct = min(100, round(forecast_otb / rooms_count * 100, 1))

            # demand score 0-100: forecast_occ contributes 40%, DOW 30%, season 30%
            score = round((forecast_occupancy_pct / 100) * 40 + ((dow_w - 0.7) / 0.6) * 30 + ((season_w - 0.7) / 0.65) * 30, 1)
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

            # Confidence: near-term (real OTB) = high, far-term (model) = decays
            confidence = max(35, 100 - abs(days_from_today) // 10) if days_from_today > 0 else 95

            days_out.append({
                "date": d.isoformat(),
                "dow": ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"][dow],
                "occupancy_pct": occupancy,
                "forecast_occupancy_pct": forecast_occupancy_pct,
                "otb": on_the_books,
                "forecast_otb": forecast_otb,
                "demand_score": score,
                "confidence": confidence,
                "tier": tier,
                "tier_label": tier_label,
                "holiday": holiday,
                "is_weekend": dow >= 4,
                "is_forecast": days_from_today > 60,
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

    # ========== 2-YEAR (24-MONTH) SUMMARY (iter 372) ==========
    # RMS Atomize parity: quarterly aggregates + YoY chart + confidence bands.
    @router.get("/forecast-v2/two-year-summary/{property_id}")
    async def two_year_summary(property_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Executive-level 24-month forward summary with quarterly breakdown,
        Year-1 vs Year-2 comparison, and low/mid/high revenue confidence bands."""
        today = date.today()

        # Build historical monthly stats (last 12 months) — same logic as horizon()
        historical: Dict[str, Dict] = {}
        for i in range(12, 0, -1):
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
                "bookings": n, "revenue": round(rev, 2),
                "adr": round(rev / nights, 2) if nights else 0,
                "avg_los": round(nights / n, 2) if n else 0,
            }

        last_12 = list(historical.values())
        avg_bk = sum(x["bookings"] for x in last_12) / max(len(last_12), 1)
        avg_adr = sum(x["adr"] for x in last_12 if x["adr"] > 0) / max(sum(1 for x in last_12 if x["adr"] > 0), 1) or 120
        avg_los = sum(x["avg_los"] for x in last_12 if x["avg_los"] > 0) / max(sum(1 for x in last_12 if x["avg_los"] > 0), 1) or 2.0

        keys_sorted = sorted(historical.keys())
        recent_6 = keys_sorted[-6:] if len(keys_sorted) >= 6 else keys_sorted
        prior_6 = keys_sorted[-12:-6] if len(keys_sorted) >= 12 else []
        r6 = sum(historical[k]["bookings"] for k in recent_6) or 1
        p6 = sum(historical[k]["bookings"] for k in prior_6) or r6
        yoy = max(0.7, min(1.5, r6 / p6 if p6 else 1.0))

        # Build 24-month forecast
        monthly: List[Dict] = []
        for i in range(24):
            fy = today.year
            fm = today.month + i
            while fm > 12:
                fm -= 12
                fy += 1
            season = SEASON_WEIGHTS.get(fm, 1.0)
            base_bk = avg_bk * season * yoy
            # For year-2, apply compound yoy again
            if i >= 12:
                base_bk *= yoy
            revenue = base_bk * avg_adr * avg_los
            # Confidence bands (±15% mid, ±30% low/high)
            confidence = max(35, 95 - i * 2)
            monthly.append({
                "period": f"{fy:04d}-{fm:02d}",
                "label": f"{calendar.month_abbr[fm]} {fy}",
                "year_offset": 1 if i < 12 else 2,
                "quarter": (fm - 1) // 3 + 1,
                "bookings": int(round(base_bk)),
                "revenue": round(revenue, 2),
                "revenue_low": round(revenue * 0.70, 2),
                "revenue_high": round(revenue * 1.30, 2),
                "adr": round(avg_adr, 2),
                "los": round(avg_los, 2),
                "confidence": confidence,
                "season_factor": round(season, 2),
            })

        # Yearly + quarterly aggregates
        y1 = [m for m in monthly if m["year_offset"] == 1]
        y2 = [m for m in monthly if m["year_offset"] == 2]

        def _agg(rows):
            return {
                "bookings":     sum(r["bookings"] for r in rows),
                "revenue":      round(sum(r["revenue"] for r in rows), 2),
                "revenue_low":  round(sum(r["revenue_low"] for r in rows), 2),
                "revenue_high": round(sum(r["revenue_high"] for r in rows), 2),
            }

        year1 = _agg(y1)
        year2 = _agg(y2)
        yoy_growth = round((year2["revenue"] - year1["revenue"]) / year1["revenue"] * 100, 1) if year1["revenue"] else None

        # Quarterly aggregates for chart
        quarterly: List[Dict] = []
        for yr_off, rows in [(1, y1), (2, y2)]:
            for q in range(1, 5):
                qrows = [r for r in rows if r["quarter"] == q]
                if qrows:
                    quarterly.append({
                        "label": f"Y{yr_off} Q{q}",
                        "year_offset": yr_off,
                        "quarter": q,
                        **_agg(qrows),
                    })

        # Peak/trough months
        top_5 = sorted(monthly, key=lambda x: x["revenue"], reverse=True)[:5]
        bottom_5 = sorted(monthly, key=lambda x: x["revenue"])[:5]

        return {
            "property_id":  property_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "assumptions":  {
                "avg_adr":         round(avg_adr, 2),
                "avg_los":         round(avg_los, 2),
                "yoy_growth_pct":  round((yoy - 1) * 100, 1),
                "historical_months": len(last_12),
            },
            "year_1_total":  year1,
            "year_2_total":  year2,
            "yoy_growth_pct": yoy_growth,
            "monthly":       monthly,
            "quarterly":     quarterly,
            "top_5_months":  [{"label": m["label"], "revenue": m["revenue"]} for m in top_5],
            "bottom_5_months": [{"label": m["label"], "revenue": m["revenue"]} for m in bottom_5],
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
