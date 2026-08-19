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

    async def _do_scan(property_id: str, data: Dict):
        """Core scan logic — callable from HTTP endpoint and background loop.
        Supports two modes:
          - city (default): whole-city scan via text (e.g. "London")
          - geo: radius scan around a postcode/address/coordinates

        Concurrency: uses PER-PROPERTY locks (SCRAPE_LOCKS / SCRAPE_LOCKS_GEO) so
        every property can scan independently in parallel. A property cannot
        double-scan itself, but unrelated properties never block each other.
        """
        config = await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        mode = (data.get("mode") or "city").lower()
        is_geo = mode == "geo"

        # Per-property locks → unrelated properties scan in parallel
        if is_geo and SCRAPE_LOCKS_GEO.get(property_id):
            return {"error": f"Geo scan already in progress for {property_id}", "status": "busy"}
        if not is_geo and SCRAPE_LOCKS.get(property_id):
            return {"error": f"City scan already in progress for {property_id}", "status": "busy"}

        # Resolve scan location
        if is_geo:
            location = data.get("location") or data.get("postcode") or data.get("address") or ""
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            radius_km = float(data.get("radius_km") or data.get("radius") or 3.2)  # default ~2 miles
            if not location and (latitude is None or longitude is None):
                return {"error": "Geo scan requires 'location' (postcode/address) or latitude+longitude", "status": "error"}
            scan_label = f"{location or f'{latitude},{longitude}'} · {radius_km}km"
        else:
            location = data.get("city") or config.get("city", "London")
            latitude = longitude = radius_km = None
            scan_label = location

        days_ahead = min(int(data.get("days_ahead") or config.get("days_ahead", 365)), 365)
        auto_pricing = config.get("auto_pricing", True) and not is_geo  # geo scans don't auto-price main property
        language = config.get("language", "en-gb")
        # Pin Booking.com price rendering to a consistent ISO currency so all prices in the
        # snapshot collection are comparable. Order: explicit request param → property record
        # (most authoritative for geo scans) → mr config → default GBP.
        prop_doc = await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        scan_currency = (
            data.get("currency")
            or (prop_doc.get("currency") if is_geo else None)
            or config.get("currency")
            or "GBP"
        )

        if is_geo:
            SCRAPE_LOCKS_GEO[property_id] = True
        else:
            SCRAPE_LOCKS[property_id] = True
        now = datetime.now(timezone.utc)
        scan_id = str(uuid.uuid4())[:8]
        snapshots = []

        try:
            # Scan ALL days for complete coverage
            scan_dates = []
            for i in range(days_ahead):
                d = now + timedelta(days=i)
                scan_dates.append(d)
            scan_dates.sort()

            # Per-date worker — runs in parallel under a Semaphore so we don't
            # hammer Booking.com or exhaust browser contexts. 4 concurrent
            # scrapes brings a 30-day scan from ~3min sequential to ~50-80s,
            # which fits comfortably inside the proxy/ingress 120s timeout.
            scan_sem = asyncio.Semaphore(4)

            async def _scan_one_date(d):
                checkin = d.strftime("%Y-%m-%d")
                checkout = (d + timedelta(days=1)).strftime("%Y-%m-%d")
                async with scan_sem:
                    supply = await S._scrape_booking_date(
                        location, checkin, checkout, language,
                        latitude=latitude, longitude=longitude, radius_km=radius_km,
                        currency=scan_currency,
                    )
                prev = await db.market_supply.find_one(
                    {"property_id": property_id, "date": checkin, "scan_type": "geo" if is_geo else "city"},
                    {"_id": 0},
                    sort=[("scanned_at", -1)]
                )
                adj_pct, reason = (0, "Geo scan (informational only)") if is_geo else \
                    await S._calculate_price_adjustment(db, property_id, checkin, supply, prev)
                snapshot = {
                    "scan_id": scan_id,
                    "property_id": property_id,
                    "scan_type": "geo" if is_geo else "city",
                    "city": location if not is_geo else "",
                    "location": location if is_geo else "",
                    "latitude": latitude, "longitude": longitude, "radius_km": radius_km,
                    "date": checkin,
                    "total_properties": supply["total_properties"],
                    "total_source": supply.get("total_source", "unknown"),
                    "unavailable_pct": supply["unavailable_pct"],
                    "available_pct": supply["available_pct"],
                    "available_est": supply["available_est"],
                    "avg_price": supply.get("avg_price", 0),
                    "min_price": supply.get("min_price", 0),
                    "max_price": supply.get("max_price", 0),
                    "median_price": supply.get("median_price", 0),
                    "price_samples": supply.get("price_samples", 0),
                    "scraped": supply["scraped"],
                    "method": supply.get("method", "unknown"),
                    "price_adjustment_pct": adj_pct,
                    "reason": reason,
                    "scanned_at": now.isoformat(),
                    # Stamp the currency Booking.com was told to render in — essential for
                    # charts to label prices correctly when a property's currency is later changed.
                    "scan_currency": scan_currency,
                }
                await db.market_supply.insert_one(snapshot)
                snapshot.pop("_id", None)
                return snapshot

            # Fire all dates in parallel (bounded by the Semaphore).
            snapshots = await asyncio.gather(
                *[_scan_one_date(d) for d in scan_dates],
                return_exceptions=False,
            )

            # Auto-pricing (city mode only)
            applied = []
            if auto_pricing and snapshots:
                applied = await S._apply_auto_pricing(db, property_id, snapshots)

            # Competitive rule auto-apply (geo scans → triggers the competitive pricing rule if enabled)
            competitive_applied = 0
            if is_geo:
                comp_cfg = await db.market_robot_competitive_config.find_one(
                    {"property_id": property_id, "enabled": True, "auto_apply": True}, {"_id": 0})
                if comp_cfg:
                    try:
                        recs, _ = await S._compute_competitive_recommendations(property_id, days=days_ahead)
                        audit_batch = []
                        for r in recs:
                            if r["skipped_low_demand"]:
                                continue
                            await db.rate_overrides.update_one(
                                {"property_id": property_id, "date": r["date"], "room_type_id": r["room_type_id"]},
                                {"$set": {
                                    "property_id": property_id,
                                    "room_type_id": r["room_type_id"],
                                    "date": r["date"],
                                    "custom_rate": r["suggested_rate"],
                                    "set_by": "competitive-rule-auto",
                                    "reason": f"Auto competitive {r['reference']}→{r['suggested_rate']} (mkt £{r['market_avg']}, demand {r['demand_pct']}%)",
                                    "updated_at": datetime.now(timezone.utc).isoformat(),
                                }},
                                upsert=True,
                            )
                            audit_batch.append({
                                "id": str(uuid.uuid4()),
                                "property_id": property_id,
                                "date": r["date"],
                                "room_type_id": r["room_type_id"],
                                "room_type_name": r["room_type_name"],
                                "set_by": "auto-scan",
                                "mode": comp_cfg.get("target_mode", "below_avg"),
                                "offset_pct": comp_cfg.get("target_offset_pct", 0),
                                "reference": r["reference"],
                                "prev_rate": r["current_rate"],
                                "new_rate": r["suggested_rate"],
                                "delta_pct": r["delta_vs_current_pct"],
                                "market_avg": r["market_avg"],
                                "market_min": r["market_min"],
                                "demand_pct": r["demand_pct"],
                                "clamped": r["clamped"],
                                "applied_at": datetime.now(timezone.utc).isoformat(),
                            })
                            competitive_applied += 1
                        if audit_batch:
                            await db.competitive_rate_audit.insert_many(audit_batch)
                        if competitive_applied > 0:
                            await db.market_robot_competitive_config.update_one(
                                {"property_id": property_id},
                                {"$set": {"last_apply_at": datetime.now(timezone.utc).isoformat(),
                                          "last_apply_count": competitive_applied}},
                            )
                    except Exception as e:
                        logger.warning(f"Competitive auto-apply failed for {property_id}: {e}")

            # Update config — only for city scans (geo scans are per-request)
            if not is_geo:
                await db.market_robot_config.update_one(
                    {"property_id": property_id},
                    {"$set": {"last_scan": now.isoformat()},
                     "$inc": {"total_scans": 1}},
                    upsert=True
                )

            # Log the scan
            await db.market_robot_logs.insert_one({
                "id": scan_id, "property_id": property_id,
                "scan_type": "geo" if is_geo else "city",
                "location": scan_label,
                "city": location if not is_geo else "",
                "radius_km": radius_km,
                "dates_scanned": len(snapshots), "auto_adjustments": len(applied),
                "scanned_at": now.isoformat(),
            })

        finally:
            if is_geo:
                SCRAPE_LOCKS_GEO.pop(property_id, None)
            else:
                SCRAPE_LOCKS.pop(property_id, None)

        return {
            "scan_id": scan_id,
            "scan_type": "geo" if is_geo else "city",
            "location": scan_label,
            "city": location if not is_geo else "",
            "radius_km": radius_km,
            "dates_scanned": len(snapshots),
            "snapshots": snapshots[:10],
            "auto_adjustments": applied[:10],
            "competitive_applied": competitive_applied if is_geo else 0,
            "status": "completed",
        }

    @router.get("/revenue/market-robot/{property_id}/supply")
    async def get_supply_data(property_id: str, days: int = 30,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get latest supply snapshots with event intelligence overlay."""
        now = datetime.now(timezone.utc)
        cfg = await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0}) or {}

        # Get latest snapshot per date (no time cutoff — show ALL available data)
        pipeline = [
            {"$match": {"property_id": property_id}},
            {"$sort": {"scanned_at": -1}},
            {"$group": {"_id": "$date", "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$sort": {"date": 1}},
            {"$project": {"_id": 0}},
        ]
        snapshots = await db.market_supply.aggregate(pipeline).to_list(100)

        # Load events and create date map (filter by ALL tracked cities —
        # primary + secondary — case-insensitive to prevent cross-city leakage)
        _primary = (cfg.get("city") or "London").strip()
        _sec = cfg.get("secondary_cities") or []
        _sec = [str(c).strip() for c in (_sec if isinstance(_sec, list) else []) if c and str(c).strip()]
        _tracked = [_primary] + [s for s in _sec if s.lower() != _primary.lower()]
        _city_pattern = "^\\s*(" + "|".join(re.escape(c) for c in _tracked) + ")\\s*$"
        events_list = await db.market_events.find(
            {"property_id": property_id, "city": {"$regex": _city_pattern, "$options": "i"}}, {"_id": 0}
        ).to_list(500)
        event_map = {}
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
                impact_rank = {"mega": 4, "large": 3, "medium": 2, "small": 1}
                if ds_key not in event_map or impact_rank.get(ev.get("impact", ""), 0) > impact_rank.get(event_map[ds_key].get("impact", ""), 0):
                    event_map[ds_key] = ev
                d_iter += timedelta(days=1)

        # Merge events into supply snapshots
        for s in snapshots:
            ev = event_map.get(s.get("date", ""))
            if ev:
                s["event"] = ev.get("name", "")
                s["event_impact"] = ev.get("impact", "")
                s["event_attendance"] = ev.get("estimated_attendance", 0)
                s["hotel_demand_score"] = ev.get("hotel_demand_score", 0)
                s["visitor_origin"] = ev.get("visitor_origin", "")
                hds = int(ev.get("hotel_demand_score", 0) or 0)
                imp = ev.get("impact", "")
                s["event_boost"] = 45 if hds >= 80 or imp == "critical" else 30 if hds >= 60 or imp in ("high", "mega") else 15 if hds >= 40 or imp in ("moderate", "large") else 5 if hds >= 20 or imp in ("low", "medium", "small") else 0

        # ===== OUR HOTEL overlay: occupancy + rate per date =====
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        total_rooms = sum(int(r.get("total_rooms", 0)) for r in room_types) or 20
        base_rate_avg = sum(float(r.get("base_rate", 0) or 0) for r in room_types) / max(len(room_types), 1) if room_types else 130

        # PARALLEL fan-out — was serial, blowing past 30s on 90-day windows.
        # Now: gather all per-date queries concurrently, brings total to <3s.
        async def _our_row(snap):
            ds = snap.get("date")
            if not ds:
                return None
            bookings_count, rate_doc = await asyncio.gather(
                db.bookings.count_documents({
                    "property_id": property_id,
                    "check_in": {"$lte": ds},
                    "check_out": {"$gt": ds},
                    "status": {"$nin": ["cancelled"]},
                }),
                db.rate_overrides.find_one(
                    {"property_id": property_id, "date": ds},
                    {"_id": 0, "custom_rate": 1},
                    sort=[("updated_at", -1)],
                ),
            )
            occ = round(min(100, bookings_count / total_rooms * 100), 1)
            our_rate = round(
                float(rate_doc["custom_rate"]) if rate_doc and rate_doc.get("custom_rate") else base_rate_avg,
                2,
            )
            return (ds, occ, our_rate, bookings_count)

        our_results = await asyncio.gather(*[_our_row(s) for s in snapshots])
        our_by_date = {r[0]: r for r in our_results if r}
        our_occ_sum = 0
        our_rate_sum = 0
        for s in snapshots:
            row = our_by_date.get(s.get("date"))
            if not row:
                continue
            _, occ, our_rate, bookings_count = row
            s["our_occupancy_pct"] = occ
            s["our_avg_rate"] = our_rate
            s["our_bookings"] = bookings_count
            s["our_total_rooms"] = total_rooms
            our_occ_sum += occ
            our_rate_sum += our_rate

        # Summary stats
        if snapshots:
            avg_unavail = round(sum(s.get("unavailable_pct", 0) for s in snapshots) / len(snapshots))
            high_demand_days = sum(1 for s in snapshots if s.get("unavailable_pct", 0) >= 70)
            low_demand_days = sum(1 for s in snapshots if s.get("unavailable_pct", 0) < 30)
            event_days = sum(1 for s in snapshots if s.get("event"))
        else:
            avg_unavail = 0
            high_demand_days = 0
            low_demand_days = 0
            event_days = 0

        # Upcoming events summary for dashboard
        today_str = now.strftime("%Y-%m-%d")
        upcoming_events = sorted(
            [ev for ev in events_list if ev.get("date", "") >= today_str],
            key=lambda x: x.get("date", "")
        )[:10]

        return {
            "snapshots": snapshots,
            "scan_city": cfg.get("city", ""),
            "property_currency": (await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}).get("currency", "GBP"),
            "summary": {
                "total_dates": len(snapshots),
                "avg_unavailable_pct": avg_unavail,
                "high_demand_days": high_demand_days,
                "low_demand_days": low_demand_days,
                "event_days": event_days,
            },
            "our_summary": {
                "avg_occupancy_pct": round(our_occ_sum / max(len(snapshots), 1), 1) if snapshots else 0,
                "avg_rate": round(our_rate_sum / max(len(snapshots), 1), 2) if snapshots else 0,
                "total_rooms": total_rooms,
            } if snapshots else None,
            "upcoming_events": [{
                "name": ev.get("name", ""),
                "date": ev.get("date", ""),
                "end_date": ev.get("end_date", ""),
                "impact": ev.get("impact", ""),
                "category": ev.get("category", ""),
                "estimated_attendance": ev.get("estimated_attendance", 0),
                "hotel_demand_score": ev.get("hotel_demand_score", 0),
                "visitor_origin": ev.get("visitor_origin", ""),
                "reasoning": ev.get("reasoning", ""),
            } for ev in upcoming_events],
        }

    @router.get("/revenue/market-robot/{property_id}/logs")
    async def get_logs(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        logs = await db.market_robot_logs.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("scanned_at", -1).to_list(50)
        return {"logs": logs}

    @router.post("/revenue/market-robot/auto-bootstrap")
    async def auto_bootstrap(
        current_user: dict = Depends(require_roles("admin", "manager"))
    ):
        """Enable auto-scan for every property that currently has no config or has
        enabled=None / missing interval. Idempotent: safe to call repeatedly."""
        now_iso = datetime.now(timezone.utc).isoformat()
        properties = await db.properties.find({}, {"_id": 0}).to_list(500)
        fixed, seeded = 0, 0
        for p in properties:
            pid = p.get("id")
            if not pid or pid in ("all", "default"):
                continue
            existing = await db.market_robot_config.find_one({"property_id": pid}, {"_id": 0})
            if existing:
                patch = {}
                if existing.get("enabled") is None:
                    patch["enabled"] = True
                if existing.get("scan_interval_minutes") is None:
                    patch["scan_interval_minutes"] = 60
                if not existing.get("city"):
                    patch["city"] = p.get("city") or "London"
                if not existing.get("language"):
                    patch["language"] = "en-gb"
                if patch:
                    patch["updated_at"] = now_iso
                    patch["updated_by"] = current_user.get("name", "auto-bootstrap")
                    await db.market_robot_config.update_one({"property_id": pid}, {"$set": patch})
                    fixed += 1
            else:
                await db.market_robot_config.insert_one({
                    "property_id": pid,
                    "enabled": True,
                    "scan_interval_minutes": 60,
                    "city": p.get("city") or "London",
                    "language": "en-gb",
                    "auto_pricing": False,
                    "days_ahead": 365,
                    "total_scans": 0,
                    "created_at": now_iso,
                    "created_by": current_user.get("name", "auto-bootstrap"),
                })
                seeded += 1
        return {"fixed": fixed, "seeded": seeded, "checked_at": now_iso}

    # ==================== OCCUPANCY & PICKUP + RECENT BOOKINGS ====================

    @router.get("/revenue/market-robot/{property_id}/occupancy-pickup")
    async def get_occupancy_pickup(property_id: str, days: int = 90, pickup_window: str = "24h",
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Occupancy & Pickup chart data — base occupancy bars + booking velocity overlay.

        Was serial across days×properties → 30s+ timeout on 90d×all-branches. Now uses
        a single $facet aggregation per property and asyncio.gather across days.
        """
        now = datetime.now(timezone.utc)
        props = await db.properties.find({}, {"_id": 0}).to_list(50) if property_id == "all" else [await db.properties.find_one({"id": property_id}, {"_id": 0})]
        props = [p for p in props if p]
        prop_ids = [p.get("id", "") for p in props]

        # Total rooms — parallel count
        room_counts = await asyncio.gather(*[db.rooms.count_documents({"property_id": pid}) for pid in prop_ids])
        total_rooms = max(sum(rc or 10 for rc in room_counts), 1)

        # Pickup window in hours
        pw_hours = {"24h": 24, "3d": 72, "7d": 168}.get(pickup_window, 24)
        pickup_cutoff = (now - timedelta(hours=pw_hours)).isoformat()

        date_list = [(now + timedelta(days=i)) for i in range(days)]

        async def _row_for(d):
            ds = d.strftime("%Y-%m-%d")
            booked, pickup_rooms = await asyncio.gather(
                db.bookings.count_documents({
                    "property_id": {"$in": prop_ids} if len(prop_ids) > 1 else (prop_ids[0] if prop_ids else ""),
                    "check_in": {"$lte": ds},
                    "check_out": {"$gt": ds},
                    "status": {"$ne": "cancelled"},
                }),
                db.bookings.count_documents({
                    "property_id": {"$in": prop_ids} if len(prop_ids) > 1 else (prop_ids[0] if prop_ids else ""),
                    "check_in": {"$lte": ds},
                    "check_out": {"$gt": ds},
                    "status": {"$ne": "cancelled"},
                    "created_at": {"$gte": pickup_cutoff},
                }),
            )
            occ_pct = min(100, round((booked / total_rooms) * 100))
            pickup_pct = min(100, round((pickup_rooms / total_rooms) * 100))
            return {
                "date": ds,
                "dow": d.strftime("%a"),
                "month": d.strftime("%b"),
                "day": d.day,
                "occupancy_pct": occ_pct,
                "pickup_pct": pickup_pct,
                "booked_rooms": booked,
                "pickup_rooms": pickup_rooms,
                "total_rooms": total_rooms,
            }

        daily = await asyncio.gather(*[_row_for(d) for d in date_list])

        avg_occ = round(sum(d["occupancy_pct"] for d in daily) / max(len(daily), 1))
        avg_pickup = round(sum(d["pickup_pct"] for d in daily) / max(len(daily), 1))
        peak_occ = max(d["occupancy_pct"] for d in daily) if daily else 0
        peak_date = next((d["date"] for d in daily if d["occupancy_pct"] == peak_occ), None)

        return {
            "daily": daily,
            "pickup_window": pickup_window,
            "kpis": {
                "total_days": len(daily),
                "total_rooms": total_rooms,
                "avg_occupancy": avg_occ,
                "avg_pickup": avg_pickup,
                "peak_occupancy": peak_occ,
                "peak_date": peak_date,
            },
        }

    @router.get("/revenue/market-robot/{property_id}/recent-bookings")
    async def get_recent_bookings(property_id: str, days: int = 7,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Recent bookings summary — last N days of booking activity with ADR & Revenue."""
        now = datetime.now(timezone.utc)
        props = await db.properties.find({}, {"_id": 0}).to_list(50) if property_id == "all" else [await db.properties.find_one({"id": property_id}, {"_id": 0})]
        props = [p for p in props if p]
        prop_ids = [p.get("id", "") for p in props]

        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0

        daily = []
        total_bookings = 0
        total_nights = 0
        total_revenue = 0

        for i in range(days):
            d = now - timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")

            # Get bookings that were created on this date OR have check-in on this date
            day_bookings = []
            for pid in prop_ids:
                bks = await db.bookings.find({
                    "property_id": pid,
                    "check_in": {"$lte": ds},
                    "check_out": {"$gt": ds},
                    "status": {"$ne": "cancelled"}
                }, {"_id": 0}).to_list(50)
                day_bookings.extend(bks)

            booking_count = len(day_bookings)
            room_nights = sum(max(1, int(b.get("nights", 1) or 1)) for b in day_bookings)
            day_revenue = sum(float(b.get("total_price", 0) or 0) for b in day_bookings)

            # If no revenue data, estimate from rate overrides or base rate
            if day_revenue == 0 and booking_count > 0:
                override = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": ds}, {"_id": 0}
                )
                rate = float(override.get("custom_rate", base_rate)) if override else base_rate
                day_revenue = round(rate * booking_count, 2)

            adr = round(day_revenue / max(booking_count, 1), 2)

            daily.append({
                "date": ds,
                "dow": d.strftime("%a"),
                "day": d.day,
                "month": d.strftime("%b"),
                "bookings": booking_count,
                "room_nights": room_nights,
                "adr": adr,
                "revenue": round(day_revenue, 2),
            })

            total_bookings += booking_count
            total_nights += room_nights
            total_revenue += day_revenue

        return {
            "daily": daily,
            "summary": {
                "total_bookings": total_bookings,
                "total_room_nights": total_nights,
                "total_revenue": round(total_revenue, 2),
                "avg_adr": round(total_revenue / max(total_bookings, 1), 2),
                "days": days,
            },
        }

    @router.get("/revenue/market-robot/{property_id}/demand-dashboard")
    async def get_demand_dashboard(property_id: str, days: int = 365,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Full-year market demand dashboard with occupancy, rates, events, and AI status."""
        now = datetime.now(timezone.utc)
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0

        # Get properties and total rooms
        props = await db.properties.find({}, {"_id": 0}).to_list(50) if property_id == "all" else [await db.properties.find_one({"id": property_id}, {"_id": 0})]
        props = [p for p in props if p]
        total_rooms = 0
        for p in props:
            total_rooms += await db.rooms.count_documents({"property_id": p.get("id", "")}) or 10
        total_rooms = max(total_rooms, 1)

        # Get all supply data (no time cutoff — show all)
        supply_docs = await db.market_supply.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("scanned_at", -1).to_list(2000)
        supply_map = {}
        for s in supply_docs:
            if s["date"] not in supply_map:
                supply_map[s["date"]] = s

        # Get all rate overrides
        overrides = await db.rate_overrides.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(1000)
        override_map = {}
        for ov in overrides:
            if ov["date"] not in override_map:
                override_map[ov["date"]] = ov

        # Get events (filter by ALL tracked cities — primary + secondary —
        # case-insensitive). For property_id="all" we keep no city filter.
        if property_id != "all":
            _cfg = await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
            _city = (_cfg.get("city") or "London").strip()
            _sec = _cfg.get("secondary_cities") or []
            _sec = [str(c).strip() for c in (_sec if isinstance(_sec, list) else []) if c and str(c).strip()]
            _tracked = [_city] + [s for s in _sec if s.lower() != _city.lower()]
            _city_pat = "^\\s*(" + "|".join(re.escape(c) for c in _tracked) + ")\\s*$"
            events = await db.market_events.find(
                {"property_id": property_id, "city": {"$regex": _city_pat, "$options": "i"}}, {"_id": 0}
            ).to_list(500)
        else:
            events = await db.market_events.find(
                {"property_id": property_id}, {"_id": 0}
            ).to_list(500)
        event_map = {}
        for ev in events:
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
                impact_rank = {"mega": 4, "large": 3, "medium": 2, "small": 1}
                if ds_key not in event_map or impact_rank.get(ev.get("impact", ""), 0) > impact_rank.get(event_map[ds_key].get("impact", ""), 0):
                    event_map[ds_key] = ev
                d_iter += timedelta(days=1)

        # Get strategy for floor rate
        strategy = await db.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0}) or {}
        price_floors = strategy.get("price_floors", {})

        # Get historical data for floor rates
        hist_floor_map = {}
        for month_str, floor_data in price_floors.items():
            try:
                hist_floor_map[int(month_str)] = float(floor_data.get("min_price", 0))
            except (ValueError, TypeError):
                pass

        # Get competitor price data
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

        # Build day-by-day data
        daily_data = []
        for i in range(days):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")

            # Occupancy
            booked = 0
            for p in props:
                booked += await db.bookings.count_documents({
                    "property_id": p.get("id", ""), "check_in": {"$lte": ds},
                    "check_out": {"$gt": ds}, "status": {"$ne": "cancelled"}
                })
            occ = min(100, round((booked / total_rooms) * 100))

            # Supply / demand
            supply = supply_map.get(ds, {})
            market_unavail = supply.get("unavailable_pct") if supply else None

            # Our rates
            ov = override_map.get(ds)
            ai_rate = float(ov.get("custom_rate", base_rate)) if ov else None
            sell_rate = ai_rate if ai_rate else base_rate
            set_by = ov.get("set_by", "") if ov else ""

            # AI status
            ai_status = "ai" if set_by in ("ai-dynamic-pricing", "auto-scanner") else "event" if set_by == "event-intelligence" else "manual" if set_by == "market-robot" else "base"

            # Floor rate
            floor_rate = hist_floor_map.get(d.month, round(base_rate * 0.5, 2))

            # Min rate (guardrail)
            min_rate = round(base_rate * 0.5, 2)

            # Event
            event = event_map.get(ds)

            # Target sell rate (what AI recommends)
            target_rate = ai_rate if ai_rate else base_rate

            # Competitor avg for this date
            comp_prices = comp_price_map.get(ds, [])
            comp_avg = round(sum(comp_prices) / len(comp_prices), 2) if comp_prices else None

            # Position: above or below market
            position = None
            position_pct = 0
            if comp_avg and sell_rate:
                position_pct = round(((sell_rate - comp_avg) / comp_avg) * 100, 1)
                position = "above" if position_pct > 2 else "below" if position_pct < -2 else "aligned"

            entry = {
                "date": ds,
                "day": d.day,
                "dow": d.strftime("%a"),
                "month": d.strftime("%b"),
                "days_ahead": i,
                "occupancy": occ,
                "market_unavail": market_unavail,
                "demand_level": "high" if (market_unavail or 0) >= 70 else "moderate" if (market_unavail or 0) >= 40 else "low",
                "base_rate": base_rate,
                "ai_rate": ai_rate,
                "sell_rate": sell_rate,
                "min_rate": min_rate,
                "floor_rate": floor_rate,
                "target_rate": target_rate,
                "comp_avg": comp_avg,
                "position": position,
                "position_pct": position_pct,
                "ai_status": ai_status,
                "set_by": set_by,
                "event": event.get("name") if event else None,
                "event_impact": event.get("impact") if event else None,
                "event_attendance": event.get("estimated_attendance", 0) if event else None,
            }
            daily_data.append(entry)

        # Summary KPIs
        avg_occ = round(sum(d["occupancy"] for d in daily_data) / max(len(daily_data), 1))
        avg_rate = round(sum(d["sell_rate"] for d in daily_data) / max(len(daily_data), 1), 2)
        high_demand_days = sum(1 for d in daily_data if d["demand_level"] == "high")
        low_demand_days = sum(1 for d in daily_data if d["demand_level"] == "low")
        event_days = sum(1 for d in daily_data if d["event"])
        ai_managed_days = sum(1 for d in daily_data if d["ai_status"] in ("ai", "event"))
        days_with_comp = [d for d in daily_data if d["comp_avg"]]
        avg_comp = round(sum(d["comp_avg"] for d in days_with_comp) / max(len(days_with_comp), 1), 2) if days_with_comp else None
        above_market = sum(1 for d in daily_data if d["position"] == "above")
        below_market = sum(1 for d in daily_data if d["position"] == "below")
        aligned_market = sum(1 for d in daily_data if d["position"] == "aligned")
        avg_position_pct = round(sum(d["position_pct"] for d in days_with_comp) / max(len(days_with_comp), 1), 1) if days_with_comp else 0

        # Market occupancy (from supply data = unavailability ≈ market occupancy)
        days_with_market = [d for d in daily_data if d["market_unavail"] is not None]
        market_avg_occ = round(sum(d["market_unavail"] for d in days_with_market) / max(len(days_with_market), 1)) if days_with_market else None

        # Market ADR estimate (from supply data — avg price adjustment applied)
        market_adr = None
        if days_with_market:
            market_adr = round(sum(
                base_rate * (1 + (supply_map.get(d["date"], {}).get("price_adjustment_pct", 0) or 0) / 100)
                for d in days_with_market
            ) / len(days_with_market), 2)

        # Competitor ADR and occupancy estimate
        comp_adr = avg_comp
        # Competitor occupancy estimated from their pricing vs base
        comp_occ = None
        if days_with_comp:
            # Higher priced = likely higher occupancy
            comp_occ = min(100, round(sum(
                min(100, max(10, 50 + (d["comp_avg"] - base_rate) / base_rate * 80))
                for d in days_with_comp
            ) / len(days_with_comp)))

        return {
            "daily_data": daily_data,
            "kpis": {
                "total_days": len(daily_data),
                "base_rate": base_rate,
                # Our hotel
                "our_adr": avg_rate,
                "our_occupancy": avg_occ,
                # Market
                "market_adr": market_adr,
                "market_occupancy": market_avg_occ,
                # Competitors
                "comp_adr": comp_adr,
                "comp_occupancy": comp_occ,
                # Positioning
                "avg_position_pct": avg_position_pct,
                "above_market_days": above_market,
                "below_market_days": below_market,
                "aligned_days": aligned_market,
                # Other
                "high_demand_days": high_demand_days,
                "low_demand_days": low_demand_days,
                "event_days": event_days,
                "ai_managed_days": ai_managed_days,
                "ai_managed_pct": round((ai_managed_days / max(len(daily_data), 1)) * 100),
                "competitors_tracked": len(competitors),
                "market_data_days": len(days_with_market),
            },
            "property_currency": (await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}).get("currency", "GBP"),
            "scan_city": (await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0, "city": 1}) or {}).get("city", ""),
        }

    @router.get("/revenue/market-robot/{property_id}/adjustments")
    async def get_adjustments(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get all rate overrides set by market robot."""
        overrides = await db.rate_overrides.find(
            {"property_id": property_id, "set_by": "market-robot"},
            {"_id": 0}
        ).sort("date", 1).to_list(200)
        return {"adjustments": overrides}

    # ==================== PERFORMANCE REPORT ====================

    @router.get("/revenue/market-robot/{property_id}/action-feed")
    async def action_feed(property_id: str, since: Optional[str] = None, limit: int = 30,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Chronological feed of pricing & market events for the revenue manager.

        Aggregates events from 4 sources so a single panel answers "what happened
        recently?" without switching tabs:
          • auto_pricing_logs     — Market Robot's rate adjustments (e.g. "+8.5% for 15 Mar")
          • market_competitors    — Competitor price snapshots (detects >5% day-over-day change)
          • rate_overrides        — Manual rate edits in the last 24h (authored by someone)
          • smart_scanner_runs    — Significant scan outcomes (unavailable% jumps, scraper errors)

        Query:
          since?  ISO timestamp — only events strictly newer than this (for "unread" tracking)
          limit   default 30, max 100

        Returns: { events: [{ id, type, severity, timestamp, title, detail, meta }], latest_ts }
        """
        if property_id == "all":
            return {"events": [], "latest_ts": None, "unread": 0}

        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except Exception:
                since_dt = None
        floor_dt = since_dt or (now - timedelta(days=2))
        floor_iso = floor_dt.isoformat()

        events = []

        # 1) Auto-pricing log entries
        async for log in db.auto_pricing_logs.find(
            {"property_id": property_id, "timestamp": {"$gte": floor_iso}},
            {"_id": 0},
        ).sort("timestamp", -1).limit(limit):
            ts = log.get("timestamp", "")
            change_pct = log.get("change_pct") or log.get("adjustment_pct") or 0
            direction = "up" if change_pct > 0 else ("down" if change_pct < 0 else "flat")
            events.append({
                "id": f"ap:{log.get('id', ts)}",
                "type": "auto_pricing",
                "severity": "info" if abs(change_pct) < 5 else ("warn" if abs(change_pct) < 12 else "alert"),
                "timestamp": ts,
                "title": f"Auto-pricing {direction} {abs(change_pct):.1f}% on {log.get('date','?')}",
                "detail": log.get("reason") or log.get("trigger") or "",
                "meta": {
                    "date": log.get("date"),
                    "old_rate": log.get("old_rate"),
                    "new_rate": log.get("new_rate"),
                    "change_pct": change_pct,
                },
            })

        # 2) Competitor price change events (detect deltas since last scan)
        async for comp in db.market_competitors.find(
            {"property_id": property_id, "last_scraped": {"$gte": floor_iso}},
            {"_id": 0, "name": 1, "prices": 1, "last_scraped": 1, "id": 1},
        ).sort("last_scraped", -1).limit(10):
            prices = [p.get("lowest_price") for p in (comp.get("prices") or []) if p.get("lowest_price")]
            if len(prices) < 2:
                continue
            latest = prices[0]
            prev   = next((p for p in prices[1:6] if p and p != latest), None)
            if not prev:
                continue
            delta_pct = ((latest - prev) / prev) * 100
            if abs(delta_pct) < 5:
                continue
            direction = "dropped" if delta_pct < 0 else "raised"
            events.append({
                "id": f"cp:{comp.get('id','?')}:{comp.get('last_scraped','')}",
                "type": "competitor_move",
                "severity": "warn" if abs(delta_pct) >= 10 else "info",
                "timestamp": comp.get("last_scraped", ""),
                "title": f"{comp.get('name','Competitor')} {direction} {abs(delta_pct):.1f}%",
                "detail": f"{prev:.0f} → {latest:.0f} in the latest scan",
                "meta": {"competitor_id": comp.get("id"), "prev": prev, "latest": latest, "delta_pct": delta_pct},
            })

        # 3) Manual rate overrides within the window
        async for rov in db.rate_overrides.find(
            {"property_id": property_id, "updated_at": {"$gte": floor_iso}},
            {"_id": 0},
        ).sort("updated_at", -1).limit(10):
            # Skip Market Robot-authored entries (they're already in auto_pricing_logs)
            if (rov.get("source") or "").lower() in ("auto", "market-robot", "auto-pricer"):
                continue
            events.append({
                "id": f"ov:{rov.get('date','?')}:{rov.get('updated_at','')}",
                "type": "manual_override",
                "severity": "info",
                "timestamp": rov.get("updated_at", ""),
                "title": f"Manual rate override for {rov.get('date','?')}",
                "detail": f"New rate {rov.get('override_rate', '?')}. Author: {rov.get('updated_by','?')}",
                "meta": rov,
            })

        # 4) Scanner errors (from smart_scanner_runs)
        async for run in db.smart_scanner_runs.find(
            {"property_id": property_id, "started_at": {"$gte": floor_iso}, "status": "error"},
            {"_id": 0},
        ).sort("started_at", -1).limit(5):
            events.append({
                "id": f"sc:{run.get('id','?')}:{run.get('started_at','')}",
                "type": "scanner_error",
                "severity": "alert",
                "timestamp": run.get("started_at", ""),
                "title": f"Scanner error: {run.get('scan_type','?')}",
                "detail": (run.get("error_message") or "")[:200],
                "meta": {"scan_type": run.get("scan_type"), "city": run.get("city")},
            })

        # Sort newest-first and trim
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        events = events[:limit]
        latest_ts = events[0]["timestamp"] if events else None
        return {"events": events, "latest_ts": latest_ts, "unread": len(events)}

    S._do_scan = _do_scan
    S.action_feed = action_feed
    S.auto_bootstrap = auto_bootstrap
    S.get_adjustments = get_adjustments
    S.get_demand_dashboard = get_demand_dashboard
    S.get_logs = get_logs
    S.get_occupancy_pickup = get_occupancy_pickup
    S.get_recent_bookings = get_recent_bookings
    S.get_supply_data = get_supply_data
