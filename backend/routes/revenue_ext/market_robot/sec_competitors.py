"""Market Robot bölümü — core fabrikasından faz-2'de ayrıldı. register(router, db, require_roles, resend, S) çağrılır; bölümler arası paylaşım S (SimpleNamespace) üzerinden."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional, Tuple
import uuid
import re
import asyncio
import logging
import os
import httpx

from .state import (SCRAPE_LOCKS, SCRAPE_LOCKS_GEO, MAX_CONCURRENT_SCANS,
                    AUTO_SCAN_MAX_DAYS)
from .gap_logic import _internal_close_gap
from .geo_utils import (_count_booking_cards, _osm_hotel_count, _google_places_hotel_count,
                        _radius_based_property_count, _price_stats)

logger = logging.getLogger(__name__)

def register(router, db, require_roles, resend, S):

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

    S._do_auto_heal_competitors = _do_auto_heal_competitors
    S._do_revalidate_competitors = _do_revalidate_competitors
    S.add_competitor = add_competitor
    S.auto_geocode_property = auto_geocode_property
    S.auto_heal_competitors = auto_heal_competitors
    S.auto_heal_status = auto_heal_status
    S.clear_all_competitors = clear_all_competitors
    S.discover_nearby_competitors = discover_nearby_competitors
    S.get_auto_heal_config = get_auto_heal_config
    S.get_competitors = get_competitors
    S.get_discover_status = get_discover_status
    S.put_auto_heal_config = put_auto_heal_config
    S.remove_competitor = remove_competitor
    S.revalidate_all_competitors = revalidate_all_competitors
    S.revalidate_status = revalidate_status
    S.validate_booking_url_endpoint = validate_booking_url_endpoint
