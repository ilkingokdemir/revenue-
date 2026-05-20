"""
Cancellation Insurance Offer (P1)
---------------------------------
Optional add-on offered at booking time. Guest pays a small fee (% of booking
or fixed). On cancellation within the policy window, the booking is fully
refunded (instead of the standard non-refundable / late-cancel fee).

Endpoints
---------
POST /cancel-insurance/config           Save price/window per property
GET  /cancel-insurance/{property_id}/config
POST /cancel-insurance/quote            Compute fee for a booking total
POST /cancel-insurance/attach           Attach to a booking (record purchase)
POST /cancel-insurance/{booking_id}/claim
GET  /cancel-insurance/{property_id}/policies
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_cancel_insurance_router(db, require_roles):
    router = APIRouter()

    @router.post("/cancel-insurance/config")
    async def upsert(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        if not property_id:
            raise HTTPException(400, "property_id required")
        record = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", True)),
            "fee_pct": float(data.get("fee_pct") or 4.0),         # 4% of booking total
            "fee_min": float(data.get("fee_min") or 5.0),
            "fee_max": float(data.get("fee_max") or 60.0),
            "claim_window_hours_before_ci": int(data.get("claim_window_hours_before_ci") or 24),
            "underwriter_label": data.get("underwriter_label", "BookingShield"),
            "updated_at": _now(),
        }
        await db.cancel_insurance_config.update_one({"property_id": property_id}, {"$set": record}, upsert=True)
        return {"ok": True, "config": record}

    @router.get("/cancel-insurance/{property_id}/config")
    async def get_cfg(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await db.cancel_insurance_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "property_id": property_id, "enabled": True, "fee_pct": 4.0,
            "fee_min": 5.0, "fee_max": 60.0, "claim_window_hours_before_ci": 24,
            "underwriter_label": "BookingShield",
        }

    @router.post("/cancel-insurance/quote")
    async def quote(data: Dict):
        property_id = (data.get("property_id") or "").strip()
        booking_total = float(data.get("booking_total") or 0)
        cfg = await db.cancel_insurance_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "fee_pct": 4.0, "fee_min": 5.0, "fee_max": 60.0,
        }
        fee = booking_total * float(cfg["fee_pct"]) / 100
        fee = max(float(cfg["fee_min"]), min(fee, float(cfg["fee_max"])))
        return {"fee": round(fee, 2), "currency": data.get("currency", "GBP"),
                 "booking_total": booking_total,
                 "underwriter_label": cfg.get("underwriter_label", "BookingShield"),
                 "claim_window_hours_before_ci": cfg.get("claim_window_hours_before_ci", 24)}

    @router.post("/cancel-insurance/attach")
    async def attach(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking_id = (data.get("booking_id") or "").strip()
        if not booking_id:
            raise HTTPException(400, "booking_id required")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        existing = await db.cancel_insurance_policies.find_one({"booking_id": booking_id}, {"_id": 0})
        if existing:
            raise HTTPException(409, "Policy already attached")
        cfg = await db.cancel_insurance_config.find_one({"property_id": booking.get("property_id", "")}, {"_id": 0}) or {}
        booking_total = float(booking.get("total_price") or 0)
        fee_pct = float(cfg.get("fee_pct") or 4.0)
        fee = max(float(cfg.get("fee_min") or 5),
                   min(booking_total * fee_pct / 100, float(cfg.get("fee_max") or 60)))
        policy = {
            "id": str(uuid.uuid4()),
            "policy_ref": f"INS-{uuid.uuid4().hex[:6].upper()}",
            "booking_id": booking_id,
            "property_id": booking.get("property_id", ""),
            "guest_name": booking.get("guest_name", ""),
            "guest_email": booking.get("guest_email", ""),
            "fee": round(fee, 2),
            "currency": booking.get("currency", "GBP"),
            "underwriter_label": cfg.get("underwriter_label", "BookingShield"),
            "claim_window_hours": int(cfg.get("claim_window_hours_before_ci") or 24),
            "status": "active",  # active | claimed | expired
            "purchased_at": _now(),
            "purchased_by": current_user.get("name", "Staff"),
        }
        await db.cancel_insurance_policies.insert_one(dict(policy))
        await db.folio_charges.insert_one({
            "id": str(uuid.uuid4()), "booking_id": booking_id, "category": "insurance",
            "description": f"Cancellation insurance · {policy['policy_ref']}",
            "amount": policy["fee"], "currency": policy["currency"],
            "posted_at": _now(), "posted_by": current_user.get("name", "Staff"),
        })
        return {"ok": True, "policy": policy}

    @router.post("/cancel-insurance/{booking_id}/claim")
    async def claim(booking_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        policy = await db.cancel_insurance_policies.find_one({"booking_id": booking_id}, {"_id": 0})
        if not policy:
            raise HTTPException(404, "No active policy")
        if policy["status"] != "active":
            raise HTTPException(400, f"Policy is {policy['status']}")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        # Ensure within window
        try:
            ci = datetime.fromisoformat((booking["check_in"] or "")[:10])
            ci = ci.replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            raise HTTPException(400, "Booking missing valid check_in")
        cutoff = ci - timedelta(hours=policy.get("claim_window_hours", 24))
        if datetime.now(timezone.utc) > cutoff:
            raise HTTPException(400, "Outside claim window")
        await db.cancel_insurance_policies.update_one(
            {"booking_id": booking_id},
            {"$set": {"status": "claimed", "claimed_at": _now(),
                       "claimed_by": current_user.get("name", "Staff")}},
        )
        await db.bookings.update_one({"id": booking_id}, {"$set": {"status": "cancelled", "cancellation_reason": "insurance_claim"}})
        return {"ok": True, "policy_ref": policy["policy_ref"], "refund_due": booking.get("total_price", 0)}

    @router.get("/cancel-insurance/{property_id}/policies")
    async def list_policies(property_id: str, days: int = 90, status: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "purchased_at": {"$gte": since}}
        if status:
            q["status"] = status
        rows = await db.cancel_insurance_policies.find(q, {"_id": 0}).sort("purchased_at", -1).to_list(500)
        revenue = round(sum(float(r.get("fee") or 0) for r in rows), 2)
        claimed = sum(1 for r in rows if r["status"] == "claimed")
        loss = round(sum(float(r.get("fee") or 0) for r in rows if r["status"] == "claimed"), 2)
        return {"items": rows, "count": len(rows), "fee_revenue": revenue,
                 "claimed": claimed, "claim_loss_estimate": loss}

    return router
