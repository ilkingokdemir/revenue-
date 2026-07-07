"""
Channel Manager Inbound Webhook (iter 371) — Mews parity
=========================================================
Real 2-way OTA sync: OTAs (Booking.com, Expedia, Airbnb) POST reservation
events to our webhook, we ingest them into `bookings` collection with
provenance tracking. Existing outbound sync (rates/availability push) is
handled by `sync_queue.py`.

iter 372: Added **Auto Room Assign** — when the OTA payload lacks a
`room_number`, we automatically pick the best available room matching the
requested `room_type_id`. Scoring considers guest loyalty tier, view
preference (from raw_payload.view_preference) and housekeeping status.

Endpoints
---------
  POST /api/ota-inbound/{channel}/reservation      — new/updated reservation
  POST /api/ota-inbound/{channel}/cancellation      — cancellation event
  GET  /api/ota-inbound/log                         — recent inbound events (staff)
  POST /api/ota-inbound/auto-assign/{booking_id}    — retry auto-assign

Supported channels: booking_com, expedia, airbnb (extend as needed).

Signature verification is stubbed — production must verify HMAC per OTA.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import hashlib
import hmac
import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel


ALLOWED_CHANNELS = {"booking_com", "expedia", "airbnb"}

# Loyalty tier -> upgrade eligibility (True = eligible for one-tier free upgrade)
_TIER_UPGRADE = {"platinum": True, "diamond": True, "gold": False,
                 "silver": False, "bronze": False}
_TIER_SCORE = {"diamond": 40, "platinum": 30, "gold": 20, "silver": 10,
               "bronze": 5}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verify_signature(raw_body: bytes, sig: Optional[str], channel: str) -> bool:
    """Stub HMAC verify — env var `OTA_WEBHOOK_SECRET_{CHANNEL}` holds the
    shared secret. If not configured, we skip (dev mode)."""
    secret = os.environ.get(f"OTA_WEBHOOK_SECRET_{channel.upper()}")
    if not secret or not sig:
        return True   # accept in dev; production must configure
    computed = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, sig)


class InboundReservation(BaseModel):
    channel_reference:  str            # OTA's own booking ID
    property_id:        str
    guest_name:         str
    guest_email:        Optional[str] = None
    check_in:           str            # YYYY-MM-DD
    check_out:          str
    room_number:        Optional[str] = None
    room_type_id:       Optional[str] = None   # NEW — used for auto-assign
    view_preference:    Optional[str] = None   # e.g. "sea", "city", "garden"
    total_price:        float
    currency:           str = "GBP"
    guest_count:        int = 1
    status:             str = "confirmed"
    raw_payload:        Optional[dict] = None


class InboundCancellation(BaseModel):
    channel_reference: str
    reason:            Optional[str] = None


async def _get_loyalty_tier(db, guest_email: Optional[str]) -> Optional[str]:
    """Look up loyalty tier for a guest email. Returns tier string or None."""
    if not guest_email:
        return None
    m = await db.loyalty_members.find_one({"guest_email": guest_email.lower()},
                                            {"_id": 0, "tier": 1})
    if not m:
        # try case-insensitive fallback
        m = await db.loyalty_members.find_one({"guest_email": guest_email},
                                                {"_id": 0, "tier": 1})
    return (m or {}).get("tier")


async def _auto_assign_room(db, property_id: str, room_type_id: Optional[str],
                              check_in: str, check_out: str,
                              guest_email: Optional[str] = None,
                              view_preference: Optional[str] = None,
                              exclude_booking_id: Optional[str] = None
                              ) -> Optional[dict]:
    """Score-based room picker.

    Returns the best available room document (with `_score` field added) or
    None if nothing suitable. Scoring:
      + 100  clean & vacant
      +  50  matches requested view_preference
      + tier_score  loyalty bonus (higher floor preferred)
      +  10  currently 'available' status
    Rooms already booked in the [check_in, check_out) window are filtered out.
    Platinum/Diamond members may be upgraded one tier when no match exists.
    """
    if not property_id:
        return None

    # Fetch candidate rooms (matching room_type first)
    q: dict = {"property_id": property_id}
    if room_type_id:
        q["room_type_id"] = room_type_id
    rooms = await db.rooms.find(q, {"_id": 0}).to_list(500)
    if not rooms and room_type_id:
        # No rooms for that type → try any room in the property (upgrade path)
        rooms = await db.rooms.find({"property_id": property_id}, {"_id": 0}).to_list(500)

    if not rooms:
        return None

    # Find rooms already occupied in the date window
    occupied_ids = set()
    occ_filter = {
        "property_id": property_id,
        "check_in":  {"$lt": check_out},
        "check_out": {"$gt": check_in},
        "status":    {"$in": ["confirmed", "pending", "checked_in"]},
    }
    if exclude_booking_id:
        occ_filter["id"] = {"$ne": exclude_booking_id}
    async for b in db.bookings.find(occ_filter, {"_id": 0, "room_id": 1,
                                                   "room_number": 1}):
        if b.get("room_id"):
            occupied_ids.add(b["room_id"])
        if b.get("room_number"):
            occupied_ids.add(b["room_number"])

    tier = await _get_loyalty_tier(db, guest_email)
    tier_bonus = _TIER_SCORE.get((tier or "").lower(), 0)
    upgrade_eligible = _TIER_UPGRADE.get((tier or "").lower(), False)

    # Score candidates
    scored: list[dict] = []
    for r in rooms:
        rid = r.get("id")
        rname = r.get("name")
        if rid in occupied_ids or rname in occupied_ids:
            continue

        score = 0
        # Housekeeping cleanliness
        hk = (r.get("housekeeping") or "").lower()
        if hk == "clean":
            score += 100
        elif hk in ("inspected", "ready"):
            score += 90
        elif hk == "dirty":
            score += 20
        elif hk == "out_of_order":
            continue   # skip
        else:
            score += 60

        # Room status
        if (r.get("status") or "").lower() == "available":
            score += 10

        # View preference match (from room.view field if set)
        rv = (r.get("view") or "").lower()
        if view_preference and rv and view_preference.lower() in rv:
            score += 50

        # Loyalty tier — higher floor preferred for elite members
        floor = int(r.get("floor") or 0)
        score += tier_bonus + (floor * 2 if tier_bonus >= 30 else floor)

        # Exact room_type match wins over upgrades
        if room_type_id and r.get("room_type_id") == room_type_id:
            score += 200
        elif room_type_id and r.get("room_type_id") != room_type_id:
            # Only allow upgrade if platinum/diamond
            if not upgrade_eligible:
                continue
            score += 5   # small bonus, prefers same-type when tied

        r["_score"] = score
        r["_upgrade"] = bool(room_type_id and r.get("room_type_id") != room_type_id)
        scored.append(r)

    if not scored:
        return None
    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[0]


def create_ota_inbound_router(db, require_roles):
    router = APIRouter(prefix="/ota-inbound", tags=["channel-manager-inbound"])

    @router.post("/{channel}/reservation")
    async def receive_reservation(channel: str, body: InboundReservation,
                                     x_signature: Optional[str] = Header(None)):
        if channel not in ALLOWED_CHANNELS:
            raise HTTPException(400, f"Desteklenmeyen kanal: {channel}")
        _ = x_signature   # sig hook (production)

        # Log the raw event
        event_id = str(uuid.uuid4())
        await db.ota_inbound_log.insert_one({
            "id":               event_id,
            "channel":          channel,
            "event_type":       "reservation",
            "channel_reference": body.channel_reference,
            "received_at":      _now(),
            "payload":          body.model_dump(),
        })

        # Upsert into bookings — idempotent per (channel, channel_reference)
        booking_key = f"{channel}:{body.channel_reference}"
        existing = await db.bookings.find_one({"channel_key": booking_key},
                                                {"_id": 0, "id": 1,
                                                 "room_id": 1, "room_number": 1})
        booking_id = existing["id"] if existing else str(uuid.uuid4())

        # --- Auto Room Assign (iter 372) -------------------------------
        # Only auto-assign if:
        #  (a) OTA did not send a room_number, AND
        #  (b) booking has no room assigned yet
        assignment_info: dict = {}
        room_number = body.room_number
        room_id = None
        already_assigned = bool(existing and (existing.get("room_id") or
                                                 existing.get("room_number")))
        if not room_number and not already_assigned:
            picked = await _auto_assign_room(
                db,
                property_id=body.property_id,
                room_type_id=body.room_type_id,
                check_in=body.check_in,
                check_out=body.check_out,
                guest_email=body.guest_email,
                view_preference=body.view_preference,
                exclude_booking_id=booking_id,
            )
            if picked:
                room_id = picked.get("id")
                room_number = picked.get("name") or picked.get("id")
                assignment_info = {
                    "auto_assigned":   True,
                    "assigned_room_id": room_id,
                    "assigned_score":   picked.get("_score"),
                    "assigned_upgrade": picked.get("_upgrade", False),
                    "assigned_at":      _now(),
                }
            else:
                assignment_info = {
                    "auto_assigned":         False,
                    "room_assignment_status": "unassigned",
                    "unassigned_reason":     "no_available_room",
                    "assigned_at":           _now(),
                }
        # ---------------------------------------------------------------

        doc = {
            "id":              booking_id,
            "channel_key":     booking_key,
            "channel":         channel,
            "channel_reference": body.channel_reference,
            "property_id":     body.property_id,
            "guest_name":      body.guest_name,
            "guest_email":     body.guest_email,
            "check_in":        body.check_in,
            "check_out":       body.check_out,
            "room_number":     room_number,
            "room_id":         room_id,
            "room_type_id":    body.room_type_id,
            "total_price":     body.total_price,
            "currency":        body.currency,
            "guest_count":     body.guest_count,
            "status":          body.status,
            "source":          f"ota:{channel}",
            "created_at":      _now() if not existing else None,
            "updated_at":      _now(),
            **assignment_info,
        }
        # Drop None fields so we don't clobber existing values
        doc = {k: v for k, v in doc.items() if v is not None}
        await db.bookings.update_one(
            {"channel_key": booking_key}, {"$set": doc}, upsert=True
        )
        return {
            "ok":              True,
            "action":          "updated" if existing else "created",
            "booking_id":      booking_id,
            "event_id":        event_id,
            "auto_assigned":   assignment_info.get("auto_assigned", False),
            "room_number":     room_number,
            "room_id":         room_id,
            "upgrade":         assignment_info.get("assigned_upgrade", False),
        }

    @router.post("/{channel}/cancellation")
    async def receive_cancellation(channel: str, body: InboundCancellation):
        if channel not in ALLOWED_CHANNELS:
            raise HTTPException(400, f"Desteklenmeyen kanal: {channel}")
        booking_key = f"{channel}:{body.channel_reference}"
        r = await db.bookings.update_one(
            {"channel_key": booking_key},
            {"$set": {"status": "cancelled",
                       "cancelled_at": _now(),
                       "cancellation_reason": body.reason or "OTA cancellation"}}
        )
        await db.ota_inbound_log.insert_one({
            "id":               str(uuid.uuid4()),
            "channel":          channel,
            "event_type":       "cancellation",
            "channel_reference": body.channel_reference,
            "received_at":      _now(),
            "payload":          body.model_dump(),
        })
        return {"ok": True, "cancelled": r.modified_count > 0}

    @router.get("/log")
    async def get_log(channel: Optional[str] = None, limit: int = 50,
                        _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if channel:
            q["channel"] = channel
        rows = await db.ota_inbound_log.find(q, {"_id": 0}).sort("received_at", -1).to_list(limit)
        return {"total": len(rows), "items": rows}

    @router.post("/auto-assign/{booking_id}")
    async def retry_auto_assign(booking_id: str,
                                  _: dict = Depends(require_roles("admin",
                                                                     "manager",
                                                                     "front_desk"))):
        """Retry the auto-assign flow for an unassigned OTA booking."""
        bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not bk:
            raise HTTPException(404, "Booking bulunamadı")
        if bk.get("room_id") or bk.get("room_number"):
            return {"ok": False, "reason": "already_assigned",
                     "room_number": bk.get("room_number")}

        picked = await _auto_assign_room(
            db,
            property_id=bk.get("property_id", ""),
            room_type_id=bk.get("room_type_id"),
            check_in=bk.get("check_in", ""),
            check_out=bk.get("check_out", ""),
            guest_email=bk.get("guest_email"),
            view_preference=bk.get("view_preference"),
            exclude_booking_id=booking_id,
        )
        if not picked:
            await db.bookings.update_one(
                {"id": booking_id},
                {"$set": {"room_assignment_status": "unassigned",
                           "unassigned_reason": "no_available_room",
                           "updated_at": _now()}}
            )
            return {"ok": False, "reason": "no_available_room"}

        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"room_id":       picked.get("id"),
                       "room_number":   picked.get("name") or picked.get("id"),
                       "auto_assigned": True,
                       "assigned_room_id": picked.get("id"),
                       "assigned_score": picked.get("_score"),
                       "assigned_upgrade": picked.get("_upgrade", False),
                       "assigned_at":   _now(),
                       "room_assignment_status": "auto_assigned",
                       "updated_at":    _now()}}
        )
        return {"ok": True, "booking_id": booking_id,
                 "room_id": picked.get("id"),
                 "room_number": picked.get("name") or picked.get("id"),
                 "score": picked.get("_score"),
                 "upgrade": picked.get("_upgrade", False)}

    @router.get("/unassigned")
    async def list_unassigned(limit: int = 50,
                                _: dict = Depends(require_roles("admin",
                                                                   "manager",
                                                                   "front_desk"))):
        """List OTA bookings that couldn't be auto-assigned (need front-desk action)."""
        q = {
            "source": {"$regex": "^ota:"},
            "$or": [
                {"room_assignment_status": "unassigned"},
                {"room_id": None, "room_number": None},
            ],
            "status": {"$ne": "cancelled"},
        }
        rows = await db.bookings.find(q, {"_id": 0}).sort("check_in", 1).to_list(limit)
        return {"total": len(rows), "items": rows}

    return router
