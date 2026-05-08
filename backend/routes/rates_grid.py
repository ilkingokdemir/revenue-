"""
My Rates — Market Pulse style 365-day rate grid for hotel-owner-driven pricing.
Combines: ADR (booked), Occupancy, Live PMS Rate, Scraped OTA Sell Rate,
Min Rate, Floor (LMF), Target Sell Rate, PMS Override, Sentinel AI Rate.
Owner can override AI on any day; batch submitted to PMS+OTA.
"""
import json
import logging
import os
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

        # 4b) Owner-locked PMS rates (the actual rate guests see — pushed via submit-to-pms)
        pms_locked_query = {"date": {"$gte": start_date, "$lt": end_date},
                            "set_by": "owner-override", **prop_filter}
        pms_locked = await db.rate_overrides.find(pms_locked_query, {"_id": 0}).to_list(500)
        pms_locked_by_date = {p["date"]: p for p in pms_locked}

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
            # Live PMS rate = locked owner override > grid override > base
            pms_locked = pms_locked_by_date.get(ds)
            if pms_locked and pms_locked.get("custom_rate"):
                live_pms_rate = float(pms_locked.get("custom_rate"))
            else:
                live_pms_rate = float(ov.get("live_pms_rate") or default_rate)
            current_sell_rate = comp.get("own") or (
                float(pms_locked.get("custom_rate")) if pms_locked and pms_locked.get("custom_rate") else None
            )
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
        """Push pending overrides to channel sync queue AND to the PMS rate_overrides
        collection (which booking engine, channel pushes, dynamic_pricing all read from).
        This is the actual 'PMS link' — owner overrides become the live sell rate."""
        property_id = data.get("property_id", "")
        dates = data.get("dates", [])
        if not dates:
            return {"queued": 0, "pms_synced": 0}
        now = datetime.now(timezone.utc).isoformat()
        owner_name = current_user.get("name", "Owner")
        queued = 0
        pms_synced = 0
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

            # Capture AI rate at submit time for win/loss comparison
            ai_at_submit = await _compute_ai_rate_for_date(db, property_id, d)

            # Capture previous PMS rate for history diff
            prev_doc = await db.rate_overrides.find_one(
                {"property_id": property_id, "date": d, "set_by": "owner-override",
                 "room_type_id": ""}, {"_id": 0, "custom_rate": 1}
            )
            prev_rate = float(prev_doc["custom_rate"]) if prev_doc and prev_doc.get("custom_rate") else None

            # 1) Write to channel sync queue (logical record of intent)
            await db.rate_sync_queue.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "date": d,
                "rate": effective,
                "status": "queued",
                "set_by": owner_name,
                "created_at": now,
            })

            # 2) Update grid display
            await db.owner_rate_overrides.update_one(
                {"property_id": property_id, "date": d},
                {"$set": {"live_pms_rate": effective, "submitted_at": now}}
            )

            # 3) PMS LINK — upsert into rate_overrides so booking engine, channel
            # managers, dynamic pricing, scrapers all see the new rate.
            # set_by="owner-override" + locked=True so auto-scanner doesn't overwrite.
            reason_parts = []
            if ov.get("pms_override"):
                reason_parts.append(f"PMS Override £{ov.get('pms_override')}")
            if ov.get("target_sell_rate"):
                reason_parts.append(f"Target £{ov.get('target_sell_rate')}")
            if min_r:
                reason_parts.append(f"Min £{min_r}")
            if floor_r:
                reason_parts.append(f"Floor £{floor_r}")
            reason = "Owner: " + " · ".join(reason_parts) if reason_parts else "Owner override"

            await db.rate_overrides.update_one(
                {"property_id": property_id, "date": d, "set_by": "owner-override",
                 "room_type_id": ""},
                {"$set": {
                    "custom_rate": float(effective),
                    "min_rate": float(min_r) if min_r else 0,
                    "floor_rate": float(floor_r) if floor_r else 0,
                    "locked": True,
                    "reason": reason,
                    "updated_at": now,
                    "updated_by": owner_name,
                 },
                 "$setOnInsert": {"id": str(uuid.uuid4()),
                                  "property_id": property_id,
                                  "date": d,
                                  "room_type_id": "",
                                  "set_by": "owner-override",
                                  "created_at": now}},
                upsert=True
            )

            # 4) HISTORY — every submission appends an audit entry
            await db.rate_override_history.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "date": d,
                "action": "submit",
                "previous_rate": prev_rate,
                "new_rate": float(effective),
                "ai_rate_at_submit": ai_at_submit,
                "delta": round(float(effective) - prev_rate, 2) if prev_rate else None,
                "delta_pct": round(((float(effective) - prev_rate) / prev_rate * 100), 1)
                              if prev_rate else None,
                "delta_vs_ai": round(float(effective) - ai_at_submit, 2) if ai_at_submit else None,
                "fields": {
                    "pms_override": ov.get("pms_override"),
                    "target_sell_rate": ov.get("target_sell_rate"),
                    "min_rate": min_r if min_r else None,
                    "floor_rate": floor_r if floor_r else None,
                },
                "by": owner_name,
                "created_at": now,
            })

            pms_synced += 1
            queued += 1
        return {"queued": queued, "pms_synced": pms_synced}

    @router.get("/rates/grid/history/{property_id}/{date}")
    async def rate_history(property_id: str, date: str, limit: int = 20,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return the audit trail for a specific date."""
        items = await db.rate_override_history.find(
            {"property_id": property_id, "date": date}, {"_id": 0}
        ).sort("created_at", -1).to_list(min(limit, 50))
        return {"property_id": property_id, "date": date, "history": items}

    @router.post("/rates/grid/release/{property_id}/{date}")
    async def release_to_ai(property_id: str, date: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Remove the owner lock for this date — Sentinel AI takes over again."""
        now = datetime.now(timezone.utc).isoformat()
        owner_name = current_user.get("name", "Owner")
        # Capture previous rate for history
        prev_doc = await db.rate_overrides.find_one(
            {"property_id": property_id, "date": date, "set_by": "owner-override",
             "room_type_id": ""}, {"_id": 0, "custom_rate": 1}
        )
        prev_rate = float(prev_doc["custom_rate"]) if prev_doc and prev_doc.get("custom_rate") else None

        # 1) Delete the owner-override doc from PMS source-of-truth
        deleted = await db.rate_overrides.delete_one(
            {"property_id": property_id, "date": date, "set_by": "owner-override",
             "room_type_id": ""}
        )
        # 2) Clear pms_override + target_sell_rate + live_pms_rate from grid (keep min_rate, floor_rate)
        await db.owner_rate_overrides.update_one(
            {"property_id": property_id, "date": date},
            {"$unset": {"pms_override": "", "target_sell_rate": "", "live_pms_rate": ""}}
        )
        # 3) History
        await db.rate_override_history.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "date": date,
            "action": "release",
            "previous_rate": prev_rate,
            "new_rate": None,
            "by": owner_name,
            "created_at": now,
        })
        return {"released": True, "deleted_count": deleted.deleted_count}

    @router.get("/rates/grid/explain/{property_id}/{date}")
    async def explain_rate(property_id: str, date: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """AI-generated explanation of WHY the Sentinel rate is what it is.
        Uses Emergent LLM (gpt-4o-mini) with all context: occupancy, pickup, compset,
        events, day-of-week, lead time."""
        # Re-fetch the day's grid context
        prop_filter = {} if property_id == "all" else {"property_id": property_id}
        # Stay/occupancy
        bk_query = {"check_in": {"$lte": date}, "check_out": {"$gt": date},
                    "status": {"$in": ["confirmed", "checked_in"]}, **prop_filter}
        in_house = await db.bookings.count_documents(bk_query)
        total_rooms = await db.rooms.count_documents(prop_filter) or 1
        occ_pct = round(min(100.0, in_house / total_rooms * 100), 1)
        # Pickup last 24h
        cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        pickup_q = {**bk_query, "created_at": {"$gte": cutoff}}
        pickup_count = await db.bookings.count_documents(pickup_q)
        # Compset
        comp_q = {"check_in_date": date, **prop_filter}
        comp_docs = await db.competitor_rates.find(comp_q, {"_id": 0}).to_list(50)
        comp_prices = [float(c.get("rate") or c.get("price") or 0) for c in comp_docs
                       if c.get("hotel_role") != "own" and (c.get("rate") or c.get("price"))]
        comp_avg = round(sum(comp_prices) / len(comp_prices), 2) if comp_prices else None
        comp_min = min(comp_prices) if comp_prices else None
        comp_max = max(comp_prices) if comp_prices else None
        # Events
        events = await db.event_calendar.find({"date": date, **prop_filter},
                                              {"_id": 0, "name": 1, "category": 1, "magnitude": 1}
        ).to_list(10) if "event_calendar" in await db.list_collection_names() else []
        # Owner override?
        ov = await db.owner_rate_overrides.find_one(
            {"property_id": property_id, "date": date}, {"_id": 0}
        ) or {}
        # PMS locked?
        pms_lock = await db.rate_overrides.find_one(
            {"property_id": property_id, "date": date, "set_by": "owner-override"}, {"_id": 0}
        )
        # Day-of-week + lead time
        try:
            d_obj = datetime.strptime(date, "%Y-%m-%d")
            dow = d_obj.strftime("%A")
            today = datetime.now(timezone.utc).date()
            lead = (d_obj.date() - today).days
        except ValueError:
            dow = "?"
            lead = 0

        # Default base
        rate_plan = await db.rate_plans.find_one(prop_filter, {"_id": 0}) or {}
        base = float(rate_plan.get("base_rate") or 90)

        # Heuristic decomposition
        anchor = comp_avg or base
        demand_score = min(100, occ_pct + pickup_count * 5)
        multiplier = 1.0 + (demand_score - 50) / 200
        ai_rate = round(max(anchor * multiplier, ov.get("min_rate") or 0,
                            ov.get("floor_rate") or 0), 2)

        breakdown = {
            "anchor": {"label": "Compset average" if comp_avg else "Base rate",
                       "value": anchor, "weight": "60%"},
            "occupancy_signal": {"label": f"Occupancy {occ_pct}%",
                                 "value": f"{(occ_pct - 50) / 200 * 100:+.1f}%",
                                 "weight": "25%"},
            "pickup_signal": {"label": f"Pickup +{pickup_count} (24h)",
                              "value": f"{pickup_count * 5 / 200 * 100:+.1f}%",
                              "weight": "15%"},
            "guardrails": {"min_rate": ov.get("min_rate"),
                           "floor_rate": ov.get("floor_rate")},
        }

        # LLM narrative
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        narrative = None
        if api_key:
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                ctx = {
                    "date": date, "day_of_week": dow, "lead_time_days": lead,
                    "occupancy_pct": occ_pct, "in_house": in_house, "total_rooms": total_rooms,
                    "pickup_24h": pickup_count,
                    "compset_avg": comp_avg, "compset_min": comp_min, "compset_max": comp_max,
                    "compset_count": len(comp_prices),
                    "base_rate": base, "ai_suggested_rate": ai_rate,
                    "owner_override": ov.get("pms_override"),
                    "target_sell_rate": ov.get("target_sell_rate"),
                    "min_rate": ov.get("min_rate"), "floor_rate": ov.get("floor_rate"),
                    "events": [e.get("name") for e in events],
                    "is_locked": bool(pms_lock),
                }
                prompt = (
                    f"You are a hotel revenue analyst. Explain in 3 short Turkish bullet points "
                    f"why the AI Sentinel rate for {date} is £{ai_rate}. "
                    f"Be specific about which signals matter most (occupancy, pickup, compset, events, day-of-week). "
                    f"If owner overrode the rate, mention what they changed. "
                    f"Context (JSON): {json.dumps(ctx, ensure_ascii=False)}. "
                    f"Format: ONLY 3 bullets, Turkish, each starting with • and 1-2 sentences max."
                )
                chat = LlmChat(
                    api_key=api_key,
                    session_id=f"explain-{property_id}-{date}",
                    system_message="Sen bir otel gelir yöneticisi danışmanısın. Sadece kısa, net Türkçe yanıt ver."
                ).with_model("openai", "gpt-4o-mini")
                resp = await chat.send_message(UserMessage(text=prompt))
                narrative = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
            except Exception as e:
                logger.warning(f"explain LLM failed: {e}")

        return {
            "date": date,
            "ai_rate": ai_rate,
            "breakdown": breakdown,
            "context": {
                "day_of_week": dow,
                "lead_time_days": lead,
                "occupancy_pct": occ_pct,
                "in_house": in_house, "total_rooms": total_rooms,
                "pickup_24h": pickup_count,
                "compset_avg": comp_avg,
                "compset_min": comp_min,
                "compset_max": comp_max,
                "events": [e.get("name") for e in events],
                "owner_override": ov.get("pms_override"),
                "target_sell_rate": ov.get("target_sell_rate"),
                "is_locked": bool(pms_lock),
            },
            "narrative": narrative,
        }

    @router.get("/rates/winloss/{property_id}")
    async def winloss(property_id: str, lookback_days: int = 60,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """AI vs Owner performance scoreboard for past dates with owner overrides.
        Compares Owner's locked rate vs Sentinel AI rate at the time of submit and
        actual booking outcomes (occupancy + revenue captured)."""
        today = datetime.now(timezone.utc).date()
        start = (today - timedelta(days=int(lookback_days or 60))).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        # Find historical submits for past dates only
        submits = await db.rate_override_history.find(
            {"property_id": property_id if property_id != "all" else {"$exists": True},
             "action": "submit",
             "date": {"$gte": start, "$lte": end}},
            {"_id": 0}
        ).sort("created_at", -1).to_list(1000)

        # Dedupe to latest submit per date (most recent rate wins)
        latest_by_date: dict = {}
        for s in submits:
            if s["date"] not in latest_by_date:
                latest_by_date[s["date"]] = s

        prop_filter = {} if property_id == "all" else {"property_id": property_id}
        comparisons = []
        wins = 0
        losses = 0
        neutrals = 0
        revenue_owner = 0.0
        revenue_ai_counterfactual = 0.0
        biggest_win = None
        biggest_loss = None

        for ds, s in latest_by_date.items():
            owner_rate = float(s.get("new_rate") or 0)
            ai_rate = float(s.get("ai_rate_at_submit") or 0)
            if owner_rate <= 0 or ai_rate <= 0:
                continue
            # Actual bookings on this date
            bk_query = {"check_in": {"$lte": ds}, "check_out": {"$gt": ds},
                        "status": {"$in": ["confirmed", "checked_in", "checked_out"]}, **prop_filter}
            bookings_count = await db.bookings.count_documents(bk_query)
            # Total rooms for occupancy
            total_rooms = await db.rooms.count_documents(prop_filter) or 1
            occ_pct = round(min(100.0, bookings_count / total_rooms * 100), 1)

            # Revenue model:
            # actual: bookings × owner_rate
            # counterfactual: bookings × ai_rate (assume same demand — naive)
            actual_rev = bookings_count * owner_rate
            cf_rev = bookings_count * ai_rate
            delta_rev = actual_rev - cf_rev

            # Classification
            verdict = "neutral"
            if owner_rate > ai_rate:
                # Owner priced higher
                if bookings_count > 0:
                    verdict = "win"  # captured higher ADR with same bookings
                elif occ_pct == 0:
                    verdict = "loss"  # priced too high, 0 bookings
            elif owner_rate < ai_rate:
                # Owner priced lower
                if bookings_count > 0 and occ_pct >= 50:
                    verdict = "neutral"  # leaving money on table but full
                else:
                    verdict = "loss"  # priced lower without filling

            if verdict == "win":
                wins += 1
            elif verdict == "loss":
                losses += 1
            else:
                neutrals += 1

            revenue_owner += actual_rev
            revenue_ai_counterfactual += cf_rev

            entry = {
                "date": ds,
                "owner_rate": owner_rate,
                "ai_rate": ai_rate,
                "delta_per_night": round(owner_rate - ai_rate, 2),
                "bookings": bookings_count,
                "occupancy_pct": occ_pct,
                "actual_revenue": round(actual_rev, 2),
                "ai_counterfactual": round(cf_rev, 2),
                "revenue_delta": round(delta_rev, 2),
                "verdict": verdict,
                "submitted_by": s.get("by"),
                "submitted_at": s.get("created_at"),
            }
            comparisons.append(entry)

            if verdict == "win" and (biggest_win is None or delta_rev > biggest_win["revenue_delta"]):
                biggest_win = entry
            if verdict == "loss" and (biggest_loss is None or delta_rev < biggest_loss["revenue_delta"]):
                biggest_loss = entry

        comparisons.sort(key=lambda x: x["date"], reverse=True)
        total = wins + losses + neutrals
        return {
            "property_id": property_id,
            "lookback_days": lookback_days,
            "start_date": start,
            "end_date": end,
            "summary": {
                "total_overrides": total,
                "wins": wins,
                "losses": losses,
                "neutrals": neutrals,
                "win_rate_pct": round(wins / total * 100, 1) if total else 0,
                "revenue_owner": round(revenue_owner, 2),
                "revenue_ai_counterfactual": round(revenue_ai_counterfactual, 2),
                "revenue_lift": round(revenue_owner - revenue_ai_counterfactual, 2),
                "biggest_win": biggest_win,
                "biggest_loss": biggest_loss,
            },
            "comparisons": comparisons,
        }

    @router.get("/rates/grid/insights/{property_id}")
    async def insights(property_id: str, lookback_days: int = 90,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Pattern detection from override history: repeated wins/losses by day-of-week,
        consecutive minimum-rate days, anomaly streaks. Returns actionable recommendations."""
        today = datetime.now(timezone.utc).date()
        start = (today - timedelta(days=int(lookback_days or 90))).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")

        prop_filter = {} if property_id == "all" else {"property_id": property_id}

        # Historical submits
        submits = await db.rate_override_history.find(
            {**({"property_id": property_id} if property_id != "all" else {"property_id": {"$exists": True}}),
             "action": "submit",
             "date": {"$gte": start, "$lte": end}},
            {"_id": 0}
        ).to_list(2000)
        # Latest per date
        latest_by_date: dict = {}
        for s in submits:
            existing = latest_by_date.get(s["date"])
            if not existing or s.get("created_at", "") > existing.get("created_at", ""):
                latest_by_date[s["date"]] = s

        # Group by day-of-week with outcomes
        total_rooms = await db.rooms.count_documents(prop_filter) or 1
        DOW_NAMES_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        dow_buckets: dict = {i: [] for i in range(7)}

        for ds, s in latest_by_date.items():
            owner_rate = float(s.get("new_rate") or 0)
            ai_rate = float(s.get("ai_rate_at_submit") or 0)
            if owner_rate <= 0 or ai_rate <= 0:
                continue
            try:
                dt = datetime.strptime(ds, "%Y-%m-%d")
            except ValueError:
                continue
            bk_query = {"check_in": {"$lte": ds}, "check_out": {"$gt": ds},
                        "status": {"$in": ["confirmed", "checked_in", "checked_out"]}, **prop_filter}
            bookings = await db.bookings.count_documents(bk_query)
            occ_pct = round(min(100.0, bookings / total_rooms * 100), 1)
            dow_buckets[dt.weekday()].append({
                "date": ds, "owner": owner_rate, "ai": ai_rate,
                "bookings": bookings, "occ_pct": occ_pct,
                "delta_pct": round((owner_rate - ai_rate) / ai_rate * 100, 1) if ai_rate else 0,
            })

        insights_list = []

        for dow_idx, items in dow_buckets.items():
            if len(items) < 2:
                continue
            # Pattern 1: Repeated low-occupancy days when priced above AI (≥10% above)
            low_occ_high_price = [it for it in items
                                  if it["occ_pct"] < 30 and it["delta_pct"] >= 10]
            if len(low_occ_high_price) >= 2:
                avg_delta = round(sum(it["delta_pct"] for it in low_occ_high_price)
                                  / len(low_occ_high_price), 1)
                avg_owner = round(sum(it["owner"] for it in low_occ_high_price)
                                  / len(low_occ_high_price), 2)
                avg_ai = round(sum(it["ai"] for it in low_occ_high_price)
                               / len(low_occ_high_price), 2)
                avg_occ = round(sum(it["occ_pct"] for it in low_occ_high_price)
                                / len(low_occ_high_price), 1)
                insights_list.append({
                    "id": str(uuid.uuid4()),
                    "severity": "warning",
                    "type": "repeated_loss_pattern",
                    "dow": dow_idx,
                    "dow_name": DOW_NAMES_TR[dow_idx],
                    "message": (
                        f"Son {len(low_occ_high_price)} {DOW_NAMES_TR[dow_idx]} günü "
                        f"AI'dan ortalama %{avg_delta} yüksek (£{avg_owner} vs £{avg_ai}) "
                        f"fiyatladın ve doluluk sadece %{avg_occ} oldu. Sonraki "
                        f"{DOW_NAMES_TR[dow_idx]} için fiyatı AI'a yaklaştırmak doluluğu artırabilir."
                    ),
                    "recommendation": {
                        "action": "lower_to_ai",
                        "label": f"Sonraki 3 {DOW_NAMES_TR[dow_idx]} için AI fiyatına çek",
                        "dow": dow_idx,
                        "target_offset_pct": -10,
                    },
                    "evidence": low_occ_high_price[:5],
                })

            # Pattern 2: Repeated wins (owner > AI + good occupancy)
            consistent_wins = [it for it in items
                               if it["bookings"] > 0 and it["owner"] > it["ai"]
                               and it["occ_pct"] >= 30]
            if len(consistent_wins) >= 3:
                avg_delta = round(sum(it["delta_pct"] for it in consistent_wins)
                                  / len(consistent_wins), 1)
                avg_extra = round(sum((it["owner"] - it["ai"]) * it["bookings"]
                                      for it in consistent_wins), 2)
                insights_list.append({
                    "id": str(uuid.uuid4()),
                    "severity": "success",
                    "type": "consistent_win_pattern",
                    "dow": dow_idx,
                    "dow_name": DOW_NAMES_TR[dow_idx],
                    "message": (
                        f"{DOW_NAMES_TR[dow_idx]} günleri AI'dan %{avg_delta} yüksek "
                        f"fiyatlayıp {len(consistent_wins)} kez kazandın "
                        f"(toplam +£{avg_extra} ek gelir). Bu pattern devam edebilir."
                    ),
                    "recommendation": {
                        "action": "keep_strategy",
                        "label": f"Sonraki 3 {DOW_NAMES_TR[dow_idx]} için aynı strateji",
                        "dow": dow_idx,
                        "target_offset_pct": avg_delta,
                    },
                    "evidence": consistent_wins[:5],
                })

        # Pattern 3: Min-rate streak detection (last 7 days from owner_rate_overrides)
        recent_overrides = await db.owner_rate_overrides.find(
            {**prop_filter,
             "date": {"$gte": (today - timedelta(days=14)).strftime("%Y-%m-%d"),
                      "$lte": end}},
            {"_id": 0}
        ).to_list(50)
        min_streak = sum(
            1 for ov in recent_overrides
            if ov.get("live_pms_rate") and ov.get("min_rate")
            and float(ov["live_pms_rate"]) <= float(ov["min_rate"]) + 1
        )
        if min_streak >= 5:
            insights_list.append({
                "id": str(uuid.uuid4()),
                "severity": "info",
                "type": "min_rate_streak",
                "message": (
                    f"Son 14 gün içinde {min_streak} gün taban fiyata yapıştın. "
                    f"Pazar düşüşte mi yoksa min_rate çok mu yüksek? Kontrol et."
                ),
                "recommendation": {
                    "action": "review_min_rate",
                    "label": "Min Rate'i gözden geçir",
                },
            })

        # Sort by severity
        sev_order = {"warning": 0, "success": 1, "info": 2}
        insights_list.sort(key=lambda x: sev_order.get(x["severity"], 99))

        return {
            "property_id": property_id,
            "lookback_days": lookback_days,
            "insights": insights_list,
            "count": len(insights_list),
        }

    @router.post("/rates/grid/insights/apply")
    async def apply_insight(data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Apply an insight recommendation to the next N matching weekdays.
        Generates pending overrides — the owner still must Submit them."""
        property_id = data.get("property_id", "")
        rec = data.get("recommendation", {})
        dow = rec.get("dow")
        offset_pct = float(rec.get("target_offset_pct", 0))
        count = int(data.get("count", 3))
        if dow is None:
            raise HTTPException(400, "dow required")
        # Find next N dates matching this weekday
        today = datetime.now(timezone.utc).date()
        target_dates = []
        d = today + timedelta(days=1)
        while len(target_dates) < count:
            if d.weekday() == int(dow):
                target_dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
            if (d - today).days > 90:
                break
        # For each target date, compute target rate from current AI suggestion + offset
        prop_filter = {} if property_id == "all" else {"property_id": property_id}
        rate_plan = await db.rate_plans.find_one(prop_filter, {"_id": 0}) or {}
        base = float(rate_plan.get("base_rate") or 90)
        suggestions = []
        for ds in target_dates:
            ai = await _compute_ai_rate_for_date(db, property_id, ds)
            target_rate = round(ai * (1 + offset_pct / 100), 2)
            suggestions.append({"date": ds, "target_pms_override": target_rate,
                                "ai_rate": ai, "base_rate": base})
        return {"applied_count": 0, "suggested_dates": suggestions,
                "note": "Frontend should pre-fill these as pending — owner reviews before Submit."}

    return router


async def _compute_ai_rate_for_date(db, property_id: str, date: str) -> float:
    """Lightweight version of the AI heuristic — used at submit time to capture
    the rate Sentinel WOULD have suggested."""
    prop_filter = {} if property_id == "all" else {"property_id": property_id}
    rate_plan = await db.rate_plans.find_one(prop_filter, {"_id": 0}) or {}
    base = float(rate_plan.get("base_rate") or 90)
    bk_query = {"check_in": {"$lte": date}, "check_out": {"$gt": date},
                "status": {"$in": ["confirmed", "checked_in"]}, **prop_filter}
    in_house = await db.bookings.count_documents(bk_query)
    total_rooms = await db.rooms.count_documents(prop_filter) or 1
    occ_pct = round(min(100.0, in_house / total_rooms * 100), 1)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    pickup = await db.bookings.count_documents({**bk_query, "created_at": {"$gte": cutoff}})
    comp = await db.competitor_rates.find(
        {"check_in_date": date, **prop_filter}, {"_id": 0, "rate": 1, "price": 1, "hotel_role": 1}
    ).to_list(50)
    comp_prices = [float(c.get("rate") or c.get("price") or 0) for c in comp
                   if c.get("hotel_role") != "own" and (c.get("rate") or c.get("price"))]
    comp_avg = round(sum(comp_prices) / len(comp_prices), 2) if comp_prices else None
    anchor = comp_avg or base
    demand_score = min(100, occ_pct + pickup * 5)
    multiplier = 1.0 + (demand_score - 50) / 200
    return round(anchor * multiplier, 2)


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
