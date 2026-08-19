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

    # Initialize smart scanner with event + competitor + our-hotel scanning
    from routes.integrations_pkg.smart_scanner import init_scanner
    scanner = init_scanner(db, S._scrape_booking_date, S._calculate_price_adjustment, S._auto_apply_pricing, S._auto_event_scan, S._auto_competitor_scan, S._auto_our_hotel_scan)

    @router.post("/revenue/market-robot/{property_id}/scanner/start")
    async def start_scanner(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await scanner.start(property_id)
        return result

    @router.post("/revenue/market-robot/{property_id}/scanner/stop")
    async def stop_scanner(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await scanner.stop(property_id)
        return result

    @router.get("/revenue/market-robot/{property_id}/scanner/status")
    async def scanner_status(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        return scanner.get_status(property_id)

    @router.get("/revenue/market-robot/{property_id}/our-booking")
    async def get_our_booking(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return the freshest Booking.com snapshot for THIS hotel (used by 'Biz vs Pazar' overlays).

        When `property_id == 'all'` (user is in "All Branches" view) we return a neutral
        empty-state response so the UI can render a "pick a branch" hint instead of crashing.
        """
        if property_id == "all":
            return {
                "property_id": "all",
                "name": "",
                "booking_url": "",
                "currency": "GBP",
                "city": "",
                "booking_data": None,
                "all_branches_mode": True,
            }
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "name": 1, "booking_url": 1, "booking_data": 1, "currency": 1, "city": 1}
        )
        if not prop:
            # Don't 404 — the card should render gracefully with an empty state.
            return {
                "property_id": property_id,
                "name": "",
                "booking_url": "",
                "currency": "GBP",
                "city": "",
                "booking_data": None,
                "missing": True,
            }
        return {
            "property_id": property_id,
            "name": prop.get("name", ""),
            "booking_url": prop.get("booking_url", ""),
            "currency": prop.get("currency", "GBP"),
            "city": prop.get("city", ""),
            "booking_data": prop.get("booking_data") or None,
        }

    @router.put("/revenue/market-robot/{property_id}/our-booking")
    async def set_our_booking(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Save/update the property's Booking.com listing URL.

        Also (optionally, default=on) validates the URL and caches `booking_hotel_id`
        on the property doc so future scans skip the expensive detail-page round-trip.
        """
        from utils.booking_scraper import validate_booking_url as _validate
        url = (data.get("booking_url") or "").strip()
        skip_validation = bool(data.get("skip_validation", False))
        if url and "booking.com" not in url.lower():
            raise HTTPException(400, "URL must be a booking.com link")

        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1}) or {}
        currency = prop.get("currency") or "GBP"

        update = {"booking_url": url,
                  "booking_url_updated_at": datetime.now(timezone.utc).isoformat()}
        validation = {}
        if url and not skip_validation:
            try:
                validation = await _validate(url, currency=currency)
                if validation.get("hotel_id"):
                    update["booking_hotel_id"] = validation["hotel_id"]
                if validation.get("hotel_name"):
                    # Only auto-fill property name if it looks uninitialised
                    update_name = False
                    current_name = (prop.get("name") or "").strip().lower() if prop else ""
                    if current_name in ("", "my property", "default"):
                        update_name = True
                    if update_name:
                        update["name"] = validation["hotel_name"]
            except Exception as e:
                logger.warning(f"Our-booking URL validation failed for {property_id}: {e}")
                validation = {"ok": False, "error": str(e)}

        await db.properties.update_one({"id": property_id}, {"$set": update})
        return {"ok": True, "booking_url": url, "validation": validation}

    @router.post("/revenue/market-robot/{property_id}/our-booking/scan")
    async def trigger_our_booking_scan(property_id: str, background_tasks: BackgroundTasks,
                                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Kick off an immediate OTA scrape of our own hotel (runs in background — takes 30-90s)."""
        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "booking_url": 1, "name": 1}
        )
        if not prop or not prop.get("booking_url"):
            raise HTTPException(400, "Set booking_url on the property first")
        background_tasks.add_task(S._auto_our_hotel_scan, db, property_id)
        return {"ok": True, "status": "queued",
                "message": "Scraping started in background. Check GET /our-booking in ~60-90s for results."}

    async def _run_room_count_job(property_id: str, booking_url: str):
        """Worker: regex → vision-LLM cascade. Writes outcome to `room_count_jobs`."""
        from utils.booking_scraper import scrape_hotel_room_count, scrape_booking_screenshot
        rc: Optional[int] = None
        source: Optional[str] = None
        err: Optional[str] = None
        evidence: Optional[str] = None

        # Stage 1 — regex / JSON-LD fast path
        try:
            rc = await scrape_hotel_room_count(booking_url, force_refresh=True)
            if rc:
                source = "booking_com_html"
        except Exception as exc:
            logger.warning("HTML room-count scrape failed for %s: %s", property_id, exc)
            err = str(exc)[:200]

        # Stage 2 — GPT-4o-mini vision fallback when HTML didn't expose a count.
        # We scan multiple dates in parallel and take the MAX of all results, because
        # Booking.com only shows AVAILABLE units for the requested check-in date.
        # A property with 9 apartments may show "3 apartments" on a busy weekend and
        # "9 apartments" on a quiet Tuesday. Max across diverse weekday/weekend dates
        # converges to the real inventory.
        if not rc:
            logger.info("Room-count vision multi-date scan starting for %s", property_id)
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
                import base64 as _b64
                import json as _json
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

                api_key = os.environ.get("EMERGENT_LLM_KEY")
                if not api_key:
                    raise RuntimeError("EMERGENT_LLM_KEY not configured")

                SYSTEM = (
                    "You read Booking.com hotel listings. Extract the property's "
                    "total room/apartment/unit count and return ONLY compact JSON: "
                    '{"room_count": <int|null>, "evidence": <short string>}. '
                    "STRICT RULES: "
                    "- ONLY return a number if you can see explicit copy like "
                    "'this property has X rooms', 'X apartments', 'X studios', "
                    "'X units', or a room-type table where each row is a distinct "
                    "unit. Count distinct units, not duplicate listings. "
                    "- DO NOT use the review count (e.g. '927 reviews'), the "
                    "people count (e.g. 'sleeps 4'), the number of bedrooms in "
                    "one apartment, or the number of property photos. "
                    "- If the page does not explicitly state a total inventory, "
                    "return null. "
                    "- evidence: cite the visible text you used (e.g. "
                    "'\"9 apartments\" near top of description'). "
                    "Return ONLY JSON, no markdown fences."
                )

                # Build a diverse set of probe dates: mix Sun / Tue / Fri across the
                # next 6 months. The further-out / midweek dates usually expose
                # max inventory because most rooms are unsold.
                today = datetime.now(timezone.utc).date()
                candidates: List = []
                offsets = [14, 28, 45, 60, 90, 120]
                for off in offsets:
                    d = today + timedelta(days=off)
                    candidates.append(d)
                # Force at least one Tuesday & one Sunday somewhere in the window
                for off in (35, 70):
                    d = today + timedelta(days=off)
                    # nudge to next Tuesday (weekday=1)
                    while d.weekday() != 1:
                        d += timedelta(days=1)
                    candidates.append(d)
                # Deduplicate
                seen = set()
                probe_dates = []
                for d in candidates:
                    if d not in seen:
                        seen.add(d)
                        probe_dates.append(d)

                async def _scan_one(ci_date, sem) -> Optional[Dict[str, Optional[object]]]:
                    async with sem:
                        co_date = ci_date + timedelta(days=1)
                        url = booking_url
                        if "/hotel/" in url:
                            p = urlparse(url)
                            q = parse_qs(p.query)
                            q["checkin"] = [ci_date.isoformat()]
                            q["checkout"] = [co_date.isoformat()]
                            q.setdefault("group_adults", ["2"])
                            q.setdefault("no_rooms", ["1"])
                            url = urlunparse(p._replace(query=urlencode(q, doseq=True)))
                        # Up to 6 attempts per date: rotate Tor circuit between
                        # them. Each attempt gets a fresh exit IP + fresh
                        # cookie jar (`fresh_context=True` below). Booking
                        # blocks ~80% of Tor exit IPs, so we need many tries
                        # to land on a "clean" exit. With fast-bail on 202,
                        # each failed attempt costs only ~3-5s, so 6 retries
                        # × 5s = ~30s worst-case per date.
                        for attempt in range(6):
                            try:
                                from utils.tor_manager import rotate_circuit
                                # Rotate twice: first call schedules NEWNYM, but
                                # Tor enforces a 10s rate-limit between actual
                                # circuit rebuilds. Calling twice with a small
                                # gap reliably advances to a NEW exit relay
                                # rather than re-using the previous one.
                                await rotate_circuit()
                                await asyncio.sleep(0.5)
                                await rotate_circuit()
                                await asyncio.sleep(2.0)
                            except Exception:
                                pass
                            try:
                                from utils.booking_scraper import scrape_booking_screenshot as _sbs
                                # 18s cap per attempt, warm context + cookie
                                # reset (instead of fresh context). The warm
                                # context reuses the Tor SOCKS connection so
                                # each retry costs ~3-5s instead of 10-15s,
                                # letting us cycle through far more exits.
                                png = await asyncio.wait_for(_sbs(url, full_page=True, clear_cookies=True, timeout_ms=15000), timeout=18)
                                if not png:
                                    continue
                                chat = LlmChat(
                                    api_key=api_key,
                                    session_id=f"rc-{property_id[:8]}-{ci_date.isoformat()}-{attempt}",
                                    system_message=SYSTEM,
                                ).with_model("openai", "gpt-4o-mini")
                                reply = await asyncio.wait_for(chat.send_message(UserMessage(
                                    text="How many rooms / apartments / units does this property have in total?",
                                    file_contents=[ImageContent(image_base64=_b64.b64encode(png).decode("ascii"))],
                                )), timeout=25)
                                raw = (reply or "").strip()
                                if raw.startswith("```"):
                                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
                                try:
                                    parsed = _json.loads(raw)
                                except Exception:
                                    parsed = {}
                                vrc = parsed.get("room_count")
                                if isinstance(vrc, str) and vrc.isdigit():
                                    vrc = int(vrc)
                                if isinstance(vrc, int) and 1 <= vrc <= 2000:
                                    logger.info("Multi-date probe %s @ %s (try %s) = %s (evidence=%s)",
                                                property_id, ci_date, attempt + 1, vrc,
                                                (parsed.get("evidence") or "")[:80])
                                    return {
                                        "room_count": vrc,
                                        "evidence": (parsed.get("evidence") or "")[:200],
                                        "date": ci_date.isoformat(),
                                        "weekday": ci_date.strftime("%a"),
                                    }
                            except asyncio.TimeoutError:
                                logger.warning("Multi-date scan timeout for %s @ %s (try %s)",
                                               property_id, ci_date, attempt + 1)
                            except Exception as scan_exc:
                                logger.warning("Multi-date scan failed for %s @ %s (try %s): %s",
                                               property_id, ci_date, attempt + 1, scan_exc)
                        return None

                # Run scans with limited concurrency — the shared headless Chromium
                # can't serve 8 simultaneous pages without deadlocking.
                sem = asyncio.Semaphore(3)
                scan_results = await asyncio.gather(*[_scan_one(d, sem) for d in probe_dates])
                hits = [s for s in scan_results if s and s.get("room_count")]
                if hits:
                    best = max(hits, key=lambda h: h["room_count"])
                    rc = int(best["room_count"])
                    source = "booking_com_vision_multidate"
                    evidence = (
                        f"max across {len(hits)} dates: {best['room_count']} on "
                        f"{best['weekday']} {best['date']} ({best['evidence']})"
                    )
                    logger.info(
                        "Multi-date room-count for %s: max=%s across %s probes, picked %s",
                        property_id, rc, len(hits), best,
                    )
                else:
                    logger.info("Multi-date room-count for %s: no usable signal across %s probes",
                                property_id, len(probe_dates))
            except Exception as exc:
                logger.warning("Vision room-count multi-date fallback failed for %s: %s", property_id, exc)
                err = err or str(exc)[:200]

        result: Dict[str, Optional[object]] = {
            "room_count": rc,
            "source": source,
            "evidence": evidence,
        }
        if rc:
            await db.properties.update_one(
                {"id": property_id},
                {"$set": {
                    "booking_room_count": rc,
                    "booking_room_count_scanned_at": datetime.now(timezone.utc).isoformat(),
                    "booking_room_count_source": source,
                }}
            )
        # Surface a helpful, action-oriented message when the auto-scan can't
        # crack Booking's anti-bot wall (commonly the case with free IP
        # rotation since Booking blocks all Tor exit ranges at the firewall).
        # The user already has a manual-override field for exactly this case.
        if not rc:
            err = err or "Booking.com tüm denenen IP'leri bot-challenge ile engelledi. Lütfen aşağıdan manuel oda sayısı girin."
        await db.room_count_jobs.update_one(
            {"property_id": property_id},
            {"$set": {
                "status": "done" if rc else "no_data",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
                "error": err,
            }},
        )

    @router.post("/revenue/market-robot/{property_id}/refresh-room-count")
    async def refresh_room_count(property_id: str,
                                 background_tasks: BackgroundTasks,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Kick off a Booking.com room-count scrape in the background.

        Returns immediately (the 60s ingress timeout makes synchronous scraping
        impossible for vision-based extraction, which takes 30-90s). The client
        polls `GET /refresh-room-count/status` to retrieve the result.

        Strategy on the worker:
          1. Fast path — pull `numberOfRooms` / `n_rooms` / "this property has N
             rooms" out of the rendered HTML via regex.
          2. Vision fallback — when HTML doesn't expose it (most apartment-style
             pages), take a full-page screenshot and ask GPT-4o-mini to count
             units WITHOUT reading the review count.
        """
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "booking_url": 1, "booking_room_count": 1}
        )
        if not prop or not prop.get("booking_url"):
            raise HTTPException(400, "Set booking_url on the property first")

        await db.room_count_jobs.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "result": None,
                "error": None,
            }},
            upsert=True,
        )
        background_tasks.add_task(_run_room_count_job, property_id, prop["booking_url"])
        return {
            "ok": True,
            "status": "queued",
            "property_id": property_id,
            "message": "Tarama başlatıldı. Sonuç ~30-90 saniye içinde hazır olacak.",
        }

    @router.get("/revenue/market-robot/{property_id}/refresh-room-count/status")
    async def refresh_room_count_status(property_id: str,
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Poll the latest room-count refresh job for this property."""
        job = await db.room_count_jobs.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        if not job:
            return {"status": "idle"}
        return job

    # ────────────────────────────────────────────────────────────────────
    #  12-month forward price scrape — drives per-month ADR in the forecast
    # ────────────────────────────────────────────────────────────────────
    async def _run_yearly_price_scan(property_id: str, booking_url: str):
        """Scrape Booking.com on the 15th of each of the next 12 months for a
        1-night, 2-adult stay. Stores results in `property_monthly_prices`
        and writes job status to `yearly_price_jobs`. Tor circuit rotates per
        probe so every month gets a fresh exit IP.
        """
        from utils.booking_scraper import scrape_booking_url, build_dated_url
        try:
            from utils.tor_manager import rotate_circuit
        except Exception:
            rotate_circuit = None  # type: ignore

        today = datetime.now(timezone.utc).date()
        # Sample 4 days per month (1st, 8th, 15th, 22nd) for a robust monthly
        # average. Mix of weekday/weekend naturally cycles through the calendar,
        # capturing London's large weekend premium (~30-50% higher Fri-Sun)
        # instead of being biased by whatever a single mid-month probe lands on.
        SAMPLE_DAYS = (1, 8, 15, 22)
        targets: List[Tuple[int, int, "date", "date"]] = []
        for i in range(12):
            y = today.year + (today.month - 1 + i) // 12
            m = (today.month - 1 + i) % 12 + 1
            for d in SAMPLE_DAYS:
                try:
                    ci = date(y, m, d)
                except ValueError:
                    continue
                # Skip past dates (within current month)
                if ci < today:
                    continue
                co = ci + timedelta(days=1)
                targets.append((y, m, ci, co))

        sem = asyncio.Semaphore(3)
        # Group probe results by month_key so we can average at the end.
        per_month: Dict[str, List[Dict]] = {}
        failed_months: List[str] = []

        async def _scrape_one(y, m, ci, co):
            month_key = f"{y:04d}-{m:02d}"
            async with sem:
                price: Optional[float] = None
                last_err: Optional[str] = None
                attempt_used = 0
                url = build_dated_url(booking_url, ci.isoformat(), co.isoformat())
                for attempt in range(4):
                    attempt_used = attempt + 1
                    if rotate_circuit is not None:
                        try:
                            await rotate_circuit()
                            await asyncio.sleep(0.4)
                            await rotate_circuit()
                            await asyncio.sleep(1.5)
                        except Exception:
                            pass
                    try:
                        result = await asyncio.wait_for(scrape_booking_url(url), timeout=22)
                        if result and result.get("lowest_price"):
                            price = float(result["lowest_price"])
                            break
                        last_err = result.get("error") if result else "no_price"
                    except asyncio.TimeoutError:
                        last_err = "timeout"
                    except Exception as e:
                        last_err = str(e)[:120]
                if price:
                    per_month.setdefault(month_key, []).append({
                        "date": ci.isoformat(),
                        "price": round(price, 2),
                        "url": url,
                        "attempt": attempt_used,
                    })
                # Update progress (running probe count) every probe
                produced_so_far = sum(len(v) for v in per_month.values())
                await db.yearly_price_jobs.update_one(
                    {"property_id": property_id},
                    {"$set": {
                        "produced_count": produced_so_far,
                        "probes_total": len(targets),
                        "failed_count": len([k for k in per_month.keys() if not per_month[k]]),
                        "last_month_done": month_key,
                        "last_err": last_err,
                    }},
                )

        try:
            await asyncio.gather(*[_scrape_one(*t) for t in targets])
            produced: List[Dict] = []
            now_iso = datetime.now(timezone.utc).isoformat()
            for month_key, samples in per_month.items():
                if not samples:
                    failed_months.append(month_key)
                    continue
                prices = [s["price"] for s in samples]
                y, m = int(month_key[:4]), int(month_key[5:7])
                produced.append({
                    "property_id": property_id,
                    "month_key": month_key,
                    "year": y,
                    "month": m,
                    "adr": round(sum(prices) / len(prices), 2),
                    "min_price": min(prices),
                    "max_price": max(prices),
                    "scraped_at": now_iso,
                    # Provenance: source, sample size & exact dates used so the
                    # operator can audit and reproduce the average in the UI.
                    "source": "booking_com_live",
                    "booking_url": samples[0]["url"],
                    "sample_size": len(samples),
                    "sample_dates": [s["date"] for s in samples],
                })
            if produced:
                # Replace stale rows for these months
                month_keys = [p["month_key"] for p in produced]
                await db.property_monthly_prices.delete_many({
                    "property_id": property_id,
                    "month_key": {"$in": month_keys},
                })
                await db.property_monthly_prices.insert_many([dict(p) for p in produced])
            await db.yearly_price_jobs.update_one(
                {"property_id": property_id},
                {"$set": {
                    "status": "done" if produced else "no_data",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "produced_count": len(produced),
                    "failed_count": len(failed_months),
                    "failed_months": failed_months,
                }},
            )
        except Exception as e:
            logger.exception("Yearly price scan crashed for %s: %s", property_id, e)
            await db.yearly_price_jobs.update_one(
                {"property_id": property_id},
                {"$set": {
                    "status": "error",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(e)[:200],
                }},
            )

    @router.post("/revenue/market-robot/{property_id}/scrape-yearly-prices")
    async def scrape_yearly_prices(property_id: str,
                                   background_tasks: BackgroundTasks,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Kick off a 12-month forward price scrape in the background. Returns
        immediately; poll `GET /scrape-yearly-prices/status` to track progress.
        """
        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "booking_url": 1}
        )
        if not prop or not prop.get("booking_url"):
            raise HTTPException(400, "Set booking_url on the property first")
        await db.yearly_price_jobs.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "produced_count": 0,
                "failed_count": 0,
                "failed_months": [],
                "last_month_done": None,
                "error": None,
            }},
            upsert=True,
        )
        background_tasks.add_task(_run_yearly_price_scan, property_id, prop["booking_url"])
        return {"ok": True, "status": "queued",
                "message": "12 aylık fiyat taraması başladı (4 gün/ay × 12 ay ≈ 48 probe, ~6-10 dakika)."}

    @router.get("/revenue/market-robot/{property_id}/scrape-yearly-prices/status")
    async def scrape_yearly_prices_status(property_id: str,
                                          current_user: dict = Depends(require_roles("admin", "manager"))):
        job = await db.yearly_price_jobs.find_one({"property_id": property_id}, {"_id": 0})
        if not job:
            return {"status": "idle"}
        return job

    @router.get("/revenue/market-robot/{property_id}/monthly-prices")
    async def get_monthly_prices(property_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return the most recent 12 months of scraped Booking.com ADRs."""
        rows = await db.property_monthly_prices.find(
            {"property_id": property_id},
            {"_id": 0},
        ).sort("month_key", 1).to_list(24)
        return {"property_id": property_id, "prices": rows}

    # ────────────────────────────────────────────────────────────────────
    #  YoY historical revenue upload (PDF / JPG / Excel / CSV)
    # ────────────────────────────────────────────────────────────────────
    @router.post("/revenue/market-robot/{property_id}/yoy-upload/preview")
    async def yoy_upload_preview(property_id: str,
                                 file: UploadFile = File(...),
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Parse an uploaded historical revenue file (Excel/CSV/PDF/JPG/PNG)
        WITHOUT saving — returns detected month/revenue rows so the operator
        can review/edit in the UI before confirming.
        """
        from utils.yoy_parser import parse_upload
        try:
            content = await file.read()
        except Exception as e:
            raise HTTPException(400, f"Failed to read file: {e}")
        if not content or len(content) < 16:
            raise HTTPException(400, "Empty or invalid file")
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(400, "File too large (max 20MB)")
        default_year = datetime.now(timezone.utc).year - 1
        try:
            result = parse_upload(content, file.filename or "upload", default_year)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            logger.exception("YoY parse failed: %s", e)
            raise HTTPException(500, f"Parse error: {str(e)[:200]}")
        return {
            "property_id": property_id,
            "filename": file.filename,
            "source_kind": result["source_kind"],
            "detected_count": result["detected_count"],
            "detected_expenses_count": result.get("detected_expenses_count", 0),
            "entries": result["entries"],
            "expenses": result.get("expenses", []),
        }

    @router.post("/revenue/market-robot/{property_id}/yoy-upload/confirm")
    async def yoy_upload_confirm(property_id: str,
                                 payload: dict,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Persist user-approved monthly revenue rows AND expense items.
        Payload:
            {
              "entries": [{"year": 2025, "month": 1, "revenue": 12345.67}, ...],
              "expenses": [{"label": "Rent", "amount": 110000, "period": "annual|monthly"}, ...],
              "source_kind": "excel|csv|pdf|image",
              "replace_expenses": true   # if true (default) clears existing expenses first
            }
        Both lists are optional; whichever is provided gets saved.
        """
        entries = payload.get("entries") or []
        expenses = payload.get("expenses") or []
        source_kind = payload.get("source_kind") or "manual"
        replace_expenses = payload.get("replace_expenses", True)
        if not entries and not expenses:
            raise HTTPException(400, "No entries or expenses to save")
        now_iso = datetime.now(timezone.utc).isoformat()
        uploader = (current_user or {}).get("email") or "unknown"

        # ── Revenue rows ──
        rows: List[Dict] = []
        for e in entries:
            try:
                y = int(e["year"])
                m = int(e["month"])
                rev = float(e["revenue"])
                if not (2000 <= y <= 2100) or not (1 <= m <= 12) or rev <= 0:
                    continue
                rows.append({
                    "property_id": property_id,
                    "year": y,
                    "month": m,
                    "month_key": f"{y:04d}-{m:02d}",
                    "revenue": round(rev, 2),
                    "source": f"upload_{source_kind}",
                    "uploaded_by": uploader,
                    "uploaded_at": now_iso,
                })
            except Exception:
                continue
        if rows:
            keys = [r["month_key"] for r in rows]
            await db.property_yoy_history.delete_many({
                "property_id": property_id, "month_key": {"$in": keys}
            })
            await db.property_yoy_history.insert_many([dict(r) for r in rows])

        # ── Expense rows ──
        from utils.yoy_parser import classify_expense as _classify_exp, EXPENSE_CATEGORY_NAMES as _CATS
        exp_rows: List[Dict] = []
        for x in expenses:
            try:
                label = str(x.get("label") or "").strip()
                amt = float(x.get("amount") or 0)
                period = str(x.get("period") or "annual").lower()
                if not label or amt <= 0 or period not in ("annual", "monthly"):
                    continue
                # User-provided category wins, else classifier-default. Always
                # validated against the canonical list so future analytics can
                # safely group by category without nulls.
                cat = str(x.get("category") or "").strip()
                if not cat or cat not in _CATS:
                    cat = _classify_exp(label)
                exp_rows.append({
                    "property_id": property_id,
                    "label": label,
                    "amount": round(amt, 2),
                    "period": period,
                    "category": cat,
                    "source": f"upload_{source_kind}",
                    "uploaded_by": uploader,
                    "uploaded_at": now_iso,
                })
            except Exception:
                continue
        if expenses is not None and (replace_expenses or exp_rows):
            if replace_expenses:
                await db.property_yoy_expenses.delete_many({"property_id": property_id})
            if exp_rows:
                await db.property_yoy_expenses.insert_many([dict(x) for x in exp_rows])

        return {
            "ok": True,
            "saved_count": len(rows),
            "saved_expenses": len(exp_rows),
            "month_keys": [r["month_key"] for r in rows],
        }

    @router.get("/revenue/market-robot/{property_id}/yoy-history")
    async def yoy_history_list(property_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.property_yoy_history.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("month_key", 1).to_list(60)
        expenses = await db.property_yoy_expenses.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("label", 1).to_list(50)
        return {"property_id": property_id, "rows": rows, "expenses": expenses}

    @router.delete("/revenue/market-robot/{property_id}/yoy-history")
    async def yoy_history_clear(property_id: str,
                                month_key: Optional[str] = None,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Clear all uploaded YoY history for the property, or a specific
        month_key if provided (?month_key=2025-03)."""
        q: Dict = {"property_id": property_id}
        if month_key:
            q["month_key"] = month_key
        res = await db.property_yoy_history.delete_many(q)
        return {"ok": True, "deleted_count": res.deleted_count}

    @router.get("/revenue/market-robot/expense-categories")
    async def yoy_expense_categories(current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return the canonical list of expense category names used by the
        upload modal dropdown. Centralised here so FE/BE stay in sync."""
        from utils.yoy_parser import EXPENSE_CATEGORY_NAMES
        return {"categories": EXPENSE_CATEGORY_NAMES}

    @router.delete("/revenue/market-robot/{property_id}/yoy-expenses")
    async def yoy_expenses_clear(property_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Clear all uploaded YoY expense rows for the property."""
        res = await db.property_yoy_expenses.delete_many({"property_id": property_id})
        return {"ok": True, "deleted_count": res.deleted_count}

    @router.post("/revenue/market-robot/{property_id}/last-minute-discount")
    async def set_last_minute_discount(property_id: str,
                                       payload: dict,
                                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Configure the last-minute discount layer that gets applied to the
        annual revenue forecast.
        Payload: {enabled: bool, discount_pct: 0-50, share_pct: 0-100}
            • discount_pct = 10/20/30 (or any custom 0-50)
            • share_pct = expected % of nights sold at last-minute
              (default 20% — a healthy assumption for most city hotels)
        """
        enabled = bool(payload.get("enabled"))
        discount_pct = float(payload.get("discount_pct") or 0)
        # Default share_pct = 100 → -X% preset = X% straight off gross revenue
        # (matches operator expectation: "click -30% → 30% off the total").
        share_pct = float(payload.get("share_pct") if payload.get("share_pct") is not None else 100)
        if not (0 <= discount_pct <= 50):
            raise HTTPException(400, "discount_pct must be 0-50")
        if not (0 <= share_pct <= 100):
            raise HTTPException(400, "share_pct must be 0-100")
        cfg = {
            "enabled": enabled,
            "discount_pct": round(discount_pct, 1),
            "share_pct": round(share_pct, 1),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": (current_user or {}).get("email") or "unknown",
        }
        await db.properties.update_one(
            {"id": property_id},
            {"$set": {"last_minute_discount": cfg}},
            upsert=False,
        )
        return {"ok": True, "last_minute_discount": cfg}

    @router.get("/revenue/market-robot/{property_id}/last-minute-discount")
    async def get_last_minute_discount(property_id: str,
                                       current_user: dict = Depends(require_roles("admin", "manager"))):
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "last_minute_discount": 1})
        return {"property_id": property_id, "last_minute_discount": (prop or {}).get("last_minute_discount") or {
            "enabled": False, "discount_pct": 0, "share_pct": 100
        }}


    @router.get("/revenue/market-robot/{property_id}/room-count")
    async def get_room_count_state(property_id: str,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return all known room-count signals for the property so the UI can show
        manual, booking-com (auto), and room_types values side-by-side."""
        prop = await db.properties.find_one(
            {"id": property_id},
            {"_id": 0, "manual_room_count": 1, "manual_room_count_set_at": 1,
             "booking_room_count": 1, "booking_room_count_scanned_at": 1,
             "booking_room_count_source": 1}
        )
        room_types_local = await db.room_types.find({"property_id": property_id},
                                                    {"_id": 0, "total_rooms": 1}).to_list(50)
        total_local = sum(int(r.get("total_rooms", 0) or 0) for r in room_types_local)
        return {
            "manual_room_count": (prop or {}).get("manual_room_count"),
            "manual_room_count_set_at": (prop or {}).get("manual_room_count_set_at"),
            "booking_room_count": (prop or {}).get("booking_room_count"),
            "booking_room_count_scanned_at": (prop or {}).get("booking_room_count_scanned_at"),
            "booking_room_count_source": (prop or {}).get("booking_room_count_source"),
            "room_types_total": total_local,
        }

    @router.post("/revenue/market-robot/{property_id}/room-count/manual")
    async def set_manual_room_count(property_id: str,
                                    body: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Operator-supplied room count. Always wins over auto-scan in the
        Performance Report and any other revenue calc. Pass `room_count: null`
        (or omit) to clear the override and fall back to the auto-scanned value.
        """
        rc = body.get("room_count")
        if rc in (None, "", 0):
            await db.properties.update_one(
                {"id": property_id},
                {"$unset": {"manual_room_count": "", "manual_room_count_set_at": ""}},
            )
            return {"ok": True, "manual_room_count": None, "cleared": True}
        try:
            n = int(rc)
        except (TypeError, ValueError):
            raise HTTPException(400, "room_count must be a positive integer")
        if n < 1 or n > 5000:
            raise HTTPException(400, "room_count must be between 1 and 5000")
        await db.properties.update_one(
            {"id": property_id},
            {"$set": {
                "manual_room_count": n,
                "manual_room_count_set_at": datetime.now(timezone.utc).isoformat(),
                "manual_room_count_set_by": current_user.get("email", "unknown"),
            }},
        )
        return {"ok": True, "manual_room_count": n}

    @router.post("/revenue/market-robot/{property_id}/adr/manual")
    async def set_manual_adr(property_id: str,
                             body: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Operator-supplied Average Daily Rate. Always wins over the average
        of room_types base rates in the Performance Report's annual forecast.

        Use when:
          - Booking.com list price differs from your actual sold ADR (commission,
            channel mix, discounts).
          - You sell mostly long-stay / weekly rates that aren't reflected in
            the per-night base_rate column.

        Pass `adr: null` (or 0) to clear the override and fall back to the
        room_types average.
        """
        v = body.get("adr")
        if v in (None, "", 0):
            await db.properties.update_one(
                {"id": property_id},
                {"$unset": {"manual_adr": "", "manual_adr_set_at": "", "manual_adr_set_by": ""}},
            )
            return {"ok": True, "manual_adr": None, "cleared": True}
        try:
            n = float(v)
        except (TypeError, ValueError):
            raise HTTPException(400, "adr must be a positive number")
        if n < 1 or n > 50000:
            raise HTTPException(400, "adr must be between 1 and 50000")
        await db.properties.update_one(
            {"id": property_id},
            {"$set": {
                "manual_adr": round(n, 2),
                "manual_adr_set_at": datetime.now(timezone.utc).isoformat(),
                "manual_adr_set_by": current_user.get("email", "unknown"),
            }},
        )
        return {"ok": True, "manual_adr": round(n, 2)}


    @router.post("/revenue/market-robot/{property_id}/occupancy/manual")
    async def set_manual_occupancy(property_id: str,
                                   body: Dict,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Operator-supplied annual-average occupancy (0–100 %). Wins over both
        the last-30-day actual booking calc and the industry-average fallback.

        Accepts either `occupancy: 0.72` (0–1) or `occupancy: 72` (0–100); we
        normalise to a 0–1 float. Pass `null` (or 0) to clear and revert.
        """
        v = body.get("occupancy")
        if v in (None, "", 0):
            await db.properties.update_one(
                {"id": property_id},
                {"$unset": {"manual_occupancy": "", "manual_occupancy_set_at": "", "manual_occupancy_set_by": ""}},
            )
            return {"ok": True, "manual_occupancy": None, "cleared": True}
        try:
            n = float(v)
        except (TypeError, ValueError):
            raise HTTPException(400, "occupancy must be a number")
        # Normalize: 0.72 → 0.72, 72 → 0.72
        if n > 1.0:
            n = n / 100.0
        if n < 0.01 or n > 1.0:
            raise HTTPException(400, "occupancy must be between 1% and 100%")
        await db.properties.update_one(
            {"id": property_id},
            {"$set": {
                "manual_occupancy": round(n, 4),
                "manual_occupancy_set_at": datetime.now(timezone.utc).isoformat(),
                "manual_occupancy_set_by": current_user.get("email", "unknown"),
            }},
        )
        return {"ok": True, "manual_occupancy": round(n, 4), "manual_occupancy_pct": round(n * 100, 1)}

    S._run_room_count_job = _run_room_count_job
    S._run_yearly_price_scan = _run_yearly_price_scan
    S.get_last_minute_discount = get_last_minute_discount
    S.get_monthly_prices = get_monthly_prices
    S.get_our_booking = get_our_booking
    S.get_room_count_state = get_room_count_state
    S.refresh_room_count = refresh_room_count
    S.refresh_room_count_status = refresh_room_count_status
    S.scanner = scanner
    S.scanner_status = scanner_status
    S.scrape_yearly_prices = scrape_yearly_prices
    S.scrape_yearly_prices_status = scrape_yearly_prices_status
    S.set_last_minute_discount = set_last_minute_discount
    S.set_manual_adr = set_manual_adr
    S.set_manual_occupancy = set_manual_occupancy
    S.set_manual_room_count = set_manual_room_count
    S.set_our_booking = set_our_booking
    S.start_scanner = start_scanner
    S.stop_scanner = stop_scanner
    S.trigger_our_booking_scan = trigger_our_booking_scan
    S.yoy_expense_categories = yoy_expense_categories
    S.yoy_expenses_clear = yoy_expenses_clear
    S.yoy_history_clear = yoy_history_clear
    S.yoy_history_list = yoy_history_list
    S.yoy_upload_confirm = yoy_upload_confirm
    S.yoy_upload_preview = yoy_upload_preview
