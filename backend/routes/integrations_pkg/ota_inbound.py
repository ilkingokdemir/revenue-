"""
Channel Manager Inbound Webhook (iter 371) — Mews parity
=========================================================
Real 2-way OTA sync: OTAs (Booking.com, Expedia, Airbnb) POST reservation
events to our webhook, we ingest them into `bookings` collection with
provenance tracking. Existing outbound sync (rates/availability push) is
handled by `sync_queue.py`.

Endpoints
---------
  POST /api/ota-inbound/{channel}/reservation      — new/updated reservation
  POST /api/ota-inbound/{channel}/cancellation      — cancellation event
  GET  /api/ota-inbound/log                         — recent inbound events (staff)

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
    total_price:        float
    currency:           str = "GBP"
    guest_count:        int = 1
    status:             str = "confirmed"
    raw_payload:        Optional[dict] = None


class InboundCancellation(BaseModel):
    channel_reference: str
    reason:            Optional[str] = None


def create_ota_inbound_router(db, require_roles):
    router = APIRouter(prefix="/ota-inbound", tags=["channel-manager-inbound"])

    @router.post("/{channel}/reservation")
    async def receive_reservation(channel: str, body: InboundReservation,
                                     x_signature: Optional[str] = Header(None)):
        if channel not in ALLOWED_CHANNELS:
            raise HTTPException(400, f"Desteklenmeyen kanal: {channel}")
        # (raw body sig check disabled in dev — needs starlette Request to
        # verify. Left as a hook for production.)
        _ = x_signature

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
        existing = await db.bookings.find_one({"channel_key": booking_key}, {"_id": 0, "id": 1})
        booking_id = existing["id"] if existing else str(uuid.uuid4())
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
            "room_number":     body.room_number,
            "total_price":     body.total_price,
            "currency":        body.currency,
            "guest_count":     body.guest_count,
            "status":          body.status,
            "source":          f"ota:{channel}",
            "created_at":      _now() if not existing else None,
            "updated_at":      _now(),
        }
        # Drop None fields so we don't clobber existing values
        doc = {k: v for k, v in doc.items() if v is not None}
        await db.bookings.update_one(
            {"channel_key": booking_key}, {"$set": doc}, upsert=True
        )
        return {
            "ok":         True,
            "action":     "updated" if existing else "created",
            "booking_id": booking_id,
            "event_id":   event_id,
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

    return router
