"""
Damage Protection — Guesty Shield paritesi.
Depozito yerine gecelik küçük ücretle hasar teminatı: fon havuzu + hasar talebi yönetimi.

Collections:
- damage_protection_config { property_id, enabled, fee_per_night, coverage_limit, currency }
- damage_claims { id, property_id, booking_id, guest_name, description, amount,
                  approved_amount, status: open|under_review|approved|denied|settled,
                  resolution_note, created_at, updated_at }

Endpoints (/api/damage-protection/*):
- GET/PUT /config/{property_id}
- GET     /stats/{property_id}   (90 günlük tahmini prim + talep toplamları + net havuz)
- POST    /claims                 GET /claims/{property_id}    PUT /claims/{claim_id}
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_perm

VALID_STATUSES = ["open", "under_review", "approved", "denied", "settled"]


class ConfigIn(BaseModel):
    enabled: bool = True
    fee_per_night: float = 3.0
    coverage_limit: float = 5000.0
    currency: str = "GBP"


class ClaimIn(BaseModel):
    property_id: str
    booking_id: Optional[str] = ""
    guest_name: str
    description: str
    amount: float


class ClaimUpdate(BaseModel):
    status: str
    approved_amount: Optional[float] = None
    resolution_note: Optional[str] = ""


def create_damage_protection_router(db):
    router = APIRouter(prefix="/damage-protection")

    @router.get("/config/{property_id}")
    async def get_config(property_id: str,
                         current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        doc = await db.damage_protection_config.find_one({"property_id": property_id}, {"_id": 0})
        return doc or {"property_id": property_id, "enabled": False, "fee_per_night": 3.0,
                       "coverage_limit": 5000.0, "currency": "GBP", "is_default": True}

    @router.put("/config/{property_id}")
    async def save_config(property_id: str, body: ConfigIn,
                          current_user: dict = Depends(require_perm("edit_bookings"))):
        if body.fee_per_night < 0 or body.coverage_limit < 0:
            raise HTTPException(400, "Values must be >= 0")
        await db.damage_protection_config.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, **body.model_dump(),
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("email", "")}},
            upsert=True)
        return {"ok": True}

    @router.get("/stats/{property_id}")
    async def stats(property_id: str,
                    current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        cfg = await db.damage_protection_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        fee = float(cfg.get("fee_per_night", 3.0) or 0)
        since = (datetime.now(timezone.utc).date() - timedelta(days=90)).isoformat()
        nights = 0
        async for b in db.bookings.find(
                {"property_id": property_id, "status": {"$ne": "cancelled"},
                 "check_in": {"$gte": since}},
                {"_id": 0, "check_in": 1, "check_out": 1, "rooms": 1}):
            try:
                d = (datetime.strptime(b["check_out"][:10], "%Y-%m-%d")
                     - datetime.strptime(b["check_in"][:10], "%Y-%m-%d")).days
                nights += max(d, 0) * int(b.get("rooms", 1) or 1)
            except (ValueError, KeyError, TypeError):
                continue
        claims = await db.damage_claims.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        paid = sum(float(c.get("approved_amount") or 0) for c in claims if c.get("status") == "settled")
        pending = sum(float(c.get("amount") or 0) for c in claims if c.get("status") in ("open", "under_review"))
        collected = round(nights * fee, 2)
        return {
            "enabled": bool(cfg.get("enabled")), "fee_per_night": fee,
            "coverage_limit": float(cfg.get("coverage_limit", 5000.0) or 0),
            "currency": cfg.get("currency", "GBP"),
            "covered_nights_90d": nights, "estimated_collected_90d": collected,
            "claims_total": len(claims),
            "claims_open": sum(1 for c in claims if c.get("status") in ("open", "under_review")),
            "claims_paid_amount": round(paid, 2), "claims_pending_amount": round(pending, 2),
            "net_pool_90d": round(collected - paid, 2),
        }

    @router.post("/attach/{booking_id}")
    async def attach_waiver(booking_id: str,
                            current_user: dict = Depends(require_perm("edit_bookings"))):
        """Ön büro: rezervasyona tek tıkla hasar koruması ekle (check-in upsell)."""
        booking = await db.bookings.find_one({"id": booking_id})
        if not booking:
            raise HTTPException(404, "Booking not found")
        if booking.get("damage_waiver"):
            raise HTTPException(400, "Bu rezervasyonda hasar koruması zaten var")
        cfg = await db.damage_protection_config.find_one(
            {"property_id": booking.get("property_id"), "enabled": True}, {"_id": 0})
        if not cfg:
            raise HTTPException(400, "Hasar koruması bu tesiste aktif değil")
        try:
            nights = max((datetime.strptime(booking["check_out"][:10], "%Y-%m-%d")
                          - datetime.strptime(booking["check_in"][:10], "%Y-%m-%d")).days, 1)
        except (ValueError, KeyError, TypeError):
            nights = 1
        fee = round(float(cfg.get("fee_per_night", 0) or 0) * nights * int(booking.get("rooms", 1) or 1), 2)
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"damage_waiver": True, "damage_waiver_fee": fee,
                      "damage_waiver_added_by": current_user.get("email", "")},
             "$inc": {"total_price": fee}})
        return {"ok": True, "fee": fee, "nights": nights,
                "currency": cfg.get("currency", "GBP"),
                "new_total": round(float(booking.get("total_price") or 0) + fee, 2)}

    @router.post("/claims")
    async def create_claim(body: ClaimIn,
                           current_user: dict = Depends(require_perm("edit_bookings"))):
        if body.amount <= 0:
            raise HTTPException(400, "amount must be > 0")
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), **body.model_dump(), "status": "open",
               "approved_amount": None, "resolution_note": "",
               "created_at": now, "updated_at": now,
               "created_by": current_user.get("email", "")}
        await db.damage_claims.insert_one(dict(doc))
        return doc

    @router.get("/claims/{property_id}")
    async def list_claims(property_id: str,
                          current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        return await db.damage_claims.find({"property_id": property_id}, {"_id": 0}) \
            .sort("created_at", -1).to_list(200)

    @router.put("/claims/{claim_id}")
    async def update_claim(claim_id: str, body: ClaimUpdate,
                           current_user: dict = Depends(require_perm("edit_bookings"))):
        if body.status not in VALID_STATUSES:
            raise HTTPException(400, f"Invalid status. Valid: {VALID_STATUSES}")
        claim = await db.damage_claims.find_one({"id": claim_id})
        if not claim:
            raise HTTPException(404, "Claim not found")
        upd = {"status": body.status, "resolution_note": body.resolution_note or "",
               "updated_at": datetime.now(timezone.utc).isoformat(),
               "updated_by": current_user.get("email", "")}
        if body.approved_amount is not None:
            upd["approved_amount"] = float(body.approved_amount)
        elif body.status in ("approved", "settled") and claim.get("approved_amount") is None:
            upd["approved_amount"] = float(claim.get("amount") or 0)
        await db.damage_claims.update_one({"id": claim_id}, {"$set": upd})
        doc = await db.damage_claims.find_one({"id": claim_id}, {"_id": 0})
        return doc

    return router
