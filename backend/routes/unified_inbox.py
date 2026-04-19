"""
Unified Inbox
-------------
Eviivo-style merged conversation view — WhatsApp, SMS, Email, Booking.com, Airbnb
messages for a given guest collapsed into a single thread. Keyed by `guest_key`
(email, phone, or booking_id — whichever the channel provides most reliably).

Collection: unified_messages
  { id, guest_key, booking_id?, guest_name, channel (whatsapp|sms|email|booking_com|airbnb|direct),
    direction (inbound|outbound), body, from_addr, to_addr, subject?, attachments[],
    read, created_at, sent_by? }

Endpoints (/api/inbox/*):
- GET  /threads                          → list of threads with last-message preview + unread count
- GET  /threads/{guest_key}/messages     → full message list for a thread (chronological)
- POST /threads/{guest_key}/send         → {channel, body, subject?} — save as outbound
- POST /mark-read/{guest_key}            → mark all inbound messages as read
- POST /webhook/{channel}                → public inbound webhook (stub — real integrations wire here)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Optional, List, Dict
import uuid

from auth import require_perm


def create_unified_inbox_router(db):
    router = APIRouter(prefix="/inbox")

    @router.get("/threads")
    async def list_threads(
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """One row per guest_key: last message preview + unread count + channels seen."""
        pipeline = [
            {"$sort": {"created_at": 1}},
            {"$group": {
                "_id": "$guest_key",
                "guest_name": {"$last": "$guest_name"},
                "booking_id": {"$last": "$booking_id"},
                "last_body": {"$last": "$body"},
                "last_at": {"$last": "$created_at"},
                "last_channel": {"$last": "$channel"},
                "last_direction": {"$last": "$direction"},
                "channels": {"$addToSet": "$channel"},
                "unread": {"$sum": {"$cond": [
                    {"$and": [{"$eq": ["$direction", "inbound"]}, {"$eq": ["$read", False]}]}, 1, 0
                ]}},
                "total": {"$sum": 1},
            }},
            {"$sort": {"last_at": -1}},
        ]
        rows = await db.unified_messages.aggregate(pipeline).to_list(500)
        # Reshape
        out = [{
            "guest_key": r["_id"],
            "guest_name": r.get("guest_name", ""),
            "booking_id": r.get("booking_id") or "",
            "last_preview": (r.get("last_body") or "")[:120],
            "last_at": r.get("last_at", ""),
            "last_channel": r.get("last_channel", ""),
            "last_direction": r.get("last_direction", ""),
            "channels": sorted([c for c in (r.get("channels") or []) if c]),
            "unread": int(r.get("unread", 0)),
            "total": int(r.get("total", 0)),
        } for r in rows if r.get("_id")]
        return out

    @router.get("/threads/{guest_key}/messages")
    async def thread_messages(
        guest_key: str,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        msgs = await db.unified_messages.find(
            {"guest_key": guest_key}, {"_id": 0},
        ).sort("created_at", 1).to_list(1000)
        return msgs

    @router.post("/threads/{guest_key}/send")
    async def send_message(
        guest_key: str, data: Dict,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """Save an outbound message. Actual transport (WhatsApp/SMS/Email) is wired per-channel
        via the existing integrations; this endpoint stores the record and returns it."""
        channel = (data.get("channel") or "").strip()
        if channel not in ("whatsapp", "sms", "email", "booking_com", "airbnb", "direct"):
            raise HTTPException(400, "Invalid channel")
        body = (data.get("body") or "").strip()
        if not body:
            raise HTTPException(400, "Body required")

        # Enrich guest_name from the most recent prior message if available
        prior = await db.unified_messages.find_one(
            {"guest_key": guest_key}, {"_id": 0, "guest_name": 1, "booking_id": 1},
            sort=[("created_at", -1)],
        ) or {}

        doc = {
            "id": str(uuid.uuid4()),
            "guest_key": guest_key,
            "booking_id": data.get("booking_id") or prior.get("booking_id", ""),
            "guest_name": data.get("guest_name") or prior.get("guest_name", ""),
            "channel": channel,
            "direction": "outbound",
            "body": body,
            "subject": data.get("subject", ""),
            "from_addr": current_user.get("email", ""),
            "to_addr": guest_key,
            "attachments": data.get("attachments", []),
            "read": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sent_by": current_user.get("name", current_user.get("email", "")),
        }
        await db.unified_messages.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.post("/mark-read/{guest_key}")
    async def mark_read(
        guest_key: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        r = await db.unified_messages.update_many(
            {"guest_key": guest_key, "direction": "inbound", "read": False},
            {"$set": {"read": True}},
        )
        return {"marked": r.modified_count}

    @router.post("/webhook/{channel}")
    async def inbound_webhook(channel: str, data: Dict):
        """PUBLIC endpoint — downstream channel providers (Twilio, Meta WhatsApp Cloud,
        Booking.com, Airbnb) POST inbound messages here. This is the common-shape stub;
        per-channel signature verification is the caller's responsibility to add."""
        if channel not in ("whatsapp", "sms", "email", "booking_com", "airbnb", "direct"):
            raise HTTPException(400, "Invalid channel")
        guest_key = (data.get("guest_key") or data.get("from") or "").strip()
        if not guest_key:
            raise HTTPException(400, "guest_key or from required")
        body = (data.get("body") or data.get("text") or "").strip()
        if not body:
            raise HTTPException(400, "Body required")

        doc = {
            "id": str(uuid.uuid4()),
            "guest_key": guest_key,
            "booking_id": data.get("booking_id", ""),
            "guest_name": data.get("guest_name", guest_key),
            "channel": channel,
            "direction": "inbound",
            "body": body,
            "subject": data.get("subject", ""),
            "from_addr": data.get("from", guest_key),
            "to_addr": data.get("to", ""),
            "attachments": data.get("attachments", []),
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.unified_messages.insert_one(dict(doc))
        return {"ok": True, "id": doc["id"]}

    return router
