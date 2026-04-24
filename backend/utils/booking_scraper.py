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
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

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
