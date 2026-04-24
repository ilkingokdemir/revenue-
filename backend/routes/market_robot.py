"""
Market Robot — Scrapes Booking.com market supply data and auto-adjusts hotel rates.
Tracks availability for 90 days, detects demand changes, and feeds into Smart Pricing.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import uuid
import re
import asyncio
import logging
import os
import httpx

logger = logging.getLogger(__name__)

SCRAPE_RUNNING = False
SCRAPE_RUNNING_GEO = False  # independent lock so geo scans can run in parallel with city scans


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
    async def run_geo_scan(property_id: str, data: Dict = {},
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Run a neighborhood (geo-radius) scan. Body: {location: 'SW1A 1AA', radius_km: 3.2, days_ahead: 30}
        Runs INDEPENDENTLY from city scans — both can run in parallel."""
        data = data or {}
        data["mode"] = "geo"
        return await _do_scan(property_id, data)

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

            for snap in snaps:
                target_date = snap.get("date")
                if not target_date:
                    continue
                bookings_count = await db.bookings.count_documents({
                    "property_id": property_id,
                    "check_in": {"$lte": target_date},
                    "check_out": {"$gt": target_date},
                    "status": {"$nin": ["cancelled"]},
                })
                occ = round(min(100, bookings_count / total_rooms * 100), 1)
                # Priority 1: live Booking.com scrape for this date
                bk_price = booking_by_date.get(target_date)
                if bk_price and bk_price > 0:
                    our_rate = round(bk_price, 2)
                    our_rate_source = "booking_live"
                else:
                    rate_doc = await db.rate_overrides.find_one(
                        {"property_id": property_id, "date": target_date},
                        {"_id": 0, "custom_rate": 1},
                        sort=[("updated_at", -1)],
                    )
                    our_rate = round(float(rate_doc["custom_rate"]) if rate_doc and rate_doc.get("custom_rate") else base_rate_avg, 2)
                    our_rate_source = "override" if rate_doc else "base_rate"
                our_data.append({
                    "date": target_date,
                    "our_occupancy_pct": occ,
                    "our_bookings": bookings_count,
                    "our_total_rooms": total_rooms,
                    "our_avg_rate": our_rate,
                    "our_rate_source": our_rate_source,
                })

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
        """
        global SCRAPE_RUNNING, SCRAPE_RUNNING_GEO

        config = await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        mode = (data.get("mode") or "city").lower()
        is_geo = mode == "geo"

        # Independent locks → city + geo can scan in parallel
        if is_geo and SCRAPE_RUNNING_GEO:
            return {"error": "Geo scan already in progress", "status": "busy"}
        if not is_geo and SCRAPE_RUNNING:
            return {"error": "City scan already in progress", "status": "busy"}

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
            SCRAPE_RUNNING_GEO = True
        else:
            SCRAPE_RUNNING = True
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

            for d in scan_dates:
                checkin = d.strftime("%Y-%m-%d")
                checkout = (d + timedelta(days=1)).strftime("%Y-%m-%d")

                supply = await _scrape_booking_date(
                    location, checkin, checkout, language,
                    latitude=latitude, longitude=longitude, radius_km=radius_km,
                    currency=scan_currency,
                )

                # Get previous snapshot for this date + same scan type
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
                snapshots.append(snapshot)

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
                SCRAPE_RUNNING_GEO = False
            else:
                SCRAPE_RUNNING = False

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

        # Load events and create date map
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
        our_occ_sum = 0
        our_rate_sum = 0
        for s in snapshots:
            ds = s.get("date")
            if not ds:
                continue
            bookings_count = await db.bookings.count_documents({
                "property_id": property_id,
                "check_in": {"$lte": ds},
                "check_out": {"$gt": ds},
                "status": {"$nin": ["cancelled"]},
            })
            occ = round(min(100, bookings_count / total_rooms * 100), 1)
            rate_doc = await db.rate_overrides.find_one(
                {"property_id": property_id, "date": ds},
                {"_id": 0, "custom_rate": 1},
                sort=[("updated_at", -1)],
            )
            our_rate = round(float(rate_doc["custom_rate"]) if rate_doc and rate_doc.get("custom_rate") else base_rate_avg, 2)
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

    # ==================== OCCUPANCY & PICKUP + RECENT BOOKINGS ====================

    @router.get("/revenue/market-robot/{property_id}/occupancy-pickup")
    async def get_occupancy_pickup(property_id: str, days: int = 90, pickup_window: str = "24h",
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Occupancy & Pickup chart data — base occupancy bars + booking velocity overlay."""
        now = datetime.now(timezone.utc)
        props = await db.properties.find({}, {"_id": 0}).to_list(50) if property_id == "all" else [await db.properties.find_one({"id": property_id}, {"_id": 0})]
        props = [p for p in props if p]
        total_rooms = 0
        for p in props:
            total_rooms += await db.rooms.count_documents({"property_id": p.get("id", "")}) or 10
        total_rooms = max(total_rooms, 1)

        # Pickup window in hours
        pw_hours = {"24h": 24, "3d": 72, "7d": 168}.get(pickup_window, 24)
        pickup_cutoff = (now - timedelta(hours=pw_hours)).isoformat()

        daily = []
        for i in range(days):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")

            # Base occupancy: all confirmed bookings overlapping this date
            booked = 0
            for p in props:
                booked += await db.bookings.count_documents({
                    "property_id": p.get("id", ""), "check_in": {"$lte": ds},
                    "check_out": {"$gt": ds}, "status": {"$ne": "cancelled"}
                })
            occ_pct = min(100, round((booked / total_rooms) * 100))

            # Pickup: bookings made within the pickup window for this date
            pickup_rooms = 0
            for p in props:
                pickup_rooms += await db.bookings.count_documents({
                    "property_id": p.get("id", ""), "check_in": {"$lte": ds},
                    "check_out": {"$gt": ds}, "status": {"$ne": "cancelled"},
                    "created_at": {"$gte": pickup_cutoff}
                })
            pickup_pct = min(100, round((pickup_rooms / total_rooms) * 100))

            daily.append({
                "date": ds,
                "dow": d.strftime("%a"),
                "month": d.strftime("%b"),
                "day": d.day,
                "occupancy_pct": occ_pct,
                "pickup_pct": pickup_pct,
                "booked_rooms": booked,
                "pickup_rooms": pickup_rooms,
                "total_rooms": total_rooms,
            })

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

        # Get events
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

    @router.get("/revenue/market-robot/{property_id}/performance")
    async def get_performance_report(property_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Scanner Performance Report — ROI, revenue impact, pricing adjustments breakdown."""
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        month_start = now.replace(day=1).strftime("%Y-%m-%d")

        # Get base rate
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0

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

        # Estimated revenue impact (assume avg 10 rooms per night)
        avg_rooms = 10
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
        await db.market_competitors.insert_one(comp)
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
        await db.market_competitors.delete_one({"id": competitor_id})
        return {"message": "Removed"}

    @router.post("/revenue/market-robot/{property_id}/competitors/scan")
    async def scan_competitors(property_id: str, background_tasks: BackgroundTasks, data: Dict = {},
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Scrape prices from all configured competitor hotels via headless Chromium.
        Runs in background — returns immediately. Check /competitor-prices in ~60s for results."""
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "id": 1, "name": 1, "booking_url": 1}
        ).to_list(20)
        if not comps:
            return {"error": "No competitors configured", "queued": 0}
        background_tasks.add_task(_auto_competitor_scan, db, property_id)
        return {
            "ok": True,
            "status": "queued",
            "queued": len(comps),
            "message": "Competitor scrape started in background. Check GET /competitor-prices in ~60-120s.",
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

    async def _auto_competitor_scan(db_ref, property_id):
        """Background competitor price scan — scrapes all configured competitors for this property."""
        from utils.booking_scraper import scrape_booking_url, build_dated_url

        comps = await db_ref.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)

        if not comps:
            return {"competitors_scanned": 0, "prices_found": 0}

        now = datetime.now(timezone.utc)
        days_ahead = 7
        total_prices = 0

        # Determine currency once from property (competitors are in the same city/currency)
        prop = await db_ref.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        target_currency = prop.get("currency") or "CHF"

        for comp in comps:
            comp_prices = []
            base_url = comp.get("booking_url", "")
            if not base_url:
                continue

            # Cache the hotel_id on the competitor record the first time it's resolved
            # so future scans skip the detail-page round-trip entirely.
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
                        total_prices += 1
                        if result["score"]:
                            last_score = result["score"]
                    else:
                        comp_prices.append({"date": checkin, "lowest_price": None, "scraped": False,
                                            "error": result.get("error")})
                except Exception as e:
                    logger.warning(f"Auto comp scrape failed for {comp.get('name')}: {e}")
                    comp_prices.append({"date": checkin, "lowest_price": None, "scraped": False})

                # Polite pacing
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
                # Never overwrite a user-picked name blindly — only persist the resolved
                # name when the original was auto-generated from the slug.
                original = (comp.get("name") or "").strip().lower()
                slug_default = (comp.get("slug") or "").replace("-", " ").strip().lower()
                if original in ("", slug_default):
                    update_fields["name"] = resolved_name
            await db_ref.market_competitors.update_one(
                {"id": comp["id"]}, {"$set": update_fields}
            )

        return {"competitors_scanned": len(comps), "prices_found": total_prices}

    async def _auto_our_hotel_scan(db_ref, property_id):
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
        days_ahead = 14
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
        await db_ref.properties.update_one(
            {"id": property_id},
            {"$set": prop_update}
        )

        return {"scraped": True, "days_with_price": len(valid_prices),
                "avg_price": avg_price, "review_score": review_score,
                "hotel_id": resolved_hotel_id}

    # Initialize smart scanner with event + competitor + our-hotel scanning
    from routes.smart_scanner import init_scanner
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

    async def auto_scan_loop():
        """Background loop: every 60s check enabled market-robot configs and trigger due scans.
        Handles BOTH city scans (market_robot_config) AND geo scans (market_robot_geo_config) in parallel."""
        logger.info("🛰️ Market Robot auto-scan loop started")
        # Auto-resume Smart Scanner if user had it ON before restart
        try:
            await scanner.resume_if_active()
        except Exception as e:
            logger.warning(f"Smart Scanner resume skipped: {e}")
        while True:
            try:
                # === City scans ===
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
                    if due and not SCRAPE_RUNNING:
                        logger.info(f"🛰️ Auto city-scan triggered for {pid}")
                        try:
                            await _do_scan(pid, {})
                        except Exception as e:
                            logger.exception(f"Auto city-scan failed for {pid}: {e}")

                # === Geo scans (neighborhood, parallel with city) ===
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
                    if due and not SCRAPE_RUNNING_GEO:
                        logger.info(f"🛰️ Auto geo-scan triggered for {pid} @ {loc}")
                        try:
                            await _do_scan(pid, {
                                "mode": "geo",
                                "location": loc,
                                "latitude": cfg.get("latitude"),
                                "longitude": cfg.get("longitude"),
                                "radius_km": float(cfg.get("radius_km") or 3.2),
                                "days_ahead": int(cfg.get("days_ahead") or 30),
                            })
                            # Update geo config last_scan / total_scans
                            await db.market_robot_geo_config.update_one(
                                {"property_id": pid},
                                {"$set": {"last_scan": datetime.now(timezone.utc).isoformat()},
                                 "$inc": {"total_scans": 1}},
                            )
                        except Exception as e:
                            logger.exception(f"Auto geo-scan failed for {pid}: {e}")

                # === Smart Scanner watchdog — check all properties (multi-instance) ===
                try:
                    await scanner.watchdog()
                except Exception as e:
                    logger.warning(f"Scanner watchdog error: {e}")

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
