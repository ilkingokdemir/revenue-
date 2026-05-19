"""
Chatbot Automation — Cloudbeds Guest Experience parity.

Provides FAQ/intent matching + sentiment/keyword triggers for guest chat. The
chatbot is a configuration store; matching happens via `POST /test` which can
be called by Guest Chat / Live Chat front-ends as guest messages arrive.

Collections:
  - chatbot_settings        per-property settings (enabled, translation, tone)
  - chatbot_intents         intent → trigger phrases + action
  - chatbot_keywords        exact-word keyword commands
  - chatbot_sentiment_acts  sentiment → action mapping
  - chatbot_content_sources URL/tone for auto-generated FAQs
  - chatbot_runs            audit log of matches

Auto-generation: `POST /content-sources/generate` calls GPT-4o-mini to scrape
the user-provided URL and produce 10 FAQ intents in the chosen tone (TR/EN).

Action types match Automated Messages: create_ticket, reply_guest,
notify_team_chat, send_email, send_sms.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import os
import re
import uuid
import json
import logging

logger = logging.getLogger(__name__)


VALID_ACTIONS = {"create_ticket", "reply_guest", "notify_team_chat", "send_email", "send_sms"}
VALID_SENTIMENTS = {"any", "positive", "negative", "neutral"}
VALID_TONES = {"professional", "friendly", "casual", "polished", "humorous"}

DEFAULT_SETTINGS = {
    "enabled": True,
    "guest_replies_live_chat": True,
    "guest_replies_guest_chat": True,
    "translation_inbound": False,
    "translation_outbound": False,
    "default_tone": "friendly",
    "default_language": "tr",
    "fallback_message": "Mesajınızı aldık, en kısa sürede ekibimiz yanıtlayacak.",
    "handoff_keywords": ["agent", "human", "live", "operatör", "insan"],
}

POSITIVE_WORDS = {"great", "perfect", "love", "amazing", "harika", "mükemmel", "süper", "teşekkür", "thanks", "thank"}
NEGATIVE_WORDS = {"bad", "terrible", "broken", "kötü", "berbat", "şikayet", "complaint", "refund", "iade"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_sentiment(text: str) -> str:
    t = (text or "").lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    if neg > pos and neg > 0:
        return "negative"
    if pos > 0:
        return "positive"
    return "neutral"


def _match_intent(text: str, intents: list) -> Optional[dict]:
    """Score each intent by overlap of trigger phrases. Return best match >= 0.3."""
    t = (text or "").lower()
    best = None
    best_score = 0.0
    for intent in intents:
        if not intent.get("enabled", True):
            continue
        phrases = intent.get("trigger_phrases") or []
        if not phrases:
            continue
        hits = 0
        for p in phrases:
            ps = (p or "").lower().strip()
            if not ps:
                continue
            if ps in t:
                hits += len(ps.split())
        # Score = hit-token count / total trigger-token count (capped)
        total_tokens = sum(len((p or "").split()) for p in phrases) or 1
        score = hits / total_tokens
        if score > best_score and score >= 0.3:
            best_score = score
            best = {**intent, "_score": round(score, 2)}
    return best


def _match_keyword(text: str, keywords: list) -> Optional[dict]:
    """Exact word/phrase match on guest text."""
    t = (text or "").lower()
    for kw in keywords:
        if not kw.get("enabled", True):
            continue
        cmd = (kw.get("command") or "").lower().strip()
        if cmd and (cmd == t.strip() or f" {cmd} " in f" {t} "):
            return kw
    return None


def create_chatbot_router(db, require_roles):
    router = APIRouter()

    # ───────────────────────── Settings ────────────────────────────
    @router.get("/chatbot/{property_id}/settings")
    async def get_settings(property_id: str,
                            _u: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.chatbot_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            doc = {"property_id": property_id, **DEFAULT_SETTINGS}
        for k, v in DEFAULT_SETTINGS.items():
            doc.setdefault(k, v)
        return doc

    @router.put("/chatbot/{property_id}/settings")
    async def put_settings(property_id: str, data: Dict,
                            _u: dict = Depends(require_roles("admin", "manager"))):
        tone = (data.get("default_tone") or "friendly").lower()
        if tone not in VALID_TONES:
            tone = "friendly"
        payload = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", True)),
            "guest_replies_live_chat": bool(data.get("guest_replies_live_chat", True)),
            "guest_replies_guest_chat": bool(data.get("guest_replies_guest_chat", True)),
            "translation_inbound": bool(data.get("translation_inbound", False)),
            "translation_outbound": bool(data.get("translation_outbound", False)),
            "default_tone": tone,
            "default_language": (data.get("default_language") or "tr").lower()[:5],
            "fallback_message": (data.get("fallback_message") or DEFAULT_SETTINGS["fallback_message"])[:500],
            "handoff_keywords": data.get("handoff_keywords") or DEFAULT_SETTINGS["handoff_keywords"],
            "updated_at": _now(),
        }
        await db.chatbot_settings.update_one(
            {"property_id": property_id}, {"$set": payload}, upsert=True
        )
        return payload

    # ───────────────────────── Intents ─────────────────────────────
    @router.get("/chatbot/{property_id}/intents")
    async def list_intents(property_id: str, category: Optional[str] = None,
                            _u: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id}
        if category:
            q["category"] = category
        docs = await db.chatbot_intents.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"property_id": property_id, "count": len(docs), "items": docs}

    @router.post("/chatbot/{property_id}/intents")
    async def create_intent(property_id: str, data: Dict,
                             _u: dict = Depends(require_roles("admin", "manager"))):
        name = (data.get("name") or "").strip()
        phrases = data.get("trigger_phrases") or []
        action_type = (data.get("action_type") or "reply_guest").lower()
        if not name or not phrases:
            raise HTTPException(400, "name and trigger_phrases are required")
        if action_type not in VALID_ACTIONS:
            raise HTTPException(400, f"action_type must be one of {VALID_ACTIONS}")
        sentiment = (data.get("sentiment") or "any").lower()
        if sentiment not in VALID_SENTIMENTS:
            sentiment = "any"
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "name": name,
            "category": (data.get("category") or "custom").strip(),
            "trigger_phrases": [str(p).strip() for p in phrases if str(p).strip()],
            "sentiment": sentiment,
            "action_type": action_type,
            "reply_text": (data.get("reply_text") or "").strip()[:1000],
            "reply_buttons": data.get("reply_buttons") or [],
            "ticket_department": (data.get("ticket_department") or "").strip(),
            "ticket_title": (data.get("ticket_title") or "").strip(),
            "team_channel": (data.get("team_channel") or "").strip(),
            "notify_email": (data.get("notify_email") or "").strip(),
            "notify_phone": (data.get("notify_phone") or "").strip(),
            "enabled": bool(data.get("enabled", True)),
            "created_at": _now(),
        }
        await db.chatbot_intents.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/chatbot/intents/{intent_id}")
    async def update_intent(intent_id: str, updates: Dict,
                             _u: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = _now()
        await db.chatbot_intents.update_one({"id": intent_id}, {"$set": updates})
        doc = await db.chatbot_intents.find_one({"id": intent_id}, {"_id": 0})
        return doc or {}

    @router.delete("/chatbot/intents/{intent_id}")
    async def delete_intent(intent_id: str,
                             _u: dict = Depends(require_roles("admin", "manager"))):
        await db.chatbot_intents.delete_one({"id": intent_id})
        return {"status": "deleted"}

    # ───────────────────────── Keywords ────────────────────────────
    @router.get("/chatbot/{property_id}/keywords")
    async def list_keywords(property_id: str,
                             _u: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.chatbot_keywords.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        return {"property_id": property_id, "count": len(docs), "items": docs}

    @router.post("/chatbot/{property_id}/keywords")
    async def create_keyword(property_id: str, data: Dict,
                              _u: dict = Depends(require_roles("admin", "manager"))):
        cmd = (data.get("command") or "").strip().lower()
        if not cmd:
            raise HTTPException(400, "command is required")
        action_type = (data.get("action_type") or "reply_guest").lower()
        if action_type not in VALID_ACTIONS:
            raise HTTPException(400, f"action_type must be one of {VALID_ACTIONS}")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "command": cmd,
            "sentiment": (data.get("sentiment") or "any").lower(),
            "action_type": action_type,
            "reply_text": (data.get("reply_text") or "").strip()[:1000],
            "enabled": bool(data.get("enabled", True)),
            "created_at": _now(),
        }
        await db.chatbot_keywords.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/chatbot/keywords/{keyword_id}")
    async def delete_keyword(keyword_id: str,
                              _u: dict = Depends(require_roles("admin", "manager"))):
        await db.chatbot_keywords.delete_one({"id": keyword_id})
        return {"status": "deleted"}

    # ─────────────────────── Sentiment actions ─────────────────────
    @router.get("/chatbot/{property_id}/sentiment-actions")
    async def list_sentiment_actions(property_id: str,
                                      _u: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.chatbot_sentiment_acts.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        return {"property_id": property_id, "count": len(docs), "items": docs}

    @router.post("/chatbot/{property_id}/sentiment-actions")
    async def create_sentiment_action(property_id: str, data: Dict,
                                       _u: dict = Depends(require_roles("admin", "manager"))):
        sentiment = (data.get("sentiment") or "negative").lower()
        if sentiment not in {"positive", "negative"}:
            raise HTTPException(400, "sentiment must be 'positive' or 'negative'")
        action_type = (data.get("action_type") or "notify_team_chat").lower()
        if action_type not in VALID_ACTIONS:
            raise HTTPException(400, f"action_type must be one of {VALID_ACTIONS}")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "sentiment": sentiment,
            "action_type": action_type,
            "reply_text": (data.get("reply_text") or "").strip()[:500],
            "team_channel": (data.get("team_channel") or "").strip(),
            "enabled": bool(data.get("enabled", True)),
            "created_at": _now(),
        }
        await db.chatbot_sentiment_acts.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/chatbot/sentiment-actions/{action_id}")
    async def delete_sentiment_action(action_id: str,
                                       _u: dict = Depends(require_roles("admin", "manager"))):
        await db.chatbot_sentiment_acts.delete_one({"id": action_id})
        return {"status": "deleted"}

    # ────────────────────── Content sources / AI ───────────────────
    @router.post("/chatbot/{property_id}/content-sources/generate")
    async def generate_from_source(property_id: str, data: Dict,
                                    _u: dict = Depends(require_roles("admin", "manager"))):
        """Use GPT-4o-mini to generate 10 FAQ intents in the chosen tone."""
        url = (data.get("url") or "").strip()
        tone = (data.get("tone") or "friendly").lower()
        if tone not in VALID_TONES:
            tone = "friendly"
        language = (data.get("language") or "tr").lower()
        if not url:
            raise HTTPException(400, "url required (hotel website or TripAdvisor URL)")

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(503, "Emergent LLM key missing — cannot generate")

        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
        except Exception as e:
            raise HTTPException(503, f"emergentintegrations not available: {e}")

        prompt = (
            f"You generate FAQs for hotel guest chatbots.\n"
            f"Source URL: {url}\n"
            f"Target language: {language}\n"
            f"Tone: {tone}\n\n"
            f"Produce a JSON object: {{\"intents\":[{{\"name\":\"...\","
            f"\"trigger_phrases\":[\"...\",\"...\"],\"reply_text\":\"...\"}}, ...]}} "
            f"with 10 most-common hotel guest FAQs (wifi, breakfast, check-in time, "
            f"parking, late checkout, airport transfer, pets, kids, gym, towels). "
            f"Each intent must have 3-6 short trigger phrases and a reply in the chosen tone+language. "
            f"Return ONLY valid JSON, no markdown."
        )
        try:
            chat = LlmChat(
                api_key=api_key,
                session_id=f"chatbot-gen-{uuid.uuid4().hex[:8]}",
                system_message="You are a hospitality chatbot designer. Always return valid JSON.",
            ).with_model("openai", "gpt-4o-mini")
            reply = await chat.send_message(UserMessage(text=prompt))
            raw = (reply or "").strip()
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("no JSON in response")
            blob = json.loads(raw[start:end + 1])
            intents = blob.get("intents") or []
        except Exception as exc:
            logger.exception("chatbot generate failed: %s", exc)
            raise HTTPException(502, f"AI generation failed: {exc}")

        created = 0
        for it in intents[:10]:
            name = (it.get("name") or "").strip()
            phrases = it.get("trigger_phrases") or []
            reply_text = (it.get("reply_text") or "").strip()
            if not name or not phrases or not reply_text:
                continue
            doc = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "name": name,
                "category": "most_popular",
                "trigger_phrases": [str(p).strip() for p in phrases if str(p).strip()][:8],
                "sentiment": "any",
                "action_type": "reply_guest",
                "reply_text": reply_text[:1000],
                "reply_buttons": [],
                "enabled": True,
                "source_url": url,
                "tone": tone,
                "created_at": _now(),
                "created_by": "ai-generator",
            }
            await db.chatbot_intents.insert_one(doc)
            created += 1

        await db.chatbot_content_sources.update_one(
            {"property_id": property_id, "url": url},
            {"$set": {
                "property_id": property_id,
                "url": url,
                "tone": tone,
                "language": language,
                "last_generated_at": _now(),
                "intents_created": created,
            }},
            upsert=True,
        )
        return {"created": created, "url": url, "tone": tone}

    @router.get("/chatbot/{property_id}/content-sources")
    async def list_content_sources(property_id: str,
                                    _u: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.chatbot_content_sources.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        return {"property_id": property_id, "count": len(docs), "items": docs}

    # ───────────────────────── Shared matcher ──────────────────────
    async def _match_message(property_id: str, text: str, session_id: Optional[str] = None,
                              source: str = "internal") -> Dict:
        """Core chatbot matching used by both /test (admin) and /public/.../chat (guest)."""
        text = (text or "").strip()
        if not text:
            return {"matched": False, "reason": "empty text"}
        settings = await db.chatbot_settings.find_one({"property_id": property_id}, {"_id": 0}) or DEFAULT_SETTINGS
        if not settings.get("enabled", True):
            return {"matched": False, "reason": "chatbot disabled"}

        # Handoff keywords → bail out to human
        handoff = [k.lower() for k in (settings.get("handoff_keywords") or [])]
        tl = text.lower()
        if any(k in tl for k in handoff):
            run = {"id": str(uuid.uuid4()), "property_id": property_id, "text": text,
                   "match_type": "handoff", "action_type": None, "source": source,
                   "session_id": session_id, "created_at": _now()}
            await db.chatbot_runs.insert_one(run)
            return {"matched": True, "match_type": "handoff",
                    "reply_text": "Sizi temsilcimize bağlıyorum…", "action_type": "handoff"}

        sentiment = _detect_sentiment(text)

        # 1) Keywords (exact)
        kws = await db.chatbot_keywords.find({"property_id": property_id, "enabled": True}, {"_id": 0}).to_list(200)
        kw_match = _match_keyword(text, kws)
        if kw_match:
            run = {"id": str(uuid.uuid4()), "property_id": property_id, "text": text,
                   "match_type": "keyword", "match_id": kw_match["id"],
                   "action_type": kw_match["action_type"], "sentiment": sentiment,
                   "source": source, "session_id": session_id, "created_at": _now()}
            await db.chatbot_runs.insert_one(run)
            return {"matched": True, "match_type": "keyword",
                    "reply_text": kw_match.get("reply_text"),
                    "action_type": kw_match.get("action_type"),
                    "intent": kw_match, "sentiment": sentiment}

        # 2) Intents (phrase overlap)
        intents = await db.chatbot_intents.find({"property_id": property_id, "enabled": True}, {"_id": 0}).to_list(500)
        eligible = [i for i in intents if i.get("sentiment", "any") in ("any", sentiment)]
        intent_match = _match_intent(text, eligible)
        if intent_match:
            run = {"id": str(uuid.uuid4()), "property_id": property_id, "text": text,
                   "match_type": "intent", "match_id": intent_match["id"],
                   "action_type": intent_match["action_type"], "sentiment": sentiment,
                   "score": intent_match.get("_score"),
                   "source": source, "session_id": session_id, "created_at": _now()}
            await db.chatbot_runs.insert_one(run)
            return {"matched": True, "match_type": "intent",
                    "reply_text": intent_match.get("reply_text"),
                    "action_type": intent_match.get("action_type"),
                    "reply_buttons": intent_match.get("reply_buttons") or [],
                    "intent": intent_match, "sentiment": sentiment}

        # 3) Sentiment fallback action
        sent_acts = await db.chatbot_sentiment_acts.find({"property_id": property_id, "enabled": True}, {"_id": 0}).to_list(20)
        sa = next((s for s in sent_acts if s.get("sentiment") == sentiment), None)
        if sa:
            run = {"id": str(uuid.uuid4()), "property_id": property_id, "text": text,
                   "match_type": "sentiment", "match_id": sa["id"],
                   "action_type": sa["action_type"], "sentiment": sentiment,
                   "source": source, "session_id": session_id, "created_at": _now()}
            await db.chatbot_runs.insert_one(run)
            return {"matched": True, "match_type": "sentiment",
                    "reply_text": sa.get("reply_text"),
                    "action_type": sa.get("action_type"),
                    "intent": sa, "sentiment": sentiment}

        # No match → fallback
        run = {"id": str(uuid.uuid4()), "property_id": property_id, "text": text,
               "match_type": "none", "sentiment": sentiment,
               "source": source, "session_id": session_id, "created_at": _now()}
        await db.chatbot_runs.insert_one(run)
        return {"matched": False, "match_type": "none", "sentiment": sentiment,
                "reply_text": settings.get("fallback_message"),
                "fallback_message": settings.get("fallback_message")}

    async def _start_handoff_session(property_id: str, session_id: str, reason: str = "user-handoff") -> None:
        """Mark a session as active in chatbot_handoff_sessions. Idempotent."""
        await db.chatbot_handoff_sessions.update_one(
            {"property_id": property_id, "session_id": session_id},
            {"$set": {
                "property_id": property_id, "session_id": session_id,
                "reason": reason, "status": "active",
                "last_message_at": _now(),
            }, "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "started_at": _now(),
                "unread_count": 0,
            }},
            upsert=True,
        )
        # Inc unread for handoff trigger event as well (no-op if just-created)
        await db.chatbot_handoff_sessions.update_one(
            {"property_id": property_id, "session_id": session_id, "status": "active"},
            {"$inc": {"unread_count": 1}},
        )

    async def _append_handoff_message(property_id: str, session_id: str,
                                       text: str, sender: str, sender_name: str = "") -> Dict:
        """Append a message in chatbot_handoff_messages. sender ∈ {guest, staff, system}."""
        msg = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "session_id": session_id,
            "sender": sender,
            "sender_name": sender_name,
            "text": text[:2000],
            "created_at": _now(),
        }
        await db.chatbot_handoff_messages.insert_one(msg)
        # Update session unread + last_message_at
        inc = {"unread_count": 1} if sender == "guest" else {"staff_unread_count": 1} if sender == "staff" else {}
        upd = {"$set": {"last_message_at": _now(), "last_message_text": text[:160], "last_sender": sender}}
        if inc:
            upd["$inc"] = inc
        await db.chatbot_handoff_sessions.update_one(
            {"property_id": property_id, "session_id": session_id},
            upd,
        )
        msg.pop("_id", None)
        return msg

    # ───────────────────────── Test / Match ────────────────────────
    @router.post("/chatbot/{property_id}/test")
    async def test_chatbot(property_id: str, data: Dict,
                            _u: dict = Depends(require_roles("admin", "manager"))):
        """Admin-only simulation. UIs call this from settings → live tester."""
        return await _match_message(property_id, data.get("text", ""), source="admin-test")

    # ──────────────────── PUBLIC widget endpoint ───────────────────
    @router.get("/public/chatbot/{property_id}/info")
    async def public_chatbot_info(property_id: str):
        """Public info for embed widget — name, currency, language, fallback msg."""
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1, "currency": 1})
        if not prop:
            raise HTTPException(404, "property not found")
        settings = await db.chatbot_settings.find_one({"property_id": property_id}, {"_id": 0}) or DEFAULT_SETTINGS
        if not settings.get("enabled", True):
            raise HTTPException(403, "chatbot disabled for this property")
        return {
            "property_id": property_id,
            "property_name": prop.get("name", "Hotel"),
            "language": settings.get("default_language", "tr"),
            "greeting": "Merhaba! Size nasıl yardımcı olabilirim?",
            "fallback_message": settings.get("fallback_message"),
        }

    @router.post("/public/chatbot/{property_id}/chat")
    async def public_chat(property_id: str, data: Dict):
        """PUBLIC (no auth) endpoint for the embedded Guest Chat widget. Rate-limited per session.

        Body: { text: str, session_id: str (uuid generated by widget) }
        Returns: { matched, match_type, reply_text, action_type, sentiment?, in_handoff? }

        If session is already in active handoff, the message is appended to handoff thread
        instead of matched — `in_handoff: true` so the widget switches to polling mode.
        """
        text = (data.get("text") or "").strip()
        session_id = (data.get("session_id") or "").strip()
        if not text:
            raise HTTPException(400, "text required")
        if not session_id:
            session_id = str(uuid.uuid4())
        if len(text) > 1000:
            raise HTTPException(400, "text too long (max 1000 chars)")

        # Per-session rate limit: 20 messages / 5 minutes
        five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        recent_count = await db.chatbot_runs.count_documents({
            "session_id": session_id, "created_at": {"$gte": five_min_ago},
        })
        if recent_count > 20:
            raise HTTPException(429, "rate limit exceeded — please wait a few minutes")

        # If session is already in handoff → append to thread, don't re-match
        existing = await db.chatbot_handoff_sessions.find_one(
            {"property_id": property_id, "session_id": session_id, "status": "active"},
            {"_id": 0, "id": 1},
        )
        if existing:
            await _append_handoff_message(property_id, session_id, text, "guest")
            return {
                "matched": True,
                "match_type": "handoff",
                "in_handoff": True,
                "reply_text": "Mesajınız temsilciye iletildi. Birazdan yanıt alacaksınız.",
                "session_id": session_id,
            }

        result = await _match_message(property_id, text, session_id=session_id, source="widget")
        out = {
            "matched": result.get("matched"),
            "match_type": result.get("match_type"),
            "reply_text": result.get("reply_text") or result.get("fallback_message"),
            "action_type": result.get("action_type"),
            "sentiment": result.get("sentiment"),
            "reply_buttons": result.get("reply_buttons") or [],
            "session_id": session_id,
            "in_handoff": False,
        }

        # If match_type was handoff, persist the guest's original message in thread + open session
        if result.get("match_type") == "handoff":
            await _start_handoff_session(property_id, session_id, reason="user-handoff-keyword")
            await _append_handoff_message(property_id, session_id, text, "guest")
            out["in_handoff"] = True
        return out

    @router.get("/public/chatbot/{property_id}/handoff-messages")
    async def public_handoff_poll(property_id: str, session_id: str, since: Optional[str] = None):
        """Public polling endpoint for the widget when in handoff mode.
        Returns staff messages since `since` ISO timestamp (or all from session start)."""
        if not session_id:
            raise HTTPException(400, "session_id required")
        q = {"property_id": property_id, "session_id": session_id, "sender": {"$in": ["staff", "system"]}}
        if since:
            q["created_at"] = {"$gt": since}
        msgs = await db.chatbot_handoff_messages.find(q, {"_id": 0}).sort("created_at", 1).to_list(50)
        sess = await db.chatbot_handoff_sessions.find_one(
            {"property_id": property_id, "session_id": session_id}, {"_id": 0, "status": 1},
        )
        return {"messages": msgs, "session_status": (sess or {}).get("status", "active"),
                "now": _now()}

    # ─────────────────── ADMIN handoff inbox ──────────────────────
    @router.get("/chatbot/{property_id}/handoff/sessions")
    async def list_handoff_sessions(property_id: str, status: str = "active",
                                     _u: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id}
        if status and status != "all":
            q["status"] = status
        rows = await db.chatbot_handoff_sessions.find(q, {"_id": 0})\
            .sort("last_message_at", -1).limit(200).to_list(200)
        return {"property_id": property_id, "count": len(rows), "items": rows}

    @router.get("/chatbot/{property_id}/handoff/sessions/{session_id}/messages")
    async def get_handoff_messages(property_id: str, session_id: str,
                                    _u: dict = Depends(require_roles("admin", "manager"))):
        # Reset guest-unread counter when staff opens the thread
        await db.chatbot_handoff_sessions.update_one(
            {"property_id": property_id, "session_id": session_id},
            {"$set": {"unread_count": 0}},
        )
        msgs = await db.chatbot_handoff_messages.find(
            {"property_id": property_id, "session_id": session_id}, {"_id": 0},
        ).sort("created_at", 1).to_list(500)
        sess = await db.chatbot_handoff_sessions.find_one(
            {"property_id": property_id, "session_id": session_id}, {"_id": 0},
        )
        return {"session": sess or {}, "messages": msgs}

    @router.post("/chatbot/{property_id}/handoff/sessions/{session_id}/reply")
    async def staff_reply(property_id: str, session_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        text = (data.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "text required")
        staff_name = current_user.get("name") or current_user.get("email") or "Staff"
        msg = await _append_handoff_message(property_id, session_id, text, "staff", sender_name=staff_name)
        # Ensure session exists (in case staff initiated)
        await db.chatbot_handoff_sessions.update_one(
            {"property_id": property_id, "session_id": session_id},
            {"$set": {"status": "active"}, "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "property_id": property_id, "session_id": session_id,
                "started_at": _now(), "reason": "staff-initiated",
            }},
            upsert=True,
        )
        return {"status": "sent", "message": msg}

    @router.post("/chatbot/{property_id}/handoff/sessions/{session_id}/close")
    async def close_session(property_id: str, session_id: str, data: Optional[Dict] = None,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.chatbot_handoff_sessions.update_one(
            {"property_id": property_id, "session_id": session_id},
            {"$set": {"status": "closed",
                       "closed_at": _now(),
                       "closed_by": current_user.get("name") or current_user.get("email") or "Staff"}},
        )
        # System message to thread
        await _append_handoff_message(
            property_id, session_id,
            "Görüşme sonlandırıldı. Tekrar bağlanmak için mesaj yazın.",
            "system", sender_name="System",
        )
        return {"status": "closed"}

    @router.get("/chatbot/{property_id}/runs")
    async def list_runs(property_id: str, limit: int = 100,
                         _u: dict = Depends(require_roles("admin", "manager"))):
        limit = max(1, min(500, int(limit)))
        rows = await db.chatbot_runs.find({"property_id": property_id}, {"_id": 0})\
            .sort("created_at", -1).limit(limit).to_list(limit)
        return {"property_id": property_id, "count": len(rows), "items": rows}

    return router
