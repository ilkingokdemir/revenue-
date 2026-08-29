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

GLOBAL_SCAN_SEM: "asyncio.Semaphore" = None  # lazy-init (event loop gerekli)

def register(router, db, require_roles, resend, S):


    @router.get("/revenue/market-robot/{property_id}/ranking")
    async def get_ranking_analysis(property_id: str, days: int = 7,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Compute relative OTA position per date — where WE rank vs competitors on three axes:

        1. Price rank: cheapest=1 (lower = more competitive pricing)
        2. Value rank: (review_score / price) — best value=1
        3. Review rank: highest score=1 (brand strength)

        Everything is derived from already-scraped Booking.com data (our own + competitors),
        so no extra external scraping is needed. More transparent than Booking's opaque search
        rank (which depends on user history + paid placements).

        Response includes a history snapshot so the UI can show day-over-day deltas.
        """
        from datetime import date as _date
        import statistics as _stats

        # 'All Branches' mode — ranking requires a specific property, so return empty.
        if property_id == "all":
            return {
                "property_id": "all",
                "property_name": "",
                "currency": "GBP",
                "city": "",
                "rankings": [],
                "summary": {},
                "all_branches_mode": True,
            }

        # Load our hotel data
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "name": 1, "currency": 1, "city": 1, "booking_data": 1}
        )
        if not prop:
            # Graceful empty state instead of 404 so the UI doesn't crash
            return {
                "property_id": property_id,
                "property_name": "",
                "currency": "GBP",
                "city": "",
                "rankings": [],
                "summary": {},
                "missing": True,
            }
        our_bd = prop.get("booking_data") or {}
        our_daily = {p["date"]: p for p in (our_bd.get("daily_prices") or []) if p.get("lowest_price")}
        our_review = our_bd.get("review_score")

        # Load competitors + their scraped prices
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)
        comp_daily = {}  # date → list of {name, price, review}
        for c in comps:
            score = c.get("review_score")
            for p in (c.get("prices") or []):
                if not p.get("scraped") or not p.get("lowest_price"):
                    continue
                comp_daily.setdefault(p["date"], []).append({
                    "id": c["id"],
                    "name": c.get("name", ""),
                    "price": p["lowest_price"],
                    "review_score": score,
                })

        # Build per-date ranking table
        rankings = []
        today_iso = _date.today().isoformat()
        for i in range(days):
            d = (_date.today() + timedelta(days=i)).isoformat()
            our_row = our_daily.get(d)
            comps_row = comp_daily.get(d, [])
            if not our_row or not comps_row:
                rankings.append({
                    "date": d,
                    "our_price": our_row.get("lowest_price") if our_row else None,
                    "competitors_count": len(comps_row),
                    "price_rank": None, "value_rank": None, "review_rank": None,
                    "total_in_set": len(comps_row) + (1 if our_row else 0),
                    "reason": "insufficient data (our price or competitor scrapes missing)",
                })
                continue

            our_price = our_row["lowest_price"]
            # Build full set (us + competitors) then compute each rank
            full = [{"id": "self", "name": prop.get("name", "Our Hotel"), "price": our_price, "review_score": our_review, "is_self": True}]
            full.extend([{**c, "is_self": False} for c in comps_row])

            # PRICE RANK (1 = cheapest)
            by_price = sorted(full, key=lambda x: x["price"])
            price_rank = next(i + 1 for i, h in enumerate(by_price) if h.get("is_self"))

            # VALUE RANK (review_score/price — higher better)
            with_review = [h for h in full if h.get("review_score")]
            if with_review and our_review:
                by_value = sorted(with_review, key=lambda x: -x["review_score"] / max(x["price"], 1))
                value_rank = next((i + 1 for i, h in enumerate(by_value) if h.get("is_self")), None)
            else:
                value_rank = None

            # REVIEW RANK (1 = highest score)
            if with_review and our_review:
                by_review = sorted(with_review, key=lambda x: -x["review_score"])
                review_rank = next((i + 1 for i, h in enumerate(by_review) if h.get("is_self")), None)
            else:
                review_rank = None

            # Median market price for context (anomali bandı ayıklanmış)
            from routes.revenue_ext.comp_anomaly import robust_band_filter
            market_prices, _dropped = robust_band_filter([h["price"] for h in comps_row])
            median = _stats.median(market_prices) if market_prices else None

            rankings.append({
                "date": d,
                "our_price": our_price,
                "our_review": our_review,
                "market_median_price": median,
                "price_delta_pct": round((our_price - median) / median * 100, 1) if median else None,
                "competitors_count": len(comps_row),
                "total_in_set": len(full),
                "price_rank": price_rank,
                "value_rank": value_rank,
                "review_rank": review_rank,
                "cheapest_competitor": (min(comps_row, key=lambda c: c["price"])["name"]) if comps_row else None,
                "cheapest_competitor_price": min(market_prices) if market_prices else None,
            })

        # Persist today's snapshot (if any) for day-over-day tracking
        today_row = next((r for r in rankings if r["date"] == today_iso and r.get("price_rank")), None)
        previous_snap = None
        if today_row:
            previous_snap = await db.booking_ranking_history.find_one(
                {"property_id": property_id, "date": today_iso},
                {"_id": 0},
                sort=[("snapshot_at", -1)],
            )
            await db.booking_ranking_history.insert_one({
                "id": str(uuid.uuid4())[:12],
                "property_id": property_id,
                "date": today_iso,
                "snapshot_at": datetime.now(timezone.utc).isoformat(),
                **{k: today_row.get(k) for k in ("price_rank", "value_rank", "review_rank", "our_price", "market_median_price", "total_in_set")},
            })

        delta = None
        if today_row and previous_snap:
            for k in ("price_rank", "value_rank", "review_rank"):
                cur_v = today_row.get(k)
                prev_v = previous_snap.get(k)
                if cur_v and prev_v:
                    delta = delta or {}
                    delta[k] = prev_v - cur_v  # positive = we moved UP (lower rank number)

        return {
            "property_id": property_id,
            "property_name": prop.get("name", ""),
            "currency": prop.get("currency", "GBP"),
            "city": prop.get("city", ""),
            "our_review_score": our_review,
            "days_analyzed": days,
            "rankings": rankings,
            "today_rank_delta_vs_previous_snapshot": delta,
            "note": "Rankings computed from scraped Booking.com data of our hotel + competitors. No opaque search algorithm involved.",
        }

    @router.get("/revenue/market-robot/proxy-status")
    async def proxy_status(current_user: dict = Depends(require_roles("admin", "manager"))):
        """Booking.com scraper proxy configuration status.

        Reports whether a residential/rotating proxy is configured via the
        BOOKING_PROXY_URL environment variable. When unset, the scraper uses
        the pod's own IP — which Booking.com aggressively blocks for property
        detail pages (and rate-limits for search results). Setting a proxy
        from a provider like Bright Data / Smartproxy / IPRoyal / Oxylabs is
        the only reliable way to bypass these blocks.
        """
        from utils.booking_scraper import _booking_proxy_config
        cfg = _booking_proxy_config()
        return {
            "configured": cfg is not None,
            "server": cfg.get("server") if cfg else None,
            "has_auth": bool(cfg and cfg.get("username")) if cfg else False,
            "env_var": "BOOKING_PROXY_URL",
            "providers": [
                {"name": "Bright Data", "url": "https://brightdata.com/proxy-types/residential-proxies",
                 "note": "Endüstri standardı, residential IPs"},
                {"name": "Smartproxy", "url": "https://smartproxy.com/proxies/residential-proxies",
                 "note": "Daha uygun fiyat, residential"},
                {"name": "IPRoyal", "url": "https://iproyal.com/residential-proxies/",
                 "note": "Pay-as-you-go, başlangıç için ideal"},
                {"name": "Oxylabs", "url": "https://oxylabs.io/products/residential-proxy-pool",
                 "note": "Enterprise tier"},
            ],
            "example_url_format": "http://user:pass@residential.proxy.com:8080",
            "warning": (
                "Booking.com cloud/datacenter IP'leri agresif blocklar — "
                "property detail page'lerini ve sık scrape'i engelliyor. "
                "Residential proxy ile bypass edilir."
            ) if cfg is None else None,
        }

    @router.get("/revenue/market-robot/health")
    async def scanner_health(current_user: dict = Depends(require_roles("admin", "manager"))):
        """Cross-branch health dashboard. Returns every scanner's current status + 24h restart count."""
        now = datetime.now(timezone.utc)
        cutoff_24h = (now - timedelta(hours=24)).isoformat()
        props = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
        branches = []
        for p in props:
            pid = p["id"]
            cfg = await db.market_robot_config.find_one({"property_id": pid}, {"_id": 0}) or {}
            geo = await db.market_robot_geo_config.find_one({"property_id": pid}, {"_id": 0}) or {}
            status = S.scanner.get_status(pid)
            # 24h scan count from logs
            scan_cnt = await db.market_robot_logs.count_documents(
                {"property_id": pid, "scanned_at": {"$gte": cutoff_24h}}
            )
            # Latest 24h snapshot count
            snap_cnt = await db.market_supply.count_documents(
                {"property_id": pid, "scanned_at": {"$gte": cutoff_24h}}
            )
            # Last scan recency in minutes
            last_scan = cfg.get("last_scan")
            age_min = None
            if last_scan:
                try:
                    last_dt = datetime.fromisoformat(last_scan.replace("Z", "+00:00"))
                    age_min = int((now - last_dt).total_seconds() / 60)
                except Exception:
                    pass
            # Derive health
            healthy = True
            warnings = []
            if cfg.get("scanner_active") and not status.get("running"):
                healthy = False
                warnings.append("Scanner flagged active but in-memory is DOWN (watchdog should recover)")
            if cfg.get("enabled") and age_min is not None and age_min > (cfg.get("scan_interval_minutes", 60) * 2):
                healthy = False
                warnings.append(f"City scan stale · last scan {age_min} min ago (interval {cfg.get('scan_interval_minutes')})")
            if geo.get("enabled") and geo.get("last_scan"):
                try:
                    geo_age = int((now - datetime.fromisoformat(geo["last_scan"].replace("Z", "+00:00"))).total_seconds() / 60)
                    if geo_age > (geo.get("scan_interval_minutes", 120) * 2):
                        healthy = False
                        warnings.append(f"Geo scan stale · last scan {geo_age} min ago")
                except Exception:
                    pass

            branches.append({
                "property_id": pid,
                "property_name": p.get("name", pid),
                "city_scanner": {
                    "enabled": bool(cfg.get("enabled")),
                    "scanner_active": bool(cfg.get("scanner_active")),
                    "in_memory_running": bool(status.get("running")),
                    "city": cfg.get("city"),
                    "interval_min": cfg.get("scan_interval_minutes"),
                    "last_scan": last_scan,
                    "last_scan_age_min": age_min,
                    "total_scans": cfg.get("total_scans", 0),
                },
                "geo_scanner": {
                    "enabled": bool(geo.get("enabled")),
                    "location": geo.get("location"),
                    "interval_min": geo.get("scan_interval_minutes"),
                    "last_scan": geo.get("last_scan"),
                    "total_scans": geo.get("total_scans", 0),
                },
                "scans_24h": scan_cnt,
                "snapshots_24h": snap_cnt,
                "healthy": healthy,
                "warnings": warnings,
            })

        total_active = sum(1 for b in branches if b["city_scanner"]["scanner_active"] or b["city_scanner"]["enabled"] or b["geo_scanner"]["enabled"])
        total_healthy = sum(1 for b in branches if b["healthy"])
        return {
            "fetched_at": now.isoformat(),
            "branches": branches,
            "summary": {
                "total_branches": len(branches),
                "active_scanners": total_active,
                "healthy": total_healthy,
                "unhealthy": len(branches) - total_healthy,
                "total_snapshots_24h": sum(b["snapshots_24h"] for b in branches),
            },
        }

    @router.get("/revenue/market-robot/{property_id}/market-pulse")
    async def market_pulse(property_id: str, days: int = 90,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Market Pulse — 90-day demand visualization with trend line, peaks and annual perf."""
        now = datetime.now(timezone.utc)
        days = min(max(int(days), 7), 365)

        # Latest snapshot per date (same aggregation as supply endpoint)
        pipeline = [
            {"$match": {"property_id": property_id}},
            {"$sort": {"scanned_at": -1}},
            {"$group": {"_id": "$date", "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$sort": {"date": 1}},
            {"$project": {"_id": 0}},
        ]
        all_snaps = await db.market_supply.aggregate(pipeline).to_list(1000)

        # Keep future-facing N days (today .. today+days)
        today_str = now.strftime("%Y-%m-%d")
        horizon_end = (now + timedelta(days=days)).strftime("%Y-%m-%d")
        snaps = [s for s in all_snaps if today_str <= s.get("date", "") <= horizon_end]

        # Event overlay
        events_list = await db.market_events.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        event_dates = {}
        for ev in events_list:
            ds = ev.get("date", "")
            if ds:
                event_dates[ds] = {
                    "name": ev.get("name", ""),
                    "impact": ev.get("impact", ""),
                    "hotel_demand_score": ev.get("hotel_demand_score", 0),
                }

        # Build bars: demand_score = unavailable_pct (0-100)
        bars = []
        for s in snaps:
            d = s.get("date", "")
            score = int(s.get("unavailable_pct", 0) or 0)
            ev = event_dates.get(d)
            kind = "normal"
            if ev and ev.get("impact") in ("mega", "large"):
                kind = "peak_event"  # red
            elif score >= 85:
                kind = "peak_high"  # amber
            elif score <= 25:
                kind = "low"
            bars.append({
                "date": d,
                "score": score,
                "kind": kind,
                "event": ev.get("name") if ev else "",
                "event_impact": ev.get("impact") if ev else "",
            })

        # 7-day moving average trend
        trend = []
        scores = [b["score"] for b in bars]
        for i in range(len(bars)):
            start = max(0, i - 3)
            end = min(len(bars), i + 4)
            window = scores[start:end]
            avg = round(sum(window) / len(window), 1) if window else 0
            trend.append({"date": bars[i]["date"], "value": avg})

        # Delta: last 30 days avg vs preceding 30 days avg (both within horizon)
        n = len(bars)
        if n >= 60:
            recent = sum(scores[n - 30:]) / 30
            prior = sum(scores[n - 60:n - 30]) / 30
            delta_pp = round(recent - prior, 1)
        elif n >= 14:
            half = n // 2
            recent = sum(scores[half:]) / max(1, n - half)
            prior = sum(scores[:half]) / max(1, half)
            delta_pp = round(recent - prior, 1)
        else:
            delta_pp = 0.0

        trend_label = "strengthening" if delta_pp > 1 else ("weakening" if delta_pp < -1 else "stable")

        # Annual performance — monthly OCC/ADR/REV for current year vs prev year
        this_year = now.year
        last_year = this_year - 1

        async def _month_agg(year: int):
            # Room inventory
            rooms = await db.rooms.count_documents({"property_id": property_id}) or 1
            # Bookings overlapping month
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            q = {
                "property_id": property_id,
                "status": {"$nin": ["cancelled", "no_show"]},
                "check_in": {"$lt": end.isoformat()},
                "check_out": {"$gt": start.isoformat()},
            }
            bookings = await db.bookings.find(q, {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1}).to_list(10000)
            months = [{"occ_nights": 0, "revenue": 0.0, "days_in_month": 0} for _ in range(12)]
            for m in range(12):
                m_start = datetime(year, m + 1, 1, tzinfo=timezone.utc)
                m_end = datetime(year + (1 if m == 11 else 0), (m + 2) if m < 11 else 1, 1, tzinfo=timezone.utc)
                days_m = (m_end - m_start).days
                months[m]["days_in_month"] = days_m
            for b in bookings:
                try:
                    ci = datetime.fromisoformat(b["check_in"].replace("Z", "+00:00"))
                    co = datetime.fromisoformat(b["check_out"].replace("Z", "+00:00"))
                except Exception:
                    continue
                total_nights = max(1, (co.date() - ci.date()).days)
                per_night = float(b.get("total_price", 0) or 0) / total_nights
                d = ci
                while d < co:
                    if d.year == year:
                        months[d.month - 1]["occ_nights"] += 1
                        months[d.month - 1]["revenue"] += per_night
                    d += timedelta(days=1)
            out = []
            for m, mdata in enumerate(months):
                inv_nights = rooms * mdata["days_in_month"]
                occ_pct = round((mdata["occ_nights"] / inv_nights) * 100, 1) if inv_nights else 0
                adr = round(mdata["revenue"] / mdata["occ_nights"], 2) if mdata["occ_nights"] else 0
                out.append({
                    "month": m + 1,
                    "occ_pct": occ_pct,
                    "adr": adr,
                    "revenue": round(mdata["revenue"], 2),
                })
            return out

        curr = await _month_agg(this_year)
        prev = await _month_agg(last_year)

        monthly = []
        tot_prev_rev = sum(p["revenue"] for p in prev)
        tot_curr_rev = sum(c["revenue"] for c in curr)
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for i in range(12):
            p = prev[i]
            c = curr[i]
            delta_rev = round(c["revenue"] - p["revenue"], 2)
            delta_pct = round((delta_rev / p["revenue"]) * 100, 1) if p["revenue"] else 0
            monthly.append({
                "month": month_names[i],
                "month_num": i + 1,
                "prev_occ": p["occ_pct"], "prev_adr": p["adr"], "prev_rev": p["revenue"],
                "curr_occ": c["occ_pct"], "curr_adr": c["adr"], "curr_rev": c["revenue"],
                "delta_pct": delta_pct, "delta_rev": delta_rev,
                "is_mtd": (i + 1 == now.month),
            })

        return {
            "property_id": property_id,
            "days": days,
            "as_of": now.isoformat(),
            "bars": bars,
            "trend": trend,
            "summary": {
                "dates_count": len(bars),
                "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                "peak_days": sum(1 for b in bars if b["kind"] in ("peak_high", "peak_event")),
                "delta_pp": delta_pp,
                "trend_label": trend_label,
            },
            "annual": {
                "prev_year": last_year,
                "curr_year": this_year,
                "monthly": monthly,
                "totals": {
                    "prev_rev": round(tot_prev_rev, 2),
                    "curr_rev": round(tot_curr_rev, 2),
                    "delta_pct": round(((tot_curr_rev - tot_prev_rev) / tot_prev_rev) * 100, 1) if tot_prev_rev else 0,
                },
            },
        }

    async def _safe_do_scan(pid: str, payload: Dict, label: str = "city"):
        """Background-friendly wrapper around _do_scan. Logs errors but never raises
        so a single failing property cannot crash the auto-scan loop.

        Hot-reload (uvicorn --reload) closes the Mongo client while old tasks
        are still in flight in the *previous* event loop. Those raise
        ``Cannot use MongoClient after close``. That is harmless noise — the
        new process will re-fire the scan — so we demote it to INFO.
        """
        try:
            global GLOBAL_SCAN_SEM
            if GLOBAL_SCAN_SEM is None:
                GLOBAL_SCAN_SEM = asyncio.Semaphore(MAX_CONCURRENT_SCANS)
            async with GLOBAL_SCAN_SEM:
                # Otomatik taramalarda gün sayısını sınırla (manuel HTTP taraması etkilenmez)
                payload = {**payload, "days_ahead": min(
                    int(payload.get("days_ahead") or AUTO_SCAN_MAX_DAYS), AUTO_SCAN_MAX_DAYS)}
                await S._do_scan(pid, payload)
        except Exception as e:
            msg = str(e)
            if "MongoClient after close" in msg or "Event loop is closed" in msg:
                logger.info(f"Auto {label}-scan {pid} aborted (process recycling) — harmless")
                return
            logger.exception(f"Auto {label}-scan task failed for {pid}: {e}")

    async def _safe_do_geo_scan(pid: str, cfg: Dict):
        """Geo wrapper that also stamps last_scan/total_scans on success."""
        try:
            await S._do_scan(pid, {
                "mode": "geo",
                "location": cfg.get("location") or "",
                "latitude": cfg.get("latitude"),
                "longitude": cfg.get("longitude"),
                "radius_km": float(cfg.get("radius_km") or 3.2),
                "days_ahead": int(cfg.get("days_ahead") or 30),
            })
            await db.market_robot_geo_config.update_one(
                {"property_id": pid},
                {"$set": {"last_scan": datetime.now(timezone.utc).isoformat()},
                 "$inc": {"total_scans": 1}},
            )
        except Exception as e:
            logger.exception(f"Auto geo-scan task failed for {pid}: {e}")

    async def _boosted_interval(pid: str, interval: int) -> int:
        """Önümüzdeki 7 günün doluluğu ≥%60 ise tarama aralığını 1/3'e indirir (min 15 dk)."""
        from datetime import date as _date
        today = _date.today().isoformat()
        horizon = (_date.today() + timedelta(days=7)).isoformat()
        sold = 0
        async for b in db.bookings.find(
                {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                 "check_in": {"$gte": today, "$lt": horizon}}, {"_id": 0, "nights": 1}):
            sold += min(int(b.get("nights") or 0), 7)
        rooms = await db.rooms.count_documents({"property_id": pid})
        occ = sold / max(1, rooms * 7)
        return max(15, interval // 3) if occ >= 0.6 else interval

    async def auto_scan_loop():
        """Background loop: every 60s check enabled market-robot configs and trigger due scans.
        Handles BOTH city scans (market_robot_config) AND geo scans (market_robot_geo_config) in parallel."""
        logger.info("🛰️ Market Robot auto-scan loop started")
        # Auto-resume Smart Scanner if user had it ON before restart
        try:
            await S.scanner.resume_if_active()
        except Exception as e:
            logger.warning(f"Smart Scanner resume skipped: {e}")
        _bootstrap_tick = 0
        while True:
            try:
                # === Auto-bootstrap missing configs every 10 loops (~10 min) ===
                # Ensures new properties auto-enable continuous scanning without admin action.
                _bootstrap_tick += 1
                if _bootstrap_tick % 10 == 1:
                    try:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        props_list = await db.properties.find({}, {"_id": 0}).to_list(500)
                        for pp in props_list:
                            pid_ = pp.get("id")
                            if not pid_ or pid_ in ("all", "default"):
                                continue
                            existing_ = await db.market_robot_config.find_one({"property_id": pid_}, {"_id": 0})
                            if existing_ is None:
                                await db.market_robot_config.insert_one({
                                    "property_id": pid_,
                                    # Iter 378: yeni tesisler için varsayılan KAPALI —
                                    # 49 tesis × 365 gün otomatik tarama event loop'u boğuyordu.
                                    "enabled": False,
                                    "scan_interval_minutes": 60,
                                    "city": pp.get("city") or "London",
                                    "language": "en-gb",
                                    "auto_pricing": False,
                                    "days_ahead": 30,
                                    "total_scans": 0,
                                    "created_at": now_iso,
                                    "created_by": "auto-bootstrap-loop",
                                })
                                logger.info(f"🌱 Auto-bootstrapped market_robot_config for {pid_} (disabled by default)")
                            elif existing_.get("enabled") is None or existing_.get("scan_interval_minutes") is None:
                                await db.market_robot_config.update_one(
                                    {"property_id": pid_},
                                    {"$set": {
                                        "enabled": False if existing_.get("enabled") is None else existing_.get("enabled"),
                                        "scan_interval_minutes": existing_.get("scan_interval_minutes") or 60,
                                        "updated_at": now_iso,
                                        "updated_by": "auto-bootstrap-loop",
                                    }},
                                )
                                logger.info(f"🌱 Auto-bootstrap repaired config for {pid_}")
                    except Exception as e:
                        logger.warning(f"Auto-bootstrap tick error: {e}")
                # === City scans (parallel per-property) ===
                configs = await db.market_robot_config.find({"enabled": True}, {"_id": 0}).to_list(500)
                now = datetime.now(timezone.utc)
                for cfg in configs:
                    pid = cfg.get("property_id")
                    if not pid or pid == "all":
                        continue
                    interval = int(cfg.get("scan_interval_minutes") or 60)
                    # Yakın-dönem kadans hızlandırma: önümüzdeki 7 gün yoğunsa 3 kat sık tara
                    if cfg.get("near_term_boost", True):
                        try:
                            interval = await _boosted_interval(pid, interval)
                        except Exception:
                            pass
                    last = cfg.get("last_scan")
                    due = True
                    if last:
                        try:
                            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                            due = (now - last_dt) >= timedelta(minutes=interval)
                        except Exception:
                            due = True
                    # Per-property lock check — different properties scan in parallel
                    if due and not SCRAPE_LOCKS.get(pid):
                        logger.info(f"🛰️ Auto city-scan triggered for {pid} (parallel)")
                        asyncio.create_task(_safe_do_scan(pid, {}, label="city"))

                # === Geo scans (parallel per-property, also parallel with city) ===
                geo_configs = await db.market_robot_geo_config.find({"enabled": True}, {"_id": 0}).to_list(500)
                for cfg in geo_configs:
                    pid = cfg.get("property_id")
                    loc = cfg.get("location") or ""
                    if not pid or pid == "all" or not (loc or (cfg.get("latitude") and cfg.get("longitude"))):
                        continue
                    interval = int(cfg.get("scan_interval_minutes") or 120)
                    last = cfg.get("last_scan")
                    due = True
                    if last:
                        try:
                            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                            due = (now - last_dt) >= timedelta(minutes=interval)
                        except Exception:
                            due = True
                    if due and not SCRAPE_LOCKS_GEO.get(pid):
                        logger.info(f"🛰️ Auto geo-scan triggered for {pid} @ {loc} (parallel)")
                        asyncio.create_task(_safe_do_geo_scan(pid, cfg))

                # === Smart Scanner watchdog — check all properties (multi-instance) ===
                try:
                    await S.scanner.watchdog()
                except Exception as e:
                    logger.warning(f"Scanner watchdog error: {e}")

                # === Auto-Heal scheduler — periodically runs _do_auto_heal_competitors
                # for every property that opted in. Each property's config says how often
                # to heal (interval_minutes) and what hit-rate floor triggers healing.
                try:
                    heal_cfgs = await db.market_robot_autoheal_config.find(
                        {"enabled": True}, {"_id": 0}
                    ).to_list(500)
                    for hc in heal_cfgs:
                        pid = hc.get("property_id")
                        if not pid or pid == "all":
                            continue
                        interval = int(hc.get("interval_minutes") or 60)
                        last = hc.get("last_run")
                        due = True
                        if last:
                            try:
                                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                                due = (now - last_dt) >= timedelta(minutes=interval)
                            except Exception:
                                due = True
                        if due:
                            logger.info(f"🩺 Auto-Heal scheduled run for {pid} (threshold={hc.get('threshold')}%)")
                            try:
                                result = await S._do_auto_heal_competitors(
                                    db, pid,
                                    days_ahead=int(hc.get("days_ahead") or 30),
                                    threshold=int(hc.get("threshold") or 50),
                                )
                                await db.market_robot_autoheal_config.update_one(
                                    {"property_id": pid},
                                    {"$set": {"last_run": datetime.now(timezone.utc).isoformat(),
                                              "last_result": result},
                                     "$inc": {"total_runs": 1}},
                                )
                            except Exception as e:
                                logger.exception(f"Scheduled Auto-Heal failed for {pid}: {e}")
                except Exception as e:
                    logger.warning(f"Auto-Heal scheduler error: {e}")

                # === Weekly email summary (Mondays 09:00 UTC) ===
                if now.weekday() == 0 and now.hour == 9 and now.minute < 2:
                    email_cfgs = await db.market_robot_competitive_config.find(
                        {"weekly_email_enabled": True, "email_recipients": {"$exists": True, "$ne": []}},
                        {"_id": 0},
                    ).to_list(200)
                    for ec in email_cfgs:
                        pid = ec.get("property_id")
                        last = ec.get("last_weekly_email_at")
                        # Dedup: only send if last send was > 6 days ago
                        should_send = True
                        if last:
                            try:
                                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                                should_send = (now - last_dt) >= timedelta(days=6)
                            except Exception:
                                should_send = True
                        if not should_send or not resend:
                            continue
                        try:
                            summary = await S._build_weekly_summary(pid, 7)
                            sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
                            resend.emails.send({
                                "from": sender,
                                "to": ec["email_recipients"],
                                "subject": f"Market Robot Haftalık Özet · {summary['property_name']} · {summary['stats']['rate_changes']} rate değişiklik",
                                "html": summary["html"],
                            })
                            await db.market_robot_competitive_config.update_one(
                                {"property_id": pid},
                                {"$set": {"last_weekly_email_at": now.isoformat()}},
                            )
                            await db.market_robot_email_log.insert_one({
                                "id": str(uuid.uuid4()),
                                "property_id": pid,
                                "recipients": ec["email_recipients"],
                                "stats": summary["stats"],
                                "sent_at": now.isoformat(),
                                "sent_by": "auto-scheduler",
                            })
                            logger.info(f"📧 Weekly summary sent to {len(ec['email_recipients'])} recipients for {pid}")
                        except Exception as e:
                            logger.warning(f"Weekly email failed for {pid}: {e}")
            except Exception as e:
                logger.exception(f"Market Robot loop error: {e}")
            await asyncio.sleep(60)

    # Expose for server.py startup
    router.auto_scan_loop = auto_scan_loop

    S._safe_do_geo_scan = _safe_do_geo_scan
    S._safe_do_scan = _safe_do_scan
    S.auto_scan_loop = auto_scan_loop
    S.get_ranking_analysis = get_ranking_analysis
    S.market_pulse = market_pulse
    S.proxy_status = proxy_status
    S.scanner_health = scanner_health
