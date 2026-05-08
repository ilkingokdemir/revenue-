"""
Hotel Point of Sale (POS) System
Multi-outlet POS for restaurants, bars, room service, spa, gift shop
Linked to Stock Management and Accounting
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from collections import defaultdict
import uuid
import logging

from routes.helpers import log_sync

logger = logging.getLogger(__name__)


def create_pos_router(db, require_roles):
    router = APIRouter()

    # ==================== OUTLETS ====================

    @router.get("/pos/outlets/{property_id}")
    async def list_outlets(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        docs = await db.pos_outlets.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if not docs:
            defaults = [
                {"id": str(uuid.uuid4()), "property_id": property_id, "name": "Restaurant", "type": "restaurant", "icon": "utensils", "tables": 12, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "property_id": property_id, "name": "Bar & Lounge", "type": "bar", "icon": "wine", "tables": 8, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "property_id": property_id, "name": "Room Service", "type": "room_service", "icon": "bell", "tables": 0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "property_id": property_id, "name": "Pool Bar", "type": "bar", "icon": "swim", "tables": 6, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "property_id": property_id, "name": "Spa", "type": "spa", "icon": "spa", "tables": 0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
                {"id": str(uuid.uuid4()), "property_id": property_id, "name": "Gift Shop", "type": "retail", "icon": "gift", "tables": 0, "active": True, "created_at": datetime.now(timezone.utc).isoformat()},
            ]
            for d in defaults:
                await db.pos_outlets.insert_one(d)
            docs = await db.pos_outlets.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        return docs

    @router.post("/pos/outlets")
    async def create_outlet(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        outlet = {
            "id": str(uuid.uuid4()), "property_id": data.get("property_id"),
            "name": data.get("name", ""), "type": data.get("type", "restaurant"),
            "icon": data.get("icon", "utensils"), "tables": data.get("tables", 0),
            "active": True, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.pos_outlets.insert_one(outlet)
        outlet.pop("_id", None)
        return outlet

    # ==================== MENU MANAGEMENT ====================

    @router.get("/pos/menu/{property_id}")
    async def get_menu(property_id: str, outlet_id: str = "", current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {"property_id": property_id}
        if outlet_id:
            query["$or"] = [{"outlet_ids": outlet_id}, {"outlet_ids": {"$exists": False}}, {"outlet_ids": []}]
        docs = await db.pos_menu_items.find(query, {"_id": 0}).sort("category", 1).to_list(500)
        if not docs:
            await _seed_menu(db, property_id)
            docs = await db.pos_menu_items.find(query, {"_id": 0}).sort("category", 1).to_list(500)
        return docs

    @router.post("/pos/menu")
    async def create_menu_item(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        item = {
            "id": str(uuid.uuid4()), "property_id": data.get("property_id"),
            "name": data.get("name", ""), "category": data.get("category", "Main"),
            "price": data.get("price", 0), "cost": data.get("cost", 0),
            "vat_rate": data.get("vat_rate", 20),
            "description": data.get("description", ""),
            "modifiers": data.get("modifiers", []),
            "allergens": data.get("allergens", []),
            "outlet_ids": data.get("outlet_ids", []),
            "available": True, "stock_linked": data.get("stock_linked", False),
            "stock_product_id": data.get("stock_product_id", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.pos_menu_items.insert_one(item)
        item.pop("_id", None)
        return item

    @router.put("/pos/menu/{item_id}")
    async def update_menu_item(item_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.pos_menu_items.update_one({"id": item_id}, {"$set": updates})
        doc = await db.pos_menu_items.find_one({"id": item_id}, {"_id": 0})
        return doc

    @router.delete("/pos/menu/{item_id}")
    async def delete_menu_item(item_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.pos_menu_items.delete_one({"id": item_id})
        return {"status": "deleted"}

    # ==================== ORDERS ====================

    @router.post("/pos/orders")
    async def create_order(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = data.get("items", [])
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

        count = await db.pos_orders.count_documents({"property_id": data.get("property_id", "")})
        order = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "outlet_id": data.get("outlet_id", ""),
            "outlet_name": data.get("outlet_name", ""),
            "order_number": f"POS-{count + 1:05d}",
            "order_type": data.get("order_type", "dine_in"),
            "table_number": data.get("table_number", ""),
            "covers": data.get("covers", 1),
            "guest_name": data.get("guest_name", ""),
            "room_number": data.get("room_number", ""),
            "booking_ref": data.get("booking_ref", ""),
            "items": items,
            "subtotal": round(subtotal, 2),
            "vat_amount": round(vat_total, 2),
            "total": round(subtotal + vat_total, 2),
            "cost_total": round(cost_total, 2),
            "discount": data.get("discount", 0),
            "discount_type": data.get("discount_type", ""),
            "payment_method": data.get("payment_method", "pending"),
            "payment_status": "pending",
            "kitchen_status": "new",
            "notes": data.get("notes", ""),
            "server_name": current_user.get("name", "Staff"),
            "server_id": current_user.get("id", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.pos_orders.insert_one(order)
        order.pop("_id", None)

        # Deduct stock for stock-linked items
        for item in items:
            if item.get("stock_product_id"):
                await db.stock_products.update_one(
                    {"id": item["stock_product_id"]},
                    {"$inc": {"current_stock": -item.get("quantity", 1)}}
                )
                # Log stock movement
                await db.stock_movements.insert_one({
                    "id": str(uuid.uuid4()),
                    "product_id": item["stock_product_id"],
                    "property_id": order.get("property_id", ""),
                    "type": "pos_sale",
                    "quantity": -item.get("quantity", 1),
                    "reference": f"POS Order {order.get('order_number','')}",
                    "order_id": order["id"],
                    "item_name": item.get("name", ""),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

        # Check low stock alerts
        low_stock = []
        for item in items:
            if item.get("stock_product_id"):
                prod = await db.stock_products.find_one({"id": item["stock_product_id"]}, {"_id": 0})
                if prod and prod.get("current_stock", 0) <= prod.get("reorder_level", 5):
                    low_stock.append({"name": prod["name"], "quantity": prod.get("current_stock", 0), "min_stock": prod.get("reorder_level", 5)})
        if low_stock:
            order["low_stock_alerts"] = low_stock

        return order

    @router.get("/pos/orders/{property_id}")
    async def list_orders(property_id: str, outlet_id: str = "", status: str = "",
                          date: str = "", current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {"property_id": property_id}
        if outlet_id:
            query["outlet_id"] = outlet_id
        if status:
            query["payment_status"] = status
        if date:
            query["created_at"] = {"$regex": f"^{date}"}
        docs = await db.pos_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    @router.get("/pos/orders/detail/{order_id}")
    async def get_order(order_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        doc = await db.pos_orders.find_one({"id": order_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Order not found")
        return doc

    # ==================== PAY / CLOSE ORDER ====================

    @router.post("/pos/orders/{order_id}/pay")
    async def pay_order(order_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        order = await db.pos_orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Order not found")

        method = data.get("payment_method", "card")
        tip = data.get("tip", 0)
        total_with_tip = round(order["total"] + tip, 2)

        # Handle void — restore stock
        if method == "void":
            await db.pos_orders.update_one({"id": order_id}, {"$set": {
                "payment_method": "void", "payment_status": "void",
                "voided_at": datetime.now(timezone.utc).isoformat(),
                "voided_by": current_user.get("name", "Staff"),
                "void_reason": data.get("reason", ""),
            }})
            # Restore stock for voided items
            for item in order.get("items", []):
                if item.get("stock_product_id"):
                    await db.stock_products.update_one(
                        {"id": item["stock_product_id"]},
                        {"$inc": {"current_stock": item.get("quantity", 1)}}
                    )
                    await db.stock_movements.insert_one({
                        "id": str(uuid.uuid4()), "product_id": item["stock_product_id"],
                        "property_id": order.get("property_id", ""),
                        "type": "void_restore", "quantity": item.get("quantity", 1),
                        "reference": f"Void: {order.get('order_number','')}",
                        "order_id": order_id, "item_name": item.get("name", ""),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
            return {"status": "voided", "order_number": order.get("order_number", "")}

        await db.pos_orders.update_one({"id": order_id}, {"$set": {
            "payment_method": method,
            "payment_status": "paid",
            "tip": tip,
            "total_with_tip": total_with_tip,
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "paid_by": current_user.get("name", "Staff"),
        }})

        # Create income entry in Accounting
        from models import IncomeEntry
        dept = "food_beverage" if order.get("outlet_name", "").lower() in ["restaurant", "bar & lounge", "pool bar", "room service"] else "other"
        income = IncomeEntry(
            property_id=order["property_id"],
            category="food_beverage" if dept == "food_beverage" else "other",
            amount=order["total"],
            currency="GBP",
            description=f"POS {order['order_number']} — {order.get('outlet_name', '')}",
            department=dept,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            source="pos",
            reference=order["order_number"],
        )
        inc_doc = income.model_dump()
        await db.income_entries.insert_one(inc_doc)

        # Room charge: if payment is "room_charge", post to booking folio
        if method == "room_charge" and order.get("room_number"):
            folio_entry = {
                "id": str(uuid.uuid4()),
                "property_id": order["property_id"],
                "room_number": order["room_number"],
                "booking_ref": order.get("booking_ref", ""),
                "guest_name": order.get("guest_name", ""),
                "description": f"POS {order['order_number']} — {order.get('outlet_name', '')}",
                "amount": order["total"],
                "type": "charge",
                "source": "pos",
                "order_id": order_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.room_folios.insert_one(folio_entry)

        await log_sync(db, "pos", "internal", "success", f"Order {order['order_number']} paid (£{total_with_tip}) via {method}", order_id)
        return {"status": "paid", "total": total_with_tip, "method": method}

    # ==================== SPLIT BILL ====================

    @router.post("/pos/orders/{order_id}/split")
    async def split_bill(order_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        order = await db.pos_orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Order not found")

        split_type = data.get("split_type", "equal")
        num_ways = data.get("num_ways", 2)

        if split_type == "equal":
            amount_each = round(order["total"] / num_ways, 2)
            splits = [{"amount": amount_each, "method": "pending", "paid": False} for _ in range(num_ways)]
        elif split_type == "by_item":
            splits = data.get("splits", [])
        else:
            splits = [{"amount": round(order["total"] / num_ways, 2), "method": "pending", "paid": False} for _ in range(num_ways)]

        await db.pos_orders.update_one({"id": order_id}, {"$set": {
            "split_bill": True, "splits": splits, "num_splits": len(splits),
        }})
        return {"splits": splits, "total": order["total"]}

    # ==================== KITCHEN DISPLAY ====================

    @router.get("/pos/kitchen/{property_id}")
    async def kitchen_orders(property_id: str, outlet_id: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query = {"property_id": property_id, "kitchen_status": {"$in": ["new", "preparing"]}, "created_at": {"$regex": f"^{today}"}}
        if outlet_id:
            query["outlet_id"] = outlet_id
        docs = await db.pos_orders.find(query, {"_id": 0}).sort("created_at", 1).to_list(50)
        return docs

    @router.post("/pos/kitchen/{order_id}/status")
    async def update_kitchen_status(order_id: str, data: Dict,
                                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        status = data.get("status", "preparing")
        await db.pos_orders.update_one({"id": order_id}, {"$set": {"kitchen_status": status}})
        return {"status": status}

    # ==================== TABLE MANAGEMENT ====================

    @router.get("/pos/tables/{outlet_id}")
    async def get_tables(outlet_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        outlet = await db.pos_outlets.find_one({"id": outlet_id}, {"_id": 0})
        if not outlet:
            return []
        num_tables = outlet.get("tables", 0)
        tables = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for i in range(1, num_tables + 1):
            active_order = await db.pos_orders.find_one(
                {"outlet_id": outlet_id, "table_number": str(i), "payment_status": "pending", "created_at": {"$regex": f"^{today}"}},
                {"_id": 0, "id": 1, "order_number": 1, "covers": 1, "total": 1, "items": 1, "created_at": 1}
            )
            tables.append({
                "number": i, "status": "occupied" if active_order else "available",
                "order": active_order,
            })
        return tables

    # ==================== SHIFTS / TILL ====================

    @router.post("/pos/shifts/open")
    async def open_shift(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        shift = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "outlet_id": data.get("outlet_id", ""),
            "opened_by": current_user.get("name", "Staff"),
            "opening_cash": data.get("opening_cash", 0),
            "status": "open",
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "closed_at": None, "closing_cash": None, "cash_difference": None,
            "total_sales": 0, "total_orders": 0, "total_tips": 0,
        }
        await db.pos_shifts.insert_one(shift)
        shift.pop("_id", None)
        return shift

    @router.post("/pos/shifts/{shift_id}/close")
    async def close_shift(shift_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        shift = await db.pos_shifts.find_one({"id": shift_id}, {"_id": 0})
        if not shift:
            raise HTTPException(404, "Shift not found")

        # Calculate shift totals
        orders = await db.pos_orders.find({
            "property_id": shift["property_id"],
            "outlet_id": shift.get("outlet_id", ""),
            "payment_status": "paid",
            "paid_at": {"$gte": shift["opened_at"]}
        }, {"_id": 0}).to_list(500)

        total_sales = sum(o.get("total", 0) for o in orders)
        total_tips = sum(o.get("tip", 0) for o in orders)
        cash_sales = sum(o.get("total", 0) for o in orders if o.get("payment_method") == "cash")
        closing_cash = data.get("closing_cash", 0)
        expected_cash = shift.get("opening_cash", 0) + cash_sales
        cash_diff = round(closing_cash - expected_cash, 2)

        # Sales by method
        by_method = defaultdict(float)
        for o in orders:
            by_method[o.get("payment_method", "other")] += o.get("total", 0)

        await db.pos_shifts.update_one({"id": shift_id}, {"$set": {
            "status": "closed",
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "closed_by": current_user.get("name", "Staff"),
            "closing_cash": closing_cash,
            "expected_cash": expected_cash,
            "cash_difference": cash_diff,
            "total_sales": round(total_sales, 2),
            "total_orders": len(orders),
            "total_tips": round(total_tips, 2),
            "sales_by_method": dict(by_method),
        }})
        return {
            "total_sales": round(total_sales, 2), "total_orders": len(orders),
            "total_tips": round(total_tips, 2), "cash_difference": cash_diff,
            "sales_by_method": dict(by_method),
        }

    @router.get("/pos/shifts/{property_id}")
    async def list_shifts(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.pos_shifts.find({"property_id": property_id}, {"_id": 0}).sort("opened_at", -1).to_list(50)
        return docs

    # ==================== ROOM CHARGING (FOLIO) ====================

    @router.get("/pos/room-folios/{property_id}")
    async def list_room_folios(property_id: str, room_number: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {"property_id": property_id}
        if room_number:
            query["room_number"] = room_number
        docs = await db.room_folios.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    # ==================== POS REPORTS ====================

    @router.get("/pos/reports/{property_id}")
    async def pos_reports(property_id: str, date: str = "", outlet_id: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        query = {"property_id": property_id, "payment_status": "paid", "created_at": {"$regex": f"^{date}"}}
        if outlet_id:
            query["outlet_id"] = outlet_id
        orders = await db.pos_orders.find(query, {"_id": 0}).to_list(500)

        total_revenue = sum(o.get("total", 0) for o in orders)
        total_cost = sum(o.get("cost_total", 0) for o in orders)
        total_tips = sum(o.get("tip", 0) for o in orders)
        total_covers = sum(o.get("covers", 0) for o in orders)
        avg_check = round(total_revenue / len(orders), 2) if orders else 0
        avg_per_cover = round(total_revenue / total_covers, 2) if total_covers else 0
        gross_margin = round(((total_revenue - total_cost) / total_revenue * 100) if total_revenue else 0, 1)

        # By outlet
        by_outlet = defaultdict(lambda: {"revenue": 0, "orders": 0, "covers": 0})
        for o in orders:
            name = o.get("outlet_name", "Other")
            by_outlet[name]["revenue"] += o.get("total", 0)
            by_outlet[name]["orders"] += 1
            by_outlet[name]["covers"] += o.get("covers", 0)

        # By payment method
        by_method = defaultdict(float)
        for o in orders:
            by_method[o.get("payment_method", "other")] += o.get("total", 0)

        # By server
        by_server = defaultdict(lambda: {"revenue": 0, "orders": 0, "tips": 0})
        for o in orders:
            name = o.get("server_name", "Unknown")
            by_server[name]["revenue"] += o.get("total", 0)
            by_server[name]["orders"] += 1
            by_server[name]["tips"] += o.get("tip", 0)

        # Top items
        item_sales = defaultdict(lambda: {"qty": 0, "revenue": 0})
        for o in orders:
            for item in o.get("items", []):
                name = item.get("name", "")
                item_sales[name]["qty"] += item.get("quantity", 1)
                item_sales[name]["revenue"] += item.get("line_total", 0)
        top_items = sorted(item_sales.items(), key=lambda x: x[1]["revenue"], reverse=True)[:10]

        # Hourly breakdown
        hourly = defaultdict(lambda: {"revenue": 0, "orders": 0})
        for o in orders:
            try:
                hour = o["created_at"][11:13]
                hourly[hour]["revenue"] += o.get("total", 0)
                hourly[hour]["orders"] += 1
            except Exception:
                pass

        return {
            "date": date,
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "gross_margin": gross_margin,
            "total_orders": len(orders),
            "total_covers": total_covers,
            "avg_check": avg_check,
            "avg_per_cover": avg_per_cover,
            "total_tips": round(total_tips, 2),
            "by_outlet": {k: {kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in by_outlet.items()},
            "by_method": {k: round(v, 2) for k, v in by_method.items()},
            "by_server": {k: {kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in by_server.items()},
            "top_items": [{"name": k, **v} for k, v in top_items],
            "hourly": dict(sorted(hourly.items())),
        }

    # ==================== STOCK LINKING ====================

    @router.post("/pos/link-stock/{property_id}")
    async def auto_link_menu_stock(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Auto-create stock products for menu items and link them"""
        menu_items = await db.pos_menu_items.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        linked = 0
        created = 0
        for mi in menu_items:
            if mi.get("stock_product_id"):
                # Verify the linked product exists
                exists = await db.stock_products.find_one({"id": mi["stock_product_id"]}, {"_id": 0, "id": 1})
                if exists:
                    linked += 1
                    continue
                # Product doesn't exist — clear the broken link
                await db.pos_menu_items.update_one({"id": mi["id"]}, {"$set": {"stock_product_id": "", "stock_linked": False}})
            
            # Check if stock product already exists with same name
            existing = await db.stock_products.find_one({"property_id": property_id, "name": mi["name"]}, {"_id": 0})
            if existing:
                await db.pos_menu_items.update_one(
                    {"id": mi["id"]},
                    {"$set": {"stock_product_id": existing["id"], "stock_linked": True}}
                )
                linked += 1
            else:
                # Create stock product
                from models import StockProduct
                category_map = {
                    "Beer": "beverages", "Wine": "beverages", "Cocktails": "beverages",
                    "Soft Drinks": "beverages", "Hot Drinks": "beverages",
                    "Starters": "food", "Mains": "food", "Desserts": "food",
                    "Room Service": "food", "Spa": "supplies",
                }
                prod = StockProduct(
                    property_id=property_id,
                    name=mi["name"],
                    category=category_map.get(mi.get("category", ""), "food"),
                    unit="portion",
                    current_stock=50,
                    reorder_level=5,
                    par_level=30,
                    cost_price=mi.get("cost", 0),
                    sell_price=mi.get("price", 0),
                    supplier="Internal Kitchen",
                )
                doc = prod.model_dump()
                await db.stock_products.insert_one(doc)
                doc.pop("_id", None)
                # Link to menu item
                await db.pos_menu_items.update_one(
                    {"id": mi["id"]},
                    {"$set": {"stock_product_id": doc["id"], "stock_linked": True}}
                )
                created += 1
                linked += 1

        return {"linked": linked, "created": created, "total_menu_items": len(menu_items),
                "message": f"Linked {linked} items ({created} new stock products created)"}

    @router.get("/pos/stock-status/{property_id}")
    async def get_menu_stock_status(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Get stock levels for all menu items"""
        menu_items = await db.pos_menu_items.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        result = []
        low_stock = []
        out_of_stock = []
        for mi in menu_items:
            item = {"id": mi["id"], "name": mi["name"], "category": mi.get("category", ""), "price": mi.get("price", 0), "stock_linked": bool(mi.get("stock_product_id"))}
            if mi.get("stock_product_id"):
                prod = await db.stock_products.find_one({"id": mi["stock_product_id"]}, {"_id": 0})
                if prod:
                    item["stock_quantity"] = prod.get("current_stock", 0)
                    item["min_stock"] = prod.get("reorder_level", 5)
                    item["stock_product_name"] = prod.get("name", "")
                    if prod.get("current_stock", 0) <= 0:
                        out_of_stock.append(mi["name"])
                    elif prod.get("current_stock", 0) <= prod.get("reorder_level", 5):
                        low_stock.append({"name": mi["name"], "quantity": prod.get("current_stock", 0), "min_stock": prod.get("reorder_level", 5)})
            result.append(item)
        return {"items": result, "low_stock": low_stock, "out_of_stock": out_of_stock,
                "total_linked": sum(1 for i in result if i.get("stock_linked")),
                "total_items": len(result)}

    @router.get("/pos/stock-movements/{property_id}")
    async def get_stock_movements(property_id: str, limit: int = 50, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Get recent stock movements from POS orders"""
        docs = await db.stock_movements.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(limit)
        return docs

    return router


async def _seed_menu(db, property_id):
    """Seed default menu items for a property"""
    menu_items = [
        # Starters
        {"name": "Soup of the Day", "category": "Starters", "price": 7.50, "cost": 1.80, "vat_rate": 20},
        {"name": "Bruschetta", "category": "Starters", "price": 8.95, "cost": 2.20, "vat_rate": 20},
        {"name": "Caesar Salad", "category": "Starters", "price": 9.50, "cost": 2.50, "vat_rate": 20},
        {"name": "Prawn Cocktail", "category": "Starters", "price": 11.50, "cost": 4.20, "vat_rate": 20},
        {"name": "Garlic Bread", "category": "Starters", "price": 5.50, "cost": 0.90, "vat_rate": 20},
        # Mains
        {"name": "Grilled Salmon", "category": "Mains", "price": 22.50, "cost": 8.50, "vat_rate": 20},
        {"name": "Ribeye Steak 10oz", "category": "Mains", "price": 28.00, "cost": 12.00, "vat_rate": 20},
        {"name": "Chicken Supreme", "category": "Mains", "price": 18.50, "cost": 5.50, "vat_rate": 20},
        {"name": "Fish & Chips", "category": "Mains", "price": 16.00, "cost": 4.80, "vat_rate": 20},
        {"name": "Mushroom Risotto", "category": "Mains", "price": 15.50, "cost": 3.20, "vat_rate": 20, "allergens": ["dairy"]},
        {"name": "Beef Burger & Fries", "category": "Mains", "price": 14.50, "cost": 4.00, "vat_rate": 20},
        {"name": "Lamb Shank", "category": "Mains", "price": 24.00, "cost": 9.00, "vat_rate": 20},
        # Desserts
        {"name": "Sticky Toffee Pudding", "category": "Desserts", "price": 8.50, "cost": 1.80, "vat_rate": 20},
        {"name": "Chocolate Fondant", "category": "Desserts", "price": 9.50, "cost": 2.20, "vat_rate": 20},
        {"name": "Cheesecake", "category": "Desserts", "price": 8.00, "cost": 1.60, "vat_rate": 20},
        {"name": "Ice Cream (3 scoops)", "category": "Desserts", "price": 6.50, "cost": 1.20, "vat_rate": 20},
        # Drinks - Soft
        {"name": "Coca-Cola", "category": "Soft Drinks", "price": 3.50, "cost": 0.40, "vat_rate": 20},
        {"name": "Orange Juice", "category": "Soft Drinks", "price": 3.50, "cost": 0.60, "vat_rate": 20},
        {"name": "Sparkling Water", "category": "Soft Drinks", "price": 2.80, "cost": 0.30, "vat_rate": 20},
        {"name": "Coffee", "category": "Hot Drinks", "price": 3.20, "cost": 0.35, "vat_rate": 20},
        {"name": "Tea", "category": "Hot Drinks", "price": 2.80, "cost": 0.15, "vat_rate": 20},
        {"name": "Cappuccino", "category": "Hot Drinks", "price": 3.80, "cost": 0.50, "vat_rate": 20},
        # Drinks - Alcoholic
        {"name": "House Wine (Glass)", "category": "Wine", "price": 7.50, "cost": 1.80, "vat_rate": 20},
        {"name": "House Wine (Bottle)", "category": "Wine", "price": 24.00, "cost": 6.00, "vat_rate": 20},
        {"name": "Prosecco (Glass)", "category": "Wine", "price": 8.50, "cost": 2.00, "vat_rate": 20},
        {"name": "Pint of Lager", "category": "Beer", "price": 5.80, "cost": 1.40, "vat_rate": 20},
        {"name": "Craft IPA", "category": "Beer", "price": 6.50, "cost": 1.80, "vat_rate": 20},
        {"name": "Gin & Tonic", "category": "Cocktails", "price": 9.50, "cost": 2.50, "vat_rate": 20},
        {"name": "Mojito", "category": "Cocktails", "price": 10.50, "cost": 2.80, "vat_rate": 20},
        {"name": "Espresso Martini", "category": "Cocktails", "price": 11.00, "cost": 3.00, "vat_rate": 20},
        # Spa
        {"name": "Full Body Massage (60m)", "category": "Spa", "price": 85.00, "cost": 20.00, "vat_rate": 20},
        {"name": "Facial Treatment", "category": "Spa", "price": 65.00, "cost": 15.00, "vat_rate": 20},
        {"name": "Manicure & Pedicure", "category": "Spa", "price": 45.00, "cost": 8.00, "vat_rate": 20},
        # Room Service Extras
        {"name": "Continental Breakfast", "category": "Room Service", "price": 14.00, "cost": 3.50, "vat_rate": 20},
        {"name": "Full English Breakfast", "category": "Room Service", "price": 18.00, "cost": 5.00, "vat_rate": 20},
        {"name": "Club Sandwich", "category": "Room Service", "price": 13.50, "cost": 3.80, "vat_rate": 20},
        {"name": "Cheese & Charcuterie Board", "category": "Room Service", "price": 16.00, "cost": 5.50, "vat_rate": 20},
    ]
    for mi in menu_items:
        mi["id"] = str(uuid.uuid4())
        mi["property_id"] = property_id
        mi["available"] = True
        mi["outlet_ids"] = []
        mi["stock_linked"] = False
        mi["stock_product_id"] = ""
        mi["modifiers"] = []
        mi["description"] = ""
        mi["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.pos_menu_items.insert_one(mi)
