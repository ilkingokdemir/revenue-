"""
Advanced POS Features — QR Ordering, Receipts, Happy Hour, Guest Preferences, Loyalty
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import os
import logging

from routes.helpers import log_sync

logger = logging.getLogger(__name__)


def create_pos_advanced_router(db, require_roles, resend):
    router = APIRouter()

    # ==================== QR CODE SELF-ORDERING (PUBLIC) ====================

    @router.get("/pos/public/menu/{property_id}/{outlet_id}")
    async def public_menu(property_id: str, outlet_id: str, table: str = ""):
        """Public endpoint — no auth. Returns menu for guest self-ordering."""
        outlet = await db.pos_outlets.find_one({"id": outlet_id}, {"_id": 0})
        if not outlet:
            raise HTTPException(404, "Outlet not found")

        items = await db.pos_menu_items.find(
            {"property_id": property_id, "available": True}, {"_id": 0}
        ).sort("category", 1).to_list(500)

        # Apply happy hour pricing
        now = datetime.now(timezone.utc)
        hour = now.hour
        happy = await db.pos_happy_hours.find_one(
            {"property_id": property_id, "outlet_id": outlet_id, "enabled": True,
             "start_hour": {"$lte": hour}, "end_hour": {"$gt": hour}},
            {"_id": 0}
        )
        if happy:
            discount_pct = happy.get("discount_pct", 0)
            categories = happy.get("categories", [])
            for item in items:
                if not categories or item["category"] in categories:
                    item["original_price"] = item["price"]
                    item["price"] = round(item["price"] * (1 - discount_pct / 100), 2)
                    item["happy_hour"] = True

        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}

        return {
            "hotel_name": ts.get("hotel_name", property_id),
            "outlet_name": outlet.get("name", ""),
            "outlet_type": outlet.get("type", ""),
            "table_number": table,
            "menu_items": items,
            "categories": sorted(set(i["category"] for i in items)),
            "happy_hour_active": happy is not None,
            "happy_hour_name": happy.get("name", "") if happy else "",
        }

    @router.post("/pos/public/order")
    async def public_place_order(data: Dict):
        """Public endpoint — guest self-order via QR code. No auth."""
        property_id = data.get("property_id")
        outlet_id = data.get("outlet_id")
        items = data.get("items", [])
        if not items:
            raise HTTPException(400, "No items in order")

        subtotal = 0
        vat_total = 0
        cost_total = 0
        for item in items:
            qty = item.get("quantity", 1)
            price = item.get("price", 0)
            vat_rate = item.get("vat_rate", 20)
            line_total = round(qty * price, 2)
            line_vat = round(line_total * vat_rate / 100, 2)
            item["line_total"] = line_total
            item["line_vat"] = line_vat
            subtotal += line_total
            vat_total += line_vat
            cost_total += round(qty * item.get("cost", 0), 2)

        count = await db.pos_orders.count_documents({"property_id": property_id})
        order = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "outlet_id": outlet_id,
            "outlet_name": data.get("outlet_name", ""),
            "order_number": f"QR-{count + 1:05d}",
            "order_type": "qr_order",
            "table_number": data.get("table_number", ""),
            "covers": data.get("covers", 1),
            "guest_name": data.get("guest_name", ""),
            "room_number": data.get("room_number", ""),
            "items": items,
            "subtotal": round(subtotal, 2),
            "vat_amount": round(vat_total, 2),
            "total": round(subtotal + vat_total, 2),
            "cost_total": round(cost_total, 2),
            "payment_method": "pending",
            "payment_status": "pending",
            "kitchen_status": "new",
            "notes": data.get("notes", ""),
            "dietary_notes": data.get("dietary_notes", ""),
            "guest_phone": data.get("guest_phone", ""),
            "guest_email": data.get("guest_email", ""),
            "server_name": "Self-Order (QR)",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.pos_orders.insert_one(order)
        order.pop("_id", None)

        # Deduct stock
        for item in items:
            if item.get("stock_product_id"):
                await db.stock_products.update_one(
                    {"id": item["stock_product_id"]},
                    {"$inc": {"quantity": -item.get("quantity", 1)}}
                )

        return {"order_number": order["order_number"], "total": order["total"], "status": "received"}

    @router.get("/pos/qr-code/{property_id}/{outlet_id}")
    async def get_qr_info(property_id: str, outlet_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get QR code URL for an outlet"""
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
        url = f"{base_url}/qr-order/{property_id}/{outlet_id}"
        return {"url": url, "property_id": property_id, "outlet_id": outlet_id}

    # ==================== DIGITAL RECEIPTS ====================

    @router.post("/pos/orders/{order_id}/receipt")
    async def send_digital_receipt(order_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        order = await db.pos_orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Order not found")

        email = data.get("email", order.get("guest_email", ""))
        if not email:
            raise HTTPException(400, "No email address")

        ts = await db.template_settings.find_one({"property_id": order["property_id"]}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name", order.get("property_id", "Hotel"))

        items_html = "".join(
            f'<tr><td style="padding:6px 0;border-bottom:1px solid #f1f5f9;">{item.get("name","")}</td>'
            f'<td style="padding:6px 0;border-bottom:1px solid #f1f5f9;text-align:center;">{item.get("quantity",1)}</td>'
            f'<td style="padding:6px 0;border-bottom:1px solid #f1f5f9;text-align:right;">£{item.get("line_total",0):.2f}</td></tr>'
            for item in order.get("items", [])
        )

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:30px;background:#fff;">
            <div style="text-align:center;margin-bottom:20px;">
                <h2 style="color:#1a1a1a;margin:0;">{hotel_name}</h2>
                <p style="color:#64748b;font-size:13px;margin:4px 0;">{order.get('outlet_name','')}</p>
                <p style="color:#94a3b8;font-size:11px;">Receipt #{order.get('order_number','')}</p>
            </div>
            <table style="width:100%;font-size:13px;color:#334155;">
                <tr style="color:#94a3b8;font-size:11px;"><th style="text-align:left;padding:4px 0;">Item</th><th style="text-align:center;">Qty</th><th style="text-align:right;">Total</th></tr>
                {items_html}
            </table>
            <div style="margin-top:16px;padding-top:12px;border-top:2px solid #e2e8f0;">
                <div style="display:flex;justify-content:space-between;font-size:13px;color:#64748b;"><span>Subtotal</span><span>£{order.get('subtotal',0):.2f}</span></div>
                <div style="display:flex;justify-content:space-between;font-size:13px;color:#64748b;margin-top:4px;"><span>VAT (20%)</span><span>£{order.get('vat_amount',0):.2f}</span></div>
                {"<div style='display:flex;justify-content:space-between;font-size:13px;color:#64748b;margin-top:4px;'><span>Tip</span><span>£" + str(order.get('tip',0)) + "</span></div>" if order.get('tip') else ""}
                <div style="display:flex;justify-content:space-between;font-size:16px;font-weight:bold;color:#1a1a1a;margin-top:8px;padding-top:8px;border-top:1px solid #e2e8f0;"><span>Total</span><span>£{order.get('total_with_tip', order.get('total',0)):.2f}</span></div>
            </div>
            <div style="margin-top:16px;font-size:11px;color:#94a3b8;text-align:center;">
                <p>Paid via {order.get('payment_method','card').replace('_',' ')} · {order.get('paid_at','')[:10] if order.get('paid_at') else ''}</p>
                <p>Table {order.get('table_number','—')} · {order.get('covers',1)} covers · Server: {order.get('server_name','')}</p>
                <p style="margin-top:12px;">Thank you for dining with us!</p>
            </div>
        </div>"""

        try:
            sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
            resend.emails.send({"from": sender, "to": [email], "subject": f"Your receipt from {hotel_name} — {order['order_number']}", "html": html})
            await db.pos_orders.update_one({"id": order_id}, {"$set": {"receipt_sent": True, "receipt_email": email}})
            return {"status": "sent", "email": email}
        except Exception as e:
            logger.error(f"Receipt email error: {e}")
            raise HTTPException(500, "Failed to send receipt")

    # ==================== HAPPY HOUR / DYNAMIC PRICING ====================

    @router.get("/pos/happy-hours/{property_id}")
    async def list_happy_hours(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.pos_happy_hours.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if not docs:
            defaults = [
                {"id": str(uuid.uuid4()), "property_id": property_id, "outlet_id": "", "name": "Happy Hour", "start_hour": 16, "end_hour": 19, "discount_pct": 25, "categories": ["Beer", "Wine", "Cocktails"], "enabled": True, "days": ["mon", "tue", "wed", "thu", "fri"], "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "property_id": property_id, "outlet_id": "", "name": "Early Bird Breakfast", "start_hour": 6, "end_hour": 8, "discount_pct": 15, "categories": ["Room Service"], "enabled": False, "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "created_at": datetime.now(timezone.utc).isoformat()},
            ]
            for d in defaults:
                await db.pos_happy_hours.insert_one(d)
            docs = await db.pos_happy_hours.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        return docs

    @router.post("/pos/happy-hours")
    async def create_happy_hour(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        hh = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "outlet_id": data.get("outlet_id", ""),
            "name": data.get("name", ""),
            "start_hour": data.get("start_hour", 16),
            "end_hour": data.get("end_hour", 19),
            "discount_pct": data.get("discount_pct", 20),
            "categories": data.get("categories", []),
            "days": data.get("days", ["mon", "tue", "wed", "thu", "fri"]),
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.pos_happy_hours.insert_one(hh)
        hh.pop("_id", None)
        return hh

    @router.put("/pos/happy-hours/{hh_id}")
    async def update_happy_hour(hh_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.pos_happy_hours.update_one({"id": hh_id}, {"$set": updates})
        doc = await db.pos_happy_hours.find_one({"id": hh_id}, {"_id": 0})
        return doc

    @router.delete("/pos/happy-hours/{hh_id}")
    async def delete_happy_hour(hh_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.pos_happy_hours.delete_one({"id": hh_id})
        return {"status": "deleted"}

    # ==================== GUEST PREFERENCES ====================

    @router.get("/pos/guest-preferences/{guest_email}")
    async def get_guest_preferences(guest_email: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        prefs = await db.pos_guest_preferences.find_one({"email": guest_email}, {"_id": 0})
        if not prefs:
            return {"email": guest_email, "dietary": [], "allergens": [], "favorites": [], "dislikes": [], "notes": ""}
        return prefs

    @router.put("/pos/guest-preferences/{guest_email}")
    async def update_guest_preferences(guest_email: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        data["email"] = guest_email
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.pos_guest_preferences.update_one(
            {"email": guest_email}, {"$set": data}, upsert=True
        )
        doc = await db.pos_guest_preferences.find_one({"email": guest_email}, {"_id": 0})
        return doc

    @router.get("/pos/guest-order-history/{guest_email}")
    async def guest_order_history(guest_email: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        orders = await db.pos_orders.find(
            {"guest_email": guest_email, "payment_status": "paid"}, {"_id": 0}
        ).sort("created_at", -1).to_list(50)

        # Calculate favorites
        from collections import defaultdict
        item_freq = defaultdict(int)
        total_spent = 0
        for o in orders:
            total_spent += o.get("total", 0)
            for item in o.get("items", []):
                item_freq[item.get("name", "")] += item.get("quantity", 1)

        top_items = sorted(item_freq.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "guest_email": guest_email,
            "total_orders": len(orders),
            "total_spent": round(total_spent, 2),
            "top_items": [{"name": k, "times_ordered": v} for k, v in top_items],
            "recent_orders": orders[:10],
        }

    # ==================== LOYALTY POINTS ====================

    @router.get("/pos/loyalty/{guest_email}")
    async def get_loyalty(guest_email: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        profile = await db.guest_profiles.find_one({"email": guest_email}, {"_id": 0})
        points = profile.get("loyalty_points", 0) if profile else 0
        tier = profile.get("loyalty_tier", "standard") if profile else "standard"

        # Points history
        history = await db.loyalty_transactions.find(
            {"guest_email": guest_email}, {"_id": 0}
        ).sort("created_at", -1).to_list(20)

        tier_benefits = {
            "standard": {"earn_rate": 1, "discount_pct": 0},
            "silver": {"earn_rate": 1.5, "discount_pct": 5},
            "gold": {"earn_rate": 2, "discount_pct": 10},
            "platinum": {"earn_rate": 3, "discount_pct": 15},
        }

        return {
            "guest_email": guest_email,
            "points": points,
            "tier": tier,
            "benefits": tier_benefits.get(tier, tier_benefits["standard"]),
            "history": history,
            "points_value": round(points * 0.01, 2),
        }

    @router.post("/pos/loyalty/earn")
    async def earn_loyalty_points(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        guest_email = data.get("guest_email")
        amount = data.get("amount", 0)
        order_id = data.get("order_id", "")

        if not guest_email or amount <= 0:
            raise HTTPException(400, "Email and positive amount required")

        profile = await db.guest_profiles.find_one({"email": guest_email}, {"_id": 0})
        tier = profile.get("loyalty_tier", "standard") if profile else "standard"

        rates = {"standard": 1, "silver": 1.5, "gold": 2, "platinum": 3}
        rate = rates.get(tier, 1)
        points_earned = round(amount * rate)

        # Update profile
        await db.guest_profiles.update_one(
            {"email": guest_email},
            {"$inc": {"loyalty_points": points_earned}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )

        # Auto-upgrade tier
        new_points = (profile.get("loyalty_points", 0) if profile else 0) + points_earned
        new_tier = "standard"
        if new_points >= 5000:
            new_tier = "platinum"
        elif new_points >= 2000:
            new_tier = "gold"
        elif new_points >= 500:
            new_tier = "silver"
        if new_tier != tier:
            await db.guest_profiles.update_one({"email": guest_email}, {"$set": {"loyalty_tier": new_tier}})

        # Log transaction
        tx = {
            "id": str(uuid.uuid4()),
            "guest_email": guest_email,
            "type": "earn",
            "points": points_earned,
            "amount": amount,
            "order_id": order_id,
            "rate": rate,
            "tier": tier,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.loyalty_transactions.insert_one(tx)
        tx.pop("_id", None)

        return {"points_earned": points_earned, "total_points": new_points, "tier": new_tier, "rate": rate}

    @router.post("/pos/loyalty/redeem")
    async def redeem_loyalty_points(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        guest_email = data.get("guest_email")
        points = data.get("points", 0)

        profile = await db.guest_profiles.find_one({"email": guest_email}, {"_id": 0})
        current_points = profile.get("loyalty_points", 0) if profile else 0

        if points > current_points:
            raise HTTPException(400, f"Insufficient points. Available: {current_points}")

        discount_value = round(points * 0.01, 2)

        await db.guest_profiles.update_one(
            {"email": guest_email},
            {"$inc": {"loyalty_points": -points}}
        )

        tx = {
            "id": str(uuid.uuid4()),
            "guest_email": guest_email,
            "type": "redeem",
            "points": -points,
            "discount_value": discount_value,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.loyalty_transactions.insert_one(tx)

        return {"points_redeemed": points, "discount_value": discount_value, "remaining_points": current_points - points}

    return router
