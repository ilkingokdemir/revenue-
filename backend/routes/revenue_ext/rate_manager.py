"""
Rate Manager — Dynamic pricing based on occupancy, season, day-of-week
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def create_rate_manager_router(db, require_roles):
    router = APIRouter()

    # ==================== RATE PLANS ====================

    @router.get("/rate-manager/plans/{property_id}")
    async def list_rate_plans(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.rate_plans.find(query, {"_id": 0}).sort("name", 1).to_list(100)
        return docs

    @router.post("/rate-manager/plans")
    async def create_rate_plan(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        plan = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": data.get("name", ""),
            "room_type": data.get("room_type", ""),
            "base_rate": data.get("base_rate", 0),
            "currency": data.get("currency", "GBP"),
            "is_active": True,
            # Day-of-week multipliers (1.0 = no change)
            "day_multipliers": data.get("day_multipliers", {d: 1.0 for d in DAYS_OF_WEEK}),
            # Occupancy-based adjustments
            "occupancy_rules": data.get("occupancy_rules", [
                {"threshold": 50, "adjustment": 0},
                {"threshold": 70, "adjustment": 10},
                {"threshold": 85, "adjustment": 25},
                {"threshold": 95, "adjustment": 50},
            ]),
            # Season rules
            "seasons": data.get("seasons", []),
            # Min/max rate bounds
            "min_rate": data.get("min_rate", 0),
            "max_rate": data.get("max_rate", 0),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
            "updated_at": now,
        }
        await db.rate_plans.insert_one(plan)
        plan.pop("_id", None)
        return plan

    @router.put("/rate-manager/plans/{plan_id}")
    async def update_rate_plan(plan_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.rate_plans.update_one({"id": plan_id}, {"$set": updates})
        doc = await db.rate_plans.find_one({"id": plan_id}, {"_id": 0})
        return doc

    @router.delete("/rate-manager/plans/{plan_id}")
    async def delete_rate_plan(plan_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.rate_plans.delete_one({"id": plan_id})
        return {"status": "deleted"}

    # ==================== CALCULATE RATE ====================

    @router.post("/rate-manager/calculate")
    async def calculate_rate(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Calculate dynamic rate for a given date and room type"""
        plan_id = data.get("plan_id", "")
        date_str = data.get("date", "")
        occupancy = data.get("occupancy_pct", 50)

        plan = await db.rate_plans.find_one({"id": plan_id}, {"_id": 0})
        if not plan:
            raise HTTPException(404, "Rate plan not found")

        base = plan.get("base_rate", 0)
        rate = base

        # Day-of-week multiplier
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                day_name = DAYS_OF_WEEK[dt.weekday()]
                multiplier = plan.get("day_multipliers", {}).get(day_name, 1.0)
                rate = rate * multiplier
            except Exception:
                pass

        # Occupancy adjustment
        occ_adj = 0
        for rule in sorted(plan.get("occupancy_rules", []), key=lambda r: r.get("threshold", 0)):
            if occupancy >= rule.get("threshold", 0):
                occ_adj = rule.get("adjustment", 0)
        rate = rate * (1 + occ_adj / 100)

        # Season adjustment
        if date_str:
            for season in plan.get("seasons", []):
                if season.get("start_date", "") <= date_str <= season.get("end_date", ""):
                    rate = rate * (1 + season.get("adjustment_pct", 0) / 100)
                    break

        # Clamp to min/max
        if plan.get("min_rate", 0) > 0:
            rate = max(rate, plan["min_rate"])
        if plan.get("max_rate", 0) > 0:
            rate = min(rate, plan["max_rate"])

        return {
            "base_rate": base,
            "calculated_rate": round(rate, 2),
            "day_multiplier": multiplier if date_str else 1.0,
            "occupancy_pct": occupancy,
            "occupancy_adjustment_pct": occ_adj,
            "currency": plan.get("currency", "GBP"),
        }

    # ==================== RATE CALENDAR (30-day forecast) ====================

    @router.get("/rate-manager/calendar/{plan_id}")
    async def rate_calendar(plan_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate 30-day rate calendar for a plan"""
        plan = await db.rate_plans.find_one({"id": plan_id}, {"_id": 0})
        if not plan:
            raise HTTPException(404, "Rate plan not found")

        # Get current occupancy estimate (simplified)
        today = datetime.now(timezone.utc).date()
        base = plan.get("base_rate", 0)
        calendar = []

        for i in range(30):
            dt = today + timedelta(days=i)
            date_str = dt.isoformat()
            day_name = DAYS_OF_WEEK[dt.weekday()]
            multiplier = plan.get("day_multipliers", {}).get(day_name, 1.0)

            # Simple occupancy estimate (higher on weekends)
            est_occ = 60 if dt.weekday() < 5 else 80

            rate = base * multiplier
            occ_adj = 0
            for rule in sorted(plan.get("occupancy_rules", []), key=lambda r: r.get("threshold", 0)):
                if est_occ >= rule.get("threshold", 0):
                    occ_adj = rule.get("adjustment", 0)
            rate = rate * (1 + occ_adj / 100)

            for season in plan.get("seasons", []):
                if season.get("start_date", "") <= date_str <= season.get("end_date", ""):
                    rate = rate * (1 + season.get("adjustment_pct", 0) / 100)
                    break

            if plan.get("min_rate", 0) > 0:
                rate = max(rate, plan["min_rate"])
            if plan.get("max_rate", 0) > 0:
                rate = min(rate, plan["max_rate"])

            calendar.append({
                "date": date_str,
                "day": day_name[:3],
                "is_weekend": dt.weekday() >= 5,
                "base_rate": base,
                "calculated_rate": round(rate, 2),
                "multiplier": multiplier,
                "est_occupancy": est_occ,
            })

        return {"plan_name": plan.get("name", ""), "currency": plan.get("currency", "GBP"), "days": calendar}

    # ==================== SEASONS ====================

    @router.get("/rate-manager/seasons/{property_id}")
    async def list_seasons(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.rate_seasons.find(query, {"_id": 0}).sort("start_date", 1).to_list(50)
        return docs

    @router.post("/rate-manager/seasons")
    async def create_season(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        season = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": data.get("name", ""),
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
            "adjustment_pct": data.get("adjustment_pct", 0),
            "color": data.get("color", "#3b82f6"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.rate_seasons.insert_one(season)
        season.pop("_id", None)
        return season

    @router.delete("/rate-manager/seasons/{season_id}")
    async def delete_season(season_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.rate_seasons.delete_one({"id": season_id})
        return {"status": "deleted"}

    return router
