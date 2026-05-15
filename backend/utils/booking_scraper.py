"""Playwright-based Booking.com scraper (2026-04 rewrite).

Why the rewrite?
----------------
Booking.com's anti-bot system (`__challenge_...` JS) fires on the *hotel detail page*
(`/hotel/{cc}/{slug}.html`) and silently strips the availability/price table from the
DOM when a datacenter IP or headless signature is detected. The page still renders,
but the "CHF 277"-style rates never appear — leading to empty scrapes and garbage
data in the Market Robot.

The search-results endpoint (`/searchresults.html?dest_id=<HOTEL_ID>&dest_type=hotel`),
by contrast, returns a proper property-card list INCLUDING the freshest "from" rate
for the target hotel — even for headless bots. This is now our primary strategy.

Flow:
  1. `resolve_hotel_id(url)` — visits the /hotel/ detail page ONCE and pulls
     `b_hotel_id` (e.g. 14990420) from the embedded JS state. Cached in-memory
     per process to avoid re-resolving.
  2. `scrape_hotel_pricing(hotel_id, checkin, checkout, currency)` — hits the
     `/searchresults.html?dest_id=<id>&dest_type=hotel` endpoint and parses the
     first `[data-testid="property-card"]` (title match + price extraction).
  3. `scrape_booking_url(url, ...)` — public wrapper: resolves id + scrapes.

Returns `{lowest_price, all_prices, score, hotel_id, hotel_name, scraped, error}`
so callers can store uniform records.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

# Ensure Playwright finds its browsers when backend runs under supervisor (where
# ~/.cache/ms-playwright doesn't exist but /pw-browsers does)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

from playwright.async_api import Browser, async_playwright

logger = logging.getLogger(__name__)

_browser: Optional[Browser] = None
_pw = None
_lock = asyncio.Lock()

# In-process cache: booking_url → hotel_id (Booking's internal dest_id)
_HOTEL_ID_CACHE: Dict[str, str] = {}


async def _get_browser() -> Browser:
    """Returns the shared headless Chromium. Lazy-launched on first use."""
    global _browser, _pw
    if _browser is None or not _browser.is_connected():
        async with _lock:
            if _browser is None or not _browser.is_connected():
                _pw = await async_playwright().start()
                _browser = await _pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                logger.info("Booking scraper: headless Chromium launched")
    return _browser


async def close_browser():
    """Call on process shutdown to free Chromium RAM."""
    global _browser, _pw
    if _browser and _browser.is_connected():
        try:
            await _browser.close()
        except Exception as exc:  # pragma: no cover
            logger.warning("Booking scraper close error: %s", exc)
    if _pw:
        try:
            await _pw.stop()
        except Exception:
            pass
    _browser = None
    _pw = None


_HOTEL_ID_RE = re.compile(r"b_hotel_id(?:\s*:\s*|\s*=\s*)['\"]?(\d{4,12})['\"]?")
_HOTEL_ID_RE_ALT = re.compile(r'"hotel_id"\s+value="(\d{4,12})"')
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
_DEFAULT_HEADERS = {
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.booking.com/",
}


def _normalize_base_url(url: str) -> str:
    """Strip query + fragment so we get a stable cache key per hotel."""
    if not url:
        return ""
    try:
        p = urlparse(url)
        path = p.path
        # Normalize en-gb.html / en.html / de.html suffixes to a single form
        path = re.sub(r"\.[a-z]{2}(?:-[a-z]{2})?\.html$", ".html", path, flags=re.I)
        return f"{p.scheme or 'https'}://{p.netloc or 'www.booking.com'}{path}"
    except Exception:
        return url.split("?")[0].split("#")[0]


def _extract_hotel_slug(url: str) -> str:
    """Return the Booking.com slug portion for human-readable logs (e.g. 'franziskaner-by-centra')."""
    m = re.search(r"/hotel/[a-z]{2}/([a-z0-9\-]+?)\.(?:[a-z]{2}(?:-[a-z]{2})?\.)?html", url or "", re.I)
    return m.group(1) if m else ""


async def resolve_hotel_id(
    booking_url: str,
    *,
    timeout_ms: int = 25000,
    force_refresh: bool = False,
) -> Optional[str]:
    """Return Booking.com's internal hotel dest_id for the given detail URL.

    Strategy: visit the detail page once, pull `b_hotel_id` from the embedded JS.
    Results are cached per-process to avoid re-resolving on every scrape.
    """
    if not booking_url:
        return None
    key = _normalize_base_url(booking_url)
    if not force_refresh and key in _HOTEL_ID_CACHE:
        return _HOTEL_ID_CACHE[key]

    browser = await _get_browser()
    # Retry 2x — first load often hits the __challenge__ redirect which invalidates
    # `page.content()` mid-navigation. The second attempt lands on the warm page.
    last_err: Optional[str] = None
    for attempt in range(2):
        ctx = await browser.new_context(
            user_agent=_UA,
            locale="en-GB",
            viewport={"width": 1280, "height": 900},
            extra_http_headers=_DEFAULT_HEADERS,
        )
        page = await ctx.new_page()
        try:
            await page.goto(booking_url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Challenge page typically redirects within ~2s — wait it out.
            await page.wait_for_timeout(2500)
            try:
                await page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass
            html = await page.content()
            m = _HOTEL_ID_RE.search(html) or _HOTEL_ID_RE_ALT.search(html)
            if m:
                hid = m.group(1)
                _HOTEL_ID_CACHE[key] = hid
                logger.info("Booking scraper: resolved hotel_id=%s for %s", hid, _extract_hotel_slug(booking_url))
                return hid
            # Fallback: look for the id inside any link pointing to searchresults
            m2 = re.search(r"dest_id=(\d{4,12})[^\"']*dest_type=hotel", html)
            if m2:
                hid = m2.group(1)
                _HOTEL_ID_CACHE[key] = hid
                logger.info("Booking scraper: resolved hotel_id=%s (via dest_id fallback) for %s", hid, _extract_hotel_slug(booking_url))
                return hid
            last_err = "no_b_hotel_id_in_html"
        except Exception as exc:
            last_err = str(exc)
        finally:
            try:
                await page.close()
            except Exception:
                pass
            await ctx.close()
        if attempt == 0:
            await asyncio.sleep(1.2)

    # Last-resort fallback: search Booking.com for the slug as a free-text query and
    # grab the first property-card's dest_id. This saves us when the challenge page
    # keeps redirecting.
    slug = _extract_hotel_slug(booking_url)
    if slug:
        try:
            hid = await _find_hotel_id_by_slug(slug)
            if hid:
                _HOTEL_ID_CACHE[key] = hid
                logger.info("Booking scraper: resolved hotel_id=%s (via slug search) for %s", hid, slug)
                return hid
        except Exception as exc:
            logger.warning("Booking scraper: slug-search fallback failed for %s — %s", slug, exc)

    logger.warning("Booking scraper: could not extract hotel_id from %s (last_err=%s)", booking_url, last_err)
    return None


async def _find_hotel_id_by_slug(slug: str, timeout_ms: int = 25000) -> Optional[str]:
    """Fallback resolver: search '<slug>' on Booking's free-text search and grab
    the dest_id of the first result that matches the slug prefix."""
    pretty = slug.replace("-", " ").strip()
    url = f"https://www.booking.com/searchresults.en-gb.html?ss={pretty.replace(' ', '+')}"
    browser = await _get_browser()
    ctx = await browser.new_context(
        user_agent=_UA,
        locale="en-GB",
        viewport={"width": 1280, "height": 900},
        extra_http_headers=_DEFAULT_HEADERS,
    )
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            await page.wait_for_selector('[data-testid="property-card"]', timeout=10000)
        except Exception:
            pass
        hid = await page.evaluate("""
            (slug) => {
                const prefix = slug.replace(/-/g, '-').toLowerCase();
                const cards = document.querySelectorAll('[data-testid="property-card"]');
                for (const c of cards) {
                    const link = c.querySelector('[data-testid="title-link"]')?.href || '';
                    const m = link.match(/\\/hotel\\/[a-z]{2}\\/([a-z0-9-]+)\\./i);
                    if (m && (m[1] === prefix || prefix.startsWith(m[1].substring(0, 14)))) {
                        const m2 = link.match(/hotel_id=(\\d+)/) || link.match(/dest_id=(\\d+)/);
                        if (m2) return m2[1];
                    }
                }
                // Fallback to first card regardless
                const first = cards[0];
                if (first) {
                    const link = first.querySelector('[data-testid="title-link"]')?.href || '';
                    const m2 = link.match(/hotel_id=(\\d+)/) || link.match(/dest_id=(\\d+)/);
                    if (m2) return m2[1];
                }
                return null;
            }
        """, slug)
        if hid:
            return str(hid)
        # Also scan the HTML for any dest_id tied to our slug's path
        html = await page.content()
        m = re.search(rf'/hotel/[a-z]{{2}}/{re.escape(slug)}[^"\']*["\'][^>]*hotel_id=(\d+)', html)
        if m:
            return m.group(1)
        m2 = re.search(rf'hotel_id=(\d+)[^"\']*/hotel/[a-z]{{2}}/{re.escape(slug)}', html)
        if m2:
            return m2.group(1)
        return None
    finally:
        try:
            await page.close()
        except Exception:
            pass
        await ctx.close()


def _search_url(hotel_id: str, checkin: str, checkout: str, currency: Optional[str], language: str = "en-gb") -> str:
    params = [
        f"dest_id={hotel_id}",
        "dest_type=hotel",
        f"checkin={checkin}",
        f"checkout={checkout}",
        "group_adults=2",
        "no_rooms=1",
        "group_children=0",
    ]
    if currency:
        params.append(f"selected_currency={currency.upper()}")
    return f"https://www.booking.com/searchresults.{language}.html?{'&'.join(params)}"


def _parse_price_text(text: str) -> Optional[float]:
    """Pull the leading numeric value out of a 'CHF 167' / 'US$167' / '€167' string."""
    if not text:
        return None
    t = text.replace("\xa0", " ").replace(",", "")
    m = re.search(r"([\d]+(?:\.\d+)?)", t)
    if not m:
        return None
    try:
        v = float(m.group(1))
        return v if 10 <= v <= 100000 else None
    except ValueError:
        return None


async def scrape_hotel_pricing(
    hotel_id: str,
    *,
    checkin: str,
    checkout: str,
    currency: Optional[str] = None,
    language: str = "en-gb",
    hotel_name_hint: str = "",
    timeout_ms: int = 30000,
) -> dict:
    """Scrape the live 'starting from' price + review score for one Booking.com hotel_id.

    Uses `/searchresults.html?dest_id=<id>&dest_type=hotel` because the hotel detail
    page blocks headless price extraction via anti-bot.

    Returns: {lowest_price, all_prices, score, hotel_name, scraped, error}
    """
    if not hotel_id:
        return {"lowest_price": None, "all_prices": [], "score": None, "scraped": False, "error": "missing_hotel_id"}

    url = _search_url(hotel_id, checkin, checkout, currency, language)
    browser = await _get_browser()
    ctx = await browser.new_context(
        user_agent=_UA,
        locale="en-GB",
        viewport={"width": 1280, "height": 900},
        extra_http_headers=_DEFAULT_HEADERS,
    )
    page = await ctx.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            await page.wait_for_selector('[data-testid="property-card"]', timeout=12000)
        except Exception:
            # No property-card means either zero availability or blocked page
            pass

        cards = await page.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('[data-testid="property-card"]')).slice(0, 5);
                return cards.map(c => ({
                    title: (c.querySelector('[data-testid="title"]')?.innerText || '').trim(),
                    price: (c.querySelector('[data-testid="price-and-discounted-price"]')?.innerText || '').trim(),
                    review: (c.querySelector('[data-testid="review-score"]')?.innerText || '').trim(),
                    soldout: !!c.querySelector('[data-testid="availability-cta"]'),
                }));
            }
        """) or []

        # Prefer the card whose title matches the target hotel; fall back to the first
        # card (searchresults with dest_id=X&dest_type=hotel usually puts the target first).
        target = None
        hint = (hotel_name_hint or "").lower().strip()
        if hint:
            for c in cards:
                if c.get("title", "").lower().startswith(hint[:18]) or hint[:18] in c.get("title", "").lower():
                    target = c
                    break
        if target is None and cards:
            target = cards[0]

        if not target:
            return {
                "lowest_price": None, "all_prices": [], "score": None,
                "hotel_name": "", "scraped": False, "error": "no_cards",
            }

        price_val = _parse_price_text(target.get("price", ""))
        review_val = None
        rv = target.get("review", "")
        if rv:
            mm = re.search(r"(\d+(?:\.\d+)?)", rv.replace(",", "."))
            if mm:
                try:
                    v = float(mm.group(1))
                    if 0 < v <= 10:
                        review_val = v
                except ValueError:
                    pass

        all_prices = []
        for c in cards[:3]:
            pv = _parse_price_text(c.get("price", ""))
            if pv is not None:
                all_prices.append(pv)

        return {
            "lowest_price": price_val,
            "all_prices": sorted(set(all_prices)),
            "score": review_val,
            "hotel_name": target.get("title", ""),
            "scraped": price_val is not None,
            "error": None if price_val is not None else "no_price_in_card",
        }
    except Exception as exc:
        return {
            "lowest_price": None, "all_prices": [], "score": None,
            "hotel_name": "", "scraped": False, "error": str(exc),
        }
    finally:
        try:
            await page.close()
        except Exception:
            pass
        await ctx.close()


def _parse_dates_from_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Pull checkin / checkout / selected_currency out of a Booking-style URL (if present)."""
    if not url or "?" not in url:
        return None, None, None
    try:
        qs = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&") if "=" in p)
        return qs.get("checkin"), qs.get("checkout"), qs.get("selected_currency")
    except Exception:
        return None, None, None


async def scrape_booking_url(
    url: str,
    *,
    timeout_ms: int = 30000,
    hotel_id: Optional[str] = None,
    hotel_name_hint: str = "",
    language: str = "en-gb",
) -> dict:
    """High-level scrape: resolve hotel_id from URL (cache-aware), then fetch live price.

    Accepts URLs built by `build_dated_url` — dates + currency are read from the query string.
    Callers that already know the hotel_id can pass it in to skip the resolve step.
    """
    checkin, checkout, currency = _parse_dates_from_url(url)
    if not checkin or not checkout:
        return {
            "lowest_price": None, "all_prices": [], "score": None,
            "hotel_id": None, "hotel_name": "",
            "scraped": False, "error": "missing_checkin_checkout",
        }

    hid = hotel_id or await resolve_hotel_id(url, timeout_ms=timeout_ms)
    if not hid:
        return {
            "lowest_price": None, "all_prices": [], "score": None,
            "hotel_id": None, "hotel_name": "",
            "scraped": False, "error": "could_not_resolve_hotel_id",
        }

    out = await scrape_hotel_pricing(
        hid,
        checkin=checkin,
        checkout=checkout,
        currency=currency,
        language=language,
        hotel_name_hint=hotel_name_hint,
        timeout_ms=timeout_ms,
    )
    out["hotel_id"] = hid
    return out


def build_dated_url(base_url: str, checkin: str, checkout: str, currency: Optional[str] = None) -> str:
    """Strip any existing query params and append a clean date range.

    When `currency` is provided, force Booking.com to render prices in that ISO code
    via `selected_currency=<code>`. Without this, Booking falls back to the scraper's
    geo-IP currency (usually USD/EUR on datacenter IPs), which confuses the price
    extractor (values look like /10 of the real CHF price)."""
    clean = (base_url or "").split("?")[0].split("#")[0]
    params = [
        f"checkin={checkin}",
        f"checkout={checkout}",
        "group_adults=2",
        "no_rooms=1",
    ]
    if currency:
        params.append(f"selected_currency={currency.upper()}")
    return f"{clean}?{'&'.join(params)}"


# ---------------------------------------------------------------------------
# URL validator — used by the onboarding wizard + "Add competitor" flow so a
# bad/wrong Booking link can never get saved silently.
# ---------------------------------------------------------------------------

async def validate_booking_url(url: str, *, currency: Optional[str] = None) -> dict:
    """Quickly test-scrape a URL and return a verdict.

    Returns:
        {
          "ok": bool,
          "hotel_id": str|None,       # Booking's internal id (cache key)
          "hotel_name": str,          # Resolved from searchresults card
          "sample_price": float|None, # Tomorrow→day-after lowest rate
          "currency": str,            # Echoed back for UI
          "error": str|None,
        }
    """
    if not url or "booking.com" not in url:
        return {"ok": False, "hotel_id": None, "hotel_name": "", "sample_price": None,
                "currency": (currency or "").upper(), "error": "not_a_booking_url"}

    hid = await resolve_hotel_id(url, timeout_ms=30000, force_refresh=True)
    if not hid:
        return {"ok": False, "hotel_id": None, "hotel_name": "", "sample_price": None,
                "currency": (currency or "").upper(), "error": "could_not_resolve_hotel_id"}

    # Sample tomorrow → day after so we avoid same-day pricing quirks
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    checkin = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    checkout = (now + timedelta(days=2)).strftime("%Y-%m-%d")

    out = await scrape_hotel_pricing(
        hid,
        checkin=checkin,
        checkout=checkout,
        currency=currency,
        language="en-gb",
        hotel_name_hint=_extract_hotel_slug(url).replace("-", " ")[:18],
        timeout_ms=30000,
    )
    return {
        "ok": bool(out.get("scraped") and out.get("lowest_price")),
        "hotel_id": hid,
        "hotel_name": out.get("hotel_name", ""),
        "sample_price": out.get("lowest_price"),
        "currency": (currency or "").upper(),
        "error": out.get("error"),
    }



async def geocode_address(
    query: str,
    *,
    country_code: str = "",
    timeout_s: float = 8.0,
) -> Optional[Tuple[float, float, str]]:
    """Geocode a free-text address/postcode/place via OpenStreetMap Nominatim.

    Returns (latitude, longitude, display_name) or None on failure.
    Free, no API key required.

    Args:
      country_code: ISO 3166-1 alpha-2 (e.g. "gb", "us", "tr") — strongly
        recommended to prevent "Camden, London" being resolved to "Camden, Boston USA".
    """
    q = (query or "").strip()
    if not q:
        return None
    params: Dict = {"q": q, "format": "json", "limit": 1, "addressdetails": 1}
    if country_code:
        params["countrycodes"] = country_code.lower().strip()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers={"User-Agent": "HotelBox/1.0 (admin@hotelbox.com)"},
            )
            r.raise_for_status()
            arr = r.json()
            if not arr:
                return None
            top = arr[0]
            lat = float(top.get("lat"))
            lon = float(top.get("lon"))
            display = top.get("display_name", q)
            return (lat, lon, display)
    except Exception as e:
        logger.warning(f"geocode_address failed for '{q}': {e}")
        return None


def _extract_district_hint(display_name: str, postcode: str = "", city: str = "") -> str:
    """From a Nominatim display_name string, extract a useful Booking.com
    search hint — typically the neighborhood/district name. Fallback: postcode → city.

    Example display_name:
      'City of London Flats, 20, Widegate Street, Broadgate, Bishopsgate,
       City of London, Greater London, England, E1 7HP, United Kingdom'

    We want something like 'Bishopsgate, London' or 'E1, London' which
    Booking.com resolves to a narrow geographic district.
    """
    if not display_name:
        return f"{postcode}, {city}".strip(", ") or city
    parts = [p.strip() for p in display_name.split(",") if p.strip()]
    # Drop common "noise" tokens
    noise = {"united kingdom", "england", "scotland", "wales", "northern ireland",
             "greater london", "city of london"}
    # Heuristic: take the first part that isn't a number, isn't noise, isn't the
    # property name, and is at least 3 chars
    district = None
    for p in parts[1:-2]:  # skip name (parts[0]) and country/region
        pl = p.lower()
        if pl in noise:
            continue
        if any(ch.isdigit() for ch in p):  # likely a postcode or number
            continue
        if len(p) >= 3:
            district = p
            break
    if district:
        suffix = f", {city}" if city and city.lower() not in district.lower() else ""
        return f"{district}{suffix}"
    # Fallback: postcode + city
    if postcode and city:
        # Use just the outward code for UK (first half), e.g. "E1 7HP" → "E1"
        outward = postcode.split()[0] if " " in postcode else postcode[:3].rstrip()
        return f"{outward}, {city}"
    return city or postcode or display_name.split(",")[-1]


async def discover_nearby_hotels(
    *,
    postcode: str = "",
    city: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    property_type: str = "any",
    radius_km: float = 2.5,
    max_results: int = 25,
    language: str = "en-gb",
    currency: str = "GBP",
    timeout_ms: int = 30000,
    district_hint: str = "",
) -> List[Dict]:
    """Discover competitor candidates near a location by scraping Booking.com search.

    Admins use this to generate a list of nearby hotels with the same property type
    (apartment/hotel/aparthotel), then pick which to add as competitors via the UI.
    Returns a list of dicts with hotel_id, name, slug, booking_url, stars, review_score,
    address, and property_type. Never raises — returns [] on failure.
    """
    # Build the search string smartly. Booking.com chokes on duplicate words like
    # "Zurich, Zurich" (returns featured global hotels). De-dupe + clean.
    parts = []
    pc_clean = (postcode or "").strip()
    city_clean = (city or "").strip()
    if pc_clean:
        parts.append(pc_clean)
    if city_clean and city_clean.lower() != pc_clean.lower():
        parts.append(city_clean)
    search_term = ", ".join(parts) or (f"{latitude},{longitude}" if latitude and longitude else "")
    if not search_term:
        logger.warning("discover_nearby_hotels: no location info")
        return []

    # When we have coords (most accurate), use the district hint (e.g.
    # "Aldgate, London" or "E1, London") instead of the property name so
    # Booking auto-resolves to a TIGHT geographic area instead of city-wide.
    if latitude is not None and longitude is not None and district_hint:
        search_term = district_hint
    elif latitude is not None and longitude is not None and city_clean:
        search_term = city_clean
    ss = search_term.replace(" ", "+").replace(",", "%2C")
    # Booking.com accommodation type filters (ht_id values)
    nflt_map = {
        "apartments": "nflt=ht_id%3D201",
        "aparthotels": "nflt=ht_id%3D204",
        "hotels": "nflt=ht_id%3D203",
    }
    nflt = nflt_map.get(property_type.lower(), "")
    # Booking.com lands on a generic page when no checkin/checkout dates are passed —
    # we feed it a real upcoming date range so the search resolves to the requested city
    # rather than featured hotels in unrelated countries.
    today = datetime.now(timezone.utc).date()
    checkin = (today + timedelta(days=14)).strftime("%Y-%m-%d")
    checkout = (today + timedelta(days=15)).strftime("%Y-%m-%d")

    # Booking.com's `ss=` is a free-text query that NEEDS a `dest_id` to resolve to a
    # specific city — without it, results default to a globally-curated landing page.
    # Pre-mapped (city → (dest_id, dest_type)) for our current portfolio. Add more here
    # as the user onboards new cities; verified by manually browsing Booking's URL bar.
    CITY_DEST_IDS = {
        "london": ("-2601889", "city"),
        "zurich": ("-2554920", "city"),
        "zürich": ("-2554920", "city"),
        "berlin": ("-1746443", "city"),
        "paris": ("-1456928", "city"),
        "amsterdam": ("-2140479", "city"),
        "istanbul": ("-755070", "city"),
        "barcelona": ("-372490", "city"),
        "madrid": ("-390625", "city"),
        "vienna": ("-1995499", "city"),
        "dublin": ("-1503281", "city"),
        "edinburgh": ("-2595386", "city"),
        "manchester": ("-2602847", "city"),
        "liverpool": ("-2602591", "city"),
        "lisbon": ("-2167973", "city"),
        "rome": ("-126693", "city"),
        "milan": ("-121726", "city"),
    }
    # Match against either `city_clean` or the first comma-separated token
    lookup_key = (city_clean or pc_clean).split(",")[0].strip().lower()
    dest = CITY_DEST_IDS.get(lookup_key)

    # Coordinate-based search (FAR more accurate for "actual neighbors"):
    # Booking.com supports latitude/longitude + nflt=distance%3D<meters> to
    # restrict results to a real geographic radius. This avoids the trap of
    # generic city-wide featured listings (Kensington shown to an Aldgate
    # property, etc.). Default radius: 2500m (~2.5 km walking neighborhood).
    use_coords = latitude is not None and longitude is not None
    _ = max(500, min(int((radius_km or 2.5) * 1000), 10000))  # reserved for future map URL pattern

    qs_parts = [
        f"ss={ss}",
        f"checkin={checkin}",
        f"checkout={checkout}",
        "group_adults=2",
        "no_rooms=1",
        "group_children=0",
        f"selected_currency={currency.upper()}",
    ]

    nflt_parts = []
    if nflt:
        # nflt is e.g. "nflt=ht_id%3D201" — extract value
        nflt_parts.append(nflt.split("=", 1)[1])

    if use_coords:
        # Booking.com works best with a DISTRICT-level ss text (resolved
        # automatically). Don't add dest_id (that locks to city center) —
        # let ss carry the geographic narrowing. Add latitude/longitude as
        # secondary hints so distance sort works.
        qs_parts.append(f"latitude={latitude:.6f}")
        qs_parts.append(f"longitude={longitude:.6f}")
        qs_parts.append("order=distance_from_search")
    elif dest:
        qs_parts.insert(0, f"dest_id={dest[0]}")
        qs_parts.insert(1, f"dest_type={dest[1]}")
    else:
        qs_parts.append("dest_type=city")

    if nflt_parts:
        qs_parts.append("nflt=" + "%3B".join(nflt_parts))

    url = f"https://www.booking.com/searchresults.{language}.html?{'&'.join(qs_parts)}"

    browser = await _get_browser()
    ctx = await browser.new_context(
        user_agent=_UA,
        locale="en-GB",
        viewport={"width": 1366, "height": 900},
        extra_http_headers=_DEFAULT_HEADERS,
    )
    page = await ctx.new_page()
    try:
        # Strategy A: directly navigate to searchresults URL — fast and reliable when
        # we have a real dest_id (most cities are pre-mapped above). The homepage flow
        # was problematic (autocomplete clicks racy), so we only fall back to it when
        # the city is NOT in our dest_id table (= no `dest_id=` in qs).
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(2500)

        # Only kick the homepage fallback if we DON'T have a known dest_id —
        # otherwise we trust the dest_id+dest_type combo Booking already accepted.
        if not dest:
            try:
                page_url = page.url or ""
                heading = (await page.locator("h1").first.text_content(timeout=2000)) or ""
            except Exception:
                heading = ""
            wrong_geo = (
                ("/searchresults" not in page_url and "/index" in page_url)
                or (heading and search_term.split(",")[0].lower() not in heading.lower()
                    and "search results" not in heading.lower())
            )
            if wrong_geo:
                # Strategy B: drive the homepage search input — slower but reliably resolves
                # the destination via Booking's own autocomplete picker.
                try:
                    logger.info("discover_nearby_hotels: fallback to homepage flow for %r", search_term)
                    home_url = f"https://www.booking.com/index.{language}.html?selected_currency={currency.upper()}"
                    await page.goto(home_url, wait_until="domcontentloaded", timeout=timeout_ms)
                    await page.wait_for_timeout(2000)
                    box_selectors = [
                        'input[name="ss"]',
                        'input[data-testid="destination-input"]',
                        'input[placeholder*="destination" i]',
                    ]
                    box = None
                    for sel in box_selectors:
                        try:
                            b = page.locator(sel).first
                            if await b.is_visible(timeout=1500):
                                box = b
                                break
                        except Exception:
                            continue
                    if box:
                        await box.click(force=True)
                        await box.fill(search_term.split(",")[0])
                        await page.wait_for_timeout(1500)
                        try:
                            suggestion = page.locator('[data-testid="autocomplete-result"]').first
                            if await suggestion.is_visible(timeout=2500):
                                await suggestion.click(force=True)
                            else:
                                await box.press("Enter")
                        except Exception:
                            await box.press("Enter")
                        await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
                        await page.wait_for_timeout(3000)
                except Exception as e:
                    logger.warning("discover_nearby_hotels: homepage fallback failed: %s", e)

        # Scroll to trigger lazy-loaded cards
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1200)
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass
        # Try both current and legacy selectors before giving up
        try:
            await page.wait_for_selector('[data-testid="property-card"], .sr_property_block, [data-testid="title"]', timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(1000)

        js_script = """
            (maxResults) => {
                // Try current selector first, then legacy
                let cards = Array.from(document.querySelectorAll('[data-testid="property-card"]'));
                if (cards.length === 0) {
                    cards = Array.from(document.querySelectorAll('.sr_property_block, [data-testid="title"]'))
                        .map(el => el.closest('[role="article"], [data-testid="property-card"], .sr_property_block, div'))
                        .filter(Boolean);
                }
                // Last-resort: treat every anchor pointing at /hotel/XX/<slug>.html as a candidate
                if (cards.length === 0) {
                    const anchors = document.querySelectorAll('a[href*="/hotel/"]');
                    const seen = new Set();
                    const fakes = [];
                    anchors.forEach(a => {
                        const m = a.href.match(/\\/hotel\\/[a-z]{2}\\/([a-z0-9-]+)\\./i);
                        if (m && !seen.has(m[1])) {
                            seen.add(m[1]);
                            // wrap anchor so the downstream parser still works
                            fakes.push(a.closest('div') || a.parentElement || a);
                        }
                    });
                    cards = fakes;
                }

                const out = [];
                for (const c of cards) {
                    if (out.length >= maxResults) break;
                    const titleEl = c.querySelector('[data-testid="title"]') || c.querySelector('[data-testid="title-link"]') || c.querySelector('a[href*="/hotel/"]');
                    const linkEl = c.querySelector('[data-testid="title-link"]') || c.querySelector('a[href*="/hotel/"]');
                    let name = titleEl ? titleEl.textContent.trim() : '';
                    const href = linkEl ? linkEl.href : '';
                    if (!name) {
                        // Fallback: use the slug as the name when the DOM hides the title
                        const m = href.match(/\\/hotel\\/[a-z]{2}\\/([a-z0-9-]+)\\./i);
                        if (m) name = m[1].replace(/-/g, ' ').replace(/\\b\\w/g, ch => ch.toUpperCase());
                    }
                    if (!name || !href) continue;
                    const u = new URL(href);
                    const cleanUrl = u.origin + u.pathname;
                    const hidMatch = href.match(/hotel_id=(\\d+)/) || href.match(/dest_id=(\\d+)/);
                    const hotel_id = hidMatch ? hidMatch[1] : null;
                    const slugMatch = u.pathname.match(/\\/hotel\\/[a-z]{2}\\/([a-z0-9-]+)\\./i);
                    const slug = slugMatch ? slugMatch[1] : '';
                    const distEl = c.querySelector('[data-testid="distance"]') || c.querySelector('[data-testid="address"]');
                    const address = distEl ? distEl.textContent.trim() : '';
                    const scoreEl = c.querySelector('[data-testid="review-score"]');
                    let review_score = null;
                    if (scoreEl) { const m = scoreEl.textContent.match(/(\\d+\\.\\d+)/); if (m) review_score = parseFloat(m[1]); }
                    const starsEl = c.querySelector('[data-testid="rating-stars"]') || c.querySelector('[aria-label*="star"]');
                    let stars = null;
                    if (starsEl) {
                        const aria = starsEl.getAttribute('aria-label') || '';
                        const m = aria.match(/(\\d)/);
                        if (m) stars = parseInt(m[1]);
                        else { const svgs = starsEl.querySelectorAll('svg'); if (svgs.length) stars = svgs.length; }
                    }
                    const typeEl = c.querySelector('[data-testid="property-type-badge"]');
                    const prop_type = typeEl ? typeEl.textContent.trim() : '';
                    out.push({ hotel_id, name, slug, booking_url: cleanUrl, stars, review_score, address, property_type: prop_type });
                }
                return out;
            }
        """
        results = await page.evaluate(js_script, max_results)

        # Last-resort raw HTML regex fallback if Playwright selectors found nothing.
        if not results:
            try:
                html = await page.content()
                pattern = re.compile(
                    r'href=["\'](https?://(?:www\.)?booking\.com/hotel/([a-z]{2})/([a-z0-9-]+)\.(?:[a-z]{2}(?:-[a-z]{2})?\.)?html)[^"\']*["\']',
                    re.I,
                )
                seen = set()
                fallback = []
                for m in pattern.finditer(html):
                    slug = m.group(3)
                    if slug in seen:
                        continue
                    seen.add(slug)
                    booking_url = f"https://www.booking.com/hotel/{m.group(2)}/{slug}.html"
                    fallback.append({
                        "hotel_id": None,
                        "name": slug.replace("-", " ").title(),
                        "slug": slug,
                        "booking_url": booking_url,
                        "stars": None, "review_score": None,
                        "address": "", "property_type": "",
                    })
                    if len(fallback) >= max_results:
                        break
                if fallback:
                    logger.info("discover_nearby_hotels: HTML-regex fallback found %d", len(fallback))
                    results = fallback
            except Exception as e:
                logger.warning("discover_nearby_hotels regex fallback error: %s", e)

        logger.info(
            "discover_nearby_hotels: %d results for ss=%r type=%s",
            len(results), search_term, property_type,
        )
        seen = set()
        deduped = []
        for r in results:
            key = r.get("slug") or r.get("booking_url", "")
            if key and key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped
    except Exception as e:
        logger.warning("discover_nearby_hotels failed: %s", e)
        return []
    finally:
        try:
            await page.close()
        except Exception:
            pass
        await ctx.close()
