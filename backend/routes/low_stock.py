"""
Inventory Low-Stock Alerts (P1)
-------------------------------
Watches `stock_items` (or `inventory_items` / `pos_inventory`) and surfaces
items below their `reorder_threshold`. Generates an `inventory_alerts` row
for the dashboard and queues a `notifications` row for the manager.

Endpoints
---------
POST /low-stock/scan                     Cron — scan, generate alerts
GET  /low-stock/{property_id}/alerts     Open / recent alerts
POST /low-stock/alert/{alert_id}/dismiss
GET  /low-stock/{property_id}/items      Current stock state with status
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _all_stock_items(db, property_id: str) -> List[Dict]:
    """Read from the first collection that has data."""
    for coll in ("stock_items", "inventory_items", "pos_inventory", "menu_items"):
        rows = await db[coll].find({"property_id": property_id}, {"_id": 0}).to_list(2000)
        if rows:
            return [dict(r, _src=coll) for r in rows]
    return []


def create_low_stock_router(db, require_roles):
    router = APIRouter()

    @router.post("/low-stock/scan")
    async def scan(data: Optional[Dict] = None,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data or {}).get("property_id", "")
        if not property_id:
            raise HTTPException(400, "property_id required")
        items = await _all_stock_items(db, property_id)
        alerts_created = 0
        for it in items:
            qty = float(it.get("qty") or it.get("quantity") or it.get("stock") or it.get("on_hand") or 0)
            threshold = float(it.get("reorder_threshold") or it.get("min_stock") or 0)
            if threshold <= 0 or qty > threshold:
                continue
            # Already an open alert?
            existing = await db.inventory_alerts.find_one({
                "property_id": property_id,
                "item_id": it.get("id") or it.get("name"),
                "status": "open",
            }, {"_id": 0})
            if existing:
                continue
            alert = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "item_id": it.get("id") or it.get("name"),
                "item_name": it.get("name", ""),
                "category": it.get("category", ""),
                "source": it.get("_src", "stock_items"),
                "qty_on_hand": qty,
                "reorder_threshold": threshold,
                "shortfall": round(max(threshold - qty, 0), 2),
                "preferred_supplier": it.get("supplier", ""),
                "status": "open",
                "opened_at": _now(),
            }
            await db.inventory_alerts.insert_one(dict(alert))
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "kind": "low_stock",
                "title": f"Low stock: {alert['item_name']}",
                "body": f"{alert['item_name']} is at {qty}, threshold {threshold}. Reorder needed.",
                "severity": "warning" if qty > 0 else "high",
                "for_role": "manager",
                "created_at": _now(),
                "read": False,
            })
            alerts_created += 1
        return {"ok": True, "items_scanned": len(items), "alerts_created": alerts_created}

    @router.get("/low-stock/{property_id}/alerts")
    async def list_alerts(property_id: str, status: str = "open", days: int = 30,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "opened_at": {"$gte": since}}
        if status:
            q["status"] = status
        rows = await db.inventory_alerts.find(q, {"_id": 0}).sort("opened_at", -1).to_list(500)
        return {"items": rows, "count": len(rows)}

    @router.post("/low-stock/alert/{alert_id}/dismiss")
    async def dismiss(alert_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await db.inventory_alerts.update_one(
            {"id": alert_id},
            {"$set": {"status": "dismissed", "dismissed_at": _now(),
                       "dismissed_by": current_user.get("name", "Staff")}},
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Alert not found")
        return {"ok": True}

    @router.get("/low-stock/{property_id}/items")
    async def items_state(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        items = await _all_stock_items(db, property_id)
        out = []
        low = 0
        ok_n = 0
        for it in items:
            qty = float(it.get("qty") or it.get("quantity") or it.get("stock") or it.get("on_hand") or 0)
            threshold = float(it.get("reorder_threshold") or it.get("min_stock") or 0)
            status = "ok"
            if threshold > 0 and qty <= 0:
                status = "out"
                low += 1
            elif threshold > 0 and qty <= threshold:
                status = "low"
                low += 1
            else:
                ok_n += 1
            out.append({
                "id": it.get("id") or it.get("name"),
                "name": it.get("name", ""),
                "category": it.get("category", ""),
                "qty_on_hand": qty,
                "reorder_threshold": threshold,
                "supplier": it.get("supplier", ""),
                "source": it.get("_src", ""),
                "status": status,
            })
        out.sort(key=lambda x: (x["status"] != "out", x["status"] != "low"))
        return {"items": out, "count": len(out), "low_count": low, "ok_count": ok_n}

    return router
