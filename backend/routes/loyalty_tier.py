"""
Loyalty Tier Engine v2 — multi-criteria tier ladder with auto-upgrade audit.

Tiers are configured per property as an ordered list:
  [{tier_key, name, color, threshold_nights, threshold_revenue, threshold_points, benefits[]}]
Lower index = lower tier. Tier 0 is the default (e.g. "Member").

A guest is auto-evaluated against tiers in DESCENDING order of index — the highest
tier whose ALL configured thresholds are met (any null threshold is treated as 0)
becomes the new tier. Manual override is supported and respected until revoked.

Collections
-----------
loyalty_tier_configs   { property_id, tiers: [...], updated_at, updated_by }
loyalty_guest_tiers    { property_id, guest_id, tier_key, source: "auto"|"manual",
                         since, history: [{from,to,reason,at,by}], updated_at }

Endpoints
---------
GET    /loyalty-tier/config/{property_id}
POST   /loyalty-tier/config/{property_id}        body: {tiers:[...]}
POST   /loyalty-tier/evaluate/{property_id}/{guest_id}
POST   /loyalty-tier/evaluate-batch/{property_id}
POST   /loyalty-tier/manual/{property_id}/{guest_id}   body: {tier_key, reason}
GET    /loyalty-tier/guest/{property_id}/{guest_id}
GET    /loyalty-tier/dashboard/{property_id}
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional
import uuid


DEFAULT_TIERS = [
    {"tier_key": "member",  "name": "Member",  "color": "stone",
     "threshold_nights": 0,  "threshold_revenue": 0,    "threshold_points": 0,
     "benefits": ["Free WiFi"]},
    {"tier_key": "bronze",  "name": "Bronze",  "color": "amber",
     "threshold_nights": 5,  "threshold_revenue": 1000, "threshold_points": 100,
     "benefits": ["Free WiFi", "10% F&B discount"]},
    {"tier_key": "silver",  "name": "Silver",  "color": "slate",
     "threshold_nights": 15, "threshold_revenue": 3000, "threshold_points": 300,
     "benefits": ["Free WiFi", "15% F&B discount", "Late checkout 2pm", "Welcome drink"]},
    {"tier_key": "gold",    "name": "Gold",    "color": "yellow",
     "threshold_nights": 30, "threshold_revenue": 7000, "threshold_points": 700,
     "benefits": ["Free WiFi", "20% F&B discount", "Late checkout 4pm", "Room upgrade (subj)", "Welcome amenity"]},
    {"tier_key": "platinum","name": "Platinum","color": "violet",
     "threshold_nights": 60, "threshold_revenue": 15000,"threshold_points": 1500,
     "benefits": ["Free WiFi", "25% F&B discount", "Late checkout 6pm", "Guaranteed upgrade", "VIP airport transfer", "Personal concierge"]},
]


class TierDef(BaseModel):
    tier_key: str
    name: str
    color: str = "stone"
    threshold_nights: int = Field(0, ge=0)
    threshold_revenue: float = Field(0.0, ge=0.0)
    threshold_points: int = Field(0, ge=0)
    benefits: List[str] = []


class TierConfigReq(BaseModel):
    tiers: List[TierDef]


class ManualTierReq(BaseModel):
    tier_key: str
    reason: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _select_tier(tiers: list, nights: int, revenue: float, points: int) -> dict:
    """Return the highest tier whose thresholds are all met."""
    for tier in reversed(tiers):
        if (nights >= tier.get("threshold_nights", 0) and
            revenue >= tier.get("threshold_revenue", 0) and
            points >= tier.get("threshold_points", 0)):
            return tier
    return tiers[0] if tiers else {}


async def _get_or_seed_config(db, property_id: str) -> dict:
    cfg = await db.loyalty_tier_configs.find_one({"property_id": property_id}, {"_id": 0})
    if cfg:
        return cfg
    seed = {
        "property_id": property_id,
        "tiers": DEFAULT_TIERS,
        "updated_at": _now(),
        "updated_by": "system",
    }
    await db.loyalty_tier_configs.insert_one(dict(seed))
    return seed


async def _guest_aggregates(db, property_id: str, guest_id: str) -> dict:
    """Compute nights stayed, total revenue, loyalty points for one guest."""
    nights_pipe = [
        {"$match": {"property_id": property_id, "guest_id": guest_id, "status": {"$in": ["checked_out", "checked_in", "confirmed"]}}},
        {"$group": {"_id": None, "n": {"$sum": {"$ifNull": ["$nights", 1]}}, "rev": {"$sum": {"$ifNull": ["$total_amount", 0]}}}},
    ]
    agg = await db.bookings.aggregate(nights_pipe).to_list(1)
    nights = int(agg[0]["n"]) if agg else 0
    revenue = float(agg[0]["rev"]) if agg else 0.0
    profile = await db.guest_profiles.find_one({"id": guest_id}, {"_id": 0, "loyalty_points": 1}) or {}
    points = int(profile.get("loyalty_points", 0))
    return {"nights": nights, "revenue": revenue, "points": points}


def create_loyalty_tier_router(db, require_roles):
    router = APIRouter()

    # ---------- CONFIG ----------
    @router.get("/loyalty-tier/config/{property_id}")
    async def get_config(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _get_or_seed_config(db, property_id)

    @router.post("/loyalty-tier/config/{property_id}")
    async def set_config(property_id: str, req: TierConfigReq,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        if not req.tiers:
            raise HTTPException(400, "at least one tier required")
        keys = [t.tier_key for t in req.tiers]
        if len(set(keys)) != len(keys):
            raise HTTPException(400, "tier_keys must be unique")
        tiers_dict = [t.model_dump() for t in req.tiers]
        await db.loyalty_tier_configs.update_one(
            {"property_id": property_id},
            {"$set": {
                "property_id": property_id,
                "tiers": tiers_dict,
                "updated_at": _now(),
                "updated_by": current_user.get("email"),
            }},
            upsert=True,
        )
        return {"ok": True, "tier_count": len(tiers_dict)}

    # ---------- EVALUATE ONE ----------
    @router.post("/loyalty-tier/evaluate/{property_id}/{guest_id}")
    async def evaluate_one(property_id: str, guest_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await _get_or_seed_config(db, property_id)
        agg = await _guest_aggregates(db, property_id, guest_id)
        target = _select_tier(cfg["tiers"], agg["nights"], agg["revenue"], agg["points"])
        if not target:
            raise HTTPException(400, "no tiers configured")

        existing = await db.loyalty_guest_tiers.find_one(
            {"property_id": property_id, "guest_id": guest_id}, {"_id": 0}
        )
        if existing and existing.get("source") == "manual":
            return {"changed": False, "reason": "manual override active", "current_tier": existing.get("tier_key"), "metrics": agg}

        old_tier = existing.get("tier_key") if existing else None
        if old_tier == target["tier_key"]:
            return {"changed": False, "current_tier": old_tier, "metrics": agg}

        history_entry = {
            "from": old_tier, "to": target["tier_key"],
            "reason": "auto_eval", "at": _now(), "by": current_user.get("email") or "system",
        }
        history = (existing.get("history", []) if existing else []) + [history_entry]
        await db.loyalty_guest_tiers.update_one(
            {"property_id": property_id, "guest_id": guest_id},
            {"$set": {
                "property_id": property_id,
                "guest_id": guest_id,
                "tier_key": target["tier_key"],
                "source": "auto",
                "since": _now(),
                "history": history[-50:],
                "metrics_snapshot": agg,
                "updated_at": _now(),
            }},
            upsert=True,
        )
        return {"changed": True, "from": old_tier, "to": target["tier_key"], "metrics": agg, "tier": target}

    # ---------- EVALUATE BATCH ----------
    @router.post("/loyalty-tier/evaluate-batch/{property_id}")
    async def evaluate_batch(property_id: str, limit: int = 1000,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        limit = max(1, min(5000, limit))
        cfg = await _get_or_seed_config(db, property_id)
        guests = await db.guest_profiles.find(
            {"property_id": {"$in": [property_id, None]}}, {"_id": 0, "id": 1}
        ).to_list(limit)
        upgraded = 0
        downgraded = 0
        unchanged = 0
        skipped_manual = 0
        for g in guests:
            gid = g.get("id")
            if not gid:
                continue
            agg = await _guest_aggregates(db, property_id, gid)
            target = _select_tier(cfg["tiers"], agg["nights"], agg["revenue"], agg["points"])
            existing = await db.loyalty_guest_tiers.find_one(
                {"property_id": property_id, "guest_id": gid}, {"_id": 0}
            )
            if existing and existing.get("source") == "manual":
                skipped_manual += 1
                continue
            old_tier = existing.get("tier_key") if existing else None
            if old_tier == target["tier_key"]:
                unchanged += 1
                continue
            old_idx = next((i for i, t in enumerate(cfg["tiers"]) if t["tier_key"] == old_tier), -1)
            new_idx = next((i for i, t in enumerate(cfg["tiers"]) if t["tier_key"] == target["tier_key"]), 0)
            if new_idx > old_idx:
                upgraded += 1
            else:
                downgraded += 1
            history = (existing.get("history", []) if existing else []) + [
                {"from": old_tier, "to": target["tier_key"], "reason": "batch_eval",
                 "at": _now(), "by": current_user.get("email") or "system"}
            ]
            await db.loyalty_guest_tiers.update_one(
                {"property_id": property_id, "guest_id": gid},
                {"$set": {
                    "property_id": property_id, "guest_id": gid,
                    "tier_key": target["tier_key"], "source": "auto", "since": _now(),
                    "history": history[-50:], "metrics_snapshot": agg, "updated_at": _now(),
                }},
                upsert=True,
            )
        return {
            "evaluated": len(guests),
            "upgraded": upgraded,
            "downgraded": downgraded,
            "unchanged": unchanged,
            "skipped_manual": skipped_manual,
        }

    # ---------- MANUAL OVERRIDE ----------
    @router.post("/loyalty-tier/manual/{property_id}/{guest_id}")
    async def manual_override(property_id: str, guest_id: str, req: ManualTierReq,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await _get_or_seed_config(db, property_id)
        valid = {t["tier_key"] for t in cfg["tiers"]}
        if req.tier_key not in valid:
            raise HTTPException(400, f"tier_key must be one of {sorted(valid)}")
        existing = await db.loyalty_guest_tiers.find_one(
            {"property_id": property_id, "guest_id": guest_id}, {"_id": 0}
        )
        old_tier = existing.get("tier_key") if existing else None
        history = (existing.get("history", []) if existing else []) + [
            {"from": old_tier, "to": req.tier_key, "reason": req.reason or "manual",
             "at": _now(), "by": current_user.get("email")}
        ]
        await db.loyalty_guest_tiers.update_one(
            {"property_id": property_id, "guest_id": guest_id},
            {"$set": {
                "property_id": property_id, "guest_id": guest_id,
                "tier_key": req.tier_key, "source": "manual", "since": _now(),
                "history": history[-50:], "updated_at": _now(),
                "manual_reason": req.reason,
            }},
            upsert=True,
        )
        return {"ok": True, "from": old_tier, "to": req.tier_key, "source": "manual"}

    @router.delete("/loyalty-tier/manual/{property_id}/{guest_id}")
    async def revoke_manual(property_id: str, guest_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.loyalty_guest_tiers.update_one(
            {"property_id": property_id, "guest_id": guest_id},
            {"$set": {"source": "auto", "manual_reason": None, "updated_at": _now()}}
        )
        return {"ok": True, "source": "auto"}

    # ---------- GET GUEST ----------
    @router.get("/loyalty-tier/guest/{property_id}/{guest_id}")
    async def get_guest(property_id: str, guest_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        cfg = await _get_or_seed_config(db, property_id)
        record = await db.loyalty_guest_tiers.find_one(
            {"property_id": property_id, "guest_id": guest_id}, {"_id": 0}
        )
        agg = await _guest_aggregates(db, property_id, guest_id)
        if not record:
            current = cfg["tiers"][0] if cfg["tiers"] else None
            return {"guest_id": guest_id, "tier": current, "metrics": agg, "history": [], "source": "auto", "is_seed": True}
        tier = next((t for t in cfg["tiers"] if t["tier_key"] == record["tier_key"]), None)
        # Compute progress to next tier
        idx = next((i for i, t in enumerate(cfg["tiers"]) if t["tier_key"] == record["tier_key"]), 0)
        next_tier = cfg["tiers"][idx + 1] if idx + 1 < len(cfg["tiers"]) else None
        progress = None
        if next_tier:
            def _pct(cur, target):
                return min(100, int(cur / target * 100)) if target else 100
            progress = {
                "next_tier": next_tier,
                "nights_pct": _pct(agg["nights"], next_tier["threshold_nights"]),
                "revenue_pct": _pct(agg["revenue"], next_tier["threshold_revenue"]),
                "points_pct": _pct(agg["points"], next_tier["threshold_points"]),
            }
        return {
            **record, "tier": tier, "metrics": agg, "progress": progress,
        }

    # ---------- DASHBOARD ----------
    @router.get("/loyalty-tier/dashboard/{property_id}")
    async def dashboard(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await _get_or_seed_config(db, property_id)
        records = await db.loyalty_guest_tiers.find(
            {"property_id": property_id}, {"_id": 0, "tier_key": 1, "source": 1, "history": 1, "updated_at": 1, "guest_id": 1}
        ).to_list(5000)
        dist = {t["tier_key"]: 0 for t in cfg["tiers"]}
        manual_count = 0
        for r in records:
            if r.get("source") == "manual":
                manual_count += 1
            dist[r.get("tier_key")] = dist.get(r.get("tier_key"), 0) + 1

        # Recent upgrades (last 30 days)
        cutoff = (datetime.now(timezone.utc).timestamp() - 30 * 86400)
        recent = []
        for r in records:
            for h in (r.get("history") or [])[-3:]:
                try:
                    at_ts = datetime.fromisoformat(h["at"].replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if at_ts >= cutoff and h.get("from") != h.get("to"):
                    recent.append({"guest_id": r["guest_id"], **h})
        recent.sort(key=lambda x: x["at"], reverse=True)
        return {
            "tiers": cfg["tiers"],
            "distribution": dist,
            "total_members": len(records),
            "manual_overrides": manual_count,
            "recent_upgrades": recent[:20],
        }

    return router
