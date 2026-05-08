"""
Door-Lock Audit Log + Owner Portal + Direct Widget Savings Banner
-----------------------------------------------------------------
Three small endpoints bundled.

1. DOOR-LOCK AUDIT — every keycard/PIN/mobile-key event (from manual entry or
   external lock provider webhook) is recorded with timestamp, room, who, by
   which method. Exposed as a filterable audit log for security ops.

2. OWNER PORTAL — for serviced-apartment landlords. Each owner sees their
   units, occupancy, gross revenue, management fee deducted, net payout.

3. DIRECT WIDGET SAVINGS BANNER — public endpoint the booking widget hits to
   render a "You save X% vs Booking.com" message under the price.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


def create_extras_v2_router(db, require_roles):
    router = APIRouter()

    # ------------------------- Door-lock audit -------------------------

    @router.post("/door-locks/log")
    async def log_event(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping"))):
        property_id = data.get("property_id", "")
        room_number = (data.get("room_number") or "").strip()
        if not property_id or not room_number:
            raise HTTPException(400, "property_id + room_number required")
        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "room_number": room_number,
            "method": data.get("method", "card"),     # card | pin | mobile_key | master | maintenance | failed_attempt
            "actor_role": data.get("actor_role", "guest"),  # guest | staff | maintenance | unknown
            "actor_name": data.get("actor_name", ""),
            "booking_id": data.get("booking_id", ""),
            "lock_id": data.get("lock_id", ""),
            "result": data.get("result", "success"),  # success | denied | error
            "device_info": data.get("device_info", ""),
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "logged_by": current_user.get("name", "Staff"),
        }
        await db.door_lock_log.insert_one(dict(record))
        record.pop("_id", None)
        return {"ok": True, "event": record}

    @router.get("/door-locks/{property_id}/log")
    async def get_log(property_id: str, days: int = 7,
                       room_number: str = "", method: str = "", result: str = "",
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "logged_at": {"$gte": since}}
        if room_number: q["room_number"] = room_number
        if method:      q["method"] = method
        if result:      q["result"] = result
        rows = await db.door_lock_log.find(q, {"_id": 0}).sort("logged_at", -1).to_list(500)
        # Stats
        denied = sum(1 for r in rows if r.get("result") == "denied")
        master_uses = sum(1 for r in rows if r.get("method") == "master")
        return {
            "items": rows, "count": len(rows),
            "denied_count": denied,
            "master_key_uses": master_uses,
        }

    # ------------------------- Owner Portal -------------------------

    @router.get("/owner-portal/{owner_id}/properties")
    async def owner_properties(owner_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager", "owner"))):
        # Owners can be linked either via property.owner_ids array, or property.owner_id
        properties = await db.properties.find(
            {"$or": [{"owner_ids": owner_id}, {"owner_id": owner_id}]}, {"_id": 0}
        ).to_list(50)
        return {"owner_id": owner_id, "properties": properties}

    @router.get("/owner-portal/{owner_id}/summary")
    async def owner_summary(owner_id: str, days: int = 30,
                              current_user: dict = Depends(require_roles("admin", "manager", "owner"))):
        properties = await db.properties.find(
            {"$or": [{"owner_ids": owner_id}, {"owner_id": owner_id}]}, {"_id": 0}
        ).to_list(50)
        if not properties:
            return {"owner_id": owner_id, "properties": [], "totals": {}}
        prop_ids = [p["id"] for p in properties]
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        bookings = await db.bookings.find(
            {"property_id": {"$in": prop_ids}, "created_at": {"$gte": since},
             "status": {"$nin": ["cancelled", "no_show"]}}, {"_id": 0}
        ).to_list(5000)

        per_prop: Dict[str, dict] = {}
        for p in properties:
            mgmt_pct = float(p.get("management_fee_pct") or 20)
            per_prop[p["id"]] = {
                "property_id": p["id"], "name": p.get("name", p["id"]),
                "currency": p.get("currency", "GBP"),
                "management_fee_pct": mgmt_pct,
                "bookings": 0, "gross": 0.0, "fees_deducted": 0.0, "net_payout": 0.0,
                "occupied_nights": 0,
            }
        for b in bookings:
            row = per_prop.get(b["property_id"])
            if not row:
                continue
            gross = float(b.get("total_price") or 0)
            row["bookings"] += 1
            row["gross"] += gross
            row["occupied_nights"] += int(b.get("nights") or 0)
            row["fees_deducted"] += gross * row["management_fee_pct"] / 100
            row["net_payout"] += gross - (gross * row["management_fee_pct"] / 100)
        items = []
        for r in per_prop.values():
            r["gross"] = round(r["gross"], 2)
            r["fees_deducted"] = round(r["fees_deducted"], 2)
            r["net_payout"] = round(r["net_payout"], 2)
            items.append(r)
        items.sort(key=lambda x: x["net_payout"], reverse=True)
        totals = {
            "gross": round(sum(i["gross"] for i in items), 2),
            "fees_deducted": round(sum(i["fees_deducted"] for i in items), 2),
            "net_payout": round(sum(i["net_payout"] for i in items), 2),
            "bookings": sum(i["bookings"] for i in items),
            "occupied_nights": sum(i["occupied_nights"] for i in items),
        }
        return {"owner_id": owner_id, "window_days": days, "properties": items, "totals": totals}

    # ------------------------- Direct widget savings banner -------------------------

    @router.get("/widget/savings-banner")
    async def savings_banner(property_id: str, total: float = 0.0):
        """PUBLIC. Returns banner copy + savings amount based on parity defender + insurance config."""
        # 1) Parity-derived savings
        snap = await db.parity_analysis.find_one(
            {"property_id": property_id}, {"_id": 0}, sort=[("captured_at", -1)]
        ) or {}
        ota_rates = snap.get("ota_rates") or snap.get("competitor_rates") or []
        if ota_rates:
            min_ota = min(float(r.get("rate") or 0) for r in ota_rates if r.get("rate"))
        else:
            min_ota = 0
        cfg = await db.parity_defender_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        savings_amount = 0.0
        savings_pct = 0
        if min_ota > 0 and total > 0:
            savings_amount = round(min_ota - total, 2)
            savings_pct = round((min_ota - total) / min_ota * 100, 1) if min_ota else 0
        elif total > 0:
            # Fall back to undercut config (e.g. 5%) — promise direct is cheaper.
            pct = float(cfg.get("undercut_pct") or 5.0)
            savings_pct = pct
            savings_amount = round(total * pct / 100, 2)

        message = ""
        if savings_pct > 0:
            message = f"You save {savings_pct}% vs Booking.com when you book direct"
        return {
            "show": savings_pct > 0 and bool(cfg.get("show_savings_badge", True)),
            "savings_pct": savings_pct,
            "savings_amount": savings_amount,
            "message": message,
            "lowest_ota": min_ota,
            "captured_at": snap.get("captured_at", ""),
        }

    return router
