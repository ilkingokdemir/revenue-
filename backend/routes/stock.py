"""
Hotel Stock Management Routes
Product catalog, recipes, stock tracking, variance alerts, all-inclusive costing
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import asyncio
import logging

from routes.helpers import fire_webhooks, log_sync

logger = logging.getLogger(__name__)


def create_stock_router(db, require_roles):
    router = APIRouter()

    # === Products ===

    @router.get("/stock/products/{property_id}")
    async def list_products(property_id: str, category: str = "", search: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if category: query["category"] = category
        if search: query["name"] = {"$regex": search, "$options": "i"}
        docs = await db.stock_products.find(query, {"_id": 0}).sort("name", 1).to_list(500)
        return docs

    @router.post("/stock/products")
    async def create_product(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import StockProduct
        prod = StockProduct(**data)
        doc = prod.model_dump()
        await db.stock_products.insert_one(doc)
        doc.pop("_id", None)
        await log_sync(db, "stock", "internal", "success", f"Product created: {doc['name']}", doc["id"])
        return doc

    @router.put("/stock/products/{product_id}")
    async def update_product(product_id: str, updates: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.stock_products.update_one({"id": product_id}, {"$set": updates})
        doc = await db.stock_products.find_one({"id": product_id}, {"_id": 0})
        return doc

    @router.delete("/stock/products/{product_id}")
    async def delete_product(product_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.stock_products.delete_one({"id": product_id})
        return {"status": "deleted"}

    # === Recipes (Portion-Based) ===

    @router.get("/stock/recipes/{property_id}")
    async def list_recipes(property_id: str, outlet: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if outlet: query["outlet"] = outlet
        docs = await db.stock_recipes.find(query, {"_id": 0}).sort("name", 1).to_list(200)
        return docs

    @router.post("/stock/recipes")
    async def create_recipe(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import Recipe
        # Calculate total cost from ingredients
        ingredients = data.get("ingredients", [])
        total_cost = 0
        for ing in ingredients:
            prod = await db.stock_products.find_one({"id": ing.get("product_id")}, {"_id": 0})
            if prod:
                ing["product_name"] = prod["name"]
                cost = prod.get("cost_price", 0) * ing.get("quantity", 0)
                total_cost += cost
        data["total_cost"] = round(total_cost, 2)
        sell = data.get("sell_price", 0)
        data["margin_pct"] = round(((sell - total_cost) / sell * 100) if sell > 0 else 0, 1)
        recipe = Recipe(**data)
        doc = recipe.model_dump()
        await db.stock_recipes.insert_one(doc)
        doc.pop("_id", None)
        await log_sync(db, "stock", "internal", "success", f"Recipe created: {doc['name']} (cost: £{total_cost})", doc["id"])
        return doc

    @router.put("/stock/recipes/{recipe_id}")
    async def update_recipe(recipe_id: str, updates: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        if "ingredients" in updates:
            total_cost = 0
            for ing in updates["ingredients"]:
                prod = await db.stock_products.find_one({"id": ing.get("product_id")}, {"_id": 0})
                if prod:
                    ing["product_name"] = prod["name"]
                    total_cost += prod.get("cost_price", 0) * ing.get("quantity", 0)
            updates["total_cost"] = round(total_cost, 2)
            sell = updates.get("sell_price", 0)
            if not sell:
                existing = await db.stock_recipes.find_one({"id": recipe_id}, {"_id": 0})
                sell = existing.get("sell_price", 0) if existing else 0
            updates["margin_pct"] = round(((sell - total_cost) / sell * 100) if sell > 0 else 0, 1)
        await db.stock_recipes.update_one({"id": recipe_id}, {"$set": updates})
        doc = await db.stock_recipes.find_one({"id": recipe_id}, {"_id": 0})
        return doc

    @router.delete("/stock/recipes/{recipe_id}")
    async def delete_recipe(recipe_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.stock_recipes.delete_one({"id": recipe_id})
        return {"status": "deleted"}

    # === Stock Movements ===

    @router.get("/stock/movements/{property_id}")
    async def list_movements(property_id: str, product_id: str = "", movement_type: str = "",
                              outlet: str = "", limit: int = 100,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if product_id: query["product_id"] = product_id
        if movement_type: query["movement_type"] = movement_type
        if outlet: query["outlet"] = outlet
        docs = await db.stock_movements.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
        return docs

    @router.post("/stock/movements")
    async def record_movement(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import StockMovement
        product = await db.stock_products.find_one({"id": data.get("product_id")}, {"_id": 0})
        if product:
            data["product_name"] = product["name"]
            data["unit"] = product.get("unit", "")
            data["cost"] = round(product.get("cost_price", 0) * abs(data.get("quantity", 0)), 2)
        data["recorded_by"] = current_user.get("name", "Staff")
        mv = StockMovement(**data)
        doc = mv.model_dump()
        await db.stock_movements.insert_one(doc)
        doc.pop("_id", None)

        # Update stock level
        qty = data.get("quantity", 0)
        mt = data.get("movement_type", "")
        if mt in ["purchase", "transfer_in", "adjustment"]:
            await db.stock_products.update_one({"id": data["product_id"]}, {"$inc": {"current_stock": abs(qty)}})
        elif mt in ["usage", "waste", "transfer_out"]:
            await db.stock_products.update_one({"id": data["product_id"]}, {"$inc": {"current_stock": -abs(qty)}})
        elif mt == "stocktake":
            await db.stock_products.update_one({"id": data["product_id"]}, {"$set": {"current_stock": qty}})

        await log_sync(db, "stock", "internal", "success", f"{mt}: {data.get('product_name', '')} x{qty}", doc["id"])
        asyncio.create_task(fire_webhooks(db, "stock.movement", {"type": mt, "product": data.get("product_name"), "quantity": qty}))
        return doc

    # === Outlets ===

    @router.get("/stock/outlets/{property_id}")
    async def list_outlets(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.stock_outlets.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not docs:
            from models import Outlet
            defaults = [
                Outlet(property_id=property_id, name="Main Restaurant", outlet_type="restaurant"),
                Outlet(property_id=property_id, name="Lobby Bar", outlet_type="bar"),
                Outlet(property_id=property_id, name="Pool Café", outlet_type="cafe"),
                Outlet(property_id=property_id, name="Kitchen Store", outlet_type="kitchen"),
            ]
            for o in defaults:
                d = o.model_dump()
                await db.stock_outlets.insert_one(d)
            docs = await db.stock_outlets.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        return docs

    @router.post("/stock/outlets")
    async def create_outlet(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import Outlet
        outlet = Outlet(**data)
        doc = outlet.model_dump()
        await db.stock_outlets.insert_one(doc)
        doc.pop("_id", None)
        return doc

    # === Variance / Theft Detection ===

    @router.post("/stock/variance/{property_id}")
    async def run_variance_check(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Compare expected vs actual stock to detect theft/waste"""
        from models import StockVariance
        products = await db.stock_products.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(500)
        variances = []
        flagged = 0

        for prod in products:
            # Calculate expected: starting stock + purchases - usage - waste - transfers out
            pipeline = [
                {"$match": {"product_id": prod["id"]}},
                {"$group": {
                    "_id": "$movement_type",
                    "total": {"$sum": "$quantity"}
                }}
            ]
            movements = {}
            async for doc in db.stock_movements.aggregate(pipeline):
                movements[doc["_id"]] = doc["total"]

            purchases = movements.get("purchase", 0) + movements.get("transfer_in", 0)
            usage = movements.get("usage", 0) + movements.get("waste", 0) + movements.get("transfer_out", 0)
            expected = purchases - usage
            actual = prod.get("current_stock", 0)
            variance = actual - expected
            variance_pct = round((variance / expected * 100) if expected > 0 else 0, 1)
            variance_cost = round(abs(variance) * prod.get("cost_price", 0), 2)

            if abs(variance_pct) > 5 or variance_cost > 10:
                sv = StockVariance(
                    property_id=property_id, product_id=prod["id"],
                    product_name=prod["name"], expected_stock=round(expected, 2),
                    actual_stock=actual, variance=round(variance, 2),
                    variance_pct=variance_pct, variance_cost=variance_cost,
                    recorded_by=current_user.get("name", ""),
                )
                doc = sv.model_dump()
                await db.stock_variances.insert_one(doc)
                doc.pop("_id", None)
                variances.append(doc)
                flagged += 1

        if flagged > 0:
            asyncio.create_task(fire_webhooks(db, "stock.variance_alert", {"property_id": property_id, "flagged": flagged}))
            await log_sync(db, "stock", "internal", "warning", f"Variance check: {flagged} products flagged", property_id)

        return {"message": f"Variance check complete. {flagged} products flagged.", "flagged": flagged, "variances": variances}

    @router.get("/stock/variances/{property_id}")
    async def list_variances(property_id: str, status: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if status: query["status"] = status
        docs = await db.stock_variances.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    # === All-Inclusive Cost Calculation ===

    @router.get("/stock/all-inclusive-cost/{property_id}")
    async def all_inclusive_cost(property_id: str, days: int = 30,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Calculate F&B cost per guest per day for all-inclusive pricing"""
        cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=days)).isoformat()

        # Total F&B cost (purchases in period)
        pipeline = [
            {"$match": {"property_id": property_id, "movement_type": "purchase", "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total_cost": {"$sum": "$cost"}, "count": {"$sum": 1}}}
        ]
        total_cost = 0
        async for doc in db.stock_movements.aggregate(pipeline):
            total_cost = doc["total_cost"]

        # Total waste
        waste_pipeline = [
            {"$match": {"property_id": property_id, "movement_type": "waste", "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total": {"$sum": "$cost"}}}
        ]
        waste_cost = 0
        async for doc in db.stock_movements.aggregate(waste_pipeline):
            waste_cost = doc["total"]

        # Guest nights in period
        bookings = await db.bookings.find(
            {"property_id": property_id, "status": {"$ne": "cancelled"}},
            {"_id": 0, "check_in": 1, "check_out": 1, "guests": 1}
        ).to_list(2000)
        total_guest_nights = 0
        for b in bookings:
            try:
                ci = datetime.fromisoformat(b.get("check_in", "2026-01-01"))
                co = datetime.fromisoformat(b.get("check_out", "2026-01-02"))
                nights = max(1, (co - ci).days)
                guests = b.get("guests", 1) or 1
                total_guest_nights += nights * guests
            except (ValueError, TypeError):
                total_guest_nights += 1

        cost_per_guest_night = round(total_cost / total_guest_nights, 2) if total_guest_nights > 0 else 0
        waste_per_guest = round(waste_cost / total_guest_nights, 2) if total_guest_nights > 0 else 0

        # Category breakdown
        cat_pipeline = [
            {"$match": {"property_id": property_id, "movement_type": "purchase", "created_at": {"$gte": cutoff}}},
            {"$lookup": {"from": "stock_products", "localField": "product_id", "foreignField": "id", "as": "product"}},
            {"$unwind": {"path": "$product", "preserveNullAndEmptyArrays": True}},
            {"$group": {"_id": "$product.category", "total": {"$sum": "$cost"}}}
        ]
        by_category = {}
        async for doc in db.stock_movements.aggregate(cat_pipeline):
            by_category[doc["_id"] or "other"] = round(doc["total"], 2)

        # Low stock alerts
        low_stock = await db.stock_products.find(
            {"property_id": property_id, "is_active": True, "$expr": {"$lte": ["$current_stock", "$reorder_level"]}},
            {"_id": 0, "id": 1, "name": 1, "current_stock": 1, "reorder_level": 1, "unit": 1}
        ).to_list(50)

        return {
            "period_days": days,
            "total_fb_cost": round(total_cost, 2),
            "total_waste_cost": round(waste_cost, 2),
            "total_guest_nights": total_guest_nights,
            "cost_per_guest_night": cost_per_guest_night,
            "waste_per_guest_night": waste_per_guest,
            "by_category": by_category,
            "low_stock_alerts": low_stock,
        }

    # === Dashboard Stats ===

    @router.get("/stock/stats/{property_id}")
    async def stock_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        total_products = await db.stock_products.count_documents({"property_id": property_id, "is_active": True})
        total_recipes = await db.stock_recipes.count_documents({"property_id": property_id})
        total_movements = await db.stock_movements.count_documents({"property_id": property_id})
        total_variances = await db.stock_variances.count_documents({"property_id": property_id, "status": "flagged"})

        # Total stock value
        pipeline = [
            {"$match": {"property_id": property_id, "is_active": True}},
            {"$group": {"_id": None, "total_value": {"$sum": {"$multiply": ["$current_stock", "$cost_price"]}}}}
        ]
        stock_value = 0
        async for doc in db.stock_products.aggregate(pipeline):
            stock_value = round(doc["total_value"], 2)

        low_stock_count = 0
        prods = await db.stock_products.find({"property_id": property_id, "is_active": True}, {"_id": 0, "current_stock": 1, "reorder_level": 1}).to_list(500)
        for p in prods:
            if p.get("reorder_level", 0) > 0 and p.get("current_stock", 0) <= p.get("reorder_level", 0):
                low_stock_count += 1

        return {
            "total_products": total_products, "total_recipes": total_recipes,
            "total_movements": total_movements, "flagged_variances": total_variances,
            "stock_value": stock_value, "low_stock_count": low_stock_count,
        }

    # === Sub-Recipes (Apicbase-level: recipe within recipe) ===

    @router.get("/stock/sub-recipes/{property_id}")
    async def list_sub_recipes(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.sub_recipes.find({"property_id": property_id}, {"_id": 0}).sort("name", 1).to_list(200)
        return docs

    @router.post("/stock/sub-recipes")
    async def create_sub_recipe(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import SubRecipe
        ingredients = data.get("ingredients", [])
        total_cost = 0
        for ing in ingredients:
            prod = await db.stock_products.find_one({"id": ing.get("product_id")}, {"_id": 0})
            if prod:
                ing["product_name"] = prod["name"]
                total_cost += prod.get("cost_price", 0) * ing.get("quantity", 0)
        data["total_cost"] = round(total_cost, 2)
        yield_qty = data.get("yield_qty", 1) or 1
        data["cost_per_unit"] = round(total_cost / yield_qty, 2)
        sr = SubRecipe(**data)
        doc = sr.model_dump()
        await db.sub_recipes.insert_one(doc)
        doc.pop("_id", None)
        return doc

    # === Wastage with Reason Codes ===

    @router.post("/stock/waste")
    async def record_waste(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Record waste with reason code for detailed tracking"""
        from models import StockMovement
        product = await db.stock_products.find_one({"id": data.get("product_id")}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        qty = abs(data.get("quantity", 0))
        reason = data.get("reason", "other")
        mv = StockMovement(
            property_id=data.get("property_id", ""),
            product_id=data["product_id"], product_name=product["name"],
            movement_type="waste", quantity=qty, unit=product.get("unit", ""),
            cost=round(product.get("cost_price", 0) * qty, 2),
            outlet=data.get("outlet", ""),
            reference=f"waste:{reason}",
            notes=f"Reason: {reason}. {data.get('notes', '')}",
            recorded_by=current_user.get("name", "Staff"),
        )
        doc = mv.model_dump()
        await db.stock_movements.insert_one(doc)
        doc.pop("_id", None)
        await db.stock_products.update_one({"id": data["product_id"]}, {"$inc": {"current_stock": -qty}})
        await log_sync(db, "stock", "internal", "warning", f"Waste recorded: {product['name']} x{qty} ({reason})", doc["id"])
        asyncio.create_task(fire_webhooks(db, "stock.waste", {"product": product["name"], "quantity": qty, "reason": reason, "cost": doc["cost"]}))
        return doc

    @router.get("/stock/waste-report/{property_id}")
    async def waste_report(property_id: str, days: int = 30,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=days)).isoformat()
        pipeline = [
            {"$match": {"property_id": property_id, "movement_type": "waste", "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": "$reference", "total_cost": {"$sum": "$cost"}, "count": {"$sum": 1}}}
        ]
        by_reason = {}
        total_waste = 0
        async for doc in db.stock_movements.aggregate(pipeline):
            reason = (doc["_id"] or "waste:other").replace("waste:", "")
            by_reason[reason] = {"cost": round(doc["total_cost"], 2), "count": doc["count"]}
            total_waste += doc["total_cost"]

        prod_pipeline = [
            {"$match": {"property_id": property_id, "movement_type": "waste", "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": "$product_name", "total_cost": {"$sum": "$cost"}, "total_qty": {"$sum": "$quantity"}}},
            {"$sort": {"total_cost": -1}},
            {"$limit": 10}
        ]
        top_waste_products = []
        async for doc in db.stock_movements.aggregate(prod_pipeline):
            top_waste_products.append({"product": doc["_id"], "cost": round(doc["total_cost"], 2), "quantity": doc["total_qty"]})

        return {"total_waste_cost": round(total_waste, 2), "by_reason": by_reason, "top_products": top_waste_products, "period_days": days}

    # === Theoretical vs Actual Consumption (Apicbase core theft-proof) ===

    @router.get("/stock/theoretical-vs-actual/{property_id}")
    async def theoretical_vs_actual(property_id: str,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Compare theoretical consumption (from recipe sales) vs actual stock usage"""
        recipes = await db.stock_recipes.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        products = {p["id"]: p for p in await db.stock_products.find({"property_id": property_id}, {"_id": 0}).to_list(500)}

        # Theoretical: sum ingredients * recipe sales count
        theoretical = {}
        for recipe in recipes:
            sales = await db.stock_movements.count_documents({"property_id": property_id, "reference": f"recipe_sale:{recipe['id']}"})
            if sales == 0:
                sales = max(1, recipe.get("total_sales", 0))
            for ing in recipe.get("ingredients", []):
                pid = ing.get("product_id", "")
                qty_per_sale = ing.get("quantity", 0)
                if pid not in theoretical:
                    theoretical[pid] = 0
                theoretical[pid] += qty_per_sale * sales

        # Actual: from usage movements
        usage_pipeline = [
            {"$match": {"property_id": property_id, "movement_type": "usage"}},
            {"$group": {"_id": "$product_id", "total": {"$sum": "$quantity"}}}
        ]
        actual_usage = {}
        async for doc in db.stock_movements.aggregate(usage_pipeline):
            actual_usage[doc["_id"]] = doc["total"]

        results = []
        for pid, prod in products.items():
            theo = round(theoretical.get(pid, 0), 2)
            act = round(actual_usage.get(pid, 0), 2)
            diff = round(act - theo, 2)
            diff_pct = round((diff / theo * 100) if theo > 0 else 0, 1)
            diff_cost = round(abs(diff) * prod.get("cost_price", 0), 2)
            flag = "ok"
            if diff_pct > 10:
                flag = "over_usage"
            elif diff_pct < -10:
                flag = "under_reported"
            results.append({
                "product_id": pid, "product_name": prod["name"],
                "theoretical": theo, "actual": act,
                "difference": diff, "difference_pct": diff_pct,
                "difference_cost": diff_cost, "flag": flag,
            })

        results.sort(key=lambda x: abs(x["difference_cost"]), reverse=True)
        flagged = [r for r in results if r["flag"] != "ok"]
        return {"products": results, "flagged_count": len(flagged), "total_variance_cost": round(sum(r["difference_cost"] for r in flagged), 2)}

    # === Suppliers ===

    @router.get("/stock/suppliers/{property_id}")
    async def list_suppliers(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.suppliers.find({"property_id": property_id}, {"_id": 0}).sort("name", 1).to_list(100)
        return docs

    @router.post("/stock/suppliers")
    async def create_supplier(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import Supplier
        s = Supplier(**data)
        doc = s.model_dump()
        await db.suppliers.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/stock/suppliers/{supplier_id}")
    async def update_supplier(supplier_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.suppliers.update_one({"id": supplier_id}, {"$set": updates})
        doc = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
        return doc

    # === Purchase Orders ===

    @router.get("/stock/purchase-orders/{property_id}")
    async def list_orders(property_id: str, status: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if status: query["status"] = status
        docs = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/stock/purchase-orders")
    async def create_order(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        from models import PurchaseOrder
        items = data.get("items", [])
        total = 0
        for item in items:
            item["total"] = round(item.get("quantity", 0) * item.get("unit_cost", 0), 2)
            total += item["total"]
        data["total_amount"] = round(total, 2)
        data["created_by"] = current_user.get("name", "Admin")
        po = PurchaseOrder(**data)
        doc = po.model_dump()
        await db.purchase_orders.insert_one(doc)
        doc.pop("_id", None)
        await log_sync(db, "stock", "internal", "success", f"PO created: £{total} for {data.get('supplier_name', '')}", doc["id"])
        return doc

    @router.put("/stock/purchase-orders/{order_id}/receive")
    async def receive_order(order_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Mark PO as received and auto-create stock purchase movements"""
        from models import StockMovement
        po = await db.purchase_orders.find_one({"id": order_id}, {"_id": 0})
        if not po:
            raise HTTPException(status_code=404, detail="Order not found")
        await db.purchase_orders.update_one({"id": order_id}, {"$set": {"status": "received", "received_date": datetime.now(timezone.utc).isoformat()}})

        for item in po.get("items", []):
            mv = StockMovement(
                property_id=po["property_id"], product_id=item.get("product_id", ""),
                product_name=item.get("product_name", ""), movement_type="purchase",
                quantity=item.get("quantity", 0), unit=item.get("unit", ""),
                cost=item.get("total", 0), reference=f"PO:{order_id}",
                recorded_by=current_user.get("name", "Staff"),
            )
            doc = mv.model_dump()
            await db.stock_movements.insert_one(doc)
            await db.stock_products.update_one({"id": item.get("product_id")}, {"$inc": {"current_stock": item.get("quantity", 0)}})

        await log_sync(db, "stock", "internal", "success", f"PO {order_id} received — {len(po.get('items', []))} items stocked", order_id)
        return {"status": "received", "items_stocked": len(po.get("items", []))}

    # === Stock Count Sheets ===

    @router.post("/stock/count-sheets")
    async def create_count_sheet(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Create a stock count sheet pre-populated with all products"""
        from models import StockCount
        property_id = data.get("property_id", "")
        products = await db.stock_products.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(500)
        items = []
        for p in products:
            items.append({
                "product_id": p["id"], "product_name": p["name"],
                "expected": p.get("current_stock", 0), "counted": None,
                "unit": p.get("unit", ""), "variance": 0, "variance_cost": 0,
            })
        sc = StockCount(
            property_id=property_id,
            name=data.get("name", f"Stock Count {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"),
            items=items, counted_by=current_user.get("name", "Staff"),
        )
        doc = sc.model_dump()
        await db.stock_counts.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/stock/count-sheets/{property_id}")
    async def list_count_sheets(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.stock_counts.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return docs

    @router.put("/stock/count-sheets/{sheet_id}")
    async def update_count_sheet(sheet_id: str, updates: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update counted values and calculate variances"""
        items = updates.get("items", [])
        total_variance_cost = 0
        for item in items:
            if item.get("counted") is not None:
                expected = item.get("expected", 0)
                counted = item["counted"]
                variance = counted - expected
                prod = await db.stock_products.find_one({"id": item["product_id"]}, {"_id": 0})
                cost_price = prod.get("cost_price", 0) if prod else 0
                item["variance"] = round(variance, 2)
                item["variance_cost"] = round(abs(variance) * cost_price, 2)
                total_variance_cost += item["variance_cost"]

        await db.stock_counts.update_one({"id": sheet_id}, {"$set": {
            "items": items, "total_variance_cost": round(total_variance_cost, 2)
        }})
        doc = await db.stock_counts.find_one({"id": sheet_id}, {"_id": 0})
        return doc

    @router.post("/stock/count-sheets/{sheet_id}/complete")
    async def complete_count_sheet(sheet_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Finalize count and update actual stock levels"""
        sheet = await db.stock_counts.find_one({"id": sheet_id}, {"_id": 0})
        if not sheet:
            raise HTTPException(status_code=404, detail="Count sheet not found")
        updated = 0
        for item in sheet.get("items", []):
            if item.get("counted") is not None:
                await db.stock_products.update_one({"id": item["product_id"]}, {"$set": {"current_stock": item["counted"]}})
                updated += 1
        await db.stock_counts.update_one({"id": sheet_id}, {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}})
        await log_sync(db, "stock", "internal", "success", f"Stock count completed — {updated} products updated, variance: £{sheet.get('total_variance_cost', 0)}", sheet_id)
        return {"status": "completed", "products_updated": updated, "total_variance_cost": sheet.get("total_variance_cost", 0)}

    # === COGS per Sale ===

    @router.post("/stock/record-sale")
    async def record_sale(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Record a recipe sale — auto-deducts ingredients from stock (COGS tracking)"""
        from models import StockMovement
        recipe_id = data.get("recipe_id", "")
        quantity = data.get("quantity", 1)
        recipe = await db.stock_recipes.find_one({"id": recipe_id}, {"_id": 0})
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")

        total_cogs = 0
        for ing in recipe.get("ingredients", []):
            prod = await db.stock_products.find_one({"id": ing.get("product_id")}, {"_id": 0})
            if not prod:
                continue
            usage_qty = ing.get("quantity", 0) * quantity
            cost = round(prod.get("cost_price", 0) * usage_qty, 2)
            total_cogs += cost

            mv = StockMovement(
                property_id=recipe.get("property_id", ""), product_id=ing["product_id"],
                product_name=prod["name"], movement_type="usage", quantity=usage_qty,
                unit=prod.get("unit", ""), cost=cost, outlet=recipe.get("outlet", ""),
                reference=f"recipe_sale:{recipe_id}", recorded_by="POS",
            )
            doc = mv.model_dump()
            await db.stock_movements.insert_one(doc)
            await db.stock_products.update_one({"id": ing["product_id"]}, {"$inc": {"current_stock": -usage_qty}})

        revenue = recipe.get("sell_price", 0) * quantity
        return {
            "recipe": recipe["name"], "quantity": quantity,
            "cogs": round(total_cogs, 2), "revenue": revenue,
            "gross_profit": round(revenue - total_cogs, 2),
            "margin_pct": round(((revenue - total_cogs) / revenue * 100) if revenue > 0 else 0, 1),
        }

    # === 1. MENU ENGINEERING (Stars/Puzzles/Plowhorses/Dogs) ===

    @router.get("/stock/menu-engineering/{property_id}")
    async def menu_engineering(property_id: str, outlet: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Profitability matrix: classify recipes as Star/Puzzle/Plowhorse/Dog"""
        query = {"property_id": property_id, "is_active": True}
        if outlet: query["outlet"] = outlet
        recipes = await db.stock_recipes.find(query, {"_id": 0}).to_list(200)
        if not recipes:
            return {"recipes": [], "summary": {}}

        avg_margin = sum(r.get("margin_pct", 0) for r in recipes) / len(recipes) if recipes else 0
        avg_sales = sum(r.get("total_sales", 0) for r in recipes) / len(recipes) if recipes else 0

        classified = []
        for r in recipes:
            margin = r.get("margin_pct", 0)
            sales = r.get("total_sales", 0)
            high_margin = margin >= avg_margin
            high_sales = sales >= avg_sales
            if high_margin and high_sales:
                menu_class = "star"
            elif high_margin and not high_sales:
                menu_class = "puzzle"
            elif not high_margin and high_sales:
                menu_class = "plowhorse"
            else:
                menu_class = "dog"
            r["menu_class"] = menu_class
            r["contribution"] = round(r.get("sell_price", 0) - r.get("total_cost", 0), 2)
            classified.append(r)
            await db.stock_recipes.update_one({"id": r["id"]}, {"$set": {"menu_class": menu_class}})

        stars = [r for r in classified if r["menu_class"] == "star"]
        puzzles = [r for r in classified if r["menu_class"] == "puzzle"]
        plowhorses = [r for r in classified if r["menu_class"] == "plowhorse"]
        dogs = [r for r in classified if r["menu_class"] == "dog"]

        return {
            "recipes": classified,
            "summary": {
                "stars": len(stars), "puzzles": len(puzzles),
                "plowhorses": len(plowhorses), "dogs": len(dogs),
                "avg_margin": round(avg_margin, 1), "avg_sales": round(avg_sales, 1),
            },
            "recommendations": {
                "promote": [r["name"] for r in puzzles[:3]],
                "reprice": [r["name"] for r in plowhorses[:3]],
                "remove_or_rework": [r["name"] for r in dogs[:3]],
            }
        }

    # === 2. FOOD COST % DASHBOARD ===

    @router.get("/stock/food-cost-dashboard/{property_id}")
    async def food_cost_dashboard(property_id: str, days: int = 30,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Real-time food cost % with COGS formula and per-outlet breakdown"""
        cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=days)).isoformat()

        # Beginning inventory value
        begin_pipeline = [
            {"$match": {"property_id": property_id, "is_active": True}},
            {"$group": {"_id": None, "value": {"$sum": {"$multiply": ["$current_stock", "$cost_price"]}}}}
        ]
        begin_inv = 0
        async for doc in db.stock_products.aggregate(begin_pipeline):
            begin_inv = round(doc["value"], 2)

        # Purchases in period
        purch_pipeline = [
            {"$match": {"property_id": property_id, "movement_type": "purchase", "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total": {"$sum": "$cost"}}}
        ]
        purchases = 0
        async for doc in db.stock_movements.aggregate(purch_pipeline):
            purchases = round(doc["total"], 2)

        # Ending inventory = current stock value
        ending_inv = begin_inv  # simplified: current stock IS ending

        # COGS = Beginning + Purchases - Ending
        cogs = round(begin_inv + purchases - ending_inv, 2)
        # Simplified: COGS ≈ purchases (for period-based)
        cogs = purchases

        # Food sales from recipe sales
        sales_pipeline = [
            {"$match": {"property_id": property_id, "movement_type": "usage", "reference": {"$regex": "^recipe_sale:"}, "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total_cost": {"$sum": "$cost"}}}
        ]
        recipe_cogs = 0
        async for doc in db.stock_movements.aggregate(sales_pipeline):
            recipe_cogs = round(doc["total_cost"], 2)

        # Estimate revenue from recipes
        total_fb_revenue = 0
        recipes = await db.stock_recipes.find({"property_id": property_id}, {"_id": 0, "total_sales": 1, "sell_price": 1}).to_list(200)
        for r in recipes:
            total_fb_revenue += (r.get("total_sales", 0) or 0) * (r.get("sell_price", 0) or 0)

        # Also check booking F&B income
        fb_income_pipeline = [
            {"$match": {"property_id": property_id, "category": "food_beverage", "date": {"$gte": cutoff[:10]}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        async for doc in db.income_entries.aggregate(fb_income_pipeline):
            total_fb_revenue += round(doc["total"], 2)

        food_cost_pct = round((cogs / total_fb_revenue * 100) if total_fb_revenue > 0 else 0, 1)

        # Per-outlet breakdown
        outlet_pipeline = [
            {"$match": {"property_id": property_id, "movement_type": {"$in": ["usage", "waste"]}, "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": "$outlet", "cost": {"$sum": "$cost"}, "count": {"$sum": 1}}}
        ]
        by_outlet = {}
        async for doc in db.stock_movements.aggregate(outlet_pipeline):
            by_outlet[doc["_id"] or "unassigned"] = {"cost": round(doc["cost"], 2), "movements": doc["count"]}

        target_min, target_max = 28, 35
        status = "on_target" if target_min <= food_cost_pct <= target_max else ("high" if food_cost_pct > target_max else "low")

        return {
            "food_cost_pct": food_cost_pct,
            "target_range": {"min": target_min, "max": target_max},
            "status": status,
            "cogs": cogs, "revenue": round(total_fb_revenue, 2),
            "beginning_inventory": begin_inv, "purchases": purchases, "ending_inventory": ending_inv,
            "by_outlet": by_outlet,
            "period_days": days,
        }

    # === 3. PAR LEVEL AUTO-ORDERING ===

    @router.post("/stock/auto-order/{property_id}")
    async def generate_auto_orders(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Auto-generate purchase orders for products below par level"""
        from models import PurchaseOrder
        products = await db.stock_products.find(
            {"property_id": property_id, "is_active": True, "par_level": {"$gt": 0}},
            {"_id": 0}
        ).to_list(500)

        # Group by supplier
        by_supplier = {}
        for p in products:
            if p["current_stock"] < p["par_level"]:
                supplier = p.get("supplier_id") or p.get("supplier", "unknown")
                supplier_name = p.get("supplier", "Unknown Supplier")
                if supplier not in by_supplier:
                    by_supplier[supplier] = {"name": supplier_name, "items": []}
                order_qty = round(p["par_level"] - p["current_stock"], 2)
                by_supplier[supplier]["items"].append({
                    "product_id": p["id"], "product_name": p["name"],
                    "quantity": order_qty, "unit": p.get("unit", ""),
                    "unit_cost": p.get("cost_price", 0),
                    "total": round(order_qty * p.get("cost_price", 0), 2),
                })

        created_pos = []
        for supplier_id, data in by_supplier.items():
            total = round(sum(i["total"] for i in data["items"]), 2)
            po = PurchaseOrder(
                property_id=property_id, supplier_id=supplier_id,
                supplier_name=data["name"], status="draft",
                items=data["items"], total_amount=total,
                order_date=datetime.now(timezone.utc).isoformat()[:10],
                created_by=current_user.get("name", "Auto"),
                notes="Auto-generated from par levels",
            )
            doc = po.model_dump()
            await db.purchase_orders.insert_one(doc)
            doc.pop("_id", None)
            created_pos.append({"supplier": data["name"], "items": len(data["items"]), "total": total, "id": doc["id"]})

        if created_pos:
            await log_sync(db, "stock", "internal", "success", f"Auto-order: {len(created_pos)} POs generated", property_id)
            asyncio.create_task(fire_webhooks(db, "stock.auto_order", {"property_id": property_id, "orders": len(created_pos)}))

        return {"message": f"{len(created_pos)} purchase orders generated", "orders": created_pos}

    # === 4. ALLERGEN & NUTRITION TRACKING ===

    @router.get("/stock/allergens/{property_id}")
    async def allergen_report(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """List all recipes with their allergen flags"""
        recipes = await db.stock_recipes.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(200)
        result = []
        for r in recipes:
            allergens = set(r.get("allergens", []))
            for ing in r.get("ingredients", []):
                prod = await db.stock_products.find_one({"id": ing.get("product_id")}, {"_id": 0, "allergens": 1})
                if prod:
                    allergens.update(prod.get("allergens", []))
            result.append({
                "recipe_id": r["id"], "name": r["name"], "outlet": r.get("outlet", ""),
                "allergens": sorted(list(allergens)),
                "nutrition": r.get("nutrition", {}),
            })
        return result

    # === 5. SUPPLIER PRICE HISTORY ===

    @router.get("/stock/price-history/{product_id}")
    async def price_history(product_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        prod = await db.stock_products.find_one({"id": product_id}, {"_id": 0})
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")
        # Also get from purchase movements
        pipeline = [
            {"$match": {"product_id": product_id, "movement_type": "purchase", "cost": {"$gt": 0}}},
            {"$project": {"_id": 0, "date": "$created_at", "cost": 1, "quantity": 1, "reference": 1}},
            {"$sort": {"date": -1}},
            {"$limit": 50}
        ]
        purchase_prices = []
        async for doc in db.stock_movements.aggregate(pipeline):
            unit_cost = round(doc["cost"] / doc["quantity"], 2) if doc.get("quantity", 0) > 0 else 0
            purchase_prices.append({"date": doc["date"][:10], "unit_cost": unit_cost, "reference": doc.get("reference", "")})

        return {
            "product": prod["name"], "current_price": prod.get("cost_price", 0),
            "price_history": prod.get("price_history", []),
            "purchase_prices": purchase_prices,
        }

    @router.post("/stock/price-update/{product_id}")
    async def update_price(product_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update product price and log history"""
        new_price = data.get("cost_price", 0)
        prod = await db.stock_products.find_one({"id": product_id}, {"_id": 0})
        if not prod:
            raise HTTPException(status_code=404, detail="Product not found")
        old_price = prod.get("cost_price", 0)
        history_entry = {"date": datetime.now(timezone.utc).isoformat()[:10], "price": new_price, "old_price": old_price, "supplier": data.get("supplier", "")}
        await db.stock_products.update_one({"id": product_id}, {
            "$set": {"cost_price": new_price},
            "$push": {"price_history": history_entry}
        })
        pct_change = round(((new_price - old_price) / old_price * 100) if old_price > 0 else 0, 1)
        await log_sync(db, "stock", "internal", "info", f"Price update: {prod['name']} £{old_price} → £{new_price} ({pct_change}%)", product_id)
        return {"product": prod["name"], "old_price": old_price, "new_price": new_price, "change_pct": pct_change}

    # === 6. YIELD MANAGEMENT ===

    @router.get("/stock/yield-analysis/{property_id}")
    async def yield_analysis(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Analyze ingredient yields — raw vs usable quantities"""
        products = await db.stock_products.find(
            {"property_id": property_id, "is_active": True, "yield_pct": {"$lt": 100, "$gt": 0}},
            {"_id": 0}
        ).to_list(200)
        result = []
        for p in products:
            yield_pct = p.get("yield_pct", 100)
            raw_cost = p.get("cost_price", 0)
            effective_cost = round(raw_cost / (yield_pct / 100), 2) if yield_pct > 0 else raw_cost
            waste_pct = round(100 - yield_pct, 1)
            result.append({
                "product_id": p["id"], "name": p["name"], "unit": p.get("unit", ""),
                "raw_cost_per_unit": raw_cost, "yield_pct": yield_pct,
                "effective_cost_per_unit": effective_cost,
                "waste_pct": waste_pct,
                "cost_increase": round(effective_cost - raw_cost, 2),
            })
        result.sort(key=lambda x: x["cost_increase"], reverse=True)
        return result

    # === 7. PERISHABLE FORECASTING (FIFO / Expiry) ===

    @router.get("/stock/perishable-alerts/{property_id}")
    async def perishable_alerts(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Track expiry dates and FIFO alerts for perishable items"""
        products = await db.stock_products.find(
            {"property_id": property_id, "is_active": True, "expiry_days": {"$gt": 0}},
            {"_id": 0}
        ).to_list(200)

        alerts = []
        for p in products:
            # Get last purchase date
            last_purchase = await db.stock_movements.find_one(
                {"product_id": p["id"], "movement_type": "purchase"},
                {"_id": 0, "created_at": 1},
                sort=[("created_at", -1)]
            )
            if last_purchase:
                try:
                    purchase_date = datetime.fromisoformat(last_purchase["created_at"].replace("Z", "+00:00"))
                    expiry_date = purchase_date + __import__('datetime').timedelta(days=p["expiry_days"])
                    days_left = (expiry_date - datetime.now(timezone.utc)).days
                    status = "expired" if days_left < 0 else ("critical" if days_left <= 2 else ("warning" if days_left <= 5 else "ok"))
                    if status != "ok":
                        alerts.append({
                            "product_id": p["id"], "name": p["name"],
                            "shelf_life_days": p["expiry_days"],
                            "last_purchased": last_purchase["created_at"][:10],
                            "estimated_expiry": expiry_date.isoformat()[:10],
                            "days_remaining": days_left,
                            "current_stock": p["current_stock"], "unit": p.get("unit", ""),
                            "stock_value": round(p["current_stock"] * p.get("cost_price", 0), 2),
                            "status": status, "storage": p.get("storage_temp", ""),
                        })
                except (ValueError, TypeError):
                    pass

        alerts.sort(key=lambda x: x["days_remaining"])
        total_at_risk = round(sum(a["stock_value"] for a in alerts), 2)
        return {"alerts": alerts, "total_at_risk_value": total_at_risk, "count": len(alerts)}

    # === 8. MULTI-OUTLET TRANSFERS ===

    @router.post("/stock/transfer")
    async def transfer_stock(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Transfer stock between outlets with full tracking"""
        from models import StockMovement
        product_id = data.get("product_id", "")
        from_outlet = data.get("from_outlet", "")
        to_outlet = data.get("to_outlet", "")
        quantity = abs(data.get("quantity", 0))
        property_id = data.get("property_id", "")

        product = await db.stock_products.find_one({"id": product_id}, {"_id": 0})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        cost = round(product.get("cost_price", 0) * quantity, 2)

        # Out from source
        mv_out = StockMovement(
            property_id=property_id, product_id=product_id, product_name=product["name"],
            movement_type="transfer_out", quantity=quantity, unit=product.get("unit", ""),
            cost=cost, outlet=from_outlet, from_outlet=from_outlet, to_outlet=to_outlet,
            reference=f"transfer:{from_outlet}→{to_outlet}",
            recorded_by=current_user.get("name", "Staff"),
        )
        d1 = mv_out.model_dump()
        await db.stock_movements.insert_one(d1)

        # In to destination
        mv_in = StockMovement(
            property_id=property_id, product_id=product_id, product_name=product["name"],
            movement_type="transfer_in", quantity=quantity, unit=product.get("unit", ""),
            cost=cost, outlet=to_outlet, from_outlet=from_outlet, to_outlet=to_outlet,
            reference=f"transfer:{from_outlet}→{to_outlet}",
            recorded_by=current_user.get("name", "Staff"),
        )
        d2 = mv_in.model_dump()
        await db.stock_movements.insert_one(d2)

        await log_sync(db, "stock", "internal", "success", f"Transfer: {product['name']} x{quantity} {from_outlet} → {to_outlet}", f"{d1['id']},{d2['id']}")
        asyncio.create_task(fire_webhooks(db, "stock.transfer", {"product": product["name"], "quantity": quantity, "from": from_outlet, "to": to_outlet}))

        return {"status": "transferred", "product": product["name"], "quantity": quantity, "from": from_outlet, "to": to_outlet, "cost": cost}

    # === 9. INVENTORY TURNOVER RATE ===

    @router.get("/stock/turnover-rate/{property_id}")
    async def inventory_turnover(property_id: str, days: int = 30,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Calculate inventory turnover rate (target: 4-8x monthly)"""
        cutoff = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=days)).isoformat()

        # COGS in period (usage + waste)
        cogs_pipeline = [
            {"$match": {"property_id": property_id, "movement_type": {"$in": ["usage", "waste"]}, "created_at": {"$gte": cutoff}}},
            {"$group": {"_id": None, "total": {"$sum": "$cost"}}}
        ]
        cogs = 0
        async for doc in db.stock_movements.aggregate(cogs_pipeline):
            cogs = round(doc["total"], 2)

        # Average inventory value
        inv_pipeline = [
            {"$match": {"property_id": property_id, "is_active": True}},
            {"$group": {"_id": None, "value": {"$sum": {"$multiply": ["$current_stock", "$cost_price"]}}}}
        ]
        avg_inv = 0
        async for doc in db.stock_products.aggregate(inv_pipeline):
            avg_inv = round(doc["value"], 2)

        turnover = round(cogs / avg_inv, 2) if avg_inv > 0 else 0
        # Annualize
        monthly_turnover = round(turnover * (30 / days), 2)

        status = "optimal" if 4 <= monthly_turnover <= 8 else ("slow" if monthly_turnover < 4 else "fast")

        # Per-product turnover
        product_turnovers = []
        products = await db.stock_products.find({"property_id": property_id, "is_active": True}, {"_id": 0}).to_list(200)
        for p in products:
            prod_cogs_pipeline = [
                {"$match": {"product_id": p["id"], "movement_type": {"$in": ["usage", "waste"]}, "created_at": {"$gte": cutoff}}},
                {"$group": {"_id": None, "total": {"$sum": "$cost"}}}
            ]
            prod_cogs = 0
            async for doc in db.stock_movements.aggregate(prod_cogs_pipeline):
                prod_cogs = round(doc["total"], 2)
            prod_value = round(p.get("current_stock", 0) * p.get("cost_price", 0), 2)
            prod_turnover = round(prod_cogs / prod_value, 2) if prod_value > 0 else 0
            if prod_value > 0:
                product_turnovers.append({
                    "product": p["name"], "turnover": prod_turnover,
                    "stock_value": prod_value, "cogs": prod_cogs,
                    "status": "optimal" if 4 <= prod_turnover * (30 / days) <= 8 else ("slow" if prod_turnover * (30 / days) < 4 else "fast"),
                })

        product_turnovers.sort(key=lambda x: x["turnover"])
        slow_movers = [p for p in product_turnovers if p["status"] == "slow"]

        return {
            "turnover_rate": turnover,
            "monthly_turnover": monthly_turnover,
            "target": {"min": 4, "max": 8},
            "status": status,
            "cogs": cogs, "avg_inventory_value": avg_inv,
            "period_days": days,
            "products": product_turnovers[:20],
            "slow_movers_count": len(slow_movers),
            "slow_movers_value": round(sum(p["stock_value"] for p in slow_movers), 2),
        }

    return router
