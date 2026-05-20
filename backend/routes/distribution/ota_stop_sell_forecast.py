"""
OTA Stop-Sell Forecaster (P1)
-----------------------------
Predicts which dates the property should temporarily *stop selling on OTAs*
(Booking, Expedia, etc.) so that the last few rooms can be sold direct at a
higher net rate.

Inputs:
  * Per-date inventory (rooms total, rooms left)
  * Last N days' booking pickup curve (how many rooms historically book in
    the last 7 days before stay date) — derived from `bookings.created_at`
    vs `check_in`.
  * OTA commission % (per channel)

Decision rule (default, configurable):
  if (rooms_left <= forecast_pickup_remaining) AND (date_in_horizon <= 14d)
      => recommend STOP-SELL OTAs

Endpoints
---------
POST /ota-forecast/config              Save commission + thresholds
GET  /ota-forecast/{property_id}/config
GET  /ota-forecast/{property_id}        Forecast for next N days (recommendations + stats)
POST /ota-forecast/{property_id}/{date}/snooze   Suppress recommendation for a date
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def create_ota_stop_sell_forecast_router(db, require_roles):
    router = APIRouter()

    @router.post("/ota-forecast/config")
    async def upsert(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        if not property_id:
            raise HTTPException(400, "property_id required")
        record = {
            "property_id": property_id,
            "commission_pct_default": float(data.get("commission_pct_default") or 17.0),
            "horizon_days": int(data.get("horizon_days") or 14),
            "min_pickup_lookback_days": int(data.get("min_pickup_lookback_days") or 60),
            "rooms_left_threshold_pct": float(data.get("rooms_left_threshold_pct") or 25.0),
            "channels": data.get("channels") or ["booking_com", "expedia"],
            "updated_at": _now(),
        }
        await db.ota_forecast_config.update_one({"property_id": property_id}, {"$set": record}, upsert=True)
        return {"ok": True, "config": record}

    @router.get("/ota-forecast/{property_id}/config")
    async def get_cfg(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        return await db.ota_forecast_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "property_id": property_id, "commission_pct_default": 17.0,
            "horizon_days": 14, "rooms_left_threshold_pct": 25.0, "channels": ["booking_com", "expedia"],
        }

    @router.get("/ota-forecast/{property_id}")
    async def forecast(property_id: str, days: int = 14,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.ota_forecast_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        commission = float(cfg.get("commission_pct_default") or 17.0)
        horizon = min(days, int(cfg.get("horizon_days") or 14))
        rooms_left_threshold_pct = float(cfg.get("rooms_left_threshold_pct") or 25.0)

        # Total inventory
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        total_inventory = sum(int(rt.get("inventory") or 0) for rt in room_types)
        if total_inventory == 0:
            return {"items": [], "count": 0, "no_inventory": True}

        # Pickup curve over last 60 days: average bookings made in last 7 days before stay date
        lookback = int(cfg.get("min_pickup_lookback_days") or 60)
        since = (datetime.now(timezone.utc) - timedelta(days=lookback)).isoformat()
        pickup_bookings = await db.bookings.find(
            {"property_id": property_id, "created_at": {"$gte": since},
             "status": {"$nin": ["cancelled", "no_show"]}}, {"_id": 0}
        ).to_list(20000)
        last7_pickup_total = 0
        eligible_dates = 0
        for b in pickup_bookings:
            try:
                created = datetime.fromisoformat((b.get("created_at") or "").replace("Z", "+00:00")).date()
                stay = date.fromisoformat((b.get("check_in") or "")[:10])
            except (ValueError, TypeError):
                continue
            if 0 <= (stay - created).days <= 7:
                last7_pickup_total += 1
                eligible_dates += 1
        avg_last7_pickup = round(last7_pickup_total / max(lookback, 1), 2)

        # Per-date forecast
        snoozes = await db.ota_forecast_snoozes.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        snooze_dates = {s["date"] for s in snoozes if s.get("date")}

        items: List[Dict] = []
        today = _today()
        for d in range(0, horizon):
            stay_date = today + timedelta(days=d)
            stay_iso = stay_date.isoformat()
            occupied = await db.bookings.count_documents({
                "property_id": property_id,
                "check_in": {"$lte": stay_iso}, "check_out": {"$gt": stay_iso},
                "status": {"$nin": ["cancelled", "no_show"]},
            })
            rooms_left = max(total_inventory - occupied, 0)
            rooms_left_pct = round(rooms_left * 100 / total_inventory, 1)
            forecast_pickup = round(avg_last7_pickup * max(7 - d, 1) / 7, 1)
            recommend = (rooms_left <= forecast_pickup
                          and rooms_left_pct <= rooms_left_threshold_pct
                          and stay_iso not in snooze_dates)
            items.append({
                "date": stay_iso,
                "rooms_total": total_inventory,
                "rooms_occupied": occupied,
                "rooms_left": rooms_left,
                "rooms_left_pct": rooms_left_pct,
                "forecast_pickup_remaining": forecast_pickup,
                "stop_sell_recommended": recommend,
                "estimated_commission_savings": round(rooms_left * 100 * commission / 100, 2)
                                                  if recommend else 0,
                "snoozed": stay_iso in snooze_dates,
            })
        return {
            "property_id": property_id,
            "horizon": horizon,
            "avg_last7_pickup_per_day": avg_last7_pickup,
            "commission_pct": commission,
            "items": items,
            "recommended_count": sum(1 for i in items if i["stop_sell_recommended"]),
        }

    @router.post("/ota-forecast/{property_id}/{the_date}/snooze")
    async def snooze(property_id: str, the_date: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.ota_forecast_snoozes.update_one(
            {"property_id": property_id, "date": the_date},
            {"$set": {"property_id": property_id, "date": the_date, "snoozed_at": _now(),
                       "snoozed_by": current_user.get("name", "Staff")}},
            upsert=True,
        )
        return {"ok": True, "date": the_date}

    return router
