"""
Staff Tip Pool + Clock-In/Out
-----------------------------
Twin operational tools: staff time tracking and shift-based tip distribution.

Tip pool model: cumulative tips for a shift are distributed across staff who
clocked in for that shift, weighted by hours worked + role multiplier
(e.g. server 1.0, busser 0.6, kitchen 0.4).

Endpoints:
  POST /api/staff/clock-in                                — start shift
  POST /api/staff/clock-out/{entry_id}                    — end shift
  GET  /api/staff/{property_id}/active                    — currently clocked-in
  GET  /api/staff/{property_id}/shifts?from&to            — shift entries

  POST /api/tip-pool/{property_id}/contribute             — record a tip
  POST /api/tip-pool/{property_id}/distribute             — close pool & split
  GET  /api/tip-pool/{property_id}/summary?date=          — current pool + last distribution
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


ROLE_WEIGHTS = {
    "server":     1.0,
    "bartender":  1.0,
    "host":       0.8,
    "busser":     0.6,
    "runner":     0.5,
    "kitchen":    0.4,
    "manager":    0.3,
    "other":      0.5,
}


def create_staff_ops_router(db, require_roles):
    router = APIRouter()

    @router.post("/staff/clock-in")
    async def clock_in(data: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb", "spa", "housekeeping"))):
        property_id = (data.get("property_id") or "").strip()
        staff_name = (data.get("staff_name") or current_user.get("name", "")).strip()
        role = (data.get("role") or "server").strip()
        if not property_id or not staff_name:
            raise HTTPException(400, "property_id and staff_name required")

        # Prevent double clock-in
        active = await db.shift_entries.find_one({
            "property_id": property_id, "staff_name": staff_name,
            "clock_out": ""
        }, {"_id": 0})
        if active:
            return {"ok": True, "entry": active, "warning": "Already clocked in"}

        entry = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "staff_name": staff_name,
            "role": role,
            "role_weight": ROLE_WEIGHTS.get(role, 0.5),
            "clock_in": datetime.now(timezone.utc).isoformat(),
            "clock_out": "",
            "duration_min": 0,
            "shift_date": date.today().isoformat(),
        }
        await db.shift_entries.insert_one(dict(entry))
        entry.pop("_id", None)
        return {"ok": True, "entry": entry}

    @router.post("/staff/clock-out/{entry_id}")
    async def clock_out(entry_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb", "spa", "housekeeping"))):
        entry = await db.shift_entries.find_one({"id": entry_id}, {"_id": 0})
        if not entry:
            raise HTTPException(404, "Entry not found")
        if entry.get("clock_out"):
            return {"ok": True, "entry": entry, "warning": "Already clocked out"}
        clock_out_dt = datetime.now(timezone.utc)
        clock_in_dt = datetime.fromisoformat(entry["clock_in"])
        dur_min = round((clock_out_dt - clock_in_dt).total_seconds() / 60, 1)
        await db.shift_entries.update_one({"id": entry_id}, {"$set": {
            "clock_out": clock_out_dt.isoformat(),
            "duration_min": dur_min,
        }})
        doc = await db.shift_entries.find_one({"id": entry_id}, {"_id": 0})
        return {"ok": True, "entry": doc}

    @router.get("/staff/{property_id}/active")
    async def active(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb", "spa", "housekeeping"))):
        rows = await db.shift_entries.find(
            {"property_id": property_id, "clock_out": ""}, {"_id": 0}
        ).sort("clock_in", 1).to_list(200)
        return rows

    @router.get("/staff/{property_id}/shifts")
    async def shifts(property_id: str, days: int = 7,
                      current_user: dict = Depends(require_roles("admin", "manager", "fnb"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.shift_entries.find(
            {"property_id": property_id, "clock_in": {"$gte": since}}, {"_id": 0}
        ).sort("clock_in", -1).to_list(500)
        return rows

    # --- Tip Pool ---

    @router.post("/tip-pool/{property_id}/contribute")
    async def contribute(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        amount = float(data.get("amount") or 0)
        if amount <= 0:
            raise HTTPException(400, "amount > 0 required")
        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "amount": amount,
            "currency": data.get("currency", "GBP"),
            "source": data.get("source", "card"),  # card | cash | service_charge
            "shift_date": data.get("shift_date", date.today().isoformat()),
            "outlet": data.get("outlet", ""),
            "note": data.get("note", ""),
            "distributed": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", "Staff"),
        }
        await db.tip_contributions.insert_one(dict(record))
        record.pop("_id", None)
        return {"ok": True, "contribution": record}

    @router.post("/tip-pool/{property_id}/distribute")
    async def distribute(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        shift_date = (data.get("shift_date") or date.today().isoformat())
        # Sum un-distributed contributions for the date
        contribs = await db.tip_contributions.find(
            {"property_id": property_id, "shift_date": shift_date, "distributed": False},
            {"_id": 0},
        ).to_list(500)
        if not contribs:
            return {"ok": False, "reason": "no contributions to distribute"}
        pool_total = round(sum(c["amount"] for c in contribs), 2)
        currency = contribs[0].get("currency", "GBP")

        # Find shift entries that were active that day
        day_start = shift_date + "T00:00:00"
        day_end   = shift_date + "T23:59:59"
        shifts = await db.shift_entries.find(
            {"property_id": property_id, "shift_date": shift_date,
             "clock_in": {"$gte": day_start, "$lte": day_end}},
            {"_id": 0},
        ).to_list(200)
        if not shifts:
            return {"ok": False, "reason": "no shifts for date"}

        # Compute weighted shares
        total_weight = 0.0
        for s in shifts:
            hours = max(0.5, (s.get("duration_min") or 0) / 60)
            s["_weight"] = hours * ROLE_WEIGHTS.get(s.get("role", "other"), 0.5)
            total_weight += s["_weight"]
        if total_weight <= 0:
            return {"ok": False, "reason": "no weighted shifts"}

        allocations = []
        running = 0.0
        for i, s in enumerate(shifts):
            share = pool_total * (s["_weight"] / total_weight)
            share_rounded = round(share, 2)
            running += share_rounded
            # Final entry gets rounding correction
            if i == len(shifts) - 1:
                share_rounded += round(pool_total - running, 2)
            allocations.append({
                "staff_name": s["staff_name"],
                "role": s["role"],
                "hours": round((s.get("duration_min") or 0) / 60, 2),
                "weight": round(s["_weight"], 2),
                "share": round(share_rounded, 2),
            })

        run = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "shift_date": shift_date,
            "pool_total": pool_total,
            "currency": currency,
            "contribution_ids": [c["id"] for c in contribs],
            "allocations": allocations,
            "distributed_at": datetime.now(timezone.utc).isoformat(),
            "distributed_by": current_user.get("name", "Staff"),
        }
        await db.tip_distributions.insert_one(dict(run))
        run.pop("_id", None)
        # Mark contributions as distributed
        await db.tip_contributions.update_many(
            {"id": {"$in": [c["id"] for c in contribs]}},
            {"$set": {"distributed": True, "distribution_id": run["id"]}}
        )
        return {"ok": True, "distribution": run}

    @router.get("/tip-pool/{property_id}/summary")
    async def summary(property_id: str, shift_date: Optional[str] = None,
                       current_user: dict = Depends(require_roles("admin", "manager", "fnb", "receptionist"))):
        sd = shift_date or date.today().isoformat()
        contribs = await db.tip_contributions.find(
            {"property_id": property_id, "shift_date": sd}, {"_id": 0}
        ).to_list(500)
        pending = [c for c in contribs if not c.get("distributed")]
        pool = round(sum(c["amount"] for c in pending), 2)
        last_dist = await db.tip_distributions.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("distributed_at", -1).to_list(5)
        return {
            "shift_date": sd,
            "pending_pool_total": pool,
            "pending_contributions": pending,
            "currency": (pending[0].get("currency") if pending else "GBP"),
            "recent_distributions": last_dist,
            "role_weights": ROLE_WEIGHTS,
        }

    return router
