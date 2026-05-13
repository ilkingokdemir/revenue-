"""
Automation Rules — event-driven workflow engine (Flexkeeping-style).

A rule binds a TRIGGER (e.g., booking_created, check_in) + CONDITIONS
(e.g., tag includes 'honeymoon', nights >= 3) → one or more ACTIONS
(e.g., create housekeeping task, log glitch, send guest message).

Endpoints:
  GET    /api/automation/rules                  — list rules
  POST   /api/automation/rules                  — create rule
  GET    /api/automation/rules/{rule_id}        — detail
  PATCH  /api/automation/rules/{rule_id}        — update (enable/disable, edit)
  DELETE /api/automation/rules/{rule_id}        — admin only
  POST   /api/automation/rules/{rule_id}/test   — dry-run against a sample event
  GET    /api/automation/runs                   — execution history
  POST   /api/automation/fire                   — internal: emit an event for testing
  GET    /api/automation/catalog                — list available triggers/actions

The dispatcher (`fire_event`) is exported so other modules can call it whenever
a domain event happens.
"""
from datetime import datetime, timezone
import re
import uuid
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


TRIGGER_CATALOG = {
    "booking_created": "Yeni rezervasyon oluştu",
    "booking_modified": "Rezervasyon değişti",
    "check_in": "Misafir check-in oldu",
    "check_out": "Misafir check-out oldu",
    "room_cleaned": "Oda temizlendi",
    "glitch_critical": "Kritik glitch açıldı",
    "review_negative": "Olumsuz inceleme geldi",
    "low_stock": "Stok düştü",
    "rate_override_set": "Owner fiyat override yaptı",
}

ACTION_CATALOG = {
    "create_task":         "Görev / iş emri oluştur",
    "create_glitch":       "Glitch log kaydı oluştur",
    "notify_role":         "Departmana bildirim gönder",
    "amenity_request":     "Oda için amenity siparişi aç",
    "set_room_status":     "Oda durumunu değiştir",
    "tag_booking":         "Booking'e tag ekle",
    "push_to_ota":         "OTA kanallarına fiyat/stok push et",
    "post_to_chat":        "Team Chat kanalına mesaj at",
}

OPERATORS = {"eq", "ne", "in", "contains", "gt", "lt", "gte", "lte"}


class Condition(BaseModel):
    field: str          # "tags", "nights", "source", "total_price", "guest_email"
    op: str = "eq"      # see OPERATORS
    value: Any = None


class Action(BaseModel):
    type: str           # see ACTION_CATALOG
    params: dict = {}


class RuleIn(BaseModel):
    name: str
    description: str = ""
    trigger: str        # booking_created | ...
    conditions: List[Condition] = []
    actions: List[Action] = []
    property_id: str = "all"
    enabled: bool = True


class RulePatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[Condition]] = None
    actions: Optional[List[Action]] = None
    enabled: Optional[bool] = None
    property_id: Optional[str] = None


# ============== Condition / Action runner ==============

def _eval_condition(cond: dict, payload: dict) -> bool:
    field = cond.get("field", "")
    op = cond.get("op", "eq")
    expected = cond.get("value")
    # Dot-path access (e.g., "guest.email")
    actual: Any = payload
    for part in field.split("."):
        if isinstance(actual, dict):
            actual = actual.get(part)
        else:
            actual = None
            break

    try:
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "in":
            return actual in (expected or [])
        if op == "contains":
            if isinstance(actual, (list, str)):
                return expected in actual
            return False
        if op == "gt":
            return float(actual) > float(expected)
        if op == "lt":
            return float(actual) < float(expected)
        if op == "gte":
            return float(actual) >= float(expected)
        if op == "lte":
            return float(actual) <= float(expected)
    except Exception:
        return False
    return False


def _render_template(template: str, payload: dict) -> str:
    """Substitute {field.path} tokens from payload into the string."""
    if not template:
        return ""
    def repl(m):
        path = m.group(1).strip()
        v = payload
        for part in path.split("."):
            if isinstance(v, dict):
                v = v.get(part)
            else:
                return ""
        return "" if v is None else str(v)
    return re.sub(r"\{([^{}]+)\}", repl, template)


async def _execute_action(db, action: dict, rule: dict, payload: dict, run_id: str) -> dict:
    """Execute one action and return a small execution record."""
    a_type = action.get("type")
    params = action.get("params", {}) or {}
    now = datetime.now(timezone.utc).isoformat()
    out = {"action": a_type, "ok": False, "detail": "", "created_id": ""}

    try:
        if a_type == "create_task":
            doc = {
                "id": str(uuid.uuid4()),
                "title": _render_template(params.get("title", "Automation task"), payload),
                "description": _render_template(params.get("description", ""), payload),
                "department": params.get("department", "housekeeping"),
                "priority": params.get("priority", "normal"),
                "property_id": payload.get("property_id") or rule.get("property_id") or "all",
                "related_booking_ref": payload.get("booking_ref", ""),
                "related_room": payload.get("room_number", ""),
                "status": "open",
                "source": f"automation:{rule.get('id', '')}",
                "created_at": now,
            }
            await db.automation_tasks.insert_one(doc)
            out["ok"] = True
            out["created_id"] = doc["id"]
            out["detail"] = doc["title"]

        elif a_type == "create_glitch":
            doc = {
                "id": str(uuid.uuid4()),
                "property_id": payload.get("property_id") or rule.get("property_id") or "default",
                "title": _render_template(params.get("title", "Auto glitch"), payload),
                "description": _render_template(params.get("description", ""), payload),
                "severity": params.get("severity", "info"),
                "department": params.get("department", "other"),
                "shift": params.get("shift", "morning"),
                "date": now[:10],
                "status": "open",
                "needs_followup": True,
                "tags": ["automation"],
                "related_booking_ref": payload.get("booking_ref", ""),
                "related_room": payload.get("room_number", ""),
                "created_by": f"automation:{rule.get('name', '')}",
                "created_by_id": f"rule:{rule.get('id', '')}",
                "created_at": now,
                "updated_at": now,
                "acknowledged_by": [],
            }
            await db.glitch_log.insert_one(doc)
            out["ok"] = True
            out["created_id"] = doc["id"]
            out["detail"] = doc["title"]

        elif a_type == "amenity_request":
            doc = {
                "id": str(uuid.uuid4()),
                "property_id": payload.get("property_id") or "all",
                "room_number": payload.get("room_number", ""),
                "booking_ref": payload.get("booking_ref", ""),
                "guest_name": payload.get("guest_name", ""),
                "amenity": params.get("amenity", "welcome amenity"),
                "qty": int(params.get("qty", 1) or 1),
                "notes": _render_template(params.get("notes", ""), payload),
                "status": "requested",
                "source": f"automation:{rule.get('id', '')}",
                "created_at": now,
            }
            await db.amenity_requests.insert_one(doc)
            out["ok"] = True
            out["created_id"] = doc["id"]
            out["detail"] = doc["amenity"]

        elif a_type == "notify_role":
            doc = {
                "id": str(uuid.uuid4()),
                "property_id": payload.get("property_id") or "all",
                "role": params.get("role", "manager"),
                "title": _render_template(params.get("title", "Automation"), payload),
                "body": _render_template(params.get("body", ""), payload),
                "read": False,
                "source": f"automation:{rule.get('id', '')}",
                "created_at": now,
            }
            await db.role_notifications.insert_one(doc)
            out["ok"] = True
            out["created_id"] = doc["id"]
            out["detail"] = f"{doc['role']}: {doc['title']}"

        elif a_type == "set_room_status":
            room_number = payload.get("room_number", "")
            status = params.get("status", "dirty")
            if room_number:
                await db.rooms.update_one(
                    {"$or": [{"id": room_number}, {"number": room_number},
                             {"name": room_number}]},
                    {"$set": {"housekeeping_status": status,
                              "status_updated_at": now}}
                )
                out["ok"] = True
                out["detail"] = f"{room_number} → {status}"
            else:
                out["detail"] = "no room_number in payload"

        elif a_type == "tag_booking":
            tag = params.get("tag", "")
            bref = payload.get("booking_ref", "")
            if tag and bref:
                await db.bookings.update_one(
                    {"booking_ref": bref},
                    {"$addToSet": {"tags": tag}}
                )
                out["ok"] = True
                out["detail"] = f"{bref} +{tag}"
            else:
                out["detail"] = "missing tag/booking_ref"

        elif a_type == "push_to_ota":
            # Queue OTA sync via channels_v2 dispatcher
            from routes.channels_v2 import _dispatch_job
            import asyncio as _asyncio
            adapters = params.get("adapters", ["booking.com", "expedia"])
            job_type = params.get("job_type", "rate_push")
            push_payload = {
                "date": payload.get("date", ""),
                "rate": payload.get("rate") or payload.get("new_rate"),
                "room_type_id": payload.get("room_type_id", ""),
                "property_id": payload.get("property_id", ""),
            }
            job_ids = []
            for adapter in adapters:
                job_doc = {
                    "id": str(uuid.uuid4()),
                    "adapter": adapter,
                    "job_type": job_type,
                    "payload": push_payload,
                    "property_id": payload.get("property_id") or rule.get("property_id") or "all",
                    "status": "pending",
                    "attempt_count": 0,
                    "last_error": "",
                    "ota_ref": "",
                    "created_by": f"automation:{rule.get('id', '')}",
                    "created_at": now,
                    "next_retry_at": now,
                }
                await db.channel_sync_queue.insert_one(job_doc)
                _asyncio.create_task(_dispatch_job(db, job_doc["id"]))
                job_ids.append(job_doc["id"])
            out["ok"] = True
            out["detail"] = f"queued {len(job_ids)} adapter(s): {', '.join(adapters)}"
            out["created_id"] = ",".join(job_ids)

        elif a_type == "post_to_chat":
            # Post a message into a team-chat channel
            channel_name = params.get("channel", "general")
            channel = await db.chat_channels.find_one({"name": channel_name}, {"_id": 0, "id": 1})
            if not channel:
                out["detail"] = f"chat channel '{channel_name}' not found"
            else:
                msg_doc = {
                    "id": str(uuid.uuid4()),
                    "channel_id": channel["id"],
                    "author_id": "automation",
                    "author_name": f"⚡ {rule.get('name', 'Automation')}",
                    "author_role": "automation",
                    "body": _render_template(params.get("body", "Automation event triggered"), payload),
                    "mentions": [],
                    "created_at": now,
                    "edited": False,
                }
                await db.chat_messages.insert_one(msg_doc)
                await db.chat_channels.update_one(
                    {"id": channel["id"]}, {"$set": {"updated_at": now}}
                )
                out["ok"] = True
                out["created_id"] = msg_doc["id"]
                out["detail"] = f"#{channel_name}: {msg_doc['body'][:60]}"

        else:
            out["detail"] = f"unknown action type '{a_type}'"

    except Exception as ex:
        out["detail"] = f"error: {ex}"

    return out


# ============== Public dispatcher ==============

async def fire_event(db, event: str, payload: dict, dry_run: bool = False) -> dict:
    """Process all enabled rules matching `event` against `payload`.

    Other modules can `from routes.automation_rules import fire_event` and call
    this whenever a domain event occurs.
    """
    payload = payload or {}
    now = datetime.now(timezone.utc).isoformat()

    # Find applicable rules
    prop = payload.get("property_id") or "all"
    rule_query = {
        "trigger": event,
        "enabled": True,
        "$or": [{"property_id": "all"}, {"property_id": prop}],
    }
    rules = await db.automation_rules.find(rule_query, {"_id": 0}).to_list(200)

    runs: list = []
    for rule in rules:
        # Evaluate conditions (AND logic)
        all_pass = all(_eval_condition(c, payload) for c in (rule.get("conditions") or []))
        if not all_pass:
            continue

        # Execute actions
        action_results: list = []
        for action in rule.get("actions") or []:
            if dry_run:
                action_results.append({"action": action.get("type"), "ok": True,
                                       "detail": "dry-run", "created_id": ""})
            else:
                action_results.append(await _execute_action(db, action, rule, payload, ""))

        run_doc = {
            "id": str(uuid.uuid4()),
            "rule_id": rule.get("id"),
            "rule_name": rule.get("name"),
            "event": event,
            "property_id": prop,
            "actions": action_results,
            "payload_snapshot": {k: payload.get(k) for k in ["booking_ref", "guest_name",
                                                              "room_number", "tags",
                                                              "nights", "source"]},
            "dry_run": dry_run,
            "ok": all(a.get("ok") for a in action_results) if action_results else True,
            "created_at": now,
        }
        runs.append(run_doc)
        if not dry_run:
            await db.automation_runs.insert_one(dict(run_doc))

    return {"event": event, "matched_rules": len(runs), "runs": runs}


def create_automation_router(db, require_roles):
    router = APIRouter(prefix="/automation/v2")

    @router.get("/catalog")
    async def catalog(_: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance"))):
        return {
            "triggers": [{"key": k, "label": v} for k, v in TRIGGER_CATALOG.items()],
            "actions": [{"key": k, "label": v} for k, v in ACTION_CATALOG.items()],
            "operators": sorted(OPERATORS),
        }

    @router.get("/rules")
    async def list_rules(
        property_id: str = "", trigger: str = "", enabled: Optional[bool] = None,
        current_user: dict = Depends(require_roles("admin", "manager")),
    ):
        q: dict = {}
        if property_id:
            q["$or"] = [{"property_id": property_id}, {"property_id": "all"}]
        if trigger:
            q["trigger"] = trigger
        if enabled is not None:
            q["enabled"] = enabled
        rules = await db.automation_rules.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
        # Stats: last run + count
        for r in rules:
            last = await db.automation_runs.find_one({"rule_id": r["id"]}, {"_id": 0, "created_at": 1, "ok": 1},
                                                     sort=[("created_at", -1)])
            r["last_run_at"] = (last or {}).get("created_at", "")
            r["last_run_ok"] = (last or {}).get("ok") if last else None
            r["run_count"] = await db.automation_runs.count_documents({"rule_id": r["id"]})
        return {"rules": rules, "count": len(rules)}

    @router.post("/rules")
    async def create_rule(body: RuleIn, current_user: dict = Depends(require_roles("admin", "manager"))):
        if body.trigger not in TRIGGER_CATALOG:
            raise HTTPException(400, f"trigger must be one of {list(TRIGGER_CATALOG)}")
        for c in body.conditions:
            if c.op not in OPERATORS:
                raise HTTPException(400, f"operator '{c.op}' invalid; use {OPERATORS}")
        for a in body.actions:
            if a.type not in ACTION_CATALOG:
                raise HTTPException(400, f"action type '{a.type}' invalid; use {list(ACTION_CATALOG)}")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            **body.dict(),
            "created_by": current_user.get("name") or current_user.get("email") or "",
            "created_at": now,
            "updated_at": now,
        }
        await db.automation_rules.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/rules/{rule_id}")
    async def get_rule(rule_id: str, _: dict = Depends(require_roles("admin", "manager"))):
        rule = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
        if not rule:
            raise HTTPException(404, "Rule not found")
        return rule

    @router.patch("/rules/{rule_id}")
    async def patch_rule(rule_id: str, patch: RulePatch,
                         _: dict = Depends(require_roles("admin", "manager"))):
        update = {k: v for k, v in patch.dict().items() if v is not None}
        if "actions" in update:
            for a in update["actions"]:
                t = a.get("type") if isinstance(a, dict) else getattr(a, "type", None)
                if t not in ACTION_CATALOG:
                    raise HTTPException(400, f"action type '{t}' invalid")
        if "conditions" in update:
            for c in update["conditions"]:
                op = c.get("op") if isinstance(c, dict) else getattr(c, "op", None)
                if op not in OPERATORS:
                    raise HTTPException(400, f"operator '{op}' invalid")
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await db.automation_rules.update_one({"id": rule_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(404, "Rule not found")
        return {"updated": result.modified_count}

    @router.delete("/rules/{rule_id}")
    async def delete_rule(rule_id: str, _: dict = Depends(require_roles("admin"))):
        result = await db.automation_rules.delete_one({"id": rule_id})
        return {"deleted": result.deleted_count}

    @router.post("/rules/{rule_id}/test")
    async def test_rule(rule_id: str, payload: dict,
                        _: dict = Depends(require_roles("admin", "manager"))):
        rule = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
        if not rule:
            raise HTTPException(404, "Rule not found")
        # Dry-run only this rule
        all_pass = all(_eval_condition(c, payload) for c in (rule.get("conditions") or []))
        return {
            "rule_id": rule_id,
            "trigger_matches": rule.get("trigger") == payload.get("_event"),
            "conditions_pass": all_pass,
            "would_execute_actions": [a.get("type") for a in (rule.get("actions") or [])]
            if all_pass else [],
        }

    @router.post("/fire")
    async def fire(body: dict, _: dict = Depends(require_roles("admin", "manager"))):
        """Manually emit an event — used for testing automation."""
        event = body.get("event")
        if event not in TRIGGER_CATALOG:
            raise HTTPException(400, f"event must be one of {list(TRIGGER_CATALOG)}")
        payload = {k: v for k, v in body.items() if k != "event"}
        result = await fire_event(db, event, payload, dry_run=bool(body.get("dry_run")))
        return result

    @router.get("/runs")
    async def list_runs(rule_id: str = "", limit: int = 50,
                        _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if rule_id:
            q["rule_id"] = rule_id
        runs = await db.automation_runs.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))
        return {"runs": runs, "count": len(runs)}

    @router.get("/suggest")
    async def suggest_rules(property_id: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """AI-suggested automation rules based on last 30 days of activity.

        Analyzes bookings + glitches + reviews + existing rules and proposes
        3-5 new rules the property would benefit from.
        """
        import os
        from datetime import timedelta as _td

        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return {"suggestions": [], "error": "EMERGENT_LLM_KEY not configured"}

        since = (datetime.now(timezone.utc) - _td(days=30)).isoformat()
        prop_q: dict = {} if not property_id or property_id == "all" else {"property_id": property_id}

        # Mini summary of activity
        stats = {
            "total_bookings_30d": await db.bookings.count_documents({**prop_q, "created_at": {"$gte": since}}),
            "vip_bookings_30d": await db.bookings.count_documents({**prop_q, "tags": "vip", "created_at": {"$gte": since}}),
            "honeymoon_bookings_30d": await db.bookings.count_documents({**prop_q, "tags": "honeymoon", "created_at": {"$gte": since}}),
            "critical_glitches_30d": await db.glitch_log.count_documents({**prop_q, "severity": "critical", "created_at": {"$gte": since}}),
            "negative_reviews_30d": await db.reviews.count_documents({**prop_q, "rating": {"$lte": 3}, "created_at": {"$gte": since}}),
            "existing_rules": await db.automation_rules.count_documents({}),
        }

        existing_names = await db.automation_rules.distinct("name")

        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            prompt = f"""Sen bir otel operasyon AI'sısın. Aşağıdaki 30 günlük aktivite verisi ve mevcut kurallara bakarak
otele en çok fayda sağlayacak 3-5 yeni otomasyon kuralı öner.

AKTİVİTE ÖZETİ (son 30 gün):
{stats}

MEVCUT KURAL ADLARI (tekrarlama):
{existing_names[:20]}

KULLANILABİLİR TRIGGERLER:
{list(TRIGGER_CATALOG.keys())}

KULLANILABİLİR AKSİYONLAR:
{list(ACTION_CATALOG.keys())}

KULLANILABİLİR OPERATÖRLER:
{sorted(OPERATORS)}

Sadece geçerli JSON array dön. Her öneri şu yapıda:
{{"name": "...", "description": "neden faydalı", "trigger": "...", "conditions": [{{"field": "tags", "op": "contains", "value": "vip"}}], "actions": [{{"type": "notify_role", "params": {{"role": "manager", "title": "..."}}}}]}}

Sadece JSON dön, başka metin yazma."""

            chat = LlmChat(api_key=api_key, session_id="automation-suggest", system_message="Sen bir otel otomasyon uzmanısın.")
            chat.with_model("openai", "gpt-4o-mini")
            response = await chat.send_message(UserMessage(text=prompt))
            text = str(response).strip()
            # Strip markdown code fences if any
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            import json as _json
            try:
                suggestions = _json.loads(text)
            except Exception:
                # Try to extract array
                import re
                m = re.search(r"\[.*\]", text, re.DOTALL)
                suggestions = _json.loads(m.group(0)) if m else []

            # Validate each suggestion has minimal shape
            valid = []
            for s in (suggestions if isinstance(suggestions, list) else []):
                if (isinstance(s, dict)
                    and s.get("trigger") in TRIGGER_CATALOG
                    and isinstance(s.get("actions"), list)
                    and all(a.get("type") in ACTION_CATALOG for a in s["actions"])):
                    valid.append(s)
            return {"suggestions": valid, "stats": stats}
        except Exception as e:
            return {"suggestions": [], "error": str(e), "stats": stats}

    return router
