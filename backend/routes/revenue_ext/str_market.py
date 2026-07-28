"""
Airbnb / STR Pazar Verisi — Booking.com CANLI scraper + simülasyon fallback.

Mevcut Booking.com scraping altyapısını (market_robot ile aynı desen) kullanarak
apartman / tatil evi / villa segmentini (ht_id=201,220,213) tarar:
gerçek medyan gecelik fiyat, aktif arz ve doluluk (unavailable %) sinyali üretir.

Canlı veri yoksa deterministik simülasyona düşer (satır bazında source alanı).

Collections:
  str_market_snapshots  {property_id, date, median_rate, avg_rate, min_rate,
                         active_listings, unavailable_pct, source, method, scanned_at}
  str_scan_status       {property_id, status, scanned, total, live_ok, started_at, finished_at}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional
import asyncio
import hashlib
import logging
import math
import re
import os
import random as _rand

import httpx

logger = logging.getLogger(__name__)

# Booking.com property-type filters: 201=Apartments, 220=Holiday Homes, 213=Villas
STR_NFLT = "ht_id%3D201%3Bht_id%3D220%3Bht_id%3D213"
SCAN_OFFSETS = [0, 1, 2, 3, 5, 7, 10, 14]
LIVE_FRESH_HOURS = 48

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

# Booking.com free-text `ss=` şehir çözümü için dest_id (booking_scraper ile aynı değerler)
CITY_DEST_IDS = {
    "london": ("-2601889", "city"),
    "zurich": ("-2554920", "city"),
    "zürich": ("-2554920", "city"),
    "berlin": ("-1746443", "city"),
    "munich": ("-1829149", "city"),
    "münchen": ("-1829149", "city"),
    "istanbul": ("-755070", "city"),
}


def _h(seed: str, lo: float, hi: float) -> float:
    n = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return lo + n * (hi - lo)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _median(vals: list) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    return round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2, 2)


def _count_cards(html: str) -> int:
    for marker in ['data-testid="property-card"', 'data-testid="property-card-container"']:
        c = html.count(marker)
        if c:
            return c
    return 0


async def scrape_str_date(city: str, checkin: str, checkout: str,
                          latitude: Optional[float] = None, longitude: Optional[float] = None,
                          radius_km: float = 5.0, currency: str = "GBP") -> Optional[dict]:
    """Booking.com STR (apartman/tatil evi/villa) araması — tek tarih."""
    cur_param = f"&selected_currency={currency.upper()}" if currency else ""
    if latitude is not None and longitude is not None:
        radius_m = int(radius_km * 1000)
        nflt = f"distance%3D{radius_m}%3B{STR_NFLT}"
        url = (f"https://www.booking.com/searchresults.en-gb.html?"
               f"ss={city or 'Hotel'}&latitude={latitude}&longitude={longitude}"
               f"&checkin={checkin}&checkout={checkout}&group_adults=2&no_rooms=1&group_children=0"
               f"&nflt={nflt}{cur_param}")
    else:
        dest = CITY_DEST_IDS.get((city or "").strip().lower())
        dest_param = f"&dest_id={dest[0]}&dest_type={dest[1]}" if dest else ""
        url = (f"https://www.booking.com/searchresults.en-gb.html?"
               f"ss={city}{dest_param}&checkin={checkin}&checkout={checkout}"
               f"&group_adults=2&no_rooms=1&group_children=0&nflt={STR_NFLT}{cur_param}")

    ua = _rand.choice(USER_AGENTS)
    strategies = [
        {"Referer": "https://www.google.com/", "Sec-Fetch-Site": "cross-site"},
        {"Referer": "https://www.booking.com/", "Sec-Fetch-Site": "same-origin"},
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
                if resp.status_code == 202 or "challenge" in text[:500].lower():
                    continue
                parsed = _parse_search_html(text)
                if parsed:
                    return {**parsed, "method": "direct"}
        except Exception as e:
            logger.warning(f"STR scrape strategy failed {checkin}: {e}")
            continue

    scraping_key = os.environ.get("SCRAPINGBEE_API_KEY", "")
    if scraping_key:
        try:
            api_url = (f"https://app.scrapingbee.com/api/v1/?api_key={scraping_key}"
                       f"&url={url}&render_js=false&country_code=gb")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(api_url)
                parsed = _parse_search_html(resp.text)
                if parsed:
                    return {**parsed, "method": "scrapingbee"}
        except Exception as e:
            logger.warning(f"STR ScrapingBee failed {checkin}: {e}")

    # Playwright warm-context fallback — passes Booking's bot challenge
    return await _scrape_str_via_browser(url)


async def _scrape_str_via_browser(url: str) -> Optional[dict]:
    try:
        from utils.booking_scraper import _get_warm_booking_context
        ctx = await _get_warm_booking_context()
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=35000)
            try:
                await page.wait_for_selector('[data-testid="property-card"]', timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(1200)
            html = await page.content()
        finally:
            await page.close()
        parsed = _parse_search_html(html)
        if parsed:
            return {**parsed, "method": "browser"}
    except Exception as e:
        logger.warning(f"STR browser scrape failed: {e}")
    return None


def _parse_search_html(text: str) -> Optional[dict]:
    total_match = re.search(r'([\d,]+)\s*propert(?:y|ies)\s*found', text)
    total = int(total_match.group(1).replace(",", "")) if total_match else 0
    cards = _count_cards(text)
    if total == 0 and cards == 0:
        return None
    unavail_match = re.search(r'(\d+)%\s*of\s*places?\s*to\s*stay\s*are\s*unavailable', text)
    unavailable_pct = int(unavail_match.group(1)) if unavail_match else 0
    price_matches = re.findall(r'(?:£|US\$|\$|€)\s*([\d,]+(?:\.\d+)?)', text)
    prices = []
    for pm in price_matches[:120]:
        try:
            val = float(pm.replace(",", ""))
            if 20 <= val <= 5000:
                prices.append(val)
        except Exception:
            pass
    if not prices:
        return None
    return {
        "active_listings": max(cards, min(total, 1000)) if total else cards,
        "unavailable_pct": unavailable_pct,
        "median_rate": _median(prices),
        "avg_rate": round(sum(prices) / len(prices), 2),
        "min_rate": round(min(prices), 2),
        "price_samples": len(prices),
    }


def _sim_row(property_id: str, base_nightly: float, listings_total: int, d) -> dict:
    ds = d.strftime("%Y-%m-%d")
    dow = d.weekday()
    dow_mult = 1.18 if dow in (4, 5) else (0.95 if dow == 6 else 1.0)
    season_mult = 1.0 + 0.18 * math.sin((d.timetuple().tm_yday / 365.0) * 2 * math.pi - 1.6)
    jitter = _h(f"{property_id}:{ds}:j", 0.94, 1.06)
    occ = round(_h(f"{property_id}:{ds}:o", 42, 88) * dow_mult / 1.05, 1)
    return {"date": ds,
            "median_rate": round(base_nightly * dow_mult * season_mult * jitter, 2),
            "active_listings": int(listings_total * _h(f"{property_id}:{ds}:s", 0.72, 0.95)),
            "occupancy_proxy": min(occ, 97.0),
            "source": "simulated"}


async def run_str_scan(db, property_id: str, offsets: Optional[list] = None) -> dict:
    """STR canlı taraması — router ve gece cron'u (workers.py) ortak kullanır."""
    offsets = offsets or SCAN_OFFSETS
    prop = await db.properties.find_one(
        {"id": property_id},
        {"_id": 0, "city": 1, "latitude": 1, "longitude": 1, "currency": 1}) or {}
    city = prop.get("city") or "London"
    currency = (prop.get("currency") or "GBP").upper()
    today = datetime.now(timezone.utc).date()
    live_ok = 0
    for idx, off in enumerate(offsets):
        d = today + timedelta(days=off)
        checkin = d.strftime("%Y-%m-%d")
        checkout = (d + timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            res = await scrape_str_date(
                city, checkin, checkout,
                latitude=prop.get("latitude"), longitude=prop.get("longitude"),
                currency=currency)
        except Exception as e:
            logger.warning(f"STR scan error {checkin}: {e}")
            res = None
        if res:
            live_ok += 1
            await db.str_market_snapshots.update_one(
                {"property_id": property_id, "date": checkin},
                {"$set": {"property_id": property_id, "date": checkin,
                          "median_rate": res["median_rate"], "avg_rate": res["avg_rate"],
                          "min_rate": res["min_rate"],
                          "active_listings": res["active_listings"],
                          "unavailable_pct": res["unavailable_pct"],
                          "price_samples": res["price_samples"],
                          "currency": currency,
                          "source": "booking-live", "method": res["method"],
                          "scanned_at": _now()}},
                upsert=True)
        await db.str_scan_status.update_one(
            {"property_id": property_id},
            {"$set": {"scanned": idx + 1, "live_ok": live_ok}})
        await asyncio.sleep(1.2)
    await db.str_scan_status.update_one(
        {"property_id": property_id},
        {"$set": {"status": "done", "finished_at": _now(),
                  "live_ok": live_ok, "scanned": len(offsets)}})
    logger.info(f"STR scan done for {property_id}: {live_ok}/{len(offsets)} live dates")
    return {"live_ok": live_ok, "total": len(offsets)}


def create_str_market_router(db, require_roles):
    router = APIRouter(prefix="/str-market", tags=["str-market"])

    @router.post("/{property_id}/scan")
    async def start_scan(property_id: str, days: int = 14,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        status = await db.str_scan_status.find_one({"property_id": property_id}, {"_id": 0})
        if status and status.get("status") == "running":
            started = status.get("started_at", "")
            if started > (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat():
                raise HTTPException(409, "Tarama zaten çalışıyor")
        offsets = [o for o in SCAN_OFFSETS if o <= max(1, min(30, days))]
        await db.str_scan_status.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, "status": "running",
                      "scanned": 0, "total": len(offsets), "live_ok": 0,
                      "started_at": _now(), "finished_at": None,
                      "started_by": current_user.get("email")}},
            upsert=True)
        asyncio.create_task(run_str_scan(db, property_id, offsets))
        return {"started": True, "dates_to_scan": len(offsets), "offsets": offsets}

    @router.get("/{property_id}/scan/status")
    async def scan_status(property_id: str,
                          _u: dict = Depends(require_roles("admin", "manager"))):
        status = await db.str_scan_status.find_one({"property_id": property_id}, {"_id": 0})
        return status or {"property_id": property_id, "status": "idle"}

    @router.get("/{property_id}/overview")
    async def overview(property_id: str, days: int = 60,
                       _u: dict = Depends(require_roles("admin", "manager"))):
        days = max(7, min(180, days))
        rts = await db.room_types.find({"property_id": property_id},
                                       {"_id": 0, "base_rate": 1}).to_list(50)
        hotel_base = (sum(float(r.get("base_rate", 0) or 0) for r in rts) / len(rts)) if rts else 130.0
        hotel_base = hotel_base or 130.0
        listings_total_sim = int(_h(f"{property_id}:listings", 60, 240))
        entire_pct = round(_h(f"{property_id}:entire", 55, 80), 1)

        today = datetime.now(timezone.utc).date()
        end_str = (today + timedelta(days=days)).strftime("%Y-%m-%d")
        fresh_cutoff = (datetime.now(timezone.utc) - timedelta(hours=LIVE_FRESH_HOURS)).isoformat()
        live_rows = await db.str_market_snapshots.find(
            {"property_id": property_id,
             "date": {"$gte": today.strftime("%Y-%m-%d"), "$lte": end_str},
             "scanned_at": {"$gte": fresh_cutoff}},
            {"_id": 0}).to_list(200)
        live_map = {r["date"]: r for r in live_rows}

        # Kalibrasyon: canlı veri varsa simülasyon bazını canlı medyana hizala
        sim_base = hotel_base * 0.62
        sim_listings = listings_total_sim
        if live_rows:
            norm = []
            for r in live_rows:
                d0 = datetime.strptime(r["date"], "%Y-%m-%d")
                dow_mult = 1.18 if d0.weekday() in (4, 5) else (0.95 if d0.weekday() == 6 else 1.0)
                season_mult = 1.0 + 0.18 * math.sin((d0.timetuple().tm_yday / 365.0) * 2 * math.pi - 1.6)
                norm.append(float(r["median_rate"]) / max(dow_mult * season_mult, 0.1))
            sim_base = sum(norm) / len(norm)
            sim_listings = round(sum(r["active_listings"] for r in live_rows) / len(live_rows))

        rows = []
        for i in range(days):
            d = today + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            lv = live_map.get(ds)
            if lv:
                rows.append({"date": ds,
                             "median_rate": lv["median_rate"],
                             "active_listings": lv["active_listings"],
                             "occupancy_proxy": float(lv.get("unavailable_pct") or 0),
                             "source": "booking-live"})
            else:
                rows.append(_sim_row(property_id, sim_base, sim_listings, d))

        live_count = sum(1 for r in rows if r["source"] == "booking-live")
        med_avg = round(sum(r["median_rate"] for r in rows) / len(rows), 2)
        gap_pct = round((hotel_base - med_avg) / med_avg * 100, 1) if med_avg else 0
        weekend_rows = [r for r in rows if datetime.strptime(r["date"], "%Y-%m-%d").weekday() in (4, 5)]
        weekend_uplift = 0.0
        if weekend_rows:
            weekend_uplift = round(
                (sum(r["median_rate"] for r in weekend_rows) / len(weekend_rows) - med_avg) / med_avg * 100, 1)
        listings_display = (round(sum(r["active_listings"] for r in rows if r["source"] == "booking-live")
                                  / live_count) if live_count else listings_total_sim)
        high_occ = [r["date"] for r in rows if r["occupancy_proxy"] >= 80][:3]
        last_scan = max((r.get("scanned_at", "") for r in live_rows), default=None)

        findings = []
        if live_count:
            findings.append(
                f"Booking.com canlı taramasından {live_count} tarih için gerçek STR verisi kullanılıyor (apartman + tatil evi + villa segmenti); kalan tarihler canlı medyana kalibre edilmiş tahmindir.")
        findings.append(f"Bölgede ~{listings_display} aktif STR ilanı{'' if live_count else f' (%{entire_pct} tüm ev, simülasyon)'}.")
        findings.append(
            f"STR medyan gecelik fiyat £{med_avg} — otel baz fiyatınız STR pazarının %{abs(gap_pct)} {'üzerinde' if gap_pct >= 0 else 'altında'}.")
        findings.append(
            f"Hafta sonu STR fiyatları medyana göre %{weekend_uplift} yukarıda — Cuma/Cumartesi fiyat tavanınızı gözden geçirin.")
        if high_occ:
            findings.append(
                f"Talep baskısı yüksek günler: {', '.join(high_occ)} — bu tarihlerde fiyat yükseltme fırsatı.")

        return {
            "property_id": property_id,
            "days": days,
            "rows": rows,
            "summary": {
                "listings_total": listings_display,
                "entire_home_pct": entire_pct,
                "median_rate_avg": med_avg,
                "hotel_base_rate": round(hotel_base, 2),
                "hotel_vs_str_gap_pct": gap_pct,
                "weekend_uplift_pct": weekend_uplift,
                "live_dates": live_count,
                "simulated_dates": len(rows) - live_count,
                "last_scan_at": last_scan,
            },
            "findings": findings,
            "source": "hybrid" if live_count else "simulated",
        }

    return router
