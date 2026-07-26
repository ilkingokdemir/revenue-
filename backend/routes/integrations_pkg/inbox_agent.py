"""
Inbox AI Agent (Mews Guest Messaging paritesi) — unified inbox'a gelen basit
misafir mesajlarını otonom cevaplar; güven eşiğinin altında kalınca insana
devreder (bildirim + escalation log). Bilgi kaynağı: chatbot_intents (FAQ).
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import json
import os
import re
import uuid
import logging

from routes.chatbot_automation import _match_intent

logger = logging.getLogger(__name__)

_DEFAULT_CFG = {"enabled": False, "threshold": 70, "property_id": "all"}


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _get_cfg(db) -> Dict:
    doc = await db.inbox_agent_config.find_one({"_id": "singleton"}) or {}
    return {**_DEFAULT_CFG, **{k: v for k, v in doc.items() if k != "_id"}}


async def _resolve_property(db, msg: Dict, cfg: Dict) -> str:
    bid = msg.get("booking_id")
    if bid:
        bk = await db.bookings.find_one({"id": bid}, {"_id": 0, "property_id": 1})
        if bk and bk.get("property_id"):
            return bk["property_id"]
    return cfg.get("property_id", "all")


async def _load_faq(db, property_id: str):
    q = {"enabled": True}
    if property_id and property_id != "all":
        q["property_id"] = {"$in": [property_id, "all"]}
    return await db.chatbot_intents.find(q, {"_id": 0}).to_list(300)


async def _llm_answer(text: str, guest_name: str, faq: list, thread: list) -> Optional[Dict]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        kb = "\n".join(
            f"- S: {', '.join(i.get('trigger_phrases', [])[:3])} → C: {i.get('reply_text','')[:300]}"
            for i in faq if i.get("reply_text")
        )[:6000]
        transcript = "\n".join(f"[{m.get('direction')}] {m.get('body','')[:250]}" for m in thread[-6:])
        sys_prompt = (
            "Sen bir otelin resepsiyon AI asistanısın. SADECE aşağıdaki bilgi tabanındaki bilgilerle "
            "cevap verebilirsin. Bilgi tabanında cevabı yoksa, para iadesi/rezervasyon değişikliği/şikayet "
            "gibi hassas bir konuysa veya emin değilsen can_answer=false döndür. Misafirin dilinde, kısa ve "
            "kibar yaz. Asla bilgi uydurma.\n\nBİLGİ TABANI:\n" + (kb or "(boş)") +
            '\n\nStrict JSON döndür: {"can_answer":true/false,"confidence":0-100,"body":"cevap metni"}'
        )
        chat = LlmChat(api_key=api_key, session_id=f"inbox-agent-{uuid.uuid4().hex[:8]}",
                       system_message=sys_prompt).with_model("openai", "gpt-4o-mini")
        resp = await chat.send_message(UserMessage(
            text=f"Konuşma geçmişi:\n{transcript}\n\nMisafir ({guest_name}) son mesajı: {text}\nStrict JSON döndür."))
        m = re.search(r"\{.*\}", (resp or "").strip(), re.DOTALL)
        return json.loads(m.group(0)) if m else None
    except Exception as e:
        logger.warning("Inbox agent LLM failed: %s", e)
        return None


async def agent_handle_inbound(db, msg: Dict) -> Dict:
    """Called by unified_inbox webhook after saving an inbound message.
    Returns {handled, action, confidence}."""
    cfg = await _get_cfg(db)
    if not cfg.get("enabled"):
        return {"handled": False, "action": "disabled"}
    threshold = int(cfg.get("threshold", 70))
    pid = await _resolve_property(db, msg, cfg)
    faq = await _load_faq(db, pid)
    text = msg.get("body", "")
    guest_name = msg.get("guest_name", "") or msg.get("guest_key", "")

    confidence, body = 0, None
    # 1) Heuristic intent match (free, instant)
    hit = _match_intent(text, faq)
    if hit and hit.get("reply_text"):
        confidence, body = 78, hit["reply_text"]
    # 2) LLM (if available) can override with better answer or refuse
    llm = await _llm_answer(text, guest_name, faq, await db.unified_messages.find(
        {"guest_key": msg["guest_key"]}, {"_id": 0}).sort("created_at", -1).to_list(6))
    if llm is not None:
        if llm.get("can_answer") and (llm.get("body") or "").strip():
            confidence, body = int(llm.get("confidence", 0)), llm["body"].strip()
        elif not hit:
            confidence, body = int(llm.get("confidence", 0)), None

    log = {
        "id": str(uuid.uuid4()), "guest_key": msg["guest_key"], "message_id": msg.get("id"),
        "property_id": pid, "inbound_body": text[:400], "confidence": confidence,
        "threshold": threshold, "created_at": _now(),
    }
    if body and confidence >= threshold:
        out = {
            "id": str(uuid.uuid4()), "guest_key": msg["guest_key"],
            "booking_id": msg.get("booking_id", ""), "guest_name": guest_name,
            "channel": msg.get("channel", "direct"), "direction": "outbound",
            "body": body, "subject": "", "from_addr": "ai-agent",
            "to_addr": msg["guest_key"], "attachments": [], "read": True,
            "created_at": _now(), "sent_by": "AI Agent", "agent": True,
        }
        await db.unified_messages.insert_one(dict(out))
        await db.unified_messages.update_one({"id": msg.get("id")}, {"$set": {"read": True, "agent_handled": True}})
        log.update({"action": "auto_replied", "reply_body": body[:400]})
        await db.inbox_agent_log.insert_one(log)
        return {"handled": True, "action": "auto_replied", "confidence": confidence}

    # Escalate to human
    await db.unified_messages.update_one({"id": msg.get("id")}, {"$set": {"needs_human": True}})
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "property_id": pid, "category": "inbox_agent",
        "priority": "high", "title": "Inbox AI Agent — insana devredildi",
        "message": f"{guest_name}: \"{text[:120]}\" (güven %{confidence} < eşik %{threshold})",
        "read": False, "created_at": _now(),
    })
    log.update({"action": "escalated"})
    await db.inbox_agent_log.insert_one(log)
    return {"handled": True, "action": "escalated", "confidence": confidence}


def create_inbox_agent_router(db, require_roles):
    router = APIRouter(prefix="/inbox/agent")

    @router.get("/config")
    async def get_config(current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _get_cfg(db)

    @router.put("/config")
    async def put_config(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = {}
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        if "threshold" in data:
            t = int(data["threshold"])
            if not 40 <= t <= 95:
                raise HTTPException(400, "threshold 40-95 arasında olmalı")
            upd["threshold"] = t
        if "property_id" in data:
            upd["property_id"] = str(data["property_id"])
        await db.inbox_agent_config.update_one({"_id": "singleton"}, {"$set": upd}, upsert=True)
        return await _get_cfg(db)

    @router.get("/stats")
    async def stats(days: int = 7, current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.inbox_agent_log.find({"created_at": {"$gte": since}}, {"_id": 0}).sort("created_at", -1).to_list(500)
        auto = [r for r in rows if r.get("action") == "auto_replied"]
        esc = [r for r in rows if r.get("action") == "escalated"]
        return {
            "days": days, "auto_replied": len(auto), "escalated": len(esc),
            "automation_rate": round(len(auto) / len(rows) * 100, 1) if rows else 0,
            "avg_confidence": round(sum(r.get("confidence", 0) for r in auto) / len(auto), 1) if auto else 0,
            "recent": rows[:20],
        }

    @router.post("/process/{guest_key}")
    async def process_thread(guest_key: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Manuel tetikleme: thread'in son cevaplanmamış inbound mesajını agent'a ver."""
        msg = await db.unified_messages.find_one(
            {"guest_key": guest_key, "direction": "inbound"}, {"_id": 0}, sort=[("created_at", -1)])
        if not msg:
            raise HTTPException(404, "Inbound mesaj bulunamadı")
        cfg = await _get_cfg(db)
        if not cfg.get("enabled"):
            await db.inbox_agent_config.update_one({"_id": "singleton"}, {"$set": {"enabled": True}}, upsert=True)
        result = await agent_handle_inbound(db, msg)
        return result

    return router
