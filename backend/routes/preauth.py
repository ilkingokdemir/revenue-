"""
Pre-Authorization Hold (P0 #11)
-------------------------------
Lightweight ledger for credit-card pre-auth holds taken at check-in.

Real card capture is intentionally *not* triggered here — that requires a live
Stripe / payment-terminal session per booking. Instead this is the operations
ledger that:

  * Records the authorised amount, expiry (typical 7-day window)
  * Tracks state: authorized → captured | released | expired
  * Is the source of truth surfaced on the front desk so staff don't take a
    second hold by mistake, and incident damages can be captured against it.

Endpoints
---------
POST   /preauth/holds                      Create / replace a hold for a booking
GET    /preauth/{property_id}/holds        List holds (filter by status / day window)
POST   /preauth/holds/{hold_id}/capture    Capture (full or partial) — closes hold
POST   /preauth/holds/{hold_id}/release    Release the hold (no charge)
POST   /preauth/holds/expire-due           Cron-able sweeper — flips expired holds
GET    /preauth/{property_id}/summary      KPI snapshot
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_preauth_router(db, require_roles):
    router = APIRouter()

    @router.post("/preauth/holds")
    async def create_hold(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking_id = (data.get("booking_id") or "").strip()
        property_id = (data.get("property_id") or "").strip()
        amount = float(data.get("amount") or 0)
        if not booking_id or not property_id or amount <= 0:
            raise HTTPException(400, "booking_id, property_id, amount required")

        hold_days = int(data.get("hold_days") or 7)
        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "booking_id": booking_id,
            "guest_name": data.get("guest_name", ""),
            "room_number": data.get("room_number", ""),
            "amount": round(amount, 2),
            "currency": data.get("currency", "GBP"),
            "card_brand": data.get("card_brand", "visa"),
            "card_last4": data.get("card_last4", "0000"),
            "auth_code": data.get("auth_code", f"AUTH-{uuid.uuid4().hex[:6].upper()}"),
            "reason": data.get("reason", "incidentals"),  # incidentals | damage | extra_services
            "status": "authorized",
            "authorized_at": _now(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=hold_days)).isoformat(),
            "captured_amount": 0.0,
            "captured_at": "",
            "released_at": "",
            "notes": data.get("notes", ""),
            "created_by": current_user.get("name", "Staff"),
        }
        # Mark any prior open hold for this booking as superseded
        await db.preauth_holds.update_many(
            {"booking_id": booking_id, "status": "authorized"},
            {"$set": {"status": "released", "released_at": _now(), "notes_release": "superseded"}}
        )
        await db.preauth_holds.insert_one(dict(record))
        record.pop("_id", None)
        return {"ok": True, "hold": record}

    @router.get("/preauth/{property_id}/holds")
    async def list_holds(property_id: str, status: str = "", days: int = 30,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "authorized_at": {"$gte": since}}
        if status:
            q["status"] = status
        rows = await db.preauth_holds.find(q, {"_id": 0}).sort("authorized_at", -1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/preauth/holds/{hold_id}/capture")
    async def capture_hold(hold_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        hold = await db.preauth_holds.find_one({"id": hold_id}, {"_id": 0})
        if not hold:
            raise HTTPException(404, "Hold not found")
        if hold["status"] != "authorized":
            raise HTTPException(400, f"Cannot capture a hold in '{hold['status']}' state")
        amount = float(data.get("amount") or hold["amount"])
        if amount <= 0 or amount > hold["amount"]:
            raise HTTPException(400, f"Capture amount must be 0 < amt <= {hold['amount']}")
        await db.preauth_holds.update_one(
            {"id": hold_id},
            {"$set": {
                "status": "captured",
                "captured_amount": round(amount, 2),
                "captured_at": _now(),
                "capture_reason": data.get("reason", "damage"),
                "captured_by": current_user.get("name", "Staff"),
            }}
        )
        return {"ok": True, "captured": amount, "hold_id": hold_id}

    @router.post("/preauth/holds/{hold_id}/release")
    async def release_hold(hold_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        hold = await db.preauth_holds.find_one({"id": hold_id}, {"_id": 0})
        if not hold:
            raise HTTPException(404, "Hold not found")
        if hold["status"] != "authorized":
            raise HTTPException(400, f"Cannot release a hold in '{hold['status']}' state")
        await db.preauth_holds.update_one(
            {"id": hold_id},
            {"$set": {"status": "released", "released_at": _now(),
                      "released_by": current_user.get("name", "Staff")}}
        )
        return {"ok": True, "hold_id": hold_id}

    @router.post("/preauth/holds/expire-due")
    async def expire_due():
        """Cron-able. Flips expired authorized holds to 'expired' state."""
        now_iso = _now()
        result = await db.preauth_holds.update_many(
            {"status": "authorized", "expires_at": {"$lt": now_iso}},
            {"$set": {"status": "expired", "expired_at": now_iso}}
        )
        return {"ok": True, "expired": result.modified_count}

    @router.get("/preauth/{property_id}/summary")
    async def summary(property_id: str, days: int = 30,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.preauth_holds.find({"property_id": property_id, "authorized_at": {"$gte": since}}, {"_id": 0}).to_list(2000)
        by_status = {"authorized": 0, "captured": 0, "released": 0, "expired": 0}
        total_held = 0.0
        total_captured = 0.0
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
            if r["status"] == "authorized":
                total_held += float(r.get("amount") or 0)
            if r["status"] == "captured":
                total_captured += float(r.get("captured_amount") or 0)
        return {
            "window_days": days,
            "count": len(rows),
            "by_status": by_status,
            "total_currently_held": round(total_held, 2),
            "total_captured": round(total_captured, 2),
        }

    return router
