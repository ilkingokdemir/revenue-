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

    DEPT_ROUTING = {
        "cleanliness":   ("housekeeping", "housekeeping_tasks"),
        "amenities":     ("housekeeping", "housekeeping_tasks"),
        "maintenance":   ("maintenance", "maintenance_requests"),
        "wifi":          ("maintenance", "maintenance_requests"),
        "facilities":    ("maintenance", "maintenance_requests"),
        "noise":         ("front_office", "staff_tasks"),
        "billing":       ("front_office", "staff_tasks"),
        "check_in_out":  ("front_office", "staff_tasks"),
        "staff_attitude": ("management", "staff_tasks"),
        "food_beverage": ("fnb", "staff_tasks"),
        "other":         ("front_office", "staff_tasks"),
    }

    async def _route_to_department(record: dict) -> dict:
        """Şikayeti kategorisine göre ilgili departmana görev olarak ata."""
        dept, coll_name = DEPT_ROUTING.get(record.get("category", "other"),
                                           ("front_office", "staff_tasks"))
        sev = record.get("severity", "medium")
        priority = "urgent" if sev in ("high", "critical") else "normal"
        now = datetime.now(timezone.utc)
        task_id = str(uuid.uuid4())
        title = f"Şikayet: {record.get('category', '')} — {record.get('guest_name') or 'Misafir'}"
        desc = (f"[{sev.upper()}] {record.get('text', '')[:400]}\n"
                f"Önerilen aksiyon: {record.get('ai_action', '-')}")
        if coll_name == "housekeeping_tasks":
            await db.housekeeping_tasks.insert_one({
                "id": task_id, "property_id": record.get("property_id", ""),
                "room_number": record.get("room_number", ""),
                "task_type": "complaint", "status": "pending",
                "priority": "urgent" if priority == "urgent" else "high",
                "notes": desc, "due_date": now.strftime("%Y-%m-%d"),
                "source": "service_recovery", "complaint_id": record["id"],
                "created_at": now.isoformat()})
        elif coll_name == "maintenance_requests":
            await db.maintenance_requests.insert_one({
                "id": task_id, "property_id": record.get("property_id", ""),
                "room_number": record.get("room_number", ""),
                "title": title, "description": desc,
                "status": "open", "priority": priority,
                "source": "service_recovery", "complaint_id": record["id"],
                "created_at": now.isoformat()})
        else:
            await db.staff_tasks.insert_one({
                "id": task_id, "property_id": record.get("property_id", ""),
                "title": title, "description": desc,
                "status": "open", "priority": priority,
                "department": dept, "source": "service_recovery",
                "complaint_id": record["id"], "created_at": now.isoformat()})
        return {"department": dept, "task_id": task_id, "collection": coll_name}

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
            "guest_phone": (data.get("guest_phone") or "").strip(),
            "guest_email": (data.get("guest_email") or "").strip(),
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
        try:
            routing = await _route_to_department(record)
            await db.guest_complaints.update_one(
                {"id": record["id"]},
                {"$set": {"routed_department": routing["department"],
                          "routed_task_id": routing["task_id"],
                          "routed_collection": routing["collection"]}})
            record.update({"routed_department": routing["department"],
                           "routed_task_id": routing["task_id"]})
        except Exception as e:
            logger.warning(f"complaint routing failed: {e}")

        # Takip linkini misafire otomatik gönder (SMS/e-posta — MOCKED kuyruk)
        try:
            if record.get("guest_phone") or record.get("guest_email"):
                t_token = uuid.uuid4().hex[:12]
                await db.guest_complaints.update_one(
                    {"id": record["id"]}, {"$set": {"tracking_token": t_token}})
                base = os.environ.get("PUBLIC_BASE_URL") or ""
                link = f"{base}/track/{t_token}"
                msg = (f"Sayın {record.get('guest_name') or 'Misafirimiz'}, geri bildiriminiz "
                       f"alındı ve ilgili ekibimize iletildi. Durumu buradan takip edebilirsiniz: {link}")
                now_iso = datetime.now(timezone.utc).isoformat()
                if record.get("guest_phone"):
                    await db.outbound_sms_queue.insert_one({
                        "id": str(uuid.uuid4()), "property_id": record.get("property_id", ""),
                        "to": record["guest_phone"], "body": msg,
                        "type": "complaint_tracking_link", "complaint_id": record["id"],
                        "status": "queued", "delivery_status": "mocked_sms_queued",
                        "created_at": now_iso})
                if record.get("guest_email"):
                    await db.outbound_email_queue.insert_one({
                        "id": str(uuid.uuid4()), "property_id": record.get("property_id", ""),
                        "to": record["guest_email"],
                        "subject": "Geri bildiriminiz alındı — takip linkiniz",
                        "body": msg, "type": "complaint_tracking_link",
                        "complaint_id": record["id"],
                        "status": "queued", "delivery_status": "mocked_email_queued",
                        "created_at": now_iso})
                record["tracking_token"] = t_token
                record["tracking_url"] = link
                record["tracking_link_sent"] = True
        except Exception as e:
            logger.warning(f"tracking link send failed: {e}")
        try:
            import asyncio
            from routes.platform_ext.mobile_push import send_expo_push
            sev = record.get("severity", "")
            asyncio.create_task(send_expo_push(
                db, f"⚠️ Yeni şikayet — {record.get('guest_name') or 'Misafir'}",
                f"[{record.get('category', '')}{' · ' + sev if sev else ''}] {record.get('text', '')[:110]}",
                {"type": "new_complaint", "id": record["id"],
                 "property_id": record.get("property_id", "")},
                kind="new_complaint"))
        except Exception as e:
            logger.warning(f"complaint push failed: {e}")
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

    @router.get("/service-recovery/{complaint_id}/tracking-link")
    async def tracking_link(complaint_id: str,
                            _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        c = await db.guest_complaints.find_one({"id": complaint_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Şikayet bulunamadı")
        token = c.get("tracking_token")
        if not token:
            token = uuid.uuid4().hex[:12]
            await db.guest_complaints.update_one(
                {"id": complaint_id}, {"$set": {"tracking_token": token}})
        base = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
        return {"token": token, "url": f"{base}/track/{token}"}

    @router.get("/public/complaint-track/{token}")
    async def public_track(token: str):
        """Public — misafir takip linki (auth yok)."""
        c = await db.guest_complaints.find_one({"tracking_token": token}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Kayıt bulunamadı")
        return {
            "guest_name": c.get("guest_name", ""),
            "category": c.get("category", ""),
            "status": c.get("status", "open"),
            "created_at": c.get("created_at", ""),
            "routed_department": c.get("routed_department", ""),
            "response_text": c.get("guest_response_text", ""),
            "response_at": c.get("guest_response_at", ""),
            "resolved_at": c.get("resolved_at", ""),
        }

    return router
