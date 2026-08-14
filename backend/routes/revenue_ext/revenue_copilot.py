"""
AI Revenue Copilot — GPT-5.2 powered chat assistant for revenue management
Analyzes hotel data and provides natural language insights and recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import json
import re
import uuid
import os
import calendar
import logging

logger = logging.getLogger(__name__)

ACTION_RE = re.compile(r"```action\s*(\{.*?\})\s*```", re.DOTALL)


ALL_ACTION_TYPES = ("rate_set", "rate_adjust_pct", "set_guardrail", "apply_overbooking",
                    "run_optimizer", "learn_now", "analyze_sensitivity", "expert_brief",
                    "simulate_lesson")


def _extract_action(text: str):
    """LLM yanıtındaki ```action {...}``` bloğunu ayıkla ve metinden çıkar."""
    m = ACTION_RE.search(text or "")
    if not m:
        return text, None
    try:
        action = json.loads(m.group(1))
    except Exception:
        return ACTION_RE.sub("", text).strip(), None
    if action.get("type") not in ALL_ACTION_TYPES:
        return ACTION_RE.sub("", text).strip(), None
    action["id"] = str(uuid.uuid4())[:8]
    action["status"] = "proposed"
    return ACTION_RE.sub("", text).strip(), action


async def _execute_action(db, pid: str, action: dict, user_name: str) -> dict:
    t = action.get("type")
    now = datetime.now(timezone.utc).isoformat()
    if t in ("rate_set", "rate_adjust_pct"):
        from routes.distribution.push_history import resolve_rate
        sd = datetime.strptime(action["start_date"], "%Y-%m-%d").date()
        ed = datetime.strptime(action["end_date"], "%Y-%m-%d").date()
        if (ed - sd).days > 60 or ed < sd:
            raise HTTPException(400, "Tarih aralığı geçersiz (maks 60 gün)")
        n = 0
        d = sd
        while d <= ed:
            ds = d.isoformat()
            if t == "rate_set":
                rate = round(float(action["rate"]), 2)
            else:
                base, _src = await resolve_rate(db, pid, ds)
                rate = round(base * (1 + float(action["pct"]) / 100), 2)
            await db.rate_overrides.update_one(
                {"property_id": pid, "date": ds},
                {"$set": {"property_id": pid, "date": ds, "custom_rate": rate,
                          "source": "copilot_chat", "set_by": user_name, "set_at": now,
                          "context": {"copilot_action": action.get("summary", "")}}},
                upsert=True)
            n += 1
            d += timedelta(days=1)
        return {"ok": True, "dates_updated": n,
                "detail": f"{n} günün fiyatı güncellendi"}
    if t == "set_guardrail":
        pct = float(action.get("value") or 0)
        if not 5 <= pct <= 50:
            raise HTTPException(400, "Guardrail 5-50 arası olmalı")
        await db.rms_settings.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "guardrail_pct": pct,
                      "updated_by": user_name, "updated_at": now}}, upsert=True)
        return {"ok": True, "detail": f"Guardrail ±%{pct} olarak ayarlandı"}
    if t == "apply_overbooking":
        from routes.revenue_ext.overbooking_control import _compute_analysis
        data = await _compute_analysis(db, pid, 14)
        applied, extra = 0, 0
        for r in data["days"]:
            limit = r["recommended_overbooking_limit"]
            await db.overbooking_limits.update_one(
                {"property_id": pid, "date": r["date"]},
                {"$set": {"property_id": pid, "date": r["date"], "limit": limit,
                          "capacity": data["capacity"], "sell_limit": data["capacity"] + limit,
                          "is_active": True, "source": "copilot_chat",
                          "applied_at": now, "applied_by": user_name},
                 "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
            applied += 1
            extra += limit
        return {"ok": True, "detail": f"{applied} günün overbooking limiti uygulandı (+{extra} oda)"}
    if t == "run_optimizer":
        from routes.revenue_ext.open_pricing import run_open_pricing_optimizer
        days = int(action.get("days") or 14)
        res = await run_open_pricing_optimizer(db, pid, days=days, apply=True)
        return {"ok": True, "detail": f"Optimizer çalıştı: {res['overrides_written']} hücre fiyatı üretildi "
                                      f"(guardrail ±%{res['guardrail_pct']}, {res['days']} gün)"}
    if t == "learn_now":
        from routes.revenue_ext.revenue_brain import run_learning_cycle
        res = await run_learning_cycle(db, pid)
        return {"ok": True, "detail": f"Öğrenme döngüsü bitti: {res['measured']} sonuç ölçüldü, "
                                      f"{res['weights_updated']} çarpan, {res['memory_consolidated']} kalıcı hafıza, "
                                      f"{res.get('regional_memory_updated', 0)} bölgesel, {res['global_memory_updated']} küresel ders"}
    if t == "analyze_sensitivity":
        from routes.revenue_ext.rm_expertise import compute_sensitivity
        res = await compute_sensitivity(db, pid)
        tops = "; ".join(f"{b['dow_type']}/{b['band']}: {b['label']}" for b in res["buckets"][:3])
        return {"ok": True, "detail": f"Duyarlılık analizi bitti ({res['sample_total']} örnek). {tops or 'Henüz yeterli örnek yok.'}"}
    if t == "expert_brief":
        from routes.revenue_ext.rm_expertise import generate_expert_brief
        doc = await generate_expert_brief(db, pid, user_name)
        return {"ok": True, "detail": "Uzman strateji brifingi üretildi — Öğrenen Beyin → Alan Uzmanlığı sekmesinde.",
                "brief_excerpt": (doc.get("content") or "")[:400]}
    if t == "simulate_lesson":
        from routes.revenue_ext.revenue_brain import simulate_lesson_impact
        res = await simulate_lesson_impact(db, pid, (action.get("bucket_key") or "").strip())
        return {"ok": True, "detail": f"Simülasyon: {res['affected_days']} gün etkilenir, 14 günlük tahmini etki "
                                      f"{res['est_revenue_delta_14d']}. {res['recommendation']}"}
    raise HTTPException(400, "Bilinmeyen aksiyon tipi")


def create_revenue_copilot_router(db, require_roles):
    router = APIRouter()

    async def _build_hotel_context(db, property_id):
        """Aggregate live hotel data into a context string for the AI."""
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        props = await db.properties.find({}, {"_id": 0}).to_list(50) if property_id == "all" else [await db.properties.find_one({"id": property_id}, {"_id": 0})]
        props = [p for p in props if p]

        total_rooms = 0
        total_booked = 0
        total_rev_today = 0
        for p in props:
            pid = p.get("id", "")
            rooms = await db.rooms.count_documents({"property_id": pid}) or 10
            total_rooms += rooms
            booked = await db.bookings.count_documents({"property_id": pid, "check_in": {"$lte": today_str}, "check_out": {"$gt": today_str}, "status": {"$ne": "cancelled"}})
            total_booked += booked
            bks = await db.bookings.find({"property_id": pid, "check_in": {"$lte": today_str}, "check_out": {"$gt": today_str}}, {"_id": 0, "total_price": 1, "nights": 1}).to_list(200)
            total_rev_today += sum(float(b.get("total_price", 0) or 0) / max(int(b.get("nights", 1) or 1), 1) for b in bks)

        today_occ = min(100, round((total_booked / max(total_rooms, 1)) * 100))
        adr = round(total_rev_today / max(total_booked, 1), 2)
        revpar = round(total_rev_today / max(total_rooms, 1), 2)

        # Next 7 days
        next7 = []
        for i in range(1, 8):
            d = now + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            b = 0
            for p in props:
                b += await db.bookings.count_documents({"property_id": p.get("id", ""), "check_in": {"$lte": ds}, "check_out": {"$gt": ds}, "status": {"$ne": "cancelled"}})
            occ = min(100, round((b / max(total_rooms, 1)) * 100))
            next7.append(f"{d.strftime('%A %b %d')}: {occ}% occupancy ({b}/{total_rooms} rooms)")

        # Booking pace
        next_week = (now + timedelta(days=7)).strftime("%Y-%m-%d")
        pace = 0
        for p in props:
            pace += await db.bookings.count_documents({"property_id": p.get("id", ""), "check_in": {"$gte": today_str, "$lte": next_week}, "status": {"$ne": "cancelled"}})

        # Strategy
        strategy = await db.pricing_strategy.find_one({"property_id": property_id}, {"_id": 0}) or {}
        dow_adj = strategy.get("dow_adjustments", {})
        monthly_adj = strategy.get("monthly_adjustments", {})
        agg = strategy.get("aggressiveness", 1.0)

        # Monthly performance
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        mtd_rev = 0
        mtd_nights = 0
        for p in props:
            bks = await db.bookings.find({"property_id": p.get("id", ""), "check_in": {"$gte": month_start}}, {"_id": 0, "total_price": 1, "nights": 1}).to_list(500)
            for b in bks:
                mtd_rev += float(b.get("total_price", 0) or 0)
                mtd_nights += max(1, int(b.get("nights", 1) or 1))

        # Channel mix
        channel_mix = {}
        for p in props:
            bks = await db.bookings.find({"property_id": p.get("id", ""), "check_in": {"$gte": (now - timedelta(days=30)).strftime("%Y-%m-%d")}}, {"_id": 0, "source": 1}).to_list(500)
            for b in bks:
                src = b.get("source", "Direct") or "Direct"
                channel_mix[src] = channel_mix.get(src, 0) + 1

        context = f"""HOTEL DATA SNAPSHOT (as of {now.strftime('%A, %B %d, %Y %H:%M UTC')}):

PROPERTIES: {len(props)} properties, {total_rooms} total rooms

TODAY'S PERFORMANCE:
- Occupancy: {today_occ}% ({total_booked}/{total_rooms} rooms occupied)
- ADR (Average Daily Rate): £{adr}
- RevPAR: £{revpar}
- Daily Revenue: £{round(total_rev_today, 2)}

NEXT 7 DAYS OUTLOOK:
{chr(10).join(next7)}

BOOKING PACE: {pace} check-ins in next 7 days

MONTH-TO-DATE ({now.strftime('%B')}):
- Total Revenue: £{round(mtd_rev, 2)}
- Room Nights Sold: {mtd_nights}
- Avg ADR: £{round(mtd_rev / max(mtd_nights, 1), 2)}

CHANNEL MIX (Last 30 days):
{chr(10).join(f'- {ch}: {cnt} bookings' for ch, cnt in sorted(channel_mix.items(), key=lambda x: -x[1]))}

PRICING STRATEGY:
- Day-of-Week Adjustments: {dow_adj if dow_adj else 'Not configured'}
- Monthly Adjustments: {monthly_adj if monthly_adj else 'Not configured'}
- Aggressiveness: {agg}x
- Target Occupancy: {strategy.get('target_occupancy', 'Not set')}

COMMISSION RATES: Booking.com 15%, Expedia 18%, Airbnb 3%, Direct 0%
"""
        # 🧠 Robot hafızası (kalıcı + bölgesel + küresel) — chat'e beslenir
        try:
            mem = await db.revenue_brain_memory.find(
                {"property_id": property_id}, {"_id": 0, "detail": 1, "status": 1,
                 "times_confirmed": 1, "first_learned": 1}).sort("times_confirmed", -1).to_list(6)
            if mem:
                context += ("\nKALICI HAFIZA (bu otelin asla silinmeyen dersleri — tavsiyelerinde ATIF YAP):\n"
                            + "\n".join(f"- [{str(m.get('first_learned',''))[:10]}'den beri, "
                                        f"{m.get('times_confirmed',1)}x doğrulandı, {m.get('status')}] {m['detail']}"
                                        for m in mem))
            prop_doc = await db.properties.find_one({"id": property_id}, {"_id": 0, "country": 1, "city": 1})
            region = ((prop_doc or {}).get("country") or (prop_doc or {}).get("city") or "diger").strip() or "diger"
            rmem = await db.revenue_brain_regional_memory.find(
                {"region": region}, {"_id": 0, "detail": 1}).sort("samples", -1).to_list(4)
            if rmem:
                context += (f"\n\nBÖLGESEL HAFIZA ({region}):\n" + "\n".join(f"- {m['detail']}" for m in rmem))
            gmem = await db.revenue_brain_global_memory.find(
                {}, {"_id": 0, "detail": 1}).sort("samples", -1).to_list(4)
            if gmem:
                context += ("\n\nKÜRESEL HAFIZA (tüm portföy):\n" + "\n".join(f"- {m['detail']}" for m in gmem))
            from routes.revenue_ext.rm_expertise import expertise_context_for_llm
            context += "\n" + await expertise_context_for_llm(db, property_id)
            from routes.revenue_ext.ml_pickup import ml_pickup_summary_for_llm
            context += await ml_pickup_summary_for_llm(db, property_id)
        except Exception:
            pass
        return context

    SYSTEM_PROMPT = """You are the AI Revenue Copilot for My Hotel Box — an expert, opinionated hotel revenue manager. Deep knowledge of dynamic pricing, demand forecasting, occupancy/gap management, competitive analysis and profit optimization.

LANGUAGE: ALWAYS respond in the user's language. If the user writes in Turkish, respond in Turkish.

EXPERT IDENTITY: You are the BEST revenue manager in the business — 20+ years across luxury chains and independents. All knowledge in your context (RM UZMANLIK TABANI, DERİN UZMANLIK BİLGİN, İÇSELLEŞTİRDİĞİN UZMAN KURALLARIN) is YOUR OWN internalized expertise. NEVER say "kaynaklara göre", "bilgi tabanına göre", "kütüphanede", or cite any source/library — speak first-person, decisively, as your own knowledge. ALWAYS convert theory into THIS hotel's concrete numbers and applicable steps (dates, rates, percentages). Your obsession: maximum profit AND maximum occupancy, in that order of priority when they conflict.

Your role:
1. Chat naturally about revenue, occupancy, empty-night gaps, pricing, channels — answer questions and give advice tied to the live data snapshot.
2. You are a FULL DOMAIN EXPERT in revenue management: pricing theory, elasticity, displacement, hurdle/LRV, open pricing, forecasting, overbooking science, TRevPAR/GOPPAR, the 2026 RMS competitor landscape and market trends — all internalized as your own mastery.
3. Recommend specific actions with exact numbers and clear reasoning.
4. DEFEND YOUR STRATEGY: You are not a yes-man. If the user proposes something that contradicts the data or the robot's measured lessons (KALICI/BÖLGESEL/KÜRESEL HAFIZA) or measured price sensitivity, politely push back with evidence and defend your own correct strategy. Only if the user explicitly insists, accept — but state the risk clearly first.
5. Reference the robot's memory lessons explicitly when relevant ("Hafızamdaki derse göre...").

ACTION PROTOCOL — when you and the user AGREE on a concrete executable decision, end your message with EXACTLY ONE fenced action block so the system can apply it with one click:
```action
{"type": "rate_set", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "rate": 120, "summary": "kısa Türkçe özet"}
```
Supported types:
- rate_set: fixed nightly rate for a date range (fields: start_date, end_date, rate)
- rate_adjust_pct: percentage change on current rates (fields: start_date, end_date, pct e.g. 10 or -5)
- set_guardrail: optimizer guardrail band percent (field: value, 5-50)
- apply_overbooking: apply recommended overbooking limits for next 14 days (no extra fields)
- run_optimizer: run the open-pricing optimizer now and apply cell rates (optional field: days, default 14)
- learn_now: run a full learning cycle now (measure outcomes, update weights, consolidate permanent/regional/global memory)
- analyze_sensitivity: recompute price elasticity/sensitivity from measured outcomes
- expert_brief: generate a full expert strategy brief (market + competitors + sensitivity + memory)
- simulate_lesson: simulate 14-day revenue impact of disabling a memory lesson (field: bucket_key e.g. "0-3|weekday|down")
You are CAPABLE of executing ALL of the above yourself once the user approves — never say you cannot do these.
Rules: max 60-day range; only include the block when a decision is actually agreed or the user asks you to run an operation; never invent other types; always include a Turkish "summary".

Guidelines:
- Be specific with numbers; tie every recommendation to data points
- Use GBP (£)
- Consider channel costs (Direct saves 15-18% vs OTAs)
- Flag opportunities AND risks; think TRevPAR, not just occupancy
- Keep responses concise but data-rich"""

    @router.get("/revenue/copilot/{property_id}/history")
    async def get_copilot_history(property_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        user_id = current_user.get("email", "")
        messages = await db.revenue_copilot_messages.find(
            {"property_id": property_id,
             "user_id": {"$in": [user_id, "robot-brifing"]}},
            {"_id": 0}
        ).sort("created_at", 1).to_list(50)
        return {"messages": messages}

    @router.post("/revenue/copilot/{property_id}/chat")
    async def copilot_chat(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        user_text = data.get("message", "").strip()
        if not user_text:
            return {"error": "Message is required"}

        user_id = current_user.get("email", "")
        session_id = f"rev-copilot-{property_id}-{user_id}"
        now = datetime.now(timezone.utc)

        # Save user message
        user_msg = {
            "id": str(uuid.uuid4())[:8],
            "property_id": property_id,
            "user_id": user_id,
            "role": "user",
            "content": user_text,
            "created_at": now.isoformat(),
        }
        await db.revenue_copilot_messages.insert_one(user_msg)

        # Build hotel context
        hotel_context = await _build_hotel_context(db, property_id)
        try:
            from routes.revenue_ext.rm_knowledge_seed import knowledge_context_for_chat
            hotel_context += await knowledge_context_for_chat(db, user_text)
        except Exception:
            pass

        # Get recent chat history for context
        recent = await db.revenue_copilot_messages.find(
            {"property_id": property_id, "user_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(10)
        recent.reverse()

        # Build conversation context
        history_text = ""
        for msg in recent[:-1]:  # Exclude current message
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"

        full_system = f"{SYSTEM_PROMPT}\n\n{hotel_context}\n\nRecent conversation:\n{history_text}" if history_text else f"{SYSTEM_PROMPT}\n\n{hotel_context}"

        try:
            api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            chat = LlmChat(
                api_key=api_key,
                session_id=session_id,
                system_message=full_system
            ).with_model("openai", "gpt-5.2")

            user_message = UserMessage(text=user_text)
            response = await chat.send_message(user_message)
            display_text, action = _extract_action(response)

            # Save assistant message
            assistant_msg = {
                "id": str(uuid.uuid4())[:8],
                "property_id": property_id,
                "user_id": user_id,
                "role": "assistant",
                "content": display_text,
                "action": action,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.revenue_copilot_messages.insert_one(assistant_msg)

            return {
                "response": display_text,
                "action": action,
                "message_id": assistant_msg["id"],
            }
        except Exception as e:
            logger.error(f"Copilot error: {e}")
            error_msg = {
                "id": str(uuid.uuid4())[:8],
                "property_id": property_id,
                "user_id": user_id,
                "role": "assistant",
                "content": f"I encountered an issue analyzing your data. Please try again. Error: {str(e)[:100]}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.revenue_copilot_messages.insert_one(error_msg)
            return {"response": error_msg["content"], "message_id": error_msg["id"]}

    @router.post("/revenue/copilot/{property_id}/apply-action/{action_id}")
    async def apply_copilot_action(property_id: str, action_id: str,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Chat'te birlikte alınan kararı robota uygulat (1 tık)."""
        msg = await db.revenue_copilot_messages.find_one(
            {"property_id": property_id, "action.id": action_id}, {"_id": 0})
        if not msg or not msg.get("action"):
            raise HTTPException(404, "Aksiyon bulunamadı")
        action = msg["action"]
        if action.get("status") == "applied":
            return {"ok": True, "already_applied": True, "detail": "Bu karar zaten uygulanmış"}
        user_name = current_user.get("name") or current_user.get("email", "")
        result = await _execute_action(db, property_id, action, user_name)
        await db.revenue_copilot_messages.update_one(
            {"property_id": property_id, "action.id": action_id},
            {"$set": {"action.status": "applied",
                      "action.applied_at": datetime.now(timezone.utc).isoformat(),
                      "action.applied_by": user_name,
                      "action.result": result.get("detail", "")}})
        return {**result, "action_id": action_id, "status": "applied"}

    @router.delete("/revenue/copilot/{property_id}/clear")
    async def clear_copilot_history(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        user_id = current_user.get("email", "")
        result = await db.revenue_copilot_messages.delete_many({"property_id": property_id, "user_id": user_id})
        return {"message": f"Cleared {result.deleted_count} messages"}

    return router
