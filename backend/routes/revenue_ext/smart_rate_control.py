"""
Smart Rate Control (Iter 165) — Bulk editor for Rate Calendar.

Parity with Mews / Eviivo / Cloudbeds / SiteMinder. Applies:
  • action: increase | decrease | set
  • target: rates | availability | min_los | max_los | cta | ctd | stop_sell
  • unit:   percent | flat   (for rates only; ignored for bools)
  • value:  numeric amount
  • scope:  date range + optional rate_plan_ids + optional room_type_ids

Writes to db.rate_calendar_cells (keyed by property_id, room_type_id,
rate_plan_id, date) which the existing Rate Calendar reads.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date as date_cls, timedelta
from typing import Dict, List
import uuid


ACTIONS = {"increase", "decrease", "set"}
TARGETS = {"rates", "availability", "min_los", "max_los",
           "cta", "ctd", "stop_sell"}
BOOL_TARGETS = {"cta", "ctd", "stop_sell"}


def create_smart_rate_control_router(db, require_roles):
    router = APIRouter()

    @router.post("/smart-rate-control/{property_id}/apply")
    async def apply_bulk(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        action = data.get("action")
        target = data.get("target")
        unit = data.get("unit", "percent")
        value = data.get("value")
        from_date = data.get("from_date")
        to_date = data.get("to_date")

        if action not in ACTIONS:
            raise HTTPException(400, f"action must be one of {sorted(ACTIONS)}")
        if target not in TARGETS:
            raise HTTPException(400, f"target must be one of {sorted(TARGETS)}")
        if not from_date or not to_date:
            raise HTTPException(400, "from_date and to_date required")
        try:
            d_from = date_cls.fromisoformat(from_date)
            d_to = date_cls.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(400, "dates must be YYYY-MM-DD")
        if (d_to - d_from).days > 365:
            raise HTTPException(400, "Range max 1 year")
        if target in BOOL_TARGETS:
            if value not in (True, False, 0, 1, "true", "false"):
                raise HTTPException(400, f"{target} requires boolean value")
            bool_value = str(value).lower() == "true" or value is True or value == 1
        else:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                raise HTTPException(400, "value must be numeric")

        rate_plan_ids: List[str] = data.get("rate_plan_ids") or []
        room_type_ids: List[str] = data.get("room_type_ids") or []

        # Build date list
        dates: List[str] = []
        cur = d_from
        while cur <= d_to:
            dates.append(cur.isoformat())
            cur = cur + timedelta(days=1)

        # Build query for existing cells (in-scope filter)
        # We iterate over all rate_plans × room_types × dates and upsert
        q: Dict = {"property_id": property_id}
        if rate_plan_ids:
            q["rate_plan_id"] = {"$in": rate_plan_ids}
        if room_type_ids:
            q["room_type_id"] = {"$in": room_type_ids}

        # Fetch scoping targets (rate plans under property)
        plans_q = {"property_id": property_id}
        if rate_plan_ids:
            plans_q["id"] = {"$in": rate_plan_ids}
        rate_plans = await db.rate_plans.find(plans_q, {"_id": 0, "id": 1, "room_type_id": 1}) \
            .to_list(500)
        # If no rate_plans collection results, fall back to rate_products
        if not rate_plans:
            rate_plans = await db.rate_products.find(
                plans_q, {"_id": 0, "id": 1, "room_type_id": 1}
            ).to_list(500)
        if not rate_plans:
            raise HTTPException(400, "No rate plans found for this property — create some first")

        # Optional room_type_ids filter applied over rate_plans
        if room_type_ids:
            rate_plans = [p for p in rate_plans if p.get("room_type_id") in room_type_ids]
            if not rate_plans:
                raise HTTPException(400, "No rate plans match the selected room types")

        now = datetime.now(timezone.utc).isoformat()
        touched = 0
        for plan in rate_plans:
            for d in dates:
                cell_key = {"property_id": property_id,
                            "rate_plan_id": plan["id"],
                            "room_type_id": plan.get("room_type_id") or "",
                            "date": d}
                if target in BOOL_TARGETS:
                    await db.rate_calendar_cells.update_one(
                        cell_key,
                        {"$set": {**cell_key, target: bool_value, "updated_at": now,
                                  "updated_by": current_user.get("email", "")},
                         "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
                        upsert=True,
                    )
                    touched += 1
                    continue
                # Numeric target — need existing value for increase/decrease
                existing = await db.rate_calendar_cells.find_one(cell_key, {"_id": 0})
                current_val = (existing or {}).get(target) if existing else None
                if action == "set":
                    new_val = numeric_value
                else:
                    base = current_val if current_val is not None else 0
                    # If we're modifying rates for a plan that's empty, fall back
                    # to the plan's base_price for a sane starting point
                    if target == "rates" and base == 0:
                        base = await _plan_base_price(db, plan["id"])
                    if unit == "percent" and target == "rates":
                        delta = base * numeric_value / 100
                    else:
                        delta = numeric_value
                    new_val = base + delta if action == "increase" else base - delta
                    new_val = max(0, round(new_val, 2))
                await db.rate_calendar_cells.update_one(
                    cell_key,
                    {"$set": {**cell_key, target: new_val, "updated_at": now,
                              "updated_by": current_user.get("email", "")},
                     "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
                    upsert=True,
                )
                touched += 1

        # Write one audit row for the bulk operation
        await db.channel_audit.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "event": "smart_rate_control.apply",
            "details": {"action": action, "target": target, "unit": unit,
                        "value": value, "from_date": from_date, "to_date": to_date,
                        "cells_touched": touched,
                        "rate_plan_count": len(rate_plans),
                        "date_count": len(dates)},
            "user_email": current_user.get("email", ""),
            "ts": now,
        })
        return {
            "status": "ok",
            "cells_touched": touched,
            "dates_in_range": len(dates),
            "rate_plans_in_scope": len(rate_plans),
        }

    @router.get("/smart-rate-control/{property_id}/calendar")
    async def get_calendar(property_id: str,
                           from_date: str = "", to_date: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return calendar cells grouped by room_type × rate_plan × date."""
        if not from_date or not to_date:
            today = date_cls.today()
            d_from = today
            d_to = today + timedelta(days=30)
        else:
            d_from = date_cls.fromisoformat(from_date)
            d_to = date_cls.fromisoformat(to_date)
        cells = await db.rate_calendar_cells.find(
            {"property_id": property_id,
             "date": {"$gte": d_from.isoformat(), "$lte": d_to.isoformat()}},
            {"_id": 0}
        ).to_list(10000)
        return {"from_date": d_from.isoformat(),
                "to_date": d_to.isoformat(),
                "cells": cells}

    return router


async def _plan_base_price(db, plan_id: str) -> float:
    plan = await db.rate_plans.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        plan = await db.rate_products.find_one({"id": plan_id}, {"_id": 0})
    if not plan:
        return 0.0
    return float(plan.get("base_price") or plan.get("price") or 0)
