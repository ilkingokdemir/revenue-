"""
Smart Tiered Scanner — Scans different date windows at different frequencies,
auto-scans events via GPT-5.2, then auto-triggers AI Dynamic Pricing after each batch.
Runs as a background async task.
"""
from datetime import datetime, timezone, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)

# Tiered scan schedule
TIERS = [
    {"label": "Today + Tomorrow",   "days_from": 0,  "days_to": 2,   "interval_mins": 30},
    {"label": "Next 3-7 days",      "days_from": 2,  "days_to": 7,   "interval_mins": 60},
    {"label": "1-2 weeks out",      "days_from": 7,  "days_to": 14,  "interval_mins": 180},
    {"label": "2-4 weeks out",      "days_from": 14, "days_to": 28,  "interval_mins": 360},
    {"label": "1-3 months out",     "days_from": 28, "days_to": 90,  "interval_mins": 720},
    {"label": "3-6 months out",     "days_from": 90, "days_to": 180, "interval_mins": 1440},
    {"label": "6-12 months out",    "days_from": 180, "days_to": 365, "interval_mins": 2880},
]

# Event scanning schedule — every 2 hours for fresh data
EVENT_SCAN_INTERVAL_MINS = 120

# Competitor price scanning — every 3 hours (Booking.com anti-bot friendly pace)
COMPETITOR_SCAN_INTERVAL_MINS = 180


class SmartScanner:
    def __init__(self, db, scrape_fn, calculate_price_fn, apply_pricing_fn, event_scan_fn=None, competitor_scan_fn=None):
        self.db = db
        self.scrape_fn = scrape_fn
        self.calculate_price_fn = calculate_price_fn
        self.apply_pricing_fn = apply_pricing_fn
        self.event_scan_fn = event_scan_fn
        self.competitor_scan_fn = competitor_scan_fn
        self.running = False
        self.task = None
        self.stats = {
            "total_scans_today": 0,
            "total_requests_today": 0,
            "last_scan_time": None,
            "last_reprice_time": None,
            "last_event_scan": None,
            "events_found_today": 0,
            "event_scan_enabled": True,
            "last_competitor_scan": None,
            "competitors_scanned_today": 0,
            "competitor_scan_enabled": True,
            "tier_status": {},
            "started_at": None,
        }

    async def start(self, property_id: str):
        if self.running:
            return {"status": "already_running"}
        self.running = True
        self.current_property_id = property_id
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self.stats["events_found_today"] = 0
        # Persist so backend-restart auto-resumes (user said "turn off yapincaya kadar devam")
        try:
            await self.db.market_robot_config.update_one(
                {"property_id": property_id},
                {"$set": {
                    "scanner_active": True,
                    "scanner_started_at": self.stats["started_at"],
                }},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Scanner persistence on start failed: {e}")
        self.task = asyncio.create_task(self._run_loop(property_id))
        return {"status": "started", "event_scanning": bool(self.event_scan_fn)}

    async def stop(self):
        self.running = False
        pid = getattr(self, "current_property_id", None)
        if self.task:
            self.task.cancel()
            self.task = None
        # Persist so auto-resume does NOT re-start it after backend restart
        try:
            if pid:
                await self.db.market_robot_config.update_one(
                    {"property_id": pid},
                    {"$set": {"scanner_active": False}},
                    upsert=True,
                )
        except Exception as e:
            logger.warning(f"Scanner persistence on stop failed: {e}")
        self.current_property_id = None
        return {"status": "stopped"}

    async def resume_if_active(self):
        """Called on backend startup — resumes scanner for any property where scanner_active=True."""
        try:
            active = await self.db.market_robot_config.find_one(
                {"scanner_active": True}, {"_id": 0, "property_id": 1}
            )
            if active and active.get("property_id"):
                logger.info(f"🔁 Smart Scanner auto-resume for {active['property_id']} (was active before restart)")
                await self.start(active["property_id"])
        except Exception as e:
            logger.warning(f"Scanner resume failed: {e}")

    def get_status(self):
        return {
            "running": self.running,
            "stats": self.stats,
            "tiers": TIERS,
            "event_scan_interval_mins": EVENT_SCAN_INTERVAL_MINS,
            "competitor_scan_interval_mins": COMPETITOR_SCAN_INTERVAL_MINS,
        }

    async def _run_competitor_scan(self, property_id: str):
        """Run competitor price scraping in the background. Every COMPETITOR_SCAN_INTERVAL_MINS."""
        if not self.competitor_scan_fn:
            return 0

        now = datetime.now(timezone.utc)
        last = self.stats.get("last_competitor_scan")

        # Check if competitor scan is due
        if last:
            last_dt = datetime.fromisoformat(last)
            if now < last_dt + timedelta(minutes=COMPETITOR_SCAN_INTERVAL_MINS):
                return 0

        try:
            logger.info(f"Smart Scanner: Starting competitor price scan for {property_id}")
            result = await self.competitor_scan_fn(self.db, property_id)
            comps_scanned = result.get("competitors_scanned", 0)
            prices_found = result.get("prices_found", 0)

            self.stats["last_competitor_scan"] = now.isoformat()
            self.stats["competitors_scanned_today"] += comps_scanned

            logger.info(f"Smart Scanner: Competitor scan complete — {comps_scanned} competitors, {prices_found} prices")
            return comps_scanned
        except Exception as e:
            logger.error(f"Smart Scanner: Competitor scan failed: {e}")
            return 0

    async def _run_event_scan(self, property_id: str, city: str):
        """Run event intelligence scan in the background."""
        if not self.event_scan_fn:
            return 0

        now = datetime.now(timezone.utc)
        last = self.stats.get("last_event_scan")

        # Check if event scan is due
        if last:
            last_dt = datetime.fromisoformat(last)
            if now < last_dt + timedelta(minutes=EVENT_SCAN_INTERVAL_MINS):
                return 0

        try:
            logger.info(f"Smart Scanner: Starting event intelligence scan for {city}")
            result = await self.event_scan_fn(self.db, property_id, city)
            events_found = result.get("events_found", 0)
            events_stored = result.get("events_stored", 0)

            self.stats["last_event_scan"] = now.isoformat()
            self.stats["events_found_today"] += events_found

            logger.info(f"Smart Scanner: Event scan complete — {events_found} found, {events_stored} stored")
            return events_found
        except Exception as e:
            logger.error(f"Smart Scanner: Event scan failed: {e}")
            return 0

    async def _run_loop(self, property_id: str):
        """Main loop — checks each tier and scans if interval has passed. Also runs event scans."""
        # Initialize tier last-scan times
        for tier in TIERS:
            self.stats["tier_status"][tier["label"]] = {
                "last_scan": None,
                "next_scan": datetime.now(timezone.utc).isoformat(),
                "dates_in_tier": tier["days_to"] - tier["days_from"],
                "interval_mins": tier["interval_mins"],
            }

        while self.running:
            try:
                now = datetime.now(timezone.utc)
                config = await self.db.market_robot_config.find_one(
                    {"property_id": property_id}, {"_id": 0}
                ) or {}
                city = config.get("city", "London")
                language = config.get("language", "en-gb")
                any_scanned = False

                # ===== MARKET SUPPLY SCANNING =====
                for tier in TIERS:
                    tier_key = tier["label"]
                    ts = self.stats["tier_status"][tier_key]
                    last = ts.get("last_scan")

                    # Check if this tier is due
                    if last:
                        last_dt = datetime.fromisoformat(last)
                        next_dt = last_dt + timedelta(minutes=tier["interval_mins"])
                        if now < next_dt:
                            ts["next_scan"] = next_dt.isoformat()
                            continue

                    # Scan this tier
                    dates_scanned = 0
                    for i in range(tier["days_from"], tier["days_to"]):
                        d = now + timedelta(days=i)
                        checkin = d.strftime("%Y-%m-%d")
                        checkout = (d + timedelta(days=1)).strftime("%Y-%m-%d")

                        supply = await self.scrape_fn(city, checkin, checkout, language)

                        # Get previous for trend
                        prev = await self.db.market_supply.find_one(
                            {"property_id": property_id, "date": checkin},
                            {"_id": 0},
                            sort=[("scanned_at", -1)]
                        )

                        adj_pct, reason = await self.calculate_price_fn(
                            self.db, property_id, checkin, supply, prev
                        )

                        await self.db.market_supply.insert_one({
                            "scan_id": f"auto-{tier_key[:5]}",
                            "property_id": property_id,
                            "city": city,
                            "date": checkin,
                            "total_properties": supply.get("total_properties", 0),
                            "unavailable_pct": supply.get("unavailable_pct", 0),
                            "available_pct": supply.get("available_pct", 100),
                            "available_est": supply.get("available_est", 0),
                            "scraped": supply.get("scraped", False),
                            "method": supply.get("method", "unknown"),
                            "price_adjustment_pct": adj_pct,
                            "reason": reason,
                            "tier": tier_key,
                            "scanned_at": now.isoformat(),
                        })
                        dates_scanned += 1

                    ts["last_scan"] = now.isoformat()
                    ts["next_scan"] = (now + timedelta(minutes=tier["interval_mins"])).isoformat()
                    ts["dates_scanned"] = dates_scanned
                    self.stats["total_scans_today"] += 1
                    self.stats["total_requests_today"] += dates_scanned
                    self.stats["last_scan_time"] = now.isoformat()
                    any_scanned = True

                    logger.info(f"Smart Scanner: {tier_key} — {dates_scanned} dates scanned")

                # ===== EVENT INTELLIGENCE SCANNING =====
                events_found = await self._run_event_scan(property_id, city)
                if events_found > 0:
                    any_scanned = True

                # ===== COMPETITOR PRICE SCANNING =====
                comps_scanned = await self._run_competitor_scan(property_id)
                if comps_scanned > 0:
                    any_scanned = True

                # ===== AUTO RE-PRICE =====
                if any_scanned and config.get("auto_pricing", True):
                    await self.apply_pricing_fn(self.db, property_id)
                    self.stats["last_reprice_time"] = datetime.now(timezone.utc).isoformat()
                    logger.info("Smart Scanner: AI Dynamic Pricing auto-applied (market + events + competitors + historical)")

                # Log
                await self.db.market_robot_logs.insert_one({
                    "id": f"auto-{now.strftime('%H%M')}",
                    "property_id": property_id,
                    "city": city,
                    "type": "auto_scan",
                    "dates_scanned": self.stats["total_requests_today"],
                    "events_found": events_found,
                    "auto_adjustments": 0,
                    "scanned_at": now.isoformat(),
                })

                # Reset daily stats at midnight
                if now.hour == 0 and now.minute < 2:
                    self.stats["total_scans_today"] = 0
                    self.stats["total_requests_today"] = 0
                    self.stats["events_found_today"] = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Smart Scanner error: {e}")

            # Sleep 1 minute between checks
            await asyncio.sleep(60)


# Multi-instance registry — one SmartScanner per property_id so branches can run in parallel
_scanners = {}


def get_scanner(property_id=None):
    global _scanners
    if property_id is None:
        return _scanners
    return _scanners.get(property_id)


def init_scanner(db, scrape_fn, calc_fn, apply_fn, event_scan_fn=None, competitor_scan_fn=None):
    """Returns a manager object with .get(pid) / .start(pid) / .stop(pid) / .get_status(pid) / .resume_if_active()
    Each property gets its own SmartScanner instance on first use."""
    global _scanners

    class ScannerManager:
        def __init__(self):
            self.db = db

        def _get_or_create(self, pid):
            if pid not in _scanners:
                _scanners[pid] = SmartScanner(db, scrape_fn, calc_fn, apply_fn, event_scan_fn, competitor_scan_fn)
            return _scanners[pid]

        async def start(self, pid):
            return await self._get_or_create(pid).start(pid)

        async def stop(self, pid):
            s = _scanners.get(pid)
            if not s:
                return {"status": "not_running"}
            return await s.stop()

        def get_status(self, pid):
            s = _scanners.get(pid)
            if not s:
                return {"running": False, "stats": {}, "tiers": TIERS,
                        "event_scan_interval_mins": EVENT_SCAN_INTERVAL_MINS,
                        "competitor_scan_interval_mins": COMPETITOR_SCAN_INTERVAL_MINS}
            return s.get_status()

        async def resume_if_active(self):
            """Called on backend startup — resumes scanner for every property with scanner_active=True."""
            try:
                active = await db.market_robot_config.find({"scanner_active": True},
                                                           {"_id": 0, "property_id": 1}).to_list(500)
                for row in active:
                    pid = row.get("property_id")
                    if not pid:
                        continue
                    logger.info(f"🔁 Smart Scanner auto-resume for {pid} (was active before restart)")
                    await self.start(pid)
            except Exception as e:
                logger.warning(f"Scanner resume failed: {e}")

        # Watchdog: DB active but in-memory not running → restart
        async def watchdog(self):
            try:
                active = await db.market_robot_config.find({"scanner_active": True},
                                                           {"_id": 0, "property_id": 1}).to_list(500)
                for row in active:
                    pid = row.get("property_id")
                    s = _scanners.get(pid)
                    if not s or not s.running:
                        logger.info(f"🔁 Smart Scanner watchdog restart for {pid}")
                        await self.start(pid)
            except Exception as e:
                logger.warning(f"Scanner watchdog error: {e}")

    return ScannerManager()
