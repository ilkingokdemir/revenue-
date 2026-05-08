"""
AI Revenue Copilot — GPT-5.2 powered chat assistant for revenue management
Analyzes hotel data and provides natural language insights and recommendations.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import os
import calendar
import logging

logger = logging.getLogger(__name__)


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
        return context

    SYSTEM_PROMPT = """You are the AI Revenue Copilot for My Hotel Box, the most advanced hotel revenue management system in the market. You are an expert hotel revenue manager with deep knowledge of dynamic pricing, demand forecasting, competitive analysis, and profit optimization.

Your role:
1. Analyze the hotel's live data and provide actionable insights
2. Recommend specific pricing actions with clear reasoning
3. Identify revenue opportunities and risks
4. Answer revenue management questions in plain, concise language
5. Suggest what-if scenarios and their expected impact

Guidelines:
- Be specific with numbers — don't say "consider raising rates", say "increase Friday rates by £12 (15%) based on 90%+ occupancy trend"
- Always tie recommendations to data points
- Use GBP (£) currency
- Consider channel costs when recommending (Direct bookings save 15-18% vs OTAs)
- Flag both opportunities AND risks
- Keep responses concise but data-rich
- When suggesting actions, reference specific tabs: "Go to Pricing Strategy → Day-of-Week to adjust Friday rates"
- Think about TRevPAR (total revenue per available room), not just occupancy"""

    @router.get("/revenue/copilot/{property_id}/history")
    async def get_copilot_history(property_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        user_id = current_user.get("email", "")
        messages = await db.revenue_copilot_messages.find(
            {"property_id": property_id, "user_id": user_id},
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

            # Save assistant message
            assistant_msg = {
                "id": str(uuid.uuid4())[:8],
                "property_id": property_id,
                "user_id": user_id,
                "role": "assistant",
                "content": response,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.revenue_copilot_messages.insert_one(assistant_msg)

            return {
                "response": response,
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

    @router.delete("/revenue/copilot/{property_id}/clear")
    async def clear_copilot_history(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        user_id = current_user.get("email", "")
        result = await db.revenue_copilot_messages.delete_many({"property_id": property_id, "user_id": user_id})
        return {"message": f"Cleared {result.deleted_count} messages"}

    return router
