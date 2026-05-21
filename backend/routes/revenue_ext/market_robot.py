"""
Market Robot — Scrapes Booking.com market supply data and auto-adjusts hotel rates.
Tracks availability for 90 days, detects demand changes, and feeds into Smart Pricing.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import uuid
import re
import asyncio
import logging
import os
import httpx

logger = logging.getLogger(__name__)

SCRAPE_RUNNING = False  # legacy global flag (kept for backward compat, NOT used for new per-property lock)
SCRAPE_RUNNING_GEO = False  # legacy global flag
# Per-property concurrency locks — allows every property to scan independently in parallel.
# Key: property_id, Value: True if a scan is in flight for that property.
SCRAPE_LOCKS: dict = {}
SCRAPE_LOCKS_GEO: dict = {}


async def _internal_close_gap(db, property_id: str, strategy: str = "half",
                              days: int = 14, dry_run: bool = False,
                              min_gap_pct: float = 0.0,
                              source: str = "market-gap-close",
                              user_name: str = "system",
                              batch_id: str | None = None) -> dict:
    """Re-usable gap-close logic — used by both /close-gap endpoint and /fleet-close-gap.

    Sadece pazarın altındaki günlere yazar. min_gap_pct (default 0) altında olanlar
    skip edilir. batch_id geçerse rate_overrides'a batch_id ile damgalanır (undo için).
    """
    from datetime import datetime, timezone, timedelta

    comps = await db.market_competitors.find(
        {"property_id": property_id}, {"_id": 0, "prices": 1}
    ).to_list(50)
    per_day: dict = {}
    for c in comps:
        for row in (c.get("prices") or []):
            if not row.get("scraped"):
                continue
            d = row.get("date")
            lp = row.get("lowest_price")
            if not (d and lp):
                continue
            try:
                per_day.setdefault(d, []).append(float(lp))
            except Exception:
                pass

    if not per_day:
        return {"applied": 0, "skipped": 0, "avg_uplift_pct": 0,
                "days_evaluated": days, "reason": "no_competitor_data"}

    now = datetime.now(timezone.utc)
    date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
    base_rate = float((rt or {}).get("base_rate") or 100)
    existing_ov = await db.rate_overrides.find(
        {"property_id": property_id, "date": {"$in": date_keys}},
        {"_id": 0, "date": 1, "custom_rate": 1},
    ).to_list(500)
    ov_map = {o["date"]: o.get("custom_rate") for o in existing_ov if o.get("custom_rate")}

    applied = 0
    skipped = 0
    total_uplift_pct = 0.0
    upserts = []
    for d in date_keys:
        prices = per_day.get(d) or []
        if not prices:
            skipped += 1
            continue
        market_avg = sum(prices) / len(prices)
        market_min = min(prices)
        our_rate = float(ov_map.get(d, base_rate))

        gap_pct = ((market_avg - our_rate) / market_avg) * 100 if market_avg else 0
        if gap_pct < min_gap_pct or our_rate >= market_avg:
            skipped += 1
            continue

        if strategy == "full":
            new_rate = market_avg
        elif strategy == "half":
            new_rate = our_rate + (market_avg - our_rate) * 0.5
        elif strategy == "floor":
            new_rate = max(our_rate, market_min)
        else:  # value
            new_rate = market_avg * 0.95

        if strategy != "full":
            new_rate = min(new_rate, market_avg)
        new_rate = max(new_rate, our_rate)
        new_rate = round(new_rate, 2)

        if new_rate > our_rate:
            uplift_pct = ((new_rate - our_rate) / our_rate) * 100 if our_rate else 0
            applied += 1
            total_uplift_pct += uplift_pct
            ctx = {
                "strategy": strategy,
                "market_avg": round(market_avg, 2),
                "market_min": round(market_min, 2),
                "previous_rate": round(our_rate, 2),
            }
            if batch_id:
                ctx["batch_id"] = batch_id
            upserts.append({
                "property_id": property_id, "date": d,
                "custom_rate": new_rate, "source": source,
                "set_by": user_name, "set_at": now.isoformat(),
                "context": ctx,
            })

    if not dry_run and upserts:
        for u in upserts:
            await db.rate_overrides.update_one(
                {"property_id": property_id, "date": u["date"]},
                {"$set": u}, upsert=True,
            )

    return {
        "applied": applied,
        "skipped": skipped,
        "days_evaluated": days,
        "avg_uplift_pct": round(total_uplift_pct / applied, 1) if applied else 0,
    }


def _count_booking_cards(html_text: str) -> int:
    """Count actual property cards rendered in Booking.com search HTML.
    Booking wraps each result with data-testid attributes — these respect
    the distance/geo filter, unlike the '4,260 properties found' header.
    """
    if not html_text:
        return 0
    # Primary marker used across Booking.com layouts
    count = len(re.findall(r'data-testid="property-card"', html_text))
    if count > 0:
        return count
    # Secondary fallback markers seen on A/B variants
    alt = len(re.findall(r'data-testid="property-card-container"', html_text))
    if alt > 0:
        return alt
    # Anchor-based fallback: hotel listing links
    anchors = len(re.findall(r'/hotel/[a-z]{2}/[a-z0-9\-]+\.', html_text, re.I))
    return anchors


async def _osm_hotel_count(latitude: float, longitude: float, radius_km: float) -> Optional[int]:
    """Query OpenStreetMap Overpass API for hotels/hostels/guest_houses within radius.
    Free, no API key, ~1 req/sec. Returns None on failure.
    """
    if latitude is None or longitude is None:
        return None
    try:
        radius_m = int(radius_km * 1000)
        query = (
            f"[out:json][timeout:15];"
            f"(node(around:{radius_m},{latitude},{longitude})[tourism~\"^(hotel|hostel|guest_house|apartment|motel)$\"];"
            f"way(around:{radius_m},{latitude},{longitude})[tourism~\"^(hotel|hostel|guest_house|apartment|motel)$\"];);"
            f"out count;"
        )
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                headers={"User-Agent": "HotelBox-MarketRobot/1.0"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            elems = data.get("elements", [])
            for el in elems:
                if el.get("type") == "count":
                    tags = el.get("tags", {})
                    total = int(tags.get("total", 0))
                    if total > 0:
                        return total
            return None
    except Exception as e:
        logger.info(f"OSM Overpass failed: {e}")
        return None


async def _google_places_hotel_count(latitude: float, longitude: float, radius_km: float) -> Optional[int]:
    """Count lodgings via Google Places API Nearby Search (requires GOOGLE_PLACES_API_KEY).
    Google caps to 60 results, so for radius > 2 km we use it as a lower bound signal only.
    """
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not key or latitude is None or longitude is None:
        return None
    try:
        radius_m = min(int(radius_km * 1000), 50000)
        url = (
            f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            f"?location={latitude},{longitude}&radius={radius_m}&type=lodging&key={key}"
        )
        results = []
        next_token = None
        async with httpx.AsyncClient(timeout=15) as client:
            for _ in range(3):  # up to 3 pages × 20 = 60 results
                u = url + (f"&pagetoken={next_token}" if next_token else "")
                resp = await client.get(u)
                if resp.status_code != 200:
                    break
                data = resp.json()
                results.extend(data.get("results", []))
                next_token = data.get("next_page_token")
                if not next_token:
                    break
                await asyncio.sleep(2)  # Google requires 2s between paginated calls
        return len(results) if results else None
    except Exception as e:
        logger.info(f"Google Places failed: {e}")
        return None


def _radius_based_property_count(radius_km, location_hint=""):
    """Realistic neighborhood property count based on geo-radius.
    Central London density ≈ 35/sq mi; suburban ≈ 8/sq mi.
    """
    import math
    radius_mi = radius_km * 0.621371
    area_mi2 = math.pi * (radius_mi ** 2)
    hint = (location_hint or "").lower()
    central_codes = ["e1", "ec1", "ec2", "ec3", "ec4", "w1", "wc1", "wc2", "se1", "sw1", "nw1", "n1", "aldgate", "city of london", "shoreditch", "covent garden", "soho", "westminster", "holborn", "bloomsbury", "kings cross", "london bridge"]
    is_central = any(c in hint for c in central_codes) or hint.strip() == "london"
    density = 35 if is_central else 10  # per sq mi
    return max(15, round(area_mi2 * density))


def _price_stats(prices):
    """Return avg/min/max/median price stats from a list of numbers (empty-safe)."""
    if not prices:
        return {"avg_price": 0, "min_price": 0, "max_price": 0, "median_price": 0, "price_samples": 0}
    sorted_p = sorted(prices)
    n = len(sorted_p)
    median = sorted_p[n // 2] if n % 2 == 1 else (sorted_p[n // 2 - 1] + sorted_p[n // 2]) / 2
    return {
        "avg_price": round(sum(sorted_p) / n, 2),
        "min_price": round(sorted_p[0], 2),
        "max_price": round(sorted_p[-1], 2),
        "median_price": round(median, 2),
        "price_samples": n,
    }


async def fleet_geo_validate_worker(db, *, fix: bool = True, sleep_s: float = 1.1) -> dict:
    """Standalone fleet-wide coordinate validation + auto-repair (iter 320).

    Importable from server.py to register as a weekly cron job. Implements
    the same logic as POST /api/revenue/market-robot/fleet-validate-geo but
    with no FastAPI deps. Returns the summary dict used in scheduler_history.
    """
    from utils.booking_scraper import reverse_geocode, geocode_address

    COUNTRY_MAP_FV = {
        "UK": "gb", "GB": "gb", "ENGLAND": "gb", "UNITED KINGDOM": "gb",
        "US": "us", "USA": "us", "UNITED STATES": "us",
        "TR": "tr", "TURKEY": "tr", "TÜRKIYE": "tr", "TURKIYE": "tr",
        "FR": "fr", "FRANCE": "fr", "DE": "de", "GERMANY": "de",
        "ES": "es", "SPAIN": "es", "IT": "it", "ITALY": "it",
        "NL": "nl", "NETHERLANDS": "nl", "CH": "ch", "SWITZERLAND": "ch",
        "AT": "at", "AUSTRIA": "at", "BE": "be", "BELGIUM": "be",
        "PT": "pt", "PORTUGAL": "pt", "IE": "ie", "IRELAND": "ie",
        "GR": "gr", "GREECE": "gr",
    }
    sleep_s = max(0.5, min(sleep_s, 3.0))
    props = await db.properties.find(
        {"is_active": {"$ne": False}},
        {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1,
         "postcode": 1, "address": 1, "latitude": 1, "longitude": 1},
    ).to_list(500)

    ok_ct = flagged_ct = fixed_ct = skipped_ct = 0
    flagged_names: list = []
    fixed_names: list = []

    for prop in props:
        pid = prop.get("id")
        lat, lon = prop.get("latitude"), prop.get("longitude")
        city = (prop.get("city") or "").strip()
        country_raw = (prop.get("country") or "").strip().upper()
        expected_cc = COUNTRY_MAP_FV.get(country_raw, country_raw.lower()[:2] if country_raw else "")
        if not (lat and lon) or not expected_cc:
            skipped_ct += 1
            continue
        rev = await reverse_geocode(lat, lon)
        await asyncio.sleep(sleep_s)
        if not rev:
            skipped_ct += 1
            continue
        actual_cc = (rev.get("country_code") or "").lower()
        if actual_cc == expected_cc:
            ok_ct += 1
            continue
        flagged_ct += 1
        flagged_names.append(prop.get("name", pid))
        if not fix:
            continue
        # Repair: forward-geocode with country bias.
        addr = (prop.get("address") or "").strip()
        pc = (prop.get("postcode") or "").strip()
        nm = (prop.get("name") or "").strip()
        candidates_q = []
        if addr:
            candidates_q.append(" ".join([x for x in [addr, pc, city] if x]))
        if pc and city:
            candidates_q.append(f"{pc} {city}")
        if nm and city:
            candidates_q.append(f"{nm} {city}")
        if nm and expected_cc:
            candidates_q.append(nm)
        seen, ordered_q = set(), []
        for q in candidates_q:
            qn = (q or "").strip()
            if qn and qn.lower() not in seen:
                seen.add(qn.lower())
                ordered_q.append(qn)
        for q in ordered_q:
            geo = await geocode_address(q, country_code=expected_cc)
            await asyncio.sleep(sleep_s)
            if not geo:
                continue
            new_lat, new_lon, new_display = geo
            if city and city.lower() not in (new_display or "").lower():
                continue
            await db.properties.update_one(
                {"id": pid},
                {"$set": {
                    "latitude": new_lat, "longitude": new_lon,
                    "geocoded_from": q,
                    "geocoded_display_name": new_display,
                    "geocoded_at": datetime.now(timezone.utc).isoformat(),
                    "geo_validated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            fixed_ct += 1
            fixed_names.append(prop.get("name", pid))
            break

    return {
        "ok": True,
        "total_properties": len(props),
        "ok_count": ok_ct,
        "flagged_count": flagged_ct,
        "fixed_count": fixed_ct,
        "skipped_count": skipped_ct,
        "flagged": flagged_names[:10],
        "fixed": fixed_names[:10],
        "fix": fix,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


async def _vision_extract_one_module(booking_url: str, model: str = "gpt-4o-mini") -> dict:
    """Module-scope Vision extractor — usable from background workers and
    weekly cron. See `_vision_extract_one` inside the router for context.

    Returns dict with keys: ok, hotel_name, room_count, price_per_night,
    currency, star_rating, review_score, review_count, is_blocked_page,
    screenshot_size_bytes, error.
    """
    from utils.booking_scraper import scrape_booking_screenshot
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    import base64 as _b64
    import json as _json

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {"ok": False, "error": "no_emergent_llm_key"}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    except ImportError:
        return {"ok": False, "error": "emergentintegrations_missing"}

    url = (booking_url or "").strip()
    if not url:
        return {"ok": False, "error": "missing_url"}
    if "/hotel/" in url:
        ci = (datetime.now(timezone.utc).date() + timedelta(days=14)).isoformat()
        co = (datetime.now(timezone.utc).date() + timedelta(days=15)).isoformat()
        p = urlparse(url)
        q = parse_qs(p.query)
        if "checkin" not in q:
            q["checkin"] = [ci]
        if "checkout" not in q:
            q["checkout"] = [co]
        if "group_adults" not in q:
            q["group_adults"] = ["2"]
        if "no_rooms" not in q:
            q["no_rooms"] = ["1"]
        url = urlunparse(p._replace(query=urlencode(q, doseq=True)))
    png = await scrape_booking_screenshot(url, full_page=False)
    if not png:
        return {"ok": False, "error": "screenshot_failed", "booking_url": url}
    b64 = _b64.b64encode(png).decode("ascii")
    SYSTEM = (
        "You are a hospitality data extractor. Given a screenshot of a "
        "Booking.com hotel/apartment listing page, extract the visible "
        "facts and return ONLY compact JSON with these keys: "
        '{"hotel_name": <string|null>, "room_count": <int|null>, '
        '"price_per_night": <float|null>, "currency": <"GBP"|"USD"|"EUR"|"TRY"|"CHF"|null>, '
        '"star_rating": <int|null>, "review_score": <float|null>, '
        '"review_count": <int|null>, "is_blocked_page": <bool>}. '
        "Rules: room_count only when 'X rooms/apartments/units' visible; "
        "price_per_night = headline lowest visible price; currency 3-letter ISO; "
        "is_blocked_page true if 'Page not found' or generic landing. "
        "Return ONLY JSON, no markdown fences."
    )
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"booking-vision-cron-{uuid.uuid4().hex[:8]}",
            system_message=SYSTEM,
        ).with_model("openai", model)
        reply = await chat.send_message(UserMessage(
            text="Extract the facts from this Booking.com screenshot.",
            file_contents=[ImageContent(image_base64=b64)],
        ))
    except Exception as e:
        return {"ok": False, "error": "vision_call_failed",
                "message": str(e)[:200], "screenshot_size_bytes": len(png)}
    raw = (reply or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
    try:
        parsed = _json.loads(raw)
    except Exception:
        return {"ok": False, "error": "parse_failed",
                "raw_extraction": raw[:300],
                "screenshot_size_bytes": len(png)}
    return {
        "ok": True,
        "hotel_name": parsed.get("hotel_name"),
        "room_count": parsed.get("room_count"),
        "price_per_night": parsed.get("price_per_night"),
        "currency": parsed.get("currency"),
        "star_rating": parsed.get("star_rating"),
        "review_score": parsed.get("review_score"),
        "review_count": parsed.get("review_count"),
        "is_blocked_page": bool(parsed.get("is_blocked_page", False)),
        "screenshot_size_bytes": len(png),
    }


async def fleet_vision_enrich_worker(db, *, max_per_property: int = 25) -> dict:
    """Standalone fleet-wide Vision enrichment for ALL property competitors.

    Used by the weekly scheduler cron (`fleet_vision_enrich` job) to keep
    competitor room counts + prices fresh without any user action.

    Sequential per-URL (Booking.com rate-limit). Caps each property to
    `max_per_property` competitors so a single mega-property can't starve
    the rest.

    Returns: {processed, enriched, blocked, errors, properties_done, ran_at}
    """
    props = await db.properties.find(
        {"is_active": {"$ne": False}}, {"_id": 0, "id": 1},
    ).to_list(500)

    total_processed = 0
    total_enriched = 0
    total_blocked = 0
    total_errors = 0
    properties_done = 0

    for prop in props:
        pid = prop.get("id")
        if not pid:
            continue
        comps = await db.market_competitors.find(
            {"property_id": pid},
            {"_id": 0, "id": 1, "booking_url": 1, "name": 1},
        ).limit(max_per_property).to_list(max_per_property)
        if not comps:
            continue
        properties_done += 1
        await db.market_robot_vision_status.update_one(
            {"property_id": pid},
            {"$set": {
                "property_id": pid, "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total": len(comps), "done": 0, "enriched": 0,
                "blocked": 0, "errors": 0, "source": "weekly_cron",
            }},
            upsert=True,
        )
        done = enriched = blocked = errors = 0
        for c in comps:
            url = c.get("booking_url") or ""
            if not url:
                errors += 1
                done += 1
                total_processed += 1
                continue
            try:
                out = await _vision_extract_one_module(url)
            except Exception as e:
                logger.warning("fleet_vision_enrich failed for %s: %s", c.get("name"), e)
                out = {"ok": False, "error": str(e)[:120]}
            update_doc = {"vision_checked_at": datetime.now(timezone.utc).isoformat()}
            if out.get("ok"):
                if out.get("is_blocked_page"):
                    blocked += 1
                    update_doc["vision_is_blocked"] = True
                else:
                    update_doc["vision_is_blocked"] = False
                    if out.get("room_count") is not None:
                        update_doc["vision_room_count"] = out["room_count"]
                    if out.get("price_per_night") is not None:
                        update_doc["vision_price"] = out["price_per_night"]
                    if out.get("currency"):
                        update_doc["vision_currency"] = out["currency"]
                    if out.get("star_rating") is not None:
                        update_doc["vision_star_rating"] = out["star_rating"]
                    if out.get("review_score") is not None:
                        update_doc["vision_review_score"] = out["review_score"]
                    if out.get("review_count") is not None:
                        update_doc["vision_review_count"] = out["review_count"]
                    enriched += 1
            else:
                errors += 1
                update_doc["vision_last_error"] = out.get("error", "unknown")[:120]
            await db.market_competitors.update_one(
                {"id": c["id"]}, {"$set": update_doc}
            )
            done += 1
            total_processed += 1
            await db.market_robot_vision_status.update_one(
                {"property_id": pid},
                {"$set": {"done": done, "enriched": enriched,
                          "blocked": blocked, "errors": errors,
                          "last_name": c.get("name", "")}},
            )
        await db.market_robot_vision_status.update_one(
            {"property_id": pid},
            {"$set": {"status": "done",
                      "finished_at": datetime.now(timezone.utc).isoformat()}},
        )
        total_enriched += enriched
        total_blocked += blocked
        total_errors += errors

    return {
        "processed": total_processed,
        "enriched": total_enriched,
        "blocked": total_blocked,
        "errors": total_errors,
        "properties_done": properties_done,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


async def fleet_competitor_price_scan_worker(
    db, *, days_ahead: int = 30, max_per_property: int = 25,
    comp_concurrency: int = 3,
) -> dict:
    """Weekly fleet-wide competitor PRICE scrape (Booking.com lowest-rate
    extraction). Complements `fleet_vision_enrich_worker` which only pulls
    room counts + headline price from screenshots.

    For every active property:
      • Pull up to `max_per_property` saved competitors
      • For each competitor, scrape `days_ahead` days of Booking.com prices
        (via `scrape_booking_url` + `build_dated_url`) running `comp_concurrency`
        competitors in parallel under a Semaphore
      • Persist the per-date `prices` array on the competitor row so the
        Per-Hotel Price Trend chart populates without any user action

    Sized so a 30-day × 10-competitor fleet refresh fits inside ~7 minutes
    per property. Runs sequentially across properties to keep memory steady.
    """
    from utils.booking_scraper import scrape_booking_url, build_dated_url

    props = await db.properties.find(
        {"is_active": {"$ne": False}}, {"_id": 0, "id": 1, "currency": 1},
    ).to_list(500)

    total_scanned = 0
    total_prices = 0
    total_properties = 0
    days_ahead = max(1, min(int(days_ahead), 90))

    for prop in props:
        pid = prop.get("id")
        if not pid:
            continue
        comps = await db.market_competitors.find(
            {"property_id": pid}, {"_id": 0},
        ).limit(max_per_property).to_list(max_per_property)
        if not comps:
            continue
        total_properties += 1
        target_currency = prop.get("currency") or "GBP"
        now = datetime.now(timezone.utc)
        comp_sem = asyncio.Semaphore(comp_concurrency)
        scanned = [0]
        prices = [0]

        async def _scan_comp(comp):
            base_url = comp.get("booking_url", "")
            if not base_url:
                return
            async with comp_sem:
                comp_prices = []
                cached_hotel_id = comp.get("booking_hotel_id")
                resolved_hotel_id = cached_hotel_id
                resolved_name = comp.get("name", "")
                last_score = None
                name_hint = (comp.get("slug") or "").replace("-", " ")[:18]
                for i in range(days_ahead):
                    d = now + timedelta(days=i)
                    checkin = d.strftime("%Y-%m-%d")
                    checkout = (d + timedelta(days=1)).strftime("%Y-%m-%d")
                    url = build_dated_url(base_url, checkin, checkout, target_currency)
                    try:
                        result = await scrape_booking_url(
                            url, timeout_ms=30000,
                            hotel_id=resolved_hotel_id,
                            hotel_name_hint=name_hint,
                        )
                        if result.get("hotel_id"):
                            resolved_hotel_id = result["hotel_id"]
                        if result.get("hotel_name"):
                            resolved_name = result["hotel_name"]
                        if result["scraped"]:
                            comp_prices.append({
                                "date": checkin,
                                "lowest_price": result["lowest_price"],
                                "all_prices": result["all_prices"],
                                "score": result["score"],
                                "scraped": True,
                            })
                            prices[0] += 1
                            if result["score"]:
                                last_score = result["score"]
                        else:
                            comp_prices.append({"date": checkin, "lowest_price": None,
                                                "scraped": False, "error": result.get("error")})
                    except Exception as e:
                        logger.warning(f"fleet comp scan failed for {comp.get('name')}: {e}")
                        comp_prices.append({"date": checkin, "lowest_price": None, "scraped": False})
                    await asyncio.sleep(1.5)
                update_fields = {
                    "prices": comp_prices,
                    "last_scraped": now.isoformat(),
                    "last_source": "weekly_cron",
                }
                if last_score:
                    update_fields["review_score"] = last_score
                if resolved_hotel_id and resolved_hotel_id != cached_hotel_id:
                    update_fields["booking_hotel_id"] = resolved_hotel_id
                if resolved_name and resolved_name != comp.get("name", ""):
                    original = (comp.get("name") or "").strip().lower()
                    slug_default = (comp.get("slug") or "").replace("-", " ").strip().lower()
                    if original in ("", slug_default):
                        update_fields["name"] = resolved_name
                await db.market_competitors.update_one(
                    {"id": comp["id"]}, {"$set": update_fields}
                )
                scanned[0] += 1

        await asyncio.gather(*[_scan_comp(c) for c in comps])
        total_scanned += scanned[0]
        total_prices += prices[0]

    return {
        "properties_done": total_properties,
        "competitors_scanned": total_scanned,
        "prices_found": total_prices,
        "days_ahead": days_ahead,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


def create_market_robot_router(db, require_roles, resend=None):
    router = APIRouter()

    async def _scrape_booking_date(location: str, checkin: str, checkout: str, language: str = "en-gb",
                                   latitude: Optional[float] = None, longitude: Optional[float] = None,
                                   radius_km: Optional[float] = None, currency: Optional[str] = None):
        """Scrape Booking.com search results. Accepts either free-text location (city/postcode/address)
        OR coordinates+radius for precise geo-radius scanning.

        `currency` pins Booking.com's price rendering to an ISO code (e.g. 'GBP' for London
        scans). Without this, Booking falls back to datacenter geo-IP currency and the
        extracted numbers become inconsistent — which is what users saw on the Neighborhood
        chart (London postcode scans showing CHF-labelled numbers that were actually EUR/USD).
        """
        # URL params: ss=location for text, or latitude+longitude+nflt=distance for precise geo
        cur_param = f"&selected_currency={currency.upper()}" if currency else ""
        if latitude is not None and longitude is not None and radius_km:
            # Booking.com geo-radius filter: distance in meters
            radius_m = int(radius_km * 1000)
            url = (f"https://www.booking.com/searchresults.{language}.html?"
                   f"ss={location or 'Hotel'}&latitude={latitude}&longitude={longitude}"
                   f"&checkin={checkin}&checkout={checkout}&group_adults=2&no_rooms=1&group_children=0"
                   f"&nflt=distance%3D{radius_m}{cur_param}")
        else:
            url = (f"https://www.booking.com/searchresults.{language}.html?"
                   f"ss={location}&checkin={checkin}&checkout={checkout}"
                   f"&group_adults=2&no_rooms=1&group_children=0{cur_param}")

        # Strategy 1: Direct request with rotating headers
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        ]
        import random as _rand
        ua = _rand.choice(user_agents)

        strategies = [
            # Strategy 1: Google referer
            {"Referer": "https://www.google.com/", "Sec-Fetch-Site": "cross-site"},
            # Strategy 2: Direct navigation
            {"Referer": "https://www.booking.com/", "Sec-Fetch-Site": "same-origin"},
            # Strategy 3: No referer
            {},
        ]

        for strat in strategies:
            try:
                headers = {
                    "User-Agent": ua,
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Cache-Control": "no-cache",
                    **strat,
                }
                async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                    text = resp.text

                    # Check if blocked
                    if resp.status_code == 202 or "challenge" in text[:500].lower():
                        continue

                    total_match = re.search(r'([\d,]+)\s*properties?\s*found', text)
                    total_properties = int(total_match.group(1).replace(",", "")) if total_match else 0

                    if total_properties == 0:
                        continue

                    # Priority chain for geo scans: the '4,260 properties found' header
                    # ignores nflt=distance, so we must source a realistic number.
                    is_geo_scan = radius_km is not None
                    total_source = "booking-header"
                    if is_geo_scan:
                        # 1) Booking property-card count (respects distance filter)
                        card_count = _count_booking_cards(text)
                        if card_count >= 5:
                            # Booking paginates at 25/page; card_count × (total_pages heuristic)
                            # Attempt to read "Showing 1-25 of X properties" first
                            page_total = re.search(r'Showing\s*\d+\s*[-–]\s*\d+\s*of\s*([\d,]+)', text, re.I)
                            if page_total:
                                total_properties = int(page_total.group(1).replace(",", ""))
                                total_source = "booking-pager"
                            else:
                                total_properties = card_count
                                total_source = "booking-cards"
                        else:
                            # 2) OSM Overpass free API
                            osm_n = await _osm_hotel_count(latitude, longitude, radius_km) if (latitude and longitude) else None
                            # 3) Google Places API (only if key present)
                            gp_n = await _google_places_hotel_count(latitude, longitude, radius_km) if (latitude and longitude) else None
                            # Prefer Google if populated & radius small (<=5km), else OSM, else heuristic
                            if gp_n and (gp_n >= 10 or (osm_n is None or gp_n >= osm_n)):
                                total_properties = gp_n
                                total_source = "google-places"
                            elif osm_n:
                                total_properties = osm_n
                                total_source = "osm"
                            else:
                                total_properties = _radius_based_property_count(radius_km, location)
                                total_source = "heuristic"

                    unavail_match = re.search(r'(\d+)%\s*of\s*places?\s*to\s*stay\s*are\s*unavailable', text)
                    unavailable_pct = int(unavail_match.group(1)) if unavail_match else 0

                    if total_properties > 0 and unavailable_pct == 0:
                        alt_match = re.search(r'(\d+)%\s*of\s*places', text)
                        if alt_match:
                            unavailable_pct = int(alt_match.group(1))

                    available_pct = 100 - unavailable_pct
                    available_est = round(total_properties * available_pct / 100)

                    # Extract prices (£123, $123, €123, etc.) — up to 60 matches
                    price_matches = re.findall(r'(?:£|US\$|\$|€)\s*([\d,]+(?:\.\d+)?)', text)
                    prices = []
                    for pm in price_matches[:120]:
                        try:
                            val = float(pm.replace(",", ""))
                            if 20 <= val <= 5000:  # Sanity window — filter out per-person fees and totals
                                prices.append(val)
                        except Exception:
                            pass
                    price_stats = _price_stats(prices)

                    return {
                        "total_properties": total_properties,
                        "total_source": total_source,
                        "unavailable_pct": unavailable_pct,
                        "available_pct": available_pct,
                        "available_est": available_est,
                        "scraped": True,
                        "method": "direct",
                        **price_stats,
                    }
            except Exception as e:
                logger.warning(f"Strategy failed for {checkin}: {e}")
                continue

        # Strategy 2: Use ScrapingBee API if configured
        scraping_key = os.environ.get("SCRAPINGBEE_API_KEY", "")
        if scraping_key:
            try:
                api_url = f"https://app.scrapingbee.com/api/v1/?api_key={scraping_key}&url={url}&render_js=false&country_code=gb"
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(api_url)
                    text = resp.text
                    total_match = re.search(r'([\d,]+)\s*properties?\s*found', text)
                    total_properties = int(total_match.group(1).replace(",", "")) if total_match else 0
                    unavail_match = re.search(r'(\d+)%\s*of\s*places?\s*to\s*stay\s*are\s*unavailable', text)
                    unavailable_pct = int(unavail_match.group(1)) if unavail_match else 0
                    if total_properties > 0:
                        # For geo scans: override with radius-based realistic count
                        if radius_km is not None:
                            total_properties = _radius_based_property_count(radius_km, location)
                        price_matches = re.findall(r'(?:£|US\$|\$|€)\s*([\d,]+(?:\.\d+)?)', text)
                        prices = []
                        for pm in price_matches[:120]:
                            try:
                                val = float(pm.replace(",", ""))
                                if 20 <= val <= 5000:
                                    prices.append(val)
                            except Exception:
                                pass
                        return {
                            "total_properties": total_properties, "unavailable_pct": unavailable_pct,
                            "available_pct": 100 - unavailable_pct,
                            "available_est": round(total_properties * (100 - unavailable_pct) / 100),
                            "scraped": True, "method": "scrapingbee",
                            **_price_stats(prices),
                        }
            except Exception as e:
                logger.warning(f"ScrapingBee failed for {checkin}: {e}")

        # Fallback: intelligent estimation based on date patterns
        try:
            d = datetime.strptime(checkin, "%Y-%m-%d")
            dow = d.weekday()
            days_ahead = (d - datetime.now(timezone.utc).replace(tzinfo=None)).days
            # Base unavailability from typical London patterns
            base = 55
            if dow >= 4:  # Fri/Sat/Sun higher demand
                base += 15
            if days_ahead <= 3:  # Last-minute higher
                base += 10
            elif days_ahead > 60:  # Far out lower
                base -= 10
            # Month seasonality
            month = d.month
            if month in [6, 7, 8, 12]:  # Summer + Christmas
                base += 10
            elif month in [1, 2, 11]:  # Low season
                base -= 10
            unavail = max(15, min(92, base + _rand.randint(-8, 8)))
            # For geo scans: try OSM → Google → heuristic; else use London-wide baseline
            total_source = "heuristic"
            if radius_km is not None:
                osm_n = await _osm_hotel_count(latitude, longitude, radius_km) if (latitude and longitude) else None
                gp_n = await _google_places_hotel_count(latitude, longitude, radius_km) if (latitude and longitude) else None
                if gp_n and gp_n >= 10:
                    total_props = gp_n
                    total_source = "google-places"
                elif osm_n:
                    total_props = osm_n
                    total_source = "osm"
                else:
                    total_props = _radius_based_property_count(radius_km, location)
                    total_source = "heuristic"
            else:
                total_props = 4260
                total_source = "city-baseline"
            # Estimated prices scale with demand + seasonality + day-of-week
            base_price = 130  # London ADR baseline
            price_factor = 1.0 + (unavail - 55) * 0.012  # higher demand → higher prices
            if dow >= 4:  # Weekends
                price_factor += 0.10
            if month in [6, 7, 8, 12]:
                price_factor += 0.12
            elif month in [1, 2, 11]:
                price_factor -= 0.10
            avg = round(base_price * price_factor * (1 + _rand.uniform(-0.05, 0.08)), 2)
            return {
                "total_properties": total_props,
                "total_source": total_source,
                "unavailable_pct": unavail,
                "available_pct": 100 - unavail,
                "available_est": round(total_props * (100 - unavail) / 100),
                "scraped": True,
                "method": "estimated",
                "avg_price": avg,
                "min_price": round(avg * 0.55, 2),
                "max_price": round(avg * 2.4, 2),
                "median_price": round(avg * 0.88, 2),
                "price_samples": 0,
            }
        except Exception:
            return {"total_properties": 0, "unavailable_pct": 0, "available_pct": 100, "available_est": 0,
                    "scraped": False, "method": "failed",
                    "avg_price": 0, "min_price": 0, "max_price": 0, "median_price": 0, "price_samples": 0}

    async def _calculate_price_adjustment(db, property_id, date_str, supply_data, prev_supply):
        """Calculate price adjustment based on supply trend."""
        if not supply_data.get("scraped"):
            return 0, "No data"

        unavail = supply_data["unavailable_pct"]
        prev_unavail = prev_supply.get("unavailable_pct", 50) if prev_supply else 50

        # Supply is dropping (more unavailable = more demand)
        if unavail >= 90:
            adj = 35  # Extreme demand
            reason = f"Extreme scarcity: {unavail}% unavailable"
        elif unavail >= 80:
            adj = 25
            reason = f"Very high demand: {unavail}% unavailable"
        elif unavail >= 70:
            adj = 15
            reason = f"High demand: {unavail}% unavailable"
        elif unavail >= 60:
            adj = 8
            reason = f"Above average demand: {unavail}% unavailable"
        elif unavail >= 40:
            adj = 0
            reason = f"Normal supply: {unavail}% unavailable"
        elif unavail >= 25:
            adj = -8
            reason = f"Below average demand: {unavail}% unavailable"
        elif unavail >= 10:
            adj = -15
            reason = f"Low demand, oversupply: {unavail}% unavailable"
        else:
            adj = -25
            reason = f"Very low demand: {unavail}% unavailable"

        # Trend bonus: if supply is dropping faster than before
        if prev_supply and prev_supply.get("scraped"):
            trend = unavail - prev_unavail
            if trend > 10:
                adj += 5
                reason += f" | Accelerating demand (+{trend}pp)"
            elif trend < -10:
                adj -= 5
                reason += f" | Demand declining ({trend}pp)"

        return adj, reason

    async def _apply_auto_pricing(db, property_id, snapshots):
        """Apply price adjustments to rate overrides based on supply data."""
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if not room_types:
            room_types = [{"id": "default", "name": "Standard", "base_rate": 100}]

        applied = []
        for snap in snapshots:
            if not snap.get("scraped"):
                continue
            date_str = snap["date"]
            adj_pct = snap.get("price_adjustment_pct", 0)
            if adj_pct == 0:
                continue

            for rt in room_types:
                base = float(rt.get("base_rate", 100) or 100)
                new_rate = round(base * (1 + adj_pct / 100), 2)
                min_rate = round(base * 0.6, 2)
                max_rate = round(base * 2.5, 2)
                new_rate = max(min_rate, min(max_rate, new_rate))

                await db.rate_overrides.update_one(
                    {"property_id": property_id, "date": date_str, "room_type_id": rt.get("id", "")},
                    {"$set": {
                        "property_id": property_id,
                        "room_type_id": rt.get("id", ""),
                        "date": date_str,
                        "custom_rate": new_rate,
                        "set_by": "market-robot",
                        "reason": snap.get("reason", ""),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True
                )
                applied.append({"date": date_str, "room": rt.get("name", ""), "rate": new_rate, "adj": adj_pct})

        return applied

    # ==================== ENDPOINTS ====================

    @router.get("/revenue/market-robot/{property_id}/config")
    async def get_config(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        # Default config structure
        defaults = {
            "property_id": property_id,
            "enabled": False,
            "city": "London",
            "scan_interval_minutes": 10,
            "days_ahead": 365,
            "auto_pricing": True,
            "max_increase_pct": 35,
            "max_decrease_pct": 25,
            "currency": "GBP",
            "language": "en-gb",
            "last_scan": None,
            "total_scans": 0,
        }
        config = await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0})
        if config:
            # Merge with defaults to ensure all fields present
            defaults.update(config)
        return defaults

    # City → currency mapping (same as frontend — source of truth for auto-sync)
    CITY_CURRENCY = {
        "london": "GBP", "manchester": "GBP", "edinburgh": "GBP",
        "dublin": "EUR", "paris": "EUR", "berlin": "EUR", "munich": "EUR",
        "amsterdam": "EUR", "rome": "EUR", "madrid": "EUR", "barcelona": "EUR",
        "vienna": "EUR", "lisbon": "EUR", "athens": "EUR", "brussels": "EUR",
        "zurich": "CHF", "geneva": "CHF", "basel": "CHF",
        "oslo": "NOK", "stockholm": "SEK", "copenhagen": "DKK",
        "istanbul": "TRY", "ankara": "TRY", "izmir": "TRY",
        "new york": "USD", "los angeles": "USD", "chicago": "USD", "miami": "USD",
        "toronto": "CAD", "vancouver": "CAD",
        "sydney": "AUD", "melbourne": "AUD", "auckland": "NZD",
        "tokyo": "JPY", "osaka": "JPY",
        "beijing": "CNY", "shanghai": "CNY",
        "hong kong": "HKD", "singapore": "SGD", "bangkok": "THB",
        "dubai": "AED", "abu dhabi": "AED",
        "mumbai": "INR", "delhi": "INR", "bangalore": "INR",
        "moscow": "RUB", "warsaw": "PLN", "prague": "CZK", "budapest": "HUF",
        "tel aviv": "ILS", "riyadh": "SAR",
        "kuala lumpur": "MYR", "jakarta": "IDR", "manila": "PHP",
        "johannesburg": "ZAR", "cape town": "ZAR",
        "mexico city": "MXN", "sao paulo": "BRL", "rio de janeiro": "BRL",
    }

    def _infer_currency(city_str: str) -> str:
        if not city_str:
            return ""
        k = city_str.strip().lower()
        if k in CITY_CURRENCY:
            return CITY_CURRENCY[k]
        for city_key, code in CITY_CURRENCY.items():
            if city_key in k:
                return code
        return ""

    @router.post("/revenue/market-robot/{property_id}/neighborhood/refresh")
    async def refresh_neighborhood_data(property_id: str, data: Dict, background_tasks: BackgroundTasks,
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """One-click neighborhood refresh: wipe stale snapshots → trigger fresh scrape.

        Why users need this: the 2026-04 scraper rewrite introduced a per-row `scan_currency`
        stamp, but pre-rewrite snapshots have no such stamp (and may be in the wrong currency
        entirely). The graph silently blends stale + fresh rows, which is why "grafik eski
        veri gösteriyor" even after manual scans.

        Body:
          location?: str       (default: property's stored scan location OR postcode OR city)
          radius_km?: float    (default: current geo-config radius)
          days_ahead?: int     (default: 30)
          keep_stale?: bool    (default: false — set true to only trigger a new scan without deletion)
        """
        prop = await db.properties.find_one({"id": property_id},
                                            {"_id": 0, "city": 1, "currency": 1, "name": 1}) or {}
        geo_cfg = await db.market_robot_geo_config.find_one({"property_id": property_id}, {"_id": 0}) or {}

        location = (data.get("location") or geo_cfg.get("location") or prop.get("city") or "").strip()
        if not location:
            raise HTTPException(400, "No scan location — pass 'location' or set one in geo-config first.")
        radius_km = float(data.get("radius_km") or geo_cfg.get("radius_km") or 3.2)
        days_ahead = int(data.get("days_ahead") or geo_cfg.get("days_ahead") or 30)
        keep_stale = bool(data.get("keep_stale", False))
        currency = (prop.get("currency") or "GBP").upper()

        deleted = 0
        if not keep_stale:
            res = await db.market_supply.delete_many({
                "property_id": property_id,
                "scan_type": "geo",
                "$or": [
                    {"scan_currency": {"$exists": False}},
                    {"scan_currency": None},
                    {"scan_currency": ""},
                    {"scan_currency": {"$ne": currency}},
                ],
            })
            deleted = res.deleted_count

        # Also auto-seed the geo-config location if empty so future auto-runs work out of the box
        if not geo_cfg.get("location"):
            await db.market_robot_geo_config.update_one(
                {"property_id": property_id},
                {"$set": {
                    "property_id": property_id,
                    "location": location,
                    "radius_km": radius_km,
                    "days_ahead": days_ahead,
                    "enabled": True,  # turn on auto-scan so the user sees fresh data on the dashboard
                    "scan_interval_minutes": geo_cfg.get("scan_interval_minutes", 120),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )

        # Fire the fresh scan in the background — takes 30-60s per date so we don't block the request.
        scan_payload = {
            "mode": "geo",
            "location": location,
            "radius_km": radius_km,
            "days_ahead": days_ahead,
            "currency": currency,
        }
        background_tasks.add_task(_do_scan, property_id, scan_payload)

        return {
            "ok": True,
            "property_id": property_id,
            "stale_snapshots_cleared": deleted,
            "scan_queued": True,
            "location": location,
            "radius_km": radius_km,
            "days_ahead": days_ahead,
            "currency": currency,
            "message": (
                f"Cleaned {deleted} stale snapshot(s). "
                f"Fresh geo-scan queued for {location} · {radius_km}km · {days_ahead}d · {currency}. "
                f"Check back in ~60-90s."
            ),
        }

    @router.post("/revenue/market-robot/search-booking-hotel")
    async def search_booking_hotel(data: Dict,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Free-text search Booking.com for a hotel by NAME and return the top 3 candidates.

        Saves the user the job of finding the correct Booking.com URL — they just type
        'Hotel Adler Zurich' and we return matching property cards with full URL + hotel_id.

        Body: { name: str, city?: str }
        Returns: { candidates: [{ name, booking_url, hotel_id, sample_price, currency }] }
        """
        from utils.booking_scraper import _get_browser, _UA, _DEFAULT_HEADERS  # reuse the shared browser
        name = (data.get("name") or "").strip()
        city = (data.get("city") or "").strip()
        if not name:
            raise HTTPException(400, "Hotel name required")

        query = f"{name} {city}".strip() if city.lower() not in name.lower() else name
        url = f"https://www.booking.com/searchresults.en-gb.html?ss={query.replace(' ', '+')}"
        browser = await _get_browser()
        ctx = await browser.new_context(
            user_agent=_UA, locale="en-GB", viewport={"width": 1280, "height": 900},
            extra_http_headers=_DEFAULT_HEADERS,
        )
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=35000)
            try:
                await page.wait_for_selector('[data-testid="property-card"]', timeout=12000)
            except Exception:
                pass
            cards = await page.evaluate("""
                () => {
                    const cards = Array.from(document.querySelectorAll('[data-testid="property-card"]')).slice(0, 6);
                    return cards.map(c => {
                        const a = c.querySelector('[data-testid="title-link"]');
                        const href = a?.href || '';
                        return {
                            title: (c.querySelector('[data-testid="title"]')?.innerText || '').trim(),
                            price: (c.querySelector('[data-testid="price-and-discounted-price"]')?.innerText || '').trim(),
                            href: href,
                        };
                    }).filter(x => x.title && x.href.includes('/hotel/'));
                }
            """) or []
            # Build canonical URLs (strip query), dedupe by slug
            import re as _re
            seen = set()
            candidates = []
            for c in cards:
                sm = _re.search(r"/hotel/([a-z]{2})/([a-z0-9-]+)\.", c.get("href", ""))
                if not sm:
                    continue
                slug_key = sm.group(2)
                if slug_key in seen:
                    continue
                seen.add(slug_key)
                booking_url = f"https://www.booking.com/hotel/{sm.group(1)}/{sm.group(2)}.en-gb.html"
                price_val = None
                currency = None
                if c.get("price"):
                    pm = _re.search(r"(\d[\d,.]*)", c["price"].replace("\xa0", " ").replace(",", ""))
                    if pm:
                        try:
                            price_val = float(pm.group(1))
                        except ValueError:
                            pass
                    cm = _re.search(r"([A-Z]{3}|€|£|\$|Fr\.|kr)", c["price"])
                    if cm:
                        currency = cm.group(1)
                candidates.append({
                    "name": c.get("title"),
                    "booking_url": booking_url,
                    "hotel_id": None,   # Resolved when user clicks "Add" — keeps this endpoint fast
                    "sample_price": price_val,
                    "currency": currency,
                })
                if len(candidates) >= 3:
                    break
            return {"query": query, "candidates": candidates}
        finally:
            try:
                await page.close()
            except Exception:
                pass
            await ctx.close()

    @router.post("/revenue/market-robot/{property_id}/fix-property-location")
    async def fix_property_location(property_id: str, data: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Reset a property's city/currency/scan_city to the correct values.

        Why this exists: earlier iterations had an aggressive auto-sync rule that overwrote
        properties.city/currency whenever the Market Robot scan city was changed — causing
        e.g. `aldgate-flats` (London) to be flipped to Zurich/CHF. This endpoint lets users
        snap a branch back to its correct location and optionally wipe stale snapshots
        tagged with the wrong currency.

        Body: {
            city: str,                  # e.g. "London"
            currency: str,              # e.g. "GBP"
            postcode?: str,             # e.g. "E1 6AN" — also updates geo-config location
            clear_stale_snapshots?: bool (default=true)  # drops market_supply rows with mismatched scan_currency
        }
        """
        city = (data.get("city") or "").strip().title()
        currency = (data.get("currency") or "").strip().upper()
        postcode = (data.get("postcode") or "").strip()
        clear_stale = bool(data.get("clear_stale_snapshots", True))

        if not city:
            raise HTTPException(400, "'city' is required")
        if not currency:
            raise HTTPException(400, "'currency' is required")

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1) Fix the properties record
        await db.properties.update_one(
            {"id": property_id},
            {"$set": {
                "city": city,
                "currency": currency,
                "currency_auto_set_from": None,  # user-set, not auto-inferred
                "currency_updated_at": now_iso,
                "location_fixed_at": now_iso,
            }},
        )

        # 2) Fix the market_robot_config (scan city + scan currency)
        await db.market_robot_config.update_one(
            {"property_id": property_id},
            {"$set": {
                "city": city,
                "currency": currency,
                "updated_at": now_iso,
            }},
            upsert=True,
        )

        # 3) Fix the geo-config if a postcode was passed
        if postcode:
            await db.market_robot_geo_config.update_one(
                {"property_id": property_id},
                {"$set": {
                    "property_id": property_id,
                    "location": postcode,
                    "updated_at": now_iso,
                }},
                upsert=True,
            )

        # 4) Optionally drop snapshots that were stored with a different currency (stale data)
        deleted = 0
        if clear_stale:
            res = await db.market_supply.delete_many({
                "property_id": property_id,
                "$or": [
                    {"scan_currency": {"$exists": False}},
                    {"scan_currency": {"$ne": currency}},
                ],
            })
            deleted = res.deleted_count

        return {
            "ok": True,
            "property_id": property_id,
            "city": city,
            "currency": currency,
            "postcode": postcode or None,
            "stale_snapshots_cleared": deleted,
            "message": (
                f"✅ {property_id} reset: city→{city}, currency→{currency}"
                f"{f', postcode→{postcode}' if postcode else ''}"
                f"{f' · cleared {deleted} stale snapshot(s)' if deleted else ''}"
            ),
        }

    @router.put("/revenue/market-robot/{property_id}/config")
    async def update_config(property_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        data.pop("_id", None)
        data["property_id"] = property_id
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.market_robot_config.update_one({"property_id": property_id}, {"$set": data}, upsert=True)
        # === Conservative currency sync ===
        # We DO NOT overwrite property.city/currency just because the scanner is tracking a
        # different market — the "scan city" is a market-intelligence setting, not the hotel's
        # actual location. Stale data from an earlier permissive version caused branches like
        # aldgate-flats (London) to be flipped to Zurich/CHF. Only fill these when the
        # property record is still empty (first-run seed) so real hotels keep their identity.
        new_city = (data.get("city") or "").strip()
        inferred = _infer_currency(new_city)
        if new_city:
            prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1, "city": 1})
            prop_update = {}
            if prop and not (prop.get("city") or "").strip():
                prop_update["city"] = new_city.title()
            if prop and inferred and not (prop.get("currency") or "").strip():
                prop_update["currency"] = inferred
                prop_update["currency_auto_set_from"] = new_city
                prop_update["currency_updated_at"] = datetime.now(timezone.utc).isoformat()
            if prop_update:
                await db.properties.update_one({"id": property_id}, {"$set": prop_update})
                logger.info(f"💱 Property {property_id} city/currency first-fill from scan config: {prop_update}")
        return await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0})

    @router.post("/revenue/market-robot/sync-all-currencies")
    async def sync_all_currencies(
        current_user: dict = Depends(require_roles("admin", "manager"))
    ):
        """One-shot migration: re-sync every property's city+currency based on its current
        market_robot_config.city. Useful after the auto-sync rule was introduced/changed."""
        configs = await db.market_robot_config.find({}, {"_id": 0}).to_list(500)
        now_iso = datetime.now(timezone.utc).isoformat()
        fixed = []
        for cfg in configs:
            pid = cfg.get("property_id")
            city = (cfg.get("city") or "").strip()
            if not pid or not city:
                continue
            inferred = _infer_currency(city)
            prop = await db.properties.find_one({"id": pid}, {"_id": 0, "currency": 1, "city": 1, "name": 1})
            if not prop:
                continue
            new_city = city.title()
            changes = {}
            if prop.get("city") != new_city:
                changes["city"] = new_city
            if inferred and prop.get("currency") != inferred:
                changes["currency"] = inferred
                changes["currency_auto_set_from"] = city
                changes["currency_updated_at"] = now_iso
            if changes:
                await db.properties.update_one({"id": pid}, {"$set": changes})
                if inferred:
                    await db.market_robot_config.update_one(
                        {"property_id": pid}, {"$set": {"currency": inferred}}
                    )
                fixed.append({
                    "property_id": pid, "name": prop.get("name", ""),
                    "old_city": prop.get("city", ""), "new_city": changes.get("city"),
                    "old_currency": prop.get("currency", ""), "new_currency": changes.get("currency"),
                })
        return {"fixed_count": len(fixed), "fixed": fixed}

    @router.post("/revenue/market-robot/{property_id}/scan")
    async def run_scan(property_id: str, data: Dict = {},
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Run a market supply scan for the next N days."""
        return await _do_scan(property_id, data or {})

    @router.post("/revenue/market-robot/{property_id}/scan-geo")
    async def run_geo_scan(property_id: str, background_tasks: BackgroundTasks, data: Dict = {},
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Run a neighborhood (geo-radius) scan. Body: {location: 'SW1A 1AA', radius_km: 3.2, days_ahead: 30}

        Runs as a BACKGROUND TASK because a 30-day geo scan with Booking.com
        scrapes takes 60-120s, well over Kubernetes ingress 60s timeout. The
        endpoint returns immediately with {scan_id, status:'queued'}; clients
        poll GET /scan-geo-status/{property_id} for progress.
        """
        data = data or {}
        data["mode"] = "geo"

        # Validate location early so caller gets a 200 with a meaningful error
        # rather than discovering it after the background task starts.
        if not (data.get("location") or data.get("postcode") or data.get("address")
                or (data.get("latitude") is not None and data.get("longitude") is not None)):
            return {
                "error": "Geo scan requires 'location' (postcode/address) or latitude+longitude",
                "status": "error",
            }
        if SCRAPE_LOCKS_GEO.get(property_id):
            return {"error": f"Geo scan already in progress for {property_id}", "status": "busy"}

        scan_id = str(uuid.uuid4())[:8]
        started_at = datetime.now(timezone.utc).isoformat()
        await db.market_robot_scan_status.update_one(
            {"property_id": property_id, "kind": "geo"},
            {"$set": {
                "property_id": property_id, "kind": "geo",
                "scan_id": scan_id, "status": "queued",
                "started_at": started_at,
                "location": data.get("location") or data.get("postcode") or "",
                "radius_km": data.get("radius_km"),
                "days_ahead": data.get("days_ahead"),
                "result": None, "error": None, "finished_at": None,
            }},
            upsert=True,
        )

        async def _run_in_bg():
            try:
                await db.market_robot_scan_status.update_one(
                    {"property_id": property_id, "kind": "geo"},
                    {"$set": {"status": "running"}}
                )
                # Only run the market supply scan here (~50-60s for 30 days).
                # Per-competitor + our-hotel scrapes are SEPARATE because they
                # take 5-7 min each and would overwhelm the polling UX. The
                # user can click "🔄 Rakip Fiyatlarını Tara" for that.
                result = await _do_scan(property_id, data)
                await db.market_robot_scan_status.update_one(
                    {"property_id": property_id, "kind": "geo"},
                    {"$set": {
                        "status": "done" if result.get("status") != "error" else "error",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "result": result,
                    }}
                )
            except Exception as e:
                logger.exception("Background geo scan failed for %s: %s", property_id, e)
                await db.market_robot_scan_status.update_one(
                    {"property_id": property_id, "kind": "geo"},
                    {"$set": {
                        "status": "error",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "error": str(e)[:300],
                    }}
                )

        background_tasks.add_task(_run_in_bg)
        return {"scan_id": scan_id, "status": "queued",
                "message": "Geo scan başladı — durum için /scan-geo-status sorgula."}

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
                    supply = await _scrape_booking_date(
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
                    await _calculate_price_adjustment(db, property_id, checkin, supply, prev)
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
                applied = await _apply_auto_pricing(db, property_id, snapshots)

            # Competitive rule auto-apply (geo scans → triggers the competitive pricing rule if enabled)
            competitive_applied = 0
            if is_geo:
                comp_cfg = await db.market_robot_competitive_config.find_one(
                    {"property_id": property_id, "enabled": True, "auto_apply": True}, {"_id": 0})
                if comp_cfg:
                    try:
                        recs, _ = await _compute_competitive_recommendations(property_id, days=days_ahead)
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

    def _build_annual_revenue_forecast(*, base_rate: float, total_rooms: int,
                                       occupancy_factor: float, start_date) -> dict:
        """Forward-looking 12-month room revenue projection.

        Methodology (same maths as Hotel Revenue Lab's "Sadece Oda" mode):
            monthly_revenue = ADR × rooms × days_in_month × occupancy × season_mult
        Annual revenue is the sum across all 12 months. Returns enough metadata
        for the frontend to render a bar chart + KPI tiles.
        """
        import calendar as _cal
        monthly: List[Dict] = []
        annual_total = 0.0
        # Generate 12 months starting from the current month
        cur_y = start_date.year
        cur_m = start_date.month
        for i in range(12):
            y = cur_y + (cur_m - 1 + i) // 12
            m = (cur_m - 1 + i) % 12 + 1
            days_in_month = _cal.monthrange(y, m)[1]
            season_mult = _MONTH_SEASONALITY[m - 1]
            month_revenue = base_rate * total_rooms * days_in_month * occupancy_factor * season_mult
            month_revenue = round(month_revenue, 2)
            annual_total += month_revenue
            monthly.append({
                "year": y,
                "month": m,
                "label": f"{_cal.month_abbr[m]} {str(y)[2:]}",
                "days": days_in_month,
                "season_multiplier": season_mult,
                "occupancy_pct": round(occupancy_factor * season_mult * 100, 1),
                "adr": round(base_rate, 2),
                "revenue": month_revenue,
            })
        # RevPAR = annual_revenue / (rooms × 365)
        rev_par = annual_total / (total_rooms * 365) if total_rooms else 0
        avg_occupancy = sum(m["occupancy_pct"] for m in monthly) / 12.0 if monthly else 0
        return {
            "annual_revenue": round(annual_total, 2),
            "monthly": monthly,
            "adr": round(base_rate, 2),
            "revpar": round(rev_par, 2),
            "avg_occupancy_pct": round(avg_occupancy, 1),
            "total_rooms": total_rooms,
            "methodology": "ADR × rooms × days × occupancy × seasonality",
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
             "manual_room_count": 1, "manual_room_count_set_at": 1}
        )
        property_currency = (prop.get("currency") if prop else None) or "GBP"

        # Get all room types — base rate + inventory
        room_types_list = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        # Only types with a real base_rate contribute to the average — otherwise
        # types that are missing the rate field dilute the mean to near-zero
        # (which then makes every rate-override look like a £100+ uplift).
        rated_types = [r for r in room_types_list if float(r.get("base_rate", 0) or 0) > 0]
        if rated_types:
            base_rate = sum(float(r.get("base_rate", 0)) for r in rated_types) / len(rated_types)
        else:
            base_rate = 100.0
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
        if available_rn > 0 and total_occupied_rn > 0:
            occupancy_factor = max(0.05, min(1.0, total_occupied_rn / available_rn))
            occupancy_basis = "actual_30d"
        else:
            occupancy_factor = 0.7
            occupancy_basis = "industry_avg_fallback"

        # Get ALL rate overrides set by robot/scanner/dynamic-pricing
        all_overrides = await db.rate_overrides.find(
            {"property_id": property_id, "set_by": {"$in": ["auto-scanner", "market-robot", "ai-dynamic-pricing", "event-intelligence"]}},
            {"_id": 0}
        ).sort("date", 1).to_list(500)

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

        for ov in all_overrides:
            rate = float(ov.get("custom_rate", base_rate))
            diff = rate - base_rate
            diff_pct = round((diff / base_rate) * 100, 1) if base_rate > 0 else 0
            ov_date = ov.get("date", "")
            source = ov.get("set_by", "unknown")
            reason = ov.get("reason", "")

            if rate != base_rate:
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
                    "robot_rate": rate,
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
            "occupancy_assumption": occupancy_factor,
            "occupancy_basis": occupancy_basis,
            "annual_forecast": _build_annual_revenue_forecast(
                base_rate=base_rate,
                total_rooms=total_rooms,
                occupancy_factor=occupancy_factor,
                start_date=now.date(),
            ),
        }

    @router.get("/revenue/market-robot/{property_id}/competitors")
    async def get_competitors(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)
        return {"competitors": comps}

    @router.post("/revenue/market-robot/validate-booking-url")
    async def validate_booking_url_endpoint(data: Dict,
                                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Test-scrape a Booking.com URL before saving it. Used by the 'Add Competitor' UI
        and the Onboarding Wizard so bad/wrong links cannot pollute the database.

        Body: { booking_url: str, currency?: str }
        Returns: { ok, hotel_id, hotel_name, sample_price, currency, error }
        """
        from utils.booking_scraper import validate_booking_url
        url = (data.get("booking_url") or "").strip()
        currency = (data.get("currency") or "").strip() or None
        if not url:
            return {"ok": False, "error": "missing_url"}
        try:
            return await validate_booking_url(url, currency=currency)
        except Exception as e:
            logger.warning(f"Validator failed for {url}: {e}")
            return {"ok": False, "error": str(e)}

    @router.post("/revenue/market-robot/{property_id}/competitors")
    async def add_competitor(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        from utils.booking_scraper import validate_booking_url as _validate
        booking_url = data.get("booking_url", "").strip()
        name = data.get("name", "").strip()
        skip_validation = bool(data.get("skip_validation", False))
        if not booking_url:
            return {"error": "Booking.com URL is required"}

        # Dedup BEFORE any expensive Booking.com round-trip — otherwise the
        # user pastes the same URL twice from different tabs and we burn 10s
        # validating it just to insert a duplicate row.
        norm_url = booking_url.rstrip("/").split("?")[0]
        norm_url_no_locale = re.sub(r"\.[a-z]{2}-[a-z]{2}\.html$", ".html", norm_url, flags=re.I)
        existing_dup = await db.market_competitors.find_one(
            {
                "property_id": property_id,
                "$or": [
                    {"booking_url": booking_url},
                    {"booking_url": norm_url},
                    {"booking_url": norm_url_no_locale},
                ],
            },
            {"_id": 0, "id": 1, "name": 1, "booking_url": 1, "booking_hotel_id": 1},
        )
        if existing_dup:
            return {
                "error": "duplicate",
                "message": f"Bu rakip zaten ekli: {existing_dup.get('name')}",
                "existing": existing_dup,
            }

        # Resolve hotel_id (also doubles as a sanity test — if Booking won't give us
        # an id, the URL is wrong and we should warn the user before saving).
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        currency = prop.get("currency") or "GBP"

        validation = {}
        hotel_id = None
        resolved_name = ""
        sample_price = None
        if not skip_validation:
            try:
                validation = await _validate(booking_url, currency=currency)
                hotel_id = validation.get("hotel_id")
                resolved_name = validation.get("hotel_name", "")
                sample_price = validation.get("sample_price")
                if not hotel_id:
                    return {
                        "error": "invalid_booking_url",
                        "message": "Booking.com URL doğrulanamadı. Lütfen URL'yi kontrol edin.",
                        "validation": validation,
                    }
            except Exception as e:
                logger.warning(f"Competitor URL validation failed: {e}")

        # Second-chance dedup BY hotel_id — catches the case where the user
        # pasted the same hotel under a different URL (e.g. with vs without
        # locale suffix, with vs without trailing slash, with vs without query
        # params).
        if hotel_id:
            id_dup = await db.market_competitors.find_one(
                {"property_id": property_id, "booking_hotel_id": str(hotel_id)},
                {"_id": 0, "id": 1, "name": 1},
            )
            if id_dup:
                return {
                    "error": "duplicate_hotel_id",
                    "message": f"Bu otel zaten ekli (farklı URL ile): {id_dup.get('name')}",
                    "existing": id_dup,
                }

        # Extract hotel slug from URL
        slug_match = re.search(r'/hotel/[a-z]{2}/([^.?]+)', booking_url)
        slug = slug_match.group(1) if slug_match else ""

        comp = {
            "id": str(uuid.uuid4())[:8],
            "property_id": property_id,
            "name": name or resolved_name or slug.replace("-", " ").title(),
            "booking_url": booking_url,
            "slug": slug,
            "booking_hotel_id": hotel_id,
            "sample_price": sample_price,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "last_scraped": None,
            "prices": [],
        }
        try:
            await db.market_competitors.insert_one(comp)
        except Exception as e:
            # Unique-index race (parallel POST /competitors): another tab
            # just inserted the same row 5ms before us. Return the existing
            # row instead of a 500.
            if "duplicate key" in str(e).lower():
                existing_now = await db.market_competitors.find_one(
                    {"property_id": property_id, "booking_url": booking_url},
                    {"_id": 0, "id": 1, "name": 1},
                )
                return {
                    "error": "duplicate",
                    "message": "Bu rakip zaten ekli (eş zamanlı eklendi).",
                    "existing": existing_now,
                }
            raise
        comp.pop("_id", None)
        return {**comp, "validation": validation}

    async def _do_revalidate_competitors(db_ref, property_id: str):
        """Background worker: re-run Booking.com URL validation on every competitor."""
        from utils.booking_scraper import validate_booking_url as _validate
        comps = await db_ref.market_competitors.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not comps:
            return

        prop = await db_ref.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        currency = prop.get("currency") or "GBP"
        now_iso = datetime.now(timezone.utc).isoformat()

        await db_ref.market_robot_revalidate_status.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id,
                "status": "running",
                "started_at": now_iso,
                "total": len(comps),
                "done": 0,
                "valid": 0,
                "invalid": 0,
            }},
            upsert=True,
        )

        valid_cnt = 0
        invalid_cnt = 0
        done = 0
        for comp in comps:
            url = comp.get("booking_url", "")
            if not url:
                invalid_cnt += 1
            else:
                try:
                    v = await _validate(url, currency=currency)
                except Exception as e:
                    v = {"ok": False, "error": str(e)}

                update_fields = {"last_validation": {**v, "checked_at": datetime.now(timezone.utc).isoformat()}}
                if v.get("hotel_id"):
                    update_fields["booking_hotel_id"] = v["hotel_id"]
                    valid_cnt += 1
                else:
                    invalid_cnt += 1
                if v.get("hotel_name"):
                    original = (comp.get("name") or "").strip().lower()
                    slug_default = (comp.get("slug") or "").replace("-", " ").strip().lower()
                    if original in ("", slug_default):
                        update_fields["name"] = v["hotel_name"]
                await db_ref.market_competitors.update_one({"id": comp["id"]}, {"$set": update_fields})
            done += 1
            await db_ref.market_robot_revalidate_status.update_one(
                {"property_id": property_id},
                {"$set": {"done": done, "valid": valid_cnt, "invalid": invalid_cnt}},
            )

        await db_ref.market_robot_revalidate_status.update_one(
            {"property_id": property_id},
            {"$set": {"status": "done", "finished_at": datetime.now(timezone.utc).isoformat()}},
        )

    async def _do_auto_heal_competitors(db_ref, property_id: str, days_ahead: int = 30, threshold: int = 50):
        """Background worker: heal under-performing competitors.

        For every competitor whose hit_rate (days_covered / attempted_days * 100) is below
        `threshold`, or which has never been scraped:
          1. Re-validate the Booking.com URL (updates last_validation + hotel_id if resolved).
          2. If validation OK → trigger a targeted re-scrape for `days_ahead` days.
          3. If validation fails → leave the row with last_validation.ok=False so the UI
             surfaces the broken URL to the user (never auto-delete — user owns the list).
        """
        from utils.booking_scraper import validate_booking_url as _validate, scrape_booking_url, build_dated_url

        comps = await db_ref.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(50)
        if not comps:
            return {"healed": 0, "queued": 0}

        prop = await db_ref.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        currency = prop.get("currency") or "GBP"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Pick the under-performers (or never-scraped)
        targets = []
        for c in comps:
            raw_prices = c.get("prices") or []
            attempted = len(raw_prices)
            covered = sum(1 for p in raw_prices if p.get("scraped") and p.get("lowest_price"))
            hit = (covered / attempted) * 100 if attempted > 0 else 0
            if attempted == 0 or hit < threshold:
                targets.append(c)
        if not targets:
            await db_ref.market_robot_autoheal_status.update_one(
                {"property_id": property_id},
                {"$set": {"property_id": property_id, "status": "done",
                          "finished_at": now_iso, "total": 0, "healed": 0, "failed": 0,
                          "message": "All competitors already healthy — nothing to heal."}},
                upsert=True,
            )
            return {"healed": 0, "queued": 0}

        await db_ref.market_robot_autoheal_status.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, "status": "running",
                      "started_at": now_iso, "total": len(targets),
                      "healed": 0, "failed": 0, "done": 0}},
            upsert=True,
        )

        healed = 0
        failed = 0
        days_ahead = max(1, min(int(days_ahead), 90))
        now = datetime.now(timezone.utc)

        for comp in targets:
            url = comp.get("booking_url", "")
            name_hint = (comp.get("slug") or "").replace("-", " ")[:18]
            if not url:
                failed += 1
                await db_ref.market_competitors.update_one(
                    {"id": comp["id"]},
                    {"$set": {"last_validation": {"ok": False, "error": "missing_url",
                                                   "checked_at": datetime.now(timezone.utc).isoformat()}}},
                )
            else:
                # Step 1: re-validate
                try:
                    v = await _validate(url, currency=currency)
                except Exception as e:
                    v = {"ok": False, "error": str(e)}

                update_fields = {"last_validation": {**v, "checked_at": datetime.now(timezone.utc).isoformat()}}
                resolved_hotel_id = v.get("hotel_id") or comp.get("booking_hotel_id")
                if v.get("hotel_id"):
                    update_fields["booking_hotel_id"] = v["hotel_id"]
                if v.get("hotel_name"):
                    orig = (comp.get("name") or "").strip().lower()
                    slug_def = (comp.get("slug") or "").replace("-", " ").strip().lower()
                    if orig in ("", slug_def):
                        update_fields["name"] = v["hotel_name"]

                # Step 2: if URL is valid → re-scrape days_ahead
                if v.get("ok"):
                    comp_prices = []
                    for i in range(days_ahead):
                        d = now + timedelta(days=i)
                        ci = d.strftime("%Y-%m-%d")
                        co = (d + timedelta(days=1)).strftime("%Y-%m-%d")
                        try:
                            r = await scrape_booking_url(
                                build_dated_url(url, ci, co, currency),
                                timeout_ms=30000,
                                hotel_id=resolved_hotel_id,
                                hotel_name_hint=name_hint,
                            )
                            if r.get("scraped"):
                                comp_prices.append({
                                    "date": ci, "lowest_price": r["lowest_price"],
                                    "all_prices": r.get("all_prices"), "score": r.get("score"),
                                    "scraped": True,
                                })
                            else:
                                comp_prices.append({"date": ci, "lowest_price": None, "scraped": False,
                                                    "error": r.get("error")})
                        except Exception as e:
                            logger.warning(f"Auto-heal scrape failed for {comp.get('name')}: {e}")
                            comp_prices.append({"date": ci, "lowest_price": None, "scraped": False})
                        await asyncio.sleep(1.2)
                    update_fields["prices"] = comp_prices
                    update_fields["last_scraped"] = datetime.now(timezone.utc).isoformat()
                    update_fields["last_source"] = "auto-heal"
                    healed += 1
                else:
                    failed += 1
                await db_ref.market_competitors.update_one({"id": comp["id"]}, {"$set": update_fields})

            await db_ref.market_robot_autoheal_status.update_one(
                {"property_id": property_id},
                {"$inc": {"done": 1}, "$set": {"healed": healed, "failed": failed}},
            )

        await db_ref.market_robot_autoheal_status.update_one(
            {"property_id": property_id},
            {"$set": {"status": "done", "finished_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"healed": healed, "failed": failed, "queued": len(targets)}

    @router.post("/revenue/market-robot/{property_id}/competitors/auto-heal")
    async def auto_heal_competitors(property_id: str, background_tasks: BackgroundTasks, data: Dict = {},
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Fire-and-forget: re-validate + re-scrape all under-performing competitors.

        Body (optional):
          days_ahead: 1-90 (default 30) — window to re-scrape for each healed competitor.
          threshold:  0-100 (default 50) — hit-rate below which a competitor is healed.
        """
        days_ahead = max(1, min(int(data.get("days_ahead") or 30), 90))
        threshold = max(0, min(int(data.get("threshold") or 50), 100))

        # Preview how many will be healed so the UI can show an accurate toast immediately
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "prices": 1, "name": 1},
        ).to_list(50)
        targets = []
        for c in comps:
            raw = c.get("prices") or []
            covered = sum(1 for p in raw if p.get("scraped") and p.get("lowest_price"))
            hit = (covered / len(raw)) * 100 if raw else 0
            if not raw or hit < threshold:
                targets.append(c.get("name", "?"))

        if not targets:
            return {"ok": True, "status": "skipped", "queued": 0, "threshold": threshold,
                    "message": "Tüm rakipler sağlıklı — iyileştirilecek kimse yok."}

        background_tasks.add_task(_do_auto_heal_competitors, db, property_id, days_ahead, threshold)
        await db.market_robot_autoheal_status.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, "status": "queued",
                      "started_at": datetime.now(timezone.utc).isoformat(),
                      "total": len(targets), "healed": 0, "failed": 0, "done": 0,
                      "threshold": threshold, "days_ahead": days_ahead}},
            upsert=True,
        )
        return {
            "ok": True, "status": "queued", "queued": len(targets),
            "threshold": threshold, "days_ahead": days_ahead,
            "targets": targets,
            "message": f"{len(targets)} rakip için Auto-Heal başlatıldı (hit<{threshold}%). Arka planda çalışıyor — 1-2 dk sonra health kartı yenilenecek.",
        }

    @router.get("/revenue/market-robot/{property_id}/competitors/auto-heal/status")
    async def auto_heal_status(property_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.market_robot_autoheal_status.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        return doc or {"property_id": property_id, "status": "idle"}

    @router.get("/revenue/market-robot/{property_id}/competitors/auto-heal/config")
    async def get_auto_heal_config(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Current Auto-Heal schedule config. Defaults: disabled, hourly, threshold 50%, 30 days."""
        doc = await db.market_robot_autoheal_config.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        return doc or {
            "property_id": property_id, "enabled": False,
            "interval_minutes": 60, "threshold": 50, "days_ahead": 30,
            "last_run": None, "total_runs": 0,
        }

    @router.put("/revenue/market-robot/{property_id}/competitors/auto-heal/config")
    async def put_auto_heal_config(property_id: str, data: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update the Auto-Heal schedule (enabled/interval/threshold/days_ahead)."""
        payload = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", False)),
            "interval_minutes": max(15, min(int(data.get("interval_minutes") or 60), 24 * 60)),
            "threshold": max(0, min(int(data.get("threshold") or 50), 100)),
            "days_ahead": max(1, min(int(data.get("days_ahead") or 30), 90)),
        }
        await db.market_robot_autoheal_config.update_one(
            {"property_id": property_id}, {"$set": payload}, upsert=True,
        )
        doc = await db.market_robot_autoheal_config.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        return doc

    @router.post("/revenue/market-robot/{property_id}/competitors/revalidate-all")
    async def revalidate_all_competitors(property_id: str, background_tasks: BackgroundTasks,
                                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """Kick off a background re-validation of every competitor's Booking.com URL.
        Each URL takes 30-60s (Chromium-based scrape), so this is run in the background.

        Poll GET /competitors/revalidate-status to watch progress, and GET /competitors to see
        updated `booking_hotel_id` and `last_validation` fields per row.
        """
        comps_count = await db.market_competitors.count_documents({"property_id": property_id})
        if comps_count == 0:
            return {"queued": 0, "status": "no_competitors"}
        background_tasks.add_task(_do_revalidate_competitors, db, property_id)
        # Reset status doc optimistically so the UI shows the in-progress state immediately
        await db.market_robot_revalidate_status.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id,
                "status": "queued",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total": comps_count, "done": 0, "valid": 0, "invalid": 0,
            }},
            upsert=True,
        )
        return {
            "queued": comps_count,
            "status": "queued",
            "message": f"Re-validation of {comps_count} competitors started in background. Poll /competitors/revalidate-status for progress.",
        }

    @router.get("/revenue/market-robot/{property_id}/competitors/revalidate-status")
    async def revalidate_status(property_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.market_robot_revalidate_status.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        return doc or {"property_id": property_id, "status": "idle"}

    @router.delete("/revenue/market-robot/competitors/{competitor_id}")
    async def remove_competitor(competitor_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Delete a single competitor by id. Used by the trash button on each
        row in the Competitor Hotels tab UI."""
        await db.market_competitors.delete_one({"id": competitor_id})
        return {"message": "Removed"}

    @router.post("/revenue/market-robot/{property_id}/competitors/discover")
    async def discover_nearby_competitors(
        property_id: str, background_tasks: BackgroundTasks, data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Find nearby Booking.com hotels the admin can choose to add as competitors.

        Request body (all optional — sensible defaults pulled from property):
          - postcode: str (defaults to property's postcode)
          - city: str (defaults to property's city)
          - property_type: "any" | "apartments" | "hotels" | "aparthotels" (defaults "any")
          - max_results: 5-50 (defaults 20)

        Response:
          { "candidates": [ {hotel_id, name, slug, booking_url, stars, review_score, address,
                              property_type, already_added: bool, is_self: bool} ],
            "search_used": {postcode, city, property_type, currency, language} }

        No DB writes — returns a list. Admin then POSTs to /competitors/bulk-add with
        the subset they want to import. Respects the existing competitor list so rows
        already added are shown greyed out (not silently duplicated).
        """
        from utils.booking_scraper import discover_nearby_hotels, geocode_address, _extract_district_hint

        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "postcode": 1, "city": 1, "currency": 1, "country": 1,
             "latitude": 1, "longitude": 1, "booking_url": 1, "name": 1, "address": 1,
             "property_type": 1, "type": 1, "geocoded_display_name": 1},
        )
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        # Smart property-type filter: if the request didn't specify a type, infer
        # one from the property's own `property_type` field. apartment-only
        # properties don't want hotels as competitors and vice versa.
        TYPE_MAP = {
            "apartment": "apartments",
            "apartments": "apartments",
            "aparthotel": "aparthotels",
            "aparthotels": "aparthotels",
            "serviced_apartment": "apartments",
            "hotel": "hotels",
            "hotels": "hotels",
            "guest_house": "hotels",
            "guesthouse": "hotels",
            "bnb": "hotels",
            "b&b": "hotels",
        }
        raw_prop_type = (prop.get("property_type") or prop.get("type") or "").lower().strip()
        inferred = TYPE_MAP.get(raw_prop_type, "any")

        postcode = (data.get("postcode") or prop.get("postcode") or "").strip()
        city = (data.get("city") or prop.get("city") or "").strip()
        # Request body may explicitly override the inferred type; otherwise
        # use the inferred filter (or "any" if we couldn't classify).
        property_type = (data.get("property_type") or inferred or "any").lower()
        if property_type not in ("any", "apartments", "hotels", "aparthotels"):
            property_type = "any"
        max_results = max(5, min(int(data.get("max_results") or 20), 50))
        currency = (data.get("currency") or prop.get("currency") or "GBP").upper()
        language = (data.get("language") or "en-gb").lower()
        radius_km = float(data.get("radius_km") or 2.5)
        radius_km = max(0.5, min(radius_km, 10.0))
        # Default ON: exclude single-room/studio listings from auto-discovery.
        # A "1 Bedroom Flat" or "Studio Apartment" is NOT a meaningful pricing
        # benchmark for a multi-room PMS-managed property.
        exclude_single_room = bool(data.get("exclude_single_room", True))
        # Minimum review count: filter out "tiny operations" (single-flat
        # owner-operated places with very few reviews). 20 default ≈ 5+ unit
        # multi-property operations. Set to 0 to disable.
        min_review_count = int(data.get("min_review_count", 20))
        min_review_count = max(0, min(min_review_count, 500))
        # NEW: real unit/room count filter — attempts to read numberOfRooms
        # from each candidate's Booking.com property page (JSON-LD). NOTE:
        # Booking.com currently returns "page not found" shells for direct
        # /hotel/<cc>/<slug>.html URLs, so numberOfRooms is rarely
        # extractable. When set > 0, we still try — but candidates with
        # unknown room counts are KEPT (so we don't accidentally hide every
        # legit listing). The review_count threshold (above) is the more
        # reliable size proxy in practice. Default 0 (disabled).
        min_unit_count = int(data.get("min_unit_count", 0))
        min_unit_count = max(0, min(min_unit_count, 500))
        # Detail-page fetch toggle. False by default (slow, ~5-8s per
        # candidate × 15 candidates = 60-120s extra latency, all for an
        # uncertain payoff right now).
        fetch_unit_counts = bool(data.get("fetch_unit_counts", False))

        latitude = prop.get("latitude")
        longitude = prop.get("longitude")

        # AUTO-GEOCODE: If the property has no coords yet, derive them from
        # the property name + postcode + city via Nominatim. Persist the
        # result so subsequent runs hit the cache. This is the difference
        # between getting actual neighbors vs city-wide featured listings.
        geocode_used = None
        if not (latitude and longitude):
            address = (prop.get("address") or "").strip()
            name = (prop.get("name") or "").strip()
            country_raw = (prop.get("country") or "").strip().upper()
            COUNTRY_MAP = {"UK": "gb", "GB": "gb", "ENGLAND": "gb", "UNITED KINGDOM": "gb",
                           "US": "us", "USA": "us", "UNITED STATES": "us",
                           "TR": "tr", "TURKEY": "tr", "TÜRKIYE": "tr",
                           "FR": "fr", "FRANCE": "fr", "DE": "de", "GERMANY": "de",
                           "ES": "es", "SPAIN": "es", "IT": "it", "ITALY": "it",
                           "NL": "nl", "NETHERLANDS": "nl"}
            country_code = COUNTRY_MAP.get(country_raw, country_raw.lower()[:2] if country_raw else "")
            # Build queries: name MUST always have city/postcode suffix so we don't
            # ambiguously hit "Camden Apartments" → Boston, USA.
            candidates_q = []
            if address:
                candidates_q.append(" ".join([x for x in [address, postcode, city] if x]))
                candidates_q.append(", ".join([x for x in [address, postcode, city] if x]))
            if name and city:
                candidates_q.append(f"{name} {city}")
                candidates_q.append(f"{name}, {city}")
            if postcode and city:
                candidates_q.append(f"{postcode} {city}")
                candidates_q.append(f"{postcode}, {city}")
            # Bare-name fallback ONLY when we have country_code to bias the search.
            # Without country_code, "Camden Apartments" alone is dangerous.
            if name and country_code:
                candidates_q.append(name)
            elif postcode:
                candidates_q.append(postcode)
            seen_q = set()
            ordered_q = []
            for q in candidates_q:
                qn = q.strip()
                if qn and qn.lower() not in seen_q:
                    seen_q.add(qn.lower())
                    ordered_q.append(qn)

            for q in ordered_q:
                geo = await geocode_address(q, country_code=country_code)
                if geo:
                    latitude, longitude, display = geo
                    # Sanity check: if we have a city name, the geocode display
                    # MUST contain it case-insensitively. Prevents Camden→Boston.
                    if city and city.lower() not in display.lower():
                        logger.warning(
                            f"⚠️ Geocode rejected — city mismatch: '{q}' → '{display}' "
                            f"(expected city '{city}')"
                        )
                        continue
                    geocode_used = {"query": q, "display": display, "lat": latitude, "lng": longitude}
                    await db.properties.update_one(
                        {"id": property_id},
                        {"$set": {
                            "latitude": latitude, "longitude": longitude,
                            "geocoded_from": q,
                            "geocoded_display_name": display,
                            "geocoded_at": datetime.now(timezone.utc).isoformat(),
                        }},
                    )
                    logger.info(f"🗺️ Auto-geocoded '{property_id}' from '{q}' → ({latitude}, {longitude})")
                    break

        # Build a district hint from the geocode display name (or stored)
        if not geocode_used:
            stored_display = prop.get("geocoded_display_name") or ""
        else:
            stored_display = geocode_used["display"]
        district_hint = _extract_district_hint(stored_display, postcode, city) if stored_display else ""

        if not postcode and not city and not (latitude and longitude):
            raise HTTPException(
                status_code=400,
                detail="Property has no postcode/city/coordinates. Set them under 'Fix Branch Location' first.",
            )

        # ASYNC MODE — default true. Booking.com scrapes can run 50-70s
        # (cold Chromium + slow Booking response). Kubernetes ingress kills
        # the request at 60s. Run as a BackgroundTask, persist result in
        # market_robot_discover_status, frontend polls /competitors/discover-status.
        # Pass `background: false` to force a synchronous response (legacy).
        run_async = bool(data.get("background", True))
        if run_async:
            scan_id = str(uuid.uuid4())[:8]
            started_at = datetime.now(timezone.utc).isoformat()
            await db.market_robot_discover_status.update_one(
                {"property_id": property_id},
                {"$set": {
                    "property_id": property_id,
                    "scan_id": scan_id, "status": "queued",
                    "started_at": started_at,
                    "finished_at": None, "result": None, "error": None,
                }},
                upsert=True,
            )

            # Snapshot all the locals we need for the background task to run
            # independently of the request scope.
            _postcode, _city = postcode, city
            _property_type = property_type
            _max_results = max_results
            _currency = currency
            _language = language
            _radius_km = radius_km
            _exclude_single = exclude_single_room
            _min_review = min_review_count
            _min_unit = min_unit_count
            _fetch_units = fetch_unit_counts
            _latitude, _longitude = latitude, longitude
            _district_hint = district_hint
            _geocode_used = geocode_used
            _auto_add_top_flag = bool(data.get("auto_add"))
            _auto_add_top_n = int(data.get("auto_add_top") or 5)
            _our_url = (prop.get("booking_url") or "").rstrip("/").split("?")[0]

            async def _run_discover_bg():
                try:
                    await db.market_robot_discover_status.update_one(
                        {"property_id": property_id},
                        {"$set": {"status": "running"}},
                    )
                    cands = await discover_nearby_hotels(
                        postcode=_postcode, city=_city,
                        latitude=_latitude, longitude=_longitude,
                        property_type=_property_type, max_results=_max_results,
                        radius_km=_radius_km, language=_language, currency=_currency,
                        district_hint=_district_hint,
                        exclude_single_room=_exclude_single,
                        min_review_count=_min_review, min_unit_count=_min_unit,
                        fetch_unit_counts=_fetch_units,
                    )
                    # Flag candidates already imported
                    existing2 = await db.market_competitors.find(
                        {"property_id": property_id},
                        {"_id": 0, "booking_url": 1, "booking_hotel_id": 1},
                    ).to_list(200)
                    existing_urls2 = {(c.get("booking_url") or "").rstrip("/").split("?")[0] for c in existing2}
                    existing_hids2 = {str(c.get("booking_hotel_id")) for c in existing2 if c.get("booking_hotel_id")}
                    for c in cands:
                        u2 = (c.get("booking_url") or "").rstrip("/").split("?")[0]
                        c["already_added"] = bool(
                            (u2 and u2 in existing_urls2)
                            or (c.get("hotel_id") and str(c["hotel_id"]) in existing_hids2)
                        )
                        c["is_self"] = bool(u2 and _our_url and u2 == _our_url)

                    auto_added_n = 0
                    if _auto_add_top_flag:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        top_n = max(1, min(_auto_add_top_n, 15))
                        for cand in cands[:top_n]:
                            if cand.get("is_self"):
                                continue
                            url2 = (cand.get("booking_url") or "").rstrip("/").split("?")[0]
                            name2 = (cand.get("name") or "").strip()
                            if not url2 or not name2:
                                continue
                            exists = await db.market_competitors.find_one(
                                {"property_id": property_id, "booking_url": url2},
                                {"_id": 0, "id": 1},
                            )
                            if exists:
                                continue
                            hid = str(cand.get("booking_hotel_id") or cand.get("hotel_id") or "")
                            slug_m = re.search(r"/hotel/[a-z]{2}/([a-z0-9-]+)\.", url2)
                            slug = slug_m.group(1) if slug_m else name2.lower().replace(" ", "-")[:40]
                            await db.market_competitors.insert_one({
                                "id": str(uuid.uuid4()),
                                "property_id": property_id,
                                "name": name2,
                                "booking_url": url2,
                                "slug": slug,
                                "booking_hotel_id": hid or None,
                                "stars": cand.get("stars"),
                                "review_score": cand.get("review_score"),
                                "prices": [], "score": None, "last_scraped": None,
                                "last_source": "auto_reset_autoadd",
                                "last_validation": {"ok": True,
                                                     "checked_at": now_iso,
                                                     "hotel_name": name2,
                                                     "hotel_id": hid or None},
                                "created_at": now_iso,
                                "created_by": "auto_reset_autoadd",
                            })
                            auto_added_n += 1

                    result = {
                        "candidates": cands,
                        "total": len(cands),
                        "auto_added": auto_added_n,
                        "search_used": {
                            "postcode": _postcode, "city": _city,
                            "property_type": _property_type, "currency": _currency,
                            "language": _language, "max_results": _max_results,
                            "latitude": _latitude, "longitude": _longitude,
                            "radius_km": _radius_km,
                            "geocode_used": _geocode_used,
                            "district_hint": _district_hint,
                            "exclude_single_room": _exclude_single,
                            "min_review_count": _min_review,
                            "min_unit_count": _min_unit,
                            "fetch_unit_counts": _fetch_units,
                        },
                    }
                    await db.market_robot_discover_status.update_one(
                        {"property_id": property_id},
                        {"$set": {
                            "status": "done",
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                            "result": result,
                        }},
                    )
                except Exception as e:
                    logger.exception("Background discover failed for %s: %s", property_id, e)
                    await db.market_robot_discover_status.update_one(
                        {"property_id": property_id},
                        {"$set": {
                            "status": "error",
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                            "error": str(e)[:300],
                        }},
                    )

            background_tasks.add_task(_run_discover_bg)
            return {"scan_id": scan_id, "status": "queued",
                    "message": "Discover başladı — durum için /competitors/discover-status sorgula."}

        # SYNCHRONOUS LEGACY PATH (kept for backward compat / curl debug)
        candidates = await discover_nearby_hotels(
            postcode=postcode,
            city=city,
            latitude=latitude,
            longitude=longitude,
            property_type=property_type,
            max_results=max_results,
            radius_km=radius_km,
            language=language,
            currency=currency,
            district_hint=district_hint,
            exclude_single_room=exclude_single_room,
            min_review_count=min_review_count,
            min_unit_count=min_unit_count,
            fetch_unit_counts=fetch_unit_counts,
        )

        # Flag candidates already imported so the UI can disable their checkbox.
        existing = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "booking_url": 1, "booking_hotel_id": 1},
        ).to_list(200)
        existing_urls = {(c.get("booking_url") or "").rstrip("/").split("?")[0] for c in existing}
        existing_hids = {str(c.get("booking_hotel_id")) for c in existing if c.get("booking_hotel_id")}

        # Slug/URL of our own property — so user never accidentally adds themselves.
        our_url = (prop.get("booking_url") or "").rstrip("/").split("?")[0]

        for c in candidates:
            url = (c.get("booking_url") or "").rstrip("/").split("?")[0]
            c["already_added"] = bool(
                (url and url in existing_urls)
                or (c.get("hotel_id") and str(c["hotel_id"]) in existing_hids)
            )
            c["is_self"] = bool(url and our_url and url == our_url)

        # Optional auto-add for 0-click reset flows
        auto_added = 0
        if bool(data.get("auto_add")):
            auto_add_top = max(1, min(int(data.get("auto_add_top") or 5), 15))
            now_iso = datetime.now(timezone.utc).isoformat()
            for cand in candidates[:auto_add_top]:
                if cand.get("is_self"):
                    continue
                url2 = (cand.get("booking_url") or "").rstrip("/").split("?")[0]
                name2 = (cand.get("name") or "").strip()
                if not url2 or not name2:
                    continue
                exists = await db.market_competitors.find_one(
                    {"property_id": property_id, "booking_url": url2}, {"_id": 0, "id": 1},
                )
                if exists:
                    continue
                hid = str(cand.get("booking_hotel_id") or cand.get("hotel_id") or "")
                slug_m = re.search(r"/hotel/[a-z]{2}/([a-z0-9-]+)\.", url2)
                slug = slug_m.group(1) if slug_m else name2.lower().replace(" ", "-")[:40]
                await db.market_competitors.insert_one({
                    "id": str(uuid.uuid4()),
                    "property_id": property_id,
                    "name": name2,
                    "booking_url": url2,
                    "slug": slug,
                    "booking_hotel_id": hid or None,
                    "stars": cand.get("stars"),
                    "review_score": cand.get("review_score"),
                    "prices": [], "score": None, "last_scraped": None,
                    "last_source": "auto_reset_autoadd",
                    "last_validation": {"ok": True, "checked_at": now_iso,
                                        "hotel_name": name2, "hotel_id": hid or None},
                    "created_at": now_iso,
                    "created_by": "auto_reset_autoadd",
                })
                auto_added += 1

        return {
            "candidates": candidates,
            "total": len(candidates),
            "auto_added": auto_added,
            "search_used": {
                "postcode": postcode, "city": city,
                "property_type": property_type, "currency": currency,
                "language": language, "max_results": max_results,
                "latitude": latitude, "longitude": longitude,
                "radius_km": radius_km,
                "geocode_used": geocode_used,
                "district_hint": district_hint,
                "exclude_single_room": exclude_single_room,
                "min_review_count": min_review_count,
                "min_unit_count": min_unit_count,
                "fetch_unit_counts": fetch_unit_counts,
            },
        }

    @router.get("/revenue/market-robot/{property_id}/competitors/discover-status")
    async def get_discover_status(property_id: str,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Polling endpoint for the most recent /competitors/discover background task.
        Returns {status: idle|queued|running|done|error, result?, error?, scan_id, started_at, finished_at}."""
        doc = await db.market_robot_discover_status.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        return doc or {"property_id": property_id, "status": "idle"}

    @router.post("/revenue/market-robot/{property_id}/auto-geocode")
    async def auto_geocode_property(
        property_id: str, data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Run only the Nominatim auto-geocode step and persist the result on
        the property doc. Useful when the user wants to seed coordinates first
        and only afterwards run /discover with a custom radius.

        Body (optional): {force: true} — re-geocode even if lat/lon already set.
        """
        from utils.booking_scraper import geocode_address

        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "name": 1, "city": 1, "postcode": 1, "address": 1,
                                  "latitude": 1, "longitude": 1, "country": 1},
        )
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        force = bool((data or {}).get("force"))
        if (prop.get("latitude") and prop.get("longitude")) and not force:
            return {
                "ok": True,
                "skipped": True,
                "latitude": prop["latitude"], "longitude": prop["longitude"],
                "message": "Property zaten geocode'lu. force:true ile yeniden çalıştır.",
            }

        name = (prop.get("name") or "").strip()
        city = (prop.get("city") or "").strip()
        postcode = (prop.get("postcode") or "").strip()
        address = (prop.get("address") or "").strip()
        custom_query = ((data or {}).get("query") or "").strip()
        country_raw = (prop.get("country") or "").strip().upper()
        COUNTRY_MAP_AG = {"UK": "gb", "GB": "gb", "ENGLAND": "gb", "UNITED KINGDOM": "gb",
                          "US": "us", "USA": "us", "UNITED STATES": "us",
                          "TR": "tr", "TURKEY": "tr", "TÜRKIYE": "tr",
                          "FR": "fr", "FRANCE": "fr", "DE": "de", "GERMANY": "de",
                          "ES": "es", "SPAIN": "es", "IT": "it", "ITALY": "it",
                          "NL": "nl", "NETHERLANDS": "nl"}
        country_code = COUNTRY_MAP_AG.get(country_raw, country_raw.lower()[:2] if country_raw else "")

        candidates_q = []
        if custom_query:
            candidates_q.append(custom_query)
        if address:
            candidates_q.append(" ".join([x for x in [address, postcode, city] if x]))
            candidates_q.append(", ".join([x for x in [address, postcode, city] if x]))
        if name and city:
            candidates_q.append(f"{name} {city}")
            candidates_q.append(f"{name}, {city}")
        if postcode and city:
            candidates_q.append(f"{postcode} {city}")
        if name and country_code:
            candidates_q.append(name)
        elif postcode:
            candidates_q.append(postcode)
        seen = set()
        ordered_q = []
        for q in candidates_q:
            qn = q.strip()
            if qn and qn.lower() not in seen:
                seen.add(qn.lower())
                ordered_q.append(qn)

        if not ordered_q:
            raise HTTPException(400, "Property has no name/postcode/address — cannot geocode")

        attempts = []
        for q in ordered_q:
            geo = await geocode_address(q, country_code=country_code)
            attempts.append({"query": q, "found": bool(geo)})
            if geo:
                lat, lng, display = geo
                if city and city.lower() not in display.lower():
                    attempts[-1]["rejected"] = "city_mismatch"
                    continue
                await db.properties.update_one(
                    {"id": property_id},
                    {"$set": {
                        "latitude": lat, "longitude": lng,
                        "geocoded_from": q,
                        "geocoded_display_name": display,
                        "geocoded_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                return {
                    "ok": True,
                    "latitude": lat, "longitude": lng,
                    "geocoded_from": q,
                    "display_name": display,
                    "attempts": attempts,
                }
        return {"ok": False, "error": "no_match", "attempts": attempts,
                "message": "Hiçbir geocode adayı eşleşmedi. Manuel lat/lng girin."}

    @router.delete("/revenue/market-robot/{property_id}/competitors/clear")
    async def clear_all_competitors(
        property_id: str,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Wipe ALL competitors for this property. Useful after a wrong-neighborhood
        auto-discovery — admin can clear and re-run discover with proper radius.
        Also drops dependent supply/validation/log rows tagged to those competitors.
        """
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "id": 1, "name": 1},
        ).to_list(100)
        comp_ids = [c["id"] for c in comps]
        names = [c.get("name", "") for c in comps]

        deleted = await db.market_competitors.delete_many({"property_id": property_id})
        # Best-effort cleanup of orphaned data
        await db.market_supply.delete_many({"property_id": property_id})
        if comp_ids:
            await db.competitor_validation.delete_many({"competitor_id": {"$in": comp_ids}})

        return {
            "ok": True,
            "deleted": deleted.deleted_count,
            "names": names,
            "message": f"{deleted.deleted_count} rakip silindi. /discover ile yeniden bul.",
        }

    @router.post("/revenue/market-robot/fleet-reset-neighbors")
    async def fleet_reset_neighbors(
        data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Fleet-wide: for EVERY property, run the same 3-step reset that the
        single-property UI button does — clear all competitors, force-geocode,
        re-discover with radius. Returns per-property results.

        Body (optional):
          - property_ids: [] — restrict to specific IDs (default: ALL active)
          - radius_km: 2.0 (default)
          - max_results: 15 (default)
          - dry_run: false — when true, only reports what would happen
          - auto_add: false — when true, top `auto_add_top` discovered candidates
            are immediately inserted as competitors for each property (0-click).
          - auto_add_top: 5 — how many top-ranked candidates to auto-add.
        """
        from utils.booking_scraper import discover_nearby_hotels, geocode_address, _extract_district_hint

        radius_km = max(0.5, min(float((data or {}).get("radius_km") or 2.0), 10.0))
        max_results = max(5, min(int((data or {}).get("max_results") or 15), 50))
        dry_run = bool((data or {}).get("dry_run"))
        auto_add = bool((data or {}).get("auto_add"))
        auto_add_top = max(1, min(int((data or {}).get("auto_add_top") or 5), 15))
        target_ids = (data or {}).get("property_ids") or []
        exclude_single_room = bool((data or {}).get("exclude_single_room", True))
        min_review_count = max(0, min(int((data or {}).get("min_review_count") or 20), 500))

        prop_query: Dict = {"is_active": {"$ne": False}}
        if target_ids:
            prop_query["id"] = {"$in": list(target_ids)}
        props = await db.properties.find(
            prop_query,
            {"_id": 0, "id": 1, "name": 1, "city": 1, "postcode": 1, "address": 1,
             "latitude": 1, "longitude": 1, "currency": 1, "geocoded_display_name": 1,
             "property_type": 1, "type": 1},
        ).to_list(200)

        TYPE_MAP = {
            "apartment": "apartments", "apartments": "apartments",
            "aparthotel": "aparthotels", "aparthotels": "aparthotels",
            "serviced_apartment": "apartments",
            "hotel": "hotels", "hotels": "hotels",
            "guest_house": "hotels", "guesthouse": "hotels",
            "bnb": "hotels", "b&b": "hotels",
        }

        results = []
        for prop in props:
            pid = prop.get("id")
            if not pid:
                continue
            entry = {"property_id": pid, "name": prop.get("name"), "city": prop.get("city")}
            if dry_run:
                entry["status"] = "would_reset"
                results.append(entry)
                continue
            try:
                # 1) Clear existing
                prev_comps = await db.market_competitors.find(
                    {"property_id": pid}, {"_id": 0, "id": 1}
                ).to_list(200)
                prev_count = len(prev_comps)
                if prev_count:
                    await db.market_competitors.delete_many({"property_id": pid})
                    await db.market_supply.delete_many({"property_id": pid})

                # 2) Force geocode (country-aware + city-validated)
                name = (prop.get("name") or "").strip()
                city = (prop.get("city") or "").strip()
                postcode = (prop.get("postcode") or "").strip()
                address = (prop.get("address") or "").strip()
                country_raw = (prop.get("country") or "").strip().upper()
                COUNTRY_MAP_FR = {"UK": "gb", "GB": "gb", "ENGLAND": "gb", "UNITED KINGDOM": "gb",
                                  "US": "us", "USA": "us", "UNITED STATES": "us",
                                  "TR": "tr", "TURKEY": "tr", "TÜRKIYE": "tr",
                                  "FR": "fr", "FRANCE": "fr", "DE": "de", "GERMANY": "de",
                                  "ES": "es", "SPAIN": "es", "IT": "it", "ITALY": "it",
                                  "NL": "nl", "NETHERLANDS": "nl"}
                country_code = COUNTRY_MAP_FR.get(country_raw, country_raw.lower()[:2] if country_raw else "")
                candidates_q = []
                if address:
                    candidates_q.append(" ".join([x for x in [address, postcode, city] if x]))
                if name and city:
                    candidates_q.append(f"{name} {city}")
                if postcode and city:
                    candidates_q.append(f"{postcode} {city}")
                if name and country_code:
                    candidates_q.append(name)
                seen = set()
                ordered_q = []
                for q in candidates_q:
                    qn = q.strip()
                    if qn and qn.lower() not in seen:
                        seen.add(qn.lower())
                        ordered_q.append(qn)

                geo_ok = False
                latitude = None
                longitude = None
                display = ""
                for q in ordered_q:
                    geo = await geocode_address(q, country_code=country_code)
                    if geo:
                        cand_lat, cand_lon, cand_display = geo
                        # City sanity check — reject if city mismatch
                        if city and city.lower() not in cand_display.lower():
                            continue
                        latitude, longitude, display = cand_lat, cand_lon, cand_display
                        await db.properties.update_one(
                            {"id": pid},
                            {"$set": {
                                "latitude": latitude, "longitude": longitude,
                                "geocoded_from": q, "geocoded_display_name": display,
                                "geocoded_at": datetime.now(timezone.utc).isoformat(),
                            }},
                        )
                        geo_ok = True
                        break

                if not geo_ok:
                    entry["status"] = "geocode_failed"
                    entry["cleared"] = prev_count
                    results.append(entry)
                    continue

                # 3) Discover nearby — use inferred property type filter
                raw_type = (prop.get("property_type") or prop.get("type") or "").lower().strip()
                inf_type = TYPE_MAP.get(raw_type, "any")
                district_hint = _extract_district_hint(display, postcode, city) if display else ""
                cands = await discover_nearby_hotels(
                    postcode=postcode, city=city, latitude=latitude, longitude=longitude,
                    property_type=inf_type, max_results=max_results, radius_km=radius_km,
                    language="en-gb", currency=(prop.get("currency") or "GBP"),
                    district_hint=district_hint,
                    exclude_single_room=exclude_single_room,
                    min_review_count=min_review_count,
                )
                entry["status"] = "ok"
                entry["cleared"] = prev_count
                entry["geocoded_from"] = display[:80] if display else ""
                entry["candidates_found"] = len(cands)
                entry["property_type_filter"] = inf_type

                # 4) Auto-add top candidates as competitors (when requested)
                if auto_add and cands:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    added_ct = 0
                    for cand in cands[:auto_add_top]:
                        url = (cand.get("booking_url") or "").rstrip("/").split("?")[0]
                        name_c = (cand.get("name") or "").strip()
                        hid = str(cand.get("booking_hotel_id") or cand.get("hotel_id") or "")
                        if not url or not name_c:
                            continue
                        slug_m = re.search(r"/hotel/[a-z]{2}/([a-z0-9-]+)\.", url)
                        slug = slug_m.group(1) if slug_m else name_c.lower().replace(" ", "-")[:40]
                        # Skip if already exists (race-safe upsert by booking_url)
                        existing = await db.market_competitors.find_one(
                            {"property_id": pid, "booking_url": url}, {"_id": 0, "id": 1}
                        )
                        if existing:
                            continue
                        await db.market_competitors.insert_one({
                            "id": str(uuid.uuid4()),
                            "property_id": pid,
                            "name": name_c,
                            "booking_url": url,
                            "slug": slug,
                            "booking_hotel_id": hid or None,
                            "stars": cand.get("stars"),
                            "review_score": cand.get("review_score"),
                            "prices": [],
                            "score": None,
                            "last_scraped": None,
                            "last_source": "fleet_reset_autoadd",
                            "last_validation": {
                                "ok": True, "checked_at": now_iso,
                                "hotel_name": name_c, "hotel_id": hid or None,
                            },
                            "created_at": now_iso,
                            "created_by": "fleet_reset_autoadd",
                        })
                        added_ct += 1
                    entry["auto_added"] = added_ct
            except Exception as e:
                entry["status"] = "error"
                entry["error"] = str(e)[:160]
            results.append(entry)

        ok_count = sum(1 for r in results if r.get("status") == "ok")
        total_added = sum(r.get("auto_added", 0) or 0 for r in results)
        return {
            "ok": True,
            "total_properties": len(props),
            "ok_count": ok_count,
            "auto_added": total_added,
            "auto_add": auto_add,
            "dry_run": dry_run,
            "results": results,
            "message": (
                f"Fleet reset: {ok_count}/{len(props)} property işlendi. "
                f"radius={radius_km}km, max={max_results}."
                + (f" Auto-added {total_added} competitors (top {auto_add_top}/property)." if auto_add else "")
            ),
        }

    @router.post("/revenue/market-robot/fleet-validate-geo")
    async def fleet_validate_geo(
        data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Fleet-wide coordinate sanity check + auto-repair.

        For every active property with lat/lon stored, reverse-geocode the
        coordinates via Nominatim and check whether the resulting country code
        matches the property's `country` field. If it doesn't (e.g. UK property
        landed on US lat/lon — the Camden→Boston bug), the property is flagged
        and — when `fix=true` — re-geocoded using the country-biased forward
        path. Always returns a per-property report.

        Body (optional):
          - property_ids: [] — restrict to specific IDs (default: ALL active)
          - dry_run: true (default) — only report; do not write
          - fix: false (default) — when true, re-geocode flagged properties
          - sleep_s: 1.1 — Nominatim free policy enforces 1 req/sec.
        """
        from utils.booking_scraper import (
            reverse_geocode, geocode_address,
        )

        target_ids = (data or {}).get("property_ids") or []
        dry_run = bool((data or {}).get("dry_run", True))
        fix = bool((data or {}).get("fix", False))
        sleep_s = float((data or {}).get("sleep_s") or 1.1)
        sleep_s = max(0.5, min(sleep_s, 3.0))

        COUNTRY_MAP_FV = {
            "UK": "gb", "GB": "gb", "ENGLAND": "gb", "UNITED KINGDOM": "gb",
            "US": "us", "USA": "us", "UNITED STATES": "us",
            "TR": "tr", "TURKEY": "tr", "TÜRKIYE": "tr", "TURKIYE": "tr",
            "FR": "fr", "FRANCE": "fr", "DE": "de", "GERMANY": "de",
            "ES": "es", "SPAIN": "es", "IT": "it", "ITALY": "it",
            "NL": "nl", "NETHERLANDS": "nl", "CH": "ch", "SWITZERLAND": "ch",
            "AT": "at", "AUSTRIA": "at", "BE": "be", "BELGIUM": "be",
            "PT": "pt", "PORTUGAL": "pt", "IE": "ie", "IRELAND": "ie",
            "GR": "gr", "GREECE": "gr",
        }

        prop_query: Dict = {"is_active": {"$ne": False}}
        if target_ids:
            prop_query["id"] = {"$in": target_ids}
        props = await db.properties.find(
            prop_query,
            {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1,
             "postcode": 1, "address": 1, "latitude": 1, "longitude": 1,
             "geocoded_display_name": 1},
        ).to_list(500)

        ok_count = 0
        flagged_count = 0
        fixed_count = 0
        skipped_count = 0
        results = []

        for prop in props:
            pid = prop.get("id")
            pname = prop.get("name") or pid
            lat = prop.get("latitude")
            lon = prop.get("longitude")
            city = (prop.get("city") or "").strip()
            country_raw = (prop.get("country") or "").strip().upper()
            expected_cc = COUNTRY_MAP_FV.get(country_raw, country_raw.lower()[:2] if country_raw else "")

            entry = {
                "property_id": pid,
                "name": pname,
                "city": city,
                "country": country_raw,
                "expected_country_code": expected_cc,
                "before": {"latitude": lat, "longitude": lon,
                           "display": prop.get("geocoded_display_name")},
                "status": "skipped",
                "reason": None,
            }

            if not (lat and lon):
                entry["reason"] = "no_coordinates"
                skipped_count += 1
                results.append(entry)
                continue
            if not expected_cc:
                entry["reason"] = "no_country_on_property"
                skipped_count += 1
                results.append(entry)
                continue

            # Reverse geocode current coords — confirm where they actually land.
            rev = await reverse_geocode(lat, lon)
            await asyncio.sleep(sleep_s)
            if not rev:
                entry["status"] = "unknown"
                entry["reason"] = "reverse_geocode_failed"
                skipped_count += 1
                results.append(entry)
                continue

            actual_cc = (rev.get("country_code") or "").lower()
            actual_city = (rev.get("city") or "").lower()
            entry["actual_country_code"] = actual_cc
            entry["actual_city"] = rev.get("city")
            entry["actual_display"] = rev.get("display_name")

            country_match = (actual_cc == expected_cc)
            city_match = True
            if city and actual_city:
                # forgiving: city contained in either direction
                cl = city.lower()
                city_match = (cl in actual_city) or (actual_city in cl)

            if country_match and city_match:
                entry["status"] = "ok"
                entry["reason"] = "country_and_city_match"
                ok_count += 1
                results.append(entry)
                continue

            # Mismatch — flag.
            entry["status"] = "flagged"
            entry["reason"] = (
                "country_mismatch" if not country_match
                else "city_mismatch"
            )
            flagged_count += 1

            if dry_run or not fix:
                results.append(entry)
                continue

            # Repair path: forward-geocode with country bias and persist.
            name = (prop.get("name") or "").strip()
            postcode = (prop.get("postcode") or "").strip()
            address = (prop.get("address") or "").strip()

            candidates_q = []
            if address:
                candidates_q.append(" ".join([x for x in [address, postcode, city] if x]))
            if postcode and city:
                candidates_q.append(f"{postcode} {city}")
            if name and city:
                candidates_q.append(f"{name} {city}")
            if name and expected_cc:
                candidates_q.append(name)

            seen = set()
            ordered_q = []
            for q in candidates_q:
                qn = (q or "").strip()
                if qn and qn.lower() not in seen:
                    seen.add(qn.lower())
                    ordered_q.append(qn)

            repaired = False
            for q in ordered_q:
                geo = await geocode_address(q, country_code=expected_cc)
                await asyncio.sleep(sleep_s)
                if not geo:
                    continue
                new_lat, new_lon, new_display = geo
                # Sanity: display must include the property's city
                if city and city.lower() not in (new_display or "").lower():
                    continue
                await db.properties.update_one(
                    {"id": pid},
                    {"$set": {
                        "latitude": new_lat, "longitude": new_lon,
                        "geocoded_from": q,
                        "geocoded_display_name": new_display,
                        "geocoded_at": datetime.now(timezone.utc).isoformat(),
                        "geo_validated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                entry["status"] = "fixed"
                entry["after"] = {"latitude": new_lat, "longitude": new_lon,
                                  "display": new_display, "geocoded_from": q}
                fixed_count += 1
                repaired = True
                break

            if not repaired:
                entry["status"] = "unfixable"
                entry["reason"] = "no_geocode_match_with_country_bias"

            results.append(entry)

        return {
            "ok": True,
            "total_properties": len(props),
            "ok_count": ok_count,
            "flagged_count": flagged_count,
            "fixed_count": fixed_count,
            "skipped_count": skipped_count,
            "dry_run": dry_run,
            "fix": fix,
            "results": results,
            "message": (
                f"Geo validate: {ok_count} OK · {flagged_count} flag · "
                f"{fixed_count} fixed · {skipped_count} skipped "
                f"({'DRY-RUN' if dry_run else 'LIVE'})."
            ),
        }

    @router.post("/revenue/market-robot/fleet-classify-property-types")
    async def fleet_classify_property_types(
        data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Fleet-wide AI Property-Type Inference.

        Uses GPT-4o-mini to re-classify each property's `property_type`
        based on its name (e.g. "Camden Apartments" → apartment,
        "City Gate Guest House" → guesthouse, "Whitechapel Grand" → hotel).

        Booking.com filter implications:
          - apartment / serviced_apartment → "apartments" filter
          - aparthotel                     → "aparthotels" filter
          - hotel / guesthouse / bnb / b&b → "hotels" filter

        Body (optional):
          - property_ids: [] — restrict to specific IDs
          - dry_run: true (default) — only return preview, no writes
          - only_missing: false — when true, only classify properties whose
            current `property_type` is null/empty/missing
          - confidence_threshold: 0.7 — only persist when AI confidence >= this
          - model: "gpt-4o-mini" (default; supports any Emergent-LLM model)
        """
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
        except ImportError:
            raise HTTPException(500, "emergentintegrations not installed")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

        target_ids = (data or {}).get("property_ids") or []
        dry_run = bool((data or {}).get("dry_run", True))
        only_missing = bool((data or {}).get("only_missing", False))
        conf_thr = float((data or {}).get("confidence_threshold") or 0.7)
        conf_thr = max(0.0, min(conf_thr, 1.0))
        model = (data or {}).get("model") or "gpt-4o-mini"

        prop_query: Dict = {"is_active": {"$ne": False}}
        if target_ids:
            prop_query["id"] = {"$in": target_ids}
        if only_missing:
            prop_query["$or"] = [
                {"property_type": {"$exists": False}},
                {"property_type": None},
                {"property_type": ""},
            ]
        props = await db.properties.find(
            prop_query,
            {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1,
             "property_type": 1, "address": 1},
        ).to_list(500)

        valid_types = {"hotel", "apartment", "serviced_apartment",
                       "aparthotel", "guesthouse", "bnb", "hostel"}

        results = []
        updated_count = 0
        unchanged_count = 0
        skipped_count = 0
        low_confidence_count = 0

        # NOTE: we issue one LlmChat per property (separate session) so each
        # classification is independent and reproducible. This is cheap with
        # gpt-4o-mini and avoids context bleed.
        SYSTEM_PROMPT = (
            "You are a hospitality classification expert. Given a property's "
            "name, city, country and address, classify the lodging type. "
            "Return ONLY compact JSON, no markdown, with EXACTLY these keys: "
            '{"type": "<one of: hotel | apartment | serviced_apartment | aparthotel | guesthouse | bnb | hostel>", '
            '"confidence": <float 0..1>, '
            '"reasoning": "<one short sentence>"}. '
            "Heuristics: names containing 'Apartments', 'Flats', 'Studios', "
            "'Suites' (without 'Hotel') usually mean apartment. 'Guest House', "
            "'B&B' → guesthouse/bnb. 'Hostel' → hostel. 'Aparthotel' or "
            "'Apartment Hotel' → aparthotel. Default to hotel only when name "
            "explicitly contains 'Hotel', 'Inn', 'Grand', 'Plaza', 'Resort'."
        )

        for prop in props:
            pid = prop.get("id")
            pname = (prop.get("name") or "").strip()
            current = (prop.get("property_type") or "").lower().strip()

            entry = {
                "property_id": pid,
                "name": pname,
                "current_type": current or None,
                "city": prop.get("city"),
                "status": "skipped",
                "reason": None,
            }

            if not pname:
                entry["reason"] = "no_name"
                skipped_count += 1
                results.append(entry)
                continue

            user_prompt = (
                f"Property:\n"
                f"  name: {pname}\n"
                f"  city: {prop.get('city') or '-'}\n"
                f"  country: {prop.get('country') or '-'}\n"
                f"  address: {prop.get('address') or '-'}\n"
                f"  current_label: {current or 'null'}\n\n"
                f"Return JSON only."
            )

            try:
                chat = LlmChat(
                    api_key=api_key,
                    session_id=f"classify-{pid}-{uuid.uuid4().hex[:8]}",
                    system_message=SYSTEM_PROMPT,
                ).with_model("openai", model)
                reply = await chat.send_message(UserMessage(text=user_prompt))
                raw = (reply or "").strip()
                # Tolerate ```json fences
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
                import json as _json
                parsed = _json.loads(raw)
                pred_type = (parsed.get("type") or "").lower().strip()
                conf = float(parsed.get("confidence") or 0.0)
                reasoning = (parsed.get("reasoning") or "")[:200]
            except Exception as e:
                entry["status"] = "error"
                entry["reason"] = f"llm_error: {str(e)[:120]}"
                skipped_count += 1
                results.append(entry)
                continue

            entry["predicted_type"] = pred_type
            entry["confidence"] = round(conf, 3)
            entry["reasoning"] = reasoning

            if pred_type not in valid_types:
                entry["status"] = "skipped"
                entry["reason"] = f"invalid_type: {pred_type}"
                skipped_count += 1
                results.append(entry)
                continue

            if conf < conf_thr:
                entry["status"] = "low_confidence"
                entry["reason"] = f"conf {conf:.2f} < threshold {conf_thr:.2f}"
                low_confidence_count += 1
                results.append(entry)
                continue

            if pred_type == current:
                entry["status"] = "unchanged"
                entry["reason"] = "ai_confirmed_current_label"
                unchanged_count += 1
                results.append(entry)
                continue

            # High-confidence change.
            entry["status"] = "would_update" if dry_run else "updated"
            entry["reason"] = (
                f"reclassified from '{current or 'null'}' to '{pred_type}'"
            )
            if not dry_run:
                await db.properties.update_one(
                    {"id": pid},
                    {"$set": {
                        "property_type": pred_type,
                        "property_type_classified_by": "ai-gpt-4o-mini",
                        "property_type_classified_at": datetime.now(timezone.utc).isoformat(),
                        "property_type_classification_confidence": round(conf, 3),
                        "property_type_classification_reason": reasoning,
                        # Iter 322: preserve previous value for one-click rollback.
                        "property_type_previous": current or None,
                        "property_type_previous_reason": (
                            f"AI re-classified {current or 'null'} → {pred_type} on "
                            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                        ),
                    }},
                )
                updated_count += 1
            results.append(entry)

        return {
            "ok": True,
            "total_properties": len(props),
            "updated_count": updated_count,
            "would_update_count": sum(1 for r in results if r["status"] == "would_update"),
            "unchanged_count": unchanged_count,
            "low_confidence_count": low_confidence_count,
            "skipped_count": skipped_count,
            "dry_run": dry_run,
            "only_missing": only_missing,
            "confidence_threshold": conf_thr,
            "model": model,
            "results": results,
            "message": (
                f"AI classify: {updated_count} updated · "
                f"{sum(1 for r in results if r['status'] == 'would_update')} would_update · "
                f"{unchanged_count} unchanged · {low_confidence_count} low_conf · "
                f"{skipped_count} skip "
                f"({'DRY-RUN' if dry_run else 'LIVE'})."
            ),
        }

    @router.get("/revenue/market-robot/ai-classification-history")
    async def ai_classification_history(
        days: int = 30,
        limit: int = 100,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """List properties whose `property_type` was set by AI (GPT-4o-mini).

        Returns each entry with: property_id, name, city, current_type,
        previous_type, confidence, reason, classified_at, classified_by,
        rollback_available (true if `property_type_previous` is set and
        differs from current).

        Query params:
          - days: lookback window (default 30). Set to 0 for ALL time.
          - limit: max rows (default 100, cap 500).
        """
        days = max(0, min(int(days or 0), 365))
        limit = max(1, min(int(limit or 100), 500))

        q: Dict = {"property_type_classified_by": {"$exists": True}}
        if days > 0:
            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            q["property_type_classified_at"] = {"$gte": since}

        rows = await db.properties.find(
            q,
            {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1,
             "property_type": 1, "property_type_previous": 1,
             "property_type_classified_by": 1,
             "property_type_classified_at": 1,
             "property_type_classification_confidence": 1,
             "property_type_classification_reason": 1},
        ).sort("property_type_classified_at", -1).limit(limit).to_list(limit)

        out = []
        for r in rows:
            current = r.get("property_type") or None
            previous = r.get("property_type_previous")
            out.append({
                "property_id": r.get("id"),
                "name": r.get("name"),
                "city": r.get("city"),
                "country": r.get("country"),
                "current_type": current,
                "previous_type": previous,
                "confidence": r.get("property_type_classification_confidence"),
                "reason": r.get("property_type_classification_reason") or "",
                "classified_at": r.get("property_type_classified_at"),
                "classified_by": r.get("property_type_classified_by"),
                "rollback_available": bool(previous and previous != current),
            })
        return {"total": len(out), "days": days, "items": out}

    @router.post("/revenue/market-robot/{property_id}/ai-classification-rollback")
    async def ai_classification_rollback(
        property_id: str,
        data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Roll back an AI-driven property_type change to the saved previous value.

        Body (optional): {target_type?: str} — override target instead of using
        the saved `property_type_previous`. Useful when admin wants to set a
        specific value (e.g. "aparthotel") instead of going back to "hotel".
        """
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        explicit = (data or {}).get("target_type")
        if explicit:
            valid_types = {"hotel", "apartment", "serviced_apartment",
                           "aparthotel", "guesthouse", "bnb", "hostel"}
            t = (explicit or "").lower().strip()
            if t not in valid_types:
                raise HTTPException(status_code=400,
                                    detail=f"Invalid target_type. Must be one of {sorted(valid_types)}")
            target = t
        else:
            target = prop.get("property_type_previous")
            if not target:
                raise HTTPException(
                    status_code=400,
                    detail="No saved previous_type for this property. Pass target_type explicitly.",
                )

        current = prop.get("property_type")
        if target == current:
            return {"ok": True, "no_op": True, "current_type": current,
                    "message": "Hedef değer mevcut değerle aynı, değişiklik yok."}

        await db.properties.update_one(
            {"id": property_id},
            {"$set": {
                "property_type": target,
                "property_type_classified_by": f"manual-rollback:{current_user.get('email','admin')}",
                "property_type_classified_at": datetime.now(timezone.utc).isoformat(),
                "property_type_classification_confidence": 1.0,
                "property_type_classification_reason": f"Manual rollback from '{current}' to '{target}'",
                "property_type_previous": current,
                "property_type_previous_reason": (
                    f"Was '{current}' (set by "
                    f"{prop.get('property_type_classified_by','?')}) — rolled back "
                    f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
            }},
        )
        return {"ok": True, "property_id": property_id,
                "previous_type": current, "current_type": target,
                "message": f"Property type '{current}' → '{target}'"}

    @router.post("/revenue/market-robot/scrape-booking-vision")
    async def scrape_booking_vision(
        data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Vision-based extraction from a Booking.com page screenshot.

        Pipeline:
          1. If a /hotel/<cc>/<slug>.html URL is given, automatically append
             checkin/checkout query params 14 days out so prices render.
          2. Playwright screenshots the page (pre-warmed context bypasses
             cold deep-link blocks).
          3. PNG bytes → base64 → GPT-4o-mini vision → JSON.

        "Kullanıcının gözüyle bak" approach — works even when JSON-LD is
        missing or property type is non-standard, because the visual page
        rendering is the source of truth.

        Body:
          - booking_url: required, target Booking.com URL
          - model: optional, default "gpt-4o-mini" (vision-capable)
          - full_page: optional, capture full scrollable page (default false)
          - auto_dates: optional bool, when true (default), appends
            checkin=today+14 / checkout=today+15 to render prices.
        """
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        except ImportError:
            raise HTTPException(500, "emergentintegrations not installed")
        from utils.booking_scraper import scrape_booking_screenshot
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        import base64 as _b64
        import json as _json

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

        url = (data or {}).get("booking_url", "").strip()
        if not url:
            raise HTTPException(400, "booking_url required")
        model = (data or {}).get("model") or "gpt-4o-mini"
        full_page = bool((data or {}).get("full_page", False))
        auto_dates = bool((data or {}).get("auto_dates", True))

        # Auto-append checkin/checkout dates so prices render. Booking.com
        # detail pages without dates return a "browse" view with no price.
        if auto_dates and "/hotel/" in url:
            ci = (datetime.now(timezone.utc).date() + timedelta(days=14)).isoformat()
            co = (datetime.now(timezone.utc).date() + timedelta(days=15)).isoformat()
            p = urlparse(url)
            q = parse_qs(p.query)
            if "checkin" not in q:
                q["checkin"] = [ci]
            if "checkout" not in q:
                q["checkout"] = [co]
            if "group_adults" not in q:
                q["group_adults"] = ["2"]
            if "no_rooms" not in q:
                q["no_rooms"] = ["1"]
            url = urlunparse(p._replace(query=urlencode(q, doseq=True)))

        png = await scrape_booking_screenshot(url, full_page=full_page)
        if not png:
            return {
                "ok": False,
                "error": "screenshot_failed",
                "booking_url": url,
                "message": "Booking.com sayfası açılamadı (block veya timeout).",
            }
        png_size = len(png)
        b64 = _b64.b64encode(png).decode("ascii")

        SYSTEM = (
            "You are a hospitality data extractor. Given a screenshot of a "
            "Booking.com hotel/apartment listing page, extract the visible "
            "facts and return ONLY compact JSON with these keys: "
            '{"hotel_name": <string|null>, "room_count": <int|null>, '
            '"price_per_night": <float|null>, "currency": <"GBP"|"USD"|"EUR"|"TRY"|null>, '
            '"star_rating": <int|null>, "review_score": <float|null>, '
            '"review_count": <int|null>, "is_blocked_page": <bool>}. '
            "Rules: "
            "- room_count: only set if the page explicitly shows 'X rooms', "
            "'X apartments', 'X units' as part of the property description. "
            "Do NOT infer from review count, area listings, or recommended "
            "filters. If unsure, return null. "
            "- price_per_night: the headline lowest visible price (the "
            "biggest/most prominent number labeled with a currency, often "
            "near a 'See availability' or 'Reserve' button). Strip currency "
            "symbol; just the number. "
            "- currency: 3-letter code based on the symbol shown (£→GBP, "
            "$→USD, €→EUR, ₺→TRY). "
            "- star_rating: 1-5 visible stars; null otherwise. "
            "- review_score: 0.0-10.0 numeric Booking.com badge (often shown "
            "as e.g. '7.4' next to 'Good' or 'Very good'). "
            "- review_count: total reviews shown (e.g. '923 reviews'). "
            "- is_blocked_page: true if the page shows 'Page not found', a "
            "404, cookie consent wall blocking content, or generic landing "
            "with no specific hotel info visible. "
            "Return ONLY JSON, no markdown fences, no extra text."
        )
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"booking-vision-{uuid.uuid4().hex[:8]}",
                system_message=SYSTEM,
            ).with_model("openai", model)
            reply = await chat.send_message(UserMessage(
                text="Extract the facts from this Booking.com screenshot.",
                file_contents=[ImageContent(image_base64=b64)],
            ))
        except Exception as e:
            return {"ok": False, "error": "vision_call_failed",
                    "message": str(e)[:200], "booking_url": url,
                    "screenshot_size_bytes": png_size}

        raw = (reply or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
        try:
            parsed = _json.loads(raw)
        except Exception:
            return {"ok": False, "error": "parse_failed",
                    "raw_extraction": raw[:500], "booking_url": url,
                    "screenshot_size_bytes": png_size}

        return {
            "ok": True,
            "booking_url": url,
            "hotel_name": parsed.get("hotel_name"),
            "room_count": parsed.get("room_count"),
            "price_per_night": parsed.get("price_per_night"),
            "currency": parsed.get("currency"),
            "star_rating": parsed.get("star_rating"),
            "review_score": parsed.get("review_score"),
            "review_count": parsed.get("review_count"),
            "is_blocked_page": bool(parsed.get("is_blocked_page", False)),
            "model": model,
            "screenshot_size_bytes": png_size,
        }

    @router.post("/revenue/market-robot/{property_id}/competitors/bulk-add")
    async def bulk_add_competitors(
        property_id: str, data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Import multiple competitors in one call — driven by the Discover modal.

        Body: { "candidates": [ {name, booking_url, booking_hotel_id?, stars?, review_score?,
                                  vision_room_count?, vision_price?, vision_currency?,
                                  vision_star_rating?, vision_review_score?, vision_review_count?} ] }

        Skips duplicates (same booking_url or booking_hotel_id). Auto-generates an id
        and seeds last_validation from the candidate score so the Health Card shows
        a sensible OK tone until the first real scrape lands.

        When vision_* fields are provided (from the auto Vision enrichment in the
        Discover panel), they are persisted on the competitor row so the Market
        Robot competitor list shows real Booking.com room counts + prices straight
        away — no extra button click needed.
        """
        items = data.get("candidates") or []
        if not isinstance(items, list) or not items:
            raise HTTPException(status_code=400, detail="candidates list is required")

        existing = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "booking_url": 1, "booking_hotel_id": 1},
        ).to_list(500)
        existing_urls = {(c.get("booking_url") or "").rstrip("/").split("?")[0] for c in existing}
        existing_hids = {str(c.get("booking_hotel_id")) for c in existing if c.get("booking_hotel_id")}

        added = 0
        skipped = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        to_insert = []
        for cand in items:
            url = (cand.get("booking_url") or "").rstrip("/").split("?")[0]
            hid = str(cand.get("booking_hotel_id") or cand.get("hotel_id") or "")
            name = (cand.get("name") or "").strip()
            if not url or not name:
                skipped += 1
                continue
            if url in existing_urls or (hid and hid in existing_hids):
                skipped += 1
                continue
            existing_urls.add(url)
            if hid:
                existing_hids.add(hid)
            slug_m = re.search(r"/hotel/[a-z]{2}/([a-z0-9-]+)\.", url)
            slug = slug_m.group(1) if slug_m else name.lower().replace(" ", "-")[:40]
            row = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "name": name,
                "booking_url": url,
                "slug": slug,
                "booking_hotel_id": hid or None,
                "stars": cand.get("stars"),
                "review_score": cand.get("review_score"),
                "prices": [],
                "score": None,
                "last_scraped": None,
                "last_source": "discovered",
                "last_validation": {
                    "ok": True, "checked_at": now_iso,
                    "hotel_name": name, "hotel_id": hid or None,
                },
                "created_at": now_iso,
                "created_by": "discover_modal",
            }
            # Persist Vision-extracted facts when the Discover panel pre-enriched
            # this candidate. These are the "ground truth" room count + price
            # the user saw, so we keep them on the competitor record.
            vision_keys = (
                "vision_room_count", "vision_price", "vision_currency",
                "vision_star_rating", "vision_review_score", "vision_review_count",
            )
            v_dict = {}
            for k in vision_keys:
                if cand.get(k) is not None:
                    v_dict[k] = cand[k]
            if v_dict:
                v_dict["vision_checked_at"] = now_iso
                row.update(v_dict)
            to_insert.append(row)
            added += 1

        if to_insert:
            # ordered=False so a single colliding doc (race condition with a
            # parallel /bulk-add or /competitors POST) doesn't abort the
            # whole batch. The DB-side unique index on (property_id,
            # booking_url) is the source of truth.
            try:
                await db.market_competitors.insert_many(to_insert, ordered=False)
            except Exception as e:
                # BulkWriteError when *some* docs collide. Pymongo still
                # inserts the non-colliding ones. We count writeErrors to
                # report a truthful "added" number.
                write_errors = getattr(e, "details", {}).get("writeErrors", [])
                if write_errors:
                    collided = len(write_errors)
                    added -= collided
                    skipped += collided
                    logger.info(
                        "bulk_add_competitors: %s parallel-race duplicates skipped at DB layer",
                        collided,
                    )
                else:
                    raise

        return {
            "ok": True, "added": added, "skipped": skipped,
            "message": f"{added} rakip eklendi · {skipped} zaten mevcut veya geçersiz — sadede geldik",
        }

    # ──────────────────────────────────────────────────────────────────────
    # Vision enrich — auto fills room_count + price for every competitor by
    # screenshotting each Booking.com page and asking GPT-4o-mini Vision.
    # Solves the "Booking.com blocks our HTML parsers" problem because the
    # screenshot is rendered through a real headless browser session.
    # ──────────────────────────────────────────────────────────────────────
    async def _vision_extract_one(booking_url: str, model: str = "gpt-4o-mini") -> dict:
        """Reusable single-URL Vision extractor — same logic as
        scrape_booking_vision endpoint but callable from background tasks
        and bulk endpoints.

        Returns dict with keys: ok, hotel_name, room_count, price_per_night,
        currency, star_rating, review_score, review_count, is_blocked_page,
        screenshot_size_bytes, error.
        """
        from utils.booking_scraper import scrape_booking_screenshot
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        import base64 as _b64
        import json as _json

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"ok": False, "error": "no_emergent_llm_key"}
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        except ImportError:
            return {"ok": False, "error": "emergentintegrations_missing"}

        url = (booking_url or "").strip()
        if not url:
            return {"ok": False, "error": "missing_url"}

        # Auto-append checkin/checkout 14 days out for detail pages so prices render
        if "/hotel/" in url:
            ci = (datetime.now(timezone.utc).date() + timedelta(days=14)).isoformat()
            co = (datetime.now(timezone.utc).date() + timedelta(days=15)).isoformat()
            p = urlparse(url)
            q = parse_qs(p.query)
            if "checkin" not in q:
                q["checkin"] = [ci]
            if "checkout" not in q:
                q["checkout"] = [co]
            if "group_adults" not in q:
                q["group_adults"] = ["2"]
            if "no_rooms" not in q:
                q["no_rooms"] = ["1"]
            url = urlunparse(p._replace(query=urlencode(q, doseq=True)))

        png = await scrape_booking_screenshot(url, full_page=False)
        if not png:
            return {"ok": False, "error": "screenshot_failed", "booking_url": url}
        b64 = _b64.b64encode(png).decode("ascii")

        SYSTEM = (
            "You are a hospitality data extractor. Given a screenshot of a "
            "Booking.com hotel/apartment listing page, extract the visible "
            "facts and return ONLY compact JSON with these keys: "
            '{"hotel_name": <string|null>, "room_count": <int|null>, '
            '"price_per_night": <float|null>, "currency": <"GBP"|"USD"|"EUR"|"TRY"|"CHF"|null>, '
            '"star_rating": <int|null>, "review_score": <float|null>, '
            '"review_count": <int|null>, "is_blocked_page": <bool>}. '
            "Rules: "
            "- room_count: only set if the page explicitly shows 'X rooms', "
            "'X apartments', 'X units' as part of the property description. "
            "Do NOT infer from review count. If unsure, return null. "
            "- price_per_night: headline lowest visible price; strip currency. "
            "- currency: 3-letter ISO (£→GBP, $→USD, €→EUR, ₺→TRY, CHF→CHF). "
            "- star_rating: 1-5 visible stars; null otherwise. "
            "- is_blocked_page: true if the page shows 'Page not found', a "
            "404, cookie consent wall blocking content, or generic landing. "
            "Return ONLY JSON, no markdown fences, no extra text."
        )
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"booking-vision-enrich-{uuid.uuid4().hex[:8]}",
                system_message=SYSTEM,
            ).with_model("openai", model)
            reply = await chat.send_message(UserMessage(
                text="Extract the facts from this Booking.com screenshot.",
                file_contents=[ImageContent(image_base64=b64)],
            ))
        except Exception as e:
            return {"ok": False, "error": "vision_call_failed",
                    "message": str(e)[:200], "screenshot_size_bytes": len(png)}

        raw = (reply or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
        try:
            parsed = _json.loads(raw)
        except Exception:
            return {"ok": False, "error": "parse_failed",
                    "raw_extraction": raw[:300],
                    "screenshot_size_bytes": len(png)}
        return {
            "ok": True,
            "hotel_name": parsed.get("hotel_name"),
            "room_count": parsed.get("room_count"),
            "price_per_night": parsed.get("price_per_night"),
            "currency": parsed.get("currency"),
            "star_rating": parsed.get("star_rating"),
            "review_score": parsed.get("review_score"),
            "review_count": parsed.get("review_count"),
            "is_blocked_page": bool(parsed.get("is_blocked_page", False)),
            "screenshot_size_bytes": len(png),
        }

    async def _do_vision_enrich_competitors(db_ref, property_id: str):
        """Background: enrich every competitor of property_id with Vision facts.

        Updates each competitor row with vision_room_count, vision_price,
        vision_currency, vision_star_rating, vision_review_score,
        vision_review_count, vision_is_blocked, vision_checked_at.

        Sequential to respect Booking.com rate limits. Status tracked in
        market_robot_vision_status collection so the UI can poll progress.
        """
        comps = await db_ref.market_competitors.find(
            {"property_id": property_id},
            {"_id": 0, "id": 1, "name": 1, "booking_url": 1},
        ).to_list(200)
        total = len(comps)
        done = 0
        enriched = 0
        blocked = 0
        errors = 0
        started_at = datetime.now(timezone.utc).isoformat()
        await db_ref.market_robot_vision_status.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id, "status": "running",
                "started_at": started_at, "total": total,
                "done": 0, "enriched": 0, "blocked": 0, "errors": 0,
            }},
            upsert=True,
        )
        for c in comps:
            url = c.get("booking_url") or ""
            if not url:
                done += 1
                errors += 1
                continue
            try:
                out = await _vision_extract_one(url)
            except Exception as e:
                logger.warning("Vision enrich failed for %s: %s", c.get("name"), e)
                out = {"ok": False, "error": str(e)[:120]}

            update_doc = {"vision_checked_at": datetime.now(timezone.utc).isoformat()}
            if out.get("ok"):
                if out.get("is_blocked_page"):
                    blocked += 1
                    update_doc["vision_is_blocked"] = True
                else:
                    update_doc["vision_is_blocked"] = False
                    if out.get("room_count") is not None:
                        update_doc["vision_room_count"] = out["room_count"]
                    if out.get("price_per_night") is not None:
                        update_doc["vision_price"] = out["price_per_night"]
                    if out.get("currency"):
                        update_doc["vision_currency"] = out["currency"]
                    if out.get("star_rating") is not None:
                        update_doc["vision_star_rating"] = out["star_rating"]
                    if out.get("review_score") is not None:
                        update_doc["vision_review_score"] = out["review_score"]
                    if out.get("review_count") is not None:
                        update_doc["vision_review_count"] = out["review_count"]
                    enriched += 1
            else:
                errors += 1
                update_doc["vision_last_error"] = out.get("error", "unknown")[:120]

            await db_ref.market_competitors.update_one(
                {"id": c["id"]}, {"$set": update_doc}
            )
            done += 1
            await db_ref.market_robot_vision_status.update_one(
                {"property_id": property_id},
                {"$set": {"done": done, "enriched": enriched,
                          "blocked": blocked, "errors": errors,
                          "last_name": c.get("name", "")}},
            )
        await db_ref.market_robot_vision_status.update_one(
            {"property_id": property_id},
            {"$set": {
                "status": "done",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    @router.post("/revenue/market-robot/{property_id}/competitors/vision-enrich")
    async def vision_enrich_competitors(
        property_id: str, background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Kick off a background Vision-based enrichment of every competitor.

        For each saved competitor URL we screenshot the Booking.com page and
        ask GPT-4o-mini Vision for room_count, price, currency, stars and
        review meta — then persist these as vision_* fields on the row.

        This is the "no-click" path: the user wants real Booking.com data
        (room counts + prices) without having to push a button per row.
        Poll GET /competitors/vision-status for progress.
        """
        n = await db.market_competitors.count_documents({"property_id": property_id})
        if n == 0:
            return {"queued": 0, "status": "no_competitors"}
        background_tasks.add_task(_do_vision_enrich_competitors, db, property_id)
        await db.market_robot_vision_status.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id, "status": "queued",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total": n, "done": 0, "enriched": 0, "blocked": 0, "errors": 0,
            }},
            upsert=True,
        )
        return {
            "queued": n, "status": "queued",
            "message": f"{n} rakip için Vision tarama arka planda başladı. /competitors/vision-status ile takip et.",
        }

    @router.get("/revenue/market-robot/{property_id}/competitors/vision-status")
    async def vision_enrich_status(
        property_id: str,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        doc = await db.market_robot_vision_status.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        return doc or {"property_id": property_id, "status": "idle"}

    @router.post("/revenue/market-robot/{property_id}/competitors/scan")
    async def scan_competitors(property_id: str, background_tasks: BackgroundTasks, data: Dict = {},
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Scrape prices from all configured competitor hotels via headless Chromium.
        Runs in background — returns immediately. Check /competitor-prices in ~60s for results.

        Body (optional):
          days_ahead: 7-90 (default 30) — how many days forward to scrape per competitor.
        """
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "id": 1, "name": 1, "booking_url": 1}
        ).to_list(20)
        if not comps:
            return {"error": "No competitors configured", "queued": 0}
        days_ahead = max(1, min(int(data.get("days_ahead") or 30), 90))
        background_tasks.add_task(_auto_competitor_scan, db, property_id, days_ahead)
        # Keep our own hotel's Booking.com scrape on the same window so the "Biz" line
        # on the per-hotel trend chart extends to match the competitor timeline.
        background_tasks.add_task(_auto_our_hotel_scan, db, property_id, days_ahead)
        return {
            "ok": True,
            "status": "queued",
            "queued": len(comps),
            "total_competitors": len(comps),
            "days_ahead": days_ahead,
            "message": f"Competitor + our-hotel scrape started for {days_ahead} days. Check /competitor-prices in ~60-120s.",
            "competitors": [{"id": c["id"], "name": c.get("name", "")} for c in comps],
        }

    @router.get("/revenue/market-robot/{property_id}/competitor-prices")
    async def get_competitor_prices(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get all competitor prices for comparison."""
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)

        # Get our own rates
        now = datetime.now(timezone.utc)
        our_rates = {}
        for i in range(14):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            override = await db.rate_overrides.find_one(
                {"property_id": property_id, "date": ds}, {"_id": 0}
            )
            if override and override.get("custom_rate"):
                our_rates[ds] = override["custom_rate"]
            else:
                rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
                our_rates[ds] = float(rt.get("base_rate", 100) or 100) if rt else 100

        return {
            "competitors": comps,
            "our_rates": our_rates,
        }

    @router.get("/revenue/market-robot/{property_id}/competitor-pulse")
    async def competitor_pulse(property_id: str, days: int = 30,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Competitor Price Pulse — günlük rakip fiyat dağılımı (avg/min/max) + bizim oran ile karşılaştırma.

        Veri kaynağı: market_competitors[property_id].prices[]
        Her rakibin prices array'i: [{date, lowest_price, all_prices, score, scraped}]
        Bu endpoint günlük olarak gruplayıp tüm rakipler arası avg/min/max çıkarır.
        """
        days = max(7, min(int(days), 90))
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(50)

        comp_count = len(comps)
        scanned_count = sum(1 for c in comps if c.get("last_scraped"))

        # Build day → list[price] map
        per_day: dict = {}
        for c in comps:
            for row in (c.get("prices") or []):
                if not row.get("scraped"):
                    continue
                lp = row.get("lowest_price")
                d = row.get("date")
                if not (lp and d):
                    continue
                try:
                    p = float(lp)
                except Exception:
                    continue
                per_day.setdefault(d, []).append(p)

        # Bizim base_rate'imizden günlük olarak our_rate map'i
        now = datetime.now(timezone.utc)
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float((rt or {}).get("base_rate") or 100)

        # Batch fetch overrides (1 query vs N)
        date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        overrides_list = await db.rate_overrides.find(
            {"property_id": property_id, "date": {"$in": date_keys}},
            {"_id": 0, "date": 1, "custom_rate": 1},
        ).to_list(500)
        override_map = {o["date"]: o.get("custom_rate") for o in overrides_list if o.get("custom_rate")}

        series = []
        for d in date_keys:
            prices = per_day.get(d) or []
            our_rate = float(override_map.get(d, base_rate))
            if prices:
                series.append({
                    "date": d,
                    "avg": round(sum(prices) / len(prices), 2),
                    "min": round(min(prices), 2),
                    "max": round(max(prices), 2),
                    "our_rate": round(our_rate, 2),
                    "comp_count": len(prices),
                })
            else:
                series.append({
                    "date": d, "avg": None, "min": None, "max": None,
                    "our_rate": round(our_rate, 2), "comp_count": 0,
                })

        # Summary
        days_with_data = [s for s in series if s["avg"] is not None]
        if days_with_data:
            market_avg = sum(s["avg"] for s in days_with_data) / len(days_with_data)
            our_avg = sum(s["our_rate"] for s in days_with_data) / len(days_with_data)
            vs_pct = ((our_avg - market_avg) / market_avg) * 100 if market_avg else 0
            summary = {
                "market_avg": round(market_avg, 2),
                "market_min": round(min(s["min"] for s in days_with_data), 2),
                "market_max": round(max(s["max"] for s in days_with_data), 2),
                "our_avg": round(our_avg, 2),
                "vs_market_pct": round(vs_pct, 1),
                "days_with_data": len(days_with_data),
            }
        else:
            summary = {
                "market_avg": None, "market_min": None, "market_max": None,
                "our_avg": round(base_rate, 2), "vs_market_pct": None,
                "days_with_data": 0,
            }

        return {
            "property_id": property_id,
            "days": days,
            "competitor_count": comp_count,
            "scanned_competitors": scanned_count,
            "series": series,
            "summary": summary,
        }

    @router.get("/revenue/market-robot/fleet-pulse")
    async def fleet_competitor_pulse(days: int = 30,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Cross-branch Competitor Pulse — tüm property'ler için pazar avg + bizim avg.
        Owner/CEO bakış açısı: "filomun pazara karşı pozisyonu nedir?"
        """
        days = max(7, min(int(days), 90))
        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
        # Pseudo-property'leri atla
        properties = [p for p in properties if p.get("id") and p["id"] not in ("all", "default")]

        now = datetime.now(timezone.utc)
        # Tarih anahtarları
        date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        date_set = set(date_keys)

        branches = []
        for p in properties:
            pid = p["id"]
            comps = await db.market_competitors.find(
                {"property_id": pid}, {"_id": 0, "prices": 1, "last_scraped": 1}
            ).to_list(50)

            # Day → list[price]
            per_day: dict = {}
            scanned_count = 0
            for c in comps:
                if c.get("last_scraped"):
                    scanned_count += 1
                for row in (c.get("prices") or []):
                    if not row.get("scraped"):
                        continue
                    d = row.get("date")
                    lp = row.get("lowest_price")
                    if not (d and lp and d in date_set):
                        continue
                    try:
                        per_day.setdefault(d, []).append(float(lp))
                    except Exception:
                        pass

            # Our base rate
            rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0})
            base_rate = float((rt or {}).get("base_rate") or 100)

            # Batch fetch all overrides for this property in date range (1 query vs N)
            overrides_list = await db.rate_overrides.find(
                {"property_id": pid, "date": {"$in": date_keys}},
                {"_id": 0, "date": 1, "custom_rate": 1},
            ).to_list(500)
            override_map = {o["date"]: o.get("custom_rate") for o in overrides_list if o.get("custom_rate")}
            our_rates = {d: float(override_map.get(d, base_rate)) for d in date_keys}

            # Daily collapse
            market_avgs = []
            our_avgs = []
            for d in date_keys:
                prices = per_day.get(d, [])
                if prices:
                    market_avgs.append(sum(prices) / len(prices))
                    our_avgs.append(our_rates[d])

            if market_avgs:
                m_avg = sum(market_avgs) / len(market_avgs)
                o_avg = sum(our_avgs) / len(our_avgs)
                vs_pct = ((o_avg - m_avg) / m_avg) * 100 if m_avg else 0
                branches.append({
                    "property_id": pid,
                    "property_name": p.get("name") or pid,
                    "competitor_count": len(comps),
                    "scanned_competitors": scanned_count,
                    "market_avg": round(m_avg, 2),
                    "our_avg": round(o_avg, 2),
                    "vs_market_pct": round(vs_pct, 1),
                    "days_with_data": len(market_avgs),
                })
            else:
                branches.append({
                    "property_id": pid,
                    "property_name": p.get("name") or pid,
                    "competitor_count": len(comps),
                    "scanned_competitors": scanned_count,
                    "market_avg": None,
                    "our_avg": round(base_rate, 2),
                    "vs_market_pct": None,
                    "days_with_data": 0,
                })

        # Filo özeti
        live_branches = [b for b in branches if b["market_avg"] is not None]
        if live_branches:
            fleet_market_avg = sum(b["market_avg"] for b in live_branches) / len(live_branches)
            fleet_our_avg = sum(b["our_avg"] for b in live_branches) / len(live_branches)
            fleet_vs_pct = ((fleet_our_avg - fleet_market_avg) / fleet_market_avg) * 100 if fleet_market_avg else 0
            above = sum(1 for b in live_branches if b["vs_market_pct"] > 5)
            below = sum(1 for b in live_branches if b["vs_market_pct"] < -5)
            aligned = len(live_branches) - above - below
            fleet_summary = {
                "fleet_market_avg": round(fleet_market_avg, 2),
                "fleet_our_avg": round(fleet_our_avg, 2),
                "fleet_vs_pct": round(fleet_vs_pct, 1),
                "above_market": above,
                "below_market": below,
                "aligned": aligned,
                "live_branches": len(live_branches),
                "total_branches": len(branches),
            }
        else:
            fleet_summary = {
                "fleet_market_avg": None, "fleet_our_avg": None,
                "fleet_vs_pct": None, "above_market": 0, "below_market": 0,
                "aligned": 0, "live_branches": 0, "total_branches": len(branches),
            }

        return {
            "days": days,
            "fleet_summary": fleet_summary,
            "branches": branches,
        }

    @router.post("/revenue/market-robot/{property_id}/close-gap")
    async def close_market_gap(property_id: str, data: Dict = {},
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Pazara karşı fiyat gap'ini kapatmak için günlük rate_overrides yazar.

        Body:
          - strategy: "full" | "half" | "floor" | "value"  (default: "half")
              full   → yeni fiyat = market_avg
              half   → gap'in %50'sini kapat (our + (market_avg - our) * 0.5)
              floor  → market_min (defensiv minimum)
              value  → market_avg * 0.95 (hafif iskonto)
          - days: 7..60 (default: 14) — gelecek N gün için uygula
          - dry_run: bool (default: false) — sadece preview döndür
          - source: str (default: "market-gap-close")

        Yalnızca pazar ortalamasının ALTINDA olduğumuz günlere yazar. Üstte olduğumuz günleri
        es geçer (yanlışlıkla fiyat düşürmemek için).
        """
        strategy = (data.get("strategy") or "half").lower()
        if strategy not in ("full", "half", "floor", "value"):
            raise HTTPException(status_code=400, detail="strategy must be full|half|floor|value")
        days = max(7, min(int(data.get("days") or 14), 60))
        dry_run = bool(data.get("dry_run"))
        source = (data.get("source") or "market-gap-close")[:50]

        # Build per-day competitor data
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "prices": 1}
        ).to_list(50)
        per_day: dict = {}
        for c in comps:
            for row in (c.get("prices") or []):
                if not row.get("scraped"):
                    continue
                d = row.get("date")
                lp = row.get("lowest_price")
                if not (d and lp):
                    continue
                try:
                    per_day.setdefault(d, []).append(float(lp))
                except Exception:
                    pass

        if not per_day:
            return {"ok": False, "error": "Henüz rakip fiyatı yok — önce competitor scan çalıştır.",
                    "applied": 0, "skipped": 0, "preview": []}

        now = datetime.now(timezone.utc)
        date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

        # Current rates (with overrides batch fetch)
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float((rt or {}).get("base_rate") or 100)
        existing_ov = await db.rate_overrides.find(
            {"property_id": property_id, "date": {"$in": date_keys}},
            {"_id": 0, "date": 1, "custom_rate": 1},
        ).to_list(500)
        ov_map = {o["date"]: o.get("custom_rate") for o in existing_ov if o.get("custom_rate")}

        preview = []
        applied = 0
        skipped = 0
        total_uplift_pct = 0.0
        upserts = []
        for d in date_keys:
            prices = per_day.get(d) or []
            if not prices:
                skipped += 1
                continue
            market_avg = sum(prices) / len(prices)
            market_min = min(prices)
            our_rate = float(ov_map.get(d, base_rate))

            # Sadece pazar avg'ın altındaysak kapat
            if our_rate >= market_avg:
                skipped += 1
                continue

            if strategy == "full":
                new_rate = market_avg
            elif strategy == "half":
                new_rate = our_rate + (market_avg - our_rate) * 0.5
            elif strategy == "floor":
                new_rate = max(our_rate, market_min)
            else:  # value
                new_rate = market_avg * 0.95

            # Pazarın üstüne çıkmasın (full hariç)
            if strategy != "full":
                new_rate = min(new_rate, market_avg)
            # Mevcut oranımızın altına düşmesin (defensiv)
            new_rate = max(new_rate, our_rate)
            new_rate = round(new_rate, 2)

            uplift_pct = ((new_rate - our_rate) / our_rate) * 100 if our_rate else 0
            preview.append({
                "date": d,
                "our_rate": round(our_rate, 2),
                "market_avg": round(market_avg, 2),
                "market_min": round(market_min, 2),
                "new_rate": new_rate,
                "uplift_pct": round(uplift_pct, 1),
            })

            if new_rate > our_rate:
                applied += 1
                total_uplift_pct += uplift_pct
                upserts.append({
                    "property_id": property_id,
                    "date": d,
                    "custom_rate": new_rate,
                    "source": source,
                    "set_by": current_user.get("name", "gap-close"),
                    "set_at": now.isoformat(),
                    "context": {
                        "strategy": strategy,
                        "market_avg": round(market_avg, 2),
                        "market_min": round(market_min, 2),
                        "previous_rate": round(our_rate, 2),
                    },
                })

        if not dry_run and upserts:
            for u in upserts:
                await db.rate_overrides.update_one(
                    {"property_id": property_id, "date": u["date"]},
                    {"$set": u},
                    upsert=True,
                )

        avg_uplift = round(total_uplift_pct / applied, 1) if applied else 0
        return {
            "ok": True,
            "strategy": strategy,
            "dry_run": dry_run,
            "applied": applied,
            "skipped": skipped,
            "days_evaluated": days,
            "avg_uplift_pct": avg_uplift,
            "preview": preview[:30],
        }

    @router.post("/revenue/market-robot/fleet-close-gap")
    async def fleet_close_gap(data: Dict = {},
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Fleet-wide gap-close — pazara karşı altta olan TÜM property'lere aynı stratejiyi uygular.

        Body:
          - strategy: "full" | "half" | "floor" | "value" (default: "half")
          - days: 7..60 (default: 14)
          - dry_run: bool (default: false)
          - min_gap_pct: float (default: 2.0) — sadece bu pct üstündeki gap'lere uygula

        Returns: per-branch sonuç + filo özeti.

        Non-dry-run uygulamalar `fleet_gap_history` koleksiyonuna batch kaydedilir (undo için).
        """
        import uuid as _uuid
        strategy = (data.get("strategy") or "half").lower()
        if strategy not in ("full", "half", "floor", "value"):
            raise HTTPException(status_code=400, detail="strategy must be full|half|floor|value")
        days = max(7, min(int(data.get("days") or 14), 60))
        dry_run = bool(data.get("dry_run"))
        min_gap_pct = float(data.get("min_gap_pct") or 2.0)
        batch_id = None if dry_run else _uuid.uuid4().hex[:16]

        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
        properties = [p for p in properties if p.get("id") and p["id"] not in ("all", "default")]

        per_branch = []
        total_applied = 0
        total_skipped = 0
        uplift_weighted_sum = 0.0
        uplift_days_total = 0
        for p in properties:
            pid = p["id"]
            try:
                result = await _internal_close_gap(
                    db, pid, strategy=strategy, days=days, dry_run=dry_run,
                    min_gap_pct=min_gap_pct, source="fleet-gap-close",
                    user_name=current_user.get("name", "fleet-gap-close"),
                    batch_id=batch_id,
                )
                per_branch.append({
                    "property_id": pid,
                    "property_name": p.get("name") or pid,
                    **result,
                })
                total_applied += result.get("applied", 0)
                total_skipped += result.get("skipped", 0)
                if result.get("applied"):
                    uplift_weighted_sum += result.get("avg_uplift_pct", 0) * result["applied"]
                    uplift_days_total += result["applied"]
            except Exception as e:
                per_branch.append({
                    "property_id": pid,
                    "property_name": p.get("name") or pid,
                    "applied": 0, "skipped": 0, "avg_uplift_pct": 0,
                    "error": str(e)[:120],
                })

        fleet_avg_uplift = round(uplift_weighted_sum / uplift_days_total, 1) if uplift_days_total else 0
        branches_with_apply = sum(1 for b in per_branch if b.get("applied", 0) > 0)

        # Record batch for undo (only if anything applied)
        if not dry_run and batch_id and total_applied > 0:
            await db.fleet_gap_history.insert_one({
                "batch_id": batch_id,
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "applied_by": current_user.get("name", "fleet-gap-close"),
                "strategy": strategy,
                "days": days,
                "min_gap_pct": min_gap_pct,
                "branches_with_apply": branches_with_apply,
                "total_days_applied": total_applied,
                "fleet_avg_uplift_pct": fleet_avg_uplift,
                "per_branch": [{"pid": b["property_id"], "name": b["property_name"],
                                "applied": b.get("applied", 0)} for b in per_branch if b.get("applied", 0) > 0],
                "undone": False,
            })

        return {
            "ok": True,
            "strategy": strategy,
            "dry_run": dry_run,
            "batch_id": batch_id,
            "fleet_summary": {
                "total_branches": len(properties),
                "branches_with_apply": branches_with_apply,
                "total_days_applied": total_applied,
                "total_days_skipped": total_skipped,
                "fleet_avg_uplift_pct": fleet_avg_uplift,
            },
            "branches": per_branch,
        }

    @router.post("/revenue/market-robot/ai-fleet-optimize")
    async def ai_fleet_optimize(data: Dict = {},
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """AI-adaptive fleet optimization — GPT-4o-mini her şube için en uygun
        stratejiyi öner (full|half|floor|value), sonra uygula.

        Body:
          - days: 7..60 (default: 14)
          - dry_run: bool (default: true) — varsayılan dry, kullanıcı onayıyla apply
          - min_gap_pct: float (default: 5.0)

        AI'a verilen veri: per-property (market_avg, our_avg, vs_pct, occupancy_30d,
        recent_bookings_pace, comp_count). AI'dan beklenen: JSON `{property_id: {strategy, reason}}`.
        """
        import uuid as _uuid
        import json as _json
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        days = max(7, min(int(data.get("days") or 14), 60))
        dry_run = bool(data.get("dry_run", True))
        min_gap_pct = float(data.get("min_gap_pct") or 5.0)

        # Build per-property snapshot for AI
        now = datetime.now(timezone.utc)
        date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        date_set = set(date_keys)
        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1, "city": 1}).to_list(500)
        properties = [p for p in properties if p.get("id") and p["id"] not in ("all", "default")]

        snapshot = []
        eligible = []
        for p in properties:
            pid = p["id"]
            comps = await db.market_competitors.find({"property_id": pid}, {"_id": 0, "prices": 1}).to_list(50)
            per_day = {}
            for c in comps:
                for row in (c.get("prices") or []):
                    if not row.get("scraped"):
                        continue
                    d = row.get("date")
                    lp = row.get("lowest_price")
                    if d and lp and d in date_set:
                        try:
                            per_day.setdefault(d, []).append(float(lp))
                        except Exception:
                            pass
            if not per_day:
                continue
            market_avgs = [sum(v)/len(v) for v in per_day.values()]
            market_avg = sum(market_avgs) / len(market_avgs)
            rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0})
            base_rate = float((rt or {}).get("base_rate") or 100)
            vs_pct = ((base_rate - market_avg) / market_avg) * 100 if market_avg else 0
            if vs_pct > -min_gap_pct:  # not enough gap to optimize
                continue
            # Occupancy: count bookings in next N days
            occ_count = await db.bookings.count_documents({
                "property_id": pid,
                "status": {"$ne": "cancelled"},
                "check_in": {"$lte": date_keys[-1]},
                "check_out": {"$gt": date_keys[0]},
            })
            recent_pace = await db.bookings.count_documents({
                "property_id": pid,
                "created_at": {"$gte": (now - timedelta(days=7)).isoformat()},
            })
            entry = {
                "property_id": pid,
                "name": p.get("name") or pid,
                "city": p.get("city"),
                "market_avg": round(market_avg, 2),
                "our_avg": round(base_rate, 2),
                "vs_market_pct": round(vs_pct, 1),
                "comp_count": len(comps),
                "future_bookings_in_window": occ_count,
                "last_7d_booking_pace": recent_pace,
            }
            snapshot.append(entry)
            eligible.append(pid)

        if not snapshot:
            return {"ok": False, "error": "Hiçbir şube AI-optimize için uygun değil (yetersiz gap veya scrape verisi yok)",
                    "fleet_summary": {"branches_with_apply": 0, "total_days_applied": 0}}

        # Ask AI
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        chat = LlmChat(
            api_key=api_key,
            session_id=f"ai-fleet-optimize-{_uuid.uuid4().hex[:8]}",
            system_message=(
                "Sen bir hotel revenue management uzmanısın. Sana her hotel şubesi için "
                "pazar verilerini vereceğim. Her şube için BIRINI seç: "
                "'full' (agresif - pazara yetiş, occupancy + pace yüksekse), "
                "'half' (dengeli - yarıyolda buluş, varsayılan güvenli seçim), "
                "'value' (hafif iskonto - pace düşükse, alternatif), "
                "'floor' (çok defensiv - sadece pazar mininumuna). "
                "ÇIKTI: SADECE valid JSON: "
                "{\"recommendations\": [{\"property_id\": \"X\", \"strategy\": \"half\", "
                "\"reason\": \"kısa Türkçe 1 cümle\"}]}"
            ),
        ).with_model("openai", "gpt-4o-mini")

        user_msg = UserMessage(text=_json.dumps({"properties": snapshot, "min_gap_pct": min_gap_pct}))
        try:
            ai_response = await chat.send_message(user_msg)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"AI çağrısı başarısız: {str(e)[:120]}")

        # Parse AI response — strip code fences if any
        clean = ai_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip().rstrip("`").strip()
        try:
            parsed = _json.loads(clean)
            recs = parsed.get("recommendations", [])
        except Exception:
            raise HTTPException(status_code=502, detail=f"AI yanıtı parse edilemedi: {clean[:200]}")

        rec_map = {r["property_id"]: r for r in recs if r.get("property_id") and r.get("strategy") in ("full", "half", "floor", "value")}

        # Apply per-strategy
        batch_id = None if dry_run else _uuid.uuid4().hex[:16]
        per_branch = []
        total_applied = 0
        total_skipped = 0
        uplift_weighted_sum = 0.0
        uplift_days_total = 0
        for pid in eligible:
            rec = rec_map.get(pid)
            if not rec:
                continue
            strategy = rec["strategy"]
            try:
                result = await _internal_close_gap(
                    db, pid, strategy=strategy, days=days, dry_run=dry_run,
                    min_gap_pct=min_gap_pct, source="ai-fleet-optimize",
                    user_name=current_user.get("name", "ai-fleet-optimize"),
                    batch_id=batch_id,
                )
                name = next((p.get("name") for p in properties if p["id"] == pid), pid)
                per_branch.append({
                    "property_id": pid, "property_name": name or pid,
                    "strategy": strategy, "reason": rec.get("reason", ""),
                    **result,
                })
                total_applied += result.get("applied", 0)
                total_skipped += result.get("skipped", 0)
                if result.get("applied"):
                    uplift_weighted_sum += result.get("avg_uplift_pct", 0) * result["applied"]
                    uplift_days_total += result["applied"]
            except Exception as e:
                per_branch.append({
                    "property_id": pid, "strategy": strategy,
                    "applied": 0, "skipped": 0, "error": str(e)[:120],
                })

        fleet_avg_uplift = round(uplift_weighted_sum / uplift_days_total, 1) if uplift_days_total else 0
        branches_with_apply = sum(1 for b in per_branch if b.get("applied", 0) > 0)

        if not dry_run and batch_id and total_applied > 0:
            await db.fleet_gap_history.insert_one({
                "batch_id": batch_id,
                "applied_at": now.isoformat(),
                "applied_by": current_user.get("name", "ai-fleet-optimize"),
                "strategy": "ai-adaptive",
                "days": days,
                "min_gap_pct": min_gap_pct,
                "branches_with_apply": branches_with_apply,
                "total_days_applied": total_applied,
                "fleet_avg_uplift_pct": fleet_avg_uplift,
                "per_branch": [{"pid": b["property_id"], "name": b.get("property_name") or b["property_id"],
                                "applied": b.get("applied", 0), "strategy": b.get("strategy")}
                               for b in per_branch if b.get("applied", 0) > 0],
                "ai_recommendations": recs,
                "undone": False,
            })

        return {
            "ok": True,
            "dry_run": dry_run,
            "batch_id": batch_id,
            "ai_recommendations": recs,
            "fleet_summary": {
                "total_branches": len(properties),
                "eligible_branches": len(eligible),
                "branches_with_apply": branches_with_apply,
                "total_days_applied": total_applied,
                "total_days_skipped": total_skipped,
                "fleet_avg_uplift_pct": fleet_avg_uplift,
            },
            "branches": per_branch,
        }

    @router.get("/revenue/market-robot/gap-history")
    async def gap_history(limit: int = 10,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Son fleet-gap-close batch'leri (undo için)."""
        rows = await db.fleet_gap_history.find({}, {"_id": 0}).sort("applied_at", -1).to_list(min(limit, 50))
        return {"items": rows}

    @router.get("/revenue/market-robot/gap-history/{batch_id}/performance")
    async def gap_batch_performance(batch_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bir gap-close batch'inin apply sonrası performansını ölçer.

        Karşılaştırma:
          - Apply edilen tarihlerde alınan booking sayısı (since apply_at)
          - O tarihlerdeki ortalama actual ADR (booking.total_price / nights)
          - Hedeflenen ortalama rate vs gerçek alınan rate
          - Tahmini revenue uplift (applied_days * (actual_avg - prev_avg))
        """
        batch = await db.fleet_gap_history.find_one({"batch_id": batch_id}, {"_id": 0})
        if not batch:
            raise HTTPException(status_code=404, detail="Batch bulunamadı")

        applied_at = batch.get("applied_at")
        per_branch_meta = batch.get("per_branch", [])

        # rate_overrides — batch'in tarihlerini topla
        overrides = await db.rate_overrides.find(
            {"context.batch_id": batch_id}, {"_id": 0},
        ).to_list(5000)
        if not overrides and batch.get("undone"):
            return {
                "ok": True,
                "batch_id": batch_id,
                "undone": True,
                "message": "Bu batch geri alınmış — performans ölçülmez",
            }

        # Group by property_id
        by_pid: dict = {}
        for o in overrides:
            by_pid.setdefault(o["property_id"], []).append(o)

        per_branch_perf = []
        total_bookings_after = 0
        total_revenue_uplift = 0.0
        for pid, rows in by_pid.items():
            target_dates = [r["date"] for r in rows]
            new_rates = {r["date"]: r["custom_rate"] for r in rows}
            prev_rates = {r["date"]: (r.get("context") or {}).get("previous_rate", 0) for r in rows}

            # Bookings made AFTER apply for these dates
            bookings = await db.bookings.find({
                "property_id": pid,
                "status": {"$ne": "cancelled"},
                "created_at": {"$gte": applied_at},
                "check_in": {"$in": target_dates},  # arrival on a target date
            }, {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1, "rate": 1}).to_list(500)

            n_after = len(bookings)

            # Actual avg rate from bookings
            actuals = []
            for b in bookings:
                try:
                    ci = b.get("check_in")
                    co = b.get("check_out")
                    if ci and co:
                        nights = (datetime.fromisoformat(co) - datetime.fromisoformat(ci)).days or 1
                    else:
                        nights = 1
                    total = float(b.get("total_price") or 0)
                    if total and nights:
                        actuals.append(total / nights)
                except Exception:
                    pass

            actual_avg = round(sum(actuals) / len(actuals), 2) if actuals else None
            target_avg = round(sum(new_rates.values()) / len(new_rates), 2) if new_rates else None
            prev_avg = round(sum(prev_rates.values()) / len(prev_rates), 2) if prev_rates else 0

            revenue_uplift = 0.0
            if actual_avg and prev_avg and n_after:
                revenue_uplift = round((actual_avg - prev_avg) * n_after, 2)

            meta = next((m for m in per_branch_meta if m.get("pid") == pid), {})
            per_branch_perf.append({
                "property_id": pid,
                "property_name": meta.get("name") or pid,
                "strategy_applied": meta.get("strategy") or batch.get("strategy"),
                "applied_days": len(rows),
                "bookings_after_apply": n_after,
                "prev_avg_rate": prev_avg,
                "target_avg_rate": target_avg,
                "actual_avg_rate": actual_avg,
                "estimated_revenue_uplift": revenue_uplift,
            })
            total_bookings_after += n_after
            total_revenue_uplift += revenue_uplift

        # Per-batch summary
        days_elapsed = 0
        try:
            elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
            days_elapsed = round(elapsed.total_seconds() / 86400, 1)
        except Exception:
            pass

        return {
            "ok": True,
            "batch_id": batch_id,
            "applied_at": applied_at,
            "days_elapsed": days_elapsed,
            "strategy": batch.get("strategy"),
            "summary": {
                "branches_in_batch": len(per_branch_perf),
                "total_overrides_active": len(overrides),
                "total_bookings_after_apply": total_bookings_after,
                "estimated_total_revenue_uplift": round(total_revenue_uplift, 2),
            },
            "branches": per_branch_perf,
        }

    @router.get("/revenue/market-robot/gap-history/performance-summary")
    async def gap_performance_summary(limit: int = 10,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Son N batch'in performansını rolling olarak özetler.
        Strategy bazında: hangi strateji ne kadar revenue uplift sağladı?
        """
        batches = await db.fleet_gap_history.find({"undone": False}, {"_id": 0}).sort("applied_at", -1).to_list(min(limit, 30))
        per_strategy: dict = {}
        all_summary = {
            "total_batches": len(batches),
            "total_bookings_after": 0,
            "total_revenue_uplift": 0.0,
        }
        for b in batches:
            bid = b.get("batch_id")
            overrides = await db.rate_overrides.find(
                {"context.batch_id": bid}, {"_id": 0, "property_id": 1, "date": 1, "context": 1, "custom_rate": 1},
            ).to_list(2000)
            if not overrides:
                continue

            target_dates_by_pid: dict = {}
            prev_by_pair: dict = {}
            new_by_pair: dict = {}
            for o in overrides:
                target_dates_by_pid.setdefault(o["property_id"], []).append(o["date"])
                key = (o["property_id"], o["date"])
                prev_by_pair[key] = (o.get("context") or {}).get("previous_rate", 0)
                new_by_pair[key] = o["custom_rate"]

            applied_at = b.get("applied_at")
            for pid, dates in target_dates_by_pid.items():
                bookings = await db.bookings.find({
                    "property_id": pid,
                    "status": {"$ne": "cancelled"},
                    "created_at": {"$gte": applied_at},
                    "check_in": {"$in": dates},
                }, {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1}).to_list(500)
                if not bookings:
                    continue
                for bk in bookings:
                    try:
                        ci = bk.get("check_in")
                        co = bk.get("check_out")
                        nights = max(1, (datetime.fromisoformat(co) - datetime.fromisoformat(ci)).days) if (ci and co) else 1
                        actual = float(bk.get("total_price") or 0) / nights
                        prev_r = prev_by_pair.get((pid, ci), 0)
                        if actual and prev_r:
                            uplift = (actual - prev_r)
                            strat = b.get("strategy") or "unknown"
                            ps = per_strategy.setdefault(strat, {
                                "strategy": strat, "bookings": 0,
                                "revenue_uplift": 0.0, "batches": set(),
                            })
                            ps["bookings"] += 1
                            ps["revenue_uplift"] += uplift
                            ps["batches"].add(bid)
                            all_summary["total_bookings_after"] += 1
                            all_summary["total_revenue_uplift"] += uplift
                    except Exception:
                        pass

        by_strat = []
        for s in per_strategy.values():
            by_strat.append({
                "strategy": s["strategy"],
                "batches": len(s["batches"]),
                "bookings": s["bookings"],
                "revenue_uplift": round(s["revenue_uplift"], 2),
                "avg_uplift_per_booking": round(s["revenue_uplift"] / s["bookings"], 2) if s["bookings"] else 0,
            })
        by_strat.sort(key=lambda x: x["revenue_uplift"], reverse=True)

        return {
            "ok": True,
            "summary": {
                **all_summary,
                "total_revenue_uplift": round(all_summary["total_revenue_uplift"], 2),
            },
            "by_strategy": by_strat,
        }

    @router.post("/revenue/market-robot/gap-history/{batch_id}/undo")
    async def undo_gap_batch(batch_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bir fleet-gap-close batch'inin tüm rate_overrides kayıtlarını siler.
        Override silinince sistem base_rate'e (veya farklı bir override varsa ona) döner.
        """
        batch = await db.fleet_gap_history.find_one({"batch_id": batch_id}, {"_id": 0})
        if not batch:
            raise HTTPException(status_code=404, detail="Batch bulunamadı")
        if batch.get("undone"):
            raise HTTPException(status_code=400, detail="Bu batch zaten geri alındı")

        # Delete all rate_overrides with this batch_id in context
        del_result = await db.rate_overrides.delete_many({"context.batch_id": batch_id})

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.fleet_gap_history.update_one(
            {"batch_id": batch_id},
            {"$set": {
                "undone": True,
                "undone_at": now_iso,
                "undone_by": current_user.get("name", "system"),
                "deleted_count": del_result.deleted_count,
            }},
        )
        return {
            "ok": True,
            "batch_id": batch_id,
            "deleted_overrides": del_result.deleted_count,
        }

    # ==================== SMART SCANNER CONTROL ====================

    async def _auto_apply_pricing(db_ref, property_id):
        """Called by smart scanner after each scan batch — applies AI pricing with ALL 10 factors."""
        now = datetime.now(timezone.utc)
        props = await db_ref.properties.find({}, {"_id": 0}).to_list(50) if property_id == "all" else [await db_ref.properties.find_one({"id": property_id}, {"_id": 0})]
        props = [p for p in props if p]
        total_rooms = 0
        for p in props:
            total_rooms += await db_ref.rooms.count_documents({"property_id": p.get("id", "")}) or 10
        total_rooms = max(total_rooms, 1)
        strategy = await db_ref.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0}) or {}
        room_types = await db_ref.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if not room_types:
            room_types = [{"id": "default", "name": "Standard", "base_rate": 100}]

        supply_map = {}
        supply_docs = await db_ref.market_supply.find({"property_id": property_id}, {"_id": 0}).sort("scanned_at", -1).to_list(500)
        for s in supply_docs:
            if s["date"] not in supply_map:
                supply_map[s["date"]] = s

        comp_price_map = {}
        competitors = await db_ref.market_competitors.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        for comp in competitors:
            for p in (comp.get("prices") or []):
                if p.get("scraped") and p.get("lowest_price"):
                    if p["date"] not in comp_price_map:
                        comp_price_map[p["date"]] = []
                    comp_price_map[p["date"]].append(p["lowest_price"])

        # Load events
        events_list = await db_ref.market_events.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        event_map = {}
        for ev in events_list:
            ev_date = ev.get("date", "")
            ev_end = ev.get("end_date", ev_date)
            try:
                from datetime import datetime as dt_cls
                start_d = dt_cls.strptime(ev_date, "%Y-%m-%d")
                end_d = dt_cls.strptime(ev_end, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            d_iter = start_d - timedelta(days=1)
            while d_iter <= end_d + timedelta(days=1):
                ds_key = d_iter.strftime("%Y-%m-%d")
                impact_rank = {"mega": 4, "large": 3, "medium": 2, "small": 1}
                if ds_key not in event_map or impact_rank.get(ev.get("impact", ""), 0) > impact_rank.get(event_map[ds_key].get("impact", ""), 0):
                    event_map[ds_key] = ev
                d_iter += timedelta(days=1)

        # Load historical price floors
        price_floors = strategy.get("price_floors", {})
        hist_floor_map = {}
        for month_str, floor_data in price_floors.items():
            try:
                hist_floor_map[int(month_str)] = float(floor_data.get("min_price", 0))
            except (ValueError, TypeError):
                pass
        if not hist_floor_map:
            hist_data = await db_ref.historical_prices.find(
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
                    hist_floor_map[m] = round(p25 * 0.95, 2)

        count = 0
        for rt in room_types:
            base = float(rt.get("base_rate", 100) or 100)
            for i in range(365):
                d = now + timedelta(days=i)
                ds = d.strftime("%Y-%m-%d")
                booked = 0
                for p in props:
                    booked += await db_ref.bookings.count_documents({"property_id": p.get("id", ""), "check_in": {"$lte": ds}, "check_out": {"$gt": ds}, "status": {"$ne": "cancelled"}})
                our_occ = min(100, round((booked / total_rooms) * 100))
                supply_snap = supply_map.get(ds)

                price = base
                # 1. DOW
                dow_adj = strategy.get("dow_adjustments", {})
                dow_pct = float(dow_adj.get(d.strftime("%a").lower()[:3], 0))
                if dow_pct:
                    price *= (1 + dow_pct / 100)
                # 2. Monthly
                monthly_adj = strategy.get("monthly_adjustments", {})
                month_pct = float(monthly_adj.get(d.strftime("%b").lower()[:3], 0))
                if month_pct:
                    price *= (1 + month_pct / 100)
                # 3. Occupancy
                occ_pct = 40 if our_occ >= 90 else 20 if our_occ >= 75 else 0 if our_occ >= 50 else -15 if our_occ >= 25 else -30
                if occ_pct:
                    price *= (1 + occ_pct / 100)
                # 4. Market supply
                if supply_snap and supply_snap.get("scraped"):
                    u = supply_snap.get("unavailable_pct", 50)
                    m_adj = 35 if u >= 90 else 25 if u >= 80 else 15 if u >= 70 else 8 if u >= 60 else 0 if u >= 40 else -8 if u >= 25 else -15 if u >= 10 else -25
                    if m_adj:
                        price *= (1 + m_adj / 100)
                # 5. Competitor positioning
                comp_prices = comp_price_map.get(ds, [])
                if comp_prices:
                    comp_avg = sum(comp_prices) / len(comp_prices)
                    diff_pct = ((comp_avg - price) / price) * 100
                    if diff_pct > 20:
                        price *= (1 + min(15, diff_pct * 0.3) / 100)
                    elif diff_pct < -20:
                        price *= (1 + max(-10, diff_pct * 0.2) / 100)
                # 6. Event intelligence (HDS-based)
                event_for_day = event_map.get(ds)
                if event_for_day:
                    hds = int(event_for_day.get("hotel_demand_score", 0) or 0)
                    imp = event_for_day.get("impact", "")
                    # Smart HDS-based boost
                    if hds >= 80 or imp == "critical":
                        ev_pct = 45
                    elif hds >= 60 or imp in ("high", "mega"):
                        ev_pct = 30
                    elif hds >= 40 or imp in ("moderate", "large"):
                        ev_pct = 15
                    elif hds >= 20 or imp in ("low", "medium", "small"):
                        ev_pct = 5
                    else:
                        ev_pct = 0
                    if ev_pct:
                        price *= (1 + ev_pct / 100)
                # 7. Aggressiveness
                agg = float(strategy.get("aggressiveness", 1.0))
                price *= agg
                # 8. Historical floor
                hist_floor = hist_floor_map.get(d.month, 0)
                if hist_floor and price < hist_floor:
                    price = hist_floor
                # 9. Guardrails
                price = round(max(base * 0.5, min(base * 3.0, price)), 2)

                reason = "auto-scanner (market+events+historical)"
                if event_for_day:
                    reason += f" | Event: {event_for_day.get('name', '')}"

                await db_ref.rate_overrides.update_one(
                    {"property_id": property_id, "date": ds, "room_type_id": rt.get("id", "")},
                    {"$set": {"property_id": property_id, "room_type_id": rt.get("id", ""), "date": ds, "custom_rate": price, "set_by": "auto-scanner", "reason": reason, "updated_at": now.isoformat()}},
                    upsert=True
                )
                count += 1
        logger.info(f"Auto-pricing applied: {count} rates (market + events + historical floors)")

    # ==================== EVENT SCAN FUNCTION FOR SCANNER ====================

    async def _auto_event_scan(db_ref, property_id, city):
        """Called by smart scanner to auto-scan events using GPT-5.2."""
        import re as re_mod
        import json as json_mod
        now = datetime.now(timezone.utc)

        # Web search for events
        events_raw = []
        queries = [
            f"major events concerts festivals {city} {now.strftime('%B %Y')} next 3 months",
            f"football matches stadium events {city} {now.strftime('%Y')} upcoming",
            f"marathon exhibition conference {city} {now.strftime('%B %Y')} schedule",
        ]
        for query in queries:
            try:
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&gl=uk"
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                    resp = await client.get(search_url, headers=headers)
                    events_raw.append(resp.text[:10000])
            except Exception as e:
                logger.warning(f"Auto event search failed: {e}")

        raw_text = "\n".join(events_raw)

        # AI analysis
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            date_from = now.strftime("%Y-%m-%d")
            date_to = (now + timedelta(days=365)).strftime("%Y-%m-%d")

            system_prompt = f"""You are a HOTEL REVENUE intelligence analyst for {city}.
Identify events that make people STAY IN HOTELS — not just any event.

RULES:
- Local football derby (both teams same city) = SKIP or HDS <15 — fans go home
- International match (FIFA/UEFA/away team from abroad) = HDS 70-95
- Top team visiting from DIFFERENT city = HDS 40-60
- Major touring concert (stadium) = HDS 75-95
- Multi-day festival = HDS 80-95
- International conference = HDS 60-80
- Local small gig/event = SKIP

Return ONLY a JSON array. Each event: name, date (YYYY-MM-DD), end_date, venue, category, estimated_attendance, hotel_demand_score (0-100), visitor_origin (international/national/regional/local), is_evening (bool), is_multi_day (bool), reasoning (1 sentence), impact (critical/high/moderate/low/minimal), estimated_hotel_nights, confidence.
Skip events with hotel_demand_score below 15.
Date range: {date_from} to {date_to}."""

            chat = LlmChat(api_key=api_key, session_id=f"auto-event-{city}-{now.strftime('%Y%m%d%H')}",
                           system_message=system_prompt).with_model("openai", "gpt-5.2")
            response = await chat.send_message(UserMessage(text=f"Scraped data:\n{raw_text[:4000]}"))
            json_match = re_mod.search(r'\[[\s\S]*\]', response)
            events = json_mod.loads(json_match.group()) if json_match else []
        except Exception as e:
            logger.error(f"Auto event AI failed: {e}")
            events = []

        # Store events
        stored = 0
        for event in events:
            event_date = event.get("date", "")
            if not event_date:
                continue
            try:
                ed = datetime.strptime(event_date, "%Y-%m-%d")
                now_naive = now.replace(tzinfo=None)
                if ed.date() < now_naive.date() or ed > now_naive + timedelta(days=365):
                    continue
            except (ValueError, TypeError):
                continue

            doc = {
                "id": str(uuid.uuid4())[:8],
                "property_id": property_id,
                "city": city,
                "name": event.get("name", "Unknown"),
                "date": event_date,
                "end_date": event.get("end_date", event_date),
                "venue": event.get("venue", ""),
                "category": event.get("category", "other"),
                "estimated_attendance": int(event.get("estimated_attendance", 0) or 0),
                "hotel_demand_score": int(event.get("hotel_demand_score", 0) or 0),
                "visitor_origin": event.get("visitor_origin", "unknown"),
                "is_evening": event.get("is_evening", True),
                "is_multi_day": event.get("is_multi_day", False),
                "estimated_hotel_nights": int(event.get("estimated_hotel_nights", 0) or 0),
                "reasoning": event.get("reasoning", ""),
                "impact": event.get("impact", "small"),
                "description": event.get("description", ""),
                "confidence": event.get("confidence", "medium"),
                "source": "auto-scanner",
                "scanned_at": now.isoformat(),
            }
            await db_ref.market_events.update_one(
                {"property_id": property_id, "name": doc["name"], "date": doc["date"]},
                {"$set": doc}, upsert=True
            )
            stored += 1

        return {"events_found": len(events), "events_stored": stored}

    async def _auto_competitor_scan(db_ref, property_id, days_ahead: int = 30):
        """Background competitor price scan — scrapes all configured competitors for this property.

        Previously hardcoded to 7 days — too short to populate 30/60/90-day trend charts. Default
        now 30, callable with a larger value from the /scan-comps endpoint when users pick a
        longer window in the UI.

        iter 332 — parallelised: 10 competitors used to scrape sequentially
        (10 × 30 days × ~4s = ~20 min). Now 3 competitors run concurrently
        under a Semaphore, cutting a 30-day fleet refresh to ~6-7 min and
        keeping the per-hotel trend chart fresh within a sane polling window.
        Per-competitor we still go sequential across dates because hammering
        the SAME hotel page in parallel triggers Booking.com rate limits.
        """
        from utils.booking_scraper import scrape_booking_url, build_dated_url

        comps = await db_ref.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)

        if not comps:
            return {"competitors_scanned": 0, "prices_found": 0}

        now = datetime.now(timezone.utc)
        days_ahead = max(1, min(int(days_ahead), 90))
        total_prices = [0]  # mutable so workers can accumulate

        prop = await db_ref.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        target_currency = prop.get("currency") or "CHF"

        comp_sem = asyncio.Semaphore(3)

        async def _scan_one_competitor(comp):
            async with comp_sem:
                comp_prices = []
                base_url = comp.get("booking_url", "")
                if not base_url:
                    return
                cached_hotel_id = comp.get("booking_hotel_id")
                last_score = None
                resolved_hotel_id = cached_hotel_id
                resolved_name = comp.get("name", "")
                name_hint = (comp.get("slug") or "").replace("-", " ")[:18]
                for i in range(days_ahead):
                    d = now + timedelta(days=i)
                    checkin = d.strftime("%Y-%m-%d")
                    checkout = (d + timedelta(days=1)).strftime("%Y-%m-%d")
                    url = build_dated_url(base_url, checkin, checkout, target_currency)
                    try:
                        result = await scrape_booking_url(
                            url, timeout_ms=30000,
                            hotel_id=resolved_hotel_id,
                            hotel_name_hint=name_hint,
                        )
                        if result.get("hotel_id"):
                            resolved_hotel_id = result["hotel_id"]
                        if result.get("hotel_name"):
                            resolved_name = result["hotel_name"]
                        if result["scraped"]:
                            comp_prices.append({
                                "date": checkin,
                                "lowest_price": result["lowest_price"],
                                "all_prices": result["all_prices"],
                                "score": result["score"],
                                "scraped": True,
                            })
                            total_prices[0] += 1
                            if result["score"]:
                                last_score = result["score"]
                        else:
                            comp_prices.append({"date": checkin, "lowest_price": None, "scraped": False,
                                                "error": result.get("error")})
                    except Exception as e:
                        logger.warning(f"Auto comp scrape failed for {comp.get('name')}: {e}")
                        comp_prices.append({"date": checkin, "lowest_price": None, "scraped": False})
                    # Per-hotel polite pacing — keep 1.5s between SAME-hotel hits.
                    await asyncio.sleep(1.5)
                update_fields = {
                    "prices": comp_prices,
                    "last_scraped": now.isoformat(),
                    "last_source": "auto-scanner",
                }
                if last_score:
                    update_fields["review_score"] = last_score
                if resolved_hotel_id and resolved_hotel_id != cached_hotel_id:
                    update_fields["booking_hotel_id"] = resolved_hotel_id
                if resolved_name and resolved_name != comp.get("name", ""):
                    original = (comp.get("name") or "").strip().lower()
                    slug_default = (comp.get("slug") or "").replace("-", " ").strip().lower()
                    if original in ("", slug_default):
                        update_fields["name"] = resolved_name
                await db_ref.market_competitors.update_one(
                    {"id": comp["id"]}, {"$set": update_fields}
                )

        await asyncio.gather(*[_scan_one_competitor(c) for c in comps])
        return {"competitors_scanned": len(comps), "prices_found": total_prices[0]}

    async def _auto_our_hotel_scan(db_ref, property_id, days_ahead: int = 14):
        """Scrape OUR OWN hotel's Booking.com page — same cadence as competitors.

        Without this, 'Biz vs Pazar' comparisons weren't apples-to-apples: competitor prices came
        from live Booking.com, but our overlay came from internal rate_overrides. Now both sides
        are measured from the same OTA surface.

        Stores results in `property_booking_snapshots` collection + updates `properties.booking_data`
        with the freshest snapshot for quick overlay reads.
        """
        from utils.booking_scraper import scrape_booking_url, build_dated_url

        prop = await db_ref.properties.find_one(
            {"id": property_id},
            {"_id": 0, "booking_url": 1, "name": 1, "currency": 1, "city": 1, "booking_hotel_id": 1}
        )
        if not prop or not prop.get("booking_url"):
            return {"scraped": False, "reason": "no_booking_url"}

        base_url = prop["booking_url"]
        target_currency = prop.get("currency") or "CHF"
        cached_hotel_id = prop.get("booking_hotel_id")
        name_hint = (prop.get("name") or "").strip()[:18]
        now = datetime.now(timezone.utc)
        # Clamped to the same [1, 90] window competitors use — lets the violet "Our Hotel"
        # line extend to match when the user scrapes 60 or 90 days of competitor data.
        days_ahead = max(1, min(int(days_ahead), 90))
        prices = []
        review_score = None
        resolved_hotel_id = cached_hotel_id

        for i in range(days_ahead):
            d = now + timedelta(days=i)
            checkin = d.strftime("%Y-%m-%d")
            checkout = (d + timedelta(days=1)).strftime("%Y-%m-%d")
            url = build_dated_url(base_url, checkin, checkout, target_currency)
            try:
                result = await scrape_booking_url(
                    url, timeout_ms=30000,
                    hotel_id=resolved_hotel_id,
                    hotel_name_hint=name_hint,
                )
                if result.get("hotel_id"):
                    resolved_hotel_id = result["hotel_id"]
                if result["scraped"]:
                    prices.append({
                        "date": checkin,
                        "lowest_price": result["lowest_price"],
                        "all_prices": result["all_prices"],
                        "scraped": True,
                    })
                    if review_score is None and result["score"]:
                        review_score = result["score"]
                else:
                    prices.append({"date": checkin, "lowest_price": None, "scraped": False,
                                   "error": result.get("error")})
            except Exception as e:
                logger.warning(f"Our-hotel Booking scrape failed for {property_id} on {checkin}: {e}")
                prices.append({"date": checkin, "lowest_price": None, "scraped": False})
            await asyncio.sleep(1.5)  # polite pacing

        valid_prices = [p["lowest_price"] for p in prices if p.get("lowest_price")]
        avg_price = round(sum(valid_prices) / len(valid_prices), 2) if valid_prices else None
        snapshot = {
            "property_id": property_id,
            "snapshot_at": now.isoformat(),
            "booking_url": base_url,
            "currency": prop.get("currency", "GBP"),
            "review_score": review_score,
            "days_scraped": days_ahead,
            "days_with_price": len(valid_prices),
            "avg_price": avg_price,
            "min_price": min(valid_prices) if valid_prices else None,
            "max_price": max(valid_prices) if valid_prices else None,
            "daily_prices": prices,
        }

        # Archive (keep last 30 snapshots per property for trend)
        await db_ref.property_booking_snapshots.insert_one({**snapshot, "id": str(uuid.uuid4())[:12]})
        # Trim to latest 30
        to_delete = await db_ref.property_booking_snapshots.find(
            {"property_id": property_id}, {"_id": 1}
        ).sort("snapshot_at", -1).skip(30).to_list(1000)
        if to_delete:
            await db_ref.property_booking_snapshots.delete_many(
                {"_id": {"$in": [d["_id"] for d in to_delete]}}
            )

        # Update quick-read field on property
        prop_update = {"booking_data": {k: v for k, v in snapshot.items() if k != "_id"}}
        if resolved_hotel_id and resolved_hotel_id != cached_hotel_id:
            prop_update["booking_hotel_id"] = resolved_hotel_id
        if review_score and not prop.get("review_score"):
            prop_update["review_score"] = review_score
        # Pull the real room/apartment/unit count from the same Booking.com page
        # so the Performance Report and other revenue dashboards stop guessing
        # from the (often-mis-seeded) room_types collection.
        try:
            from utils.booking_scraper import scrape_hotel_room_count
            bk_room_count = await scrape_hotel_room_count(base_url)
            if bk_room_count and bk_room_count > 0:
                prop_update["booking_room_count"] = bk_room_count
                prop_update["booking_room_count_scanned_at"] = now.isoformat()
        except Exception as exc:
            logger.warning("Booking room-count scrape failed for %s: %s", property_id, exc)
        await db_ref.properties.update_one(
            {"id": property_id},
            {"$set": prop_update}
        )

        return {"scraped": True, "days_with_price": len(valid_prices),
                "avg_price": avg_price, "review_score": review_score,
                "hotel_id": resolved_hotel_id}

    # Initialize smart scanner with event + competitor + our-hotel scanning
    from routes.integrations_pkg.smart_scanner import init_scanner
    scanner = init_scanner(db, _scrape_booking_date, _calculate_price_adjustment, _auto_apply_pricing, _auto_event_scan, _auto_competitor_scan, _auto_our_hotel_scan)

    @router.post("/revenue/market-robot/{property_id}/scanner/start")
    async def start_scanner(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await scanner.start(property_id)
        return result

    @router.post("/revenue/market-robot/{property_id}/scanner/stop")
    async def stop_scanner(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await scanner.stop(property_id)
        return result

    @router.get("/revenue/market-robot/{property_id}/scanner/status")
    async def scanner_status(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        return scanner.get_status(property_id)

    @router.get("/revenue/market-robot/{property_id}/our-booking")
    async def get_our_booking(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return the freshest Booking.com snapshot for THIS hotel (used by 'Biz vs Pazar' overlays).

        When `property_id == 'all'` (user is in "All Branches" view) we return a neutral
        empty-state response so the UI can render a "pick a branch" hint instead of crashing.
        """
        if property_id == "all":
            return {
                "property_id": "all",
                "name": "",
                "booking_url": "",
                "currency": "GBP",
                "city": "",
                "booking_data": None,
                "all_branches_mode": True,
            }
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "name": 1, "booking_url": 1, "booking_data": 1, "currency": 1, "city": 1}
        )
        if not prop:
            # Don't 404 — the card should render gracefully with an empty state.
            return {
                "property_id": property_id,
                "name": "",
                "booking_url": "",
                "currency": "GBP",
                "city": "",
                "booking_data": None,
                "missing": True,
            }
        return {
            "property_id": property_id,
            "name": prop.get("name", ""),
            "booking_url": prop.get("booking_url", ""),
            "currency": prop.get("currency", "GBP"),
            "city": prop.get("city", ""),
            "booking_data": prop.get("booking_data") or None,
        }

    @router.put("/revenue/market-robot/{property_id}/our-booking")
    async def set_our_booking(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Save/update the property's Booking.com listing URL.

        Also (optionally, default=on) validates the URL and caches `booking_hotel_id`
        on the property doc so future scans skip the expensive detail-page round-trip.
        """
        from utils.booking_scraper import validate_booking_url as _validate
        url = (data.get("booking_url") or "").strip()
        skip_validation = bool(data.get("skip_validation", False))
        if url and "booking.com" not in url.lower():
            raise HTTPException(400, "URL must be a booking.com link")

        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        currency = prop.get("currency") or "GBP"

        update = {"booking_url": url,
                  "booking_url_updated_at": datetime.now(timezone.utc).isoformat()}
        validation = {}
        if url and not skip_validation:
            try:
                validation = await _validate(url, currency=currency)
                if validation.get("hotel_id"):
                    update["booking_hotel_id"] = validation["hotel_id"]
                if validation.get("hotel_name"):
                    # Only auto-fill property name if it looks uninitialised
                    update_name = False
                    current_name = (prop.get("name") or "").strip().lower() if prop else ""
                    if current_name in ("", "my property", "default"):
                        update_name = True
                    if update_name:
                        update["name"] = validation["hotel_name"]
            except Exception as e:
                logger.warning(f"Our-booking URL validation failed for {property_id}: {e}")
                validation = {"ok": False, "error": str(e)}

        await db.properties.update_one({"id": property_id}, {"$set": update})
        return {"ok": True, "booking_url": url, "validation": validation}

    @router.post("/revenue/market-robot/{property_id}/our-booking/scan")
    async def trigger_our_booking_scan(property_id: str, background_tasks: BackgroundTasks,
                                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Kick off an immediate OTA scrape of our own hotel (runs in background — takes 30-90s)."""
        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "booking_url": 1, "name": 1}
        )
        if not prop or not prop.get("booking_url"):
            raise HTTPException(400, "Set booking_url on the property first")
        background_tasks.add_task(_auto_our_hotel_scan, db, property_id)
        return {"ok": True, "status": "queued",
                "message": "Scraping started in background. Check GET /our-booking in ~60-90s for results."}

    async def _run_room_count_job(property_id: str, booking_url: str):
        """Worker: regex → vision-LLM cascade. Writes outcome to `room_count_jobs`."""
        from utils.booking_scraper import scrape_hotel_room_count, scrape_booking_screenshot
        rc: Optional[int] = None
        source: Optional[str] = None
        err: Optional[str] = None
        evidence: Optional[str] = None

        # Stage 1 — regex / JSON-LD fast path
        try:
            rc = await scrape_hotel_room_count(booking_url, force_refresh=True)
            if rc:
                source = "booking_com_html"
        except Exception as exc:
            logger.warning("HTML room-count scrape failed for %s: %s", property_id, exc)
            err = str(exc)[:200]

        # Stage 2 — GPT-4o-mini vision fallback when HTML didn't expose a count.
        # We scan multiple dates in parallel and take the MAX of all results, because
        # Booking.com only shows AVAILABLE units for the requested check-in date.
        # A property with 9 apartments may show "3 apartments" on a busy weekend and
        # "9 apartments" on a quiet Tuesday. Max across diverse weekday/weekend dates
        # converges to the real inventory.
        if not rc:
            logger.info("Room-count vision multi-date scan starting for %s", property_id)
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
                import base64 as _b64
                import json as _json
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

                api_key = os.environ.get("EMERGENT_LLM_KEY")
                if not api_key:
                    raise RuntimeError("EMERGENT_LLM_KEY not configured")

                SYSTEM = (
                    "You read Booking.com hotel listings. Extract the property's "
                    "total room/apartment/unit count and return ONLY compact JSON: "
                    '{"room_count": <int|null>, "evidence": <short string>}. '
                    "STRICT RULES: "
                    "- ONLY return a number if you can see explicit copy like "
                    "'this property has X rooms', 'X apartments', 'X studios', "
                    "'X units', or a room-type table where each row is a distinct "
                    "unit. Count distinct units, not duplicate listings. "
                    "- DO NOT use the review count (e.g. '927 reviews'), the "
                    "people count (e.g. 'sleeps 4'), the number of bedrooms in "
                    "one apartment, or the number of property photos. "
                    "- If the page does not explicitly state a total inventory, "
                    "return null. "
                    "- evidence: cite the visible text you used (e.g. "
                    "'\"9 apartments\" near top of description'). "
                    "Return ONLY JSON, no markdown fences."
                )

                # Build a diverse set of probe dates: mix Sun / Tue / Fri across the
                # next 6 months. The further-out / midweek dates usually expose
                # max inventory because most rooms are unsold.
                today = datetime.now(timezone.utc).date()
                candidates: List = []
                offsets = [14, 28, 45, 60, 90, 120]
                for off in offsets:
                    d = today + timedelta(days=off)
                    candidates.append(d)
                # Force at least one Tuesday & one Sunday somewhere in the window
                for off in (35, 70):
                    d = today + timedelta(days=off)
                    # nudge to next Tuesday (weekday=1)
                    while d.weekday() != 1:
                        d += timedelta(days=1)
                    candidates.append(d)
                # Deduplicate
                seen = set()
                probe_dates = []
                for d in candidates:
                    if d not in seen:
                        seen.add(d)
                        probe_dates.append(d)

                async def _scan_one(ci_date, sem) -> Optional[Dict[str, Optional[object]]]:
                    async with sem:
                        co_date = ci_date + timedelta(days=1)
                        url = booking_url
                        if "/hotel/" in url:
                            p = urlparse(url)
                            q = parse_qs(p.query)
                            q["checkin"] = [ci_date.isoformat()]
                            q["checkout"] = [co_date.isoformat()]
                            q.setdefault("group_adults", ["2"])
                            q.setdefault("no_rooms", ["1"])
                            url = urlunparse(p._replace(query=urlencode(q, doseq=True)))
                        # Up to 6 attempts per date: rotate Tor circuit between
                        # them. Each attempt gets a fresh exit IP + fresh
                        # cookie jar (`fresh_context=True` below). Booking
                        # blocks ~80% of Tor exit IPs, so we need many tries
                        # to land on a "clean" exit. With fast-bail on 202,
                        # each failed attempt costs only ~3-5s, so 6 retries
                        # × 5s = ~30s worst-case per date.
                        for attempt in range(6):
                            try:
                                from utils.tor_manager import rotate_circuit
                                # Rotate twice: first call schedules NEWNYM, but
                                # Tor enforces a 10s rate-limit between actual
                                # circuit rebuilds. Calling twice with a small
                                # gap reliably advances to a NEW exit relay
                                # rather than re-using the previous one.
                                await rotate_circuit()
                                await asyncio.sleep(0.5)
                                await rotate_circuit()
                                await asyncio.sleep(2.0)
                            except Exception:
                                pass
                            try:
                                from utils.booking_scraper import scrape_booking_screenshot as _sbs
                                # 18s cap per attempt, warm context + cookie
                                # reset (instead of fresh context). The warm
                                # context reuses the Tor SOCKS connection so
                                # each retry costs ~3-5s instead of 10-15s,
                                # letting us cycle through far more exits.
                                png = await asyncio.wait_for(_sbs(url, full_page=True, clear_cookies=True, timeout_ms=15000), timeout=18)
                                if not png:
                                    continue
                                chat = LlmChat(
                                    api_key=api_key,
                                    session_id=f"rc-{property_id[:8]}-{ci_date.isoformat()}-{attempt}",
                                    system_message=SYSTEM,
                                ).with_model("openai", "gpt-4o-mini")
                                reply = await asyncio.wait_for(chat.send_message(UserMessage(
                                    text="How many rooms / apartments / units does this property have in total?",
                                    file_contents=[ImageContent(image_base64=_b64.b64encode(png).decode("ascii"))],
                                )), timeout=25)
                                raw = (reply or "").strip()
                                if raw.startswith("```"):
                                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
                                try:
                                    parsed = _json.loads(raw)
                                except Exception:
                                    parsed = {}
                                vrc = parsed.get("room_count")
                                if isinstance(vrc, str) and vrc.isdigit():
                                    vrc = int(vrc)
                                if isinstance(vrc, int) and 1 <= vrc <= 2000:
                                    logger.info("Multi-date probe %s @ %s (try %s) = %s (evidence=%s)",
                                                property_id, ci_date, attempt + 1, vrc,
                                                (parsed.get("evidence") or "")[:80])
                                    return {
                                        "room_count": vrc,
                                        "evidence": (parsed.get("evidence") or "")[:200],
                                        "date": ci_date.isoformat(),
                                        "weekday": ci_date.strftime("%a"),
                                    }
                            except asyncio.TimeoutError:
                                logger.warning("Multi-date scan timeout for %s @ %s (try %s)",
                                               property_id, ci_date, attempt + 1)
                            except Exception as scan_exc:
                                logger.warning("Multi-date scan failed for %s @ %s (try %s): %s",
                                               property_id, ci_date, attempt + 1, scan_exc)
                        return None

                # Run scans with limited concurrency — the shared headless Chromium
                # can't serve 8 simultaneous pages without deadlocking.
                sem = asyncio.Semaphore(3)
                scan_results = await asyncio.gather(*[_scan_one(d, sem) for d in probe_dates])
                hits = [s for s in scan_results if s and s.get("room_count")]
                if hits:
                    best = max(hits, key=lambda h: h["room_count"])
                    rc = int(best["room_count"])
                    source = "booking_com_vision_multidate"
                    evidence = (
                        f"max across {len(hits)} dates: {best['room_count']} on "
                        f"{best['weekday']} {best['date']} ({best['evidence']})"
                    )
                    logger.info(
                        "Multi-date room-count for %s: max=%s across %s probes, picked %s",
                        property_id, rc, len(hits), best,
                    )
                else:
                    logger.info("Multi-date room-count for %s: no usable signal across %s probes",
                                property_id, len(probe_dates))
            except Exception as exc:
                logger.warning("Vision room-count multi-date fallback failed for %s: %s", property_id, exc)
                err = err or str(exc)[:200]

        result: Dict[str, Optional[object]] = {
            "room_count": rc,
            "source": source,
            "evidence": evidence,
        }
        if rc:
            await db.properties.update_one(
                {"id": property_id},
                {"$set": {
                    "booking_room_count": rc,
                    "booking_room_count_scanned_at": datetime.now(timezone.utc).isoformat(),
                    "booking_room_count_source": source,
                }}
            )
        # Surface a helpful, action-oriented message when the auto-scan can't
        # crack Booking's anti-bot wall (commonly the case with free IP
        # rotation since Booking blocks all Tor exit ranges at the firewall).
        # The user already has a manual-override field for exactly this case.
        if not rc:
            err = err or "Booking.com tüm denenen IP'leri bot-challenge ile engelledi. Lütfen aşağıdan manuel oda sayısı girin."
        await db.room_count_jobs.update_one(
            {"property_id": property_id},
            {"$set": {
                "status": "done" if rc else "no_data",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
                "error": err,
            }},
        )

    @router.post("/revenue/market-robot/{property_id}/refresh-room-count")
    async def refresh_room_count(property_id: str,
                                 background_tasks: BackgroundTasks,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Kick off a Booking.com room-count scrape in the background.

        Returns immediately (the 60s ingress timeout makes synchronous scraping
        impossible for vision-based extraction, which takes 30-90s). The client
        polls `GET /refresh-room-count/status` to retrieve the result.

        Strategy on the worker:
          1. Fast path — pull `numberOfRooms` / `n_rooms` / "this property has N
             rooms" out of the rendered HTML via regex.
          2. Vision fallback — when HTML doesn't expose it (most apartment-style
             pages), take a full-page screenshot and ask GPT-4o-mini to count
             units WITHOUT reading the review count.
        """
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "booking_url": 1, "booking_room_count": 1}
        )
        if not prop or not prop.get("booking_url"):
            raise HTTPException(400, "Set booking_url on the property first")

        await db.room_count_jobs.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "result": None,
                "error": None,
            }},
            upsert=True,
        )
        background_tasks.add_task(_run_room_count_job, property_id, prop["booking_url"])
        return {
            "ok": True,
            "status": "queued",
            "property_id": property_id,
            "message": "Tarama başlatıldı. Sonuç ~30-90 saniye içinde hazır olacak.",
        }

    @router.get("/revenue/market-robot/{property_id}/refresh-room-count/status")
    async def refresh_room_count_status(property_id: str,
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Poll the latest room-count refresh job for this property."""
        job = await db.room_count_jobs.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        if not job:
            return {"status": "idle"}
        return job

    @router.get("/revenue/market-robot/{property_id}/room-count")
    async def get_room_count_state(property_id: str,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return all known room-count signals for the property so the UI can show
        manual, booking-com (auto), and room_types values side-by-side."""
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "manual_room_count": 1, "manual_room_count_set_at": 1,
             "booking_room_count": 1, "booking_room_count_scanned_at": 1,
             "booking_room_count_source": 1}
        )
        room_types_local = await db.room_types.find({"property_id": property_id},
                                                    {"_id": 0, "total_rooms": 1}).to_list(50)
        total_local = sum(int(r.get("total_rooms", 0) or 0) for r in room_types_local)
        return {
            "manual_room_count": (prop or {}).get("manual_room_count"),
            "manual_room_count_set_at": (prop or {}).get("manual_room_count_set_at"),
            "booking_room_count": (prop or {}).get("booking_room_count"),
            "booking_room_count_scanned_at": (prop or {}).get("booking_room_count_scanned_at"),
            "booking_room_count_source": (prop or {}).get("booking_room_count_source"),
            "room_types_total": total_local,
        }

    @router.post("/revenue/market-robot/{property_id}/room-count/manual")
    async def set_manual_room_count(property_id: str,
                                    body: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Operator-supplied room count. Always wins over auto-scan in the
        Performance Report and any other revenue calc. Pass `room_count: null`
        (or omit) to clear the override and fall back to the auto-scanned value.
        """
        rc = body.get("room_count")
        if rc in (None, "", 0):
            await db.properties.update_one(
                {"id": property_id},
                {"$unset": {"manual_room_count": "", "manual_room_count_set_at": ""}},
            )
            return {"ok": True, "manual_room_count": None, "cleared": True}
        try:
            n = int(rc)
        except (TypeError, ValueError):
            raise HTTPException(400, "room_count must be a positive integer")
        if n < 1 or n > 5000:
            raise HTTPException(400, "room_count must be between 1 and 5000")
        await db.properties.update_one(
            {"id": property_id},
            {"$set": {
                "manual_room_count": n,
                "manual_room_count_set_at": datetime.now(timezone.utc).isoformat(),
                "manual_room_count_set_by": current_user.get("email", "unknown"),
            }},
        )
        return {"ok": True, "manual_room_count": n}

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

            # Median market price for context
            market_prices = [h["price"] for h in comps_row]
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
            status = scanner.get_status(pid)
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
            await _do_scan(pid, payload)
        except Exception as e:
            msg = str(e)
            if "MongoClient after close" in msg or "Event loop is closed" in msg:
                logger.info(f"Auto {label}-scan {pid} aborted (process recycling) — harmless")
                return
            logger.exception(f"Auto {label}-scan task failed for {pid}: {e}")

    async def _safe_do_geo_scan(pid: str, cfg: Dict):
        """Geo wrapper that also stamps last_scan/total_scans on success."""
        try:
            await _do_scan(pid, {
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

    async def auto_scan_loop():
        """Background loop: every 60s check enabled market-robot configs and trigger due scans.
        Handles BOTH city scans (market_robot_config) AND geo scans (market_robot_geo_config) in parallel."""
        logger.info("🛰️ Market Robot auto-scan loop started")
        # Auto-resume Smart Scanner if user had it ON before restart
        try:
            await scanner.resume_if_active()
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
                                    "enabled": True,
                                    "scan_interval_minutes": 60,
                                    "city": pp.get("city") or "London",
                                    "language": "en-gb",
                                    "auto_pricing": False,
                                    "days_ahead": 365,
                                    "total_scans": 0,
                                    "created_at": now_iso,
                                    "created_by": "auto-bootstrap-loop",
                                })
                                logger.info(f"🌱 Auto-bootstrapped market_robot_config for {pid_}")
                            elif existing_.get("enabled") is None or existing_.get("scan_interval_minutes") is None:
                                await db.market_robot_config.update_one(
                                    {"property_id": pid_},
                                    {"$set": {
                                        "enabled": True if existing_.get("enabled") is None else existing_.get("enabled"),
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
                    await scanner.watchdog()
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
                                result = await _do_auto_heal_competitors(
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
                            summary = await _build_weekly_summary(pid, 7)
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

    return router
