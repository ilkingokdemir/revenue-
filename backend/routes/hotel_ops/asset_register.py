"""
Asset Register (P2) — tracks physical assets (TV, mattress, HVAC, appliances)
with depreciation, warranty, and replacement schedule. Enterprise-grade
inventory for finance + maintenance reporting.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_asset_register_router(db, require_roles):
    router = APIRouter()

    @router.get("/assets/{property_id}")
    async def list_assets(property_id: str, category: str = "", location: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager", "maintenance"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        if category:
            q["category"] = category
        if location:
            q["location"] = location
        rows = await db.assets.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)

        today = datetime.now(timezone.utc).date()
        for r in rows:
            # Compute depreciated value (straight-line over useful_life_years)
            try:
                purchase = datetime.strptime(r.get("purchase_date", "1970-01-01"), "%Y-%m-%d").date()
                years_elapsed = max(0, (today - purchase).days / 365.25)
                life = float(r.get("useful_life_years") or 5)
                dep_pct = min(1.0, years_elapsed / life)
                r["depreciated_value"] = round(float(r.get("purchase_price", 0)) * (1 - dep_pct), 2)
                r["age_years"] = round(years_elapsed, 1)
                r["depreciation_pct"] = round(dep_pct * 100, 1)
                # Warranty
                if r.get("warranty_expires"):
                    r["warranty_active"] = r["warranty_expires"] >= today.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                r["depreciated_value"] = float(r.get("purchase_price", 0))
                r["age_years"] = 0
                r["depreciation_pct"] = 0
        return rows

    @router.get("/assets/summary/{property_id}")
    async def summary(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        rows = await db.assets.find(q, {"_id": 0}).to_list(5000)
        today = datetime.now(timezone.utc).date()
        total_purchase = 0.0
        total_depreciated = 0.0
        category_counts = {}
        warranty_expiring_soon = 0
        for r in rows:
            total_purchase += float(r.get("purchase_price", 0))
            try:
                purchase = datetime.strptime(r.get("purchase_date", "1970-01-01"), "%Y-%m-%d").date()
                years_elapsed = max(0, (today - purchase).days / 365.25)
                life = float(r.get("useful_life_years") or 5)
                dep_pct = min(1.0, years_elapsed / life)
                total_depreciated += float(r.get("purchase_price", 0)) * (1 - dep_pct)
            except (ValueError, TypeError):
                total_depreciated += float(r.get("purchase_price", 0))
            category_counts[r.get("category", "other")] = category_counts.get(r.get("category", "other"), 0) + 1

            if r.get("warranty_expires"):
                try:
                    exp = datetime.strptime(r["warranty_expires"], "%Y-%m-%d").date()
                    if today <= exp <= today + timedelta(days=60):
                        warranty_expiring_soon += 1
                except ValueError:
                    pass

        return {
            "count": len(rows),
            "total_purchase_value": round(total_purchase, 2),
            "total_book_value": round(total_depreciated, 2),
            "total_depreciation": round(total_purchase - total_depreciated, 2),
            "by_category": [{"category": k, "count": v} for k, v in sorted(category_counts.items())],
            "warranty_expiring_soon": warranty_expiring_soon,
        }

    @router.post("/assets")
    async def create_asset(data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        asset = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": name,
            "category": data.get("category", "other"),  # tv, appliance, hvac, mattress, furniture, it, other
            "location": (data.get("location") or "").strip(),
            "serial_number": (data.get("serial_number") or "").strip(),
            "supplier": (data.get("supplier") or "").strip(),
            "purchase_date": data.get("purchase_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "purchase_price": float(data.get("purchase_price") or 0),
            "currency": data.get("currency", "GBP"),
            "useful_life_years": float(data.get("useful_life_years") or 5),
            "warranty_expires": data.get("warranty_expires", ""),
            "status": data.get("status", "active"),  # active, decommissioned, sold, written_off
            "notes": (data.get("notes") or "").strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.assets.insert_one(asset)
        asset.pop("_id", None)
        return asset

    @router.put("/assets/{asset_id}")
    async def update_asset(asset_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        updates = {k: v for k, v in data.items() if k not in ("id", "_id", "created_at", "created_by")}
        await db.assets.update_one({"id": asset_id}, {"$set": updates})
        return await db.assets.find_one({"id": asset_id}, {"_id": 0})

    @router.delete("/assets/{asset_id}")
    async def delete_asset(asset_id: str,
                           current_user: dict = Depends(require_roles("admin"))):
        await db.assets.delete_one({"id": asset_id})
        return {"status": "deleted"}

    return router
