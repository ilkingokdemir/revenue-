"""
Automation Engine Routes
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import os
import logging

logger = logging.getLogger(__name__)


def fill_template(template: str, booking: dict, property_id: str = "") -> str:
    """Replace template variables with actual values"""
    base_url = os.environ.get("FRONTEND_URL", os.environ.get("BACKEND_URL", ""))
    replacements = {
        "{guest_name}": booking.get("guest_name", "Guest"),
        "{hotel_name}": property_id.replace("-", " ").title() if property_id else "Hotel",
        "{hotel_address}": "",
        "{booking_ref}": booking.get("booking_ref", ""),
        "{check_in}": booking.get("check_in", ""),
        "{check_out}": booking.get("check_out", ""),
        "{room_type}": booking.get("room_type_id", "").replace("-", " ").title(),
        "{total_price}": f"\u00a3{booking.get('total_price', 0)}",
        "{checkin_link}": f"{base_url}/checkin?ref={booking.get('booking_ref', '')}",
        "{review_link}": f"{base_url}/review?property={property_id}&ref={booking.get('booking_ref', '')}",
        "{portal_link}": f"{base_url}/guest-portal",
        "{cart_link}": f"{base_url}/book?property={property_id}",
    }
    result = template
    for key, val in replacements.items():
        result = result.replace(key, str(val))
    return result


def create_automation_router(db, require_roles, resend):
    """Factory function that creates automation routes with injected dependencies"""
    router = APIRouter()

    @router.get("/automation/rules/{property_id}")
    async def list_automation_rules(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.automation_rules.find({"property_id": property_id}, {"_id": 0}).sort("trigger", 1).to_list(50)
        if not docs:
            from models import AUTOMATION_DEFAULTS, AutomationRule
            for t in AUTOMATION_DEFAULTS:
                ar = AutomationRule(property_id=property_id, **t)
                d = ar.model_dump()
                await db.automation_rules.insert_one(d)
            docs = await db.automation_rules.find({"property_id": property_id}, {"_id": 0}).sort("trigger", 1).to_list(50)
            for d in docs:
                d.pop("_id", None)
        return docs

    @router.post("/automation/rules")
    async def create_automation_rule(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import AutomationRule
        ar = AutomationRule(**data)
        doc = ar.model_dump()
        await db.automation_rules.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/automation/rules/{rule_id}")
    async def update_automation_rule(rule_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.automation_rules.update_one({"id": rule_id}, {"$set": updates})
        doc = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
        return doc

    @router.delete("/automation/rules/{rule_id}")
    async def delete_automation_rule(rule_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.automation_rules.delete_one({"id": rule_id})
        return {"status": "deleted"}

    @router.post("/automation/rules/{rule_id}/toggle")
    async def toggle_automation_rule(rule_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        rule = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        new_state = not rule.get("enabled", True)
        await db.automation_rules.update_one({"id": rule_id}, {"$set": {"enabled": new_state}})
        return {"enabled": new_state}

    @router.post("/automation/run/{property_id}")
    async def run_automation(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Manually trigger automation check for a property"""
        from models import AutomationLog
        rules = await db.automation_rules.find({"property_id": property_id, "enabled": True}, {"_id": 0}).to_list(50)
        if not rules:
            return {"message": "No active automation rules", "sent": 0, "results": []}

        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        results = []
        total_sent = 0

        for rule in rules:
            trigger = rule["trigger"]
            timing = rule.get("timing_hours", 0)
            sent_for_rule = 0

            bookings = []
            if trigger == "pre_arrival":
                target_date = tomorrow if timing == -24 else today
                bookings = await db.bookings.find({"property_id": property_id, "check_in": target_date, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(200)
            elif trigger == "day_of_arrival":
                bookings = await db.bookings.find({"property_id": property_id, "check_in": today, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(200)
            elif trigger == "during_stay":
                bookings = await db.bookings.find({"property_id": property_id, "check_in": {"$lte": today}, "check_out": {"$gt": today}, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(200)
            elif trigger == "post_checkout":
                bookings = await db.bookings.find({"property_id": property_id, "check_out": today, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(200)
            elif trigger == "cart_abandonment":
                carts = await db.cart_abandonment.find({"property_id": property_id, "recovered": {"$ne": True}}, {"_id": 0}).to_list(50)
                bookings = [{"guest_name": c.get("guest_name", c.get("email", "Guest")), "guest_email": c.get("email", ""), "booking_ref": "", "check_in": "", "check_out": ""} for c in carts]

            for booking in bookings:
                guest_email = booking.get("guest_email", "")
                guest_phone = booking.get("guest_phone", "")
                booking_ref = booking.get("booking_ref", "")

                already_sent = await db.automation_logs.find_one({
                    "rule_id": rule["id"], "booking_ref": booking_ref, "guest_email": guest_email
                })
                if already_sent:
                    continue

                message = fill_template(rule["message_template"], booking, property_id)
                subject = fill_template(rule.get("subject", ""), booking, property_id) if rule.get("subject") else ""
                channel = rule["channel"]
                status = "sent"

                try:
                    if channel == "email" and guest_email:
                        sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
                        resend.emails.send({"from": sender, "to": [guest_email], "subject": subject or "Message from Hotel", "html": f"<div style='font-family:sans-serif;max-width:600px;margin:auto;padding:20px;'><p style='white-space:pre-line;'>{message}</p></div>"})
                    elif channel in ["whatsapp", "sms", "telegram"]:
                        settings = await db.channel_settings.find_one({"property_id": property_id}, {"_id": 0})
                        if not settings or not settings.get(f"{channel}_enabled", False):
                            status = "queued"
                    elif channel == "internal":
                        pass
                except Exception as e:
                    logger.error(f"Automation send error: {e}")
                    status = "failed"

                log = AutomationLog(
                    rule_id=rule["id"], rule_name=rule["name"], property_id=property_id,
                    guest_name=booking.get("guest_name", ""), guest_email=guest_email,
                    guest_phone=guest_phone, booking_ref=booking_ref,
                    channel=channel, message=message[:500], status=status,
                )
                ld = log.model_dump()
                await db.automation_logs.insert_one(ld)
                sent_for_rule += 1
                total_sent += 1

            if sent_for_rule > 0:
                await db.automation_rules.update_one({"id": rule["id"]}, {"$inc": {"total_sent": sent_for_rule}})

            results.append({"rule": rule["name"], "trigger": trigger, "channel": rule["channel"], "matched": len(bookings), "sent": sent_for_rule})

        return {"message": f"Automation complete. {total_sent} messages sent.", "sent": total_sent, "results": results}

    @router.get("/automation/logs/{property_id}")
    async def automation_logs(property_id: str, limit: int = 50, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.automation_logs.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(limit)
        return docs

    @router.get("/automation/stats/{property_id}")
    async def automation_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        total_rules = await db.automation_rules.count_documents({"property_id": property_id})
        active_rules = await db.automation_rules.count_documents({"property_id": property_id, "enabled": True})
        total_sent = await db.automation_logs.count_documents({"property_id": property_id})
        sent_today = await db.automation_logs.count_documents({
            "property_id": property_id,
            "created_at": {"$gte": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
        })
        failed = await db.automation_logs.count_documents({"property_id": property_id, "status": "failed"})
        queued = await db.automation_logs.count_documents({"property_id": property_id, "status": "queued"})
        pipeline = [
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": "$channel", "count": {"$sum": 1}}}
        ]
        by_channel = {}
        async for doc in db.automation_logs.aggregate(pipeline):
            by_channel[doc["_id"]] = doc["count"]
        pipeline2 = [
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": "$rule_name", "count": {"$sum": 1}}}
        ]
        by_rule = {}
        async for doc in db.automation_logs.aggregate(pipeline2):
            by_rule[doc["_id"]] = doc["count"]
        return {
            "total_rules": total_rules, "active_rules": active_rules,
            "total_sent": total_sent, "sent_today": sent_today,
            "failed": failed, "queued": queued,
            "by_channel": by_channel, "by_rule": by_rule
        }

    @router.post("/automation/preview")
    async def preview_automation(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Preview a filled automation template"""
        template = data.get("message_template", "")
        property_id = data.get("property_id", "")
        sample_booking = {
            "guest_name": "John Smith",
            "guest_email": "john@example.com",
            "guest_phone": "+447700123456",
            "booking_ref": "BK-2026-0412",
            "check_in": "2026-04-13",
            "check_out": "2026-04-16",
            "room_type_id": "deluxe-double",
            "total_price": 450,
        }
        filled = fill_template(template, sample_booking, property_id)
        return {"preview": filled}

    return router
