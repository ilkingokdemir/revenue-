"""
Multi-currency Tax Reports (P1)
-------------------------------
Aggregates folio_charges across a date window, broken down by currency and by
tax_category (room/food/beverage/other). Useful when one chain runs properties
in different currencies and the central finance team needs a roll-up.

Endpoints
---------
GET /tax-reports/{property_id}            Reports for a single property
GET /tax-reports/all                      Cross-property roll-up (admin only)
GET /tax-reports/{property_id}/export.csv CSV export
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Default UK-ish tax map. Hotels can override via property.tax_map
DEFAULT_TAX_MAP = {
    "room": 20.0, "food": 12.0, "beverage": 20.0, "alcohol": 20.0,
    "spa": 20.0, "tax": 0.0, "discount": 0.0, "tip": 0.0, "insurance": 0.0,
    "late_checkout": 20.0, "minibar": 20.0, "parking": 20.0,
}


async def _aggregate(db, q: Dict, days: int) -> Dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = {**q, "posted_at": {"$gte": since}}
    rows = await db.folio_charges.find(q, {"_id": 0}).to_list(50000)

    # Property currencies map
    properties = await db.properties.find({}, {"_id": 0}).to_list(500)
    prop_currency = {p.get("id"): p.get("currency", "GBP") for p in properties}
    prop_taxmap = {p.get("id"): {**DEFAULT_TAX_MAP, **(p.get("tax_map") or {})} for p in properties}

    by_currency: Dict[str, Dict] = {}
    by_category: Dict[str, Dict] = {}
    by_property: Dict[str, Dict] = {}

    for r in rows:
        booking_id = r.get("booking_id")
        booking = None
        if booking_id:
            booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0, "property_id": 1, "currency": 1}) or {}
        prop_id = (booking or {}).get("property_id") or r.get("property_id") or ""
        currency = r.get("currency") or (booking or {}).get("currency") or prop_currency.get(prop_id, "GBP")
        cat = r.get("category") or "other"
        amt = float(r.get("amount") or 0)
        # VAT rate
        rate = (prop_taxmap.get(prop_id, DEFAULT_TAX_MAP)).get(cat, 0.0)
        # Treat amount as gross — back out tax
        net = round(amt / (1 + rate / 100), 2) if rate > 0 else round(amt, 2)
        tax = round(amt - net, 2)

        cur_cell = by_currency.setdefault(currency, {"net": 0.0, "tax": 0.0, "gross": 0.0, "lines": 0})
        cur_cell["net"] += net; cur_cell["tax"] += tax; cur_cell["gross"] += amt; cur_cell["lines"] += 1

        cat_cell = by_category.setdefault(cat, {"net": 0.0, "tax": 0.0, "gross": 0.0, "rate": rate})
        cat_cell["net"] += net; cat_cell["tax"] += tax; cat_cell["gross"] += amt

        if prop_id:
            p_cell = by_property.setdefault(prop_id, {"net": 0.0, "tax": 0.0, "gross": 0.0,
                                                        "currency": currency,
                                                        "name": next((p.get("name") for p in properties if p.get("id") == prop_id), prop_id)})
            p_cell["net"] += net; p_cell["tax"] += tax; p_cell["gross"] += amt

    for d in (by_currency, by_category, by_property):
        for v in d.values():
            for k in ("net", "tax", "gross"):
                if k in v:
                    v[k] = round(v[k], 2)

    return {
        "window_days": days,
        "lines_total": len(rows),
        "by_currency": by_currency,
        "by_category": by_category,
        "by_property": by_property,
    }


def create_tax_reports_router(db, require_roles):
    router = APIRouter()

    @router.get("/tax-reports/{property_id}")
    async def report(property_id: str, days: int = 30,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        booking_ids = await db.bookings.find({"property_id": property_id}, {"_id": 0, "id": 1}).to_list(20000)
        bid_list = [b["id"] for b in booking_ids]
        if not bid_list:
            return await _aggregate(db, {"booking_id": {"$in": []}}, days)
        return await _aggregate(db, {"booking_id": {"$in": bid_list}}, days)

    @router.get("/tax-reports/all")
    async def all_props(days: int = 30,
                          current_user: dict = Depends(require_roles("admin"))):
        return await _aggregate(db, {}, days)

    @router.get("/tax-reports/{property_id}/export.csv", response_class=PlainTextResponse)
    async def export(property_id: str, days: int = 30,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        rep = await report(property_id, days, current_user)  # type: ignore[arg-type]
        lines = ["section,key,currency_or_rate,net,tax,gross,lines_or_rate"]
        for cur, v in rep["by_currency"].items():
            lines.append(f"by_currency,{cur},{cur},{v['net']},{v['tax']},{v['gross']},{v['lines']}")
        for cat, v in rep["by_category"].items():
            lines.append(f"by_category,{cat},{v.get('rate', 0)}%,{v['net']},{v['tax']},{v['gross']},{v.get('rate', 0)}")
        return "\n".join(lines)

    return router
