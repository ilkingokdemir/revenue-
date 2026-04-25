"""
AI Concierge — public chat endpoint that powers a floating "Need help?" bubble
on the direct booking widget. Uses GPT-5.2 via Emergent LLM key with a tight
hotel-context system prompt. Conversations are persisted in `concierge_chats`
keyed by `session_id` (the frontend generates a UUID per visitor session).

Endpoints (`/api/concierge/*`):
- POST /api/concierge/{property_id}/chat   {session_id, message}  -> {reply, suggestions[]}
- GET  /api/concierge/{property_id}/history?session_id=...        -> [messages]
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Dict
import os
import uuid
import logging

logger = logging.getLogger(__name__)


def create_concierge_router(db):
    router = APIRouter()

    @router.post("/concierge/{property_id}/chat")
    async def chat(property_id: str, data: Dict):
        msg = (data.get("message") or "").strip()
        session_id = (data.get("session_id") or "").strip() or str(uuid.uuid4())
        if not msg:
            raise HTTPException(400, "message required")
        if len(msg) > 1000:
            raise HTTPException(400, "message too long")

        # Build hotel context
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0}) or {}
        ts = await db.tenant_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        amenities_set = set()
        for r in rooms:
            for a in (r.get("amenities") or []):
                amenities_set.add(a)
        guest_app = await db.guest_app.find_one({"property_id": property_id}, {"_id": 0}) or {}

        context_parts = [
            f"Hotel name: {ts.get('hotel_name') or prop.get('name') or 'our hotel'}.",
            f"Address: {prop.get('address', '')} {prop.get('city', '')}.".strip(),
            f"Currency: {ts.get('currency', 'GBP')}.",
            "Rooms: " + ", ".join(
                f"{r.get('name', '')} (£{r.get('base_rate', 0)}, sleeps {r.get('max_occupancy', 2)})"
                for r in rooms[:8]
            ),
            f"Amenities: {', '.join(sorted(amenities_set)[:20])}." if amenities_set else "",
            f"Check-in: {ts.get('check_in_time', '15:00')}. Check-out: {ts.get('check_out_time', '11:00')}.",
        ]
        if guest_app.get("wifi_password"):
            context_parts.append(f"WiFi: SSID {guest_app.get('wifi_ssid', '')}, password {guest_app.get('wifi_password')}.")
        if guest_app.get("policies"):
            context_parts.append(f"Policies: {str(guest_app.get('policies'))[:400]}")
        hotel_ctx = "\n".join(p for p in context_parts if p)

        # Save user message
        now_iso = datetime.now(timezone.utc).isoformat()
        user_doc = {"id": str(uuid.uuid4()), "session_id": session_id,
                    "property_id": property_id, "role": "user",
                    "content": msg, "created_at": now_iso}
        await db.concierge_chats.insert_one(dict(user_doc))

        # Recent history (last 10 turns)
        history = await db.concierge_chats.find(
            {"session_id": session_id}, {"_id": 0, "role": 1, "content": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(10)
        history.reverse()

        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            reply = ("I'm offline right now. Please email reception or use the "
                     "booking form — we'll get back to you within the hour.")
            assistant_doc = {"id": str(uuid.uuid4()), "session_id": session_id,
                             "property_id": property_id, "role": "assistant",
                             "content": reply, "created_at": now_iso, "fallback": True}
            await db.concierge_chats.insert_one(dict(assistant_doc))
            return {"reply": reply, "session_id": session_id, "fallback": True,
                    "suggestions": ["Book a room", "Check policies", "Contact reception"]}

        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sys_prompt = (
            "You are the friendly AI concierge for the hotel listed below. Reply in the "
            "SAME LANGUAGE as the guest's message. Be warm, concise (2–4 short sentences), "
            "and grounded — never invent prices, rooms, or amenities not in the context. "
            "If the guest asks for a booking, encourage them to use the form on this page. "
            "If you don't know something, say so and offer to forward the question to "
            "reception. Do NOT use markdown, headings, or bullet lists.\n\n"
            f"HOTEL CONTEXT:\n{hotel_ctx}"
        )
        history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[:-1]) if len(history) > 1 else ""
        full_system = f"{sys_prompt}\n\nRecent conversation:\n{history_text}" if history_text else sys_prompt

        try:
            llm = LlmChat(
                api_key=api_key, session_id=f"concierge-{session_id}",
                system_message=full_system,
            ).with_model("openai", "gpt-5.2")
            reply = await llm.send_message(UserMessage(text=msg))
            reply = (reply or "").strip()
        except Exception as e:
            logger.exception("Concierge LLM failed: %s", e)
            reply = ("I'm having trouble reaching our knowledge base. "
                     "Please use the booking form or contact reception directly.")
            assistant_doc = {"id": str(uuid.uuid4()), "session_id": session_id,
                             "property_id": property_id, "role": "assistant",
                             "content": reply, "created_at": now_iso,
                             "fallback": True, "error": str(e)[:200]}
            await db.concierge_chats.insert_one(dict(assistant_doc))
            return {"reply": reply, "session_id": session_id, "fallback": True,
                    "suggestions": ["Book a room", "Check-in time", "WiFi info"]}

        assistant_doc = {"id": str(uuid.uuid4()), "session_id": session_id,
                         "property_id": property_id, "role": "assistant",
                         "content": reply, "created_at": now_iso}
        await db.concierge_chats.insert_one(dict(assistant_doc))

        # Suggested follow-up chips (heuristic; cheap and good UX)
        suggestions = []
        low = msg.lower()
        if "room" in low or "book" in low or "rezerv" in low:
            suggestions = ["What's included?", "Is there parking?", "Cancellation policy"]
        elif "wifi" in low or "internet" in low:
            suggestions = ["Pool / spa hours", "Breakfast included?", "Late check-in"]
        elif "check" in low or "in" in low or "out" in low:
            suggestions = ["Early check-in?", "Luggage storage", "Airport transfer"]
        else:
            suggestions = ["Show me the rooms", "Local recommendations", "Talk to reception"]

        return {"reply": reply, "session_id": session_id, "suggestions": suggestions, "fallback": False}

    @router.get("/concierge/{property_id}/history")
    async def history(property_id: str, session_id: str = ""):
        if not session_id:
            return {"messages": []}
        msgs = await db.concierge_chats.find(
            {"property_id": property_id, "session_id": session_id},
            {"_id": 0, "role": 1, "content": 1, "created_at": 1}
        ).sort("created_at", 1).to_list(100)
        return {"messages": msgs}

    return router
