"""
Payroll Rate Matrix — cross-tab view of user × branch × pay-type × rate with
split-across-branches and active toggles. Stored on users.branch_payments.
Each user.branch_payments[<property_id>] = {
  payment_type: "hourly" | "daily",
  rate: number,
  split: bool,     # split the daily rate across branches worked that day
  active: bool,    # if false, this branch is excluded from payroll
}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def create_payroll_matrix_router(db, require_roles):
    router = APIRouter()

    # -------- LIST MATRIX --------
    @router.get("/payroll-matrix")
    async def list_matrix(q: str = "", role: str = "", property_id: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}) \
                                          .sort("name", 1).to_list(100)
        users = await db.users.find(
            {}, {"_id": 0, "password_hash": 0}
        ).sort("name", 1).to_list(500)

        if q:
            ql = q.lower()
            users = [u for u in users
                     if ql in (u.get("name") or "").lower()
                     or ql in (u.get("email") or "").lower()]
        if role:
            users = [u for u in users if u.get("role") == role]
        if property_id:
            users = [u for u in users if property_id in (u.get("property_access") or [])]

        # Calculate quick stats
        total_configured_cells = 0
        for u in users:
            bp = u.get("branch_payments") or {}
            total_configured_cells += sum(1 for v in bp.values() if v and float(v.get("rate") or 0) > 0)

        return {
            "properties": properties,
            "users": users,
            "total_users": len(users),
            "total_configured_cells": total_configured_cells,
            "total_possible_cells": len(users) * len(properties),
        }

    # -------- BULK UPDATE CELL --------
    @router.put("/payroll-matrix/{user_id}/{property_id}")
    async def update_cell(user_id: str, property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin"))):
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "branch_payments": 1})
        if not user:
            raise HTTPException(404, "User not found")

        bp = user.get("branch_payments") or {}
        existing = bp.get(property_id) or {}
        cell = {
            "payment_type": data.get("payment_type", existing.get("payment_type", "hourly")),
            "rate":         float(data.get("rate", existing.get("rate", 0)) or 0),
            "split":        bool(data.get("split", existing.get("split", False))),
            "active":       bool(data.get("active", existing.get("active", True))),
            "updated_at":   datetime.now(timezone.utc).isoformat(),
            "updated_by":   current_user.get("name", ""),
        }
        if cell["payment_type"] not in ("hourly", "daily"):
            raise HTTPException(400, "payment_type must be hourly or daily")
        if cell["rate"] < 0:
            raise HTTPException(400, "Rate cannot be negative")

        bp[property_id] = cell
        # If cell.rate is 0 AND not active, remove it entirely (cleans stale entries)
        if cell["rate"] == 0 and not cell["active"]:
            bp.pop(property_id, None)

        await db.users.update_one(
            {"id": user_id},
            {"$set": {"branch_payments": bp,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"ok": True, "cell": bp.get(property_id)}

    # -------- DELETE CELL --------
    @router.delete("/payroll-matrix/{user_id}/{property_id}")
    async def delete_cell(user_id: str, property_id: str,
                          current_user: dict = Depends(require_roles("admin"))):
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "branch_payments": 1})
        if not user:
            raise HTTPException(404, "User not found")
        bp = user.get("branch_payments") or {}
        if property_id not in bp:
            return {"ok": True}
        bp.pop(property_id, None)
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"branch_payments": bp,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"ok": True}

    return router
