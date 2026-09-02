"""
AI Upsell Engine — Automatically suggests room upgrades, early check-in,
late checkout, and add-ons based on guest profile and availability.
"""
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import os
import random
import logging

logger = logging.getLogger(__name__)


def create_upsell_router(db, require_roles, LlmChat, UserMessage):
    router = APIRouter()

    @router.get("/revenue/upsell/{booking_id}")
    async def get_upsell_suggestions(booking_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Generate upsell suggestions for a specific booking."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            return {"error": "Booking not found"}

        pid = booking.get("property_id", "")
        ci = booking.get("check_in", "")
        co = booking.get("check_out", "")
        current_rate = float(booking.get("rate_per_night", 0) or 0)
        current_rt_id = booking.get("room_type_id", "")
        nights = int(booking.get("nights", 1) or 1)

        # Get all room types for upgrade options
        room_types = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
        rt_map = {rt.get("id", ""): rt for rt in room_types}
        current_rt = rt_map.get(current_rt_id, {})

        suggestions = []

        # 1. ROOM UPGRADE — Find higher-tier rooms with availability
        for rt in room_types:
            rt_id = rt.get("id", "")
            if rt_id == current_rt_id:
                continue
            rt_rate = float(rt.get("base_rate") or current_rate * 1.3)
            if rt_rate <= current_rate:
                continue

            # Check availability
            rt_rooms = await db.rooms.find({"property_id": pid, "room_type_id": rt_id}, {"_id": 0}).to_list(10)
            available = 0
            for room in rt_rooms:
                conflict = await db.bookings.find_one({
                    "room_id": room.get("id"), "status": {"$nin": ["cancelled"]},
                    "check_in": {"$lt": co}, "check_out": {"$gt": ci}
                })
                if not conflict:
                    available += 1

            if available > 0:
                upgrade_cost = round((rt_rate - current_rate) * nights, 2)
                suggestions.append({
                    "id": str(uuid.uuid4()),
                    "type": "room_upgrade",
                    "title": f"Upgrade to {rt.get('name', 'Premium Room')}",
                    "description": f"Move from {current_rt.get('name', 'Current Room')} to {rt.get('name', 'Premium Room')} — {available} available",
                    "price": upgrade_cost,
                    "price_label": f"+£{upgrade_cost:.0f} for {nights} night{'s' if nights > 1 else ''}",
                    "per_night": round(rt_rate - current_rate, 2),
                    "availability": available,
                    "priority": "high" if upgrade_cost < 50 else "medium",
                    "target_room_type": rt_id,
                })

        # 2. EARLY CHECK-IN
        suggestions.append({
            "id": str(uuid.uuid4()),
            "type": "early_checkin",
            "title": "Early Check-In (from 12pm)",
            "description": "Arrive 2 hours early and go straight to your room",
            "price": round(current_rate * 0.25, 2),
            "price_label": f"£{current_rate * 0.25:.0f}",
            "priority": "medium",
        })

        # 3. LATE CHECKOUT
        suggestions.append({
            "id": str(uuid.uuid4()),
            "type": "late_checkout",
            "title": "Late Check-Out (until 2pm)",
            "description": "Enjoy an extra 2 hours before departure",
            "price": round(current_rate * 0.3, 2),
            "price_label": f"£{current_rate * 0.3:.0f}",
            "priority": "medium",
        })

        # 4. ADD-ONS
        addons = [
            {"name": "Breakfast Package", "desc": "Full English breakfast for all guests", "pct": 0.15, "per": "night"},
            {"name": "Airport Transfer", "desc": "Private car to/from airport", "flat": 45, "per": "trip"},
            {"name": "Welcome Hamper", "desc": "Champagne, chocolates & local treats", "flat": 35, "per": "stay"},
            {"name": "Parking Space", "desc": "Secure on-site parking", "flat": 12, "per": "night"},
            {"name": "Spa Access", "desc": "Full-day access to spa facilities", "flat": 25, "per": "night"},
        ]
        for addon in addons:
            price = addon.get("flat", round(current_rate * addon.get("pct", 0.1), 2))
            total = price * nights if addon["per"] == "night" else price
            suggestions.append({
                "id": str(uuid.uuid4()),
                "type": "addon",
                "title": addon["name"],
                "description": addon["desc"],
                "price": round(total, 2),
                "price_label": f"£{price:.0f}/{addon['per']}" + (f" (£{total:.0f} total)" if addon["per"] == "night" and nights > 1 else ""),
                "priority": "low",
            })

        # Calculate total upsell potential
        total_potential = round(sum(s["price"] for s in suggestions), 2)

        return {
            "booking_id": booking_id,
            "guest_name": booking.get("guest_name", ""),
            "current_room": current_rt.get("name", ""),
            "current_rate": current_rate,
            "nights": nights,
            "suggestions": suggestions,
            "total_potential": total_potential,
        }

    async def _apply_upsell(booking_id: str, suggestion_type: str, price: float, description: str, actor: str,
                            target_room_type: str = "", current_room_type: str = "", source: str = "staff") -> dict:
        """Shared: folio charge + optional room upgrade + upsell_log (used by staff accept and guest e-mail claim)."""
        now = datetime.now(timezone.utc).isoformat()
        await db.folio_items.insert_one({
            "id": str(uuid.uuid4()), "booking_id": booking_id, "type": "charge", "category": "upsell",
            "description": description or f"Upsell: {suggestion_type}", "quantity": 1, "unit_price": price,
            "amount": price, "currency": "GBP", "created_at": now, "created_by": actor or "AI Upsell"})
        if suggestion_type == "room_upgrade" and target_room_type:
            await db.bookings.update_one({"id": booking_id}, {"$set": {
                "room_type_id": target_room_type, "upgraded": True, "upgrade_from": current_room_type}})
        await db.upsell_log.insert_one({
            "id": str(uuid.uuid4()), "booking_id": booking_id, "type": suggestion_type, "revenue": price,
            "accepted_at": now, "accepted_by": actor, "source": source})
        return {"status": "accepted", "type": suggestion_type, "revenue_added": price}

    router.apply_upsell = _apply_upsell

    @router.post("/revenue/upsell/{booking_id}/accept")
    async def accept_upsell(booking_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Accept an upsell — add charge to folio and update booking if needed."""
        return await _apply_upsell(booking_id, data.get("type", ""), float(data.get("price", 0)), data.get("description", ""),
                                   current_user.get("name", ""), data.get("target_room_type", ""), data.get("current_room_type", ""))

    CLAIM_T = {
        "en": ("Added to your booking", "{label} has been added to your reservation {ref}. You'll pay {amount} at the property. See you soon!", "Already added", "This link has expired or is invalid.", "Link not valid"),
        "tr": ("Rezervasyonunuza eklendi", "{label} rezervasyonunuza ({ref}) eklendi. {amount} tutarını otelde ödeyeceksiniz. Görüşmek üzere!", "Zaten eklenmiş", "Bu bağlantının süresi dolmuş ya da geçersiz.", "Bağlantı geçersiz"),
        "de": ("Zu Ihrer Buchung hinzugefügt", "{label} wurde Ihrer Reservierung {ref} hinzugefügt. Sie zahlen {amount} vor Ort. Bis bald!", "Bereits hinzugefügt", "Dieser Link ist abgelaufen oder ungültig.", "Link ungültig"),
    }

    def _claim_page(title: str, body: str, ok: bool) -> HTMLResponse:
        color = "#2F855A" if ok else "#C53030"
        return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
        <body style="font-family:Arial,sans-serif;background:#F5F7FA;margin:0;padding:40px 16px"><div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.06)">
        <div style="font-size:40px">{'✅' if ok else '⚠️'}</div><h2 style="color:{color};margin:12px 0">{title}</h2><p style="color:#444;font-size:15px">{body}</p></div></body></html>""")

    @router.get("/revenue/upsell/claim/{token}", response_class=HTMLResponse)
    async def claim_upsell(token: str):
        """Public one-click link from the pre-arrival e-mail: adds the offer to the booking (pay at property)."""
        tk = await db.upsell_claim_tokens.find_one({"token": token}, {"_id": 0})
        lang = (tk or {}).get("lang", "en")
        t = CLAIM_T.get(lang, CLAIM_T["en"])
        if not tk or tk.get("expires_at", "") < datetime.now(timezone.utc).isoformat():
            return _claim_page(t[4], t[3], False)
        if tk.get("used_at"):
            return _claim_page(t[2], t[1].format(label=tk["label"], ref=tk.get("booking_ref", ""), amount=tk["amount_label"]), True)
        await _apply_upsell(tk["booking_id"], "addon", float(tk["amount"]), tk["label"], tk.get("guest_email", "guest"), source="pre_arrival_email")
        await db.upsell_claim_tokens.update_one({"token": token}, {"$set": {"used_at": datetime.now(timezone.utc).isoformat()}})
        bk = await db.bookings.find_one({"id": tk["booking_id"]}, {"_id": 0, "property_id": 1, "guest_name": 1, "check_in": 1, "room_type": 1}) or {}
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "category": "upsell", "priority": "high", "title": f"Misafir ekstra ekledi: {tk['label']}",
            "message": (f"{bk.get('guest_name') or tk.get('guest_email', '')} ({tk.get('booking_ref', '')}, giriş {bk.get('check_in', '')}, "
                        f"{bk.get('room_type', '')}) e-postadan '{tk['label']}' ekledi — {tk['amount_label']} otelde tahsil edilecek, folyoya işlendi."),
            "property_id": bk.get("property_id", ""), "booking_id": tk["booking_id"], "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()})
        return _claim_page(t[0], t[1].format(label=tk["label"], ref=tk.get("booking_ref", ""), amount=tk["amount_label"]), True)

    @router.get("/revenue/upsell/stats/{property_id}")
    async def upsell_stats(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Upsell performance stats."""
        logs = await db.upsell_log.find({}, {"_id": 0}).to_list(500)
        total_revenue = round(sum(float(log.get("revenue", 0)) for log in logs), 2)
        by_type = {}
        for log in logs:
            t = log.get("type", "other")
            by_type.setdefault(t, {"count": 0, "revenue": 0})
            by_type[t]["count"] += 1
            by_type[t]["revenue"] += float(log.get("revenue", 0))

        return {
            "total_upsells": len(logs),
            "total_revenue": total_revenue,
            "by_type": [{
                "type": k, "count": v["count"], "revenue": round(v["revenue"], 2)
            } for k, v in sorted(by_type.items(), key=lambda x: -x[1]["revenue"])],
        }

    return router
