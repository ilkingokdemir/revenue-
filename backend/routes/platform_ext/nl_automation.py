"""
NL Automation Builder (Mews Automations paritesi) — doğal dil cümlesini
çalışan otomasyon kuralına çevirir. POST /api/automation/v2/nl-parse {text}
→ {name, description, trigger, conditions, actions} (kaydetmez; önizleme döner,
kayıt mevcut POST /automation/v2/rules ile yapılır).
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Optional
import json
import os
import re
import uuid
import logging

from routes.automation_rules import TRIGGER_CATALOG, ACTION_CATALOG, OPERATORS

logger = logging.getLogger(__name__)

_TRIGGER_HINTS = [
    (("rezervasyon oluş", "yeni rezervasyon", "booking created", "rezervasyon gel"), "booking_created"),
    (("rezervasyon değiş", "booking modified", "tarih değiş"), "booking_modified"),
    (("check-in", "check in", "giriş yap", "misafir geldiğinde", "varış"), "check_in"),
    (("check-out", "check out", "çıkış yap", "ayrıl"), "check_out"),
    (("temizlen", "oda temiz", "cleaned"), "room_cleaned"),
    (("glitch", "kritik sorun", "şikayet aç"), "glitch_critical"),
    (("olumsuz yorum", "kötü yorum", "negatif inceleme", "düşük puan"), "review_negative"),
    (("stok düş", "stok az", "low stock"), "low_stock"),
    (("fiyat override", "owner fiyat"), "rate_override_set"),
]

_ACTION_HINTS = [
    (("görev", "task", "iş emri"), "create_task"),
    (("amenity", "ikram", "hediye", "şampanya", "meyve tabağı", "çiçek"), "amenity_request"),
    (("bildirim", "haber ver", "bilgilendir", "notify"), "notify_role"),
    (("oda durum", "kirli işaretle", "temiz işaretle"), "set_room_status"),
    (("etiket", "tag"), "tag_booking"),
    (("ota", "kanala push", "fiyat push"), "push_to_ota"),
    (("chat", "mesaj at", "kanala yaz"), "post_to_chat"),
    (("glitch", "kayıt aç"), "create_glitch"),
]


def _heuristic_parse(text: str) -> Dict:
    low = text.lower()
    trigger = "booking_created"
    for keys, trig in _TRIGGER_HINTS:
        if any(k in low for k in keys):
            trigger = trig
            break
    actions = []
    for keys, act in _ACTION_HINTS:
        if any(k in low for k in keys):
            if act == "create_task":
                actions.append({"type": act, "params": {"title": text[:80], "department": "front_office", "priority": "normal"}})
            elif act == "amenity_request":
                actions.append({"type": act, "params": {"amenity": "welcome amenity", "qty": "1", "notes": text[:120]}})
            elif act == "notify_role":
                actions.append({"type": act, "params": {"role": "manager", "title": "Otomasyon bildirimi", "body": text[:160]}})
            else:
                actions.append({"type": act, "params": {}})
    if not actions:
        actions = [{"type": "create_task", "params": {"title": text[:80], "department": "front_office", "priority": "normal"}}]
    conditions = []
    m = re.search(r"(\d+)\s*(?:\+\s*)?gece", low)
    if m:
        conditions.append({"field": "nights", "op": "gte", "value": int(m.group(1))})
    for tag in ("honeymoon", "vip", "balayı", "aile", "business"):
        if tag in low:
            conditions.append({"field": "tags", "op": "contains", "value": tag})
            break
    return {
        "name": (text[:60] + "…") if len(text) > 60 else text,
        "description": f"Doğal dilden üretildi: \"{text[:200]}\"",
        "trigger": trigger,
        "conditions": conditions,
        "actions": actions,
    }


async def _llm_parse(text: str) -> Optional[Dict]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sys_prompt = (
            "Sen bir otel PMS otomasyon kural derleyicisisin. Kullanıcının Türkçe/İngilizce doğal dil "
            "cümlesini aşağıdaki katalogla sınırlı, çalıştırılabilir bir kurala çevir.\n\n"
            f"TRIGGERS (trigger alanı bunlardan BİRİ olmalı): {json.dumps(TRIGGER_CATALOG, ensure_ascii=False)}\n"
            f"ACTIONS (her action.type bunlardan biri olmalı): {json.dumps(ACTION_CATALOG, ensure_ascii=False)}\n"
            f"CONDITION OPERATORS: {sorted(OPERATORS)}\n"
            "Condition field örnekleri: tags, nights, source, total_price, guest_email, room_type, adults.\n"
            "Action params şablonları: create_task{title,department,priority,description}, "
            "amenity_request{amenity,qty,notes}, notify_role{role,title,body}, create_glitch{title,severity,department}, "
            "set_room_status{status}, tag_booking{tag}, post_to_chat{channel,body}. "
            "Params içinde {guest_name} {room_number} {booking_ref} placeholder'ları kullanılabilir.\n"
            "SADECE şu şemada strict JSON döndür (markdown yok): "
            '{"name":"kısa TR ad","description":"1 cümle TR","trigger":"...","conditions":[{"field":"...","op":"...","value":...}],'
            '"actions":[{"type":"...","params":{...}}],"confidence":0-100}'
        )
        chat = LlmChat(api_key=api_key, session_id=f"nl-auto-{uuid.uuid4().hex[:8]}",
                       system_message=sys_prompt).with_model("openai", "gpt-4o-mini")
        resp = await chat.send_message(UserMessage(text=f"Cümle: {text}\nStrict JSON döndür."))
        m = re.search(r"\{.*\}", (resp or "").strip(), re.DOTALL)
        if not m:
            return None
        parsed = json.loads(m.group(0))
        if parsed.get("trigger") not in TRIGGER_CATALOG:
            return None
        acts = [a for a in parsed.get("actions", []) if a.get("type") in ACTION_CATALOG]
        if not acts:
            return None
        parsed["actions"] = acts
        conds = []
        for c in parsed.get("conditions", []):
            if c.get("field") and c.get("op") in OPERATORS:
                conds.append({"field": c["field"], "op": c["op"], "value": c.get("value")})
        parsed["conditions"] = conds
        return parsed
    except Exception as e:
        logger.warning("NL automation LLM parse failed: %s", e)
        return None


def create_nl_automation_router(db, require_roles):
    router = APIRouter(prefix="/automation/v2")

    @router.post("/nl-parse")
    async def nl_parse(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        text = (data.get("text") or "").strip()
        if len(text) < 8:
            raise HTTPException(400, "En az 8 karakterlik bir cümle yazın")
        parsed = await _llm_parse(text)
        source = "llm"
        if not parsed:
            parsed = _heuristic_parse(text)
            parsed["confidence"] = 45
            source = "heuristic"
        parsed["enabled"] = False
        rule = {
            "name": parsed.get("name", text[:60]),
            "description": parsed.get("description", ""),
            "trigger": parsed["trigger"],
            "conditions": parsed.get("conditions", []),
            "actions": parsed.get("actions", []),
            "enabled": False,
        }
        await db.nl_automation_log.insert_one({
            "id": str(uuid.uuid4()), "text": text, "source": source,
            "rule": json.loads(json.dumps(rule)), "user": current_user.get("email", ""),
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })
        return {"rule": rule, "source": source, "confidence": parsed.get("confidence", 70),
                "trigger_label": TRIGGER_CATALOG.get(rule["trigger"], rule["trigger"]),
                "action_labels": [ACTION_CATALOG.get(a["type"], a["type"]) for a in rule["actions"]]}

    return router
