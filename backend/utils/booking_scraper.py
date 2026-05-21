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
import sys
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

# Shared "warm" Booking.com browser context — once we've cleared the first
# anti-bot challenge and Booking.com has set its session cookies on this
# context, every subsequent page navigation on the SAME context skips that
# challenge entirely. Multi-date scans previously created a fresh context per
# probe → every probe re-paid the 30-40s cold-start cost and most timed out.
# Reusing the warmed context cuts per-probe cost from ~35s to ~3-6s.
_booking_ctx = None  # type: ignore[var-annotated]
_booking_ctx_lock = asyncio.Lock()
_booking_ctx_warmed = False


async def _get_warm_booking_context(force_recreate: bool = False):
    """Return the shared warmed-up Browser context for Booking.com scraping.

    Lazy-created on first use, warmed by visiting the homepage so Booking sets
    its anti-bot cookies on us. Re-creates if the previous context was closed.

    `force_recreate=True` tears down the existing context and builds a fresh
    one with empty cookies — used between Tor circuit rotations so the new
    exit IP doesn't carry over Booking's "this session is a bot" flag.
    """
    global _booking_ctx, _booking_ctx_warmed
    async with _booking_ctx_lock:
        # Detect dead contexts (browser restarted) and recreate
        try:
            if _booking_ctx is not None:
                _ = _booking_ctx.pages
        except Exception:
            _booking_ctx = None
            _booking_ctx_warmed = False

        if force_recreate and _booking_ctx is not None:
            try:
                await _booking_ctx.close()
            except Exception:
                pass
            _booking_ctx = None
            _booking_ctx_warmed = False

        if _booking_ctx is None:
            browser = await _get_browser()
            ctx_kwargs = dict(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"),
                locale="en-GB",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={
                    "Accept-Language": "en-GB,en;q=0.9",
                    "sec-ch-ua-platform": '"Windows"',
                },
            )
            proxy_cfg = _booking_proxy_config()
            if proxy_cfg:
                ctx_kwargs["proxy"] = proxy_cfg
            _booking_ctx = await browser.new_context(**ctx_kwargs)
            _booking_ctx_warmed = False
            logger.info("Booking scraper: created shared warm context")

        if not _booking_ctx_warmed:
            # Pre-warm: visit homepage to acquire bot-challenge cookies
            try:
                page = await _booking_ctx.new_page()
                try:
                    await page.goto(
                        "https://www.booking.com/index.en-gb.html",
                        wait_until="domcontentloaded",
                        timeout=20000,
                    )
                    await page.wait_for_timeout(1500)
                    _booking_ctx_warmed = True
                    logger.info("Booking scraper: warm context primed via homepage visit")
                finally:
                    await page.close()
            except Exception as e:
                logger.warning("Booking scraper: warm-up navigation failed (%s) — context still usable", e)
                # Mark warmed anyway so we don't loop forever; subsequent
                # scrapes may still succeed if Booking just rate-limited the
                # homepage but lets product pages through.
                _booking_ctx_warmed = True

        return _booking_ctx


def _booking_proxy_config() -> Optional[Dict]:
    """Returns Playwright proxy config dict. Priority:
      1. BOOKING_PROXY_URL (paid residential / SOCKS / HTTPS proxy)
      2. Local Tor SOCKS (free, IP rotates per circuit)
      3. None — direct pod IP

    Booking.com aggressively blocks/rate-limits scraping from cloud/datacenter
    IPs. The Tor fallback gives users a free way to rotate IP per scrape
    without paying for a residential proxy provider; Tor exit IPs are widely
    blocked by Booking too but it's strictly better than the static pod IP.

    Format (for BOOKING_PROXY_URL):
      - http://user:pass@host:port
      - https://user:pass@host:port
      - http://host:port            (no auth)
      - socks5://user:pass@host:port
    """
    url = os.environ.get("BOOKING_PROXY_URL", "").strip()
    if url:
        try:
            from urllib.parse import urlparse
            u = urlparse(url)
            if not u.hostname:
                logger.warning("BOOKING_PROXY_URL has no host: %s", url)
            else:
                cfg = {"server": f"{u.scheme}://{u.hostname}:{u.port or 80}"}
                if u.username:
                    cfg["username"] = u.username
                if u.password:
                    cfg["password"] = u.password
                return cfg
        except Exception as e:
            logger.warning("BOOKING_PROXY_URL parse failed: %s — %s", url, e)
    # Free fallback: local Tor SOCKS proxy (if enabled & running)
    try:
        from utils.tor_manager import playwright_proxy_config as _tor_pw_proxy
        tor_cfg = _tor_pw_proxy()
        if tor_cfg:
            return tor_cfg
    except Exception:
        pass
    return None


async def _ensure_chromium_installed(*, force: bool = False) -> bool:
    """Block until Playwright Chromium-headless-shell binary exists on disk.

    The /pw-browsers volume keeps disappearing on this environment between
    pod restarts. We call this at startup AND on Browser-launch failure so
    that the very first scrape after a restart self-heals instead of 500'ing.

    Args:
      force: when True, runs `playwright install` even if any headless_shell
        binary is already present. Use this on Browser-launch failure —
        playwright might want a specific version that isn't on disk yet.
    Returns True if install succeeded (or already up to date).
    """
    base_str = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")
    try:
        # Resolve the EXACT revision Playwright wants right now (e.g. v1217),
        # not just "any older version that happens to be on disk". This
        # closes the bug where v1208 sat in /pw-browsers and we said "all
        # good" even though Playwright 1.59 needs v1217.
        from pathlib import Path as _P
        expected_dir = None
        try:
            dry = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "playwright", "install", "--dry-run", "chromium-headless-shell",
                env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": base_str},
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _stderr = await asyncio.wait_for(dry.communicate(), timeout=10)
            except asyncio.TimeoutError:
                stdout = b""
                try:
                    dry.kill()
                except Exception:
                    pass
            for line in stdout.decode(errors="ignore").splitlines():
                if "Install location:" in line and "chromium_headless_shell" in line:
                    expected_dir = line.split("Install location:")[-1].strip()
                    break
        except Exception:
            pass

        if not force and expected_dir:
            shell = _P(expected_dir) / "chrome-linux" / "headless_shell"
            if shell.exists():
                return True
        elif not force:
            # Fallback: dry-run failed — accept any version (legacy behaviour).
            base = _P(base_str)
            if base.exists():
                for _ in base.glob("chromium_headless_shell-*/chrome-linux/headless_shell"):
                    return True

        logger.warning(
            "Playwright Chromium-headless-shell %s — installing (blocking)... target=%s",
            "force-refresh" if force else "missing", expected_dir or "auto",
        )
        # IMPORTANT: Playwright v1.59+ requires `chromium-headless-shell` AS A
        # SEPARATE PACKAGE from `chromium`. Installing just `chromium` (as we
        # were before) leaves the headless_shell binary missing and every
        # browser-launch fails with `Executable doesn't exist`.
        # NOTE: When forcing (e.g. after seeing a "missing binary" error at
        # launch time), pass --force so playwright actually re-downloads —
        # otherwise it short-circuits in ~1s if a stale older-revision dir
        # exists on disk, and we never get the v1217 (or current) binary.
        install_args = [sys.executable, "-m", "playwright", "install", "chromium-headless-shell"]
        if force:
            install_args.insert(4, "--force")
        proc = await asyncio.create_subprocess_exec(
            *install_args,
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": base_str},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=180)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            logger.error("Playwright install timed out after 180s")
            return False
        if proc.returncode == 0:
            # Sanity check the expected dir is actually there now. If not,
            # something silently failed and we should report rather than lie.
            if expected_dir:
                shell = _P(expected_dir) / "chrome-linux" / "headless_shell"
                if not shell.exists():
                    logger.error(
                        "Playwright install rc=0 but %s missing — retrying with --force",
                        expected_dir,
                    )
                    # One retry with --force to nuke any stale cache.
                    proc2 = await asyncio.create_subprocess_exec(
                        sys.executable, "-m", "playwright", "install", "--force", "chromium-headless-shell",
                        env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": base_str},
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    )
                    try:
                        await asyncio.wait_for(proc2.wait(), timeout=180)
                    except asyncio.TimeoutError:
                        try:
                            proc2.kill()
                        except Exception:
                            pass
                    if proc2.returncode == 0 and shell.exists():
                        logger.info("Playwright Chromium installed ✓ (forced retry)")
                        return True
                    return False
            logger.info("Playwright Chromium installed ✓")
            return True
        logger.error("Playwright install rc=%s", proc.returncode)
        return False
    except Exception as e:
        logger.error("Playwright install error: %s", e)
        return False


async def _get_browser() -> Browser:
    """Returns the shared headless Chromium. Lazy-launched on first use.

    Self-heals when the binary is missing (re-downloads, then retries).
    """
    global _browser, _pw
    if _browser is None or not _browser.is_connected():
        async with _lock:
            if _browser is None or not _browser.is_connected():
                if _pw is None:
                    _pw = await async_playwright().start()
                launch_kwargs = {
                    "headless": True,
                    "args": [
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                }
                # Browser-level proxy applies to all contexts unless overridden
                proxy = _booking_proxy_config()
                if proxy:
                    launch_kwargs["proxy"] = proxy
                    logger.info(
                        "Booking scraper: routing via proxy server=%s (auth=%s)",
                        proxy.get("server"), bool(proxy.get("username")),
                    )
                try:
                    _browser = await _pw.chromium.launch(**launch_kwargs)
                except Exception as e:
                    if "Executable doesn't exist" in str(e):
                        logger.warning("Chromium binary missing — auto-installing (force)...")
                        ok = await _ensure_chromium_installed(force=True)
                        if not ok:
                            raise
                        _browser = await _pw.chromium.launch(**launch_kwargs)
                    else:
                        raise
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

# In-process cache: { normalized_url: room_count_int }
_ROOM_COUNT_CACHE: Dict[str, int] = {}

# Patterns we use to read the property-level inventory off the Booking.com hotel page.
# Booking publishes the room count in several spots — JSON-LD ("numberOfRooms"),
# inline page state ("hotel_room_count" / "n_rooms"), or human-readable copy in
# the "About this property" block ("This property has 9 rooms / apartments / units").
# We try every pattern in order; first non-zero match wins. Reviews count is
# explicitly EXCLUDED — we never read a number that's adjacent to "review(s)".
_ROOM_COUNT_PATTERNS = [
    re.compile(r'"numberOfRooms"\s*:\s*"?(\d{1,4})"?', re.I),
    re.compile(r'"hotel_room_count"\s*:\s*(\d{1,4})', re.I),
    re.compile(r'"n_rooms"\s*:\s*(\d{1,4})', re.I),
    re.compile(r'<meta\s+itemprop=["\']numberOfRooms["\']\s+content=["\'](\d{1,4})["\']', re.I),
    # Visible copy fallbacks — must NOT be near "review" / "rating".
    re.compile(r'(?:property|hotel|apart\s?hotel|aparthotel|building|residence)\s+(?:has|offers|features)\s+(\d{1,4})\s+(?:rooms?|apartments?|units?|studios?)\b', re.I),
    re.compile(r'\b(\d{1,4})\s+(?:rooms?|apartments?|units?|studios?)\s+(?:in\s+total|available|at\s+this\s+property)', re.I),
]


def _extract_room_count_from_html(html: str) -> Optional[int]:
    """Pull the property-level room count out of a Booking.com hotel-detail HTML
    blob. Returns None if no pattern matches or the number looks unreasonable.

    Why this exists: scraping the *review count* and treating it as rooms is the
    classic Booking.com bug — reviews can be in the thousands and look nothing
    like the real inventory. This helper goes the other way: only patterns that
    are anchored to property structure (JSON-LD, inline state, "this property
    has N rooms" sentences) are accepted.
    """
    if not html:
        return None
    # Snip the part of the HTML that immediately surrounds the "review" word so
    # we don't accidentally match "1,234 reviews".
    text_lower = html.lower()
    if "review" in text_lower:
        # We still want JSON-LD / state matches; they're safe because they look
        # for the explicit key. Only the natural-language patterns at the bottom
        # of the list need this guard, and they require very specific anchor
        # words ("property has", "in total", "at this property") that don't
        # appear next to review counts anyway.
        pass
    for rx in _ROOM_COUNT_PATTERNS:
        m = rx.search(html)
        if m:
            try:
                n = int(m.group(1))
            except (TypeError, ValueError):
                continue
            # Sanity bounds: Booking.com lists properties from 1 to ~2000 rooms.
            # Anything outside this window is almost certainly a misread.
            if 1 <= n <= 2000:
                return n
    return None


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
            # Opportunistic room-count extraction from the same HTML payload —
            # avoids a second scrape on the same Booking.com page (saves ~2-3s
            # and keeps us under our polite request budget).
            rc = _extract_room_count_from_html(html)
            if rc is not None:
                _ROOM_COUNT_CACHE[key] = rc
            if m:
                hid = m.group(1)
                _HOTEL_ID_CACHE[key] = hid
                logger.info("Booking scraper: resolved hotel_id=%s for %s (room_count=%s)", hid, _extract_hotel_slug(booking_url), rc)
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


async def scrape_hotel_room_count(
    booking_url: str,
    *,
    timeout_ms: int = 25000,
    force_refresh: bool = False,
) -> Optional[int]:
    """Public helper — return the room/apartment/unit count from a Booking.com hotel
    page. Cached per-process; uses the same HTML the hotel_id resolver fetches so
    repeated calls cost nothing. Returns None if the property page doesn't expose
    a count we can trust.
    """
    if not booking_url:
        return None
    key = _normalize_base_url(booking_url)
    if not force_refresh and key in _ROOM_COUNT_CACHE:
        return _ROOM_COUNT_CACHE[key]
    # Resolving the hotel_id populates the room-count cache as a side effect.
    await resolve_hotel_id(booking_url, timeout_ms=timeout_ms, force_refresh=force_refresh)
    return _ROOM_COUNT_CACHE.get(key)


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


async def reverse_geocode(
    latitude: float,
    longitude: float,
    *,
    timeout_s: float = 8.0,
) -> Optional[Dict]:
    """Reverse-geocode a lat/lon to its administrative address via Nominatim.

    Returns a dict with keys: country_code (alpha-2 lowercase), country, city,
    state, display_name — or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": latitude, "lon": longitude,
                        "format": "json", "addressdetails": 1, "zoom": 10},
                headers={"User-Agent": "HotelBox/1.0 (admin@hotelbox.com)"},
            )
            r.raise_for_status()
            data = r.json() or {}
            addr = data.get("address") or {}
            return {
                "country_code": (addr.get("country_code") or "").lower(),
                "country": addr.get("country") or "",
                "city": addr.get("city") or addr.get("town") or addr.get("village")
                        or addr.get("municipality") or addr.get("suburb") or "",
                "state": addr.get("state") or "",
                "display_name": data.get("display_name") or "",
            }
    except Exception as e:
        logger.warning(f"reverse_geocode failed for ({latitude},{longitude}): {e}")
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


# Single-room / studio listing detector — these are not pricing benchmarks for a
# multi-room PMS property; e.g. "1 Bedroom Flat", "Studio Apartment", "Cosy King
# Size Bed", "Single Room", "Designers 1-bedroom Flat", etc. Used by
# discover_nearby_hotels to filter out noise from Booking.com search results.
_SINGLE_ROOM_REGEX = re.compile(
    r"\b("
    r"1[\s-]?bed(room)?s?|"           # "1 Bed", "1-bed", "1 Bedroom"
    r"one[\s-]?bed(room)?s?|"         # "One Bed", "One-Bedroom"
    r"studio[\s-]?(apartment|flat)?|"  # "Studio", "Studio Apartment", "Studio Flat"
    r"single[\s-]?(room|bed)|"        # "Single Room", "Single Bed"
    r"king[\s-]?size[\s-]?bed|"       # "King Size Bed" — single bedroom marker
    r"queen[\s-]?size[\s-]?bed"       # "Queen Size Bed"
    r")\b",
    re.I,
)


def _is_single_room_listing(name: str) -> bool:
    """Heuristic: does the listing name suggest a single-room/studio unit?

    Used to filter out Booking.com search results that aren't meaningful price
    benchmarks for a multi-room PMS-managed property. Returns True when the
    name matches patterns like "1 Bedroom Flat", "Studio", "King Size Bed",
    "Single Room", etc.
    """
    if not name:
        return False
    return bool(_SINGLE_ROOM_REGEX.search(name))


async def scrape_booking_screenshot(
    booking_url: str,
    *,
    timeout_ms: int = 20000,
    full_page: bool = False,
    pre_warm: bool = True,
    fresh_context: bool = False,
    clear_cookies: bool = False,
) -> Optional[bytes]:
    """Take a PNG screenshot of a Booking.com property/search page.

    Returns the raw PNG bytes ready to be sent to a vision model. Uses
    pre-warming (Booking.com homepage → target URL) to bypass cold
    deep-link blocking. Never raises — returns None on failure.

    Args:
      booking_url: target page (detail page OR search result)
      timeout_ms: per-navigation timeout
      full_page: when True captures the full scrollable page (heavier)
      pre_warm: when True, visits Booking.com homepage first so anti-bot
        cookies are set before navigating to the detail URL.
    """
    if not booking_url:
        return None
    # When `fresh_context=True` we ALWAYS create a brand-new browser context
    # (and never touch the shared warm one). Combined with Tor circuit rotation,
    # this gives every probe its OWN exit IP + OWN cookie jar, which prevents
    # Booking.com from correlating successive scrapes back to a single
    # flagged session.
    if fresh_context:
        browser = await _get_browser()
        ctx_kwargs = dict(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            locale="en-GB",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "en-GB,en;q=0.9",
                "sec-ch-ua-platform": '"Windows"',
            },
        )
        proxy_cfg = _booking_proxy_config()
        if proxy_cfg:
            ctx_kwargs["proxy"] = proxy_cfg
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        _fresh_ctx_to_close = ctx
    else:
        # Use the shared warmed-up Booking.com context — drastically reduces
        # anti-bot challenges on subsequent calls (cookies persist).
        ctx = await _get_warm_booking_context()
        if clear_cookies:
            # Wipe cookies between Tor circuit rotations so the new exit IP
            # doesn't carry over Booking's "this session is a bot" flag.
            try:
                await ctx.clear_cookies()
            except Exception:
                pass
        try:
            page = await ctx.new_page()
            _fresh_ctx_to_close = None
        except Exception as e:
            logger.warning("scrape_booking_screenshot: could not create page on warm ctx (%s) — falling back to fresh ctx", e)
            browser = await _get_browser()
            ctx = await browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"),
                locale="en-GB",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={
                    "Accept-Language": "en-GB,en;q=0.9",
                    "sec-ch-ua-platform": '"Windows"',
                },
            )
            page = await ctx.new_page()
            _fresh_ctx_to_close = ctx
    try:
        # pre_warm is now a no-op when using the shared context (already warmed
        # at construction); for fresh contexts we visit the homepage first so
        # anti-bot cookies are set before navigating to the deep detail URL.
        if pre_warm and _fresh_ctx_to_close is not None:
            try:
                await page.goto("https://www.booking.com/index.en-gb.html",
                                wait_until="domcontentloaded", timeout=timeout_ms)
                await page.wait_for_timeout(1500)
            except Exception:
                pass
        try:
            # IMPORTANT: use wait_until="commit" so we fail FAST on the bot
            # challenge response (202) — Booking's challenge page never fires
            # `domcontentloaded` reliably in headless, so the old setting could
            # burn the entire timeout budget on a single bad exit. With
            # `commit` we get response headers back in ~1-3s, can check status,
            # and bail to the next Tor circuit immediately.
            resp = await page.goto(booking_url, wait_until="commit", timeout=timeout_ms)
            status = resp.status if resp else 0
            if status == 202:
                # Bot challenge. With Tor + circuit rotation it's cheaper to
                # abandon this exit and let the caller retry with a fresh
                # circuit (~3s) than to wait out the challenge page (~30s).
                try:
                    from utils.tor_manager import tor_enabled as _tor_enabled
                    using_tor = _tor_enabled()
                except Exception:
                    using_tor = False
                if using_tor:
                    logger.info("scrape_booking_screenshot: 202 challenge — abandoning this exit, caller may retry")
                    return None
                # Direct-IP path: wait it out once
                logger.info("scrape_booking_screenshot: 202 challenge — waiting for JS resolution")
                await page.wait_for_timeout(5000)
            elif status and not (200 <= status < 400):
                logger.warning("scrape_booking_screenshot: unexpected status %s on %s", status, booking_url)
                return None
            # Now wait for the actual content to render before screenshotting
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
        except Exception as e:
            logger.warning("scrape_booking_screenshot: goto failed %s — %s", booking_url, e)
            return None
        await page.wait_for_timeout(2200)
        try:
            png = await page.screenshot(type="png", full_page=full_page)
            return png
        except Exception as e:
            logger.warning("scrape_booking_screenshot: shot failed %s — %s", booking_url, e)
            return None
    finally:
        # Only close the PAGE (keep the shared warm context alive); close the
        # fallback fresh context if we created one.
        try:
            await page.close()
        except Exception:
            pass
        if _fresh_ctx_to_close is not None:
            try:
                await _fresh_ctx_to_close.close()
            except Exception:
                pass



async def _fetch_property_unit_count(ctx, booking_url: str, timeout_ms: int = 15000) -> Optional[int]:
    """Attempt to fetch room/apartment count from a Booking.com property page.

    LIMITATION: Booking.com only exposes `numberOfRooms` for a small subset of
    listings (some Hotel-type, almost no Apartment-type). Even when the page
    opens correctly via session-warmed navigation, the JSON-LD schema usually
    omits this field. Combined with frequent "Page not found" responses for
    direct deep links from cloud IPs, this signal is unreliable in practice.

    The function is kept for the day Booking.com restores broader coverage:
      1. Pre-warm the session by visiting Booking.com homepage (sets anti-bot
         cookies that real users get implicitly).
      2. Visit the property detail URL with the warmed session.
      3. Parse JSON-LD blocks for any `numberOfRooms` field.

    Returns the int unit count, or None if not extractable. Callers should
    treat None as "unknown" — DO NOT auto-exclude. Use review_count as the
    primary size proxy instead.
    """
    if not booking_url:
        return None
    page = None
    try:
        page = await ctx.new_page()
        # Pre-warm: visit homepage so Booking.com sets the anti-bot cookies
        # a real user would have when arriving at a detail page. Otherwise
        # most direct deep-links return a "page not found" shell.
        try:
            await page.goto("https://www.booking.com/index.en-gb.html",
                            wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(1200)
        except Exception:
            pass  # warm-up best-effort
        try:
            await page.goto(booking_url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(800)
        except Exception:
            return None
        try:
            ld_count = await page.evaluate(
                """
                () => {
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const s of scripts) {
                        try {
                            const data = JSON.parse(s.textContent);
                            const stack = Array.isArray(data) ? [...data] : [data];
                            while (stack.length) {
                                const it = stack.pop();
                                if (!it || typeof it !== 'object') continue;
                                if (it.numberOfRooms !== undefined && it.numberOfRooms !== null) {
                                    const v = parseInt(it.numberOfRooms);
                                    if (!isNaN(v) && v > 0 && v < 5000) return v;
                                }
                                if (Array.isArray(it['@graph'])) stack.push(...it['@graph']);
                            }
                        } catch (e) {}
                    }
                    return null;
                }
                """
            )
            if isinstance(ld_count, int) and ld_count > 0:
                return ld_count
        except Exception as e:
            logger.debug("JSON-LD parse failed for %s: %s", booking_url, e)
        # Raw-HTML fallback (rare but free)
        try:
            html = await page.content()
            m = re.search(r'"numberOfRooms"\s*:\s*(\d{1,4})', html)
            if m:
                v = int(m.group(1))
                if 0 < v < 5000:
                    return v
        except Exception:
            pass
        return None
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass



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
    timeout_ms: int = 45000,
    district_hint: str = "",
    exclude_single_room: bool = True,
    min_review_count: int = 20,
    min_unit_count: int = 0,
    fetch_unit_counts: bool = False,
) -> List[Dict]:
    """Discover competitor candidates near a location by scraping Booking.com search.

    Admins use this to generate a list of nearby hotels with the same property type
    (apartment/hotel/aparthotel), then pick which to add as competitors via the UI.
    Returns a list of dicts with hotel_id, name, slug, booking_url, stars, review_score,
    address, property_type, and is_single_room (bool). Never raises — returns [] on failure.

    When `exclude_single_room=True` (default), candidates whose name suggests a
    single-room listing (e.g. "1 Bedroom Flat", "Studio", "King Size Bed") are
    filtered out — these are not meaningful pricing benchmarks for a multi-room
    PMS-managed property.
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
        # Use `commit` (only wait for nav commit) — Booking.com lazy-loads cards
        # via JS later anyway, so waiting for `domcontentloaded` ends up
        # blocking on tracking/ad pixels and frequently hits the 30s timeout
        # giving us 0 candidates. `commit` returns in ~1s, then we explicitly
        # wait_for_selector for the property cards (8s budget, configured below).
        try:
            await page.goto(url, wait_until="commit", timeout=timeout_ms)
        except Exception as nav_e:
            logger.warning("discover_nearby_hotels: initial nav warning (continuing): %s", nav_e)
        await page.wait_for_timeout(3500)

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
                    let review_count = null;
                    if (scoreEl) {
                        const m = scoreEl.textContent.match(/(\\d+\\.\\d+)/);
                        if (m) review_score = parseFloat(m[1]);
                    }
                    // review_count: search the whole card for "1,234 reviews" / "1234 yorum"
                    // patterns. Booking.com places this near the score but on a sibling
                    // element so we widen the search to the whole card text.
                    {
                        const cardText = (c.textContent || '').replace(/\\s+/g, ' ');
                        const cm = cardText.match(/([\\d,]+)\\s*(reviews|yorum|opiniones|avis|recensione|recensioni|Bewertungen|recenzij|reseñas|opinii|opinie|μέσοι όροι)/i);
                        if (cm) {
                            const v = parseInt(cm[1].replace(/,/g, ''));
                            if (!isNaN(v)) review_count = v;
                        }
                    }
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
                    out.push({ hotel_id, name, slug, booking_url: cleanUrl, stars, review_score, review_count, address, property_type: prop_type });
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
                        "stars": None, "review_score": None, "review_count": None,
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
        excluded_single_room = 0
        excluded_tiny = 0
        for r in results:
            key = r.get("slug") or r.get("booking_url", "")
            if not key or key in seen:
                continue
            # Flag single-room/studio listings — optionally filter them out.
            r["is_single_room"] = _is_single_room_listing(r.get("name", ""))
            if exclude_single_room and r["is_single_room"]:
                excluded_single_room += 1
                continue
            # Filter "tiny operations" — properties with very few reviews are
            # likely single-flat owner-operated listings, not multi-unit
            # operations meaningful for pricing benchmark.
            # Only filter when review_count is KNOWN to be below threshold.
            # Listings where rc is None (scraper couldn't extract) are KEPT
            # — let the user decide. Otherwise we lose half the legitimate
            # apartment-market candidates and the UI shows "Auto-Discover 15
            # found 2".
            rc = r.get("review_count")
            if min_review_count > 0 and isinstance(rc, int) and rc < min_review_count:
                excluded_tiny += 1
                r["is_tiny"] = True
                continue
            r["is_tiny"] = False
            seen.add(key)
            deduped.append(r)
        if excluded_single_room:
            logger.info(
                "discover_nearby_hotels: filtered %d single-room listings",
                excluded_single_room,
            )
        if excluded_tiny:
            logger.info(
                "discover_nearby_hotels: filtered %d tiny operations (review_count < %d)",
                excluded_tiny, min_review_count,
            )
        # --- Fetch real unit/room count per candidate (slow, opt-in) ---
        # When fetch_unit_counts=True, we visit each candidate's property page
        # in parallel (max 4 concurrent) and try to extract numberOfRooms from
        # JSON-LD or fallback regex. Result stored in `unit_count`.
        if fetch_unit_counts and deduped:
            sem = asyncio.Semaphore(4)

            async def _fill_unit_count(item):
                async with sem:
                    try:
                        n = await _fetch_property_unit_count(ctx, item.get("booking_url"))
                        item["unit_count"] = n
                    except Exception as e:
                        logger.debug("unit_count fetch failed for %s: %s", item.get("name"), e)
                        item["unit_count"] = None

            await asyncio.gather(*[_fill_unit_count(d) for d in deduped])

            # Apply min_unit_count filter AFTER fetch
            if min_unit_count > 0:
                kept = []
                excluded_small = 0
                for d in deduped:
                    uc = d.get("unit_count")
                    if uc is None:
                        # If we couldn't determine — keep it (let user decide).
                        d["unit_size_known"] = False
                        kept.append(d)
                    elif uc < min_unit_count:
                        excluded_small += 1
                        continue
                    else:
                        d["unit_size_known"] = True
                        kept.append(d)
                if excluded_small:
                    logger.info(
                        "discover_nearby_hotels: filtered %d small operations (unit_count < %d)",
                        excluded_small, min_unit_count,
                    )
                deduped = kept
        # Sort: prefer larger operations first (when known), then more reviews,
        # then higher review_score. Properties with unknown unit_count come last.
        def _sort_key(d):
            uc = d.get("unit_count")
            rc = d.get("review_count")
            rs = d.get("review_score") or 0.0
            # Unknown unit_count → push to bottom by giving -1 (sort descending = lowest)
            uc_key = -(uc or 0) if uc and uc > 0 else 0
            return (uc_key, -(rc or -1), -rs)
        deduped.sort(key=_sort_key)
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
