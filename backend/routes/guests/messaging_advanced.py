"""
Advanced Messaging Features — Chatlyn Competitor Parity
Internal Notes, Snooze, Translate, Booking Sidebar, Analytics, Webchat Widget, Contact Lists
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from collections import defaultdict
import os
import uuid
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)


def create_messaging_advanced_router(db, require_roles, LlmChat, UserMessage):
    router = APIRouter()

    # ==================== 1. INTERNAL NOTES ====================

    @router.get("/messaging/notes/{conv_id}")
    async def list_notes(conv_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        docs = await db.conversation_notes.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/messaging/notes")
    async def create_note(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        note = {
            "id": str(uuid.uuid4()),
            "conversation_id": data.get("conversation_id"),
            "author_id": current_user.get("id", "admin"),
            "author_name": current_user.get("name", "Staff"),
            "content": data.get("content", ""),
            "mentions": data.get("mentions", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.conversation_notes.insert_one(note)
        note.pop("_id", None)
        return note

    @router.delete("/messaging/notes/{note_id}")
    async def delete_note(note_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.conversation_notes.delete_one({"id": note_id})
        return {"status": "deleted"}

    # ==================== 2. CONVERSATION SNOOZE ====================

    @router.post("/messaging/conversations/{conv_id}/snooze")
    async def snooze_conversation(conv_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        duration_minutes = data.get("duration_minutes", 120)
        snooze_until = (datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)).isoformat()
        await db.conversations.update_one({"id": conv_id}, {"$set": {
            "status": "snoozed",
            "snoozed_until": snooze_until,
            "snoozed_by": current_user.get("name", "Staff"),
        }})
        return {"status": "snoozed", "snoozed_until": snooze_until}

    @router.post("/messaging/conversations/{conv_id}/unsnooze")
    async def unsnooze_conversation(conv_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        await db.conversations.update_one({"id": conv_id}, {
            "$set": {"status": "in_progress"},
            "$unset": {"snoozed_until": "", "snoozed_by": ""}
        })
        return {"status": "unsnoozed"}

    @router.post("/messaging/snooze/check")
    async def check_snoozed_conversations(current_user: dict = Depends(require_roles("admin", "manager"))):
        """Wake up any conversations past their snooze time"""
        now = datetime.now(timezone.utc).isoformat()
        result = await db.conversations.update_many(
            {"status": "snoozed", "snoozed_until": {"$lte": now}},
            {"$set": {"status": "in_progress"}, "$unset": {"snoozed_until": "", "snoozed_by": ""}}
        )
        return {"woken_up": result.modified_count}

    # ==================== 3. ONE-CLICK TRANSLATE ====================

    @router.post("/messaging/translate")
    async def translate_message(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        text = data.get("text", "")
        target_language = data.get("target_language", "English")
        if not text:
            raise HTTPException(400, "No text provided")
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            raise HTTPException(500, "AI not configured")
        try:
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"translate-{uuid.uuid4()}",
                system_message="You are a professional translator for hotel guest communication. Translate the given text accurately while maintaining the tone and context. Return ONLY the translated text, nothing else."
            ).with_model("openai", "gpt-5.2")
            prompt = f"Translate the following text to {target_language}:\n\n{text}"
            reply = await chat.send_message(UserMessage(text=prompt))
            return {"translated_text": reply.strip(), "target_language": target_language, "original_text": text}
        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise HTTPException(500, "Translation failed")

    @router.post("/messaging/detect-language")
    async def detect_language(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        text = data.get("text", "")
        if not text:
            return {"language": "Unknown"}
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            return {"language": "Unknown"}
        try:
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"detect-{uuid.uuid4()}",
                system_message="Detect the language of the given text. Respond with ONLY the language name in English (e.g., 'Spanish', 'German', 'Japanese'). Nothing else."
            ).with_model("openai", "gpt-5.2")
            reply = await chat.send_message(UserMessage(text=text))
            return {"language": reply.strip()}
        except Exception:
            return {"language": "Unknown"}

    # ==================== 4. GUEST BOOKING DATA SIDEBAR ====================

    @router.get("/messaging/guest-booking-data/{conv_id}")
    async def get_guest_booking_data(conv_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        conv = await db.conversations.find_one({"id": conv_id}, {"_id": 0})
        if not conv:
            raise HTTPException(404, "Conversation not found")

        guest_email = conv.get("guest_email", "")
        guest_phone = conv.get("guest_phone", "")
        guest_name = conv.get("guest_name", "")

        query_conditions = []
        if guest_email:
            query_conditions.append({"guest_email": guest_email})
        if guest_phone:
            query_conditions.append({"guest_phone": guest_phone})
        if guest_name:
            query_conditions.append({"guest_name": {"$regex": guest_name, "$options": "i"}})

        bookings = []
        if query_conditions:
            bookings = await db.bookings.find(
                {"$or": query_conditions}, {"_id": 0}
            ).sort("check_in", -1).to_list(20)

        # Get guest profile if exists
        profile = None
        if guest_email:
            profile = await db.guest_profiles.find_one({"email": guest_email}, {"_id": 0})
        elif guest_name:
            profile = await db.guest_profiles.find_one({"name": {"$regex": guest_name, "$options": "i"}}, {"_id": 0})

        total_stays = len(bookings)
        total_spent = sum(b.get("total_price", 0) for b in bookings)

        # Find room type names
        for b in bookings:
            rt = await db.room_types.find_one({"id": b.get("room_type_id")}, {"_id": 0, "name": 1})
            b["room_name"] = rt["name"] if rt else b.get("room_type_id", "")

        return {
            "guest_name": guest_name,
            "guest_email": guest_email,
            "guest_phone": guest_phone,
            "total_stays": total_stays,
            "total_spent": total_spent,
            "bookings": bookings[:10],
            "profile": profile,
            "vip": profile.get("vip", False) if profile else False,
            "loyalty_tier": profile.get("loyalty_tier", "standard") if profile else "standard",
            "preferred_language": profile.get("preferences", {}).get("language", "") if profile else "",
        }

    # ==================== 5. CONVERSATION ANALYTICS ====================

    @router.get("/messaging/analytics/{property_id}")
    async def conversation_analytics(property_id: str, period: str = "30d", current_user: dict = Depends(require_roles("admin", "manager"))):
        days = int(period.replace("d", "")) if "d" in period else 30
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # All conversations in period
        convs = await db.conversations.find(
            {"property_id": property_id, "created_at": {"$gte": cutoff}}, {"_id": 0}
        ).to_list(5000)

        # All messages in period
        conv_ids = [c["id"] for c in convs]
        all_messages = await db.messages.find(
            {"conversation_id": {"$in": conv_ids}}, {"_id": 0}
        ).to_list(50000) if conv_ids else []

        # --- Volume by channel ---
        by_channel = defaultdict(int)
        for c in convs:
            by_channel[c.get("channel", "internal")] += 1

        # --- Volume by status ---
        by_status = defaultdict(int)
        for c in convs:
            by_status[c.get("status", "new")] += 1

        # --- Volume by agent ---
        by_agent = defaultdict(int)
        for c in convs:
            agent = c.get("assigned_name") or "Unassigned"
            by_agent[agent] += 1

        # --- Heatmap: conversations by day of week × hour ---
        heatmap = [[0]*24 for _ in range(7)]
        for c in convs:
            try:
                dt = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                heatmap[dt.weekday()][dt.hour] += 1
            except Exception:
                pass

        # --- First Response Time (FRT) ---
        frt_values = []
        for c in convs:
            conv_msgs = sorted(
                [m for m in all_messages if m["conversation_id"] == c["id"]],
                key=lambda m: m.get("created_at", "")
            )
            first_guest = next((m for m in conv_msgs if m.get("sender_type") == "guest"), None)
            first_staff = next((m for m in conv_msgs if m.get("sender_type") in ("staff", "ai")), None)
            if first_guest and first_staff:
                try:
                    t1 = datetime.fromisoformat(first_guest["created_at"].replace("Z", "+00:00"))
                    t2 = datetime.fromisoformat(first_staff["created_at"].replace("Z", "+00:00"))
                    diff = (t2 - t1).total_seconds() / 60
                    if diff >= 0:
                        frt_values.append(diff)
                except Exception:
                    pass

        avg_frt = round(sum(frt_values) / len(frt_values), 1) if frt_values else 0

        # --- Resolution Time ---
        resolution_values = []
        for c in convs:
            if c.get("status") == "resolved":
                conv_msgs = sorted(
                    [m for m in all_messages if m["conversation_id"] == c["id"]],
                    key=lambda m: m.get("created_at", "")
                )
                if conv_msgs:
                    try:
                        t1 = datetime.fromisoformat(conv_msgs[0]["created_at"].replace("Z", "+00:00"))
                        t2 = datetime.fromisoformat(conv_msgs[-1]["created_at"].replace("Z", "+00:00"))
                        diff = (t2 - t1).total_seconds() / 60
                        if diff >= 0:
                            resolution_values.append(diff)
                    except Exception:
                        pass

        avg_resolution = round(sum(resolution_values) / len(resolution_values), 1) if resolution_values else 0

        # --- Daily volume trend ---
        daily = defaultdict(int)
        for c in convs:
            try:
                day = c["created_at"][:10]
                daily[day] += 1
            except Exception:
                pass
        daily_trend = [{"date": k, "count": v} for k, v in sorted(daily.items())]

        # --- Sentiment breakdown ---
        sentiment_counts = defaultdict(int)
        for c in convs:
            sentiment_counts[c.get("sentiment", "neutral")] += 1

        # --- Resolution rate ---
        total = len(convs)
        resolved = sum(1 for c in convs if c.get("status") == "resolved")
        resolution_rate = round((resolved / total) * 100, 1) if total else 0

        # --- By label/tag ---
        by_tag = defaultdict(int)
        for c in convs:
            for tag in c.get("tags", []):
                by_tag[tag] += 1

        return {
            "period_days": days,
            "total_conversations": total,
            "avg_first_response_min": avg_frt,
            "avg_resolution_min": avg_resolution,
            "resolution_rate": resolution_rate,
            "by_channel": dict(by_channel),
            "by_status": dict(by_status),
            "by_agent": dict(by_agent),
            "by_tag": dict(by_tag),
            "sentiment": dict(sentiment_counts),
            "heatmap": heatmap,
            "daily_trend": daily_trend,
        }

    # ==================== 6. WEBCHAT WIDGET CONFIGURATOR ====================

    @router.get("/messaging/webchat-config/{property_id}")
    async def get_webchat_config(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.webchat_configs.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            default = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "enabled": True,
                "widget_color": "#2563eb",
                "widget_position": "bottom-right",
                "welcome_message": "Hello! How can we help you today?",
                "offline_message": "We're currently offline. Leave a message and we'll get back to you.",
                "avatar_url": "",
                "hotel_name": "",
                "auto_reply_enabled": True,
                "ai_enabled": True,
                "show_agent_name": True,
                "show_agent_photo": False,
                "require_email": False,
                "require_name": True,
                "bubble_text": "Chat with us",
                "operating_hours": {"enabled": False, "start": "08:00", "end": "22:00", "timezone": "UTC"},
                "custom_css": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.webchat_configs.insert_one(default)
            default.pop("_id", None)
            return default
        return doc

    @router.put("/messaging/webchat-config/{property_id}")
    async def update_webchat_config(property_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.webchat_configs.update_one({"property_id": property_id}, {"$set": updates}, upsert=True)
        doc = await db.webchat_configs.find_one({"property_id": property_id}, {"_id": 0})
        return doc

    @router.get("/messaging/webchat-embed/{property_id}")
    async def get_webchat_embed_code(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate embeddable HTML snippet for the webchat widget"""
        config = await db.webchat_configs.find_one({"property_id": property_id}, {"_id": 0})
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
        embed = f"""<!-- MyHotelBox Live Chat Widget -->
<script>
  (function(){{
    var w=document.createElement('script');
    w.src='{base_url}/api/messaging/webchat-widget.js?pid={property_id}';
    w.async=true;
    document.head.appendChild(w);
  }})();
</script>"""
        return {"embed_code": embed, "config": config}

    # ==================== 7. CONTACT LISTS ====================

    @router.get("/messaging/contact-lists/{property_id}")
    async def list_contact_lists(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.contact_lists.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return docs

    @router.post("/messaging/contact-lists")
    async def create_contact_list(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        cl = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "list_type": data.get("list_type", "static"),
            "filters": data.get("filters", {}),
            "member_count": 0,
            "members": data.get("members", []),
            "created_by": current_user.get("name", "Staff"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.contact_lists.insert_one(cl)
        cl.pop("_id", None)
        return cl

    @router.put("/messaging/contact-lists/{list_id}")
    async def update_contact_list(list_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.contact_lists.update_one({"id": list_id}, {"$set": updates})
        doc = await db.contact_lists.find_one({"id": list_id}, {"_id": 0})
        return doc

    @router.delete("/messaging/contact-lists/{list_id}")
    async def delete_contact_list(list_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.contact_lists.delete_one({"id": list_id})
        return {"status": "deleted"}

    @router.get("/messaging/contact-lists/{list_id}/members")
    async def get_list_members(list_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        cl = await db.contact_lists.find_one({"id": list_id}, {"_id": 0})
        if not cl:
            raise HTTPException(404, "List not found")

        if cl.get("list_type") == "dynamic":
            # Build dynamic member list from filters
            filters = cl.get("filters", {})
            query = {}
            if filters.get("vip"):
                query["vip"] = True
            if filters.get("loyalty_tier"):
                query["loyalty_tier"] = filters["loyalty_tier"]
            if filters.get("min_stays"):
                query["total_stays"] = {"$gte": filters["min_stays"]}
            if filters.get("tags"):
                query["tags"] = {"$in": filters["tags"]}
            if filters.get("min_spend"):
                query["total_spend"] = {"$gte": filters["min_spend"]}

            profiles = await db.guest_profiles.find(query, {"_id": 0}).to_list(500)
            members = [{"name": p.get("name", ""), "email": p.get("email", ""), "phone": p.get("phone", ""), "vip": p.get("vip", False)} for p in profiles]
            # Update count
            await db.contact_lists.update_one({"id": list_id}, {"$set": {"member_count": len(members)}})
            return {"list_id": list_id, "list_type": "dynamic", "members": members, "total": len(members)}
        else:
            # Static list — return stored members
            members = cl.get("members", [])
            return {"list_id": list_id, "list_type": "static", "members": members, "total": len(members)}

    @router.post("/messaging/contact-lists/{list_id}/add-member")
    async def add_list_member(list_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        member = {
            "name": data.get("name", ""),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.contact_lists.update_one(
            {"id": list_id},
            {"$push": {"members": member}, "$inc": {"member_count": 1}}
        )
        return {"status": "added", "member": member}

    @router.post("/messaging/contact-lists/{list_id}/remove-member")
    async def remove_list_member(list_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        email = data.get("email", "")
        await db.contact_lists.update_one(
            {"id": list_id},
            {"$pull": {"members": {"email": email}}, "$inc": {"member_count": -1}}
        )
        return {"status": "removed"}

    return router
