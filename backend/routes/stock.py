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

    return router
