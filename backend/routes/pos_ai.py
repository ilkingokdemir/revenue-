"""
AI Upselling Engine + Self-Service Kiosk Support
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
from collections import defaultdict
import uuid
import os
import logging

logger = logging.getLogger(__name__)


def create_pos_ai_router(db, require_roles, LlmChat, UserMessage):
    router = APIRouter()

    # ==================== AI UPSELLING ====================

    @router.post("/pos/ai-upsell")
    async def ai_upsell_suggestions(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Generate AI-powered upsell suggestions based on current cart + guest history"""
        property_id = data.get("property_id")
        cart_items = data.get("cart_items", [])
        guest_email = data.get("guest_email", "")

        # Get menu
        menu_items = await db.pos_menu_items.find({"property_id": property_id, "available": True}, {"_id": 0}).to_list(200)
        menu_names = {m["name"]: m for m in menu_items}

        # Guest history
        history_context = ""
        if guest_email:
            past_orders = await db.pos_orders.find(
                {"guest_email": guest_email, "payment_status": "paid"}, {"_id": 0}
            ).sort("created_at", -1).to_list(10)

            item_freq = defaultdict(int)
            for o in past_orders:
                for item in o.get("items", []):
                    item_freq[item.get("name", "")] += item.get("quantity", 1)
            top_items = sorted(item_freq.items(), key=lambda x: x[1], reverse=True)[:5]

            prefs = await db.pos_guest_preferences.find_one({"email": guest_email}, {"_id": 0})

            if top_items:
                history_context = f"Guest frequently orders: {', '.join(f'{n} ({c}x)' for n, c in top_items)}. "
            if prefs:
                if prefs.get("dietary"):
                    history_context += f"Dietary: {', '.join(prefs['dietary'])}. "
                if prefs.get("allergens"):
                    history_context += f"Allergens to avoid: {', '.join(prefs['allergens'])}. "
                if prefs.get("favorites"):
                    history_context += f"Favorites: {', '.join(prefs['favorites'])}. "

        cart_names = [f"{i.get('name', '')} (x{i.get('quantity', 1)})" for i in cart_items]
        cart_text = ", ".join(cart_names) if cart_names else "empty cart"

        # Available items not in cart
        cart_item_names = set(i.get("name", "") for i in cart_items)
        available = [m["name"] for m in menu_items if m["name"] not in cart_item_names][:30]

        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            # Fallback: rule-based suggestions
            suggestions = _rule_based_upsell(cart_items, menu_items)
            return {"suggestions": suggestions, "source": "rules"}

        try:
            chat = LlmChat(
                api_key=llm_key,
                session_id=f"upsell-{uuid.uuid4()}",
                system_message="You are a hotel restaurant upselling assistant. Suggest 3-4 additional menu items that pair well with the guest's current order. Consider their history and preferences. Be brief and persuasive. Return a JSON array of objects with 'name' (exact menu item name) and 'reason' (1-sentence why). Only suggest items from the available menu list."
            ).with_model("openai", "gpt-5.2")

            prompt = f"""Current order: {cart_text}
{history_context}
Available menu items: {', '.join(available[:20])}

Suggest 3-4 upsell items as JSON array: [{{"name": "...", "reason": "..."}}]"""

            reply = await chat.send_message(UserMessage(text=prompt))

            # Parse AI response
            import json
            try:
                # Extract JSON from response
                text = reply.strip()
                if "```" in text:
                    text = text.split("```")[1].strip()
                    if text.startswith("json"):
                        text = text[4:].strip()
                if text.startswith("["):
                    suggestions_raw = json.loads(text)
                else:
                    # Try to find array in text
                    start = text.index("[")
                    end = text.rindex("]") + 1
                    suggestions_raw = json.loads(text[start:end])

                # Match to actual menu items with prices
                suggestions = []
                for s in suggestions_raw[:4]:
                    name = s.get("name", "")
                    if name in menu_names:
                        suggestions.append({
                            "name": name,
                            "price": menu_names[name]["price"],
                            "category": menu_names[name]["category"],
                            "reason": s.get("reason", ""),
                        })
                return {"suggestions": suggestions, "source": "ai"}
            except Exception:
                suggestions = _rule_based_upsell(cart_items, menu_items)
                return {"suggestions": suggestions, "source": "rules_fallback"}

        except Exception as e:
            logger.error(f"AI upsell error: {e}")
            suggestions = _rule_based_upsell(cart_items, menu_items)
            return {"suggestions": suggestions, "source": "rules_fallback"}

    # ==================== KIOSK SESSION ====================

    @router.post("/pos/kiosk/start")
    async def kiosk_start_session(data: Dict):
        """Public - start a kiosk ordering session"""
        session = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "outlet_id": data.get("outlet_id", ""),
            "kiosk_id": data.get("kiosk_id", "kiosk-1"),
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return session

    @router.post("/pos/kiosk/order")
    async def kiosk_place_order(data: Dict):
        """Public - place order from kiosk"""
        items = data.get("items", [])
        if not items:
            raise HTTPException(400, "No items")

        subtotal = 0
        vat_total = 0
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

        count = await db.pos_orders.count_documents({"property_id": data.get("property_id", "")})
        order = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "outlet_id": data.get("outlet_id", ""),
            "outlet_name": data.get("outlet_name", ""),
            "order_number": f"KSK-{count + 1:05d}",
            "order_type": "kiosk",
            "table_number": data.get("table_number", ""),
            "covers": 1,
            "guest_name": data.get("guest_name", "Kiosk Guest"),
            "room_number": data.get("room_number", ""),
            "items": items,
            "subtotal": round(subtotal, 2),
            "vat_amount": round(vat_total, 2),
            "total": round(subtotal + vat_total, 2),
            "payment_method": data.get("payment_method", "card"),
            "payment_status": "paid",
            "kitchen_status": "new",
            "server_name": "Self-Service Kiosk",
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.pos_orders.insert_one(order)
        order.pop("_id", None)

        # Auto income entry
        from models import IncomeEntry
        income = IncomeEntry(
            property_id=order["property_id"],
            category="food_beverage",
            amount=order["total"],
            currency="GBP",
            description=f"Kiosk {order['order_number']}",
            department="food_beverage",
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            source="pos_kiosk",
            reference=order["order_number"],
        )
        inc_doc = income.model_dump()
        await db.income_entries.insert_one(inc_doc)

        return {"order_number": order["order_number"], "total": order["total"]}

    return router


def _rule_based_upsell(cart_items, menu_items):
    """Simple rule-based upselling when AI is unavailable"""
    cart_cats = set(i.get("category", "") for i in cart_items)
    cart_names = set(i.get("name", "") for i in cart_items)
    suggestions = []

    # If ordering mains but no drinks, suggest a drink
    if any(c in cart_cats for c in ["Mains", "Starters"]):
        if not any(c in cart_cats for c in ["Wine", "Beer", "Cocktails", "Soft Drinks"]):
            drinks = [m for m in menu_items if m["category"] in ("Wine", "Beer", "Cocktails") and m["name"] not in cart_names]
            if drinks:
                d = drinks[0]
                suggestions.append({"name": d["name"], "price": d["price"], "category": d["category"], "reason": "Pairs perfectly with your meal"})

    # If ordering mains but no dessert, suggest dessert
    if any(c in cart_cats for c in ["Mains"]):
        if "Desserts" not in cart_cats:
            desserts = [m for m in menu_items if m["category"] == "Desserts" and m["name"] not in cart_names]
            if desserts:
                d = desserts[0]
                suggestions.append({"name": d["name"], "price": d["price"], "category": d["category"], "reason": "The perfect way to finish your meal"})

    # If no starters, suggest one
    if "Starters" not in cart_cats:
        starters = [m for m in menu_items if m["category"] == "Starters" and m["name"] not in cart_names]
        if starters:
            s = starters[0]
            suggestions.append({"name": s["name"], "price": s["price"], "category": s["category"], "reason": "Start your dining experience right"})

    # If ordering drinks but no snacks
    if any(c in cart_cats for c in ["Wine", "Beer", "Cocktails"]) and not any(c in cart_cats for c in ["Mains", "Starters"]):
        snacks = [m for m in menu_items if m["category"] == "Starters" and m["name"] not in cart_names]
        if snacks:
            s = snacks[0]
            suggestions.append({"name": s["name"], "price": s["price"], "category": s["category"], "reason": "Something to nibble with your drinks"})

    return suggestions[:4]
