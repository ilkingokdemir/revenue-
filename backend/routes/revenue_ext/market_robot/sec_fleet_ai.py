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

    @router.post("/revenue/market-robot/fleet-reset-neighbors")
    async def fleet_reset_neighbors(
        data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Fleet-wide: for EVERY property, run the same 3-step reset that the
        single-property UI button does — clear all competitors, force-geocode,
        re-discover with radius. Returns per-property results.

        Body (optional):
          - property_ids: [] — restrict to specific IDs (default: ALL active)
          - radius_km: 2.0 (default)
          - max_results: 15 (default)
          - dry_run: false — when true, only reports what would happen
          - auto_add: false — when true, top `auto_add_top` discovered candidates
            are immediately inserted as competitors for each property (0-click).
          - auto_add_top: 5 — how many top-ranked candidates to auto-add.
        """
        from utils.booking_scraper import discover_nearby_hotels, geocode_address, _extract_district_hint

        radius_km = max(0.5, min(float((data or {}).get("radius_km") or 2.0), 10.0))
        max_results = max(5, min(int((data or {}).get("max_results") or 15), 50))
        dry_run = bool((data or {}).get("dry_run"))
        auto_add = bool((data or {}).get("auto_add"))
        auto_add_top = max(1, min(int((data or {}).get("auto_add_top") or 5), 15))
        target_ids = (data or {}).get("property_ids") or []
        exclude_single_room = bool((data or {}).get("exclude_single_room", True))
        min_review_count = max(0, min(int((data or {}).get("min_review_count") or 20), 500))

        prop_query: Dict = {"is_active": {"$ne": False}}
        if target_ids:
            prop_query["id"] = {"$in": list(target_ids)}
        props = await db.properties.find(
            prop_query,
            {"_id": 0, "id": 1, "name": 1, "city": 1, "postcode": 1, "address": 1,
             "latitude": 1, "longitude": 1, "currency": 1, "geocoded_display_name": 1,
             "property_type": 1, "type": 1},
        ).to_list(200)

        TYPE_MAP = {
            "apartment": "apartments", "apartments": "apartments",
            "aparthotel": "aparthotels", "aparthotels": "aparthotels",
            "serviced_apartment": "apartments",
            "hotel": "hotels", "hotels": "hotels",
            "guest_house": "hotels", "guesthouse": "hotels",
            "bnb": "hotels", "b&b": "hotels",
        }

        results = []
        for prop in props:
            pid = prop.get("id")
            if not pid:
                continue
            entry = {"property_id": pid, "name": prop.get("name"), "city": prop.get("city")}
            if dry_run:
                entry["status"] = "would_reset"
                results.append(entry)
                continue
            try:
                # 1) Clear existing
                prev_comps = await db.market_competitors.find(
                    {"property_id": pid}, {"_id": 0, "id": 1}
                ).to_list(200)
                prev_count = len(prev_comps)
                if prev_count:
                    await db.market_competitors.delete_many({"property_id": pid})
                    await db.market_supply.delete_many({"property_id": pid})

                # 2) Force geocode (country-aware + city-validated)
                name = (prop.get("name") or "").strip()
                city = (prop.get("city") or "").strip()
                postcode = (prop.get("postcode") or "").strip()
                address = (prop.get("address") or "").strip()
                country_raw = (prop.get("country") or "").strip().upper()
                COUNTRY_MAP_FR = {"UK": "gb", "GB": "gb", "ENGLAND": "gb", "UNITED KINGDOM": "gb",
                                  "US": "us", "USA": "us", "UNITED STATES": "us",
                                  "TR": "tr", "TURKEY": "tr", "TÜRKIYE": "tr",
                                  "FR": "fr", "FRANCE": "fr", "DE": "de", "GERMANY": "de",
                                  "ES": "es", "SPAIN": "es", "IT": "it", "ITALY": "it",
                                  "NL": "nl", "NETHERLANDS": "nl"}
                country_code = COUNTRY_MAP_FR.get(country_raw, country_raw.lower()[:2] if country_raw else "")
                candidates_q = []
                if address:
                    candidates_q.append(" ".join([x for x in [address, postcode, city] if x]))
                if name and city:
                    candidates_q.append(f"{name} {city}")
                if postcode and city:
                    candidates_q.append(f"{postcode} {city}")
                if name and country_code:
                    candidates_q.append(name)
                seen = set()
                ordered_q = []
                for q in candidates_q:
                    qn = q.strip()
                    if qn and qn.lower() not in seen:
                        seen.add(qn.lower())
                        ordered_q.append(qn)

                geo_ok = False
                latitude = None
                longitude = None
                display = ""
                for q in ordered_q:
                    geo = await geocode_address(q, country_code=country_code)
                    if geo:
                        cand_lat, cand_lon, cand_display = geo
                        # City sanity check — reject if city mismatch
                        if city and city.lower() not in cand_display.lower():
                            continue
                        latitude, longitude, display = cand_lat, cand_lon, cand_display
                        await db.properties.update_one(
                            {"id": pid},
                            {"$set": {
                                "latitude": latitude, "longitude": longitude,
                                "geocoded_from": q, "geocoded_display_name": display,
                                "geocoded_at": datetime.now(timezone.utc).isoformat(),
                            }},
                        )
                        geo_ok = True
                        break

                if not geo_ok:
                    entry["status"] = "geocode_failed"
                    entry["cleared"] = prev_count
                    results.append(entry)
                    continue

                # 3) Discover nearby — use inferred property type filter
                raw_type = (prop.get("property_type") or prop.get("type") or "").lower().strip()
                inf_type = TYPE_MAP.get(raw_type, "any")
                district_hint = _extract_district_hint(display, postcode, city) if display else ""
                cands = await discover_nearby_hotels(
                    postcode=postcode, city=city, latitude=latitude, longitude=longitude,
                    property_type=inf_type, max_results=max_results, radius_km=radius_km,
                    language="en-gb", currency=(prop.get("currency") or "GBP"),
                    district_hint=district_hint,
                    exclude_single_room=exclude_single_room,
                    min_review_count=min_review_count,
                )
                entry["status"] = "ok"
                entry["cleared"] = prev_count
                entry["geocoded_from"] = display[:80] if display else ""
                entry["candidates_found"] = len(cands)
                entry["property_type_filter"] = inf_type

                # 4) Auto-add top candidates as competitors (when requested)
                if auto_add and cands:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    added_ct = 0
                    for cand in cands[:auto_add_top]:
                        url = (cand.get("booking_url") or "").rstrip("/").split("?")[0]
                        name_c = (cand.get("name") or "").strip()
                        hid = str(cand.get("booking_hotel_id") or cand.get("hotel_id") or "")
                        if not url or not name_c:
                            continue
                        slug_m = re.search(r"/hotel/[a-z]{2}/([a-z0-9-]+)\.", url)
                        slug = slug_m.group(1) if slug_m else name_c.lower().replace(" ", "-")[:40]
                        # Skip if already exists (race-safe upsert by booking_url)
                        existing = await db.market_competitors.find_one(
                            {"property_id": pid, "booking_url": url}, {"_id": 0, "id": 1}
                        )
                        if existing:
                            continue
                        await db.market_competitors.insert_one({
                            "id": str(uuid.uuid4()),
                            "property_id": pid,
                            "name": name_c,
                            "booking_url": url,
                            "slug": slug,
                            "booking_hotel_id": hid or None,
                            "stars": cand.get("stars"),
                            "review_score": cand.get("review_score"),
                            "prices": [],
                            "score": None,
                            "last_scraped": None,
                            "last_source": "fleet_reset_autoadd",
                            "last_validation": {
                                "ok": True, "checked_at": now_iso,
                                "hotel_name": name_c, "hotel_id": hid or None,
                            },
                            "created_at": now_iso,
                            "created_by": "fleet_reset_autoadd",
                        })
                        added_ct += 1
                    entry["auto_added"] = added_ct
            except Exception as e:
                entry["status"] = "error"
                entry["error"] = str(e)[:160]
            results.append(entry)

        ok_count = sum(1 for r in results if r.get("status") == "ok")
        total_added = sum(r.get("auto_added", 0) or 0 for r in results)
        return {
            "ok": True,
            "total_properties": len(props),
            "ok_count": ok_count,
            "auto_added": total_added,
            "auto_add": auto_add,
            "dry_run": dry_run,
            "results": results,
            "message": (
                f"Fleet reset: {ok_count}/{len(props)} property işlendi. "
                f"radius={radius_km}km, max={max_results}."
                + (f" Auto-added {total_added} competitors (top {auto_add_top}/property)." if auto_add else "")
            ),
        }

    @router.post("/revenue/market-robot/fleet-validate-geo")
    async def fleet_validate_geo(
        data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Fleet-wide coordinate sanity check + auto-repair.

        For every active property with lat/lon stored, reverse-geocode the
        coordinates via Nominatim and check whether the resulting country code
        matches the property's `country` field. If it doesn't (e.g. UK property
        landed on US lat/lon — the Camden→Boston bug), the property is flagged
        and — when `fix=true` — re-geocoded using the country-biased forward
        path. Always returns a per-property report.

        Body (optional):
          - property_ids: [] — restrict to specific IDs (default: ALL active)
          - dry_run: true (default) — only report; do not write
          - fix: false (default) — when true, re-geocode flagged properties
          - sleep_s: 1.1 — Nominatim free policy enforces 1 req/sec.
        """
        from utils.booking_scraper import (
            reverse_geocode, geocode_address,
        )

        target_ids = (data or {}).get("property_ids") or []
        dry_run = bool((data or {}).get("dry_run", True))
        fix = bool((data or {}).get("fix", False))
        sleep_s = float((data or {}).get("sleep_s") or 1.1)
        sleep_s = max(0.5, min(sleep_s, 3.0))

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

        prop_query: Dict = {"is_active": {"$ne": False}}
        if target_ids:
            prop_query["id"] = {"$in": target_ids}
        props = await db.properties.find(
            prop_query,
            {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1,
             "postcode": 1, "address": 1, "latitude": 1, "longitude": 1,
             "geocoded_display_name": 1},
        ).to_list(500)

        ok_count = 0
        flagged_count = 0
        fixed_count = 0
        skipped_count = 0
        results = []

        for prop in props:
            pid = prop.get("id")
            pname = prop.get("name") or pid
            lat = prop.get("latitude")
            lon = prop.get("longitude")
            city = (prop.get("city") or "").strip()
            country_raw = (prop.get("country") or "").strip().upper()
            expected_cc = COUNTRY_MAP_FV.get(country_raw, country_raw.lower()[:2] if country_raw else "")

            entry = {
                "property_id": pid,
                "name": pname,
                "city": city,
                "country": country_raw,
                "expected_country_code": expected_cc,
                "before": {"latitude": lat, "longitude": lon,
                           "display": prop.get("geocoded_display_name")},
                "status": "skipped",
                "reason": None,
            }

            if not (lat and lon):
                entry["reason"] = "no_coordinates"
                skipped_count += 1
                results.append(entry)
                continue
            if not expected_cc:
                entry["reason"] = "no_country_on_property"
                skipped_count += 1
                results.append(entry)
                continue

            # Reverse geocode current coords — confirm where they actually land.
            rev = await reverse_geocode(lat, lon)
            await asyncio.sleep(sleep_s)
            if not rev:
                entry["status"] = "unknown"
                entry["reason"] = "reverse_geocode_failed"
                skipped_count += 1
                results.append(entry)
                continue

            actual_cc = (rev.get("country_code") or "").lower()
            actual_city = (rev.get("city") or "").lower()
            entry["actual_country_code"] = actual_cc
            entry["actual_city"] = rev.get("city")
            entry["actual_display"] = rev.get("display_name")

            country_match = (actual_cc == expected_cc)
            city_match = True
            if city and actual_city:
                # forgiving: city contained in either direction
                cl = city.lower()
                city_match = (cl in actual_city) or (actual_city in cl)

            if country_match and city_match:
                entry["status"] = "ok"
                entry["reason"] = "country_and_city_match"
                ok_count += 1
                results.append(entry)
                continue

            # Mismatch — flag.
            entry["status"] = "flagged"
            entry["reason"] = (
                "country_mismatch" if not country_match
                else "city_mismatch"
            )
            flagged_count += 1

            if dry_run or not fix:
                results.append(entry)
                continue

            # Repair path: forward-geocode with country bias and persist.
            name = (prop.get("name") or "").strip()
            postcode = (prop.get("postcode") or "").strip()
            address = (prop.get("address") or "").strip()

            candidates_q = []
            if address:
                candidates_q.append(" ".join([x for x in [address, postcode, city] if x]))
            if postcode and city:
                candidates_q.append(f"{postcode} {city}")
            if name and city:
                candidates_q.append(f"{name} {city}")
            if name and expected_cc:
                candidates_q.append(name)

            seen = set()
            ordered_q = []
            for q in candidates_q:
                qn = (q or "").strip()
                if qn and qn.lower() not in seen:
                    seen.add(qn.lower())
                    ordered_q.append(qn)

            repaired = False
            for q in ordered_q:
                geo = await geocode_address(q, country_code=expected_cc)
                await asyncio.sleep(sleep_s)
                if not geo:
                    continue
                new_lat, new_lon, new_display = geo
                # Sanity: display must include the property's city
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
                entry["status"] = "fixed"
                entry["after"] = {"latitude": new_lat, "longitude": new_lon,
                                  "display": new_display, "geocoded_from": q}
                fixed_count += 1
                repaired = True
                break

            if not repaired:
                entry["status"] = "unfixable"
                entry["reason"] = "no_geocode_match_with_country_bias"

            results.append(entry)

        return {
            "ok": True,
            "total_properties": len(props),
            "ok_count": ok_count,
            "flagged_count": flagged_count,
            "fixed_count": fixed_count,
            "skipped_count": skipped_count,
            "dry_run": dry_run,
            "fix": fix,
            "results": results,
            "message": (
                f"Geo validate: {ok_count} OK · {flagged_count} flag · "
                f"{fixed_count} fixed · {skipped_count} skipped "
                f"({'DRY-RUN' if dry_run else 'LIVE'})."
            ),
        }

    @router.post("/revenue/market-robot/fleet-classify-property-types")
    async def fleet_classify_property_types(
        data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Fleet-wide AI Property-Type Inference.

        Uses GPT-4o-mini to re-classify each property's `property_type`
        based on its name (e.g. "Camden Apartments" → apartment,
        "City Gate Guest House" → guesthouse, "Whitechapel Grand" → hotel).

        Booking.com filter implications:
          - apartment / serviced_apartment → "apartments" filter
          - aparthotel                     → "aparthotels" filter
          - hotel / guesthouse / bnb / b&b → "hotels" filter

        Body (optional):
          - property_ids: [] — restrict to specific IDs
          - dry_run: true (default) — only return preview, no writes
          - only_missing: false — when true, only classify properties whose
            current `property_type` is null/empty/missing
          - confidence_threshold: 0.7 — only persist when AI confidence >= this
          - model: "gpt-4o-mini" (default; supports any Emergent-LLM model)
        """
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
        except ImportError:
            raise HTTPException(500, "emergentintegrations not installed")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

        target_ids = (data or {}).get("property_ids") or []
        dry_run = bool((data or {}).get("dry_run", True))
        only_missing = bool((data or {}).get("only_missing", False))
        conf_thr = float((data or {}).get("confidence_threshold") or 0.7)
        conf_thr = max(0.0, min(conf_thr, 1.0))
        model = (data or {}).get("model") or "gpt-4o-mini"

        prop_query: Dict = {"is_active": {"$ne": False}}
        if target_ids:
            prop_query["id"] = {"$in": target_ids}
        if only_missing:
            prop_query["$or"] = [
                {"property_type": {"$exists": False}},
                {"property_type": None},
                {"property_type": ""},
            ]
        props = await db.properties.find(
            prop_query,
            {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1,
             "property_type": 1, "address": 1},
        ).to_list(500)

        valid_types = {"hotel", "apartment", "serviced_apartment",
                       "aparthotel", "guesthouse", "bnb", "hostel"}

        results = []
        updated_count = 0
        unchanged_count = 0
        skipped_count = 0
        low_confidence_count = 0

        # NOTE: we issue one LlmChat per property (separate session) so each
        # classification is independent and reproducible. This is cheap with
        # gpt-4o-mini and avoids context bleed.
        SYSTEM_PROMPT = (
            "You are a hospitality classification expert. Given a property's "
            "name, city, country and address, classify the lodging type. "
            "Return ONLY compact JSON, no markdown, with EXACTLY these keys: "
            '{"type": "<one of: hotel | apartment | serviced_apartment | aparthotel | guesthouse | bnb | hostel>", '
            '"confidence": <float 0..1>, '
            '"reasoning": "<one short sentence>"}. '
            "Heuristics: names containing 'Apartments', 'Flats', 'Studios', "
            "'Suites' (without 'Hotel') usually mean apartment. 'Guest House', "
            "'B&B' → guesthouse/bnb. 'Hostel' → hostel. 'Aparthotel' or "
            "'Apartment Hotel' → aparthotel. Default to hotel only when name "
            "explicitly contains 'Hotel', 'Inn', 'Grand', 'Plaza', 'Resort'."
        )

        for prop in props:
            pid = prop.get("id")
            pname = (prop.get("name") or "").strip()
            current = (prop.get("property_type") or "").lower().strip()

            entry = {
                "property_id": pid,
                "name": pname,
                "current_type": current or None,
                "city": prop.get("city"),
                "status": "skipped",
                "reason": None,
            }

            if not pname:
                entry["reason"] = "no_name"
                skipped_count += 1
                results.append(entry)
                continue

            user_prompt = (
                f"Property:\n"
                f"  name: {pname}\n"
                f"  city: {prop.get('city') or '-'}\n"
                f"  country: {prop.get('country') or '-'}\n"
                f"  address: {prop.get('address') or '-'}\n"
                f"  current_label: {current or 'null'}\n\n"
                f"Return JSON only."
            )

            try:
                chat = LlmChat(
                    api_key=api_key,
                    session_id=f"classify-{pid}-{uuid.uuid4().hex[:8]}",
                    system_message=SYSTEM_PROMPT,
                ).with_model("openai", model)
                reply = await chat.send_message(UserMessage(text=user_prompt))
                raw = (reply or "").strip()
                # Tolerate ```json fences
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
                import json as _json
                parsed = _json.loads(raw)
                pred_type = (parsed.get("type") or "").lower().strip()
                conf = float(parsed.get("confidence") or 0.0)
                reasoning = (parsed.get("reasoning") or "")[:200]
            except Exception as e:
                entry["status"] = "error"
                entry["reason"] = f"llm_error: {str(e)[:120]}"
                skipped_count += 1
                results.append(entry)
                continue

            entry["predicted_type"] = pred_type
            entry["confidence"] = round(conf, 3)
            entry["reasoning"] = reasoning

            if pred_type not in valid_types:
                entry["status"] = "skipped"
                entry["reason"] = f"invalid_type: {pred_type}"
                skipped_count += 1
                results.append(entry)
                continue

            if conf < conf_thr:
                entry["status"] = "low_confidence"
                entry["reason"] = f"conf {conf:.2f} < threshold {conf_thr:.2f}"
                low_confidence_count += 1
                results.append(entry)
                continue

            if pred_type == current:
                entry["status"] = "unchanged"
                entry["reason"] = "ai_confirmed_current_label"
                unchanged_count += 1
                results.append(entry)
                continue

            # High-confidence change.
            entry["status"] = "would_update" if dry_run else "updated"
            entry["reason"] = (
                f"reclassified from '{current or 'null'}' to '{pred_type}'"
            )
            if not dry_run:
                await db.properties.update_one(
                    {"id": pid},
                    {"$set": {
                        "property_type": pred_type,
                        "property_type_classified_by": "ai-gpt-4o-mini",
                        "property_type_classified_at": datetime.now(timezone.utc).isoformat(),
                        "property_type_classification_confidence": round(conf, 3),
                        "property_type_classification_reason": reasoning,
                        # Iter 322: preserve previous value for one-click rollback.
                        "property_type_previous": current or None,
                        "property_type_previous_reason": (
                            f"AI re-classified {current or 'null'} → {pred_type} on "
                            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                        ),
                    }},
                )
                updated_count += 1
            results.append(entry)

        return {
            "ok": True,
            "total_properties": len(props),
            "updated_count": updated_count,
            "would_update_count": sum(1 for r in results if r["status"] == "would_update"),
            "unchanged_count": unchanged_count,
            "low_confidence_count": low_confidence_count,
            "skipped_count": skipped_count,
            "dry_run": dry_run,
            "only_missing": only_missing,
            "confidence_threshold": conf_thr,
            "model": model,
            "results": results,
            "message": (
                f"AI classify: {updated_count} updated · "
                f"{sum(1 for r in results if r['status'] == 'would_update')} would_update · "
                f"{unchanged_count} unchanged · {low_confidence_count} low_conf · "
                f"{skipped_count} skip "
                f"({'DRY-RUN' if dry_run else 'LIVE'})."
            ),
        }

    @router.get("/revenue/market-robot/ai-classification-history")
    async def ai_classification_history(
        days: int = 30,
        limit: int = 100,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """List properties whose `property_type` was set by AI (GPT-4o-mini).

        Returns each entry with: property_id, name, city, current_type,
        previous_type, confidence, reason, classified_at, classified_by,
        rollback_available (true if `property_type_previous` is set and
        differs from current).

        Query params:
          - days: lookback window (default 30). Set to 0 for ALL time.
          - limit: max rows (default 100, cap 500).
        """
        days = max(0, min(int(days or 0), 365))
        limit = max(1, min(int(limit or 100), 500))

        q: Dict = {"property_type_classified_by": {"$exists": True}}
        if days > 0:
            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            q["property_type_classified_at"] = {"$gte": since}

        rows = await db.properties.find(
            q,
            {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1,
             "property_type": 1, "property_type_previous": 1,
             "property_type_classified_by": 1,
             "property_type_classified_at": 1,
             "property_type_classification_confidence": 1,
             "property_type_classification_reason": 1},
        ).sort("property_type_classified_at", -1).limit(limit).to_list(limit)

        out = []
        for r in rows:
            current = r.get("property_type") or None
            previous = r.get("property_type_previous")
            out.append({
                "property_id": r.get("id"),
                "name": r.get("name"),
                "city": r.get("city"),
                "country": r.get("country"),
                "current_type": current,
                "previous_type": previous,
                "confidence": r.get("property_type_classification_confidence"),
                "reason": r.get("property_type_classification_reason") or "",
                "classified_at": r.get("property_type_classified_at"),
                "classified_by": r.get("property_type_classified_by"),
                "rollback_available": bool(previous and previous != current),
            })
        return {"total": len(out), "days": days, "items": out}

    @router.post("/revenue/market-robot/{property_id}/ai-classification-rollback")
    async def ai_classification_rollback(
        property_id: str,
        data: Dict = {},
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Roll back an AI-driven property_type change to the saved previous value.

        Body (optional): {target_type?: str} — override target instead of using
        the saved `property_type_previous`. Useful when admin wants to set a
        specific value (e.g. "aparthotel") instead of going back to "hotel".
        """
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        explicit = (data or {}).get("target_type")
        if explicit:
            valid_types = {"hotel", "apartment", "serviced_apartment",
                           "aparthotel", "guesthouse", "bnb", "hostel"}
            t = (explicit or "").lower().strip()
            if t not in valid_types:
                raise HTTPException(status_code=400,
                                    detail=f"Invalid target_type. Must be one of {sorted(valid_types)}")
            target = t
        else:
            target = prop.get("property_type_previous")
            if not target:
                raise HTTPException(
                    status_code=400,
                    detail="No saved previous_type for this property. Pass target_type explicitly.",
                )

        current = prop.get("property_type")
        if target == current:
            return {"ok": True, "no_op": True, "current_type": current,
                    "message": "Hedef değer mevcut değerle aynı, değişiklik yok."}

        await db.properties.update_one(
            {"id": property_id},
            {"$set": {
                "property_type": target,
                "property_type_classified_by": f"manual-rollback:{current_user.get('email','admin')}",
                "property_type_classified_at": datetime.now(timezone.utc).isoformat(),
                "property_type_classification_confidence": 1.0,
                "property_type_classification_reason": f"Manual rollback from '{current}' to '{target}'",
                "property_type_previous": current,
                "property_type_previous_reason": (
                    f"Was '{current}' (set by "
                    f"{prop.get('property_type_classified_by','?')}) — rolled back "
                    f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                ),
            }},
        )
        return {"ok": True, "property_id": property_id,
                "previous_type": current, "current_type": target,
                "message": f"Property type '{current}' → '{target}'"}

    @router.post("/revenue/market-robot/scrape-booking-vision")
    async def scrape_booking_vision(
        data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Vision-based extraction from a Booking.com page screenshot.

        Pipeline:
          1. If a /hotel/<cc>/<slug>.html URL is given, automatically append
             checkin/checkout query params 14 days out so prices render.
          2. Playwright screenshots the page (pre-warmed context bypasses
             cold deep-link blocks).
          3. PNG bytes → base64 → GPT-4o-mini vision → JSON.

        "Kullanıcının gözüyle bak" approach — works even when JSON-LD is
        missing or property type is non-standard, because the visual page
        rendering is the source of truth.

        Body:
          - booking_url: required, target Booking.com URL
          - model: optional, default "gpt-4o-mini" (vision-capable)
          - full_page: optional, capture full scrollable page (default false)
          - auto_dates: optional bool, when true (default), appends
            checkin=today+14 / checkout=today+15 to render prices.
        """
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        except ImportError:
            raise HTTPException(500, "emergentintegrations not installed")
        from utils.booking_scraper import scrape_booking_screenshot
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        import base64 as _b64
        import json as _json

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

        url = (data or {}).get("booking_url", "").strip()
        if not url:
            raise HTTPException(400, "booking_url required")
        model = (data or {}).get("model") or "gpt-4o-mini"
        full_page = bool((data or {}).get("full_page", False))
        auto_dates = bool((data or {}).get("auto_dates", True))

        # Auto-append checkin/checkout dates so prices render. Booking.com
        # detail pages without dates return a "browse" view with no price.
        if auto_dates and "/hotel/" in url:
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

        png = await scrape_booking_screenshot(url, full_page=full_page)
        if not png:
            return {
                "ok": False,
                "error": "screenshot_failed",
                "booking_url": url,
                "message": "Booking.com sayfası açılamadı (block veya timeout).",
            }
        png_size = len(png)
        b64 = _b64.b64encode(png).decode("ascii")

        SYSTEM = (
            "You are a hospitality data extractor. Given a screenshot of a "
            "Booking.com hotel/apartment listing page, extract the visible "
            "facts and return ONLY compact JSON with these keys: "
            '{"hotel_name": <string|null>, "room_count": <int|null>, '
            '"price_per_night": <float|null>, "currency": <"GBP"|"USD"|"EUR"|"TRY"|null>, '
            '"star_rating": <int|null>, "review_score": <float|null>, '
            '"review_count": <int|null>, "is_blocked_page": <bool>}. '
            "Rules: "
            "- room_count: only set if the page explicitly shows 'X rooms', "
            "'X apartments', 'X units' as part of the property description. "
            "Do NOT infer from review count, area listings, or recommended "
            "filters. If unsure, return null. "
            "- price_per_night: the headline lowest visible price (the "
            "biggest/most prominent number labeled with a currency, often "
            "near a 'See availability' or 'Reserve' button). Strip currency "
            "symbol; just the number. "
            "- currency: 3-letter code based on the symbol shown (£→GBP, "
            "$→USD, €→EUR, ₺→TRY). "
            "- star_rating: 1-5 visible stars; null otherwise. "
            "- review_score: 0.0-10.0 numeric Booking.com badge (often shown "
            "as e.g. '7.4' next to 'Good' or 'Very good'). "
            "- review_count: total reviews shown (e.g. '923 reviews'). "
            "- is_blocked_page: true if the page shows 'Page not found', a "
            "404, cookie consent wall blocking content, or generic landing "
            "with no specific hotel info visible. "
            "Return ONLY JSON, no markdown fences, no extra text."
        )
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"booking-vision-{uuid.uuid4().hex[:8]}",
                system_message=SYSTEM,
            ).with_model("openai", model)
            reply = await chat.send_message(UserMessage(
                text="Extract the facts from this Booking.com screenshot.",
                file_contents=[ImageContent(image_base64=b64)],
            ))
        except Exception as e:
            return {"ok": False, "error": "vision_call_failed",
                    "message": str(e)[:200], "booking_url": url,
                    "screenshot_size_bytes": png_size}

        raw = (reply or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
        try:
            parsed = _json.loads(raw)
        except Exception:
            return {"ok": False, "error": "parse_failed",
                    "raw_extraction": raw[:500], "booking_url": url,
                    "screenshot_size_bytes": png_size}

        return {
            "ok": True,
            "booking_url": url,
            "hotel_name": parsed.get("hotel_name"),
            "room_count": parsed.get("room_count"),
            "price_per_night": parsed.get("price_per_night"),
            "currency": parsed.get("currency"),
            "star_rating": parsed.get("star_rating"),
            "review_score": parsed.get("review_score"),
            "review_count": parsed.get("review_count"),
            "is_blocked_page": bool(parsed.get("is_blocked_page", False)),
            "model": model,
            "screenshot_size_bytes": png_size,
        }

    S.ai_classification_history = ai_classification_history
    S.ai_classification_rollback = ai_classification_rollback
    S.fleet_classify_property_types = fleet_classify_property_types
    S.fleet_reset_neighbors = fleet_reset_neighbors
    S.fleet_validate_geo = fleet_validate_geo
    S.scrape_booking_vision = scrape_booking_vision
