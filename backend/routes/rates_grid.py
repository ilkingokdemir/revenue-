"""
My Rates — Market Pulse style 365-day rate grid for hotel-owner-driven pricing.
Combines: ADR (booked), Occupancy, Live PMS Rate, Scraped OTA Sell Rate,
Min Rate, Floor (LMF), Target Sell Rate, PMS Override, Sentinel AI Rate.
Owner can override AI on any day; batch submitted to PMS+OTA.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def create_rates_grid_router(db, require_roles):
    router = APIRouter()

    @router.get("/rates/grid/{property_id}")
    async def rates_grid(property_id: str, start_date: str = "", days: int = 90,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return per-day metrics for the rate grid."""
        if not start_date:
            start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Invalid start_date")
        days = max(1, min(int(days or 90), 365))
        end_date = (sd + timedelta(days=days)).strftime("%Y-%m-%d")

        # Resolve property scope
        prop_filter = {} if property_id == "all" else {"property_id": property_id}

        # 1) Total room count for occupancy denominator + per-room-type inventory
        total_rooms = await db.rooms.count_documents(prop_filter) or 1
        # Per room_type counts (total inventory)
        room_types_docs = await db.room_types.find(prop_filter, {"_id": 0}).to_list(50)
        rt_inventory = {}  # room_type_id -> {"name", "total"}
        for rt in room_types_docs:
            rt_id = rt.get("id")
            if not rt_id:
                continue
            # Fallback to actual count of rooms with this room_type_id
            actual = await db.rooms.count_documents({"room_type_id": rt_id, **prop_filter})
            total_for_rt = int(rt.get("total_rooms") or actual or 0)
            if total_for_rt > 0:
                rt_inventory[rt_id] = {
                    "name": rt.get("name") or rt_id,
                    "total": total_for_rt,
                }

        # 2) Existing owner-set overrides (separate collection from auto-scanner's rate_overrides)
        ov_query = {"date": {"$gte": start_date, "$lt": end_date}, **prop_filter}
        overrides = await db.owner_rate_overrides.find(ov_query, {"_id": 0}).to_list(1000)
        ov_by_date = {o["date"]: o for o in overrides}

        # 3) Default master rate (from rate_plans collection if exists, fallback constant)
        default_rate_doc = await db.rate_plans.find_one(prop_filter, {"_id": 0})
        default_rate = float((default_rate_doc or {}).get("base_rate") or 90)

        # 4) Compset / scraped OTA rates (last result per date)
        compset_query = {"check_in_date": {"$gte": start_date, "$lt": end_date}, **prop_filter}
        compset = await db.competitor_rates.find(compset_query, {"_id": 0}).to_list(2000)
        # Aggregate own scraped rate (rate type = "own" or rate from market_robot_runs)
        comp_by_date: dict = {}
        for c in compset:
            d = c.get("check_in_date") or c.get("date")
            if not d:
                continue
            entry = comp_by_date.setdefault(d, {"prices": [], "own": None})
            if c.get("hotel_role") == "own" or c.get("source") == "self":
                entry["own"] = c.get("rate") or c.get("price")
            else:
                p = c.get("rate") or c.get("price")
                if p:
                    entry["prices"].append(float(p))

        # 5) Bookings for ADR + occupancy + pickup
        bk_query = {"check_in": {"$lt": end_date}, "check_out": {"$gt": start_date},
                    "status": {"$in": ["confirmed", "checked_in", "checked_out"]}, **prop_filter}
        bookings = await db.bookings.find(bk_query,
            {"_id": 0, "check_in": 1, "check_out": 1, "total_amount": 1, "total_price": 1,
             "rooms": 1, "created_at": 1, "room_type_id": 1}
        ).to_list(5000)
        # Pickup = bookings created in last 24h that affect this date
        cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        new_bookings = [b for b in bookings if (b.get("created_at") or "") >= cutoff]

        days_list = []
        for i in range(days):
            d = sd + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            ov = ov_by_date.get(ds, {})
            comp = comp_by_date.get(ds, {})
            # Stayed bookings for this date
            stay = [b for b in bookings if (b.get("check_in") or "") <= ds and (b.get("check_out") or "") > ds]
            in_house = sum(int(b.get("rooms") or 1) for b in stay)
            occ_pct = round(min(100.0, in_house / total_rooms * 100), 1) if total_rooms else 0.0
            # ADR — average paid amount among stay bookings
            adrs = [float(b.get("total_amount") or b.get("total_price") or 0) for b in stay
                    if (b.get("total_amount") or b.get("total_price"))]
            adr = round(sum(adrs) / len(adrs), 2) if adrs else 0.0
            # Pickup count
            pickup = len([b for b in new_bookings
                          if (b.get("check_in") or "") <= ds and (b.get("check_out") or "") > ds])
            # Per room type availability
            availability = []
            for rt_id, rt in rt_inventory.items():
                booked_rt = sum(int(b.get("rooms") or 1) for b in stay
                                if b.get("room_type_id") == rt_id)
                free = max(0, rt["total"] - booked_rt)
                availability.append({
                    "room_type_id": rt_id,
                    "name": rt["name"],
                    "total": rt["total"],
                    "booked": booked_rt,
                    "free": free,
                })
            availability.sort(key=lambda x: x["name"])
            # Live PMS rate = override > base
            live_pms_rate = float(ov.get("live_pms_rate") or default_rate)
            current_sell_rate = comp.get("own")  # scraped from OTA
            comp_avg = round(sum(comp.get("prices", [])) / len(comp["prices"]), 2) if comp.get("prices") else None
            # AI suggestion (simple heuristic: weight occupancy + pickup)
            ai_rate = _ai_suggest(default_rate, occ_pct, pickup, comp_avg, ov)
            min_rate = float(ov.get("min_rate") or 70)
            floor_rate = ov.get("floor_rate")  # date-specific
            target_sell = ov.get("target_sell_rate")
            pms_override = ov.get("pms_override")
            ai_status = ov.get("ai_status") or "sentinel"
            days_list.append({
                "date": ds,
                "dow": d.strftime("%a"),
                "ai_status": ai_status,
                "adr": adr,
                "occupancy_pct": occ_pct,
                "in_house": in_house,
                "free_total": max(0, total_rooms - in_house),
                "pickup": pickup,
                "min_rate": min_rate,
                "floor_rate": floor_rate,
                "live_pms_rate": live_pms_rate,
                "current_sell_rate": current_sell_rate,
                "compset_avg": comp_avg,
                "ai_rate": ai_rate,
                "target_sell_rate": target_sell,
                "pms_override": pms_override,
                "availability": availability,
            })

        # Min rate alerts
        min_rate_days = sum(1 for d in days_list
                            if d["live_pms_rate"] <= d["min_rate"] + 1)
        avg_occ = round(sum(d["occupancy_pct"] for d in days_list) / max(1, len(days_list)), 1)

        return {
            "property_id": property_id,
            "start_date": start_date,
            "days": len(days_list),
            "total_rooms": total_rooms,
            "default_rate": default_rate,
            "room_types": [{"id": rt_id, "name": rt["name"], "total": rt["total"]}
                           for rt_id, rt in rt_inventory.items()],
            "stats": {
                "min_rate_days": min_rate_days,
                "avg_occupancy_pct": avg_occ,
                "total_pickup": sum(d["pickup"] for d in days_list),
            },
            "rows": days_list,
        }

    @router.post("/rates/grid/override")
    async def save_overrides(data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Batch upsert per-date overrides."""
        property_id = data.get("property_id", "")
        changes = data.get("changes", [])
        if not changes:
            return {"saved": 0}
        now = datetime.now(timezone.utc).isoformat()
        saved = 0
        for ch in changes:
            d = ch.get("date")
            if not d:
                continue
            update = {k: v for k, v in {
                "min_rate": _to_float(ch.get("min_rate")),
                "floor_rate": _to_float(ch.get("floor_rate")),
                "target_sell_rate": _to_float(ch.get("target_sell_rate")),
                "pms_override": _to_float(ch.get("pms_override")),
                "ai_status": ch.get("ai_status"),
                "live_pms_rate": _to_float(ch.get("live_pms_rate")),
            }.items() if v is not None}
            if not update:
                continue
            update["updated_at"] = now
            update["updated_by"] = current_user.get("name", "")
            result = await db.owner_rate_overrides.update_one(
                {"property_id": property_id, "date": d},
                {"$set": update,
                 "$setOnInsert": {"id": str(uuid.uuid4()), "property_id": property_id,
                                  "date": d, "created_at": now}},
                upsert=True
            )
            if result.modified_count or result.upserted_id:
                saved += 1
        return {"saved": saved}

    @router.delete("/rates/grid/override/{property_id}/{date}")
    async def delete_override(property_id: str, date: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await db.owner_rate_overrides.delete_one({"property_id": property_id, "date": date})
        return {"deleted": result.deleted_count}

    @router.post("/rates/grid/submit-to-pms")
    async def submit_to_pms(data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Push pending overrides to channel sync queue.
        For now this just logs the intent — real PMS/OTA sync is queued elsewhere."""
        property_id = data.get("property_id", "")
        dates = data.get("dates", [])
        if not dates:
            return {"queued": 0}
        now = datetime.now(timezone.utc).isoformat()
        queued = 0
        for d in dates:
            ov = await db.owner_rate_overrides.find_one(
                {"property_id": property_id, "date": d}, {"_id": 0}
            )
            if not ov:
                continue
            # Effective rate: pms_override > target_sell_rate > existing live_pms_rate
            effective = (ov.get("pms_override") or ov.get("target_sell_rate")
                         or ov.get("live_pms_rate"))
            if not effective:
                continue
            # Guardrail
            min_r = ov.get("min_rate") or 0
            floor_r = ov.get("floor_rate") or 0
            effective = max(effective, min_r, floor_r)
            await db.rate_sync_queue.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "date": d,
                "rate": effective,
                "status": "queued",
                "created_at": now,
                "created_by": current_user.get("name", ""),
            })
            # Also write back as the new live_pms_rate for grid display
            await db.owner_rate_overrides.update_one(
                {"property_id": property_id, "date": d},
                {"$set": {"live_pms_rate": effective, "submitted_at": now}}
            )
            queued += 1
        return {"queued": queued}

    return router


def _to_float(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def _ai_suggest(base_rate: float, occ_pct: float, pickup: int,
                comp_avg, ov: dict) -> float:
    """Heuristic Sentinel-style AI rate suggestion."""
    # Anchor to compset midpoint if available, else base rate
    anchor = comp_avg if comp_avg and comp_avg > 0 else base_rate
    # Demand multiplier: occupancy * 0.5 + pickup * 2 (capped)
    demand_score = min(100, occ_pct + pickup * 5)
    multiplier = 1.0 + (demand_score - 50) / 200  # ranges 0.75 .. 1.25
    rate = anchor * multiplier
    # Apply guardrails
    min_r = float(ov.get("min_rate") or 70)
    floor_r = float(ov.get("floor_rate") or 0)
    rate = max(rate, min_r, floor_r)
    return round(rate, 2)
