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

    @router.get("/revenue/market-robot/{property_id}/scan-geo-status")
    async def get_geo_scan_status(property_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Polling endpoint for the most recent geo scan on this property.
        Returns {status: 'idle'|'queued'|'running'|'done'|'error', result?, error?, scan_id, started_at, finished_at}."""
        doc = await db.market_robot_scan_status.find_one(
            {"property_id": property_id, "kind": "geo"}, {"_id": 0}
        )
        return doc or {"property_id": property_id, "kind": "geo", "status": "idle"}

    @router.get("/revenue/market-robot/{property_id}/geo-supply")
    async def get_geo_supply_data(property_id: str, days: int = 30,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Latest geo-radius snapshots (neighborhood scans).
        When property_id='all', aggregates across ALL properties (averages per date)."""
        now = datetime.now(timezone.utc)
        match = {"scan_type": "geo"} if property_id == "all" else {"property_id": property_id, "scan_type": "geo"}
        pipeline = [
            {"$match": match},
            {"$sort": {"scanned_at": -1}},
            {"$group": {"_id": {"pid": "$property_id", "date": "$date"}, "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$sort": {"date": 1}},
            {"$project": {"_id": 0}},
        ]
        raw = await db.market_supply.aggregate(pipeline).to_list(5000)
        today_str = now.strftime("%Y-%m-%d")
        end_str = (now + timedelta(days=days)).strftime("%Y-%m-%d")
        raw = [s for s in raw if today_str <= s.get("date", "") <= end_str]

        if property_id == "all":
            # Aggregate across properties per date
            by_date = {}
            for s in raw:
                d = s.get("date")
                by_date.setdefault(d, []).append(s)
            snaps = []
            for d in sorted(by_date.keys()):
                rows = by_date[d]
                ap = [r.get("avg_price", 0) for r in rows if r.get("avg_price", 0) > 0]
                mn = [r.get("min_price", 0) for r in rows if r.get("min_price", 0) > 0]
                mx = [r.get("max_price", 0) for r in rows if r.get("max_price", 0) > 0]
                un = [r.get("unavailable_pct", 0) for r in rows]
                tp = [r.get("total_properties", 0) for r in rows if r.get("total_properties", 0) > 0]
                snaps.append({
                    "date": d,
                    "property_id": "all",
                    "scan_type": "geo",
                    "location": f"All {len(rows)} branches",
                    "radius_km": rows[0].get("radius_km", 3.2),
                    "total_properties": round(sum(tp) / len(tp)) if tp else 0,
                    "total_source": "aggregated",
                    "unavailable_pct": round(sum(un) / len(un), 1) if un else 0,
                    "available_pct": round(100 - (sum(un) / len(un)), 1) if un else 100,
                    "avg_price": round(sum(ap) / len(ap), 2) if ap else 0,
                    "min_price": round(min(mn), 2) if mn else 0,
                    "max_price": round(max(mx), 2) if mx else 0,
                    "median_price": round(sum(ap) / len(ap), 2) if ap else 0,
                    "scraped": True,
                    "method": "aggregated",
                    "scanned_at": rows[0].get("scanned_at", ""),
                    "scan_id": rows[0].get("scan_id", ""),
                })
        else:
            snaps = raw

        # Aggregate summary
        total_scans = len({s.get("scan_id", "") for s in snaps}) if snaps else 0
        avg_unavail = round(sum(s.get("unavailable_pct", 0) for s in snaps) / len(snaps), 1) if snaps else 0
        prices = [s.get("avg_price", 0) for s in snaps if s.get("avg_price", 0) > 0]
        avg_price = round(sum(prices) / len(prices), 2) if prices else 0
        min_prices = [s.get("min_price", 0) for s in snaps if s.get("min_price", 0) > 0]
        max_prices = [s.get("max_price", 0) for s in snaps if s.get("max_price", 0) > 0]
        mkt_min = round(min(min_prices), 2) if min_prices else 0
        mkt_max = round(max(max_prices), 2) if max_prices else 0
        latest = snaps[-1] if snaps else {}

        # Load geo auto-scan config (only for real properties)
        geo_cfg = {} if property_id == "all" else (
            await db.market_robot_geo_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        )

        # ===== OUR HOTEL — occupancy + price for same dates =====
        # APPLES-TO-APPLES: Our chart line MUST use the same OTA surface as the market average.
        # Booking.com `property.booking_data.daily_prices` is per-date scrape of our own listing —
        # exactly what guests see. We prefer it over `rate_overrides` (which reflect internal
        # price plans) so "Biz vs Pazar" compares the price a guest would pay on Booking.com
        # vs the market median on Booking.com. Fallback to rate_overrides → base_rate_avg
        # only if the Booking.com scrape doesn't cover that date yet.
        our_data = []
        booking_by_date = {}
        prop_full = {}
        if property_id != "all":
            prop_full = await db.properties.find_one(
                {"id": property_id},
                {"_id": 0, "booking_data": 1, "currency": 1},
            ) or {}
            bd = prop_full.get("booking_data") or {}
            for p in (bd.get("daily_prices") or bd.get("prices") or []):
                d = p.get("date")
                lp = p.get("lowest_price")
                if d and lp and p.get("scraped"):
                    booking_by_date[d] = float(lp)

        if property_id != "all":
            room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
            total_rooms = sum(int(r.get("total_rooms", 0)) for r in room_types) or 20
            base_rate_avg = sum(float(r.get("base_rate", 0) or 0) for r in room_types) / max(len(room_types), 1) if room_types else 130

            # PARALLEL fan-out: 30 snapshots × (bookings count + rate override
            # lookup) was running serially → 30-60s alone, blowing past the
            # 60s ingress timeout. Wrapping each per-date computation in a
            # task and gathering them brings this whole stage to <5s.
            async def _build_our_row(snap):
                target_date = snap.get("date")
                if not target_date:
                    return None
                bookings_count, rate_doc = await asyncio.gather(
                    db.bookings.count_documents({
                        "property_id": property_id,
                        "check_in": {"$lte": target_date},
                        "check_out": {"$gt": target_date},
                        "status": {"$nin": ["cancelled"]},
                    }),
                    db.rate_overrides.find_one(
                        {"property_id": property_id, "date": target_date},
                        {"_id": 0, "custom_rate": 1},
                        sort=[("updated_at", -1)],
                    ),
                )
                occ = round(min(100, bookings_count / total_rooms * 100), 1)
                bk_price = booking_by_date.get(target_date)
                if bk_price and bk_price > 0:
                    our_rate = round(bk_price, 2)
                    our_rate_source = "booking_live"
                else:
                    our_rate = round(float(rate_doc["custom_rate"]) if rate_doc and rate_doc.get("custom_rate") else base_rate_avg, 2)
                    our_rate_source = "override" if rate_doc else "base_rate"
                return {
                    "date": target_date,
                    "our_occupancy_pct": occ,
                    "our_bookings": bookings_count,
                    "our_total_rooms": total_rooms,
                    "our_avg_rate": our_rate,
                    "our_rate_source": our_rate_source,
                }

            results = await asyncio.gather(*[_build_our_row(s) for s in snaps])
            our_data = [r for r in results if r]

        # Merge our_data into snapshots by date for the chart overlay
        our_by_date = {d["date"]: d for d in our_data}
        booking_cover = sum(1 for d in our_data if d.get("our_rate_source") == "booking_live")
        for s in snaps:
            d = our_by_date.get(s.get("date"))
            if d:
                s["our_occupancy_pct"] = d["our_occupancy_pct"]
                s["our_avg_rate"] = d["our_avg_rate"]
                s["our_rate_source"] = d["our_rate_source"]
                s["our_bookings"] = d["our_bookings"]
                s["our_total_rooms"] = d["our_total_rooms"]

        # Our summary
        our_summary = None
        if our_data:
            our_summary = {
                "avg_occupancy_pct": round(sum(x["our_occupancy_pct"] for x in our_data) / len(our_data), 1),
                "avg_rate": round(sum(x["our_avg_rate"] for x in our_data) / len(our_data), 2),
                "total_rooms": our_data[0]["our_total_rooms"],
                "booking_cover_days": booking_cover,
                "booking_cover_pct": round((booking_cover / len(our_data)) * 100, 1) if our_data else 0,
            }

        # ===== COMPETITOR SERIES =====
        # Build per-competitor date→price map so the frontend can draw individual
        # lines on the Biz-vs-Pazar chart (not just the aggregated market average).
        # Each competitor row's `prices` array is a list of scraped per-date snapshots —
        # we expose the most recent scraped price per date.
        competitor_series = []
        our_hotel_name = ""
        if property_id != "all":
            prop_name = (await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1}) or {}).get("name", "")
            our_hotel_name = prop_name
            comp_docs = await db.market_competitors.find(
                {"property_id": property_id},
                {"_id": 0, "id": 1, "name": 1, "booking_hotel_id": 1, "prices": 1, "last_scraped": 1, "booking_url": 1, "last_validation": 1},
            ).to_list(20)
            for c in comp_docs:
                price_map = {}
                raw_prices = c.get("prices") or []
                for p in raw_prices:
                    if p.get("scraped") and p.get("date") and p.get("lowest_price"):
                        price_map[p["date"]] = round(float(p["lowest_price"]), 2)
                prices_list = [price_map[k] for k in sorted(price_map)]
                attempted = len(raw_prices)
                hit_rate = round((len(price_map) / attempted) * 100, 0) if attempted else 0
                competitor_series.append({
                    "id": c.get("id"),
                    "name": c.get("name", "Competitor"),
                    "booking_hotel_id": c.get("booking_hotel_id"),
                    "prices_by_date": price_map,
                    "avg_price": round(sum(prices_list) / len(prices_list), 2) if prices_list else None,
                    "min_price": round(min(prices_list), 2) if prices_list else None,
                    "max_price": round(max(prices_list), 2) if prices_list else None,
                    "days_covered": len(price_map),
                    "attempted_days": attempted,
                    "hit_rate": hit_rate,
                    "last_scraped": c.get("last_scraped"),
                    "validation_ok": (c.get("last_validation") or {}).get("ok"),
                })
            # Sort by name for stable colour assignment across polls
            competitor_series.sort(key=lambda x: (x["name"] or "").lower())

        # The scan_currency stamp on each snapshot is the source of truth for chart labels —
        # property.currency can drift, but the currency Booking.com rendered prices in is
        # baked into each row. Fall back to property.currency only if the snapshot predates
        # this field (older rows from before the 2026-04 scraper rewrite).
        display_currency = "GBP"
        if property_id != "all":
            prop_cur = (await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}).get("currency", "GBP")
            display_currency = prop_cur
        if snaps:
            latest_with_cur = next((s.get("scan_currency") for s in reversed(snaps) if s.get("scan_currency")), None)
            if latest_with_cur:
                display_currency = latest_with_cur

        # Calculate data freshness safely
        data_freshness_sec = None
        if latest.get("scanned_at"):
            try:
                data_freshness_sec = int(
                    (now - datetime.fromisoformat(latest["scanned_at"].replace("Z", "+00:00"))).total_seconds()
                )
            except Exception:
                data_freshness_sec = None

        return {
            "property_id": property_id,
            "snapshots": snaps,
            "property_currency": display_currency,
            "summary": {
                "total_snapshots": len(snaps),
                "total_scans": total_scans,
                "avg_unavailable_pct": avg_unavail,
                "avg_price": avg_price,
                "min_price": mkt_min,
                "max_price": mkt_max,
                "last_location": latest.get("location", ""),
                "last_radius_km": latest.get("radius_km", 0),
                "last_scan": latest.get("scanned_at", ""),
                "scan_currency": display_currency,
                # Surface WHEN our overlay was last refreshed so the UI can show "Last updated Xm ago"
                "our_source_refreshed_at": (prop_full.get("booking_data") or {}).get("snapshot_at"),
                "data_freshness_seconds": data_freshness_sec,
            },
            "our_summary": our_summary,
            "our_hotel_name": our_hotel_name,
            "competitor_series": competitor_series,
            "auto_config": geo_cfg,
        }

    @router.get("/revenue/market-robot/{property_id}/geo-config")
    async def get_geo_config(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.market_robot_geo_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "property_id": property_id, "enabled": False, "location": "", "radius_km": 3.2,
            "days_ahead": 30, "scan_interval_minutes": 120,
            "latitude": None, "longitude": None, "last_scan": None, "total_scans": 0,
        }
        return cfg

    @router.put("/revenue/market-robot/{property_id}/geo-config")
    async def update_geo_config(property_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        payload = {
            "enabled": bool(data.get("enabled", False)),
            "location": data.get("location", "").strip(),
            "radius_km": float(data.get("radius_km", 3.2)),
            "days_ahead": min(int(data.get("days_ahead", 30)), 90),
            "scan_interval_minutes": max(int(data.get("scan_interval_minutes", 120)), 30),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.market_robot_geo_config.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, **payload}},
            upsert=True,
        )
        cfg = await db.market_robot_geo_config.find_one({"property_id": property_id}, {"_id": 0})
        return cfg

    # ==================== COMPETITIVE PRICING RULE ====================

    @router.get("/revenue/market-robot/{property_id}/competitive-config")
    async def get_competitive_config(property_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.market_robot_competitive_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "property_id": property_id,
            "enabled": False,
            "target_mode": "below_avg",      # below_avg | match_avg | below_min | match_min | above_min
            "target_offset_pct": -3.0,       # e.g. -3 = 3% below reference
            "min_rate_pct": 60,              # floor: % of base rate
            "max_rate_pct": 250,             # ceiling: % of base rate
            "auto_apply": False,             # if true, auto-writes to rate_overrides on every scan
            "only_apply_if_demand_gte": 60,  # only apply when unavail% >= this threshold
            "email_recipients": [],          # weekly summary recipients
            "weekly_email_enabled": False,   # auto-send Mondays 09:00
            "last_weekly_email_at": None,
            "last_apply_at": None,
            "last_apply_count": 0,
        }
        return cfg

    @router.put("/revenue/market-robot/{property_id}/competitive-config")
    async def update_competitive_config(property_id: str, data: Dict,
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed_modes = {"below_avg", "match_avg", "below_min", "match_min", "above_min"}
        mode = data.get("target_mode", "below_avg")
        if mode not in allowed_modes:
            mode = "below_avg"
        payload = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", False)),
            "target_mode": mode,
            "target_offset_pct": float(data.get("target_offset_pct", -3.0)),
            "min_rate_pct": max(10, min(100, int(data.get("min_rate_pct", 60)))),
            "max_rate_pct": max(100, min(500, int(data.get("max_rate_pct", 250)))),
            "auto_apply": bool(data.get("auto_apply", False)),
            "only_apply_if_demand_gte": max(0, min(100, int(data.get("only_apply_if_demand_gte", 60)))),
            "email_recipients": [str(e).strip() for e in (data.get("email_recipients") or []) if str(e).strip()],
            "weekly_email_enabled": bool(data.get("weekly_email_enabled", False)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.market_robot_competitive_config.update_one(
            {"property_id": property_id},
            {"$set": payload},
            upsert=True,
        )
        return await db.market_robot_competitive_config.find_one({"property_id": property_id}, {"_id": 0})

    async def _compute_competitive_recommendations(property_id: str, days: int = 30):
        """For each upcoming date with geo data, compute a recommended rate per room type
        based on the competitive pricing rule + guardrails.
        """
        cfg = await db.market_robot_competitive_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        mode = cfg.get("target_mode", "below_avg")
        offset = float(cfg.get("target_offset_pct", -3.0))
        min_pct = int(cfg.get("min_rate_pct", 60))
        max_pct = int(cfg.get("max_rate_pct", 250))
        demand_gate = int(cfg.get("only_apply_if_demand_gte", 0))

        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        end_str = (now + timedelta(days=days)).strftime("%Y-%m-%d")

        pipeline = [
            {"$match": {"property_id": property_id, "scan_type": "geo"}},
            {"$sort": {"scanned_at": -1}},
            {"$group": {"_id": "$date", "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$sort": {"date": 1}},
            {"$project": {"_id": 0}},
        ]
        snaps = await db.market_supply.aggregate(pipeline).to_list(500)
        snaps = [s for s in snaps if today_str <= s.get("date", "") <= end_str]

        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not room_types:
            room_types = [{"id": "default", "name": "Standard", "base_rate": 130}]

        recs = []
        for snap in snaps:
            avg = snap.get("avg_price", 0) or 0
            mn = snap.get("min_price", 0) or 0
            unavail = snap.get("unavailable_pct", 0) or 0
            if avg <= 0:
                continue

            # Pick reference price by mode
            if mode in ("below_avg", "match_avg"):
                ref = avg
            elif mode in ("below_min", "match_min", "above_min"):
                ref = mn if mn > 0 else avg
            else:
                ref = avg

            # Apply offset (positive or negative %)
            suggested = ref * (1 + offset / 100.0)

            gated = unavail < demand_gate

            for rt in room_types:
                base = float(rt.get("base_rate", 130) or 130)
                floor_rate = round(base * min_pct / 100, 2)
                ceil_rate = round(base * max_pct / 100, 2)
                rec_rate = round(max(floor_rate, min(ceil_rate, suggested)), 2)
                current = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": snap["date"], "room_type_id": rt.get("id", "")},
                    {"_id": 0, "custom_rate": 1},
                )
                current_rate = (current or {}).get("custom_rate", base)
                delta_pct = ((rec_rate - current_rate) / current_rate * 100) if current_rate else 0
                recs.append({
                    "date": snap["date"],
                    "room_type_id": rt.get("id", ""),
                    "room_type_name": rt.get("name", ""),
                    "base_rate": base,
                    "current_rate": round(current_rate, 2),
                    "market_avg": avg,
                    "market_min": mn,
                    "reference": round(ref, 2),
                    "suggested_rate": rec_rate,
                    "delta_vs_current_pct": round(delta_pct, 1),
                    "demand_pct": unavail,
                    "skipped_low_demand": gated,
                    "clamped": rec_rate != round(suggested, 2),
                })
        return recs, cfg

    @router.get("/revenue/market-robot/{property_id}/competitive-recommendations")
    async def get_competitive_recommendations(property_id: str, days: int = 30,
                                              current_user: dict = Depends(require_roles("admin", "manager"))):
        recs, cfg = await _compute_competitive_recommendations(property_id, days)
        return {"property_id": property_id, "config": cfg, "recommendations": recs, "count": len(recs)}

    @router.post("/revenue/market-robot/{property_id}/apply-competitive-pricing")
    async def apply_competitive_pricing(property_id: str, data: Dict = {},
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Apply (write rate_overrides) competitive recommendations.
        Body (optional): { dates: ["2026-05-01", ...], room_type_ids: ["std",...] }
        If omitted, applies ALL currently-valid recommendations (skipping low-demand ones).
        """
        days = int(data.get("days", 30))
        filter_dates = set(data.get("dates") or [])
        filter_rooms = set(data.get("room_type_ids") or [])
        recs, _cfg = await _compute_competitive_recommendations(property_id, days)

        applied = []
        audit_batch = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for r in recs:
            if r["skipped_low_demand"]:
                continue
            if filter_dates and r["date"] not in filter_dates:
                continue
            if filter_rooms and r["room_type_id"] not in filter_rooms:
                continue
            await db.rate_overrides.update_one(
                {"property_id": property_id, "date": r["date"], "room_type_id": r["room_type_id"]},
                {"$set": {
                    "property_id": property_id,
                    "room_type_id": r["room_type_id"],
                    "date": r["date"],
                    "custom_rate": r["suggested_rate"],
                    "set_by": "competitive-rule",
                    "reason": f"Competitive {r['reference']}→{r['suggested_rate']} (market avg £{r['market_avg']}, demand {r['demand_pct']}%)",
                    "updated_at": now_iso,
                }},
                upsert=True,
            )
            applied.append({"date": r["date"], "room": r["room_type_name"], "rate": r["suggested_rate"]})
            audit_batch.append({
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "date": r["date"],
                "room_type_id": r["room_type_id"],
                "room_type_name": r["room_type_name"],
                "set_by": "manual-apply",
                "mode": _cfg.get("target_mode", "below_avg"),
                "offset_pct": _cfg.get("target_offset_pct", 0),
                "reference": r["reference"],
                "prev_rate": r["current_rate"],
                "new_rate": r["suggested_rate"],
                "delta_pct": r["delta_vs_current_pct"],
                "market_avg": r["market_avg"],
                "market_min": r["market_min"],
                "demand_pct": r["demand_pct"],
                "clamped": r["clamped"],
                "applied_at": now_iso,
            })
        if audit_batch:
            await db.competitive_rate_audit.insert_many(audit_batch)

        await db.market_robot_competitive_config.update_one(
            {"property_id": property_id},
            {"$set": {"last_apply_at": now_iso, "last_apply_count": len(applied)}},
            upsert=True,
        )
        return {"applied": len(applied), "items": applied[:50]}

    @router.get("/revenue/market-robot/{property_id}/competitive-audit")
    async def get_competitive_audit(property_id: str, days: int = 14,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return the last N days of competitive-rule applications (auto + manual)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = db.competitive_rate_audit.find(
            {"property_id": property_id, "applied_at": {"$gte": cutoff}},
            {"_id": 0},
        ).sort("applied_at", -1).limit(500)
        entries = await cursor.to_list(500)
        total_count = await db.competitive_rate_audit.count_documents({"property_id": property_id})
        return {"property_id": property_id, "entries": entries, "total_ever": total_count}

    # ==================== WEEKLY EMAIL SUMMARY ====================

    async def _build_weekly_summary(property_id: str, days: int = 7):
        """Aggregate a weekly summary of Market Robot activity for one property.
        Returns dict with stats + prebuilt HTML email body.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days))
        cutoff_iso = cutoff.isoformat()

        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1}) or {"name": property_id}

        # Audit entries (rate changes from competitive rule)
        entries = await db.competitive_rate_audit.find(
            {"property_id": property_id, "applied_at": {"$gte": cutoff_iso}},
            {"_id": 0},
        ).sort("applied_at", -1).limit(1000).to_list(1000)

        auto_cnt = sum(1 for e in entries if e.get("set_by") == "auto-scan")
        manual_cnt = sum(1 for e in entries if e.get("set_by") == "manual-apply")
        deltas = [float(e.get("delta_pct", 0) or 0) for e in entries]
        avg_delta = round(sum(deltas) / len(deltas), 1) if deltas else 0.0
        biggest = max(entries, key=lambda e: abs(float(e.get("delta_pct", 0) or 0)), default=None)

        # Geo scans in last N days
        geo_count = await db.market_supply.count_documents(
            {"property_id": property_id, "scan_type": "geo", "scanned_at": {"$gte": cutoff_iso}}
        )
        # City scans in last N days
        city_count = await db.market_supply.count_documents(
            {"property_id": property_id, "scan_type": "city", "scanned_at": {"$gte": cutoff_iso}}
        )

        # Market snapshot (latest upcoming 7 days)
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        upcoming = await db.market_supply.aggregate([
            {"$match": {"property_id": property_id, "scan_type": "geo", "date": {"$gte": today_str}}},
            {"$sort": {"scanned_at": -1}},
            {"$group": {"_id": "$date", "doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$doc"}},
            {"$sort": {"date": 1}},
            {"$limit": 7},
            {"$project": {"_id": 0}},
        ]).to_list(7)
        avg_mkt_price = round(sum(s.get("avg_price", 0) or 0 for s in upcoming) / len(upcoming), 2) if upcoming else 0
        avg_demand = round(sum(s.get("unavailable_pct", 0) or 0 for s in upcoming) / len(upcoming), 1) if upcoming else 0

        # Build HTML
        prop_name = prop.get("name", property_id)
        rows_html = ""
        for e in entries[:15]:
            up = float(e.get("delta_pct", 0) or 0) > 0
            delta_color = "#f87171" if up else "#34d399" if float(e.get("delta_pct", 0) or 0) < 0 else "#a8a29e"
            src_color = "#67e8f9" if e.get("set_by") == "auto-scan" else "#c4b5fd"
            src_label = "Auto" if e.get("set_by") == "auto-scan" else "Manual"
            rows_html += (
                f"<tr style='border-bottom:1px solid #292524;'>"
                f"<td style='padding:8px;color:#d6d3d1;font-size:12px;'>{e.get('date','')}</td>"
                f"<td style='padding:8px;color:#a8a29e;font-size:12px;'>{e.get('room_type_name','')}</td>"
                f"<td style='padding:8px;color:#a8a29e;font-size:12px;text-align:right;'>£{e.get('prev_rate','—')}</td>"
                f"<td style='padding:8px;color:#c4b5fd;font-size:12px;text-align:right;font-weight:700;'>£{e.get('new_rate','—')}</td>"
                f"<td style='padding:8px;color:{delta_color};font-size:12px;text-align:right;font-weight:700;'>{'+' if up else ''}{e.get('delta_pct','—')}%</td>"
                f"<td style='padding:8px;color:{src_color};font-size:11px;text-align:right;'>{src_label}</td>"
                f"</tr>"
            )
        if not rows_html:
            rows_html = "<tr><td colspan='6' style='padding:20px;text-align:center;color:#78716c;font-size:12px;'>Bu hafta rekabetçi rate değişikliği yok.</td></tr>"

        biggest_html = ""
        if biggest:
            up = float(biggest.get("delta_pct", 0) or 0) > 0
            biggest_html = (
                f"<div style='padding:12px;background:#1c1917;border:1px solid #44403c;border-radius:8px;margin-bottom:12px;'>"
                f"<div style='font-size:10px;color:#a8a29e;text-transform:uppercase;letter-spacing:2px;'>En Büyük Değişim</div>"
                f"<div style='color:#e7e5e4;font-size:16px;font-weight:800;margin-top:4px;'>"
                f"{biggest.get('date','')} · {biggest.get('room_type_name','')} · "
                f"£{biggest.get('prev_rate','')} → £{biggest.get('new_rate','')} "
                f"<span style='color:{'#f87171' if up else '#34d399'};'>({'+' if up else ''}{biggest.get('delta_pct','')}%)</span>"
                f"</div></div>"
            )

        html = f"""
<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0a0a0a;font-family:-apple-system,system-ui,sans-serif;">
  <div style="max-width:640px;margin:0 auto;padding:24px;background:#0c0a09;color:#e7e5e4;">
    <div style="border-left:3px solid #a78bfa;padding-left:12px;margin-bottom:24px;">
      <h1 style="margin:0;color:#c4b5fd;font-size:20px;">Market Robot · Haftalık Özet</h1>
      <p style="margin:4px 0 0;color:#a8a29e;font-size:13px;">{prop_name} · Son {days} gün</p>
    </div>

    <div style="display:table;width:100%;margin-bottom:20px;">
      <div style="display:table-row;">
        <div style="display:table-cell;padding:10px;background:#1c1917;border:1px solid #44403c;border-radius:8px;margin-right:8px;width:24%;vertical-align:top;">
          <div style="font-size:10px;color:#a8a29e;text-transform:uppercase;letter-spacing:2px;">Rate Değişim</div>
          <div style="font-size:24px;color:#c4b5fd;font-weight:900;">{len(entries)}</div>
          <div style="font-size:10px;color:#78716c;">{auto_cnt} auto · {manual_cnt} manual</div>
        </div>
      </div>
    </div>

    <table style="width:100%;border-collapse:separate;border-spacing:8px;margin-bottom:20px;">
      <tr>
        <td style="padding:12px;background:#1c1917;border:1px solid #44403c;border-radius:8px;width:25%;">
          <div style="font-size:10px;color:#a8a29e;text-transform:uppercase;letter-spacing:2px;">Geo Tarama</div>
          <div style="font-size:22px;color:#34d399;font-weight:900;margin-top:4px;">{geo_count}</div>
        </td>
        <td style="padding:12px;background:#1c1917;border:1px solid #44403c;border-radius:8px;width:25%;">
          <div style="font-size:10px;color:#a8a29e;text-transform:uppercase;letter-spacing:2px;">City Tarama</div>
          <div style="font-size:22px;color:#60a5fa;font-weight:900;margin-top:4px;">{city_count}</div>
        </td>
        <td style="padding:12px;background:#1c1917;border:1px solid #44403c;border-radius:8px;width:25%;">
          <div style="font-size:10px;color:#a8a29e;text-transform:uppercase;letter-spacing:2px;">Ort. Pazar £</div>
          <div style="font-size:22px;color:#fbbf24;font-weight:900;margin-top:4px;">£{avg_mkt_price}</div>
        </td>
        <td style="padding:12px;background:#1c1917;border:1px solid #44403c;border-radius:8px;width:25%;">
          <div style="font-size:10px;color:#a8a29e;text-transform:uppercase;letter-spacing:2px;">Ort. Talep</div>
          <div style="font-size:22px;color:#f472b6;font-weight:900;margin-top:4px;">{avg_demand}%</div>
        </td>
      </tr>
    </table>

    {biggest_html}

    <h2 style="color:#e7e5e4;font-size:14px;margin:24px 0 12px;border-bottom:1px solid #292524;padding-bottom:8px;">
      Son Rate Değişiklikleri (en yeni 15)
    </h2>
    <table style="width:100%;border-collapse:collapse;background:#0c0a09;">
      <thead>
        <tr style="border-bottom:2px solid #44403c;">
          <th style="padding:8px;text-align:left;color:#a78bfa;font-size:10px;text-transform:uppercase;letter-spacing:2px;">Tarih</th>
          <th style="padding:8px;text-align:left;color:#a78bfa;font-size:10px;text-transform:uppercase;letter-spacing:2px;">Oda</th>
          <th style="padding:8px;text-align:right;color:#a78bfa;font-size:10px;text-transform:uppercase;letter-spacing:2px;">Önceki</th>
          <th style="padding:8px;text-align:right;color:#a78bfa;font-size:10px;text-transform:uppercase;letter-spacing:2px;">Yeni</th>
          <th style="padding:8px;text-align:right;color:#a78bfa;font-size:10px;text-transform:uppercase;letter-spacing:2px;">Δ</th>
          <th style="padding:8px;text-align:right;color:#a78bfa;font-size:10px;text-transform:uppercase;letter-spacing:2px;">Kaynak</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>

    <div style="margin-top:32px;padding-top:16px;border-top:1px solid #292524;font-size:11px;color:#78716c;text-align:center;">
      Bu e-posta Market Robot tarafından otomatik gönderildi. Ayarları kapatmak için: Market Robot → Neighborhood Scan → Rekabetçi Fiyat Kuralı
    </div>
  </div>
</body></html>
"""
        return {
            "property_id": property_id,
            "property_name": prop_name,
            "period_days": days,
            "stats": {
                "rate_changes": len(entries),
                "auto_applied": auto_cnt,
                "manual_applied": manual_cnt,
                "avg_delta_pct": avg_delta,
                "geo_scans": geo_count,
                "city_scans": city_count,
                "market_avg_price": avg_mkt_price,
                "avg_demand_pct": avg_demand,
                "biggest_change": biggest,
            },
            "html": html,
        }

    @router.get("/revenue/market-robot/{property_id}/weekly-summary")
    async def preview_weekly_summary(property_id: str, days: int = 7,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _build_weekly_summary(property_id, days)

    @router.post("/revenue/market-robot/{property_id}/send-weekly-summary")
    async def send_weekly_summary(property_id: str, data: Dict = {},
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        days = int(data.get("days", 7))
        recipients = data.get("recipients") or []
        if not recipients:
            # Fall back to config-stored recipients
            cfg = await db.market_robot_competitive_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
            recipients = cfg.get("email_recipients") or []
        if not recipients:
            raise HTTPException(400, "No recipients specified. Add them to the config or pass in body.")

        summary = await _build_weekly_summary(property_id, days)
        if resend is None:
            raise HTTPException(500, "Email service not configured")
        try:
            sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
            resend.emails.send({
                "from": sender,
                "to": recipients,
                "subject": f"Market Robot Haftalık Özet · {summary['property_name']} · {summary['stats']['rate_changes']} rate değişiklik",
                "html": summary["html"],
            })
            await db.market_robot_email_log.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "recipients": recipients,
                "stats": summary["stats"],
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_by": current_user.get("email") if isinstance(current_user, dict) else "system",
            })
            return {"sent": True, "recipients": recipients, "stats": summary["stats"]}
        except Exception as e:
            logger.exception(f"Weekly summary email failed: {e}")
            raise HTTPException(500, f"Failed to send email: {e}")

    S._build_weekly_summary = _build_weekly_summary
    S._compute_competitive_recommendations = _compute_competitive_recommendations
    S.apply_competitive_pricing = apply_competitive_pricing
    S.get_competitive_audit = get_competitive_audit
    S.get_competitive_config = get_competitive_config
    S.get_competitive_recommendations = get_competitive_recommendations
    S.get_geo_config = get_geo_config
    S.get_geo_scan_status = get_geo_scan_status
    S.get_geo_supply_data = get_geo_supply_data
    S.preview_weekly_summary = preview_weekly_summary
    S.send_weekly_summary = send_weekly_summary
    S.update_competitive_config = update_competitive_config
    S.update_geo_config = update_geo_config
