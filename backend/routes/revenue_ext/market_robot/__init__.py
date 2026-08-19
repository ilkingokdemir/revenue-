"""Market Robot paketi — eski tek dosya (9k satır) bakım için modüllere bölündü.
Dış API değişmedi: create_market_robot_router + fleet worker'ları buradan import edilir."""
from .core import create_market_robot_router
from .gap_logic import _internal_close_gap
from .fleet_workers import (fleet_geo_validate_worker, fleet_vision_enrich_worker,
                            fleet_competitor_price_scan_worker)
from .state import SCRAPE_LOCKS, SCRAPE_LOCKS_GEO

__all__ = ["create_market_robot_router", "_internal_close_gap",
           "fleet_geo_validate_worker", "fleet_vision_enrich_worker",
           "fleet_competitor_price_scan_worker", "SCRAPE_LOCKS", "SCRAPE_LOCKS_GEO"]
