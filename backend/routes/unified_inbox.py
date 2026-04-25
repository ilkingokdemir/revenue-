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
- POST /threads/{guest_key}/ai-suggest   → GPT-5.2 generates 3 reply tone variants (warm / brief / apologetic)
- POST /mark-read/{guest_key}            → mark all inbound messages as read
- POST /webhook/{channel}                → public inbound webhook (stub — real integrations wire here)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Optional, List, Dict
import os
import uuid
import logging

from auth import require_perm

logger = logging.getLogger(__name__)


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

    @router.post("/threads/{guest_key}/ai-suggest")
    async def ai_suggest_reply(
        guest_key: str, data: Optional[Dict] = None,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """Use GPT-5.2 to generate 3 reply suggestions (warm / brief / apologetic).

        Pulls last ~10 messages of the thread for context, plus optional booking
        info and hotel name. Returns: {suggestions: [{tone, channel, body}, …]}.
        Falls back to a heuristic template if the LLM key/integration is missing.
        """
        msgs = await db.unified_messages.find(
            {"guest_key": guest_key}, {"_id": 0},
        ).sort("created_at", -1).to_list(10)
        msgs = list(reversed(msgs))
        if not msgs:
            raise HTTPException(404, "Thread not found")

        # Last inbound message is what we're replying to
        last_inbound = next((m for m in reversed(msgs) if m.get("direction") == "inbound"), msgs[-1])
        channel = (data or {}).get("channel") or last_inbound.get("channel", "email")
        guest_name = msgs[0].get("guest_name", "") or guest_key
        booking_id = msgs[0].get("booking_id", "")
        hotel_name = (data or {}).get("hotel_name", "")

        # Build conversation transcript
        transcript = "\n".join(
            f"[{m.get('channel','?')}|{m.get('direction','?')}] {m.get('body','')[:400]}"
            for m in msgs[-8:]
        )

        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return {
                "suggestions": [
                    {"tone": "warm",       "channel": channel, "body": f"Hi {guest_name},\n\nThanks for reaching out — happy to help. {('We will get back to you shortly with the details.' if last_inbound else '')}\n\nBest regards,\n{hotel_name or 'Reception'}"},
                    {"tone": "brief",      "channel": channel, "body": f"Hi {guest_name}, noted — we’ll get back to you shortly."},
                    {"tone": "apologetic", "channel": channel, "body": f"Dear {guest_name},\n\nApologies for any inconvenience. We're looking into this right away and will revert with a resolution.\n\nKind regards,\n{hotel_name or 'Reception'}"},
                ],
                "fallback": True,
            }

        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sys_prompt = (
            "You are a senior front-office host at a boutique hotel writing reply suggestions "
            "for a guest message. Reply in the SAME LANGUAGE the guest used. Be concise, "
            "specific, never invent facts (e.g. don't promise upgrades or refunds you weren't told about). "
            "If the guest asked a yes/no question, answer first, then add details. "
            f"Hotel name: {hotel_name or 'our hotel'}. "
            f"Booking ref: {booking_id or 'n/a'}. "
            f"Channel: {channel}. "
            "Output strict JSON: "
            '{"suggestions":[{"tone":"warm","body":"…"},{"tone":"brief","body":"…"},{"tone":"apologetic","body":"…"}]} '
            "— no markdown, no commentary."
        )
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"inbox-suggest-{guest_key}-{uuid.uuid4().hex[:6]}",
                system_message=sys_prompt,
            ).with_model("openai", "gpt-5.2")
            resp = await chat.send_message(UserMessage(
                text=f"Conversation so far:\n{transcript}\n\nWrite 3 reply suggestions (warm, brief, apologetic) "
                     f"for the LAST inbound message from {guest_name}. Return strict JSON only."
            ))
            import json, re
            txt = (resp or "").strip()
            # Strip markdown fences if any
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            parsed = json.loads(m.group(0)) if m else {"suggestions": []}
            sugg = parsed.get("suggestions", [])
            for s in sugg:
                s["channel"] = channel
            return {"suggestions": sugg, "fallback": False}
        except Exception as e:
            logger.exception("Inbox AI-suggest failed: %s", e)
            return {
                "suggestions": [
                    {"tone": "warm",       "channel": channel, "body": f"Hi {guest_name}, thanks for reaching out — we’ll get back to you shortly."},
                ],
                "fallback": True,
                "error": str(e)[:200],
            }

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
