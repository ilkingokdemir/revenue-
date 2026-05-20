"""
Voice Concierge — Whisper STT + LLM Reply
=========================================

End-to-end voice flow:

  1. Mobile/web records audio (webm/mp3/m4a/wav) → POST /voice/transcribe
  2. Whisper transcribes (auto language detect) → returns text
  3. /voice/concierge sends text to GPT-5 → AI concierge reply
  4. Reply is logged so staff can review / take over
  5. Optional: route a request to housekeeping / room service / front desk

Endpoints
---------
POST /voice/transcribe            multipart audio → {text, language, duration}
POST /voice/concierge             {text, session_id, language, guest_name?, room?}
                                  → {reply, intent, action, log_id}
GET  /voice/sessions/{property}   list recent voice sessions
GET  /voice/log/{property}?n=50   raw log entries

Intent routing (regex/keyword based; GPT confirms):
  "towel|extra pillow|cleaning"     → housekeeping
  "room service|breakfast|menu"     → room_service
  "checkout|early check|extend"     → front_desk
  "wifi|internet|password"          → faq
  default                            → concierge_chat
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, List
import io
import os
import re
import uuid
import logging

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConciergeReq(BaseModel):
    text: str
    session_id: Optional[str] = None
    language: Optional[str] = "tr"
    guest_name: Optional[str] = None
    room_number: Optional[str] = None


# ---------------------------------------------------------------------------
# intent classifier (lightweight pre-filter so we don't bill LLM for "wifi password")
# ---------------------------------------------------------------------------
INTENT_RULES = [
    ("housekeeping", r"havlu|temizlik|yastık|battaniye|temizleme|peçete|bornoz|towel|pillow|blanket|cleaning|sheets"),
    ("room_service", r"oda servisi|kahvaltı|menü|yemek|içecek|sipariş|room\s*service|breakfast|menu|drink|food|order"),
    ("front_desk",   r"check.?out|geç çıkış|erken giriş|uzatma|fatura|early|late|extend|bill|invoice|extension"),
    ("faq",          r"wifi|internet|şifre|password|otopark|parking|spa|gym|havuz|pool"),
    ("maintenance",  r"bozuk|çalışmıyor|tamir|arıza|broken|not working|leak|noisy|ses|sıcak|soğuk|hot|cold"),
    ("emergency",    r"yangın|acil|ambulans|polis|fire|emergency|urgent|ambulance|police"),
]


def _classify_intent(text: str) -> str:
    t = (text or "").lower()
    for intent, pattern in INTENT_RULES:
        if re.search(pattern, t):
            return intent
    return "concierge_chat"


def _action_for_intent(intent: str) -> dict:
    """Map an intent to a concrete in-PMS action so the UI can show a CTA."""
    return {
        "housekeeping": {"route_to": "housekeeping", "auto_create_task": True},
        "room_service": {"route_to": "pos_room_service", "auto_create_task": False},
        "front_desk":   {"route_to": "front_desk", "auto_create_task": False},
        "maintenance":  {"route_to": "maintenance", "auto_create_task": True},
        "faq":          {"route_to": "guest_chat", "auto_create_task": False},
        "emergency":    {"route_to": "front_desk", "alert_priority": "P0", "auto_create_task": True},
        "concierge_chat": {"route_to": "guest_chat", "auto_create_task": False},
    }.get(intent, {"route_to": "guest_chat"})


# ---------------------------------------------------------------------------
# router factory
# ---------------------------------------------------------------------------
def create_voice_concierge_router(db, require_roles):
    router = APIRouter()

    @router.post("/voice/transcribe")
    async def transcribe(
        audio: UploadFile = File(...),
        language: Optional[str] = Form(None),
        property_id: Optional[str] = Form("default"),
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "guest")),
    ):
        try:
            from emergentintegrations.llm.openai import OpenAISpeechToText
        except Exception as e:
            raise HTTPException(503, f"STT library missing: {e}")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(503, "EMERGENT_LLM_KEY missing")

        # Read upload — Whisper accepts up to 25 MB of audio
        raw = await audio.read()
        if len(raw) == 0:
            raise HTTPException(400, "empty audio")
        if len(raw) > 25 * 1024 * 1024:
            raise HTTPException(413, "audio > 25MB")

        stt = OpenAISpeechToText(api_key=api_key)
        # Whisper expects a file-like object with a name attribute
        bio = io.BytesIO(raw)
        bio.name = audio.filename or "audio.webm"
        try:
            kwargs = {"file": bio, "model": "whisper-1", "response_format": "verbose_json"}
            if language:
                kwargs["language"] = language
            response = await stt.transcribe(**kwargs)
        except Exception as e:
            logger.error(f"whisper failed: {e}")
            raise HTTPException(502, f"Whisper failed: {e}")

        text = getattr(response, "text", "") or ""
        detected = getattr(response, "language", language or "tr")
        duration = getattr(response, "duration", None)

        # Log
        log_id = str(uuid.uuid4())
        await db.voice_concierge_log.insert_one({
            "id": log_id,
            "property_id": property_id,
            "type": "transcription",
            "text": text,
            "language": detected,
            "duration": duration,
            "audio_size": len(raw),
            "filename": audio.filename,
            "created_by": current_user.get("email"),
            "created_at": _now(),
        })
        return {
            "log_id": log_id,
            "text": text,
            "language": detected,
            "duration": duration,
            "audio_bytes": len(raw),
        }

    @router.post("/voice/concierge")
    async def concierge(req: ConciergeReq,
                        property_id: str = "default",
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "guest"))):
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(400, "empty text")

        intent = _classify_intent(text)
        action = _action_for_intent(intent)
        sid = req.session_id or str(uuid.uuid4())

        reply = ""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            api_key = os.environ.get("EMERGENT_LLM_KEY")
            if api_key:
                lang_instr = "Reply in Turkish." if (req.language or "tr").startswith("tr") else "Reply in the guest's language."
                sys_msg = (
                    f"You are a hotel concierge AI for guests at {property_id}. "
                    f"Be warm, professional, concise (under 60 words). {lang_instr} "
                    f"Detected intent: {intent}. If the request needs staff, say so politely. "
                    f"Never invent prices or times — say you'll confirm with the front desk."
                )
                chat = LlmChat(api_key=api_key, session_id=f"voice-{sid}", system_message=sys_msg) \
                    .with_model("openai", "gpt-4o-mini")
                guest_ctx = ""
                if req.guest_name:
                    guest_ctx += f"Guest: {req.guest_name}. "
                if req.room_number:
                    guest_ctx += f"Room: {req.room_number}. "
                user_msg = UserMessage(text=f"{guest_ctx}{text}")
                resp = await chat.send_message(user_msg)
                reply = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
        except Exception as e:
            logger.error(f"voice concierge LLM failed: {e}")
            reply = "Şu an yapay zeka geçici olarak kullanılamıyor — talebiniz resepsiyona iletildi."

        log_id = str(uuid.uuid4())
        log_doc = {
            "id": log_id,
            "property_id": property_id,
            "session_id": sid,
            "type": "concierge_reply",
            "guest_name": req.guest_name,
            "room_number": req.room_number,
            "language": req.language,
            "input_text": text,
            "reply": (reply or "").strip(),
            "intent": intent,
            "action": action,
            "created_by": current_user.get("email"),
            "created_at": _now(),
        }
        await db.voice_concierge_log.insert_one(dict(log_doc))

        # Auto-create task for housekeeping/maintenance/emergency
        if action.get("auto_create_task"):
            try:
                await db.housekeeping_tasks.insert_one({
                    "id": str(uuid.uuid4()),
                    "property_id": property_id,
                    "room_number": req.room_number,
                    "type": intent,
                    "description": text,
                    "priority": "P0" if intent == "emergency" else "P2",
                    "source": "voice_concierge",
                    "status": "pending",
                    "created_at": _now(),
                })
            except Exception as e:
                logger.error(f"task auto-create failed: {e}")

        log_doc.pop("_id", None)
        return {"reply": reply, "intent": intent, "action": action, "session_id": sid, "log_id": log_id}

    @router.post("/voice/tts")
    async def tts(req: ConciergeReq,
                  property_id: str = "default",
                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "guest"))):
        """Convert reply text to speech via OpenAI TTS — returns audio/mpeg bytes."""
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(400, "empty text")
        if len(text) > 4000:
            raise HTTPException(413, "text too long (max 4000 chars)")
        try:
            from emergentintegrations.llm.openai import OpenAITextToSpeech
        except Exception as e:
            raise HTTPException(503, f"TTS library missing: {e}")
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(503, "EMERGENT_LLM_KEY missing")

        # Pick voice by language — alloy/nova are multilingual; OpenAI supports 50+ languages
        voice = "nova" if (req.language or "tr").startswith("tr") else "alloy"
        try:
            tts_client = OpenAITextToSpeech(api_key=api_key)
            audio_bytes = await tts_client.generate_speech(
                text=text,
                model="tts-1",
                voice=voice,
                response_format="mp3",
            )
        except Exception as e:
            logger.error(f"tts failed: {e}")
            raise HTTPException(502, f"TTS failed: {e}")

        # Log
        await db.voice_concierge_log.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "type": "tts",
            "text": text,
            "language": req.language,
            "voice": voice,
            "audio_size": len(audio_bytes),
            "created_by": current_user.get("email"),
            "created_at": _now(),
        })

        from fastapi.responses import Response
        return Response(content=audio_bytes, media_type="audio/mpeg",
                        headers={"Content-Disposition": 'inline; filename="reply.mp3"'})

    @router.get("/voice/sessions/{property_id}")
    async def sessions(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.voice_concierge_log.find(
            {"property_id": property_id, "type": "concierge_reply"}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
        # Group by session_id
        by_session: dict = {}
        for it in items:
            sid = it.get("session_id") or it["id"]
            bucket = by_session.setdefault(sid, {"session_id": sid, "messages": [], "guest_name": it.get("guest_name"), "room": it.get("room_number"), "intent": it.get("intent")})
            bucket["messages"].append(it)
        return {"sessions": list(by_session.values())[:50], "count": len(items)}

    @router.get("/voice/log/{property_id}")
    async def log(property_id: str, n: int = 50,
                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.voice_concierge_log.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(n)
        return {"items": items, "count": len(items)}

    @router.get("/voice/stats/{property_id}")
    async def stats(property_id: str,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.voice_concierge_log.find(
            {"property_id": property_id, "type": "concierge_reply"}, {"_id": 0}
        ).to_list(2000)
        out = {"total": len(items), "by_intent": {}}
        for it in items:
            intent = it.get("intent") or "unknown"
            out["by_intent"][intent] = out["by_intent"].get(intent, 0) + 1
        return out

    return router
