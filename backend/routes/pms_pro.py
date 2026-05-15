"""
PMS Pro Features — Mews/Cloudbeds/Pace/Hostaway/Lodgify/Apaleo rakiplerinden öne geçmek için:

1. Smart Room Assignment — check-in time, party size, preferences, history → AI auto-assign
2. AI Operations Concierge — Türkçe doğal dil PMS sorguları (GPT-4o-mini)
3. Guest Journey Orchestrator — rules engine: trigger → action (pre-arrival, in-stay, post)
4. Operations Anomaly Alerts — VIP, late checkout, no-show risk, abnormal patterns

Prefix: /api/pms-pro/*
"""
import os
import uuid
import json as _json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException


def create_pms_pro_router(db, require_roles):
    router = APIRouter(prefix="/pms-pro")

    # ==================== SMART ROOM ASSIGNMENT ====================

    @router.post("/smart-assign")
    async def smart_assign(data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Akıllı oda atama — booking detaylarına göre en uygun room number önerir.

        Body: {booking_id} VEYA {property_id, check_in, check_out, room_type, adults, children, preferences:[]}

        Scoring:
          - +20 if room_type matches
          - +15 if floor preference matched (high/low)
          - +10 if quiet (away from elevator/ice machine)
          - +10 if accessibility match
          - -5 per past complaint on this room (last 90d)
          - -10 if room currently under maintenance
        """
        booking_id = data.get("booking_id")
        if booking_id:
            booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0}) or \
                      await db.bookings.find_one({"booking_id": booking_id}, {"_id": 0})
            if not booking:
                raise HTTPException(404, "Booking not found")
            pid = booking.get("property_id")
            ci = booking.get("check_in")
            co = booking.get("check_out")
            room_type = booking.get("room_type")
            adults = int(booking.get("adults") or 1)
            preferences = booking.get("preferences") or []
        else:
            pid = data.get("property_id")
            ci = data.get("check_in")
            co = data.get("check_out")
            room_type = data.get("room_type")
            adults = int(data.get("adults") or 1)
            preferences = data.get("preferences") or []

        if not (pid and ci and co):
            raise HTTPException(400, "property_id, check_in, check_out required")

        # Get rooms in this property
        rooms = await db.rooms.find({"property_id": pid}, {"_id": 0}).to_list(500)
        if not rooms:
            raise HTTPException(404, "No rooms in property")

        # Find rooms NOT occupied in date range
        occupied = await db.bookings.find({
            "property_id": pid,
            "status": {"$ne": "cancelled"},
            "check_in": {"$lt": co},
            "check_out": {"$gt": ci},
            "assigned_room": {"$exists": True, "$ne": None},
        }, {"_id": 0, "assigned_room": 1}).to_list(500)
        occupied_set = {b["assigned_room"] for b in occupied if b.get("assigned_room")}

        # Active maintenance
        maintenance = await db.maintenance_tickets.find({
            "property_id": pid,
            "status": {"$in": ["open", "in_progress"]},
        }, {"_id": 0, "room_number": 1}).to_list(200)
        maintenance_set = {m.get("room_number") for m in maintenance if m.get("room_number")}

        # Past complaints (last 90d)
        ninety_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        complaints = await db.complaints.find({
            "property_id": pid,
            "created_at": {"$gte": ninety_ago},
        }, {"_id": 0, "room_number": 1}).to_list(500)
        complaint_count: Dict = {}
        for c in complaints:
            r = c.get("room_number")
            if r:
                complaint_count[r] = complaint_count.get(r, 0) + 1

        candidates = []
        for room in rooms:
            room_no = room.get("number") or room.get("room_number") or room.get("id")
            if not room_no or room_no in occupied_set:
                continue

            score = 0
            reasons = []

            # Room type match
            if room_type and room.get("type") == room_type:
                score += 20
                reasons.append(f"Tip uyumu ({room_type})")

            # Floor preference
            floor = room.get("floor") or 0
            if "high_floor" in preferences and floor >= 3:
                score += 15
                reasons.append("Yüksek kat tercih")
            if "low_floor" in preferences and floor <= 2:
                score += 15
                reasons.append("Alçak kat tercih")

            # Quiet
            if "quiet" in preferences and not room.get("near_elevator"):
                score += 10
                reasons.append("Sessiz (asansörden uzak)")

            # Accessibility
            if "accessibility" in preferences and room.get("accessible"):
                score += 20
                reasons.append("Engelli erişim")

            # Adults fit
            capacity = int(room.get("capacity") or 2)
            if adults <= capacity:
                score += 5

            # Penalties
            if room_no in maintenance_set:
                score -= 30
                reasons.append("⚠️ Bakımda")

            cc = complaint_count.get(room_no, 0)
            if cc > 0:
                score -= cc * 5
                reasons.append(f"-{cc * 5}: {cc} geçmiş şikayet")

            candidates.append({
                "room_number": room_no,
                "score": score,
                "floor": floor,
                "type": room.get("type"),
                "capacity": capacity,
                "reasons": reasons,
                "in_maintenance": room_no in maintenance_set,
            })

        if not candidates:
            return {"ok": False, "error": "Bu tarih için uygun oda bulunamadı", "candidates": []}

        candidates.sort(key=lambda x: x["score"], reverse=True)
        top = candidates[0]
        return {
            "ok": True,
            "best_room": top["room_number"],
            "best_score": top["score"],
            "best_reasons": top["reasons"],
            "top_candidates": candidates[:5],
        }

    # ==================== AI OPERATIONS CONCIERGE ====================

    @router.post("/ai-concierge")
    async def ai_concierge(data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Doğal dil PMS sorguları — GPT-4o-mini ile.

        Body: {query: "yarın gelen VIP'leri göster", property_id: "X"}

        AI önce kategoriye karar verir (arrivals/departures/maintenance/housekeeping/vip),
        sonra DB query çalıştırır + sonucu Türkçe özetler.
        """
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        query = (data.get("query") or "").strip()
        pid = data.get("property_id") or "all"
        if not query:
            raise HTTPException(400, "query required")

        # Quick rule-based intent
        intent = "general"
        ql = query.lower()
        if any(w in ql for w in ["yarın", "tomorrow", "gelen", "arrival", "varış"]):
            intent = "arrivals"
        elif any(w in ql for w in ["bugün", "today", "checkout", "çıkış", "ayrılan"]):
            intent = "departures"
        elif any(w in ql for w in ["vip", "loyalty", "altın", "elit"]):
            intent = "vip"
        elif any(w in ql for w in ["bakım", "maintenance", "arıza", "broken"]):
            intent = "maintenance"
        elif any(w in ql for w in ["temizlik", "housekeeping", "kirli", "clean"]):
            intent = "housekeeping"

        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filter_q: Dict = {"status": {"$ne": "cancelled"}}
        if pid and pid != "all":
            filter_q["property_id"] = pid

        # Run DB query based on intent
        result_data = []
        if intent == "arrivals":
            filter_q["check_in"] = tomorrow
            result_data = await db.bookings.find(filter_q, {"_id": 0, "guest_name": 1, "room_type": 1, "adults": 1,
                                                            "check_in": 1, "check_out": 1, "vip": 1, "property_id": 1}).limit(50).to_list(50)
        elif intent == "departures":
            filter_q["check_out"] = today
            result_data = await db.bookings.find(filter_q, {"_id": 0, "guest_name": 1, "room_type": 1,
                                                            "check_out": 1, "property_id": 1, "assigned_room": 1}).limit(50).to_list(50)
        elif intent == "vip":
            filter_q["vip"] = True
            filter_q["check_in"] = {"$gte": today, "$lte": (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")}
            result_data = await db.bookings.find(filter_q, {"_id": 0, "guest_name": 1, "check_in": 1,
                                                            "vip": 1, "property_id": 1, "room_type": 1}).limit(50).to_list(50)
        elif intent == "maintenance":
            mq = {"status": {"$in": ["open", "in_progress"]}}
            if pid and pid != "all":
                mq["property_id"] = pid
            result_data = await db.maintenance_tickets.find(mq, {"_id": 0, "room_number": 1, "issue": 1,
                                                                 "priority": 1, "created_at": 1, "status": 1}).limit(50).to_list(50)
        elif intent == "housekeeping":
            tq = {"status": {"$in": ["dirty", "pending"]}}
            if pid and pid != "all":
                tq["property_id"] = pid
            result_data = await db.housekeeping_tasks.find(tq, {"_id": 0, "room_number": 1, "status": 1,
                                                                 "task_type": 1, "due_at": 1}).limit(50).to_list(50)

        # AI summarize in Turkish
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        chat = LlmChat(
            api_key=api_key,
            session_id=f"pms-concierge-{uuid.uuid4().hex[:8]}",
            system_message=(
                "Sen bir hotel operations asistanısın. Sana kullanıcının sorusu + veritabanı sonucu "
                "verilecek. Sonucu Türkçe kısa ve eyleme dönük şekilde özetle (max 3 cümle). "
                "Önemli detayları (oda numarası, kişi sayısı, öncelik) belirt. Liste varsa bullet kullan."
            ),
        ).with_model("openai", "gpt-4o-mini")

        try:
            msg = UserMessage(text=_json.dumps({
                "query": query, "intent": intent,
                "result_count": len(result_data),
                "result_sample": result_data[:10],
            }))
            ai_text = await chat.send_message(msg)
        except Exception as e:
            ai_text = f"AI özet yapılamadı: {str(e)[:80]}"

        return {
            "ok": True,
            "query": query,
            "intent": intent,
            "result_count": len(result_data),
            "summary": ai_text,
            "raw": result_data[:20],
        }

    # ==================== GUEST JOURNEY ORCHESTRATOR ====================

    @router.get("/journey-rules")
    async def list_journey_rules(property_id: Optional[str] = None,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id} if property_id else {}
        rows = await db.guest_journey_rules.find(q, {"_id": 0}).sort("priority", 1).to_list(200)
        return {"items": rows}

    @router.post("/journey-rules")
    async def create_journey_rule(data: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Body: {property_id, name, trigger, action, when_minutes, priority, enabled}
        Triggers: booking_confirmed, pre_arrival_24h, pre_arrival_1h, checked_in, mid_stay,
                  pre_checkout_2h, checked_out, no_show, late_checkout_requested
        Actions: send_email, send_sms, send_app_push, create_task, send_qr_key, offer_upsell,
                 trigger_housekeeping, notify_manager
        """
        rid = uuid.uuid4().hex
        now_iso = datetime.now(timezone.utc).isoformat()
        rule = {
            "id": rid,
            "property_id": data.get("property_id"),
            "name": data.get("name", "Untitled rule"),
            "trigger": data.get("trigger"),
            "action": data.get("action"),
            "template": data.get("template", ""),
            "when_minutes": int(data.get("when_minutes") or 0),
            "priority": int(data.get("priority") or 100),
            "enabled": bool(data.get("enabled", True)),
            "created_at": now_iso,
            "created_by": current_user.get("name", "system"),
            "fires_count": 0,
        }
        await db.guest_journey_rules.insert_one(rule)
        rule.pop("_id", None)
        return {"ok": True, "rule": rule}

    @router.delete("/journey-rules/{rule_id}")
    async def delete_journey_rule(rule_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.guest_journey_rules.delete_one({"id": rule_id})
        if not r.deleted_count:
            raise HTTPException(404, "Rule not found")
        return {"ok": True}

    @router.patch("/journey-rules/{rule_id}/toggle")
    async def toggle_journey_rule(rule_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        rule = await db.guest_journey_rules.find_one({"id": rule_id}, {"_id": 0})
        if not rule:
            raise HTTPException(404, "Rule not found")
        new_state = not bool(rule.get("enabled"))
        await db.guest_journey_rules.update_one({"id": rule_id}, {"$set": {"enabled": new_state}})
        return {"ok": True, "enabled": new_state}

    # ==================== OPERATIONS ANOMALY ALERTS ====================

    @router.get("/anomalies/{property_id}")
    async def operations_anomalies(property_id: str,
                                   current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Aktif operasyon anomalileri:
          - VIP gelmek üzere (24h)
          - Beklenen no-show (12h içinde gelmesi gerekiyor, henüz check-in yapmadı)
          - Long-stay maintenance bekleniyor (>2 gün pending)
          - Çok kirli oda count (housekeeping queue)
          - Group rooming wizard incomplete
        """
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")

        alerts = []

        # VIP arrivals next 24h
        vip_count = await db.bookings.count_documents({
            "property_id": property_id, "status": {"$ne": "cancelled"},
            "vip": True, "check_in": tomorrow,
        })
        if vip_count > 0:
            alerts.append({
                "level": "info", "title": f"🌟 {vip_count} VIP yarın geliyor",
                "category": "vip_arrivals", "count": vip_count,
                "action": "Onaylanmış VIP karşılama paketi hazırla",
            })

        # No-show risk (check-in today + before 18:00 UTC + no checked_in)
        no_show_candidates = await db.bookings.find({
            "property_id": property_id, "status": {"$ne": "cancelled"},
            "check_in": today_str, "checked_in": {"$ne": True},
        }, {"_id": 0, "guest_name": 1, "id": 1, "check_in": 1, "phone": 1}).limit(50).to_list(50)
        if no_show_candidates and now.hour >= 18:
            alerts.append({
                "level": "warning", "title": f"⏰ {len(no_show_candidates)} olası no-show riski",
                "category": "no_show_risk", "count": len(no_show_candidates),
                "action": "Acil arama/SMS gönder",
                "samples": [b.get("guest_name") for b in no_show_candidates[:5]],
            })

        # Old open maintenance (>2 days)
        two_ago = (now - timedelta(days=2)).isoformat()
        old_maint = await db.maintenance_tickets.count_documents({
            "property_id": property_id,
            "status": {"$in": ["open", "in_progress"]},
            "created_at": {"$lt": two_ago},
        })
        if old_maint > 0:
            alerts.append({
                "level": "warning", "title": f"🔧 {old_maint} bakım talebi 2+ gündür açık",
                "category": "stale_maintenance", "count": old_maint,
                "action": "Bakım ekibi ile durum güncelle",
            })

        # Housekeeping queue
        dirty_count = await db.housekeeping_tasks.count_documents({
            "property_id": property_id,
            "status": {"$in": ["dirty", "pending"]},
        })
        if dirty_count > 5:
            alerts.append({
                "level": "info", "title": f"🧹 {dirty_count} oda housekeeping kuyruğunda",
                "category": "housekeeping_backlog", "count": dirty_count,
                "action": "Ek personel görevlendir veya öncelik sırasını kontrol et",
            })

        # Critical: maintenance on rooms with arrivals today
        arrivals_today = await db.bookings.distinct("assigned_room", {
            "property_id": property_id, "status": {"$ne": "cancelled"},
            "check_in": today_str,
        })
        blocked = await db.maintenance_tickets.count_documents({
            "property_id": property_id,
            "status": {"$in": ["open", "in_progress"]},
            "room_number": {"$in": arrivals_today} if arrivals_today else {"$exists": False},
        }) if arrivals_today else 0
        if blocked > 0:
            alerts.append({
                "level": "critical", "title": f"🚨 {blocked} bugün gelen guest'in odasında aktif bakım var",
                "category": "blocked_arrival", "count": blocked,
                "action": "Acil oda transferi veya bakım tamamla",
            })

        return {
            "property_id": property_id,
            "checked_at": now.isoformat(),
            "alert_count": len(alerts),
            "critical_count": sum(1 for a in alerts if a["level"] == "critical"),
            "alerts": alerts,
        }

    # ==================== JOURNEY ENGINE: FIRES HISTORY & MANUAL TRIGGER ====================

    @router.get("/journey-fires")
    async def list_journey_fires(property_id: Optional[str] = None,
                                 rule_id: Optional[str] = None,
                                 limit: int = 100,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Recent journey rule executions (history)."""
        q: Dict = {}
        if property_id:
            q["property_id"] = property_id
        if rule_id:
            q["rule_id"] = rule_id
        limit = max(1, min(int(limit or 100), 500))
        rows = await db.journey_fires.find(q, {"_id": 0}).sort("fired_at", -1).to_list(limit)
        return {"items": rows, "count": len(rows)}

    @router.post("/journey-engine/run-once")
    async def journey_run_now(current_user: dict = Depends(require_roles("admin", "manager"))):
        """On-demand execution of all enabled rules. Returns fires count."""
        stats = await _journey_run_once(db)
        return {"ok": True, **stats}

    @router.post("/journey-rules/{rule_id}/test-fire")
    async def journey_test_fire(rule_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Test-fire a rule against a specific booking (ignores idempotency).
        Body: {booking_id}
        """
        rule = await db.guest_journey_rules.find_one({"id": rule_id}, {"_id": 0})
        if not rule:
            raise HTTPException(404, "Rule not found")
        booking_id = (data or {}).get("booking_id")
        if not booking_id:
            raise HTTPException(400, "booking_id required")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0}) or \
                  await db.bookings.find_one({"booking_id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        result = await _execute_action(db, rule, booking)
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.journey_fires.insert_one({
            "id": uuid.uuid4().hex,
            "rule_id": rule_id,
            "rule_name": rule.get("name"),
            "trigger": rule.get("trigger"),
            "action": rule.get("action"),
            "property_id": rule.get("property_id") or booking.get("property_id"),
            "booking_id": booking_id,
            "guest_name": booking.get("guest_name") or booking.get("guest"),
            "ok": result.get("ok"),
            "reason": result.get("reason"),
            "fired_at": now_iso,
            "manual": True,
        })
        return {"ok": True, "result": result}

    return router


# ============================================================================
# JOURNEY RULES EXECUTION ENGINE (Iter 296)
# ============================================================================
# Background async loop that scans bookings every 60s, matches them against
# enabled journey rules, fires the action exactly once per (rule, booking)
# pair, and records the fire in `journey_fires` collection.
#
# Triggers supported:
#   - booking_confirmed       → booking created in last 70s
#   - pre_arrival_24h         → check_in - now ∈ [23h, 25h]
#   - pre_arrival_1h          → check_in - now ∈ [0h, 2h] AND check_in > now
#   - checked_in              → bookings with checked_in=True
#   - mid_stay                → midpoint of stay reached (today equals midpoint date)
#   - pre_checkout_2h         → check_out - now ∈ [0h, 3h]
#   - checked_out             → bookings with status="checked_out"
#   - no_show                 → check_in date past + checked_in!=True + 12h after 14:00
#   - late_checkout_requested → bookings with late_checkout=True
#
# Actions: log the fire + create side-effects in the relevant collection:
#   send_email / send_sms / send_app_push → outbound message queue
#   create_task / trigger_housekeeping    → staff_tasks / housekeeping_tasks
#   send_qr_key / offer_upsell            → outbound_email_queue (typed)
#   notify_manager                        → team_chat insert into #management
# ============================================================================

import asyncio
import logging

_journey_logger = logging.getLogger("pms_pro.journey")


def _substitute(template: str, booking: dict) -> str:
    """Simple {{field}} template substitution from booking fields."""
    if not template:
        return ""
    out = template
    for k, v in (booking or {}).items():
        if isinstance(v, (str, int, float)):
            out = out.replace("{{" + k + "}}", str(v))
    return out


async def _trigger_matches(db, trigger: str, lookback_seconds: int = 65) -> List[dict]:
    """Return bookings that currently satisfy a given trigger."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    cutoff_iso = (now - timedelta(seconds=lookback_seconds)).isoformat()

    base = {"status": {"$ne": "cancelled"}}

    if trigger == "booking_confirmed":
        return await db.bookings.find(
            {**base, "created_at": {"$gte": cutoff_iso}}, {"_id": 0}
        ).limit(200).to_list(200)

    if trigger == "pre_arrival_24h":
        # check_in tomorrow (calendar day = today + 1)
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        return await db.bookings.find(
            {**base, "check_in": tomorrow, "checked_in": {"$ne": True}}, {"_id": 0}
        ).limit(500).to_list(500)

    if trigger == "pre_arrival_1h":
        # check_in today + within 2h of typical arrival; we approximate by today + hour>=12
        if now.hour < 12:
            return []
        return await db.bookings.find(
            {**base, "check_in": today_str, "checked_in": {"$ne": True}}, {"_id": 0}
        ).limit(500).to_list(500)

    if trigger == "checked_in":
        # checked in today
        return await db.bookings.find(
            {**base, "checked_in": True, "check_in": today_str}, {"_id": 0}
        ).limit(500).to_list(500)

    if trigger == "mid_stay":
        rows = await db.bookings.find(
            {**base, "checked_in": True, "checked_out": {"$ne": True}}, {"_id": 0}
        ).limit(500).to_list(500)
        result = []
        for b in rows:
            ci = b.get("check_in")
            co = b.get("check_out")
            if not ci or not co:
                continue
            try:
                d1 = datetime.strptime(ci, "%Y-%m-%d")
                d2 = datetime.strptime(co, "%Y-%m-%d")
                mid = d1 + (d2 - d1) / 2
                if mid.strftime("%Y-%m-%d") == today_str:
                    result.append(b)
            except Exception:
                continue
        return result

    if trigger == "pre_checkout_2h":
        return await db.bookings.find(
            {**base, "check_out": today_str, "checked_out": {"$ne": True}}, {"_id": 0}
        ).limit(500).to_list(500)

    if trigger == "checked_out":
        return await db.bookings.find(
            {**base, "status": "checked_out", "check_out": today_str}, {"_id": 0}
        ).limit(500).to_list(500)

    if trigger == "no_show":
        # check_in yesterday or earlier + never checked in + within last 36h
        cutoff_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        return await db.bookings.find(
            {**base, "check_in": cutoff_date, "checked_in": {"$ne": True}}, {"_id": 0}
        ).limit(200).to_list(200)

    if trigger == "late_checkout_requested":
        return await db.bookings.find(
            {**base, "late_checkout": True, "check_out": today_str}, {"_id": 0}
        ).limit(200).to_list(200)

    return []


async def _execute_action(db, rule: dict, booking: dict) -> dict:
    """Execute the side-effect for an action. Returns side-effect summary."""
    action = rule.get("action") or ""
    template_raw = rule.get("template") or rule.get("name", "")
    msg = _substitute(template_raw, booking)
    pid = rule.get("property_id") or booking.get("property_id")
    now_iso = datetime.now(timezone.utc).isoformat()
    bid = booking.get("id") or booking.get("booking_id")
    guest = booking.get("guest_name") or booking.get("guest", "Guest")

    base_doc = {
        "id": uuid.uuid4().hex,
        "property_id": pid,
        "booking_id": bid,
        "guest_name": guest,
        "source": "journey_rule",
        "rule_id": rule.get("id"),
        "rule_name": rule.get("name"),
        "created_at": now_iso,
    }

    try:
        if action == "send_email":
            await db.outbound_email_queue.insert_one({
                **base_doc, "to": booking.get("email"), "subject": rule.get("name", "Update"),
                "body": msg, "status": "queued", "type": "journey",
            })
        elif action == "send_sms":
            await db.outbound_sms_queue.insert_one({
                **base_doc, "to": booking.get("phone"), "body": msg,
                "status": "queued", "type": "journey",
            })
        elif action == "send_app_push":
            await db.web_push_queue.insert_one({
                **base_doc, "title": rule.get("name", "Notification"),
                "body": msg, "status": "queued",
            })
        elif action == "create_task":
            await db.staff_tasks.insert_one({
                **base_doc, "title": rule.get("name", "Journey task"),
                "description": msg, "status": "open", "priority": "normal",
            })
        elif action == "send_qr_key":
            await db.outbound_email_queue.insert_one({
                **base_doc, "to": booking.get("email"), "subject": "Dijital oda anahtarınız",
                "body": msg, "status": "queued", "type": "qr_key",
            })
        elif action == "offer_upsell":
            await db.upsell_offers.insert_one({
                **base_doc, "offer_text": msg, "status": "open",
            })
        elif action == "trigger_housekeeping":
            await db.housekeeping_tasks.insert_one({
                **base_doc, "room_number": booking.get("assigned_room"),
                "task_type": "turnover", "status": "pending", "priority": "high",
                "notes": msg,
            })
        elif action == "notify_manager":
            await db.team_chat.insert_one({
                **base_doc, "channel": "management", "author": "Journey Bot",
                "text": f"⚡ {rule.get('name')}: {msg or guest}",
            })
        else:
            return {"ok": False, "reason": f"unknown_action:{action}"}
        return {"ok": True}
    except Exception as e:
        _journey_logger.exception(f"Action {action} failed: {e}")
        return {"ok": False, "reason": str(e)[:120]}


async def _journey_run_once(db) -> dict:
    """Run one execution cycle. Returns summary stats."""
    rules = await db.guest_journey_rules.find(
        {"enabled": True}, {"_id": 0}
    ).sort("priority", 1).to_list(500)

    total_fires = 0
    rules_processed = 0

    for rule in rules:
        rid = rule.get("id")
        trigger = rule.get("trigger")
        if not (rid and trigger):
            continue
        rules_processed += 1

        try:
            candidates = await _trigger_matches(db, trigger)
        except Exception as e:
            _journey_logger.exception(f"trigger_matches failed for {trigger}: {e}")
            continue

        for booking in candidates:
            # property scope check
            if rule.get("property_id") and booking.get("property_id") != rule.get("property_id"):
                continue
            bid = booking.get("id") or booking.get("booking_id")
            if not bid:
                continue

            # idempotency: have we already fired this (rule, booking)?
            fired = await db.journey_fires.find_one(
                {"rule_id": rid, "booking_id": bid}, {"_id": 0, "id": 1}
            )
            if fired:
                continue

            result = await _execute_action(db, rule, booking)
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.journey_fires.insert_one({
                "id": uuid.uuid4().hex,
                "rule_id": rid,
                "rule_name": rule.get("name"),
                "trigger": trigger,
                "action": rule.get("action"),
                "property_id": rule.get("property_id") or booking.get("property_id"),
                "booking_id": bid,
                "guest_name": booking.get("guest_name") or booking.get("guest"),
                "ok": result.get("ok"),
                "reason": result.get("reason"),
                "fired_at": now_iso,
            })
            await db.guest_journey_rules.update_one(
                {"id": rid}, {"$inc": {"fires_count": 1}, "$set": {"last_fired_at": now_iso}}
            )
            total_fires += 1

    return {"rules_processed": rules_processed, "fires": total_fires}


async def journey_engine_loop(db, interval_seconds: int = 60):
    """Forever loop. Polls every `interval_seconds` and fires due rules."""
    _journey_logger.info("🎯 Journey Engine loop started")
    while True:
        try:
            stats = await _journey_run_once(db)
            if stats.get("fires", 0) > 0:
                _journey_logger.info(
                    f"🎯 Journey engine fired {stats['fires']} action(s) across "
                    f"{stats['rules_processed']} rule(s)"
                )
        except Exception as e:
            _journey_logger.exception(f"Journey engine error: {e}")
        await asyncio.sleep(interval_seconds)
