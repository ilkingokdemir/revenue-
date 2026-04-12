"""
Guest Messaging Hub Routes
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
from typing import Dict
import os
import uuid
import asyncio
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)

def create_messaging_router(db, require_roles, LlmChat, UserMessage, resend):
    """Factory function that creates messaging routes with injected dependencies"""
    router = APIRouter()

    @router.get("/messaging/conversations/{property_id}")
    async def list_conversations(
        property_id: str, status: str = "", channel: str = "", assigned_to: str = "",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        query = {"property_id": property_id}
        if status: query["status"] = status
        if channel: query["channel"] = channel
        if assigned_to: query["assigned_to"] = assigned_to
        docs = await db.conversations.find(query, {"_id": 0}).sort("last_message_at", -1).to_list(200)
        return docs

    @router.get("/messaging/conversations/{property_id}/stats")
    async def conversation_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        total = await db.conversations.count_documents({"property_id": property_id})
        new_count = await db.conversations.count_documents({"property_id": property_id, "status": "new"})
        in_progress = await db.conversations.count_documents({"property_id": property_id, "status": "in_progress"})
        waiting = await db.conversations.count_documents({"property_id": property_id, "status": "waiting"})
        resolved = await db.conversations.count_documents({"property_id": property_id, "status": "resolved"})
        pipeline = [
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": "$channel", "count": {"$sum": 1}}}
        ]
        channel_counts = {}
        async for doc in db.conversations.aggregate(pipeline):
            channel_counts[doc["_id"]] = doc["count"]
        unread = await db.conversations.count_documents({"property_id": property_id, "unread_count": {"$gt": 0}})
        return {
            "total": total, "new": new_count, "in_progress": in_progress,
            "waiting": waiting, "resolved": resolved, "unread": unread,
            "by_channel": channel_counts
        }

    @router.post("/messaging/conversations")
    async def create_conversation(
        data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        from models import Conversation
        conv = Conversation(**data)
        doc = conv.model_dump()
        await db.conversations.insert_one(doc)
        doc.pop("_id", None)
        asyncio.create_task(fire_webhooks(db, "conversation.created", {"id": doc.get("id"), "guest_name": doc.get("guest_name"), "channel": doc.get("channel")}))
        return doc

    @router.put("/messaging/conversations/{conv_id}")
    async def update_conversation(
        conv_id: str, updates: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.conversations.update_one({"id": conv_id}, {"$set": updates})
        doc = await db.conversations.find_one({"id": conv_id}, {"_id": 0})
        return doc

    @router.post("/messaging/conversations/{conv_id}/assign")
    async def assign_conversation(
        conv_id: str, user_id: str, user_name: str = "",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        await db.conversations.update_one({"id": conv_id}, {"$set": {
            "assigned_to": user_id, "assigned_name": user_name, "status": "in_progress"
        }})
        return {"status": "assigned"}

    @router.post("/messaging/conversations/{conv_id}/resolve")
    async def resolve_conversation(
        conv_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        await db.conversations.update_one({"id": conv_id}, {"$set": {"status": "resolved"}})
        asyncio.create_task(fire_webhooks(db, "conversation.resolved", {"id": conv_id}))
        await log_sync(db, "messaging", "internal", "success", f"Conversation {conv_id} resolved", conv_id)
        return {"status": "resolved"}

    @router.get("/messaging/messages/{conv_id}")
    async def list_messages(
        conv_id: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        await db.conversations.update_one({"id": conv_id}, {"$set": {"unread_count": 0}})
        docs = await db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
        return docs

    @router.post("/messaging/messages")
    async def send_message(
        data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        from models import Message
        msg = Message(**data, sender_type="staff", sender_name=current_user.get("name", "Staff"))
        doc = msg.model_dump()
        await db.messages.insert_one(doc)
        doc.pop("_id", None)

        conv = await db.conversations.find_one({"id": data["conversation_id"]}, {"_id": 0})
        channel = conv.get("channel", "") if conv else data.get("channel", "")

        await db.conversations.update_one(
            {"id": data["conversation_id"]},
            {"$set": {
                "last_message_preview": data["content"][:100],
                "last_message_at": datetime.now(timezone.utc).isoformat(),
                "status": "waiting"
            }}
        )

        # Auto-deliver via channel
        delivery_status = "internal"
        delivery_error = None
        if conv:
            property_id = conv.get("property_id", "")
            settings = await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0})

            if channel == "whatsapp" and settings and settings.get("whatsapp_enabled"):
                phone = conv.get("guest_phone", "")
                access_token = settings.get("whatsapp_access_token", "")
                phone_id = settings.get("whatsapp_phone_number_id", "")
                if phone and access_token and phone_id:
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                            payload = {"messaging_product": "whatsapp", "to": phone.replace("+", ""), "type": "text", "text": {"body": data["content"]}}
                            resp = await client.post(f"https://graph.facebook.com/v18.0/{phone_id}/messages",
                                json=payload, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
                            if resp.status_code == 200:
                                delivery_status = "delivered"
                            else:
                                delivery_status = "failed"
                                delivery_error = resp.text[:200]
                    except Exception as e:
                        delivery_status = "failed"
                        delivery_error = str(e)[:200]
                else:
                    delivery_status = "sandbox"

            elif channel == "telegram" and settings and settings.get("telegram_enabled"):
                chat_id = conv.get("guest_phone", "") or conv.get("telegram_chat_id", "")
                bot_token = settings.get("telegram_bot_token", "")
                if chat_id and bot_token:
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                            resp = await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                                json={"chat_id": chat_id, "text": data["content"]}, timeout=10)
                            if resp.status_code == 200:
                                delivery_status = "delivered"
                            else:
                                delivery_status = "failed"
                                delivery_error = resp.text[:200]
                    except Exception as e:
                        delivery_status = "failed"
                        delivery_error = str(e)[:200]
                else:
                    delivery_status = "sandbox"

            elif channel == "email":
                guest_email = conv.get("guest_email", "")
                if guest_email and resend:
                    try:
                        sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
                        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
                        hotel_name = ts.get("hotel_name", property_id)
                        resend.emails.send({
                            "from": sender, "to": [guest_email],
                            "subject": f"Message from {hotel_name}",
                            "html": f"<div style='font-family:Arial;padding:20px;'><p>{data['content']}</p><p style='color:#999;font-size:12px;'>— {hotel_name} Team</p></div>"
                        })
                        delivery_status = "delivered"
                    except Exception as e:
                        delivery_status = "failed"
                        delivery_error = str(e)[:200]
                else:
                    delivery_status = "sandbox"
            elif channel == "sms":
                phone = conv.get("guest_phone", "")
                if settings and settings.get("sms_enabled"):
                    account_sid = settings.get("sms_api_key", "")
                    auth_token = settings.get("sms_api_secret", "")
                    from_number = settings.get("sms_sender_number", "")
                    if phone and account_sid and auth_token and from_number:
                        try:
                            import httpx
                            async with httpx.AsyncClient() as client:
                                resp = await client.post(
                                    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                                    data={"To": phone, "From": from_number, "Body": data["content"]},
                                    auth=(account_sid, auth_token), timeout=10
                                )
                                if resp.status_code in (200, 201):
                                    delivery_status = "delivered"
                                else:
                                    delivery_status = "failed"
                                    delivery_error = resp.text[:200]
                        except Exception as e:
                            delivery_status = "failed"
                            delivery_error = str(e)[:200]
                    else:
                        delivery_status = "sandbox"
                else:
                    delivery_status = "sandbox"
            else:
                delivery_status = "internal"

        # Update message with delivery status
        await db.messages.update_one({"id": doc["id"]}, {"$set": {
            "delivery_status": delivery_status,
            "delivery_error": delivery_error,
        }})
        doc["delivery_status"] = delivery_status

        asyncio.create_task(fire_webhooks(db, "message.sent", {"conversation_id": data["conversation_id"], "sender": current_user.get("name", "Staff"), "channel": channel, "delivery_status": delivery_status}))
        await log_sync(db, "messaging", "outbound", delivery_status, f"Staff message via {channel} ({delivery_status}) in conv {data['conversation_id']}", data["conversation_id"])
        return doc

    @router.post("/messaging/messages/ai-suggest")
    async def ai_suggest_reply(
        conversation_id: str, guest_message: str, property_id: str = "",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI not configured")
        recent_msgs = await db.messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", -1).to_list(6)
        recent_msgs.reverse()
        conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
        prop_name = "Hotel"
        if property_id or (conv and conv.get("property_id")):
            pid = property_id or conv["property_id"]
            ts = await db.template_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
            prop_name = ts.get("hotel_name", pid)
        history_text = "\n".join([f"{'Guest' if m['sender_type'] == 'guest' else 'Staff'}: {m['content']}" for m in recent_msgs])
        system_msg = f"""You are a professional, friendly hotel concierge for {prop_name}. Generate a helpful reply to the guest's latest message.
IMPORTANT: Detect the guest's language and ALWAYS reply in the SAME language. Support 130+ languages natively.
Keep it concise (under 80 words), warm, and actionable. If the guest has a complaint, acknowledge it empathetically. Always offer to help further."""
        try:
            chat = LlmChat(api_key=llm_key, session_id=f"suggest-{conversation_id}", system_message=system_msg).with_model("openai", "gpt-5.2")
            prompt = f"Conversation history:\n{history_text}\n\nGuest's latest message: {guest_message}\n\nGenerate a professional reply:"
            reply = await chat.send_message(UserMessage(text=prompt))
            return {"suggestion": reply.strip(), "conversation_id": conversation_id}
        except Exception as e:
            logger.error(f"AI suggest error: {e}")
            return {"suggestion": "Thank you for your message. Let me look into this and get back to you shortly.", "conversation_id": conversation_id}

    @router.post("/messaging/messages/ai-sentiment")
    async def detect_sentiment(
        text: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            return {"sentiment": "neutral", "priority": "medium"}
        try:
            chat = LlmChat(api_key=llm_key, session_id=f"sentiment-{uuid.uuid4()}", system_message="You analyze hotel guest messages. Respond ONLY with JSON.").with_model("openai", "gpt-5.2")
            prompt = f"""Analyze this guest message and respond with ONLY a JSON object:
Message: "{text}"
Format: {{"sentiment": "positive|negative|neutral", "priority": "low|medium|high|urgent", "category": "inquiry|complaint|request|booking|feedback|emergency"}}"""
            reply = await chat.send_message(UserMessage(text=prompt))
            import json
            cleaned = reply.strip().strip("```json").strip("```")
            return json.loads(cleaned)
        except Exception:
            return {"sentiment": "neutral", "priority": "medium", "category": "inquiry"}

    # Quick Reply Templates
    @router.get("/messaging/quick-replies")
    async def list_quick_replies(current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        docs = await db.quick_replies.find({}, {"_id": 0}).sort("usage_count", -1).to_list(50)
        if not docs:
            from models import QUICK_REPLY_TEMPLATES, QuickReply
            for t in QUICK_REPLY_TEMPLATES:
                qr = QuickReply(**t)
                d = qr.model_dump()
                await db.quick_replies.insert_one(d)
            docs = await db.quick_replies.find({}, {"_id": 0}).sort("usage_count", -1).to_list(50)
            for d in docs: d.pop("_id", None)
        return docs

    @router.post("/messaging/quick-replies")
    async def create_quick_reply(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import QuickReply
        qr = QuickReply(**data)
        doc = qr.model_dump()
        await db.quick_replies.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/messaging/quick-replies/{reply_id}")
    async def delete_quick_reply(reply_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.quick_replies.delete_one({"id": reply_id})
        return {"status": "deleted"}

    @router.post("/messaging/quick-replies/{reply_id}/use")
    async def use_quick_reply(reply_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        await db.quick_replies.update_one({"id": reply_id}, {"$inc": {"usage_count": 1}})
        return {"status": "incremented"}

    # Channel Settings
    @router.get("/messaging/channel-settings/{property_id}")
    async def get_channel_settings(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            from models import ChannelSettings
            cs = ChannelSettings(property_id=property_id)
            d = cs.model_dump()
            await db.channel_settings.insert_one(d)
            d.pop("_id", None)
            return d
        return doc

    @router.put("/messaging/channel-settings/{property_id}")
    async def update_channel_settings(property_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.channel_settings.update_one({"property_id": property_id}, {"$set": updates}, upsert=True)
        return await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0})

    # Guest Contact Directory
    @router.get("/messaging/guests/{property_id}")
    async def guest_directory(
        property_id: str, search: str = "", filter_type: str = "all",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query = {}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        if search:
            query["$or"] = [
                {"guest_name": {"$regex": search, "$options": "i"}},
                {"guest_email": {"$regex": search, "$options": "i"}},
                {"guest_phone": {"$regex": search, "$options": "i"}},
            ]
        if filter_type == "current":
            query["check_in"] = {"$lte": today}
            query["check_out"] = {"$gte": today}
            query["status"] = {"$ne": "cancelled"}
        elif filter_type == "arriving_today":
            query["check_in"] = today
            query["status"] = {"$ne": "cancelled"}
        elif filter_type == "departing_today":
            query["check_out"] = today
            query["status"] = {"$ne": "cancelled"}
        elif filter_type == "upcoming":
            query["check_in"] = {"$gt": today}
            query["status"] = {"$ne": "cancelled"}
        elif filter_type == "past":
            query["check_out"] = {"$lt": today}

        bookings = await db.bookings.find(query, {"_id": 0}).sort("check_in", -1).to_list(200)
        seen = {}
        guests = []
        for b in bookings:
            key = b.get("guest_email", "") or b.get("guest_phone", "") or b.get("guest_name", "")
            if key and key not in seen:
                seen[key] = True
                guests.append({
                    "guest_name": b.get("guest_name", ""),
                    "guest_email": b.get("guest_email", ""),
                    "guest_phone": b.get("guest_phone", ""),
                    "check_in": b.get("check_in", ""),
                    "check_out": b.get("check_out", ""),
                    "booking_ref": b.get("booking_ref", ""),
                    "room_type_id": b.get("room_type_id", ""),
                    "status": b.get("status", ""),
                    "total_price": b.get("total_price", 0),
                    "currency": b.get("currency", "GBP"),
                })
        return guests

    @router.post("/messaging/new-conversation")
    async def create_conversation_from_guest(
        data: Dict,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        from models import Conversation, Message
        channel = data.get("channel", "internal")
        conv = Conversation(
            property_id=data.get("property_id", ""),
            guest_name=data.get("guest_name", ""),
            guest_email=data.get("guest_email", ""),
            guest_phone=data.get("guest_phone", ""),
            channel=channel,
            status="in_progress",
            priority="medium",
            assigned_to=current_user.get("id", ""),
            assigned_name=current_user.get("name", "Staff"),
            booking_ref=data.get("booking_ref", ""),
            last_message_preview=data.get("message", "")[:100],
            unread_count=0,
        )
        doc = conv.model_dump()
        await db.conversations.insert_one(doc)
        msg = Message(
            conversation_id=conv.id, sender_type="staff",
            sender_name=current_user.get("name", "Staff"),
            content=data.get("message", ""), channel=channel,
        )
        md = msg.model_dump()
        await db.messages.insert_one(md)
        doc.pop("_id", None)
        md.pop("_id", None)
        asyncio.create_task(fire_webhooks(db, "conversation.created", {"id": doc.get("id"), "guest_name": doc.get("guest_name"), "channel": channel}))
        await log_sync(db, "messaging", "internal", "success", f"New conversation with {data.get('guest_name', '')}", doc.get("id", ""))
        return {"conversation": doc, "message": md}

    # Auto-Reply Rules
    @router.get("/messaging/auto-replies/{property_id}")
    async def list_auto_replies(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        docs = await db.auto_replies.find({"property_id": property_id}, {"_id": 0}).sort("name", 1).to_list(50)
        if not docs:
            from models import AUTO_REPLY_DEFAULTS, AutoReplyRule
            for t in AUTO_REPLY_DEFAULTS:
                ar = AutoReplyRule(property_id=property_id, **t)
                d = ar.model_dump()
                await db.auto_replies.insert_one(d)
            docs = await db.auto_replies.find({"property_id": property_id}, {"_id": 0}).sort("name", 1).to_list(50)
            for d in docs: d.pop("_id", None)
        return docs

    @router.post("/messaging/auto-replies")
    async def create_auto_reply(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import AutoReplyRule
        ar = AutoReplyRule(**data)
        doc = ar.model_dump()
        await db.auto_replies.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/messaging/auto-replies/{rule_id}")
    async def update_auto_reply(rule_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.auto_replies.update_one({"id": rule_id}, {"$set": updates})
        return await db.auto_replies.find_one({"id": rule_id}, {"_id": 0})

    @router.delete("/messaging/auto-replies/{rule_id}")
    async def delete_auto_reply(rule_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.auto_replies.delete_one({"id": rule_id})
        return {"status": "deleted"}

    @router.post("/messaging/auto-replies/check")
    async def check_auto_reply(
        property_id: str, message: str,
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        rules = await db.auto_replies.find({"property_id": property_id, "enabled": True}, {"_id": 0}).to_list(50)
        msg_lower = message.lower()
        for rule in rules:
            for kw in rule.get("keywords", []):
                if kw.lower() in msg_lower:
                    await db.auto_replies.update_one({"id": rule["id"]}, {"$inc": {"match_count": 1}})
                    return {"matched": True, "rule_name": rule["name"], "response": rule["response"], "rule_id": rule["id"]}
        return {"matched": False}

    # Calendar
    @router.get("/messaging/calendar/{property_id}")
    async def messaging_calendar(
        property_id: str, month: str = "",
        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))
    ):
        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        year, m = month.split("-")
        start = f"{year}-{m}-01"
        end_m = int(m) + 1 if int(m) < 12 else 1
        end_y = int(year) if int(m) < 12 else int(year) + 1
        end = f"{end_y}-{str(end_m).zfill(2)}-01"
        bookings = await db.bookings.find({
            "property_id": property_id,
            "$or": [
                {"check_in": {"$gte": start, "$lt": end}},
                {"check_out": {"$gte": start, "$lt": end}},
                {"check_in": {"$lt": start}, "check_out": {"$gte": end}},
            ],
            "status": {"$ne": "cancelled"}
        }, {"_id": 0}).to_list(500)
        from collections import defaultdict
        day_bookings = defaultdict(list)
        for b in bookings:
            ci = b.get("check_in", "")
            co = b.get("check_out", "")
            day_bookings[ci].append({"type": "check_in", "guest": b.get("guest_name", ""), "ref": b.get("booking_ref", ""), "room": b.get("room_type_id", "")})
            day_bookings[co].append({"type": "check_out", "guest": b.get("guest_name", ""), "ref": b.get("booking_ref", ""), "room": b.get("room_type_id", "")})
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = {
            "total_bookings": len(bookings),
            "today_checkins": len([b for b in bookings if b.get("check_in") == today]),
            "today_checkouts": len([b for b in bookings if b.get("check_out") == today]),
        }
        return {"month": month, "bookings": bookings, "day_events": dict(day_bookings), "stats": stats}

    # Send via platforms
    @router.post("/messaging/send/whatsapp")
    async def send_whatsapp_message(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        property_id = data.get("property_id", "")
        settings = await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not settings or not settings.get("whatsapp_enabled"):
            return {"status": "sandbox", "message": "WhatsApp is in sandbox mode. Configure your Meta WhatsApp credentials in Settings to send real messages.", "sent": False}
        phone = data.get("phone", "").replace("+", "").replace(" ", "")
        text = data.get("message", "")
        access_token = settings.get("whatsapp_access_token", "")
        phone_id = settings.get("whatsapp_phone_number_id", "")
        if not access_token or not phone_id:
            return {"status": "sandbox", "message": "WhatsApp credentials not configured. Go to Settings > Channel Settings.", "sent": False}
        import httpx
        try:
            url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
            payload = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"})
                if resp.status_code == 200:
                    return {"status": "sent", "message": "WhatsApp message sent successfully", "sent": True}
                else:
                    return {"status": "error", "message": f"WhatsApp API error: {resp.text}", "sent": False}
        except Exception as e:
            return {"status": "error", "message": str(e), "sent": False}

    @router.post("/messaging/send/telegram")
    async def send_telegram_message(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        property_id = data.get("property_id", "")
        settings = await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not settings or not settings.get("telegram_enabled"):
            return {"status": "sandbox", "message": "Telegram is in sandbox mode. Configure your Telegram Bot token in Settings.", "sent": False}
        chat_id = data.get("chat_id", "")
        text = data.get("message", "")
        bot_token = settings.get("telegram_bot_token", "")
        if not bot_token or not chat_id:
            return {"status": "sandbox", "message": "Telegram credentials not configured. Go to Settings > Channel Settings.", "sent": False}
        import httpx
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return {"status": "sent", "message": "Telegram message sent successfully", "sent": True}
                else:
                    return {"status": "error", "message": f"Telegram API error: {resp.text}", "sent": False}
        except Exception as e:
            return {"status": "error", "message": str(e), "sent": False}

    @router.post("/messaging/send/email")
    async def send_email_message(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        to_email = data.get("email", "")
        subject = data.get("subject", "Message from Hotel")
        body = data.get("message", "")
        sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
        try:
            resend.emails.send({"from": sender, "to": [to_email], "subject": subject, "html": f"<p>{body}</p>"})
            return {"status": "sent", "message": "Email sent successfully", "sent": True}
        except Exception as e:
            return {"status": "error", "message": str(e), "sent": False}

    @router.post("/messaging/send/sms")
    async def send_sms_message(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Send SMS via Twilio"""
        property_id = data.get("property_id", "")
        settings = await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0})
        if not settings or not settings.get("sms_enabled"):
            return {"status": "sandbox", "message": "SMS is in sandbox mode. Configure Twilio credentials in Channel Settings.", "sent": False}
        phone = data.get("phone", "")
        text = data.get("message", "")
        account_sid = settings.get("sms_api_key", "")
        auth_token = settings.get("sms_api_secret", "")
        from_number = settings.get("sms_sender_number", "")
        if not account_sid or not auth_token or not from_number:
            return {"status": "sandbox", "message": "Twilio credentials not configured. Go to Channel Settings.", "sent": False}
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                    data={"To": phone, "From": from_number, "Body": text},
                    auth=(account_sid, auth_token), timeout=10
                )
                if resp.status_code in (200, 201):
                    return {"status": "sent", "message": "SMS sent successfully via Twilio", "sent": True}
                else:
                    return {"status": "error", "message": f"Twilio error: {resp.text[:200]}", "sent": False}
        except Exception as e:
            return {"status": "error", "message": str(e), "sent": False}

    # ==================== CONNECTION VERIFICATION ====================

    @router.post("/messaging/verify-connection/{channel}")
    async def verify_channel_connection(channel: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Verify that channel credentials are valid"""
        import httpx
        if channel == "whatsapp":
            phone_id = data.get("whatsapp_phone_number_id", "")
            access_token = data.get("whatsapp_access_token", "")
            if not phone_id or not access_token:
                return {"status": "error", "message": "Phone Number ID and Access Token required", "connected": False}
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"https://graph.facebook.com/v21.0/{phone_id}", headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
                    if resp.status_code == 200:
                        info = resp.json()
                        return {"status": "connected", "message": f"Connected to WhatsApp: {info.get('display_phone_number', phone_id)}", "connected": True, "phone": info.get("display_phone_number", "")}
                    else:
                        return {"status": "error", "message": f"Invalid credentials: {resp.json().get('error', {}).get('message', 'Unknown error')}", "connected": False}
            except Exception as e:
                return {"status": "error", "message": str(e)[:200], "connected": False}

        elif channel == "telegram":
            bot_token = data.get("telegram_bot_token", "")
            if not bot_token:
                return {"status": "error", "message": "Bot Token required", "connected": False}
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
                    if resp.status_code == 200:
                        bot = resp.json().get("result", {})
                        return {"status": "connected", "message": f"Connected to bot: @{bot.get('username', 'unknown')}", "connected": True, "bot_username": f"@{bot.get('username', '')}"}
                    else:
                        return {"status": "error", "message": "Invalid bot token", "connected": False}
            except Exception as e:
                return {"status": "error", "message": str(e)[:200], "connected": False}

        elif channel == "sms":
            account_sid = data.get("sms_api_key", "")
            auth_token = data.get("sms_api_secret", "")
            if not account_sid or not auth_token:
                return {"status": "error", "message": "Account SID and Auth Token required", "connected": False}
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json", auth=(account_sid, auth_token), timeout=10)
                    if resp.status_code == 200:
                        acct = resp.json()
                        return {"status": "connected", "message": f"Connected to Twilio: {acct.get('friendly_name', account_sid)}", "connected": True}
                    else:
                        return {"status": "error", "message": "Invalid Twilio credentials", "connected": False}
            except Exception as e:
                return {"status": "error", "message": str(e)[:200], "connected": False}

        return {"status": "error", "message": f"Unknown channel: {channel}", "connected": False}

    # ==================== INBOUND WEBHOOKS ====================

    @router.post("/messaging/webhook/whatsapp")
    async def whatsapp_webhook(request: Request):
        """Receive inbound WhatsApp messages from Meta"""
        body = await request.json()
        try:
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    for msg in value.get("messages", []):
                        sender_phone = msg.get("from", "")
                        text = msg.get("text", {}).get("body", "") if msg.get("type") == "text" else f"[{msg.get('type', 'media')}]"
                        contact_name = ""
                        for c in value.get("contacts", []):
                            if c.get("wa_id") == sender_phone:
                                contact_name = c.get("profile", {}).get("name", "")

                        # Find or create conversation
                        phone_formatted = f"+{sender_phone}"
                        conv = await db.conversations.find_one({"guest_phone": phone_formatted, "channel": "whatsapp"}, {"_id": 0})
                        if not conv:
                            from models import Conversation
                            new_conv = Conversation(
                                property_id=value.get("metadata", {}).get("phone_number_id", "default"),
                                guest_name=contact_name or phone_formatted,
                                guest_phone=phone_formatted,
                                channel="whatsapp", status="new", priority="medium",
                            )
                            doc = new_conv.model_dump()
                            await db.conversations.insert_one(doc)
                            doc.pop("_id", None)
                            conv = doc

                        # Save message
                        from models import Message
                        new_msg = Message(
                            conversation_id=conv["id"], channel="whatsapp",
                            sender_type="guest", content=text,
                        )
                        md = new_msg.model_dump()
                        await db.messages.insert_one(md)

                        # Update conversation
                        await db.conversations.update_one(
                            {"id": conv["id"]},
                            {"$set": {"last_message_preview": text[:100], "last_message_at": datetime.now(timezone.utc).isoformat(), "status": "new"},
                             "$inc": {"unread_count": 1}}
                        )
                        logger.info(f"Inbound WhatsApp from {phone_formatted}: {text[:50]}")
        except Exception as e:
            logger.error(f"WhatsApp webhook error: {e}")
        return {"status": "ok"}

    @router.get("/messaging/webhook/whatsapp")
    async def whatsapp_webhook_verify(request: Request):
        """WhatsApp webhook verification (Meta sends GET to verify)"""
        mode = request.query_params.get("hub.mode", "")
        token = request.query_params.get("hub.verify_token", "")
        challenge = request.query_params.get("hub.challenge", "")
        verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "myhotelbox_verify_2026")
        if mode == "subscribe" and token == verify_token:
            return int(challenge) if challenge else 200
        raise HTTPException(403, "Verification failed")

    @router.post("/messaging/webhook/telegram")
    async def telegram_webhook(request: Request):
        """Receive inbound Telegram messages"""
        body = await request.json()
        try:
            msg = body.get("message", {})
            if not msg:
                return {"status": "ok"}
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "")
            sender_name = f"{msg.get('from', {}).get('first_name', '')} {msg.get('from', {}).get('last_name', '')}".strip()

            conv = await db.conversations.find_one({"telegram_chat_id": chat_id, "channel": "telegram"}, {"_id": 0})
            if not conv:
                conv = await db.conversations.find_one({"guest_phone": chat_id, "channel": "telegram"}, {"_id": 0})
            if not conv:
                from models import Conversation
                new_conv = Conversation(
                    property_id="default", guest_name=sender_name or chat_id,
                    guest_phone=chat_id, channel="telegram", status="new", priority="medium",
                )
                doc = new_conv.model_dump()
                doc["telegram_chat_id"] = chat_id
                await db.conversations.insert_one(doc)
                doc.pop("_id", None)
                conv = doc

            from models import Message
            new_msg = Message(conversation_id=conv["id"], channel="telegram", sender_type="guest", content=text)
            md = new_msg.model_dump()
            await db.messages.insert_one(md)

            await db.conversations.update_one(
                {"id": conv["id"]},
                {"$set": {"last_message_preview": text[:100], "last_message_at": datetime.now(timezone.utc).isoformat(), "status": "new"},
                 "$inc": {"unread_count": 1}}
            )
            logger.info(f"Inbound Telegram from {chat_id}: {text[:50]}")
        except Exception as e:
            logger.error(f"Telegram webhook error: {e}")
        return {"status": "ok"}

    @router.post("/messaging/webhook/twilio")
    async def twilio_sms_webhook(request: Request):
        """Receive inbound SMS from Twilio"""
        form = await request.form()
        from_number = form.get("From", "")
        body_text = form.get("Body", "")
        try:
            conv = await db.conversations.find_one({"guest_phone": from_number, "channel": "sms"}, {"_id": 0})
            if not conv:
                from models import Conversation
                new_conv = Conversation(
                    property_id="default", guest_name=from_number,
                    guest_phone=from_number, channel="sms", status="new", priority="medium",
                )
                doc = new_conv.model_dump()
                await db.conversations.insert_one(doc)
                doc.pop("_id", None)
                conv = doc

            from models import Message
            new_msg = Message(conversation_id=conv["id"], channel="sms", sender_type="guest", content=body_text)
            md = new_msg.model_dump()
            await db.messages.insert_one(md)

            await db.conversations.update_one(
                {"id": conv["id"]},
                {"$set": {"last_message_preview": body_text[:100], "last_message_at": datetime.now(timezone.utc).isoformat(), "status": "new"},
                 "$inc": {"unread_count": 1}}
            )
            logger.info(f"Inbound SMS from {from_number}: {body_text[:50]}")
        except Exception as e:
            logger.error(f"Twilio SMS webhook error: {e}")
        return "<Response></Response>"

    # Seed Demo Conversations
    @router.post("/messaging/seed/{property_id}")
    async def seed_conversations(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.conversations.count_documents({"property_id": property_id})
        if existing > 0:
            return {"message": f"Already has {existing} conversations", "count": existing}
        from models import Conversation, Message
        demos = [
            {"guest_name": "Sarah Mitchell", "guest_email": "sarah.m@gmail.com", "guest_phone": "+447700123456", "channel": "whatsapp",
             "status": "new", "priority": "high", "sentiment": "negative", "tags": ["complaint", "room"],
             "messages": [
                {"sender_type": "guest", "content": "Hi, I just checked in to room 305 and the air conditioning isn't working. It's really hot in here."},
                {"sender_type": "guest", "content": "Also, the minibar seems to be empty. Can someone look into this please?"},
             ]},
            {"guest_name": "James Chen", "guest_email": "jchen@yahoo.com", "channel": "email",
             "status": "in_progress", "priority": "medium", "sentiment": "neutral", "tags": ["booking", "inquiry"],
             "assigned_to": "admin", "assigned_name": "Admin",
             "messages": [
                {"sender_type": "guest", "content": "Hello, I'd like to extend my stay by 2 more nights. Currently booked until Friday. Is this possible and what would be the rate?"},
                {"sender_type": "staff", "content": "Hi James, great to hear you're enjoying your stay! Let me check availability for those extra nights. I'll get back to you shortly with the best rate."},
                {"sender_type": "guest", "content": "Thank you, looking forward to hearing back."},
             ]},
            {"guest_name": "Maria Rodriguez", "guest_email": "maria.r@outlook.com", "guest_phone": "+34612345678", "channel": "whatsapp",
             "status": "new", "priority": "medium", "sentiment": "positive", "tags": ["inquiry", "restaurant"],
             "messages": [
                {"sender_type": "guest", "content": "Hola! We're celebrating our anniversary tonight. Can you recommend your best restaurant and help with a reservation?"},
             ]},
            {"guest_name": "David Thompson", "guest_email": "d.thompson@business.com", "channel": "booking.com",
             "status": "waiting", "priority": "low", "sentiment": "positive", "tags": ["pre-arrival"],
             "messages": [
                {"sender_type": "guest", "content": "Hi there, arriving next Tuesday. Is early check-in possible around 11am? Also, do you have a gym?"},
                {"sender_type": "staff", "content": "Welcome David! Early check-in at 11am is subject to availability — we'll do our best. Yes, our gym is open 24/7 on the ground floor. Would you like us to prepare anything special for your arrival?"},
             ]},
            {"guest_name": "Emily Watson", "guest_email": "emily.w@gmail.com", "guest_phone": "+447800654321", "channel": "sms",
             "status": "new", "priority": "urgent", "sentiment": "negative", "tags": ["complaint", "urgent", "cleanliness"],
             "messages": [
                {"sender_type": "guest", "content": "I found hair on the bed sheets and the bathroom wasn't properly cleaned. This is unacceptable for the price we're paying. I want to speak to a manager."},
             ]},
            {"guest_name": "Ahmed Hassan", "guest_email": "a.hassan@mail.com", "channel": "website_chat",
             "status": "resolved", "priority": "low", "sentiment": "positive", "tags": ["feedback"],
             "messages": [
                {"sender_type": "guest", "content": "Just wanted to say thank you for the amazing service during my stay. The staff were incredibly helpful and friendly. Will definitely come back!"},
                {"sender_type": "staff", "content": "Thank you so much Ahmed! It was our pleasure hosting you. We truly appreciate your kind words and look forward to welcoming you again. Safe travels!"},
             ]},
        ]
        count = 0
        for d in demos:
            msgs_data = d.pop("messages")
            conv = Conversation(property_id=property_id, **{k: v for k, v in d.items()})
            conv.last_message_preview = msgs_data[-1]["content"][:100]
            conv.unread_count = sum(1 for m in msgs_data if m["sender_type"] == "guest")
            doc = conv.model_dump()
            await db.conversations.insert_one(doc)
            for m in msgs_data:
                msg = Message(conversation_id=conv.id, channel=d.get("channel", "internal"), **m)
                md = msg.model_dump()
                await db.messages.insert_one(md)
            count += 1
        return {"message": f"Seeded {count} demo conversations", "count": count}

    return router
