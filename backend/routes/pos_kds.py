"""
Kitchen Display System (KDS) + 86-List + Recipe-based Inventory Deduction.

KDS: Live kitchen stream of orders with station routing (hot/cold/bar/grill),
age timers (green < 5min, amber 5-10, red > 10), bump to next station workflow.

86 list: Quick out-of-stock toggle. Items on 86 are auto-hidden from menu display
endpoints and hard-fail on order create.

Recipe inventory: Each menu item can reference stock_items with qty-per-portion.
On order pay (or kitchen bump depending on kitchen_type_config), deduct stock
atomically and flag any that drop below reorder_threshold.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel
import uuid
import logging

logger = logging.getLogger(__name__)


class Recipe(BaseModel):
    menu_item_id: str
    components: List[Dict]  # [{stock_item_id, qty, unit}]


class EightySixToggle(BaseModel):
    menu_item_id: str
    on_86: bool
    reason: Optional[str] = ""


class KdsBumpRequest(BaseModel):
    order_id: str
    next_status: str  # 'preparing' | 'ready' | 'served'
    station: Optional[str] = None  # which station bumped it


def _age_minutes(created_at_iso: str) -> float:
    try:
        dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60
    except Exception:
        return 0


def _age_color(mins: float) -> str:
    if mins < 5:
        return "green"
    if mins < 10:
        return "amber"
    return "red"


def create_pos_kds_router(db, require_roles):
    router = APIRouter()

    # ---- Kitchen Display Stream ----

    @router.get("/kds/{property_id}")
    async def kds_stream(property_id: str, station: Optional[str] = None,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "kitchen", "bar"))):
        """Live KDS — ALL orders in kitchen queue grouped by age + status."""
        q = {
            "property_id": property_id,
            "kitchen_status": {"$in": ["new", "preparing", "ready"]},
        }
        if station:
            q["station"] = station
        orders = await db.pos_orders.find(q, {"_id": 0}).sort("created_at", 1).to_list(200)

        # Hydrate line items with pos_menu_items info (for station + name)
        for o in orders:
            for item in (o.get("items") or []):
                mi = await db.pos_menu_items.find_one(
                    {"id": item.get("menu_item_id")}, {"_id": 0}
                ) or {}
                item["_name"] = item.get("name") or mi.get("name") or "Item"
                item["_station"] = mi.get("station", "hot")
            age = _age_minutes(o.get("created_at", ""))
            o["age_minutes"] = round(age, 1)
            o["age_color"] = _age_color(age)

        # Group by station if no filter
        by_station = {}
        for o in orders:
            for item in (o.get("items") or []):
                s = item.get("_station", "hot")
                by_station.setdefault(s, []).append({
                    "order_id": o.get("id"),
                    "order_number": o.get("order_number") or o.get("id", "")[:6],
                    "table": o.get("table_number"),
                    "item_id": item.get("id") or item.get("menu_item_id"),
                    "name": item.get("_name"),
                    "qty": item.get("qty") or item.get("quantity") or 1,
                    "notes": item.get("notes"),
                    "age_minutes": o["age_minutes"],
                    "age_color": o["age_color"],
                    "status": o.get("kitchen_status", "new"),
                })

        # Aggregate counters
        counters = {"new": 0, "preparing": 0, "ready": 0}
        for o in orders:
            st = o.get("kitchen_status", "new")
            if st in counters:
                counters[st] += 1

        return {
            "orders": orders,
            "by_station": by_station,
            "counters": counters,
            "oldest_age_minutes": max([o.get("age_minutes", 0) for o in orders], default=0),
        }

    @router.post("/kds/bump")
    async def kds_bump(req: KdsBumpRequest,
                       current_user: dict = Depends(require_roles("admin", "manager", "kitchen", "bar"))):
        """Advance order status. new → preparing → ready → served."""
        valid = ["new", "preparing", "ready", "served", "voided"]
        if req.next_status not in valid:
            raise HTTPException(400, f"Invalid status. Must be one of {valid}")
        order = await db.pos_orders.find_one({"id": req.order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Order not found")

        now = datetime.now(timezone.utc).isoformat()
        update = {
            "kitchen_status": req.next_status,
            f"{req.next_status}_at": now,
            f"{req.next_status}_by": current_user.get("email"),
        }
        if req.station:
            update["last_bumped_station"] = req.station

        # Deduct stock on "preparing" (recipes trigger here by default)
        deductions = []
        if req.next_status == "preparing" and not order.get("recipe_deducted_at"):
            for item in (order.get("items") or []):
                recipe = await db.recipes.find_one(
                    {"menu_item_id": item.get("menu_item_id")}, {"_id": 0}
                )
                if not recipe:
                    continue
                qty = item.get("qty") or item.get("quantity") or 1
                for comp in (recipe.get("components") or []):
                    stock_id = comp.get("stock_item_id")
                    use = float(comp.get("qty") or 0) * qty
                    if use <= 0 or not stock_id:
                        continue
                    # Try stock_items first, fallback inventory_items
                    for coll in ("stock_items", "inventory_items", "pos_inventory"):
                        result = await db[coll].update_one(
                            {"id": stock_id},
                            {"$inc": {"qty_on_hand": -use, "quantity": -use}}
                        )
                        if result.matched_count:
                            deductions.append({
                                "stock_item_id": stock_id,
                                "used": use,
                                "unit": comp.get("unit"),
                            })
                            # Check threshold
                            s = await db[coll].find_one({"id": stock_id}, {"_id": 0})
                            on_hand = s.get("qty_on_hand") if s else None
                            if on_hand is None:
                                on_hand = s.get("quantity") if s else 0
                            threshold = (s or {}).get("reorder_threshold", 0)
                            if on_hand is not None and threshold and on_hand <= threshold:
                                await db.inventory_alerts.insert_one({
                                    "id": str(uuid.uuid4()),
                                    "stock_item_id": stock_id,
                                    "property_id": order.get("property_id"),
                                    "on_hand": on_hand,
                                    "threshold": threshold,
                                    "triggered_at": now,
                                    "source": "recipe_deduction",
                                })
                            break
            if deductions:
                update["recipe_deducted_at"] = now
                update["recipe_deductions"] = deductions

        await db.pos_orders.update_one({"id": req.order_id}, {"$set": update})

        return {
            "order_id": req.order_id,
            "status": req.next_status,
            "deductions": deductions,
        }

    # ---- 86 List ----

    @router.get("/86-list/{property_id}")
    async def get_86_list(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "kitchen", "bar"))):
        """All items currently flagged out of stock."""
        rows = await db.pos_menu_items.find(
            {"property_id": property_id, "on_86": True},
            {"_id": 0}
        ).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/86-list/toggle")
    async def toggle_86(req: EightySixToggle,
                        current_user: dict = Depends(require_roles("admin", "manager", "kitchen", "bar"))):
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "on_86": req.on_86,
            "on_86_at": now if req.on_86 else None,
            "on_86_reason": req.reason if req.on_86 else None,
        }
        r = await db.pos_menu_items.update_one({"id": req.menu_item_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Menu item not found")
        await db.pos_86_log.insert_one({
            "id": str(uuid.uuid4()),
            "menu_item_id": req.menu_item_id,
            "on_86": req.on_86,
            "reason": req.reason,
            "by_user": current_user.get("email"),
            "at": now,
        })
        return {"menu_item_id": req.menu_item_id, "on_86": req.on_86}

    # ---- Recipes ----

    @router.get("/recipes/{menu_item_id}")
    async def get_recipe(menu_item_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "kitchen"))):
        r = await db.recipes.find_one({"menu_item_id": menu_item_id}, {"_id": 0})
        return r or {"menu_item_id": menu_item_id, "components": []}

    @router.post("/recipes")
    async def upsert_recipe(recipe: Recipe,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = recipe.dict()
        doc["updated_at"] = now
        doc["updated_by"] = current_user.get("email")
        await db.recipes.update_one(
            {"menu_item_id": recipe.menu_item_id},
            {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
            upsert=True,
        )
        return {"menu_item_id": recipe.menu_item_id, "component_count": len(recipe.components)}

    @router.get("/recipes/property/{property_id}")
    async def list_recipes(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        # Join pos_menu_items + recipes
        menu_items = await db.pos_menu_items.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(500)
        recipes = await db.recipes.find({}, {"_id": 0}).to_list(500)
        by_mi = {r["menu_item_id"]: r for r in recipes}
        rows = []
        for mi in menu_items:
            r = by_mi.get(mi["id"])
            rows.append({
                "menu_item_id": mi["id"],
                "menu_item_name": mi.get("name"),
                "price": mi.get("price"),
                "on_86": mi.get("on_86", False),
                "has_recipe": bool(r),
                "component_count": len(r.get("components", [])) if r else 0,
            })
        return {"rows": rows, "total": len(rows), "with_recipe": sum(1 for r in rows if r["has_recipe"])}

    return router
