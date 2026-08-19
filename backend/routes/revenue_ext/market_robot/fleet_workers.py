"""Filo geneli arka plan işçileri — geo doğrulama, vision zenginleştirme, rakip fiyat taraması."""
import os
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from .geo_utils import _osm_hotel_count, _google_places_hotel_count, _radius_based_property_count, _price_stats

logger = logging.getLogger(__name__)

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

