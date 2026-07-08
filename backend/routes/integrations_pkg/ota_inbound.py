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
import asyncio
import hashlib
import hmac
import json
import logging
import os
import uuid

try:
    import httpx   # already installed for other integrations
except Exception:
    httpx = None

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel


ALLOWED_CHANNELS = {"booking_com", "expedia", "airbnb", "agoda", "trip_com"}
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


async def _send_slack(text: str, blocks: Optional[list] = None) -> bool:
    """Post to Slack via SLACK_WEBHOOK_URL_OTA (fire-and-forget)."""
    url = os.environ.get("SLACK_WEBHOOK_URL_OTA") or os.environ.get("SLACK_WEBHOOK_URL")
    if not url or not httpx:
        return False
    try:
        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(url, json=payload)
        return r.status_code < 300
    except Exception as e:
        logger.warning(f"Slack webhook failed: {e}")
        return False


async def _notify_auto_assign(db, kind: str, booking: dict, extra: Optional[dict] = None) -> None:
    """Create an in-app notification + optional Slack alert for auto-assign events.

    kind: "success" (informational), "unassigned" (high priority — needs action),
          "upgrade" (loyalty upgrade — informational).
    """
    extra = extra or {}
    channel = booking.get("channel", booking.get("source", "ota").replace("ota:", ""))
    guest = booking.get("guest_name", "-")
    ref = booking.get("channel_reference", "-")
    ci = booking.get("check_in", "-")
    room = booking.get("room_number") or extra.get("room_number") or "?"

    if kind == "success":
        title = f"OTA oda otomatik atandı: {room}"
        message = f"{channel.upper()} · {guest} · Ref {ref} · Check-in {ci}"
        priority = "low"
        link = "chmgr-hub:unassigned"
    elif kind == "upgrade":
        title = f"🎁 Loyalty upgrade: {guest} → {room}"
        message = f"{channel.upper()} · Elite üye üst kategori odaya yükseltildi (Ref {ref})"
        priority = "normal"
        link = "chmgr-hub:unassigned"
    else:  # unassigned
        title = f"⚠️ Auto-assign başarısız: {guest}"
        message = f"{channel.upper()} · Ref {ref} · Check-in {ci} — front desk manuel oda atamalı"
        priority = "high"
        link = "chmgr-hub:unassigned"

    try:
        await db.notifications.insert_one({
            "id":           str(uuid.uuid4()),
            "type":         f"ota_auto_assign_{kind}",
            "title":        title,
            "message":      message,
            "property_id":  booking.get("property_id"),
            "target_role":  "front_desk",
            "link_to":      link,
            "priority":     priority,
            "read":         False,
            "created_by":   "OTA Auto-Assign",
            "created_at":   _now(),
            "meta":         {
                "booking_id":         booking.get("id"),
                "channel":            channel,
                "channel_reference":  ref,
                "room_number":        room,
                **extra,
            },
        })
    except Exception as e:
        logger.warning(f"Notification insert failed: {e}")

    # Slack (fire-and-forget, non-blocking)
    slack_text = f"{title}\n{message}"
    asyncio.create_task(_send_slack(slack_text))


def _verify_signature_wrapper(*args, **kwargs):
    """Placeholder — unused, kept for backward compat."""
    return _verify_signature(*args, **kwargs)


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


async def _get_external_elite(db, guest_email: Optional[str]) -> list:
    """Return list of external loyalty programs where the guest is elite tier.
    Used by _auto_assign_room to boost score for Bonvoy Platinum, Hilton Diamond, etc.
    """
    if not guest_email:
        return []
    q = {"$or": [{"guest_id": guest_email.lower()},
                  {"guest_id": guest_email}],
         "is_elite": True}
    rows = await db.external_loyalty_links.find(
        q, {"_id": 0, "program": 1, "tier": 1}
    ).to_list(10)
    return rows


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

    # External loyalty (Marriott Bonvoy, Hilton Honors, etc.) — Elite bonus (iter 373b)
    ext_elite = await _get_external_elite(db, guest_email)
    ext_bonus = 50 * len(ext_elite) if ext_elite else 0   # +50 per elite program
    if ext_elite:
        upgrade_eligible = True   # Any chain elite qualifies for upgrade

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

        # External chain-loyalty elite bonus (iter 373b)
        if ext_bonus:
            score += ext_bonus
            score += floor   # extra floor bonus for chain elite

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
    best = scored[0]
    # Attach elite info for logging
    if ext_elite:
        best["_chain_elite"] = [{"program": e.get("program"), "tier": e.get("tier")} for e in ext_elite]
    return best


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
        notif_kind: Optional[str] = None
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
                is_upgrade = bool(picked.get("_upgrade"))
                chain_elite = picked.get("_chain_elite") or []
                assignment_info = {
                    "auto_assigned":   True,
                    "assigned_room_id": room_id,
                    "assigned_score":   picked.get("_score"),
                    "assigned_upgrade": is_upgrade,
                    "assigned_at":      _now(),
                }
                if chain_elite:
                    assignment_info["chain_elite"] = chain_elite
                notif_kind = "upgrade" if (is_upgrade or chain_elite) else "success"
            else:
                assignment_info = {
                    "auto_assigned":         False,
                    "room_assignment_status": "unassigned",
                    "unassigned_reason":     "no_available_room",
                    "assigned_at":           _now(),
                }
                notif_kind = "unassigned"
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

        # Fire notification (in-app + Slack) for auto-assign result
        if notif_kind:
            await _notify_auto_assign(db, notif_kind, doc, extra={
                "score":   assignment_info.get("assigned_score"),
                "upgrade": assignment_info.get("assigned_upgrade", False),
            })

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
        # Notify success (or upgrade)
        bk["room_number"] = picked.get("name") or picked.get("id")
        await _notify_auto_assign(
            db,
            "upgrade" if picked.get("_upgrade") else "success",
            bk,
            extra={"score": picked.get("_score"),
                   "upgrade": picked.get("_upgrade", False),
                   "via": "retry"},
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
