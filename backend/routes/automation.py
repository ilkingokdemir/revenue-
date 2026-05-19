"""
Automation Engine Routes
Extracted from server.py for maintainability
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import os
import asyncio
import logging

from routes.helpers import fire_webhooks, log_sync

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
        """Manually trigger automation check for a property.

        Cloudbeds parity flags (read off rule doc, default-safe):
          * multi_reservation_messaging — send per booking even when guest has many
          * enable_missed_messages — fire for bookings created AFTER schedule passed
          * send_per_room — fan-out to each room in a multi-room reservation
          * primary_guest_only — skip secondary guests
          * schedule_days (list[int 0-6, Mon=0]) — restrict run by weekday
          * schedule_time ("HH:MM" UTC) — only run when within ±15 min of this time
          * skip_guests (list[str booking_ref]) — manual skip list
          * auto_archive — silently archive the log row instead of surfacing in inbox
        """
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
            # Schedule day-of-week gate
            sched_days = rule.get("schedule_days") or []
            if sched_days and now.weekday() not in sched_days:
                results.append({"rule": rule["name"], "skipped_reason": "weekday not in schedule_days"})
                continue
            # Schedule time-of-day gate (±15min window)
            sched_time = (rule.get("schedule_time") or "").strip()
            if sched_time and ":" in sched_time:
                try:
                    sh, sm = [int(x) for x in sched_time.split(":")]
                    target_min = sh * 60 + sm
                    now_min = now.hour * 60 + now.minute
                    if abs(now_min - target_min) > 15:
                        results.append({"rule": rule["name"], "skipped_reason": f"outside time window {sched_time}"})
                        continue
                except Exception:
                    pass

            trigger = rule["trigger"]
            timing = rule.get("timing_hours", 0)
            multi_res = bool(rule.get("multi_reservation_messaging", False))
            missed_msgs = bool(rule.get("enable_missed_messages", False))
            per_room = bool(rule.get("send_per_room", False))
            primary_only = bool(rule.get("primary_guest_only", True))
            skip_list = set(rule.get("skip_guests") or [])
            auto_archive = bool(rule.get("auto_archive", False))
            sent_for_rule = 0

            bookings = []
            if trigger == "pre_arrival":
                target_date = tomorrow if timing == -24 else today
                q = {"property_id": property_id, "check_in": target_date, "status": {"$ne": "cancelled"}}
                bookings = await db.bookings.find(q, {"_id": 0}).to_list(200)
                if missed_msgs:
                    # Bookings created in last 24h whose check_in <= target_date and that have no log yet
                    yest = (now - timedelta(hours=24)).isoformat()
                    extra = await db.bookings.find({
                        "property_id": property_id,
                        "check_in": {"$lte": target_date},
                        "status": {"$ne": "cancelled"},
                        "created_at": {"$gte": yest},
                    }, {"_id": 0}).to_list(200)
                    seen = {b.get("booking_ref") for b in bookings}
                    bookings += [b for b in extra if b.get("booking_ref") not in seen]
            elif trigger == "day_of_arrival":
                bookings = await db.bookings.find({"property_id": property_id, "check_in": today, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(200)
            elif trigger == "during_stay":
                bookings = await db.bookings.find({"property_id": property_id, "check_in": {"$lte": today}, "check_out": {"$gt": today}, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(200)
            elif trigger == "post_checkout":
                bookings = await db.bookings.find({"property_id": property_id, "check_out": today, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(200)
            elif trigger == "cart_abandonment":
                carts = await db.cart_abandonment.find({"property_id": property_id, "recovered": {"$ne": True}}, {"_id": 0}).to_list(50)
                bookings = [{"guest_name": c.get("guest_name", c.get("email", "Guest")), "guest_email": c.get("email", ""), "booking_ref": "", "check_in": "", "check_out": ""} for c in carts]

            # Multi-reservation: if NOT enabled, dedupe by guest_email (one per guest)
            if not multi_res:
                seen_emails = set()
                deduped = []
                for b in bookings:
                    em = (b.get("guest_email") or "").lower()
                    if em and em in seen_emails:
                        continue
                    seen_emails.add(em)
                    deduped.append(b)
                bookings = deduped

            for booking in bookings:
                booking_ref = booking.get("booking_ref", "")
                if booking_ref in skip_list:
                    continue
                guest_email = booking.get("guest_email", "")
                guest_phone = booking.get("guest_phone", "")

                already_sent = await db.automation_logs.find_one({
                    "rule_id": rule["id"], "booking_ref": booking_ref, "guest_email": guest_email
                })
                if already_sent:
                    continue

                # Per-room fan-out — create one log per room_assignment when enabled
                rooms_to_msg = [None]
                if per_room:
                    room_assigns = booking.get("room_assignments") or booking.get("rooms") or []
                    if room_assigns:
                        rooms_to_msg = room_assigns

                # Primary-guest only filter — bookings have primary_guest=True/False
                if primary_only and booking.get("is_secondary_guest"):
                    continue

                for room_ctx in rooms_to_msg:
                    book_for_template = {**booking}
                    if room_ctx and isinstance(room_ctx, dict):
                        book_for_template["room_type_id"] = room_ctx.get("room_type_id", booking.get("room_type_id"))
                        book_for_template["room_number"] = room_ctx.get("room_number", "")

                    message = fill_template(rule["message_template"], book_for_template, property_id)
                    subject = fill_template(rule.get("subject", ""), book_for_template, property_id) if rule.get("subject") else ""
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
                    if auto_archive:
                        ld["archived"] = True
                    await db.automation_logs.insert_one(ld)
                    sent_for_rule += 1
                    total_sent += 1

            if sent_for_rule > 0:
                await db.automation_rules.update_one({"id": rule["id"]}, {"$inc": {"total_sent": sent_for_rule}})

            results.append({"rule": rule["name"], "trigger": trigger, "channel": rule["channel"], "matched": len(bookings), "sent": sent_for_rule})

        if total_sent > 0:
            asyncio.create_task(fire_webhooks(db, "automation.triggered", {"property_id": property_id, "sent": total_sent, "rules_matched": len(results)}))
            await log_sync(db, "automation", "outbound", "success", f"Automation run: {total_sent} messages sent across {len(results)} rules", property_id)

        failed_count = sum(1 for r in results if r.get("sent", 0) == 0 and r.get("matched", 0) > 0)
        if failed_count > 0:
            asyncio.create_task(fire_webhooks(db, "automation.failed", {"property_id": property_id, "failed_rules": failed_count}))

        return {"message": f"Automation complete. {total_sent} messages sent.", "sent": total_sent, "results": results}

    @router.post("/automation/rules/{rule_id}/duplicate")
    async def duplicate_automation_rule(rule_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Cloudbeds parity: 'Replicate' rule. Copies an existing rule with a new id and "Copy of" prefix."""
        import uuid as _uuid
        src = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
        if not src:
            raise HTTPException(status_code=404, detail="Rule not found")
        clone = {**src}
        clone["id"] = str(_uuid.uuid4())
        clone["name"] = f"Copy of {clone.get('name','Rule')}"
        clone["total_sent"] = 0
        clone["enabled"] = False  # Don't fire by accident
        clone["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.automation_rules.insert_one(clone)
        clone.pop("_id", None)
        return clone

    @router.post("/automation/rules/{rule_id}/skip-guest")
    async def skip_guest_for_rule(rule_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Add a booking_ref to a rule's skip_guests list — they won't receive this automation."""
        booking_ref = (data.get("booking_ref") or "").strip()
        if not booking_ref:
            raise HTTPException(400, "booking_ref required")
        await db.automation_rules.update_one(
            {"id": rule_id},
            {"$addToSet": {"skip_guests": booking_ref}},
        )
        return {"status": "skipped", "booking_ref": booking_ref}

    @router.get("/automation/rules/{rule_id}/history")
    async def rule_history(rule_id: str, limit: int = 100,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Per-rule activity log."""
        rows = await db.automation_logs.find(
            {"rule_id": rule_id}, {"_id": 0}
        ).sort("created_at", -1).limit(int(limit)).to_list(int(limit))
        return {"rule_id": rule_id, "count": len(rows), "items": rows}

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
