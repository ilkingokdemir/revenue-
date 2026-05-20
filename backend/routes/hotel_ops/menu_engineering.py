"""
Menu Engineering (P1)
---------------------
Classic 4-quadrant F&B analysis on POS sales:

                       High contribution margin
                                 │
                Star (high pop)  │  Puzzle (low pop)
        ─────────────────────────┼──────────────────────────  median CM
            Plowhorse (high pop) │  Dog (low pop)
                                 │
                       Low contribution margin

Inputs from `pos_orders` / `pos_order_items` for a window. Falls back to
`menu_items` for cost/price reference.

Endpoints
---------
GET /menu-engineering/{property_id}        Run analysis for window (default 30d)
GET /menu-engineering/{property_id}/export Export rows as CSV-ready JSON
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_menu_engineering_router(db, require_roles):
    router = APIRouter()

    async def _build_rows(property_id: str, days: int) -> List[Dict]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        # Try pos_order_items first, fall back to pos_orders.items embedded
        items: List[Dict] = []
        order_items_cur = db.pos_order_items.find(
            {"property_id": property_id, "ordered_at": {"$gte": since}}, {"_id": 0}
        )
        async for oi in order_items_cur:
            items.append(oi)
        if not items:
            orders = await db.pos_orders.find(
                {"property_id": property_id, "created_at": {"$gte": since}}, {"_id": 0}
            ).to_list(20000)
            for o in orders:
                for ln in (o.get("items") or []):
                    items.append({
                        "menu_item_id": ln.get("menu_item_id") or ln.get("id") or ln.get("name"),
                        "name": ln.get("name", ""),
                        "qty": int(ln.get("qty") or ln.get("quantity") or 1),
                        "price": float(ln.get("price") or ln.get("unit_price") or 0),
                        "cost": float(ln.get("cost") or 0),
                        "category": ln.get("category", ""),
                    })
        # Look up master menu items for cost reference
        menu_master = {m.get("id") or m.get("name"): m for m in
                        await db.menu_items.find({"property_id": property_id}, {"_id": 0}).to_list(2000)}

        agg: Dict[str, Dict] = {}
        for ln in items:
            key = ln.get("menu_item_id") or ln.get("name") or "unknown"
            row = agg.setdefault(key, {
                "id": key,
                "name": ln.get("name", key),
                "category": ln.get("category", ""),
                "qty": 0, "revenue": 0.0, "cost": 0.0,
            })
            qty = int(ln.get("qty") or 1)
            price = float(ln.get("price") or 0)
            cost = float(ln.get("cost") or 0)
            if cost == 0 and key in menu_master:
                cost = float(menu_master[key].get("cost") or 0)
                if not row["category"]:
                    row["category"] = menu_master[key].get("category", "")
            row["qty"] += qty
            row["revenue"] += price * qty
            row["cost"] += cost * qty

        rows = list(agg.values())
        if not rows:
            return []
        # CM per dish + popularity %
        total_qty = sum(r["qty"] for r in rows) or 1
        for r in rows:
            r["unit_price"] = round(r["revenue"] / max(r["qty"], 1), 2)
            r["unit_cost"] = round(r["cost"] / max(r["qty"], 1), 2)
            r["unit_cm"] = round(r["unit_price"] - r["unit_cost"], 2)
            r["total_cm"] = round(r["revenue"] - r["cost"], 2)
            r["pop_pct"] = round(r["qty"] * 100 / total_qty, 2)
            r["revenue"] = round(r["revenue"], 2)
            r["cost"] = round(r["cost"], 2)
        # Median CM and median popularity
        sorted_cm = sorted(r["unit_cm"] for r in rows)
        sorted_pop = sorted(r["pop_pct"] for r in rows)

        def _median(arr):
            if not arr: return 0
            n = len(arr)
            return arr[n // 2] if n % 2 else (arr[n // 2 - 1] + arr[n // 2]) / 2
        median_cm = _median(sorted_cm)
        median_pop = _median(sorted_pop)
        for r in rows:
            high_cm = r["unit_cm"] >= median_cm
            high_pop = r["pop_pct"] >= median_pop
            if high_cm and high_pop:
                r["quadrant"] = "star"
            elif (not high_cm) and high_pop:
                r["quadrant"] = "plowhorse"
            elif high_cm and (not high_pop):
                r["quadrant"] = "puzzle"
            else:
                r["quadrant"] = "dog"
        rows.sort(key=lambda x: x["total_cm"], reverse=True)
        return rows

    @router.get("/menu-engineering/{property_id}")
    async def analyse(property_id: str, days: int = 30,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await _build_rows(property_id, days)
        counts = {"star": 0, "plowhorse": 0, "puzzle": 0, "dog": 0}
        revenue = 0.0
        cm = 0.0
        for r in rows:
            counts[r["quadrant"]] += 1
            revenue += r["revenue"]
            cm += r["total_cm"]
        recs: List[str] = []
        for r in rows:
            if r["quadrant"] == "puzzle":
                recs.append(f"Re-position '{r['name']}' (high margin, low sales) — feature on menu, recommend by waitstaff.")
            elif r["quadrant"] == "plowhorse":
                recs.append(f"Re-engineer '{r['name']}' (popular but low margin) — review portion / cost / price by 5–10%.")
            elif r["quadrant"] == "dog":
                recs.append(f"Consider removing '{r['name']}' (low margin and low sales).")
            if len(recs) >= 8:
                break
        return {
            "window_days": days, "items_analysed": len(rows),
            "counts": counts, "total_revenue": round(revenue, 2), "total_cm": round(cm, 2),
            "rows": rows, "recommendations": recs,
        }

    @router.get("/menu-engineering/{property_id}/export")
    async def export(property_id: str, days: int = 30,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await _build_rows(property_id, days)
        cols = ["name", "category", "quadrant", "qty", "pop_pct", "unit_price", "unit_cost", "unit_cm", "total_cm", "revenue"]
        return {"columns": cols, "rows": [[r.get(c, "") for c in cols] for r in rows]}

    return router
