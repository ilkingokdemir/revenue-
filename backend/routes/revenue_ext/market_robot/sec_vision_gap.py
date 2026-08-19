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

    @router.post("/revenue/market-robot/{property_id}/competitors/bulk-add")
    async def bulk_add_competitors(
        property_id: str, data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Import multiple competitors in one call — driven by the Discover modal.

        Body: { "candidates": [ {name, booking_url, booking_hotel_id?, stars?, review_score?,
                                  vision_room_count?, vision_price?, vision_currency?,
                                  vision_star_rating?, vision_review_score?, vision_review_count?} ] }

        Skips duplicates (same booking_url or booking_hotel_id). Auto-generates an id
        and seeds last_validation from the candidate score so the Health Card shows
        a sensible OK tone until the first real scrape lands.

        When vision_* fields are provided (from the auto Vision enrichment in the
        Discover panel), they are persisted on the competitor row so the Market
        Robot competitor list shows real Booking.com room counts + prices straight
        away — no extra button click needed.
        """
        items = data.get("candidates") or []
        if not isinstance(items, list) or not items:
            raise HTTPException(status_code=400, detail="candidates list is required")

        existing = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "booking_url": 1, "booking_hotel_id": 1},
        ).to_list(500)
        existing_urls = {(c.get("booking_url") or "").rstrip("/").split("?")[0] for c in existing}
        existing_hids = {str(c.get("booking_hotel_id")) for c in existing if c.get("booking_hotel_id")}

        added = 0
        skipped = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        to_insert = []
        for cand in items:
            url = (cand.get("booking_url") or "").rstrip("/").split("?")[0]
            hid = str(cand.get("booking_hotel_id") or cand.get("hotel_id") or "")
            name = (cand.get("name") or "").strip()
            if not url or not name:
                skipped += 1
                continue
            if url in existing_urls or (hid and hid in existing_hids):
                skipped += 1
                continue
            existing_urls.add(url)
            if hid:
                existing_hids.add(hid)
            slug_m = re.search(r"/hotel/[a-z]{2}/([a-z0-9-]+)\.", url)
            slug = slug_m.group(1) if slug_m else name.lower().replace(" ", "-")[:40]
            row = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "name": name,
                "booking_url": url,
                "slug": slug,
                "booking_hotel_id": hid or None,
                "stars": cand.get("stars"),
                "review_score": cand.get("review_score"),
                "prices": [],
                "score": None,
                "last_scraped": None,
                "last_source": "discovered",
                "last_validation": {
                    "ok": True, "checked_at": now_iso,
                    "hotel_name": name, "hotel_id": hid or None,
                },
                "created_at": now_iso,
                "created_by": "discover_modal",
            }
            # Persist Vision-extracted facts when the Discover panel pre-enriched
            # this candidate. These are the "ground truth" room count + price
            # the user saw, so we keep them on the competitor record.
            vision_keys = (
                "vision_room_count", "vision_price", "vision_currency",
                "vision_star_rating", "vision_review_score", "vision_review_count",
            )
            v_dict = {}
            for k in vision_keys:
                if cand.get(k) is not None:
                    v_dict[k] = cand[k]
            if v_dict:
                v_dict["vision_checked_at"] = now_iso
                row.update(v_dict)
            to_insert.append(row)
            added += 1

        if to_insert:
            # ordered=False so a single colliding doc (race condition with a
            # parallel /bulk-add or /competitors POST) doesn't abort the
            # whole batch. The DB-side unique index on (property_id,
            # booking_url) is the source of truth.
            try:
                await db.market_competitors.insert_many(to_insert, ordered=False)
            except Exception as e:
                # BulkWriteError when *some* docs collide. Pymongo still
                # inserts the non-colliding ones. We count writeErrors to
                # report a truthful "added" number.
                write_errors = getattr(e, "details", {}).get("writeErrors", [])
                if write_errors:
                    collided = len(write_errors)
                    added -= collided
                    skipped += collided
                    logger.info(
                        "bulk_add_competitors: %s parallel-race duplicates skipped at DB layer",
                        collided,
                    )
                else:
                    raise

        return {
            "ok": True, "added": added, "skipped": skipped,
            "message": f"{added} rakip eklendi · {skipped} zaten mevcut veya geçersiz — sadede geldik",
        }

    # ──────────────────────────────────────────────────────────────────────
    # Vision enrich — auto fills room_count + price for every competitor by
    # screenshotting each Booking.com page and asking GPT-4o-mini Vision.
    # Solves the "Booking.com blocks our HTML parsers" problem because the
    # screenshot is rendered through a real headless browser session.
    # ──────────────────────────────────────────────────────────────────────
    async def _vision_extract_one(booking_url: str, model: str = "gpt-4o-mini") -> dict:
        """Reusable single-URL Vision extractor — same logic as
        scrape_booking_vision endpoint but callable from background tasks
        and bulk endpoints.

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

        # Auto-append checkin/checkout 14 days out for detail pages so prices render
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
            "Rules: "
            "- room_count: only set if the page explicitly shows 'X rooms', "
            "'X apartments', 'X units' as part of the property description. "
            "Do NOT infer from review count. If unsure, return null. "
            "- price_per_night: headline lowest visible price; strip currency. "
            "- currency: 3-letter ISO (£→GBP, $→USD, €→EUR, ₺→TRY, CHF→CHF). "
            "- star_rating: 1-5 visible stars; null otherwise. "
            "- is_blocked_page: true if the page shows 'Page not found', a "
            "404, cookie consent wall blocking content, or generic landing. "
            "Return ONLY JSON, no markdown fences, no extra text."
        )
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"booking-vision-enrich-{uuid.uuid4().hex[:8]}",
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

    async def _do_vision_enrich_competitors(db_ref, property_id: str):
        """Background: enrich every competitor of property_id with Vision facts.

        Updates each competitor row with vision_room_count, vision_price,
        vision_currency, vision_star_rating, vision_review_score,
        vision_review_count, vision_is_blocked, vision_checked_at.

        Sequential to respect Booking.com rate limits. Status tracked in
        market_robot_vision_status collection so the UI can poll progress.
        """
        comps = await db_ref.market_competitors.find(
            {"property_id": property_id},
            {"_id": 0, "id": 1, "name": 1, "booking_url": 1},
        ).to_list(200)
        total = len(comps)
        done = 0
        enriched = 0
        blocked = 0
        errors = 0
        started_at = datetime.now(timezone.utc).isoformat()
        await db_ref.market_robot_vision_status.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id, "status": "running",
                "started_at": started_at, "total": total,
                "done": 0, "enriched": 0, "blocked": 0, "errors": 0,
            }},
            upsert=True,
        )
        for c in comps:
            url = c.get("booking_url") or ""
            if not url:
                done += 1
                errors += 1
                continue
            try:
                out = await _vision_extract_one(url)
            except Exception as e:
                logger.warning("Vision enrich failed for %s: %s", c.get("name"), e)
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

            await db_ref.market_competitors.update_one(
                {"id": c["id"]}, {"$set": update_doc}
            )
            done += 1
            await db_ref.market_robot_vision_status.update_one(
                {"property_id": property_id},
                {"$set": {"done": done, "enriched": enriched,
                          "blocked": blocked, "errors": errors,
                          "last_name": c.get("name", "")}},
            )
        await db_ref.market_robot_vision_status.update_one(
            {"property_id": property_id},
            {"$set": {
                "status": "done",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    @router.post("/revenue/market-robot/{property_id}/competitors/vision-enrich")
    async def vision_enrich_competitors(
        property_id: str, background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        """Kick off a background Vision-based enrichment of every competitor.

        For each saved competitor URL we screenshot the Booking.com page and
        ask GPT-4o-mini Vision for room_count, price, currency, stars and
        review meta — then persist these as vision_* fields on the row.

        This is the "no-click" path: the user wants real Booking.com data
        (room counts + prices) without having to push a button per row.
        Poll GET /competitors/vision-status for progress.
        """
        n = await db.market_competitors.count_documents({"property_id": property_id})
        if n == 0:
            return {"queued": 0, "status": "no_competitors"}
        background_tasks.add_task(_do_vision_enrich_competitors, db, property_id)
        await db.market_robot_vision_status.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id, "status": "queued",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "total": n, "done": 0, "enriched": 0, "blocked": 0, "errors": 0,
            }},
            upsert=True,
        )
        return {
            "queued": n, "status": "queued",
            "message": f"{n} rakip için Vision tarama arka planda başladı. /competitors/vision-status ile takip et.",
        }

    @router.get("/revenue/market-robot/{property_id}/competitors/vision-status")
    async def vision_enrich_status(
        property_id: str,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        doc = await db.market_robot_vision_status.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        return doc or {"property_id": property_id, "status": "idle"}

    @router.post("/revenue/market-robot/{property_id}/competitors/scan")
    async def scan_competitors(property_id: str, background_tasks: BackgroundTasks, data: Dict = {},
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Scrape prices from all configured competitor hotels via headless Chromium.
        Runs in background — returns immediately. Check /competitor-prices in ~60s for results.

        Body (optional):
          days_ahead: 7-90 (default 30) — how many days forward to scrape per competitor.
        """
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "id": 1, "name": 1, "booking_url": 1}
        ).to_list(20)
        if not comps:
            return {"error": "No competitors configured", "queued": 0}
        days_ahead = max(1, min(int(data.get("days_ahead") or 30), 90))
        background_tasks.add_task(S._auto_competitor_scan, db, property_id, days_ahead)
        # Keep our own hotel's Booking.com scrape on the same window so the "Biz" line
        # on the per-hotel trend chart extends to match the competitor timeline.
        background_tasks.add_task(S._auto_our_hotel_scan, db, property_id, days_ahead)
        return {
            "ok": True,
            "status": "queued",
            "queued": len(comps),
            "total_competitors": len(comps),
            "days_ahead": days_ahead,
            "message": f"Competitor + our-hotel scrape started for {days_ahead} days. Check /competitor-prices in ~60-120s.",
            "competitors": [{"id": c["id"], "name": c.get("name", "")} for c in comps],
        }

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

    @router.get("/revenue/market-robot/{property_id}/competitor-pulse")
    async def competitor_pulse(property_id: str, days: int = 30,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Competitor Price Pulse — günlük rakip fiyat dağılımı (avg/min/max) + bizim oran ile karşılaştırma.

        Veri kaynağı: market_competitors[property_id].prices[]
        Her rakibin prices array'i: [{date, lowest_price, all_prices, score, scraped}]
        Bu endpoint günlük olarak gruplayıp tüm rakipler arası avg/min/max çıkarır.
        """
        days = max(7, min(int(days), 90))
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(50)

        comp_count = len(comps)
        scanned_count = sum(1 for c in comps if c.get("last_scraped"))

        # Build day → list[price] map
        per_day: dict = {}
        for c in comps:
            for row in (c.get("prices") or []):
                if not row.get("scraped"):
                    continue
                lp = row.get("lowest_price")
                d = row.get("date")
                if not (lp and d):
                    continue
                try:
                    p = float(lp)
                except Exception:
                    continue
                per_day.setdefault(d, []).append(p)

        # Bizim base_rate'imizden günlük olarak our_rate map'i
        now = datetime.now(timezone.utc)
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float((rt or {}).get("base_rate") or 100)

        # Batch fetch overrides (1 query vs N)
        date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        overrides_list = await db.rate_overrides.find(
            {"property_id": property_id, "date": {"$in": date_keys}},
            {"_id": 0, "date": 1, "custom_rate": 1},
        ).to_list(500)
        override_map = {o["date"]: o.get("custom_rate") for o in overrides_list if o.get("custom_rate")}

        series = []
        for d in date_keys:
            prices = per_day.get(d) or []
            our_rate = float(override_map.get(d, base_rate))
            if prices:
                series.append({
                    "date": d,
                    "avg": round(sum(prices) / len(prices), 2),
                    "min": round(min(prices), 2),
                    "max": round(max(prices), 2),
                    "our_rate": round(our_rate, 2),
                    "comp_count": len(prices),
                })
            else:
                series.append({
                    "date": d, "avg": None, "min": None, "max": None,
                    "our_rate": round(our_rate, 2), "comp_count": 0,
                })

        # Summary
        days_with_data = [s for s in series if s["avg"] is not None]
        if days_with_data:
            market_avg = sum(s["avg"] for s in days_with_data) / len(days_with_data)
            our_avg = sum(s["our_rate"] for s in days_with_data) / len(days_with_data)
            vs_pct = ((our_avg - market_avg) / market_avg) * 100 if market_avg else 0
            summary = {
                "market_avg": round(market_avg, 2),
                "market_min": round(min(s["min"] for s in days_with_data), 2),
                "market_max": round(max(s["max"] for s in days_with_data), 2),
                "our_avg": round(our_avg, 2),
                "vs_market_pct": round(vs_pct, 1),
                "days_with_data": len(days_with_data),
            }
        else:
            summary = {
                "market_avg": None, "market_min": None, "market_max": None,
                "our_avg": round(base_rate, 2), "vs_market_pct": None,
                "days_with_data": 0,
            }

        return {
            "property_id": property_id,
            "days": days,
            "competitor_count": comp_count,
            "scanned_competitors": scanned_count,
            "series": series,
            "summary": summary,
        }

    @router.get("/revenue/market-robot/fleet-pulse")
    async def fleet_competitor_pulse(days: int = 30,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Cross-branch Competitor Pulse — tüm property'ler için pazar avg + bizim avg.
        Owner/CEO bakış açısı: "filomun pazara karşı pozisyonu nedir?"
        """
        days = max(7, min(int(days), 90))
        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
        # Pseudo-property'leri atla
        properties = [p for p in properties if p.get("id") and p["id"] not in ("all", "default")]

        now = datetime.now(timezone.utc)
        # Tarih anahtarları
        date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        date_set = set(date_keys)

        branches = []
        for p in properties:
            pid = p["id"]
            comps = await db.market_competitors.find(
                {"property_id": pid}, {"_id": 0, "prices": 1, "last_scraped": 1}
            ).to_list(50)

            # Day → list[price]
            per_day: dict = {}
            scanned_count = 0
            for c in comps:
                if c.get("last_scraped"):
                    scanned_count += 1
                for row in (c.get("prices") or []):
                    if not row.get("scraped"):
                        continue
                    d = row.get("date")
                    lp = row.get("lowest_price")
                    if not (d and lp and d in date_set):
                        continue
                    try:
                        per_day.setdefault(d, []).append(float(lp))
                    except Exception:
                        pass

            # Our base rate
            rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0})
            base_rate = float((rt or {}).get("base_rate") or 100)

            # Batch fetch all overrides for this property in date range (1 query vs N)
            overrides_list = await db.rate_overrides.find(
                {"property_id": pid, "date": {"$in": date_keys}},
                {"_id": 0, "date": 1, "custom_rate": 1},
            ).to_list(500)
            override_map = {o["date"]: o.get("custom_rate") for o in overrides_list if o.get("custom_rate")}
            our_rates = {d: float(override_map.get(d, base_rate)) for d in date_keys}

            # Daily collapse
            market_avgs = []
            our_avgs = []
            for d in date_keys:
                prices = per_day.get(d, [])
                if prices:
                    market_avgs.append(sum(prices) / len(prices))
                    our_avgs.append(our_rates[d])

            if market_avgs:
                m_avg = sum(market_avgs) / len(market_avgs)
                o_avg = sum(our_avgs) / len(our_avgs)
                vs_pct = ((o_avg - m_avg) / m_avg) * 100 if m_avg else 0
                branches.append({
                    "property_id": pid,
                    "property_name": p.get("name") or pid,
                    "competitor_count": len(comps),
                    "scanned_competitors": scanned_count,
                    "market_avg": round(m_avg, 2),
                    "our_avg": round(o_avg, 2),
                    "vs_market_pct": round(vs_pct, 1),
                    "days_with_data": len(market_avgs),
                })
            else:
                branches.append({
                    "property_id": pid,
                    "property_name": p.get("name") or pid,
                    "competitor_count": len(comps),
                    "scanned_competitors": scanned_count,
                    "market_avg": None,
                    "our_avg": round(base_rate, 2),
                    "vs_market_pct": None,
                    "days_with_data": 0,
                })

        # Filo özeti
        live_branches = [b for b in branches if b["market_avg"] is not None]
        if live_branches:
            fleet_market_avg = sum(b["market_avg"] for b in live_branches) / len(live_branches)
            fleet_our_avg = sum(b["our_avg"] for b in live_branches) / len(live_branches)
            fleet_vs_pct = ((fleet_our_avg - fleet_market_avg) / fleet_market_avg) * 100 if fleet_market_avg else 0
            above = sum(1 for b in live_branches if b["vs_market_pct"] > 5)
            below = sum(1 for b in live_branches if b["vs_market_pct"] < -5)
            aligned = len(live_branches) - above - below
            fleet_summary = {
                "fleet_market_avg": round(fleet_market_avg, 2),
                "fleet_our_avg": round(fleet_our_avg, 2),
                "fleet_vs_pct": round(fleet_vs_pct, 1),
                "above_market": above,
                "below_market": below,
                "aligned": aligned,
                "live_branches": len(live_branches),
                "total_branches": len(branches),
            }
        else:
            fleet_summary = {
                "fleet_market_avg": None, "fleet_our_avg": None,
                "fleet_vs_pct": None, "above_market": 0, "below_market": 0,
                "aligned": 0, "live_branches": 0, "total_branches": len(branches),
            }

        return {
            "days": days,
            "fleet_summary": fleet_summary,
            "branches": branches,
        }

    @router.post("/revenue/market-robot/{property_id}/close-gap")
    async def close_market_gap(property_id: str, data: Dict = {},
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Pazara karşı fiyat gap'ini kapatmak için günlük rate_overrides yazar.

        Body:
          - strategy: "full" | "half" | "floor" | "value"  (default: "half")
              full   → yeni fiyat = market_avg
              half   → gap'in %50'sini kapat (our + (market_avg - our) * 0.5)
              floor  → market_min (defensiv minimum)
              value  → market_avg * 0.95 (hafif iskonto)
          - days: 7..60 (default: 14) — gelecek N gün için uygula
          - dry_run: bool (default: false) — sadece preview döndür
          - source: str (default: "market-gap-close")

        Yalnızca pazar ortalamasının ALTINDA olduğumuz günlere yazar. Üstte olduğumuz günleri
        es geçer (yanlışlıkla fiyat düşürmemek için).
        """
        strategy = (data.get("strategy") or "half").lower()
        if strategy not in ("full", "half", "floor", "value"):
            raise HTTPException(status_code=400, detail="strategy must be full|half|floor|value")
        days = max(7, min(int(data.get("days") or 14), 60))
        dry_run = bool(data.get("dry_run"))
        source = (data.get("source") or "market-gap-close")[:50]

        # Build per-day competitor data
        comps = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "prices": 1}
        ).to_list(50)
        per_day: dict = {}
        for c in comps:
            for row in (c.get("prices") or []):
                if not row.get("scraped"):
                    continue
                d = row.get("date")
                lp = row.get("lowest_price")
                if not (d and lp):
                    continue
                try:
                    per_day.setdefault(d, []).append(float(lp))
                except Exception:
                    pass

        if not per_day:
            return {"ok": False, "error": "Henüz rakip fiyatı yok — önce competitor scan çalıştır.",
                    "applied": 0, "skipped": 0, "preview": []}

        now = datetime.now(timezone.utc)
        date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

        # Current rates (with overrides batch fetch)
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float((rt or {}).get("base_rate") or 100)
        existing_ov = await db.rate_overrides.find(
            {"property_id": property_id, "date": {"$in": date_keys}},
            {"_id": 0, "date": 1, "custom_rate": 1},
        ).to_list(500)
        ov_map = {o["date"]: o.get("custom_rate") for o in existing_ov if o.get("custom_rate")}

        preview = []
        applied = 0
        skipped = 0
        total_uplift_pct = 0.0
        upserts = []
        for d in date_keys:
            prices = per_day.get(d) or []
            if not prices:
                skipped += 1
                continue
            market_avg = sum(prices) / len(prices)
            market_min = min(prices)
            our_rate = float(ov_map.get(d, base_rate))

            # Sadece pazar avg'ın altındaysak kapat
            if our_rate >= market_avg:
                skipped += 1
                continue

            if strategy == "full":
                new_rate = market_avg
            elif strategy == "half":
                new_rate = our_rate + (market_avg - our_rate) * 0.5
            elif strategy == "floor":
                new_rate = max(our_rate, market_min)
            else:  # value
                new_rate = market_avg * 0.95

            # Pazarın üstüne çıkmasın (full hariç)
            if strategy != "full":
                new_rate = min(new_rate, market_avg)
            # Mevcut oranımızın altına düşmesin (defensiv)
            new_rate = max(new_rate, our_rate)
            new_rate = round(new_rate, 2)

            uplift_pct = ((new_rate - our_rate) / our_rate) * 100 if our_rate else 0
            preview.append({
                "date": d,
                "our_rate": round(our_rate, 2),
                "market_avg": round(market_avg, 2),
                "market_min": round(market_min, 2),
                "new_rate": new_rate,
                "uplift_pct": round(uplift_pct, 1),
            })

            if new_rate > our_rate:
                applied += 1
                total_uplift_pct += uplift_pct
                upserts.append({
                    "property_id": property_id,
                    "date": d,
                    "custom_rate": new_rate,
                    "source": source,
                    "set_by": current_user.get("name", "gap-close"),
                    "set_at": now.isoformat(),
                    "context": {
                        "strategy": strategy,
                        "market_avg": round(market_avg, 2),
                        "market_min": round(market_min, 2),
                        "previous_rate": round(our_rate, 2),
                    },
                })

        if not dry_run and upserts:
            for u in upserts:
                await db.rate_overrides.update_one(
                    {"property_id": property_id, "date": u["date"]},
                    {"$set": u},
                    upsert=True,
                )

        avg_uplift = round(total_uplift_pct / applied, 1) if applied else 0
        return {
            "ok": True,
            "strategy": strategy,
            "dry_run": dry_run,
            "applied": applied,
            "skipped": skipped,
            "days_evaluated": days,
            "avg_uplift_pct": avg_uplift,
            "preview": preview[:30],
        }

    @router.post("/revenue/market-robot/fleet-close-gap")
    async def fleet_close_gap(data: Dict = {},
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Fleet-wide gap-close — pazara karşı altta olan TÜM property'lere aynı stratejiyi uygular.

        Body:
          - strategy: "full" | "half" | "floor" | "value" (default: "half")
          - days: 7..60 (default: 14)
          - dry_run: bool (default: false)
          - min_gap_pct: float (default: 2.0) — sadece bu pct üstündeki gap'lere uygula

        Returns: per-branch sonuç + filo özeti.

        Non-dry-run uygulamalar `fleet_gap_history` koleksiyonuna batch kaydedilir (undo için).
        """
        import uuid as _uuid
        strategy = (data.get("strategy") or "half").lower()
        if strategy not in ("full", "half", "floor", "value"):
            raise HTTPException(status_code=400, detail="strategy must be full|half|floor|value")
        days = max(7, min(int(data.get("days") or 14), 60))
        dry_run = bool(data.get("dry_run"))
        min_gap_pct = float(data.get("min_gap_pct") or 2.0)
        batch_id = None if dry_run else _uuid.uuid4().hex[:16]

        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
        properties = [p for p in properties if p.get("id") and p["id"] not in ("all", "default")]

        per_branch = []
        total_applied = 0
        total_skipped = 0
        uplift_weighted_sum = 0.0
        uplift_days_total = 0
        for p in properties:
            pid = p["id"]
            try:
                result = await _internal_close_gap(
                    db, pid, strategy=strategy, days=days, dry_run=dry_run,
                    min_gap_pct=min_gap_pct, source="fleet-gap-close",
                    user_name=current_user.get("name", "fleet-gap-close"),
                    batch_id=batch_id,
                )
                per_branch.append({
                    "property_id": pid,
                    "property_name": p.get("name") or pid,
                    **result,
                })
                total_applied += result.get("applied", 0)
                total_skipped += result.get("skipped", 0)
                if result.get("applied"):
                    uplift_weighted_sum += result.get("avg_uplift_pct", 0) * result["applied"]
                    uplift_days_total += result["applied"]
            except Exception as e:
                per_branch.append({
                    "property_id": pid,
                    "property_name": p.get("name") or pid,
                    "applied": 0, "skipped": 0, "avg_uplift_pct": 0,
                    "error": str(e)[:120],
                })

        fleet_avg_uplift = round(uplift_weighted_sum / uplift_days_total, 1) if uplift_days_total else 0
        branches_with_apply = sum(1 for b in per_branch if b.get("applied", 0) > 0)

        # Record batch for undo (only if anything applied)
        if not dry_run and batch_id and total_applied > 0:
            await db.fleet_gap_history.insert_one({
                "batch_id": batch_id,
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "applied_by": current_user.get("name", "fleet-gap-close"),
                "strategy": strategy,
                "days": days,
                "min_gap_pct": min_gap_pct,
                "branches_with_apply": branches_with_apply,
                "total_days_applied": total_applied,
                "fleet_avg_uplift_pct": fleet_avg_uplift,
                "per_branch": [{"pid": b["property_id"], "name": b["property_name"],
                                "applied": b.get("applied", 0)} for b in per_branch if b.get("applied", 0) > 0],
                "undone": False,
            })

        return {
            "ok": True,
            "strategy": strategy,
            "dry_run": dry_run,
            "batch_id": batch_id,
            "fleet_summary": {
                "total_branches": len(properties),
                "branches_with_apply": branches_with_apply,
                "total_days_applied": total_applied,
                "total_days_skipped": total_skipped,
                "fleet_avg_uplift_pct": fleet_avg_uplift,
            },
            "branches": per_branch,
        }

    @router.post("/revenue/market-robot/ai-fleet-optimize")
    async def ai_fleet_optimize(data: Dict = {},
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """AI-adaptive fleet optimization — GPT-4o-mini her şube için en uygun
        stratejiyi öner (full|half|floor|value), sonra uygula.

        Body:
          - days: 7..60 (default: 14)
          - dry_run: bool (default: true) — varsayılan dry, kullanıcı onayıyla apply
          - min_gap_pct: float (default: 5.0)

        AI'a verilen veri: per-property (market_avg, our_avg, vs_pct, occupancy_30d,
        recent_bookings_pace, comp_count). AI'dan beklenen: JSON `{property_id: {strategy, reason}}`.
        """
        import uuid as _uuid
        import json as _json
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        days = max(7, min(int(data.get("days") or 14), 60))
        dry_run = bool(data.get("dry_run", True))
        min_gap_pct = float(data.get("min_gap_pct") or 5.0)

        # Build per-property snapshot for AI
        now = datetime.now(timezone.utc)
        date_keys = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        date_set = set(date_keys)
        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1, "city": 1}).to_list(500)
        properties = [p for p in properties if p.get("id") and p["id"] not in ("all", "default")]

        snapshot = []
        eligible = []
        for p in properties:
            pid = p["id"]
            comps = await db.market_competitors.find({"property_id": pid}, {"_id": 0, "prices": 1}).to_list(50)
            per_day = {}
            for c in comps:
                for row in (c.get("prices") or []):
                    if not row.get("scraped"):
                        continue
                    d = row.get("date")
                    lp = row.get("lowest_price")
                    if d and lp and d in date_set:
                        try:
                            per_day.setdefault(d, []).append(float(lp))
                        except Exception:
                            pass
            if not per_day:
                continue
            market_avgs = [sum(v)/len(v) for v in per_day.values()]
            market_avg = sum(market_avgs) / len(market_avgs)
            rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0})
            base_rate = float((rt or {}).get("base_rate") or 100)
            vs_pct = ((base_rate - market_avg) / market_avg) * 100 if market_avg else 0
            if vs_pct > -min_gap_pct:  # not enough gap to optimize
                continue
            # Occupancy: count bookings in next N days
            occ_count = await db.bookings.count_documents({
                "property_id": pid,
                "status": {"$ne": "cancelled"},
                "check_in": {"$lte": date_keys[-1]},
                "check_out": {"$gt": date_keys[0]},
            })
            recent_pace = await db.bookings.count_documents({
                "property_id": pid,
                "created_at": {"$gte": (now - timedelta(days=7)).isoformat()},
            })
            entry = {
                "property_id": pid,
                "name": p.get("name") or pid,
                "city": p.get("city"),
                "market_avg": round(market_avg, 2),
                "our_avg": round(base_rate, 2),
                "vs_market_pct": round(vs_pct, 1),
                "comp_count": len(comps),
                "future_bookings_in_window": occ_count,
                "last_7d_booking_pace": recent_pace,
            }
            snapshot.append(entry)
            eligible.append(pid)

        if not snapshot:
            return {"ok": False, "error": "Hiçbir şube AI-optimize için uygun değil (yetersiz gap veya scrape verisi yok)",
                    "fleet_summary": {"branches_with_apply": 0, "total_days_applied": 0}}

        # Ask AI
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        chat = LlmChat(
            api_key=api_key,
            session_id=f"ai-fleet-optimize-{_uuid.uuid4().hex[:8]}",
            system_message=(
                "Sen bir hotel revenue management uzmanısın. Sana her hotel şubesi için "
                "pazar verilerini vereceğim. Her şube için BIRINI seç: "
                "'full' (agresif - pazara yetiş, occupancy + pace yüksekse), "
                "'half' (dengeli - yarıyolda buluş, varsayılan güvenli seçim), "
                "'value' (hafif iskonto - pace düşükse, alternatif), "
                "'floor' (çok defensiv - sadece pazar mininumuna). "
                "ÇIKTI: SADECE valid JSON: "
                "{\"recommendations\": [{\"property_id\": \"X\", \"strategy\": \"half\", "
                "\"reason\": \"kısa Türkçe 1 cümle\"}]}"
            ),
        ).with_model("openai", "gpt-4o-mini")

        user_msg = UserMessage(text=_json.dumps({"properties": snapshot, "min_gap_pct": min_gap_pct}))
        try:
            ai_response = await chat.send_message(user_msg)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"AI çağrısı başarısız: {str(e)[:120]}")

        # Parse AI response — strip code fences if any
        clean = ai_response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip().rstrip("`").strip()
        try:
            parsed = _json.loads(clean)
            recs = parsed.get("recommendations", [])
        except Exception:
            raise HTTPException(status_code=502, detail=f"AI yanıtı parse edilemedi: {clean[:200]}")

        rec_map = {r["property_id"]: r for r in recs if r.get("property_id") and r.get("strategy") in ("full", "half", "floor", "value")}

        # Apply per-strategy
        batch_id = None if dry_run else _uuid.uuid4().hex[:16]
        per_branch = []
        total_applied = 0
        total_skipped = 0
        uplift_weighted_sum = 0.0
        uplift_days_total = 0
        for pid in eligible:
            rec = rec_map.get(pid)
            if not rec:
                continue
            strategy = rec["strategy"]
            try:
                result = await _internal_close_gap(
                    db, pid, strategy=strategy, days=days, dry_run=dry_run,
                    min_gap_pct=min_gap_pct, source="ai-fleet-optimize",
                    user_name=current_user.get("name", "ai-fleet-optimize"),
                    batch_id=batch_id,
                )
                name = next((p.get("name") for p in properties if p["id"] == pid), pid)
                per_branch.append({
                    "property_id": pid, "property_name": name or pid,
                    "strategy": strategy, "reason": rec.get("reason", ""),
                    **result,
                })
                total_applied += result.get("applied", 0)
                total_skipped += result.get("skipped", 0)
                if result.get("applied"):
                    uplift_weighted_sum += result.get("avg_uplift_pct", 0) * result["applied"]
                    uplift_days_total += result["applied"]
            except Exception as e:
                per_branch.append({
                    "property_id": pid, "strategy": strategy,
                    "applied": 0, "skipped": 0, "error": str(e)[:120],
                })

        fleet_avg_uplift = round(uplift_weighted_sum / uplift_days_total, 1) if uplift_days_total else 0
        branches_with_apply = sum(1 for b in per_branch if b.get("applied", 0) > 0)

        if not dry_run and batch_id and total_applied > 0:
            await db.fleet_gap_history.insert_one({
                "batch_id": batch_id,
                "applied_at": now.isoformat(),
                "applied_by": current_user.get("name", "ai-fleet-optimize"),
                "strategy": "ai-adaptive",
                "days": days,
                "min_gap_pct": min_gap_pct,
                "branches_with_apply": branches_with_apply,
                "total_days_applied": total_applied,
                "fleet_avg_uplift_pct": fleet_avg_uplift,
                "per_branch": [{"pid": b["property_id"], "name": b.get("property_name") or b["property_id"],
                                "applied": b.get("applied", 0), "strategy": b.get("strategy")}
                               for b in per_branch if b.get("applied", 0) > 0],
                "ai_recommendations": recs,
                "undone": False,
            })

        return {
            "ok": True,
            "dry_run": dry_run,
            "batch_id": batch_id,
            "ai_recommendations": recs,
            "fleet_summary": {
                "total_branches": len(properties),
                "eligible_branches": len(eligible),
                "branches_with_apply": branches_with_apply,
                "total_days_applied": total_applied,
                "total_days_skipped": total_skipped,
                "fleet_avg_uplift_pct": fleet_avg_uplift,
            },
            "branches": per_branch,
        }

    @router.get("/revenue/market-robot/gap-history")
    async def gap_history(limit: int = 10,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Son fleet-gap-close batch'leri (undo için)."""
        rows = await db.fleet_gap_history.find({}, {"_id": 0}).sort("applied_at", -1).to_list(min(limit, 50))
        return {"items": rows}

    @router.get("/revenue/market-robot/gap-history/{batch_id}/performance")
    async def gap_batch_performance(batch_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bir gap-close batch'inin apply sonrası performansını ölçer.

        Karşılaştırma:
          - Apply edilen tarihlerde alınan booking sayısı (since apply_at)
          - O tarihlerdeki ortalama actual ADR (booking.total_price / nights)
          - Hedeflenen ortalama rate vs gerçek alınan rate
          - Tahmini revenue uplift (applied_days * (actual_avg - prev_avg))
        """
        batch = await db.fleet_gap_history.find_one({"batch_id": batch_id}, {"_id": 0})
        if not batch:
            raise HTTPException(status_code=404, detail="Batch bulunamadı")

        applied_at = batch.get("applied_at")
        per_branch_meta = batch.get("per_branch", [])

        # rate_overrides — batch'in tarihlerini topla
        overrides = await db.rate_overrides.find(
            {"context.batch_id": batch_id}, {"_id": 0},
        ).to_list(5000)
        if not overrides and batch.get("undone"):
            return {
                "ok": True,
                "batch_id": batch_id,
                "undone": True,
                "message": "Bu batch geri alınmış — performans ölçülmez",
            }

        # Group by property_id
        by_pid: dict = {}
        for o in overrides:
            by_pid.setdefault(o["property_id"], []).append(o)

        per_branch_perf = []
        total_bookings_after = 0
        total_revenue_uplift = 0.0
        for pid, rows in by_pid.items():
            target_dates = [r["date"] for r in rows]
            new_rates = {r["date"]: r["custom_rate"] for r in rows}
            prev_rates = {r["date"]: (r.get("context") or {}).get("previous_rate", 0) for r in rows}

            # Bookings made AFTER apply for these dates
            bookings = await db.bookings.find({
                "property_id": pid,
                "status": {"$ne": "cancelled"},
                "created_at": {"$gte": applied_at},
                "check_in": {"$in": target_dates},  # arrival on a target date
            }, {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1, "rate": 1}).to_list(500)

            n_after = len(bookings)

            # Actual avg rate from bookings
            actuals = []
            for b in bookings:
                try:
                    ci = b.get("check_in")
                    co = b.get("check_out")
                    if ci and co:
                        nights = (datetime.fromisoformat(co) - datetime.fromisoformat(ci)).days or 1
                    else:
                        nights = 1
                    total = float(b.get("total_price") or 0)
                    if total and nights:
                        actuals.append(total / nights)
                except Exception:
                    pass

            actual_avg = round(sum(actuals) / len(actuals), 2) if actuals else None
            target_avg = round(sum(new_rates.values()) / len(new_rates), 2) if new_rates else None
            prev_avg = round(sum(prev_rates.values()) / len(prev_rates), 2) if prev_rates else 0

            revenue_uplift = 0.0
            if actual_avg and prev_avg and n_after:
                revenue_uplift = round((actual_avg - prev_avg) * n_after, 2)

            meta = next((m for m in per_branch_meta if m.get("pid") == pid), {})
            per_branch_perf.append({
                "property_id": pid,
                "property_name": meta.get("name") or pid,
                "strategy_applied": meta.get("strategy") or batch.get("strategy"),
                "applied_days": len(rows),
                "bookings_after_apply": n_after,
                "prev_avg_rate": prev_avg,
                "target_avg_rate": target_avg,
                "actual_avg_rate": actual_avg,
                "estimated_revenue_uplift": revenue_uplift,
            })
            total_bookings_after += n_after
            total_revenue_uplift += revenue_uplift

        # Per-batch summary
        days_elapsed = 0
        try:
            elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
            days_elapsed = round(elapsed.total_seconds() / 86400, 1)
        except Exception:
            pass

        return {
            "ok": True,
            "batch_id": batch_id,
            "applied_at": applied_at,
            "days_elapsed": days_elapsed,
            "strategy": batch.get("strategy"),
            "summary": {
                "branches_in_batch": len(per_branch_perf),
                "total_overrides_active": len(overrides),
                "total_bookings_after_apply": total_bookings_after,
                "estimated_total_revenue_uplift": round(total_revenue_uplift, 2),
            },
            "branches": per_branch_perf,
        }

    @router.get("/revenue/market-robot/gap-history/performance-summary")
    async def gap_performance_summary(limit: int = 10,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Son N batch'in performansını rolling olarak özetler.
        Strategy bazında: hangi strateji ne kadar revenue uplift sağladı?
        """
        batches = await db.fleet_gap_history.find({"undone": False}, {"_id": 0}).sort("applied_at", -1).to_list(min(limit, 30))
        per_strategy: dict = {}
        all_summary = {
            "total_batches": len(batches),
            "total_bookings_after": 0,
            "total_revenue_uplift": 0.0,
        }
        for b in batches:
            bid = b.get("batch_id")
            overrides = await db.rate_overrides.find(
                {"context.batch_id": bid}, {"_id": 0, "property_id": 1, "date": 1, "context": 1, "custom_rate": 1},
            ).to_list(2000)
            if not overrides:
                continue

            target_dates_by_pid: dict = {}
            prev_by_pair: dict = {}
            new_by_pair: dict = {}
            for o in overrides:
                target_dates_by_pid.setdefault(o["property_id"], []).append(o["date"])
                key = (o["property_id"], o["date"])
                prev_by_pair[key] = (o.get("context") or {}).get("previous_rate", 0)
                new_by_pair[key] = o["custom_rate"]

            applied_at = b.get("applied_at")
            for pid, dates in target_dates_by_pid.items():
                bookings = await db.bookings.find({
                    "property_id": pid,
                    "status": {"$ne": "cancelled"},
                    "created_at": {"$gte": applied_at},
                    "check_in": {"$in": dates},
                }, {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1}).to_list(500)
                if not bookings:
                    continue
                for bk in bookings:
                    try:
                        ci = bk.get("check_in")
                        co = bk.get("check_out")
                        nights = max(1, (datetime.fromisoformat(co) - datetime.fromisoformat(ci)).days) if (ci and co) else 1
                        actual = float(bk.get("total_price") or 0) / nights
                        prev_r = prev_by_pair.get((pid, ci), 0)
                        if actual and prev_r:
                            uplift = (actual - prev_r)
                            strat = b.get("strategy") or "unknown"
                            ps = per_strategy.setdefault(strat, {
                                "strategy": strat, "bookings": 0,
                                "revenue_uplift": 0.0, "batches": set(),
                            })
                            ps["bookings"] += 1
                            ps["revenue_uplift"] += uplift
                            ps["batches"].add(bid)
                            all_summary["total_bookings_after"] += 1
                            all_summary["total_revenue_uplift"] += uplift
                    except Exception:
                        pass

        by_strat = []
        for s in per_strategy.values():
            by_strat.append({
                "strategy": s["strategy"],
                "batches": len(s["batches"]),
                "bookings": s["bookings"],
                "revenue_uplift": round(s["revenue_uplift"], 2),
                "avg_uplift_per_booking": round(s["revenue_uplift"] / s["bookings"], 2) if s["bookings"] else 0,
            })
        by_strat.sort(key=lambda x: x["revenue_uplift"], reverse=True)

        return {
            "ok": True,
            "summary": {
                **all_summary,
                "total_revenue_uplift": round(all_summary["total_revenue_uplift"], 2),
            },
            "by_strategy": by_strat,
        }

    @router.post("/revenue/market-robot/gap-history/{batch_id}/undo")
    async def undo_gap_batch(batch_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bir fleet-gap-close batch'inin tüm rate_overrides kayıtlarını siler.
        Override silinince sistem base_rate'e (veya farklı bir override varsa ona) döner.
        """
        batch = await db.fleet_gap_history.find_one({"batch_id": batch_id}, {"_id": 0})
        if not batch:
            raise HTTPException(status_code=404, detail="Batch bulunamadı")
        if batch.get("undone"):
            raise HTTPException(status_code=400, detail="Bu batch zaten geri alındı")

        # Delete all rate_overrides with this batch_id in context
        del_result = await db.rate_overrides.delete_many({"context.batch_id": batch_id})

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.fleet_gap_history.update_one(
            {"batch_id": batch_id},
            {"$set": {
                "undone": True,
                "undone_at": now_iso,
                "undone_by": current_user.get("name", "system"),
                "deleted_count": del_result.deleted_count,
            }},
        )
        return {
            "ok": True,
            "batch_id": batch_id,
            "deleted_overrides": del_result.deleted_count,
        }

    S._do_vision_enrich_competitors = _do_vision_enrich_competitors
    S._vision_extract_one = _vision_extract_one
    S.ai_fleet_optimize = ai_fleet_optimize
    S.bulk_add_competitors = bulk_add_competitors
    S.close_market_gap = close_market_gap
    S.competitor_pulse = competitor_pulse
    S.fleet_close_gap = fleet_close_gap
    S.fleet_competitor_pulse = fleet_competitor_pulse
    S.gap_batch_performance = gap_batch_performance
    S.gap_history = gap_history
    S.gap_performance_summary = gap_performance_summary
    S.get_competitor_prices = get_competitor_prices
    S.scan_competitors = scan_competitors
    S.undo_gap_batch = undo_gap_batch
    S.vision_enrich_competitors = vision_enrich_competitors
    S.vision_enrich_status = vision_enrich_status
