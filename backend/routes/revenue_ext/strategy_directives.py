"""Strateji Direktifleri — FLYR 'influence the AI with strategic directions' paritesi.
Serbest metin direktif LLM ile yapılandırılır; Copilot ve Stratejist önerilerinde zorunlu bağlam olur."""
import json
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict

PARSE_SYSTEM = """Otel gelir yönetimi direktifini yapılandır. SADECE şu JSON'u döndür, başka hiçbir şey yazma:
{"priority": "occupancy"|"adr"|"balanced", "aggressiveness": -2..2 arası tamsayı, "scope_start": "YYYY-MM-DD"|null, "scope_end": "YYYY-MM-DD"|null, "summary": "tek cümle Türkçe özet"}
aggressiveness: -2 çok temkinli, 0 nötr, +2 çok agresif fiyat hamleleri."""


async def directives_context_for_llm(db, pid: str) -> str:
    items = await db.strategy_directives.find(
        {"property_id": pid, "active": True}, {"_id": 0}).to_list(10)
    if not items:
        return ""
    lines = []
    for i in items:
        p = i.get("parsed") or {}
        lines.append(f"- {i['text']} (öncelik: {p.get('priority', 'balanced')}, agresiflik: {p.get('aggressiveness', 0)}"
                     + (f", kapsam: {p.get('scope_start')}→{p.get('scope_end')}" if p.get("scope_start") else "") + ")")
    return "\n\nSTRATEJİ DİREKTİFLERİ (yönetim talimatı — tüm öneri ve aksiyonlarda MUTLAKA uy):\n" + "\n".join(lines)


def create_strategy_directives_router(db, require_roles):
    router = APIRouter(prefix="/strategy-directives", tags=["strategy-directives"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def list_directives(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        items = await db.strategy_directives.find(
            {"property_id": pid, "active": True}, {"_id": 0}).sort("created_at", -1).to_list(20)
        return {"items": items}

    @router.post("/{pid}")
    async def add_directive(pid: str, body: Dict, current_user: dict = Depends(require_roles(*ROLES))):
        text = (body.get("text") or "").strip()[:300]
        if len(text) < 5:
            raise HTTPException(400, "Direktif en az 5 karakter olmalı")
        parsed = {"priority": "balanced", "aggressiveness": 0, "scope_start": None, "scope_end": None, "summary": text}
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                           session_id=f"directive-{uuid.uuid4().hex[:8]}",
                           system_message=PARSE_SYSTEM).with_model("openai", "gpt-5.2")
            raw = await chat.send_message(UserMessage(text=f"Bugün: {datetime.now(timezone.utc).date().isoformat()}. Direktif: {text}"))
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                p = json.loads(m.group(0))
                if p.get("priority") in ("occupancy", "adr", "balanced"):
                    parsed["priority"] = p["priority"]
                try:
                    parsed["aggressiveness"] = max(-2, min(2, int(p.get("aggressiveness", 0))))
                except (TypeError, ValueError):
                    pass
                for k in ("scope_start", "scope_end", "summary"):
                    if isinstance(p.get(k), str):
                        parsed[k] = p[k]
        except Exception:
            pass
        doc = {"id": str(uuid.uuid4())[:8], "property_id": pid, "text": text, "parsed": parsed,
               "active": True, "created_by": current_user.get("email", ""),
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.strategy_directives.insert_one({**doc})
        return doc

    @router.delete("/{pid}/{did}")
    async def deactivate(pid: str, did: str, _u: dict = Depends(require_roles(*ROLES))):
        r = await db.strategy_directives.update_one(
            {"property_id": pid, "id": did}, {"$set": {"active": False}})
        if r.matched_count == 0:
            raise HTTPException(404, "Direktif bulunamadı")
        return {"ok": True}

    return router
