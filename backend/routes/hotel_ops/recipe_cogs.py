"""
F&B Recipe COGS + Modifier Trees
================================

Per-menu-item recipe with ingredient tree, sub-recipes (e.g. "house dressing"
re-used across salads), and modifier groups (size, sauce, extras). Calculates
plate-level COGS, target margin, suggested sell price, and exposes weekly
inventory consumption forecasts.

Endpoints
---------
GET    /recipes/{property_id}                 list recipes
POST   /recipes/{property_id}                 create
GET    /recipes/{property_id}/{recipe_id}     get one
PUT    /recipes/{property_id}/{recipe_id}     update
DELETE /recipes/{property_id}/{recipe_id}     delete
POST   /recipes/{property_id}/{recipe_id}/cogs   recompute COGS

GET    /ingredients/{property_id}             list ingredients
POST   /ingredients/{property_id}             create
PUT    /ingredients/{property_id}/{id}        update
DELETE /ingredients/{property_id}/{id}        delete

GET    /modifier-groups/{property_id}         list modifier groups
POST   /modifier-groups/{property_id}         create
PUT    /modifier-groups/{property_id}/{id}    update
DELETE /modifier-groups/{property_id}/{id}    delete

GET    /recipes/{property_id}/dashboard       summary KPIs
POST   /recipes/{property_id}/forecast-week   weekly ingredient forecast (uses
                                              past 14d POS volume × recipes)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class Ingredient(BaseModel):
    name: str
    unit: str = "g"           # g | ml | piece | l | kg
    cost_per_unit: float = 0  # in property currency
    supplier: Optional[str] = None
    pack_size: Optional[float] = None  # e.g. 500 for "500g pack"
    pack_price: Optional[float] = None
    waste_pct: float = 0      # 0-30 (% loss in trim/prep)
    allergens: List[str] = []


class RecipeLine(BaseModel):
    """One ingredient OR one sub-recipe at one quantity."""
    ingredient_id: Optional[str] = None
    sub_recipe_id: Optional[str] = None
    qty: float
    unit: str = "g"
    note: Optional[str] = None


class ModifierOption(BaseModel):
    name: str
    extra_price: float = 0
    extra_cost: float = 0   # cost delta added to COGS if selected


class ModifierGroup(BaseModel):
    name: str
    required: bool = False
    min_select: int = 0
    max_select: int = 1
    options: List[ModifierOption] = []


class Recipe(BaseModel):
    name: str
    category: Optional[str] = None       # Starters | Mains | Desserts | Drinks ...
    yields: int = 1                      # how many plates per batch
    sell_price: float = 0
    target_margin_pct: float = 70.0
    lines: List[RecipeLine] = []
    modifier_group_ids: List[str] = []
    pos_menu_item_id: Optional[str] = None  # link to existing POS item
    notes: Optional[str] = None
    image_url: Optional[str] = None


# ---------------------------------------------------------------------------
# math
# ---------------------------------------------------------------------------
def _line_cost(line: dict, ingredients: dict, recipes: dict, depth: int = 0) -> float:
    """Recursively compute the cost of a single recipe line.
    `ingredients` and `recipes` are id→doc dicts.
    """
    if depth > 6:
        # Defensive: deny absurd recursion (circular sub-recipe).
        return 0.0
    qty = float(line.get("qty") or 0)
    if line.get("ingredient_id"):
        ing = ingredients.get(line["ingredient_id"]) or {}
        cpu = float(ing.get("cost_per_unit") or 0)
        waste = float(ing.get("waste_pct") or 0) / 100.0
        return round(qty * cpu * (1 + waste), 4)
    if line.get("sub_recipe_id"):
        sub = recipes.get(line["sub_recipe_id"]) or {}
        sub_cost = sum(_line_cost(line, ingredients, recipes, depth + 1)
                       for line in (sub.get("lines") or []))
        sub_yield = max(1, int(sub.get("yields") or 1))
        return round((sub_cost / sub_yield) * qty, 4)
    return 0.0


def _compute_cogs(recipe: dict, ingredients: dict, recipes: dict) -> dict:
    base_cost = sum(_line_cost(line, ingredients, recipes) for line in (recipe.get("lines") or []))
    yields = max(1, int(recipe.get("yields") or 1))
    cogs_per_plate = round(base_cost / yields, 4)
    sell = float(recipe.get("sell_price") or 0)
    margin = (sell - cogs_per_plate) / sell * 100.0 if sell > 0 else 0
    target_pct = float(recipe.get("target_margin_pct") or 70.0)
    suggested_sell = round(cogs_per_plate / max(0.0001, 1 - target_pct / 100), 2) if cogs_per_plate else sell
    return {
        "cogs_per_plate": cogs_per_plate,
        "batch_cost": round(base_cost, 4),
        "current_margin_pct": round(margin, 2),
        "target_margin_pct": target_pct,
        "suggested_sell_price": suggested_sell,
        "delta_vs_target": round(target_pct - margin, 2),
        "needs_repricing": (margin < target_pct - 5) and sell > 0,
    }


# ---------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------
def create_recipe_cogs_router(db, require_roles):
    router = APIRouter()

    # ---- ingredients ----
    @router.get("/ingredients/{property_id}")
    async def list_ingredients(property_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        items = await db.fnb_ingredients.find({"property_id": property_id}, {"_id": 0}).to_list(2000)
        return {"items": items, "count": len(items)}

    @router.post("/ingredients/{property_id}")
    async def add_ingredient(property_id: str, ing: Ingredient,
                             current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        doc = {**ing.model_dump(), "id": str(uuid.uuid4()), "property_id": property_id, "created_at": _now()}
        await db.fnb_ingredients.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/ingredients/{property_id}/{ing_id}")
    async def edit_ingredient(property_id: str, ing_id: str, ing: Ingredient,
                              current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        await db.fnb_ingredients.update_one(
            {"id": ing_id, "property_id": property_id},
            {"$set": {**ing.model_dump(), "updated_at": _now()}}
        )
        doc = await db.fnb_ingredients.find_one({"id": ing_id, "property_id": property_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @router.delete("/ingredients/{property_id}/{ing_id}")
    async def delete_ingredient(property_id: str, ing_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.fnb_ingredients.delete_one({"id": ing_id, "property_id": property_id})
        return {"deleted": r.deleted_count}

    # ---- modifier groups ----
    @router.get("/modifier-groups/{property_id}")
    async def list_groups(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        items = await db.fnb_modifier_groups.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        return {"items": items, "count": len(items)}

    @router.post("/modifier-groups/{property_id}")
    async def add_group(property_id: str, mg: ModifierGroup,
                        current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        doc = {**mg.model_dump(), "id": str(uuid.uuid4()), "property_id": property_id, "created_at": _now()}
        await db.fnb_modifier_groups.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/modifier-groups/{property_id}/{gid}")
    async def edit_group(property_id: str, gid: str, mg: ModifierGroup,
                         current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        await db.fnb_modifier_groups.update_one(
            {"id": gid, "property_id": property_id},
            {"$set": {**mg.model_dump(), "updated_at": _now()}}
        )
        doc = await db.fnb_modifier_groups.find_one({"id": gid, "property_id": property_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @router.delete("/modifier-groups/{property_id}/{gid}")
    async def delete_group(property_id: str, gid: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.fnb_modifier_groups.delete_one({"id": gid, "property_id": property_id})
        return {"deleted": r.deleted_count}

    # ---- recipes ----
    async def _id_maps(property_id: str):
        ing_list = await db.fnb_ingredients.find({"property_id": property_id}, {"_id": 0}).to_list(2000)
        rec_list = await db.fnb_recipes.find({"property_id": property_id}, {"_id": 0}).to_list(2000)
        ingredients = {i["id"]: i for i in ing_list}
        recipes = {r["id"]: r for r in rec_list}
        return ingredients, recipes, ing_list, rec_list

    @router.get("/recipes/{property_id}")
    async def list_recipes(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        ingredients, recipes, _, rec_list = await _id_maps(property_id)
        for r in rec_list:
            r["cogs"] = _compute_cogs(r, ingredients, recipes)
        return {"items": rec_list, "count": len(rec_list)}

    @router.post("/recipes/{property_id}")
    async def create_recipe(property_id: str, recipe: Recipe,
                            current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        doc = {**recipe.model_dump(), "id": str(uuid.uuid4()),
               "property_id": property_id, "created_at": _now(), "created_by": current_user.get("email")}
        await db.fnb_recipes.insert_one(dict(doc))
        ingredients, recipes, *_ = await _id_maps(property_id)
        doc["cogs"] = _compute_cogs(doc, ingredients, recipes)
        doc.pop("_id", None)
        return doc

    @router.get("/recipes/{property_id}/dashboard")
    async def dashboard(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        ingredients, recipes, ing_list, rec_list = await _id_maps(property_id)
        for r in rec_list:
            r["cogs"] = _compute_cogs(r, ingredients, recipes)
        if not rec_list:
            return {
                "recipe_count": 0, "ingredient_count": len(ing_list),
                "avg_margin_pct": 0, "items_below_target": 0,
                "underperformers": [], "top_margin": [],
            }
        margins = [r["cogs"]["current_margin_pct"] for r in rec_list if r.get("sell_price")]
        underperformers = sorted(
            [r for r in rec_list if r["cogs"].get("needs_repricing")],
            key=lambda x: x["cogs"]["current_margin_pct"],
        )[:10]
        top = sorted(rec_list, key=lambda x: x["cogs"].get("current_margin_pct", 0), reverse=True)[:5]
        return {
            "recipe_count": len(rec_list),
            "ingredient_count": len(ing_list),
            "avg_margin_pct": round(sum(margins) / len(margins), 2) if margins else 0,
            "items_below_target": len(underperformers),
            "underperformers": [
                {"id": r["id"], "name": r["name"], "margin": r["cogs"]["current_margin_pct"],
                 "target": r["cogs"]["target_margin_pct"], "suggested_price": r["cogs"]["suggested_sell_price"]}
                for r in underperformers
            ],
            "top_margin": [
                {"id": r["id"], "name": r["name"], "margin": r["cogs"]["current_margin_pct"]}
                for r in top
            ],
        }

    @router.post("/recipes/{property_id}/forecast-week")
    async def forecast_week(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        """Estimate next-week ingredient demand using past 14d POS volume × recipe lines."""
        since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        items = await db.pos_orders.find(
            {"property_id": property_id, "created_at": {"$gte": since}}, {"_id": 0}
        ).to_list(20000)
        sales: dict = {}
        for o in items:
            for ln in (o.get("items") or []):
                key = ln.get("menu_item_id") or ln.get("name") or "unknown"
                sales[key] = sales.get(key, 0) + int(ln.get("quantity") or 1)
        for k in list(sales.keys()):
            sales[k] = sales[k] / 14.0
        ingredients, recipes, ing_list, rec_list = await _id_maps(property_id)
        ing_demand: dict = {}
        for r in rec_list:
            link = r.get("pos_menu_item_id")
            if not link or link not in sales:
                continue
            daily_qty = sales[link]
            yields = max(1, int(r.get("yields") or 1))
            for ln in r.get("lines") or []:
                if ln.get("ingredient_id"):
                    ing = ingredients.get(ln["ingredient_id"])
                    if not ing:
                        continue
                    qty_per_plate = float(ln.get("qty") or 0) / yields
                    weekly_qty = qty_per_plate * daily_qty * 7
                    bucket = ing_demand.setdefault(
                        ing["id"],
                        {"ingredient_id": ing["id"], "name": ing.get("name"),
                         "unit": ing.get("unit"), "weekly_qty": 0,
                         "cost_per_unit": ing.get("cost_per_unit"),
                         "weekly_cost": 0}
                    )
                    bucket["weekly_qty"] = round(bucket["weekly_qty"] + weekly_qty, 2)
                    bucket["weekly_cost"] = round(bucket["weekly_qty"] * (ing.get("cost_per_unit") or 0), 2)
        forecast = sorted(ing_demand.values(), key=lambda x: -x["weekly_cost"])
        total = round(sum(b["weekly_cost"] for b in forecast), 2)
        return {"items": forecast, "total_weekly_cost": total, "based_on_days": 14, "horizon_days": 7}

    @router.get("/recipes/{property_id}/{rid}")
    async def get_recipe(property_id: str, rid: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        ingredients, recipes, *_ = await _id_maps(property_id)
        r = recipes.get(rid)
        if not r:
            raise HTTPException(404, "recipe not found")
        r["cogs"] = _compute_cogs(r, ingredients, recipes)
        # Resolve modifier groups inline for UI convenience
        if r.get("modifier_group_ids"):
            mgs = await db.fnb_modifier_groups.find(
                {"property_id": property_id, "id": {"$in": r["modifier_group_ids"]}}, {"_id": 0}
            ).to_list(50)
            r["modifier_groups"] = mgs
        return r

    @router.put("/recipes/{property_id}/{rid}")
    async def update_recipe(property_id: str, rid: str, recipe: Recipe,
                            current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        await db.fnb_recipes.update_one(
            {"id": rid, "property_id": property_id},
            {"$set": {**recipe.model_dump(), "updated_at": _now(), "updated_by": current_user.get("email")}}
        )
        ingredients, recipes, *_ = await _id_maps(property_id)
        r = await db.fnb_recipes.find_one({"id": rid, "property_id": property_id}, {"_id": 0})
        if not r:
            raise HTTPException(404, "recipe not found")
        r["cogs"] = _compute_cogs(r, ingredients, recipes)
        return r

    @router.delete("/recipes/{property_id}/{rid}")
    async def delete_recipe(property_id: str, rid: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.fnb_recipes.delete_one({"id": rid, "property_id": property_id})
        return {"deleted": r.deleted_count}

    @router.post("/recipes/{property_id}/{rid}/cogs")
    async def recompute(property_id: str, rid: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "chef"))):
        ingredients, recipes, *_ = await _id_maps(property_id)
        r = recipes.get(rid)
        if not r:
            raise HTTPException(404, "not found")
        return _compute_cogs(r, ingredients, recipes)

    return router
