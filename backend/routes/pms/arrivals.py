"""
Arrivals Cockpit — one-pane view of every incoming guest's contactless
progress: Registration -> ID -> Payment -> Digital Key.

Reuses existing guest_registrations + bookings + digital_keys collections.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta, date
from typing import Optional
import secrets
import uuid
import os
import logging

logger = logging.getLogger(__name__)


def create_arrivals_router(db, require_roles):
    router = APIRouter()

    # -------- AGGREGATE LIST --------
    @router.get("/arrivals/{property_id}")
    async def list_arrivals(property_id: str, window: str = "7d", q: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """
        window = today | 7d | 30d | all
        Returns every booking in the window with its contactless progress computed.
        """
        today = date.today()
        start = today.isoformat()
        if window == "today":
            end = today.isoformat()
        elif window == "30d":
            end = (today + timedelta(days=30)).isoformat()
        elif window == "all":
            end = (today + timedelta(days=365)).isoformat()
        else:  # 7d default
            end = (today + timedelta(days=7)).isoformat()

        bk_query = {
            "status": {"$in": ["confirmed", "pending", "checked_in"]},
            "check_in": {"$gte": start, "$lte": end},
        }
        if property_id != "all":
            bk_query["property_id"] = property_id
        if q:
            bk_query["$or"] = [
                {"guest_name": {"$regex": q, "$options": "i"}},
                {"booking_ref": {"$regex": q, "$options": "i"}},
                {"guest_email": {"$regex": q, "$options": "i"}},
            ]

        bookings = await db.bookings.find(bk_query, {"_id": 0}).sort("check_in", 1).to_list(500)

        # Preload registrations, digital_keys, payments in bulk
        booking_ids = [b["id"] for b in bookings]
        regs = await db.guest_registrations.find(
            {"booking_id": {"$in": booking_ids}}, {"_id": 0}
        ).to_list(1000)
        reg_map = {r["booking_id"]: r for r in regs}

        keys = await db.digital_keys.find(
            {"booking_id": {"$in": booking_ids}}, {"_id": 0}
        ).to_list(1000)
        key_map = {k["booking_id"]: k for k in keys}

        idvs = await db.id_verifications.find(
            {"booking_id": {"$in": booking_ids}}, {"_id": 0, "booking_id": 1, "status": 1}
        ).to_list(1000)
        idv_map = {v["booking_id"]: v.get("status") for v in idvs}

        arrivals = []
        counters = {"total": 0, "registered": 0, "id_verified": 0, "paid": 0, "key_issued": 0}
        for b in bookings:
            reg = reg_map.get(b["id"])
            key = key_map.get(b["id"])

            registered = bool(reg and (reg.get("status") == "completed" or reg.get("terms_accepted")))
            id_verified = bool(reg and reg.get("id_uploaded"))
            paid = (b.get("payment_status") or "").lower() in ("paid", "captured", "completed") \
                   or (float(b.get("amount_paid") or 0) >= float(b.get("total_price") or 1))
            key_issued = bool(key and key.get("status") != "revoked")

            # Stage: 0 none, 1 link sent, 2 registered, 3 id, 4 paid, 5 key issued
            if key_issued:
                stage, stage_label = 5, "ready"
            elif paid:
                stage, stage_label = 4, "paid"
            elif id_verified:
                stage, stage_label = 3, "id_verified"
            elif registered:
                stage, stage_label = 2, "registered"
            elif reg:
                stage, stage_label = 1, "link_sent"
            else:
                stage, stage_label = 0, "not_started"

            arrivals.append({
                "booking_id": b["id"],
                "booking_ref": b.get("booking_ref", ""),
                "property_id": b.get("property_id", ""),
                "guest_name": b.get("guest_name", ""),
                "guest_email": b.get("guest_email", ""),
                "guest_phone": b.get("guest_phone", ""),
                "check_in": b.get("check_in", ""),
                "check_out": b.get("check_out", ""),
                "eta": b.get("eta", ""),
                "nights": b.get("nights", 1),
                "rooms": b.get("rooms", 1),
                "room_number": b.get("room_number", ""),
                "total_price": float(b.get("total_price") or 0),
                "amount_paid": float(b.get("amount_paid") or 0),
                "source": b.get("source", "direct"),
                "special_requests": b.get("special_requests", ""),
                "damage_waiver": bool(b.get("damage_waiver")),
                "noshow_secured": bool(b.get("noshow_secured")),
                "id_verification": idv_map.get(b["id"], "none"),
                "progress": {
                    "link_sent": bool(reg),
                    "registered": registered,
                    "id_verified": id_verified,
                    "paid": paid,
                    "key_issued": key_issued,
                },
                "stage": stage,
                "stage_label": stage_label,
                "registration_token": reg.get("token") if reg else None,
                "registration_status": reg.get("status") if reg else None,
                "digital_key_code": key.get("code") if key_issued else None,
                "digital_key_expires": key.get("expires_at") if key_issued else None,
            })

            counters["total"] += 1
            if registered: counters["registered"] += 1
            if id_verified: counters["id_verified"] += 1
            if paid: counters["paid"] += 1
            if key_issued: counters["key_issued"] += 1

        return {
            "window": window,
            "start": start,
            "end": end,
            "counters": counters,
            "arrivals": arrivals,
        }

    # -------- ISSUE DIGITAL KEY --------
    @router.post("/arrivals/{booking_id}/issue-key")
    async def issue_key(booking_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")

        # Require paid status before issuing a key (mirrors Mews behaviour)
        paid = (booking.get("payment_status") or "").lower() in ("paid", "captured", "completed") \
               or (float(booking.get("amount_paid") or 0) >= float(booking.get("total_price") or 1))
        if not paid:
            raise HTTPException(400, "Booking must be paid before issuing a digital key")

        # Rotate/generate
        code = "".join(secrets.choice("ACDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        now = datetime.now(timezone.utc)
        expires = (datetime.fromisoformat(booking["check_out"]) if booking.get("check_out")
                   else now + timedelta(days=1)).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "booking_ref": booking.get("booking_ref", ""),
            "property_id": booking.get("property_id", ""),
            "guest_name": booking.get("guest_name", ""),
            "room_number": booking.get("room_number", ""),
            "code": code,
            "status": "active",
            "issued_at": now.isoformat(),
            "issued_by": current_user.get("name", ""),
            "expires_at": expires,
        }
        await db.digital_keys.update_one(
            {"booking_id": booking_id},
            {"$set": doc}, upsert=True
        )
        return {"ok": True, "code": code, "expires_at": expires}

    # -------- REVOKE DIGITAL KEY --------
    @router.post("/arrivals/{booking_id}/revoke-key")
    async def revoke_key(booking_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        r = await db.digital_keys.update_one(
            {"booking_id": booking_id},
            {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat(),
                      "revoked_by": current_user.get("name", "")}}
        )
        if r.matched_count == 0:
            raise HTTPException(404, "No key to revoke")
        return {"ok": True}

    # -------- MARK PAID (quick-action from cockpit) --------
    @router.post("/arrivals/{booking_id}/mark-paid")
    async def mark_paid(booking_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {
                "payment_status": "paid",
                "amount_paid": float(b.get("total_price") or 0),
                "paid_at": datetime.now(timezone.utc).isoformat(),
                "paid_by": current_user.get("name", ""),
            }}
        )
        return {"ok": True}

    return router
