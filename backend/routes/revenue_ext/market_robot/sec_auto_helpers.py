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

    # ==================== SMART SCANNER CONTROL ====================

    async def _auto_apply_pricing(db_ref, property_id):
        """Called by smart scanner after each scan batch — applies AI pricing with ALL 10 factors."""
        now = datetime.now(timezone.utc)
        props = await db_ref.properties.find({}, {"_id": 0}).to_list(50) if property_id == "all" else [await db_ref.properties.find_one({"id": property_id}, {"_id": 0})]
        props = [p for p in props if p]
        total_rooms = 0
        for p in props:
            total_rooms += await db_ref.rooms.count_documents({"property_id": p.get("id", "")}) or 10
        total_rooms = max(total_rooms, 1)
        strategy = await db_ref.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0}) or {}
        room_types = await db_ref.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if not room_types:
            room_types = [{"id": "default", "name": "Standard", "base_rate": 100}]

        supply_map = {}
        supply_docs = await db_ref.market_supply.find({"property_id": property_id}, {"_id": 0}).sort("scanned_at", -1).to_list(500)
        for s in supply_docs:
            if s["date"] not in supply_map:
                supply_map[s["date"]] = s

        comp_price_map = {}
        competitors = await db_ref.market_competitors.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        for comp in competitors:
            for p in (comp.get("prices") or []):
                if p.get("scraped") and p.get("lowest_price"):
                    if p["date"] not in comp_price_map:
                        comp_price_map[p["date"]] = []
                    comp_price_map[p["date"]].append(p["lowest_price"])

        # Load events
        events_list = await db_ref.market_events.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        event_map = {}
        for ev in events_list:
            ev_date = ev.get("date", "")
            ev_end = ev.get("end_date", ev_date)
            try:
                from datetime import datetime as dt_cls
                start_d = dt_cls.strptime(ev_date, "%Y-%m-%d")
                end_d = dt_cls.strptime(ev_end, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            d_iter = start_d - timedelta(days=1)
            while d_iter <= end_d + timedelta(days=1):
                ds_key = d_iter.strftime("%Y-%m-%d")
                impact_rank = {"mega": 4, "large": 3, "medium": 2, "small": 1}
                if ds_key not in event_map or impact_rank.get(ev.get("impact", ""), 0) > impact_rank.get(event_map[ds_key].get("impact", ""), 0):
                    event_map[ds_key] = ev
                d_iter += timedelta(days=1)

        # Load historical price floors
        price_floors = strategy.get("price_floors", {})
        hist_floor_map = {}
        for month_str, floor_data in price_floors.items():
            try:
                hist_floor_map[int(month_str)] = float(floor_data.get("min_price", 0))
            except (ValueError, TypeError):
                pass
        if not hist_floor_map:
            hist_data = await db_ref.historical_prices.find(
                {"property_id": property_id}, {"_id": 0, "month": 1, "sold_rate": 1}
            ).to_list(800)
            if hist_data:
                monthly_rates = {}
                for h in hist_data:
                    m = h.get("month")
                    if m not in monthly_rates:
                        monthly_rates[m] = []
                    monthly_rates[m].append(h["sold_rate"])
                for m, rates in monthly_rates.items():
                    sorted_rates = sorted(rates)
                    p25 = sorted_rates[len(sorted_rates) // 4]
                    hist_floor_map[m] = round(p25 * 0.95, 2)

        count = 0
        for rt in room_types:
            base = float(rt.get("base_rate", 100) or 100)
            for i in range(365):
                d = now + timedelta(days=i)
                ds = d.strftime("%Y-%m-%d")
                booked = 0
                for p in props:
                    booked += await db_ref.bookings.count_documents({"property_id": p.get("id", ""), "check_in": {"$lte": ds}, "check_out": {"$gt": ds}, "status": {"$ne": "cancelled"}})
                our_occ = min(100, round((booked / total_rooms) * 100))
                supply_snap = supply_map.get(ds)

                price = base
                # 1. DOW
                dow_adj = strategy.get("dow_adjustments", {})
                dow_pct = float(dow_adj.get(d.strftime("%a").lower()[:3], 0))
                if dow_pct:
                    price *= (1 + dow_pct / 100)
                # 2. Monthly
                monthly_adj = strategy.get("monthly_adjustments", {})
                month_pct = float(monthly_adj.get(d.strftime("%b").lower()[:3], 0))
                if month_pct:
                    price *= (1 + month_pct / 100)
                # 3. Occupancy
                occ_pct = 40 if our_occ >= 90 else 20 if our_occ >= 75 else 0 if our_occ >= 50 else -15 if our_occ >= 25 else -30
                if occ_pct:
                    price *= (1 + occ_pct / 100)
                # 4. Market supply
                if supply_snap and supply_snap.get("scraped"):
                    u = supply_snap.get("unavailable_pct", 50)
                    m_adj = 35 if u >= 90 else 25 if u >= 80 else 15 if u >= 70 else 8 if u >= 60 else 0 if u >= 40 else -8 if u >= 25 else -15 if u >= 10 else -25
                    if m_adj:
                        price *= (1 + m_adj / 100)
                # 5. Competitor positioning
                comp_prices = comp_price_map.get(ds, [])
                if comp_prices:
                    comp_avg = sum(comp_prices) / len(comp_prices)
                    diff_pct = ((comp_avg - price) / price) * 100
                    if diff_pct > 20:
                        price *= (1 + min(15, diff_pct * 0.3) / 100)
                    elif diff_pct < -20:
                        price *= (1 + max(-10, diff_pct * 0.2) / 100)
                # 6. Event intelligence (HDS-based)
                event_for_day = event_map.get(ds)
                if event_for_day:
                    hds = int(event_for_day.get("hotel_demand_score", 0) or 0)
                    imp = event_for_day.get("impact", "")
                    # Smart HDS-based boost
                    if hds >= 80 or imp == "critical":
                        ev_pct = 45
                    elif hds >= 60 or imp in ("high", "mega"):
                        ev_pct = 30
                    elif hds >= 40 or imp in ("moderate", "large"):
                        ev_pct = 15
                    elif hds >= 20 or imp in ("low", "medium", "small"):
                        ev_pct = 5
                    else:
                        ev_pct = 0
                    if ev_pct:
                        price *= (1 + ev_pct / 100)
                # 7. Aggressiveness
                agg = float(strategy.get("aggressiveness", 1.0))
                price *= agg
                # 8. Historical floor
                hist_floor = hist_floor_map.get(d.month, 0)
                if hist_floor and price < hist_floor:
                    price = hist_floor
                # 9. Guardrails
                price = round(max(base * 0.5, min(base * 3.0, price)), 2)

                reason = "auto-scanner (market+events+historical)"
                if event_for_day:
                    reason += f" | Event: {event_for_day.get('name', '')}"

                await db_ref.rate_overrides.update_one(
                    {"property_id": property_id, "date": ds, "room_type_id": rt.get("id", "")},
                    {"$set": {"property_id": property_id, "room_type_id": rt.get("id", ""), "date": ds, "custom_rate": price, "set_by": "auto-scanner", "reason": reason, "updated_at": now.isoformat()}},
                    upsert=True
                )
                count += 1
        logger.info(f"Auto-pricing applied: {count} rates (market + events + historical floors)")

    # ==================== EVENT SCAN FUNCTION FOR SCANNER ====================

    async def _auto_event_scan(db_ref, property_id, city):
        """Called by smart scanner to auto-scan events using GPT-5.2."""
        import re as re_mod
        import json as json_mod
        now = datetime.now(timezone.utc)

        # Web search for events
        events_raw = []
        queries = [
            f"major events concerts festivals {city} {now.strftime('%B %Y')} next 3 months",
            f"football matches stadium events {city} {now.strftime('%Y')} upcoming",
            f"marathon exhibition conference {city} {now.strftime('%B %Y')} schedule",
        ]
        for query in queries:
            try:
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&gl=uk"
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                    resp = await client.get(search_url, headers=headers)
                    events_raw.append(resp.text[:10000])
            except Exception as e:
                logger.warning(f"Auto event search failed: {e}")

        raw_text = "\n".join(events_raw)

        # AI analysis
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            date_from = now.strftime("%Y-%m-%d")
            date_to = (now + timedelta(days=365)).strftime("%Y-%m-%d")

            system_prompt = f"""You are a HOTEL REVENUE intelligence analyst for {city}.
Identify events that make people STAY IN HOTELS — not just any event.

RULES:
- Local football derby (both teams same city) = SKIP or HDS <15 — fans go home
- International match (FIFA/UEFA/away team from abroad) = HDS 70-95
- Top team visiting from DIFFERENT city = HDS 40-60
- Major touring concert (stadium) = HDS 75-95
- Multi-day festival = HDS 80-95
- International conference = HDS 60-80
- Local small gig/event = SKIP

Return ONLY a JSON array. Each event: name, date (YYYY-MM-DD), end_date, venue, category, estimated_attendance, hotel_demand_score (0-100), visitor_origin (international/national/regional/local), is_evening (bool), is_multi_day (bool), reasoning (1 sentence), impact (critical/high/moderate/low/minimal), estimated_hotel_nights, confidence.
Skip events with hotel_demand_score below 15.
Date range: {date_from} to {date_to}."""

            chat = LlmChat(api_key=api_key, session_id=f"auto-event-{city}-{now.strftime('%Y%m%d%H')}",
                           system_message=system_prompt).with_model("openai", "gpt-5.2")
            response = await chat.send_message(UserMessage(text=f"Scraped data:\n{raw_text[:4000]}"))
            json_match = re_mod.search(r'\[[\s\S]*\]', response)
            events = json_mod.loads(json_match.group()) if json_match else []
        except Exception as e:
            logger.error(f"Auto event AI failed: {e}")
            events = []

        # Store events
        stored = 0
        for event in events:
            event_date = event.get("date", "")
            if not event_date:
                continue
            try:
                ed = datetime.strptime(event_date, "%Y-%m-%d")
                now_naive = now.replace(tzinfo=None)
                if ed.date() < now_naive.date() or ed > now_naive + timedelta(days=365):
                    continue
            except (ValueError, TypeError):
                continue

            doc = {
                "id": str(uuid.uuid4())[:8],
                "property_id": property_id,
                "city": city,
                "name": event.get("name", "Unknown"),
                "date": event_date,
                "end_date": event.get("end_date", event_date),
                "venue": event.get("venue", ""),
                "category": event.get("category", "other"),
                "estimated_attendance": int(event.get("estimated_attendance", 0) or 0),
                "hotel_demand_score": int(event.get("hotel_demand_score", 0) or 0),
                "visitor_origin": event.get("visitor_origin", "unknown"),
                "is_evening": event.get("is_evening", True),
                "is_multi_day": event.get("is_multi_day", False),
                "estimated_hotel_nights": int(event.get("estimated_hotel_nights", 0) or 0),
                "reasoning": event.get("reasoning", ""),
                "impact": event.get("impact", "small"),
                "description": event.get("description", ""),
                "confidence": event.get("confidence", "medium"),
                "source": "auto-scanner",
                "scanned_at": now.isoformat(),
            }
            await db_ref.market_events.update_one(
                {"property_id": property_id, "name": doc["name"], "date": doc["date"]},
                {"$set": doc}, upsert=True
            )
            stored += 1

        return {"events_found": len(events), "events_stored": stored}

    async def _auto_competitor_scan(db_ref, property_id, days_ahead: int = 30):
        """Background competitor price scan — scrapes all configured competitors for this property.

        Previously hardcoded to 7 days — too short to populate 30/60/90-day trend charts. Default
        now 30, callable with a larger value from the /scan-comps endpoint when users pick a
        longer window in the UI.

        iter 332 — parallelised: 10 competitors used to scrape sequentially
        (10 × 30 days × ~4s = ~20 min). Now 3 competitors run concurrently
        under a Semaphore, cutting a 30-day fleet refresh to ~6-7 min and
        keeping the per-hotel trend chart fresh within a sane polling window.
        Per-competitor we still go sequential across dates because hammering
        the SAME hotel page in parallel triggers Booking.com rate limits.
        """
        from utils.booking_scraper import scrape_booking_url, build_dated_url

        comps = await db_ref.market_competitors.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(20)

        if not comps:
            return {"competitors_scanned": 0, "prices_found": 0}

        now = datetime.now(timezone.utc)
        days_ahead = max(1, min(int(days_ahead), 90))
        total_prices = [0]  # mutable so workers can accumulate

        prop = await db_ref.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        target_currency = prop.get("currency") or "CHF"

        comp_sem = asyncio.Semaphore(3)

        async def _scan_one_competitor(comp):
            async with comp_sem:
                comp_prices = []
                base_url = comp.get("booking_url", "")
                if not base_url:
                    return
                cached_hotel_id = comp.get("booking_hotel_id")
                last_score = None
                resolved_hotel_id = cached_hotel_id
                resolved_name = comp.get("name", "")
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
                            total_prices[0] += 1
                            if result["score"]:
                                last_score = result["score"]
                        else:
                            comp_prices.append({"date": checkin, "lowest_price": None, "scraped": False,
                                                "error": result.get("error")})
                    except Exception as e:
                        logger.warning(f"Auto comp scrape failed for {comp.get('name')}: {e}")
                        comp_prices.append({"date": checkin, "lowest_price": None, "scraped": False})
                    # Per-hotel polite pacing — keep 1.5s between SAME-hotel hits.
                    await asyncio.sleep(1.5)
                update_fields = {
                    "prices": comp_prices,
                    "last_scraped": now.isoformat(),
                    "last_source": "auto-scanner",
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
                await db_ref.market_competitors.update_one(
                    {"id": comp["id"]}, {"$set": update_fields}
                )

        await asyncio.gather(*[_scan_one_competitor(c) for c in comps])
        return {"competitors_scanned": len(comps), "prices_found": total_prices[0]}

    async def _auto_our_hotel_scan(db_ref, property_id, days_ahead: int = 14):
        """Scrape OUR OWN hotel's Booking.com page — same cadence as competitors.

        Without this, 'Biz vs Pazar' comparisons weren't apples-to-apples: competitor prices came
        from live Booking.com, but our overlay came from internal rate_overrides. Now both sides
        are measured from the same OTA surface.

        Stores results in `property_booking_snapshots` collection + updates `properties.booking_data`
        with the freshest snapshot for quick overlay reads.
        """
        from utils.booking_scraper import scrape_booking_url, build_dated_url

        prop = await db_ref.properties.find_one(
            {"id": property_id},
            {"_id": 0, "booking_url": 1, "name": 1, "currency": 1, "city": 1, "booking_hotel_id": 1}
        )
        if not prop or not prop.get("booking_url"):
            return {"scraped": False, "reason": "no_booking_url"}

        base_url = prop["booking_url"]
        target_currency = prop.get("currency") or "CHF"
        cached_hotel_id = prop.get("booking_hotel_id")
        name_hint = (prop.get("name") or "").strip()[:18]
        now = datetime.now(timezone.utc)
        # Clamped to the same [1, 90] window competitors use — lets the violet "Our Hotel"
        # line extend to match when the user scrapes 60 or 90 days of competitor data.
        days_ahead = max(1, min(int(days_ahead), 90))
        prices = []
        review_score = None
        resolved_hotel_id = cached_hotel_id

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
                if result["scraped"]:
                    prices.append({
                        "date": checkin,
                        "lowest_price": result["lowest_price"],
                        "all_prices": result["all_prices"],
                        "scraped": True,
                    })
                    if review_score is None and result["score"]:
                        review_score = result["score"]
                else:
                    prices.append({"date": checkin, "lowest_price": None, "scraped": False,
                                   "error": result.get("error")})
            except Exception as e:
                logger.warning(f"Our-hotel Booking scrape failed for {property_id} on {checkin}: {e}")
                prices.append({"date": checkin, "lowest_price": None, "scraped": False})
            await asyncio.sleep(1.5)  # polite pacing

        valid_prices = [p["lowest_price"] for p in prices if p.get("lowest_price")]
        avg_price = round(sum(valid_prices) / len(valid_prices), 2) if valid_prices else None
        snapshot = {
            "property_id": property_id,
            "snapshot_at": now.isoformat(),
            "booking_url": base_url,
            "currency": prop.get("currency", "GBP"),
            "review_score": review_score,
            "days_scraped": days_ahead,
            "days_with_price": len(valid_prices),
            "avg_price": avg_price,
            "min_price": min(valid_prices) if valid_prices else None,
            "max_price": max(valid_prices) if valid_prices else None,
            "daily_prices": prices,
        }

        # Archive (keep last 30 snapshots per property for trend)
        await db_ref.property_booking_snapshots.insert_one({**snapshot, "id": str(uuid.uuid4())[:12]})
        # Trim to latest 30
        to_delete = await db_ref.property_booking_snapshots.find(
            {"property_id": property_id}, {"_id": 1}
        ).sort("snapshot_at", -1).skip(30).to_list(1000)
        if to_delete:
            await db_ref.property_booking_snapshots.delete_many(
                {"_id": {"$in": [d["_id"] for d in to_delete]}}
            )

        # Update quick-read field on property
        prop_update = {"booking_data": {k: v for k, v in snapshot.items() if k != "_id"}}
        if resolved_hotel_id and resolved_hotel_id != cached_hotel_id:
            prop_update["booking_hotel_id"] = resolved_hotel_id
        if review_score and not prop.get("review_score"):
            prop_update["review_score"] = review_score
        # Pull the real room/apartment/unit count from the same Booking.com page
        # so the Performance Report and other revenue dashboards stop guessing
        # from the (often-mis-seeded) room_types collection.
        try:
            from utils.booking_scraper import scrape_hotel_room_count
            bk_room_count = await scrape_hotel_room_count(base_url)
            if bk_room_count and bk_room_count > 0:
                prop_update["booking_room_count"] = bk_room_count
                prop_update["booking_room_count_scanned_at"] = now.isoformat()
        except Exception as exc:
            logger.warning("Booking room-count scrape failed for %s: %s", property_id, exc)
        await db_ref.properties.update_one(
            {"id": property_id},
            {"$set": prop_update}
        )

        return {"scraped": True, "days_with_price": len(valid_prices),
                "avg_price": avg_price, "review_score": review_score,
                "hotel_id": resolved_hotel_id}

    S._auto_apply_pricing = _auto_apply_pricing
    S._auto_competitor_scan = _auto_competitor_scan
    S._auto_event_scan = _auto_event_scan
    S._auto_our_hotel_scan = _auto_our_hotel_scan
