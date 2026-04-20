"""
Inventory Allocations (Iter 164) — per-channel × room_type inventory policy.

Parity with SiteMinder / Cloudbeds / STAAH "pooled inventory" concepts:
  • pooled     → all channels share the full inventory bucket
  • dedicated  → a hard N-unit allocation reserved for this channel
  • capped     → soft cap (cannot sell more than N per day) but spillover pool
                  can absorb demand if this channel hasn't booked its cap
  • buffer     → optional N-unit safety buffer held back from this channel

The actual availability shown to a channel = total_inventory - sold_today - buffer,
then capped by allocation_cap for dedicated/capped modes.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as date_cls
from typing import Dict, List
import uuid


def create_inventory_allocations_router(db, require_roles):
    router = APIRouter()

    # ──────────────────────────────────────────────────────────────
    # ALLOCATION RULES
    # ──────────────────────────────────────────────────────────────
    @router.get("/inventory-allocations/{property_id}")
    async def list_rules(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        rules = await db.channel_allocations.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(500)
        # Enrich with channel + room names
        channels = await db.channel_configs.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(50)
        rooms = await db.room_types.find(
            {} if property_id == "all" else {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        return {
            "rules": rules,
            "channels": channels,
            "room_types": rooms,
        }

    @router.put("/inventory-allocations/{property_id}/upsert")
    async def upsert_rule(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        required = ["channel_id", "room_type_id", "mode"]
        for f in required:
            if not data.get(f):
                raise HTTPException(400, f"{f} required")
        if data["mode"] not in ("pooled", "dedicated", "capped"):
            raise HTTPException(400, "mode must be pooled|dedicated|capped")
        cap = int(data.get("allocation_cap") or 0)
        buffer = int(data.get("buffer") or 0)
        if data["mode"] in ("dedicated", "capped") and cap <= 0:
            raise HTTPException(400, "allocation_cap > 0 required for dedicated/capped")
        now = datetime.now(timezone.utc).isoformat()
        await db.channel_allocations.update_one(
            {"property_id": property_id,
             "channel_id": data["channel_id"],
             "room_type_id": data["room_type_id"]},
            {"$set": {
                "property_id": property_id,
                "channel_id": data["channel_id"],
                "room_type_id": data["room_type_id"],
                "mode": data["mode"],
                "allocation_cap": cap,
                "buffer": buffer,
                "spillover_priority": int(data.get("spillover_priority") or 10),
                "active": bool(data.get("active", True)),
                "updated_at": now,
                "updated_by": current_user.get("email", ""),
            },
             "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
            upsert=True,
        )
        return {"status": "ok"}

    @router.delete("/inventory-allocations/{rule_id}")
    async def delete_rule(rule_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.channel_allocations.delete_one({"id": rule_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    # ──────────────────────────────────────────────────────────────
    # DATE-LEVEL OVERRIDES — edit a single cell in the allocation grid
    # ──────────────────────────────────────────────────────────────
    @router.put("/inventory-allocations/{property_id}/cell")
    async def upsert_cell(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Body: {channel_id, room_type_id, date, allocation_cap}
        Upserts a date-level cap that overrides the rule-level cap for that
        (channel, room, date) cell. Pass allocation_cap=null to clear."""
        for f in ("channel_id", "room_type_id", "date"):
            if not data.get(f):
                raise HTTPException(400, f"{f} required")
        cap = data.get("allocation_cap")
        key = {"property_id": property_id,
               "channel_id": data["channel_id"],
               "room_type_id": data["room_type_id"],
               "date": data["date"]}
        if cap is None or (isinstance(cap, str) and cap.strip() == ""):
            res = await db.channel_allocation_overrides.delete_one(key)
            return {"status": "cleared", "deleted": res.deleted_count}
        try:
            cap_int = int(cap)
        except (TypeError, ValueError):
            raise HTTPException(400, "allocation_cap must be an integer or null")
        if cap_int < 0:
            raise HTTPException(400, "allocation_cap must be >= 0")
        now = datetime.now(timezone.utc).isoformat()
        await db.channel_allocation_overrides.update_one(
            key,
            {"$set": {**key, "allocation_cap": cap_int, "updated_at": now,
                      "updated_by": current_user.get("email", "")},
             "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
            upsert=True,
        )
        return {"status": "ok", "allocation_cap": cap_int}

    # ──────────────────────────────────────────────────────────────
    # AVAILABILITY CALENDAR — compute per (date, channel, room) what
    # the channel manager WOULD push as available
    # ──────────────────────────────────────────────────────────────
    @router.get("/inventory-allocations/{property_id}/calendar")
    async def availability_calendar(
        property_id: str,
        from_date: str = "",
        to_date: str = "",
        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return a grid: rows = (room_type, channel), cols = dates,
        value = computed available units for that channel on that date."""
        today = date_cls.today()
        d_from = date_cls.fromisoformat(from_date) if from_date else today
        d_to = date_cls.fromisoformat(to_date) if to_date else (today + timedelta(days=14))
        if (d_to - d_from).days > 90:
            raise HTTPException(400, "Range max 90 days")

        rooms = await db.room_types.find(
            {} if property_id == "all" else {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        channels = await db.channel_configs.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(50)
        rules = await db.channel_allocations.find(
            {"property_id": property_id, "active": True}, {"_id": 0}
        ).to_list(500)
        rule_idx: Dict[str, Dict] = {}
        for r in rules:
            rule_idx[f"{r['channel_id']}|{r['room_type_id']}"] = r

        # Date-level overrides (channel × room × date → cap)
        overrides_rows = await db.channel_allocation_overrides.find(
            {"property_id": property_id,
             "date": {"$gte": d_from.isoformat(), "$lte": d_to.isoformat()}},
            {"_id": 0}
        ).to_list(5000)
        override_idx: Dict[str, int] = {}
        for o in overrides_rows:
            override_idx[f"{o['channel_id']}|{o['room_type_id']}|{o['date']}"] = o["allocation_cap"]

        # Sold per (room, channel, date) from bookings
        q = {"property_id": property_id}
        bookings = await db.bookings.find(q, {
            "_id": 0, "check_in": 1, "check_out": 1,
            "room_type_id": 1, "channel": 1, "room_id": 1,
        }).to_list(5000)
        sold: Dict[str, int] = {}  # key = f"{room_id}|{channel}|{YYYY-MM-DD}"
        sold_pooled: Dict[str, int] = {}  # key = f"{room_id}|{YYYY-MM-DD}"
        for b in bookings:
            try:
                ci = date_cls.fromisoformat((b.get("check_in") or "")[:10])
                co = date_cls.fromisoformat((b.get("check_out") or "")[:10])
            except Exception:
                continue
            chan = b.get("channel") or "direct"
            rt = b.get("room_type_id") or ""
            cur = ci
            while cur < co:
                if d_from <= cur <= d_to:
                    key = f"{rt}|{chan}|{cur.isoformat()}"
                    sold[key] = sold.get(key, 0) + 1
                    pool_key = f"{rt}|{cur.isoformat()}"
                    sold_pooled[pool_key] = sold_pooled.get(pool_key, 0) + 1
                cur = cur + timedelta(days=1)

        # Room inventory totals (count of rooms per room_type)
        rooms_inventory = {}
        for rt in rooms:
            cnt = await db.rooms.count_documents({"room_type_id": rt["id"]})
            rooms_inventory[rt["id"]] = cnt or rt.get("total_inventory") or 1

        # Build date list
        dates: List[str] = []
        cur = d_from
        while cur <= d_to:
            dates.append(cur.isoformat())
            cur = cur + timedelta(days=1)

        # Build grid
        grid = []
        for rt in rooms:
            total_inv = rooms_inventory.get(rt["id"], 1)
            for ch in channels:
                rule = rule_idx.get(f"{ch['channel_id']}|{rt['id']}")
                mode = rule.get("mode") if rule else "pooled"
                cap = rule.get("allocation_cap", 0) if rule else 0
                buf = rule.get("buffer", 0) if rule else 0
                row_cells = []
                for d in dates:
                    sold_here = sold.get(f"{rt['id']}|{ch['channel_id']}|{d}", 0)
                    sold_all = sold_pooled.get(f"{rt['id']}|{d}", 0)
                    override_key = f"{ch['channel_id']}|{rt['id']}|{d}"
                    cell_cap = override_idx.get(override_key, cap)
                    edited = override_key in override_idx
                    if mode == "dedicated":
                        avail = max(0, cell_cap - sold_here - buf)
                    elif mode == "capped":
                        avail = max(0, min(cell_cap - sold_here, total_inv - sold_all) - buf)
                    else:  # pooled — override means "cap this channel on this date"
                        if edited:
                            avail = max(0, min(cell_cap - sold_here, total_inv - sold_all) - buf)
                        else:
                            avail = max(0, total_inv - sold_all - buf)
                    row_cells.append({
                        "date": d, "available": avail,
                        "sold_on_channel": sold_here,
                        "sold_all": sold_all,
                        "total_inventory": total_inv,
                        "effective_cap": cell_cap if (edited or mode in ("dedicated", "capped")) else total_inv,
                        "edited": edited,
                    })
                grid.append({
                    "room_type_id": rt["id"],
                    "room_type_name": rt["name"],
                    "channel_id": ch["channel_id"],
                    "channel_name": ch["name"],
                    "mode": mode,
                    "allocation_cap": cap,
                    "buffer": buf,
                    "total_inventory": total_inv,
                    "cells": row_cells,
                })
        return {"dates": dates, "grid": grid}

    return router
