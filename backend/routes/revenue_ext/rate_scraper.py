"""
Competitor Rate Scraping Automation — Auto-scan competitor prices and
adjust rates based on market position. Uses existing market_robot data.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_rate_scraper_router(db, require_roles):
    router = APIRouter()

    @router.get("/revenue/rate-scraper/{property_id}")
    async def get_scraper_status(property_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get current scraper status and latest competitor rates."""
        config = await db.rate_scraper_config.find_one({"property_id": property_id}, {"_id": 0})
        if not config:
            config = {
                "property_id": property_id,
                "enabled": False,
                "frequency": "daily",
                "auto_adjust": False,
                "strategy": "match_median",
                "max_adjustment_pct": 15,
                "min_rate": 50,
                "max_rate": 500,
            }

        # Latest competitor data
        competitors = await db.market_competitors.find(
            {"$or": [{"property_id": property_id}, {"property_id": "all"}]},
            {"_id": 0}
        ).to_list(20)

        now = datetime.now(timezone.utc)
        scan_days = 14
        daily = []

        for i in range(scan_days):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")

            comp_prices = []
            for comp in competitors:
                for p in (comp.get("prices") or []):
                    if p.get("date") == ds and p.get("lowest_price"):
                        comp_prices.append({
                            "name": comp.get("name", "Competitor"),
                            "price": float(p["lowest_price"]),
                        })

            # Get our rate
            rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
            base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0
            override = await db.rate_overrides.find_one({"property_id": property_id, "date": ds}, {"_id": 0})
            our_rate = float(override.get("custom_rate", base_rate)) if override else base_rate

            avg_comp = round(sum(c["price"] for c in comp_prices) / len(comp_prices), 2) if comp_prices else None
            min_comp = min(c["price"] for c in comp_prices) if comp_prices else None
            max_comp = max(c["price"] for c in comp_prices) if comp_prices else None

            # Suggested rate based on strategy
            suggested = our_rate
            if avg_comp and config.get("auto_adjust"):
                strategy = config.get("strategy", "match_median")
                if strategy == "match_median":
                    suggested = avg_comp
                elif strategy == "undercut_5":
                    suggested = round(avg_comp * 0.95, 2)
                elif strategy == "premium_10":
                    suggested = round(avg_comp * 1.10, 2)
                elif strategy == "match_lowest":
                    suggested = min_comp if min_comp else avg_comp

                # Apply min/max guard
                suggested = max(config.get("min_rate", 50), min(config.get("max_rate", 500), suggested))

                # Apply max adjustment limit
                max_adj = config.get("max_adjustment_pct", 15) / 100
                if abs(suggested - our_rate) / max(our_rate, 1) > max_adj:
                    if suggested > our_rate:
                        suggested = round(our_rate * (1 + max_adj), 2)
                    else:
                        suggested = round(our_rate * (1 - max_adj), 2)

            daily.append({
                "date": ds,
                "dow": d.strftime("%a"),
                "is_weekend": d.weekday() >= 5,
                "our_rate": our_rate,
                "avg_competitor": avg_comp,
                "min_competitor": min_comp,
                "max_competitor": max_comp,
                "competitors_count": len(comp_prices),
                "suggested_rate": round(suggested, 2),
                "diff_pct": round(((our_rate - avg_comp) / avg_comp) * 100, 1) if avg_comp else None,
                "competitors": comp_prices[:5],
            })

        # Last scan info
        last_scan = await db.market_scans.find_one(
            {"property_id": property_id} if property_id != "all" else {},
            {"_id": 0}
        )

        return {
            "config": config,
            "daily": daily,
            "total_competitors": len(competitors),
            "last_scan": last_scan.get("scanned_at") if last_scan else None,
        }

    @router.put("/revenue/rate-scraper/{property_id}/config")
    async def update_scraper_config(property_id: str, data: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update scraper configuration."""
        config = {
            "property_id": property_id,
            "enabled": data.get("enabled", False),
            "frequency": data.get("frequency", "daily"),
            "auto_adjust": data.get("auto_adjust", False),
            "strategy": data.get("strategy", "match_median"),
            "max_adjustment_pct": int(data.get("max_adjustment_pct", 15)),
            "min_rate": float(data.get("min_rate", 50)),
            "max_rate": float(data.get("max_rate", 500)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("name", ""),
        }
        await db.rate_scraper_config.update_one(
            {"property_id": property_id}, {"$set": config}, upsert=True
        )
        return config

    @router.post("/revenue/rate-scraper/{property_id}/apply")
    async def apply_suggested_rates(property_id: str, data: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Apply suggested rates from the scraper."""
        dates = data.get("dates", [])
        if not dates:
            return {"error": "No dates provided"}

        applied = 0
        for entry in dates:
            ds = entry.get("date", "")
            rate = float(entry.get("rate", 0))
            if ds and rate > 0:
                await db.rate_overrides.update_one(
                    {"property_id": property_id, "date": ds},
                    {"$set": {
                        "property_id": property_id,
                        "date": ds,
                        "custom_rate": rate,
                        "source": "rate_scraper",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "updated_by": current_user.get("name", ""),
                    }}, upsert=True
                )
                applied += 1

        return {"applied": applied, "dates": len(dates)}

    return router
