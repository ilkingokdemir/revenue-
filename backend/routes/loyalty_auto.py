"""
Loyalty Tier Auto-Upgrade (P1)
------------------------------
Reads `guest_profiles` (lifetime_stays, lifetime_revenue, RFM score) and
upgrades each guest's loyalty tier automatically when thresholds are met.

Tier ladder (configurable per property; defaults below):
  bronze  → silver: 3 stays   OR  £1,500 lifetime
  silver  → gold:   8 stays   OR  £4,000 lifetime
  gold    → platinum: 20 stays OR £10,000 lifetime
  platinum (top)

Endpoints
---------
POST /loyalty-auto/config                    Upsert tier thresholds (per property)
GET  /loyalty-auto/{property_id}/config
POST /loyalty-auto/sweep                     Cron — recompute & upgrade due guests
GET  /loyalty-auto/{property_id}/upgrades    Recent upgrades log
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import uuid


DEFAULT_TIERS = [
    {"tier": "bronze", "min_stays": 0, "min_lifetime": 0},
    {"tier": "silver", "min_stays": 3, "min_lifetime": 1500},
    {"tier": "gold", "min_stays": 8, "min_lifetime": 4000},
    {"tier": "platinum", "min_stays": 20, "min_lifetime": 10000},
]
TIER_ORDER = ["bronze", "silver", "gold", "platinum"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tier_for(stays: int, lifetime: float, tiers) -> str:
    eligible = "bronze"
    for t in sorted(tiers, key=lambda x: TIER_ORDER.index(x["tier"])):
        if stays >= t["min_stays"] or lifetime >= t["min_lifetime"]:
            eligible = t["tier"]
    return eligible


def create_loyalty_auto_router(db, require_roles):
    router = APIRouter()

    @router.post("/loyalty-auto/config")
    async def upsert(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        tiers = data.get("tiers") or DEFAULT_TIERS
        if not property_id:
            raise HTTPException(400, "property_id required")
        for t in tiers:
            if t.get("tier") not in TIER_ORDER:
                raise HTTPException(400, f"Invalid tier: {t.get('tier')}")
        record = {
            "property_id": property_id,
            "tiers": tiers,
            "updated_at": _now(),
            "updated_by": current_user.get("name", "Staff"),
        }
        await db.loyalty_auto_config.update_one({"property_id": property_id}, {"$set": record}, upsert=True)
        return {"ok": True, "config": record}

    @router.get("/loyalty-auto/{property_id}/config")
    async def get_cfg(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.loyalty_auto_config.find_one({"property_id": property_id}, {"_id": 0})
        return cfg or {"property_id": property_id, "tiers": DEFAULT_TIERS}

    @router.post("/loyalty-auto/sweep")
    async def sweep(data: Optional[Dict] = None,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        property_id = body.get("property_id", "")
        cfg = await db.loyalty_auto_config.find_one({"property_id": property_id}, {"_id": 0}) if property_id else None
        tiers = (cfg or {}).get("tiers") or DEFAULT_TIERS

        q: Dict = {} if not property_id else {"property_id": property_id}
        profiles = await db.guest_profiles.find(q, {"_id": 0}).to_list(20000)
        upgraded = 0
        downgraded = 0
        unchanged = 0
        for p in profiles:
            stays = int(p.get("lifetime_stays") or p.get("total_stays") or 0)
            lifetime = float(p.get("lifetime_revenue") or p.get("total_spent") or 0)
            current = (p.get("loyalty_tier") or "bronze").lower()
            target = _tier_for(stays, lifetime, tiers)
            if target == current:
                unchanged += 1
                continue
            if TIER_ORDER.index(target) > TIER_ORDER.index(current):
                action = "upgrade"
                upgraded += 1
            else:
                action = "downgrade"
                downgraded += 1
            await db.guest_profiles.update_one(
                {"id": p["id"]} if "id" in p else {"guest_email": p.get("guest_email")},
                {"$set": {"loyalty_tier": target, "loyalty_tier_changed_at": _now()}},
            )
            await db.loyalty_auto_log.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": p.get("property_id", property_id),
                "guest_email": p.get("guest_email", ""),
                "guest_name": p.get("guest_name", ""),
                "from_tier": current, "to_tier": target,
                "action": action, "stays": stays, "lifetime": round(lifetime, 2),
                "changed_at": _now(),
            })
        return {"ok": True, "scanned": len(profiles), "upgraded": upgraded,
                 "downgraded": downgraded, "unchanged": unchanged}

    @router.get("/loyalty-auto/{property_id}/upgrades")
    async def upgrades(property_id: str, days: int = 60,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.loyalty_auto_log.find(
            {"property_id": property_id, "changed_at": {"$gte": since}}, {"_id": 0}
        ).sort("changed_at", -1).to_list(500)
        ups = sum(1 for r in rows if r["action"] == "upgrade")
        downs = sum(1 for r in rows if r["action"] == "downgrade")
        return {"items": rows, "count": len(rows), "upgrades": ups, "downgrades": downs}

    return router
