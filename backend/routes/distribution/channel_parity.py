"""
Channel Parity Monitor (Iter 160) — detects when channels' effective rates
drift outside configured tolerance. Critical for OTA contract compliance.

A channel's "effective rate" = base rate (or rate override) × markup rule.
We compute expected rates for the next N days per channel and flag any
deviation beyond `tolerance_pct` vs the direct-website baseline.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def create_channel_parity_router(db, require_roles):
    router = APIRouter()

    @router.get("/channel-parity/{property_id}")
    async def parity(property_id: str, days: int = 14, tolerance_pct: float = 5.0,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """For each channel × date in next `days`, compute effective rate vs
        direct-website baseline. Returns violations (outside ± tolerance_pct).
        """
        now = datetime.now(timezone.utc)
        channels = await db.channel_connections.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(30)
        direct = next((c for c in channels if c.get("channel_id") == "direct"), None)

        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0

        # Compute direct rate for each day
        daily_direct = {}
        for i in range(days):
            d = (now + timedelta(days=i)).strftime("%Y-%m-%d")
            override = await db.rate_overrides.find_one(
                {"property_id": property_id, "date": d}, {"_id": 0}
            )
            rate = float(override.get("custom_rate", base_rate)) if override else base_rate
            if direct:
                rule = direct.get("rate_rule", "same")
                markup = float(direct.get("rate_markup_pct", 0))
                if rule == "markup":
                    rate = round(rate * (1 + markup / 100), 2)
                elif rule == "undercut":
                    rate = round(rate * (1 - markup / 100), 2)
            daily_direct[d] = rate

        violations = []
        by_channel = []
        total_violations = 0
        for ch in channels:
            if ch.get("channel_id") == "direct":
                continue
            rule = ch.get("rate_rule", "same")
            markup = float(ch.get("rate_markup_pct", 0))
            ch_violations = []
            for d, direct_rate in daily_direct.items():
                override = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": d}, {"_id": 0}
                )
                rate = float(override.get("custom_rate", base_rate)) if override else base_rate
                if rule == "markup":
                    ch_rate = round(rate * (1 + markup / 100), 2)
                elif rule == "undercut":
                    ch_rate = round(rate * (1 - markup / 100), 2)
                else:
                    ch_rate = rate

                delta = ch_rate - direct_rate
                delta_pct = round((delta / direct_rate) * 100, 2) if direct_rate > 0 else 0
                in_parity = abs(delta_pct) <= tolerance_pct
                if not in_parity:
                    v = {
                        "date": d,
                        "channel_id": ch["channel_id"],
                        "channel_name": ch.get("name", ""),
                        "direct_rate": direct_rate,
                        "channel_rate": ch_rate,
                        "delta": round(delta, 2),
                        "delta_pct": delta_pct,
                        "severity": "high" if abs(delta_pct) > tolerance_pct * 2 else "medium",
                    }
                    ch_violations.append(v)
                    violations.append(v)
                    total_violations += 1

            by_channel.append({
                "channel_id": ch["channel_id"],
                "channel_name": ch.get("name", ""),
                "connected": bool(ch.get("connected")),
                "rule": rule,
                "markup_pct": markup,
                "violation_count": len(ch_violations),
                "ok_count": days - len(ch_violations),
                "parity_pct": round((days - len(ch_violations)) / days * 100, 1) if days else 100,
            })

        return {
            "property_id": property_id,
            "as_of": now.isoformat(),
            "days": days,
            "tolerance_pct": tolerance_pct,
            "summary": {
                "total_channels": len(by_channel),
                "total_violations": total_violations,
                "channels_with_violations": sum(1 for c in by_channel if c["violation_count"] > 0),
                "overall_parity_pct": round(
                    sum(c["parity_pct"] for c in by_channel) / max(len(by_channel), 1), 1
                ),
            },
            "by_channel": by_channel,
            "violations": violations,
            "baseline": daily_direct,
        }

    @router.get("/channel-parity/{property_id}/config")
    async def get_config(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.channel_parity_config.find_one({"property_id": property_id}, {"_id": 0})
        return cfg or {"property_id": property_id, "tolerance_pct": 5.0,
                       "alert_email": "", "alert_enabled": False}

    @router.put("/channel-parity/{property_id}/config")
    async def update_config(property_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        updates = {
            "property_id": property_id,
            "tolerance_pct": float(data.get("tolerance_pct", 5.0)),
            "alert_email": (data.get("alert_email") or "").strip(),
            "alert_enabled": bool(data.get("alert_enabled", False)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("name", ""),
        }
        await db.channel_parity_config.update_one(
            {"property_id": property_id}, {"$set": updates}, upsert=True
        )
        return updates

    return router
