"""
Booking Engine v2 — Conversion optimization.

  - Package builder: combine room + extras (breakfast, parking, spa) into named packages
  - Upsell offers: at booking confirmation, propose upgrades (room class, extras)
  - Abandoned cart tracking: pre-booking sessions that didn't convert
  - A/B test buckets per session
  - Public widget endpoint (CORS-friendly) for white-label embed

Endpoints:
  GET   /api/booking-engine/packages             — list packages
  POST  /api/booking-engine/packages             — create package
  PATCH /api/booking-engine/packages/{id}        — update / disable
  GET   /api/booking-engine/upsells              — list upsell offers
  POST  /api/booking-engine/upsells              — create upsell
  POST  /api/booking-engine/cart/track           — track an abandoned cart
  GET   /api/booking-engine/cart/abandoned       — list abandoned carts (for recovery)
  POST  /api/booking-engine/cart/recover/{id}    — queue recovery email
  GET   /api/booking-engine/ab-test/assign       — assign A/B variant
"""
from datetime import datetime, timezone, timedelta
import random
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class Extra(BaseModel):
    name: str
    price: float
    description: str = ""


class PackageIn(BaseModel):
    name: str
    description: str = ""
    property_id: str = "all"
    base_room_type_id: str = ""
    extras: List[Extra] = []
    discount_percent: float = 0
    min_nights: int = 1
    max_nights: int = 30
    active: bool = True


class UpsellIn(BaseModel):
    name: str
    description: str = ""
    property_id: str = "all"
    target: str = "booking_confirmation"  # booking_confirmation | pre_arrival | in_stay
    type: str = "room_upgrade"            # room_upgrade | extra | service
    payload: dict = {}                     # e.g. {"from_room_type": "STD", "to_room_type": "DLX", "upgrade_fee": 35}
    active: bool = True


def create_booking_engine_v2_router(db, require_roles):
    router = APIRouter(prefix="/booking-engine")

    # ============== PACKAGES ==============
    @router.get("/packages")
    async def list_packages(property_id: str = "", active_only: bool = False,
                            _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["$or"] = [{"property_id": property_id}, {"property_id": "all"}]
        if active_only:
            q["active"] = True
        pkgs = await db.booking_packages.find(q, {"_id": 0}).sort("name", 1).to_list(200)
        return {"packages": pkgs, "count": len(pkgs)}

    @router.post("/packages")
    async def create_package(body: PackageIn,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), **body.dict(),
               "extras": [e.dict() for e in body.extras],
               "created_by": current_user.get("name", ""), "created_at": now,
               "bookings_count": 0}
        await db.booking_packages.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/packages/{pkg_id}")
    async def patch_package(pkg_id: str, body: dict,
                            _: dict = Depends(require_roles("admin", "manager"))):
        body["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.booking_packages.update_one({"id": pkg_id}, {"$set": body})
        if r.matched_count == 0:
            raise HTTPException(404, "Package not found")
        return {"updated": True}

    # ============== UPSELLS ==============
    @router.get("/upsells")
    async def list_upsells(property_id: str = "", target: str = "",
                           _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["$or"] = [{"property_id": property_id}, {"property_id": "all"}]
        if target:
            q["target"] = target
        upsells = await db.booking_upsells.find(q, {"_id": 0}).sort("name", 1).to_list(100)
        return {"upsells": upsells, "count": len(upsells)}

    @router.post("/upsells")
    async def create_upsell(body: UpsellIn,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), **body.dict(),
               "created_by": current_user.get("name", ""), "created_at": now,
               "presented_count": 0, "accepted_count": 0}
        await db.booking_upsells.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.post("/upsells/{upsell_id}/accept")
    async def accept_upsell(upsell_id: str, body: dict,
                            _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        await db.booking_upsells.update_one({"id": upsell_id},
                                            {"$inc": {"accepted_count": 1, "presented_count": 1}})
        # Log acceptance
        await db.booking_upsell_log.insert_one({
            "id": str(uuid.uuid4()), "upsell_id": upsell_id,
            "booking_ref": body.get("booking_ref", ""),
            "guest_email": body.get("guest_email", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"accepted": True}

    # ============== ABANDONED CART ==============
    @router.post("/cart/track")
    async def track_cart(body: dict):
        """Public endpoint — no auth (called from booking widget)."""
        now = datetime.now(timezone.utc).isoformat()
        session_id = body.get("session_id") or str(uuid.uuid4())
        doc = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "guest_email": body.get("guest_email", ""),
            "property_id": body.get("property_id", ""),
            "step": body.get("step", "search"),          # search | dates | room | extras | payment
            "details": body.get("details", {}),
            "abandoned_at": now,
            "recovered": False,
            "created_at": now,
        }
        await db.abandoned_carts.insert_one(doc)
        return {"tracked": True, "id": doc["id"]}

    @router.get("/cart/abandoned")
    async def list_abandoned(days: int = 7, with_email_only: bool = True,
                             _: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: dict = {"created_at": {"$gte": since}, "recovered": False}
        if with_email_only:
            q["guest_email"] = {"$ne": ""}
        carts = await db.abandoned_carts.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"carts": carts, "count": len(carts)}

    @router.post("/cart/recover/{cart_id}")
    async def recover_cart(cart_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        cart = await db.abandoned_carts.find_one({"id": cart_id}, {"_id": 0})
        if not cart:
            raise HTTPException(404, "Cart not found")
        if not cart.get("guest_email"):
            raise HTTPException(400, "No email on this cart")
        await db.guest_campaigns.insert_one({
            "id": str(uuid.uuid4()), "guest_email": cart["guest_email"],
            "campaign": "cart_recovery", "template": "We saved your spot — 10% off if you book today",
            "status": "queued", "metadata": {"cart_id": cart_id, "step": cart.get("step")},
            "queued_by": current_user.get("name", ""),
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })
        await db.abandoned_carts.update_one({"id": cart_id}, {"$set": {"recovery_queued": True}})
        return {"queued": True}

    # ============== A/B TEST ==============
    @router.get("/ab-test/assign")
    async def ab_assign(experiment: str, session_id: str = ""):
        """Public: assign a session to A or B."""
        # Stable hash → variant
        h = abs(hash(session_id + experiment))
        variant = "A" if h % 2 == 0 else "B"
        await db.ab_assignments.update_one(
            {"experiment": experiment, "session_id": session_id},
            {"$set": {"variant": variant, "assigned_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"experiment": experiment, "variant": variant, "session_id": session_id}

    return router
