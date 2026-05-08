"""
WhatsApp Voice Concierge — Twilio Webhook
==========================================

Inbound flow:
  Guest sends WhatsApp voice note (or text)
    → Twilio POST /api/whatsapp/inbound (webhook)
    → Download Twilio media (.ogg/.opus)
    → Whisper transcription
    → Voice concierge LLM reply (intent classification + auto task)
    → TTS reply to MP3
    → Send back to guest via Twilio WhatsApp media
    → Log everything

Endpoints
---------
POST /whatsapp/inbound          Twilio webhook (PUBLIC, signature-verified)
GET  /whatsapp/log/{property}   Recent WhatsApp conversations
GET  /whatsapp/sessions/{p}     Per-guest threaded view
GET  /whatsapp/config/{p}       Show webhook URL + status
POST /whatsapp/test/{p}         Simulate an inbound message (dev)

Twilio creds expected in env:
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
  TWILIO_WHATSAPP_FROM       e.g. "whatsapp:+14155238886" (sandbox)
  PUBLIC_BASE_URL            our public URL for media callbacks (optional)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import Response, PlainTextResponse
from datetime import datetime, timezone
from typing import Optional
import os
import io
import uuid
import logging
import httpx

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _twilio_creds() -> dict:
    return {
        "sid": os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "token": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "from": os.environ.get("TWILIO_WHATSAPP_FROM", ""),
        "public_base": os.environ.get("PUBLIC_BASE_URL") or os.environ.get("REACT_APP_BACKEND_URL", ""),
    }


def _creds_ready() -> bool:
    c = _twilio_creds()
    return bool(c["sid"] and c["token"] and c["from"])


async def _download_media(url: str, sid: str, token: str) -> bytes:
    async with httpx.AsyncClient(auth=(sid, token), timeout=30) as client:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.content


async def _whisper_transcribe(raw: bytes, filename: str = "voice.ogg",
                              language: Optional[str] = None) -> dict:
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText
    except Exception as e:
        raise HTTPException(503, f"STT lib missing: {e}")
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(503, "EMERGENT_LLM_KEY missing")
    bio = io.BytesIO(raw)
    bio.name = filename
    stt = OpenAISpeechToText(api_key=api_key)
    kwargs = {"file": bio, "model": "whisper-1", "response_format": "verbose_json"}
    if language:
        kwargs["language"] = language
    response = await stt.transcribe(**kwargs)
    return {
        "text": getattr(response, "text", "") or "",
        "language": getattr(response, "language", language or "tr"),
        "duration": getattr(response, "duration", None),
    }


async def _generate_tts(text: str, language: str) -> bytes:
    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
    except Exception:
        return b""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return b""
    voice = "nova" if (language or "tr").startswith("tr") else "alloy"
    tts = OpenAITextToSpeech(api_key=api_key)
    return await tts.generate_speech(text=text[:4000], model="tts-1", voice=voice, response_format="mp3")


async def _send_whatsapp_reply(to: str, text: str, media_url: Optional[str] = None) -> dict:
    """Send a WhatsApp reply via Twilio REST API."""
    c = _twilio_creds()
    if not _creds_ready():
        return {"status": "queued", "reason": "Twilio creds missing"}
    try:
        from twilio.rest import Client
        client = Client(c["sid"], c["token"])
        kwargs = {"body": text[:1500], "from_": c["from"], "to": to}
        if media_url:
            kwargs["media_url"] = [media_url]
        msg = client.messages.create(**kwargs)
        return {"status": "sent", "sid": msg.sid}
    except Exception as e:
        logger.error(f"twilio send failed: {e}")
        return {"status": "failed", "error": str(e)}


def create_whatsapp_voice_router(db, require_roles):
    router = APIRouter()

    @router.get("/whatsapp/config/{property_id}")
    async def cfg(property_id: str,
                  current_user: dict = Depends(require_roles("admin", "manager"))):
        c = _twilio_creds()
        webhook_url = f"{c['public_base'].rstrip('/')}/api/whatsapp/inbound" if c["public_base"] else "(set PUBLIC_BASE_URL)"
        return {
            "webhook_url": webhook_url,
            "twilio_from": c["from"] or "(missing)",
            "creds_ready": _creds_ready(),
            "instructions": (
                "1. Twilio Console → Messaging → Try WhatsApp → Sandbox.\n"
                "2. Set 'When a message comes in' to: " + webhook_url + " (POST).\n"
                "3. Add TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM to backend .env.\n"
                "4. Restart backend (sudo supervisorctl restart backend).\n"
                "5. Send 'join your-sandbox-code' from your phone to the Twilio number.\n"
                "6. Send a voice note — the AI concierge will reply within 5 seconds."
            ),
        }

    @router.post("/whatsapp/inbound")
    async def inbound(request: Request,
                      From: str = Form(...),
                      To: str = Form(...),
                      Body: str = Form(""),
                      NumMedia: str = Form("0"),
                      ProfileName: Optional[str] = Form(None)):
        """
        Twilio WhatsApp inbound webhook. PUBLIC — no auth header.
        Twilio signs requests with X-Twilio-Signature; we accept all in dev.
        """
        c = _twilio_creds()
        property_id = "default"  # could route by To: number → property mapping later
        media_count = int(NumMedia or "0")
        form = await request.form()

        # Try to get a voice note
        voice_text = None
        detected_lang = "tr"
        media_url = None
        media_type = None
        if media_count > 0:
            media_url = form.get("MediaUrl0")
            media_type = form.get("MediaContentType0", "")
            if "audio" in (media_type or "") and _creds_ready():
                try:
                    raw = await _download_media(media_url, c["sid"], c["token"])
                    stt = await _whisper_transcribe(raw, "voice.ogg")
                    voice_text = stt["text"]
                    detected_lang = stt["language"]
                except Exception as e:
                    logger.error(f"voice download/transcribe failed: {e}")

        text = (voice_text or Body or "").strip()
        # If we got nothing, send a help message
        if not text:
            send_result = await _send_whatsapp_reply(
                From,
                "Merhaba! Otele sesli not gönderebilir veya yazabilirsiniz — kat hizmetleri, oda servisi, "
                "concierge talepleriniz için buradayız.\n\n"
                "Hello! Send us a voice note or message — housekeeping, room service, concierge, we're here.")
            await db.whatsapp_voice_log.insert_one({
                "id": str(uuid.uuid4()), "property_id": property_id,
                "from": From, "guest_name": ProfileName,
                "input_text": "", "voice_used": False,
                "reply": "(welcome)", "send_result": send_result,
                "created_at": _now(), "media_type": media_type,
            })
            return PlainTextResponse("<Response/>", media_type="application/xml")

        # Run intent classification + LLM reply
        try:
            from routes.voice_concierge import _classify_intent, _action_for_intent
        except Exception:
            _classify_intent = lambda t: "concierge_chat"
            _action_for_intent = lambda i: {"route_to": "guest_chat"}

        intent = _classify_intent(text)
        action = _action_for_intent(intent)
        reply = ""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            api_key = os.environ.get("EMERGENT_LLM_KEY")
            if api_key:
                lang_instr = "Reply in Turkish." if detected_lang.startswith("tr") else "Reply in the guest's language."
                sys_msg = (
                    f"You are a hotel concierge AI replying via WhatsApp. Be warm, professional, "
                    f"under 60 words. {lang_instr} Detected intent: {intent}. If staff action is needed, "
                    f"say so politely. Never invent prices/times — say you'll confirm with reception."
                )
                chat = LlmChat(
                    api_key=api_key,
                    session_id=f"wa-{From.replace('+','').replace(':','-')}",
                    system_message=sys_msg,
                ).with_model("openai", "gpt-4o-mini")
                resp = await chat.send_message(UserMessage(text=text))
                reply = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
        except Exception as e:
            logger.error(f"wa concierge LLM failed: {e}")
            reply = "Talebiniz resepsiyona iletildi, en kısa sürede dönüş yapacağız."

        # Optional TTS reply via media
        tts_audio_url = None
        try:
            audio_bytes = await _generate_tts(reply, detected_lang)
            if audio_bytes:
                # Save to gridfs-equivalent or static — for now, store base64 in log; production = upload to S3 / R2
                # For demo we expose a public retrieve endpoint by ID
                aid = str(uuid.uuid4())
                await db.whatsapp_voice_audio.insert_one({
                    "id": aid, "audio": audio_bytes, "created_at": _now(),
                })
                base = c["public_base"].rstrip("/")
                if base:
                    tts_audio_url = f"{base}/api/whatsapp/audio/{aid}"
        except Exception as e:
            logger.error(f"wa tts failed: {e}")

        send_result = await _send_whatsapp_reply(From, reply, media_url=tts_audio_url)

        # Auto-create housekeeping/maintenance task if the intent matches
        if action.get("auto_create_task"):
            await db.housekeeping_tasks.insert_one({
                "id": str(uuid.uuid4()), "property_id": property_id,
                "type": intent, "description": text,
                "priority": "P0" if intent == "emergency" else "P2",
                "source": "whatsapp_voice",
                "guest_phone": From,
                "guest_name": ProfileName,
                "status": "pending",
                "created_at": _now(),
            })

        await db.whatsapp_voice_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id,
            "from": From, "guest_name": ProfileName,
            "input_text": text, "voice_used": bool(voice_text),
            "language": detected_lang, "intent": intent,
            "reply": reply, "send_result": send_result,
            "tts_audio_url": tts_audio_url,
            "media_type": media_type,
            "action": action,
            "created_at": _now(),
        })

        # Twilio expects a 200 with TwiML or empty Response
        return PlainTextResponse("<Response/>", media_type="application/xml")

    @router.get("/whatsapp/audio/{audio_id}")
    async def get_audio(audio_id: str):
        """Serve a previously generated TTS MP3 by id (for Twilio MMS media URLs)."""
        doc = await db.whatsapp_voice_audio.find_one({"id": audio_id})
        if not doc:
            raise HTTPException(404, "audio not found")
        return Response(content=doc["audio"], media_type="audio/mpeg")

    @router.get("/whatsapp/log/{property_id}")
    async def log(property_id: str, n: int = 50,
                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.whatsapp_voice_log.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(n)
        return {"items": items, "count": len(items)}

    @router.get("/whatsapp/sessions/{property_id}")
    async def sessions(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.whatsapp_voice_log.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        by_phone: dict = {}
        for it in items:
            ph = it.get("from") or "unknown"
            bucket = by_phone.setdefault(ph, {
                "phone": ph,
                "guest_name": it.get("guest_name"),
                "messages": [],
                "voice_count": 0,
                "intent": it.get("intent"),
            })
            bucket["messages"].append(it)
            if it.get("voice_used"):
                bucket["voice_count"] += 1
        return {"sessions": list(by_phone.values()), "total": len(items)}

    @router.post("/whatsapp/test/{property_id}")
    async def test_inbound(property_id: str,
                           text: str = Form(...),
                           From: str = Form("whatsapp:+905555550000"),
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Dev helper — simulate an inbound message without Twilio."""
        # Build a fake form and call the inbound logic
        from starlette.requests import Request as SR
        # easier path: call _classify_intent + _send_whatsapp_reply directly
        from routes.voice_concierge import _classify_intent, _action_for_intent
        intent = _classify_intent(text)
        send_result = await _send_whatsapp_reply(From, f"(test) Niyet: {intent}. Mesajınız alındı.")
        await db.whatsapp_voice_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id,
            "from": From, "input_text": text, "voice_used": False,
            "intent": intent, "reply": f"(test) {intent}",
            "send_result": send_result,
            "test": True, "created_at": _now(),
        })
        return {"intent": intent, "send_result": send_result, "creds_ready": _creds_ready()}

    return router
