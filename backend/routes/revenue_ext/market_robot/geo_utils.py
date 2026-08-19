"""Coğrafi arz sayımı ve fiyat istatistiği yardımcıları (OSM/Google Places/Booking kart sayacı)."""
import re
import os
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

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

