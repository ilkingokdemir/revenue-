"""
AI Weekly Revenue Digest — GPT-5.2 executive summary analyzing the week's
performance, highlighting wins/risks, and suggesting priority actions.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import os
import logging

logger = logging.getLogger(__name__)


def create_weekly_digest_router(db, require_roles, LlmChat, UserMessage):
    router = APIRouter()

    @router.get("/revenue/weekly-digest/{property_id}")
    async def get_weekly_digest(property_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get the latest weekly digest or generate a new one."""
        existing = await db.weekly_digests.find_one(
            {"property_id": property_id}, {"_id": 0}
        )
        if existing:
            return existing
        return {"status": "none", "message": "No digest generated yet. Click Generate to create one."}

    @router.post("/revenue/weekly-digest/{property_id}/generate")
    async def generate_weekly_digest(property_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate AI weekly revenue digest using GPT-5.2."""
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"error": "AI service not configured"}

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        today_str = now.strftime("%Y-%m-%d")
        week_ago_str = week_ago.strftime("%Y-%m-%d")

        # Gather data
        bk_query = {"status": {"$nin": ["cancelled"]}}
        if property_id != "all":
            bk_query["property_id"] = property_id

        # This week's bookings
        this_week = await db.bookings.find(
            {**bk_query, "created_at": {"$gte": week_ago_str}},
            {"_id": 0, "total_price": 1, "rate_per_night": 1, "nights": 1, "source": 1, "status": 1}
        ).to_list(500)

        new_bookings = len(this_week)
        week_revenue = round(sum(float(b.get("total_price", 0) or 0) for b in this_week), 2)
        week_room_nights = sum(int(b.get("nights", 1) or 1) for b in this_week)
        week_adr = round(week_revenue / max(week_room_nights, 1), 2)

        # Sources
        source_counts = {}
        for b in this_week:
            src = b.get("source", "Direct")
            source_counts[src] = source_counts.get(src, 0) + 1
        top_source = max(source_counts, key=source_counts.get) if source_counts else "N/A"

        # Total rooms
        total_rooms = 0
        if property_id != "all":
            total_rooms = await db.rooms.count_documents({"property_id": property_id})
        if total_rooms == 0:
            q = {} if property_id == "all" else {"property_id": property_id}
            rt_count = await db.room_types.count_documents(q)
            total_rooms = max(rt_count * 3, 10)

        # Occupancy this week (avg)
        occ_sum = 0
        for i in range(7):
            d = week_ago + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            booked = await db.bookings.count_documents({
                **bk_query, "check_in": {"$lte": ds}, "check_out": {"$gt": ds}
            })
            occ_sum += round((booked / max(total_rooms, 1)) * 100)
        avg_occ = round(occ_sum / 7)

        # Reviews this week
        reviews_count = await db.reviews.count_documents({"created_at": {"$gte": week_ago_str}})
        pending_reviews = await db.reviews.count_documents({"response_status": "pending"})

        # Price alerts
        alerts_count = await db.notifications.count_documents({
            "category": "price_intelligence", "created_at": {"$gte": week_ago_str}
        })

        # Build data summary for GPT
        data_summary = f"""
HOTEL WEEKLY PERFORMANCE REPORT ({week_ago_str} to {today_str}):

BOOKINGS: {new_bookings} new bookings this week
REVENUE: £{week_revenue} total, ADR £{week_adr}
ROOM NIGHTS SOLD: {week_room_nights}
AVG OCCUPANCY: {avg_occ}%
TOTAL ROOMS: {total_rooms}
TOP BOOKING SOURCE: {top_source} ({source_counts.get(top_source, 0)} bookings)
SOURCE BREAKDOWN: {', '.join(f'{k}: {v}' for k, v in sorted(source_counts.items(), key=lambda x: -x[1])[:5])}
REVIEWS: {reviews_count} new, {pending_reviews} awaiting response
PRICE ALERTS: {alerts_count} triggered this week
"""

        system_msg = """You are an expert hotel revenue manager writing a weekly executive digest.
Write a concise, actionable digest with these exact sections:
1. PERFORMANCE SUMMARY (2-3 sentences)
2. WINS THIS WEEK (2-3 bullet points of positive trends)
3. AREAS OF CONCERN (2-3 bullet points of risks or underperformance)
4. TOP 3 PRIORITY ACTIONS (numbered, specific and actionable for next week)
5. REVENUE OUTLOOK (1-2 sentences on next week's expectations)

Be specific with numbers. Be direct and confident. Use British English (£).
Keep the total under 300 words."""

        try:
            session_id = f"digest-{property_id}-{uuid.uuid4().hex[:8]}"
            chat = LlmChat(api_key=api_key, session_id=session_id, system_message=system_msg).with_model("openai", "gpt-5.2")
            digest_text = await chat.send_message(UserMessage(text=f"Generate the weekly revenue digest based on this data:\n{data_summary}"))
        except Exception as e:
            logger.error(f"Digest generation error: {e}")
            return {"error": f"AI generation failed: {str(e)[:80]}"}

        digest = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "week_start": week_ago_str,
            "week_end": today_str,
            "digest_text": digest_text,
            "metrics": {
                "new_bookings": new_bookings,
                "revenue": week_revenue,
                "adr": week_adr,
                "room_nights": week_room_nights,
                "avg_occupancy": avg_occ,
                "top_source": top_source,
                "reviews": reviews_count,
                "pending_reviews": pending_reviews,
                "price_alerts": alerts_count,
            },
            "generated_at": now.isoformat(),
            "generated_by": current_user.get("name", ""),
        }

        await db.weekly_digests.update_one(
            {"property_id": property_id},
            {"$set": digest}, upsert=True
        )

        return digest

    return router
