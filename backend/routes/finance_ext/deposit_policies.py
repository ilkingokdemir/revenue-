"""
Deposit Policies
----------------
Rule-based deposit collection enforced on booking creation.
Hotels configure: "Booking.com bookings with lead_time < 7 days → 50% deposit within 24h non-refundable".

Collections:
- deposit_policies: {id, property_id, name, trigger:{channels[], lead_days_lte?, rate_plan_ids[]}, amount_type:percent|flat, amount_value, due_within_hours, non_refundable, active, priority}

Endpoints (all /api/deposit-policies/*):
- GET    /
- POST   /
- PUT    /{id}
- DELETE /{id}
- POST   /evaluate  → { property_id, channel, lead_days, rate_plan_id, total_price } → matched policy + required deposit
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from auth import require_perm


class DepositTrigger(BaseModel):
    channels: List[str] = Field(default_factory=list)        # empty = all
    lead_days_lte: Optional[int] = None                       # apply when lead time ≤ N
    rate_plan_ids: List[str] = Field(default_factory=list)   # empty = all
    min_rooms: Optional[int] = None                           # apply when rooms ≥ N (group rule)


class DepositPolicyIn(BaseModel):
    property_id: str = "default"
    name: str
    trigger: DepositTrigger = Field(default_factory=DepositTrigger)
    amount_type: str = "percent"        # percent | flat
    amount_value: float = 0             # 50 = 50% OR 100 = £100 flat
    due_within_hours: int = 24          # how long guest has to pay
    non_refundable: bool = False
    active: bool = True
    priority: int = 100                 # lower = higher priority (matches first)


class DepositEvaluateIn(BaseModel):
    property_id: str = "default"
    channel: Optional[str] = ""
    lead_days: int = 0
    rate_plan_id: Optional[str] = ""
    total_price: float = 0
    rooms: int = 1


def _match_policy(policy: dict, channel: str, lead_days: int, rate_plan_id: str, rooms: int = 1) -> bool:
    t = policy.get("trigger") or {}
    chans = t.get("channels") or []
    if chans and channel not in chans:
        return False
    lead_lte = t.get("lead_days_lte")
    if lead_lte is not None and lead_days > int(lead_lte):
        return False
    min_rooms = t.get("min_rooms")
    if min_rooms is not None and rooms < int(min_rooms):
        return False
    rps = t.get("rate_plan_ids") or []
    if rps and rate_plan_id not in rps:
        return False
    return True


def create_deposit_policies_router(db):
    router = APIRouter(prefix="/deposit-policies")

    @router.get("/")
    async def list_policies(
        property_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.deposit_policies.find(q, {"_id": 0}).sort("priority", 1).to_list(200)
        return rows

    @router.post("/")
    async def create_policy(
        data: DepositPolicyIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        doc = data.model_dump()
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["created_by"] = current_user.get("email", "")
        await db.deposit_policies.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/{policy_id}")
    async def update_policy(
        policy_id: str, data: DepositPolicyIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        update = data.model_dump()
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.deposit_policies.update_one({"id": policy_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Policy not found")
        return {"updated": True, "id": policy_id}

    @router.delete("/{policy_id}")
    async def delete_policy(
        policy_id: str,
        current_user: dict = Depends(require_perm("delete_bookings")),
    ):
        r = await db.deposit_policies.delete_one({"id": policy_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Policy not found")
        return {"deleted": True}

    @router.post("/evaluate")
    async def evaluate(
        data: DepositEvaluateIn,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """Given a booking context, return the matched deposit policy + required deposit amount."""
        q = {"active": True}
        if data.property_id and data.property_id != "all":
            q["property_id"] = data.property_id
        policies = await db.deposit_policies.find(q, {"_id": 0}).sort("priority", 1).to_list(200)

        matched = None
        for p in policies:
            if _match_policy(p, data.channel or "", int(data.lead_days or 0), data.rate_plan_id or "", int(data.rooms or 1)):
                matched = p
                break

        if not matched:
            return {"matched": False, "policy": None, "deposit_required": 0,
                    "due_within_hours": 0, "non_refundable": False}

        if matched.get("amount_type") == "flat":
            deposit = float(matched.get("amount_value", 0))
        else:
            deposit = round(float(data.total_price) * float(matched.get("amount_value", 0)) / 100, 2)
        return {
            "matched": True,
            "policy": {"id": matched["id"], "name": matched["name"]},
            "deposit_required": deposit,
            "due_within_hours": int(matched.get("due_within_hours", 24)),
            "non_refundable": bool(matched.get("non_refundable")),
        }

    return router
