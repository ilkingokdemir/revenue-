"""Playwright-based Booking.com scraper.

Used by Market Robot to bypass Booking's anti-bot HTTP 202 JS challenge.
A single shared Chromium browser process is kept warm to avoid launch overhead
(~800 MB RAM). Each scrape spawns a fresh context (private cookies) to evade
session-level rate limiting.

Price extraction strategy (layered):
1. Prefer prices near `data-testid="price-and-discounted-price"` DOM nodes.
2. Fall back to currency-prefix regex sweep across the full page HTML.

Returns {lowest_price, all_prices, score} so callers can store uniform records.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import List, Optional

# Ensure Playwright finds its browsers when backend runs under supervisor (where
# ~/.cache/ms-playwright doesn't exist but /pw-browsers does)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

from playwright.async_api import Browser, async_playwright

logger = logging.getLogger(__name__)

_browser: Optional[Browser] = None
_pw = None
_lock = asyncio.Lock()


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


_PRICE_RE = re.compile(r"(?:CHF|GBP|EUR|USD|TRY|£|€|\$|Fr\.|Fr\s)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_REVIEW_RE = re.compile(r'Scored\s+([\d.]+)|"reviewScore"\s*:\s*"?([\d.]+)"?')


def _extract_prices(html: str) -> List[float]:
    raw = _PRICE_RE.findall(html)
    out = []
    for p in raw:
        try:
            val = float(p.replace(",", ""))
            # Floor at 40 filters out review counts (e.g. "30 reviews") and star ratings.
            if 40 <= val <= 5000:
                out.append(val)
        except ValueError:
            continue
    return out


def _extract_review(html: str) -> Optional[float]:
    m = _REVIEW_RE.search(html)
    if not m:
        return None
    for g in m.groups():
        if g:
            try:
                return float(g)
            except ValueError:
                continue
    return None


async def scrape_booking_url(url: str, timeout_ms: int = 35000) -> dict:
    """Fetch a single Booking.com hotel URL and extract lowest price + review score.

    Strategy:
    1. Try DOM-based price extraction via `[data-testid="price-and-discounted-price"]` selector
       (most accurate — direct hit on Booking's price widget).
    2. Fall back to regex sweep only if no DOM prices found.

    Returns:
        {"lowest_price": float|None, "all_prices": list[float], "score": float|None,
         "scraped": bool, "error": str|None}
    """
    browser = await _get_browser()
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        locale="en-GB",
        viewport={"width": 1280, "height": 900},
    )
    page = await ctx.new_page()
    prices_dom: List[float] = []
    score: Optional[float] = None
    html = ""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        # Give price widgets time to hydrate
        try:
            await page.wait_for_selector(
                '[data-testid="price-and-discounted-price"], .prco-valign-middle-helper, span[class*="prco"]',
                timeout=10000,
            )
        except Exception:
            pass

        # DOM price extraction — precise
        try:
            dom_texts = await page.evaluate("""
                () => {
                    const sels = [
                        '[data-testid="price-and-discounted-price"]',
                        '.prco-valign-middle-helper',
                        'span.prd-pri-1vb6sg2',
                        'span[class*="prco-inline"]',
                    ];
                    const out = new Set();
                    for (const s of sels) {
                        document.querySelectorAll(s).forEach(n => {
                            const t = (n.innerText || n.textContent || '').trim();
                            if (t) out.add(t);
                        });
                    }
                    return Array.from(out);
                }
            """)
            for t in (dom_texts or []):
                for m in re.findall(r"([\d,]+(?:\.\d+)?)", str(t).replace("\xa0", " ")):
                    try:
                        v = float(m.replace(",", ""))
                        if 40 <= v <= 5000:
                            prices_dom.append(v)
                    except ValueError:
                        continue
        except Exception:
            pass

        # Review score via DOM
        try:
            score = await page.evaluate("""
                () => {
                    const el = document.querySelector('[data-testid="review-score-right-component"] div, .b5cd09854e, span[class*="reviewScore"]');
                    if (!el) return null;
                    const m = (el.innerText || '').match(/([\\d.]+)/);
                    return m ? parseFloat(m[1]) : null;
                }
            """)
            if score is not None:
                score = float(score)
        except Exception:
            pass

        html = await page.content()
    except Exception as exc:
        await ctx.close()
        return {"lowest_price": None, "all_prices": [], "score": None, "scraped": False, "error": str(exc)}
    finally:
        try:
            await page.close()
        except Exception:
            pass

    await ctx.close()

    # Prefer DOM-based prices; fall back to regex if empty
    if prices_dom:
        all_prices = sorted(set(prices_dom))
    else:
        all_prices = sorted(set(_extract_prices(html)))

    if score is None:
        score = _extract_review(html)

    lowest = all_prices[0] if all_prices else None
    return {
        "lowest_price": lowest,
        "all_prices": all_prices[:8],
        "score": score,
        "scraped": lowest is not None,
        "error": None,
    }


def build_dated_url(base_url: str, checkin: str, checkout: str) -> str:
    """Strip any existing query params and append a clean date range."""
    clean = base_url.split("?")[0]
    return f"{clean}?checkin={checkin}&checkout={checkout}&group_adults=2&no_rooms=1"
