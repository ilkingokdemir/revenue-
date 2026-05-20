"""
Service Recovery / Guest Complaint Tracker
------------------------------------------
Cloudbeds + Mews ship this as a paid module ("Guest Recovery"). We ship it
free with built-in GPT-5.2 severity classification + suggested-recovery
playbooks (which compensation usually fixes a category of complaint).

Severity is classified by the LLM into: low | medium | high | critical
along with a suggested action (apology / discount % / room move / comp-night).

Endpoints:
  GET  /api/service-recovery/{property_id}                 — list with filters
  POST /api/service-recovery                                — create complaint
  PUT  /api/service-recovery/{complaint_id}                 — update / resolve
  DELETE /api/service-recovery/{complaint_id}
  GET  /api/service-recovery/{property_id}/stats            — KPIs
  POST /api/service-recovery/{complaint_id}/classify        — re-run AI
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import os
import uuid
import json
import logging

logger = logging.getLogger(__name__)


CATEGORIES = [
    "cleanliness", "noise", "staff_attitude", "amenities",
    "wifi", "facilities", "billing", "food_beverage",
    "maintenance", "check_in_out", "other",
]

SUGGESTED_ACTIONS = {
    "low":      {"action": "apology",        "comp_pct": 0,  "playbook": "Sincere apology + note in profile"},
    "medium":   {"action": "discount",       "comp_pct": 10, "playbook": "10% off current stay or comp drink/breakfast"},
    "high":     {"action": "room_move",      "comp_pct": 25, "playbook": "Upgrade room + 25% off + handwritten note"},
    "critical": {"action": "full_refund",    "comp_pct": 100,"playbook": "Full refund or comp night + manager call"},
}


def create_service_recovery_router(db, require_roles):
    router = APIRouter()

    async def _classify(text: str, category: str) -> dict:
        """Use GPT-5.2 via Emergent LLM key to classify severity."""
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key or not text:
            return {"severity": "medium", "ai_summary": "", "ai_action": SUGGESTED_ACTIONS["medium"]["action"], "fallback": True}
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=api_key,
                session_id=f"recovery-{uuid.uuid4()}",
                system_message=(
                    "You are a hotel guest-experience analyst. Classify the complaint "
                    "severity as one of: low, medium, high, critical. "
                    "low = minor inconvenience, medium = noticeable issue, "
                    "high = stay-impacting, critical = unsafe / health-related / major financial. "
                    "Suggest the appropriate recovery action: apology, discount, room_move, full_refund. "
                    "Respond ONLY in valid JSON: "
                    '{"severity":"...","summary":"...","action":"...","comp_pct":number,"reasoning":"..."}'
                ),
            ).with_model("openai", "gpt-5.2")
            resp = await chat.send_message(UserMessage(text=f"Category: {category}\nComplaint:\n{text}"))
            raw = (resp or "").strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()
            obj = json.loads(raw)
            sev = obj.get("severity", "medium")
            if sev not in SUGGESTED_ACTIONS:
                sev = "medium"
            return {
                "severity": sev,
                "ai_summary": obj.get("summary", ""),
                "ai_action": obj.get("action", SUGGESTED_ACTIONS[sev]["action"]),
                "ai_comp_pct": int(obj.get("comp_pct") or SUGGESTED_ACTIONS[sev]["comp_pct"]),
                "ai_reasoning": obj.get("reasoning", ""),
                "fallback": False,
            }
        except Exception as e:
            logger.warning(f"Service recovery LLM classify failed: {e}")
            return {"severity": "medium", "ai_summary": "", "ai_action": "discount", "ai_comp_pct": 10, "fallback": True}

    @router.get("/service-recovery/{property_id}")
    async def list_complaints(property_id: str,
                               status: str = "",
                               category: str = "",
                               days: int = 90,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query: Dict = {"property_id": property_id, "created_at": {"$gte": since}}
        if status:   query["status"]   = status
        if category: query["category"] = category
        docs = await db.guest_complaints.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
        return docs

    @router.post("/service-recovery")
    async def create_complaint(data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        property_id = data.get("property_id", "").strip()
        text = (data.get("text") or "").strip()
        category = data.get("category") or "other"
        if not property_id or not text:
            raise HTTPException(400, "property_id and text are required")
        if category not in CATEGORIES:
            category = "other"

        ai = await _classify(text, category)

        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "booking_id": data.get("booking_id", ""),
            "guest_name": data.get("guest_name", ""),
            "room_number": data.get("room_number", ""),
            "category": category,
            "channel": data.get("channel", "in_person"),  # in_person | email | phone | review
            "text": text,
            "severity": ai["severity"],
            "status": "open",
            "ai_summary": ai.get("ai_summary", ""),
            "ai_action": ai.get("ai_action", ""),
            "ai_comp_pct": ai.get("ai_comp_pct", 0),
            "ai_reasoning": ai.get("ai_reasoning", ""),
            "ai_fallback": ai.get("fallback", False),
            "compensation_amount": 0.0,
            "compensation_type": "",
            "resolution_notes": "",
            "resolved_at": "",
            "resolved_by": "",
            "created_by": current_user.get("name", "Staff"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.guest_complaints.insert_one(dict(record))
        record.pop("_id", None)
        return record

    @router.put("/service-recovery/{complaint_id}")
    async def update_complaint(complaint_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        existing = await db.guest_complaints.find_one({"id": complaint_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Complaint not found")

        update = {}
        for field in ("status", "compensation_amount", "compensation_type",
                      "resolution_notes", "severity", "category"):
            if field in data:
                update[field] = data[field]
        if data.get("compensation_amount") is not None:
            update["compensation_amount"] = float(data.get("compensation_amount") or 0)

        if data.get("status") in ("resolved", "closed") and not existing.get("resolved_at"):
            update["resolved_at"] = datetime.now(timezone.utc).isoformat()
            update["resolved_by"] = current_user.get("name", "Staff")

        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.guest_complaints.update_one({"id": complaint_id}, {"$set": update})
        doc = await db.guest_complaints.find_one({"id": complaint_id}, {"_id": 0})
        return doc

    @router.delete("/service-recovery/{complaint_id}")
    async def delete_complaint(complaint_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.guest_complaints.delete_one({"id": complaint_id})
        return {"ok": True}

    @router.post("/service-recovery/{complaint_id}/classify")
    async def reclassify(complaint_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.guest_complaints.find_one({"id": complaint_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Complaint not found")
        ai = await _classify(doc.get("text", ""), doc.get("category", "other"))
        await db.guest_complaints.update_one({"id": complaint_id}, {"$set": {
            "severity":     ai["severity"],
            "ai_summary":   ai.get("ai_summary", ""),
            "ai_action":    ai.get("ai_action", ""),
            "ai_comp_pct":  ai.get("ai_comp_pct", 0),
            "ai_reasoning": ai.get("ai_reasoning", ""),
            "ai_fallback":  ai.get("fallback", False),
        }})
        return {"ok": True, "ai": ai}

    @router.get("/service-recovery/{property_id}/stats")
    async def stats(property_id: str, days: int = 90,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        docs = await db.guest_complaints.find(
            {"property_id": property_id, "created_at": {"$gte": since}}, {"_id": 0}
        ).to_list(2000)

        by_severity: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        by_category: Dict[str, int] = {}
        by_status:   Dict[str, int] = {"open": 0, "in_progress": 0, "resolved": 0, "closed": 0}
        comp_total  = 0.0
        resolution_minutes = []

        for d in docs:
            sev = d.get("severity", "medium")
            by_severity[sev] = by_severity.get(sev, 0) + 1
            cat = d.get("category", "other")
            by_category[cat] = by_category.get(cat, 0) + 1
            st = d.get("status", "open")
            by_status[st] = by_status.get(st, 0) + 1
            comp_total += float(d.get("compensation_amount") or 0)
            if d.get("resolved_at"):
                try:
                    a = datetime.fromisoformat(d["created_at"])
                    b = datetime.fromisoformat(d["resolved_at"])
                    resolution_minutes.append((b - a).total_seconds() / 60)
                except Exception:
                    pass

        avg_resolution_min = round(sum(resolution_minutes) / len(resolution_minutes), 1) if resolution_minutes else 0
        return {
            "total": len(docs),
            "open": by_status.get("open", 0) + by_status.get("in_progress", 0),
            "resolved": by_status.get("resolved", 0) + by_status.get("closed", 0),
            "by_severity": by_severity,
            "by_category": by_category,
            "by_status":   by_status,
            "compensation_total": round(comp_total, 2),
            "avg_resolution_minutes": avg_resolution_min,
            "playbooks": SUGGESTED_ACTIONS,
            "categories": CATEGORIES,
        }

    return router
