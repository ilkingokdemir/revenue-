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


class SmartScanner:
    def __init__(self, db, scrape_fn, calculate_price_fn, apply_pricing_fn, event_scan_fn=None):
        self.db = db
        self.scrape_fn = scrape_fn
        self.calculate_price_fn = calculate_price_fn
        self.apply_pricing_fn = apply_pricing_fn
        self.event_scan_fn = event_scan_fn
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
            "tier_status": {},
            "started_at": None,
        }

    async def start(self, property_id: str):
        if self.running:
            return {"status": "already_running"}
        self.running = True
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self.stats["events_found_today"] = 0
        self.task = asyncio.create_task(self._run_loop(property_id))
        return {"status": "started", "event_scanning": bool(self.event_scan_fn)}

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None
        return {"status": "stopped"}

    def get_status(self):
        return {
            "running": self.running,
            "stats": self.stats,
            "tiers": TIERS,
            "event_scan_interval_mins": EVENT_SCAN_INTERVAL_MINS,
        }

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

                # ===== AUTO RE-PRICE =====
                if any_scanned and config.get("auto_pricing", True):
                    await self.apply_pricing_fn(self.db, property_id)
                    self.stats["last_reprice_time"] = datetime.now(timezone.utc).isoformat()
                    logger.info("Smart Scanner: AI Dynamic Pricing auto-applied (market + events + historical)")

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


# Singleton scanner instance
_scanner = None


def get_scanner():
    global _scanner
    return _scanner


def init_scanner(db, scrape_fn, calc_fn, apply_fn, event_scan_fn=None):
    global _scanner
    _scanner = SmartScanner(db, scrape_fn, calc_fn, apply_fn, event_scan_fn)
    return _scanner
