"""
Channel-aware Revenue — Open Pricing + Yield Rules Engine.

Open Pricing: Different rates per channel (direct web, Booking.com, Expedia,
corporate) rather than a single "best available rate" pushed everywhere.
Duetto + IDeaS ship this as the premier differentiator.

Yield Rules Engine: If-then rules that auto-adjust rate/restrictions based on
signals (occupancy %, competitor delta, DOW, days-to-arrival, event flag).
Atomize/Pace ship this. We expose it as a simple rules table.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import uuid
import logging

logger = logging.getLogger(__name__)


# ---------- Open Pricing per Channel ----------

class ChannelRateConfig(BaseModel):
    property_id: str
    channel: str  # direct | booking.com | expedia | airbnb | corporate | agent
    base_multiplier: float = 1.0         # e.g. 1.0 for direct, 1.15 for OTA (+commission uplift)
    min_floor_pct: float = 80.0          # don't drop below 80% of BAR
    max_ceiling_pct: float = 150.0       # don't go above 150% of BAR
    weekday_override: Optional[Dict[str, float]] = None  # {"mon": 1.05, "fri": 1.2}


class QuoteRequest(BaseModel):
    property_id: str
    channel: str
    check_in: str
    nights: int = 1
    room_type_id: Optional[str] = None


# ---------- Yield Rules ----------

class YieldRule(BaseModel):
    id: Optional[str] = None
    property_id: str
    name: str
    enabled: bool = True
    priority: int = 0  # higher runs first
    # Triggers (ALL must match)
    triggers: Dict = Field(default_factory=dict)
    # Example triggers:
    # { "occupancy_gte": 75, "days_to_arrival_lte": 14, "dow_in": ["fri","sat"], "event_flag": true }
    # Actions
    actions: Dict = Field(default_factory=dict)
    # Example actions:
    # { "rate_delta_pct": 15, "min_los": 2, "cta_enabled": true, "stop_sell": false }


DEFAULT_CHANNEL_CONFIGS = {
    "direct":       {"base_multiplier": 1.00, "min_floor_pct": 85,  "max_ceiling_pct": 140},
    "booking.com":  {"base_multiplier": 1.18, "min_floor_pct": 95,  "max_ceiling_pct": 160},
    "expedia":      {"base_multiplier": 1.20, "min_floor_pct": 95,  "max_ceiling_pct": 160},
    "airbnb":       {"base_multiplier": 1.15, "min_floor_pct": 90,  "max_ceiling_pct": 155},
    "corporate":    {"base_multiplier": 0.85, "min_floor_pct": 70,  "max_ceiling_pct": 100},
    "agent":        {"base_multiplier": 0.88, "min_floor_pct": 72,  "max_ceiling_pct": 110},
}


def create_channel_revenue_router(db, require_roles):
    router = APIRouter()

    # ---- Channel pricing config ----

    @router.get("/channel-revenue/channels/{property_id}")
    async def get_channel_configs(property_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Return all channels + configs. Auto-creates defaults on first access."""
        rows = await db.channel_rate_configs.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(100)
        existing = {r["channel"] for r in rows}
        # Seed missing defaults
        to_seed = []
        for ch, cfg in DEFAULT_CHANNEL_CONFIGS.items():
            if ch not in existing:
                to_seed.append({
                    "id": str(uuid.uuid4()),
                    "property_id": property_id,
                    "channel": ch,
                    **cfg,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
        if to_seed:
            await db.channel_rate_configs.insert_many(to_seed)
            rows.extend([{k: v for k, v in r.items() if k != "_id"} for r in to_seed])
        rows.sort(key=lambda r: r.get("channel", ""))
        return {"channels": rows}

    @router.put("/channel-revenue/channels/{property_id}/{channel}")
    async def update_channel_config(property_id: str, channel: str, req: ChannelRateConfig,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        update = req.dict(exclude_unset=True, exclude={"property_id", "channel"})
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await db.channel_rate_configs.update_one(
            {"property_id": property_id, "channel": channel},
            {"$set": update},
            upsert=True,
        )
        return {"updated": True, "matched": result.matched_count, "upserted": bool(result.upserted_id)}

    @router.post("/channel-revenue/quote")
    async def quote_channel_rate(req: QuoteRequest,
                                 current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Compute per-channel rate given BAR + channel config + active yield rules."""
        # 1. Get BAR (base available rate)
        rt = None
        if req.room_type_id:
            rt = await db.room_types.find_one({"id": req.room_type_id}, {"_id": 0})
        if not rt:
            rts = await db.room_types.find({"property_id": req.property_id}, {"_id": 0}).limit(1).to_list(1)
            if rts:
                rt = rts[0]
        if not rt:
            raise HTTPException(404, "No room type found")
        bar = float(rt.get("base_price") or 100)

        # 2. Rate override (existing rate calendar)
        try:
            ov = await db.rate_overrides.find_one(
                {"property_id": req.property_id, "date": req.check_in, "room_type_id": rt.get("id")},
                {"_id": 0}
            )
            if ov:
                bar = float(ov.get("price") or bar)
        except Exception:
            pass

        # 3. Channel config
        cfg = await db.channel_rate_configs.find_one(
            {"property_id": req.property_id, "channel": req.channel}, {"_id": 0}
        ) or {}
        default_cfg = DEFAULT_CHANNEL_CONFIGS.get(req.channel, DEFAULT_CHANNEL_CONFIGS["direct"])
        mult = cfg.get("base_multiplier", default_cfg["base_multiplier"])
        min_floor = cfg.get("min_floor_pct", default_cfg["min_floor_pct"])
        max_ceiling = cfg.get("max_ceiling_pct", default_cfg["max_ceiling_pct"])

        # DOW override
        wd = datetime.strptime(req.check_in, "%Y-%m-%d").strftime("%a").lower()
        dow_overrides = (cfg.get("weekday_override") or {})
        if wd in dow_overrides:
            mult = dow_overrides[wd]

        channel_rate = bar * mult

        # 4. Apply yield rules
        rule_log = []
        days_to = max(0, (datetime.strptime(req.check_in, "%Y-%m-%d").date() - date.today()).days)

        # Live occupancy snapshot (for the checkin date)
        occ_pct = 0
        try:
            total_rooms = await db.rooms.count_documents({"property_id": req.property_id})
            occ_count = await db.bookings.count_documents({
                "property_id": req.property_id,
                "check_in": {"$lte": req.check_in},
                "check_out": {"$gt": req.check_in},
                "status": {"$in": ["confirmed", "checked_in"]},
            })
            if total_rooms:
                occ_pct = (occ_count / total_rooms) * 100
        except Exception:
            pass

        active_rules = await db.yield_rules.find(
            {"property_id": req.property_id, "enabled": True}, {"_id": 0}
        ).sort("priority", -1).to_list(50)

        for rule in active_rules:
            triggers = rule.get("triggers", {}) or {}
            matches = True
            if "occupancy_gte" in triggers and occ_pct < triggers["occupancy_gte"]:
                matches = False
            if "occupancy_lte" in triggers and occ_pct > triggers["occupancy_lte"]:
                matches = False
            if "days_to_arrival_lte" in triggers and days_to > triggers["days_to_arrival_lte"]:
                matches = False
            if "days_to_arrival_gte" in triggers and days_to < triggers["days_to_arrival_gte"]:
                matches = False
            if "dow_in" in triggers and wd not in [d.lower() for d in (triggers["dow_in"] or [])]:
                matches = False
            if "channel_in" in triggers and req.channel not in (triggers["channel_in"] or []):
                matches = False
            if not matches:
                continue

            actions = rule.get("actions", {}) or {}
            before = channel_rate
            if "rate_delta_pct" in actions:
                channel_rate *= (1 + actions["rate_delta_pct"] / 100)
            if "rate_delta_abs" in actions:
                channel_rate += actions["rate_delta_abs"]
            rule_log.append({
                "rule_name": rule.get("name"),
                "rate_before": round(before, 2),
                "rate_after": round(channel_rate, 2),
                "actions": actions,
            })

        # 5. Apply floor/ceiling clamps
        floor = bar * (min_floor / 100)
        ceiling = bar * (max_ceiling / 100)
        clamped = max(floor, min(ceiling, channel_rate))
        was_clamped = abs(clamped - channel_rate) > 0.01
        channel_rate = clamped

        total = round(channel_rate * req.nights, 2)
        return {
            "channel": req.channel,
            "room_type": rt.get("name"),
            "check_in": req.check_in,
            "nights": req.nights,
            "bar": round(bar, 2),
            "per_night_rate": round(channel_rate, 2),
            "total": total,
            "currency": rt.get("currency", "GBP"),
            "multiplier_used": round(mult, 3),
            "occupancy_pct": round(occ_pct, 1),
            "rules_applied": rule_log,
            "clamped": was_clamped,
            "floor": round(floor, 2),
            "ceiling": round(ceiling, 2),
        }

    # ---- Yield Rules CRUD ----

    @router.get("/channel-revenue/rules/{property_id}")
    async def list_rules(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.yield_rules.find({"property_id": property_id}, {"_id": 0}).sort("priority", -1).to_list(200)
        return {"rules": rows, "count": len(rows)}

    @router.post("/channel-revenue/rules")
    async def create_rule(rule: YieldRule,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = rule.dict()
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["created_by"] = current_user.get("email")
        await db.yield_rules.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    @router.put("/channel-revenue/rules/{rule_id}")
    async def update_rule(rule_id: str, rule: YieldRule,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        update = rule.dict(exclude_unset=True, exclude={"id"})
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.yield_rules.update_one({"id": rule_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Rule not found")
        return {"updated": True}

    @router.delete("/channel-revenue/rules/{rule_id}")
    async def delete_rule(rule_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.yield_rules.delete_one({"id": rule_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Rule not found")
        return {"deleted": True}

    @router.post("/channel-revenue/rules/{property_id}/seed-defaults")
    async def seed_default_rules(property_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Drop a starter set of 4 common yield rules."""
        existing = await db.yield_rules.count_documents({"property_id": property_id})
        if existing > 0:
            return {"seeded": 0, "note": f"{existing} rule(s) already exist"}
        now = datetime.now(timezone.utc).isoformat()
        defaults = [
            {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "name": "Yüksek doluluk → +%20", "enabled": True, "priority": 10,
                "triggers": {"occupancy_gte": 85},
                "actions": {"rate_delta_pct": 20},
                "created_at": now, "created_by": current_user.get("email"),
            },
            {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "name": "Hafta sonu primi", "enabled": True, "priority": 8,
                "triggers": {"dow_in": ["fri", "sat"]},
                "actions": {"rate_delta_pct": 15},
                "created_at": now, "created_by": current_user.get("email"),
            },
            {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "name": "Last-minute <3 gün indirimi", "enabled": True, "priority": 5,
                "triggers": {"days_to_arrival_lte": 3, "occupancy_lte": 60},
                "actions": {"rate_delta_pct": -10},
                "created_at": now, "created_by": current_user.get("email"),
            },
            {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "name": "OTA kanalı sadece +%5", "enabled": True, "priority": 3,
                "triggers": {"channel_in": ["booking.com", "expedia", "airbnb"]},
                "actions": {"rate_delta_pct": 5},
                "created_at": now, "created_by": current_user.get("email"),
            },
        ]
        await db.yield_rules.insert_many(defaults)
        return {"seeded": len(defaults), "rules": [{k: v for k, v in r.items() if k != "_id"} for r in defaults]}

    return router
