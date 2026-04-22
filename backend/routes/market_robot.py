"""
Market Robot — Scrapes Booking.com market supply data and auto-adjusts hotel rates.
Tracks availability for 90 days, detects demand changes, and feeds into Smart Pricing.
"""
from fastapi import APIRouter, Depends
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


def create_market_robot_router(db, require_roles):
    router = APIRouter()

    async def _scrape_booking_date(location: str, checkin: str, checkout: str, language: str = "en-gb",
                                   latitude: Optional[float] = None, longitude: Optional[float] = None,
                                   radius_km: Optional[float] = None):
        """Scrape Booking.com search results. Accepts either free-text location (city/postcode/address)
        OR coordinates+radius for precise geo-radius scanning."""
        # URL params: ss=location for text, or latitude+longitude+nflt=distance for precise geo
        if latitude is not None and longitude is not None and radius_km:
            # Booking.com geo-radius filter: distance in meters
            radius_m = int(radius_km * 1000)
            url = (f"https://www.booking.com/searchresults.{language}.html?"
                   f"ss={location or 'Hotel'}&latitude={latitude}&longitude={longitude}"
                   f"&checkin={checkin}&checkout={checkout}&group_adults=2&no_rooms=1&group_children=0"
                   f"&nflt=distance%3D{radius_m}")
        else:
            url = (f"https://www.booking.com/searchresults.{language}.html?"
                   f"ss={location}&checkin={checkin}&checkout={checkout}"
                   f"&group_adults=2&no_rooms=1&group_children=0")

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

    @router.put("/revenue/market-robot/{property_id}/config")
    async def update_config(property_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        data.pop("_id", None)
        data["property_id"] = property_id
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.market_robot_config.update_one({"property_id": property_id}, {"$set": data}, upsert=True)
        return await db.market_robot_config.find_one({"property_id": property_id}, {"_id": 0})

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

        return {
            "property_id": property_id,
            "snapshots": snaps,
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
            },
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
                }
                await db.market_supply.insert_one(snapshot)
                snapshot.pop("_id", None)
                snapshots.append(snapshot)

            # Auto-pricing (city mode only)
            applied = []
            if auto_pricing and snapshots:
                applied = await _apply_auto_pricing(db, property_id, snapshots)

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
            "status": "completed",
        }

    @router.get("/revenue/market-robot/{property_id}/supply")
    async def get_supply_data(property_id: str, days: int = 30,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get latest supply snapshots with event intelligence overlay."""
        now = datetime.now(timezone.utc)

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
            "summary": {
                "total_dates": len(snapshots),
                "avg_unavailable_pct": avg_unavail,
                "high_demand_days": high_demand_days,
                "low_demand_days": low_demand_days,
                "event_days": event_days,
            },
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

    @router.post("/revenue/market-robot/{property_id}/competitors")
    async def add_competitor(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        booking_url = data.get("booking_url", "").strip()
        name = data.get("name", "").strip()
        if not booking_url:
            return {"error": "Booking.com URL is required"}

        # Extract hotel slug from URL
        slug_match = re.search(r'/hotel/[a-z]{2}/([^.?]+)', booking_url)
        slug = slug_match.group(1) if slug_match else ""

        comp = {
            "id": str(uuid.uuid4())[:8],
            "property_id": property_id,
            "name": name or slug.replace("-", " ").title(),
            "booking_url": booking_url,
            "slug": slug,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "last_scraped": None,
            "prices": [],
        }
        await db.market_competitors.insert_one(comp)
        comp.pop("_id", None)
        return comp

    @router.delete("/revenue/market-robot/competitors/{competitor_id}")
    async def remove_competitor(competitor_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.market_competitors.delete_one({"id": competitor_id})
        return {"message": "Removed"}

    @router.post("/revenue/market-robot/{property_id}/competitors/scan")
    async def scan_competitors(property_id: str, data: Dict = {},
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Scrape prices from all configured competitor hotels."""
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)

        if not comps:
            return {"error": "No competitors configured", "results": []}

        now = datetime.now(timezone.utc)
        days_ahead = int(data.get("days_ahead", 7))
        results = []

        for comp in comps:
            comp_prices = []
            base_url = comp.get("booking_url", "").split("?")[0]
            if not base_url:
                continue

            for i in range(min(days_ahead, 14)):
                d = now + timedelta(days=i)
                checkin = d.strftime("%Y-%m-%d")
                checkout = (d + timedelta(days=1)).strftime("%Y-%m-%d")
                url = f"{base_url}?checkin={checkin}&checkout={checkout}&group_adults=2&no_rooms=1"

                try:
                    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                            "Accept-Language": "en-GB,en;q=0.9",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        }
                        resp = await client.get(url, headers=headers)
                        text = resp.text

                        if resp.status_code == 202 or "challenge" in text[:500].lower():
                            # Blocked — try extracting from meta
                            pass

                        # Extract prices — multiple patterns
                        prices_found = []
                        # Pattern: "$XXX for 1 night" or "£XXX per night"
                        price_matches = re.findall(r'[$£€](\d+(?:,\d+)?)\s*(?:for 1 night|per night)', text)
                        for p in price_matches:
                            prices_found.append(float(p.replace(",", "")))

                        # Pattern: data attribute or JSON
                        json_prices = re.findall(r'"price":\s*"?(\d+(?:\.\d+)?)"?', text)
                        for p in json_prices:
                            val = float(p)
                            if 20 < val < 5000:
                                prices_found.append(val)

                        # Extract review score
                        score_match = re.search(r'Scored\s+([\d.]+)', text)
                        score = float(score_match.group(1)) if score_match else None


                        if prices_found:
                            lowest = min(prices_found)
                            comp_prices.append({
                                "date": checkin,
                                "lowest_price": lowest,
                                "all_prices": sorted(set(prices_found))[:5],
                                "score": score,
                                "scraped": True,
                            })
                        else:
                            comp_prices.append({
                                "date": checkin,
                                "lowest_price": None,
                                "scraped": False,
                            })

                except Exception as e:
                    logger.warning(f"Competitor scrape failed for {comp.get('name')}: {e}")
                    comp_prices.append({"date": checkin, "lowest_price": None, "scraped": False})

            # Update competitor with latest prices
            await db.market_competitors.update_one(
                {"id": comp["id"]},
                {"$set": {
                    "prices": comp_prices,
                    "last_scraped": now.isoformat(),
                }}
            )
            results.append({
                "competitor_id": comp["id"],
                "name": comp.get("name", ""),
                "dates_scraped": len(comp_prices),
                "prices_found": sum(1 for p in comp_prices if p.get("scraped")),
                "prices": comp_prices,
            })

        return {"results": results, "total_competitors": len(results)}

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

    # Initialize smart scanner with event scanning
    from routes.smart_scanner import init_scanner
    scanner = init_scanner(db, _scrape_booking_date, _calculate_price_adjustment, _auto_apply_pricing, _auto_event_scan)

    @router.post("/revenue/market-robot/{property_id}/scanner/start")
    async def start_scanner(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await scanner.start(property_id)
        return result

    @router.post("/revenue/market-robot/{property_id}/scanner/stop")
    async def stop_scanner(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await scanner.stop()
        return result

    @router.get("/revenue/market-robot/{property_id}/scanner/status")
    async def scanner_status(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        return scanner.get_status()

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
            except Exception as e:
                logger.exception(f"Market Robot loop error: {e}")
            await asyncio.sleep(60)

    # Expose for server.py startup
    router.auto_scan_loop = auto_scan_loop

    return router
