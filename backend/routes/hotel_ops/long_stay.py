"""
Long-stay Discount Auto-Apply (P1)
----------------------------------
Per-property tier ladder where bookings with N+ nights automatically receive
a discount applied to their booking rate, posted as a `long_stay_discount`
folio adjustment.

Tiers e.g.:
  ≥ 7 nights  → 10% off
  ≥ 14 nights → 15% off
  ≥ 28 nights → 25% off

Endpoints
---------
POST /long-stay/config                Save tier ladder
GET  /long-stay/{property_id}/config
POST /long-stay/sweep                 Cron — apply to eligible new bookings
GET  /long-stay/{property_id}/log     Recent applications (audit)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import uuid


DEFAULT_LADDER = [
    {"min_nights": 7, "discount_pct": 10.0},
    {"min_nights": 14, "discount_pct": 15.0},
    {"min_nights": 28, "discount_pct": 25.0},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_pct(nights: int, ladder) -> float:
    pct = 0.0
    for t in sorted(ladder, key=lambda x: x["min_nights"]):
        if nights >= int(t["min_nights"]):
            pct = float(t["discount_pct"])
    return pct


def create_long_stay_router(db, require_roles):
    router = APIRouter()

    @router.post("/long-stay/config")
    async def upsert(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        if not property_id:
            raise HTTPException(400, "property_id required")
        ladder = data.get("ladder") or DEFAULT_LADDER
        for t in ladder:
            if int(t.get("min_nights", 0)) < 2 or float(t.get("discount_pct", 0)) <= 0:
                raise HTTPException(400, "tier needs min_nights ≥ 2 and discount_pct > 0")
        record = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", True)),
            "ladder": ladder,
            "max_discount_pct": float(data.get("max_discount_pct") or 30.0),
            "updated_at": _now(),
            "updated_by": current_user.get("name", "Staff"),
        }
        await db.long_stay_config.update_one({"property_id": property_id}, {"$set": record}, upsert=True)
        return {"ok": True, "config": record}

    @router.get("/long-stay/{property_id}/config")
    async def get_cfg(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        return await db.long_stay_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "property_id": property_id, "enabled": True, "ladder": DEFAULT_LADDER, "max_discount_pct": 30.0,
        }

    @router.post("/long-stay/sweep")
    async def sweep(data: Optional[Dict] = None,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data or {}).get("property_id", "")
        cfg = await db.long_stay_config.find_one({"property_id": property_id}, {"_id": 0}) if property_id else None
        if cfg and not cfg.get("enabled", True):
            return {"ok": True, "skipped": "disabled"}
        ladder = (cfg or {}).get("ladder") or DEFAULT_LADDER
        cap = (cfg or {}).get("max_discount_pct", 30.0)

        q: Dict = {"status": {"$nin": ["cancelled", "no_show"]}, "long_stay_discount_applied": {"$ne": True}}
        if property_id:
            q["property_id"] = property_id
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(20000)
        applied = 0
        skipped = 0
        for b in bookings:
            nights = int(b.get("nights") or 0)
            if nights < 2:
                continue
            pct = min(_pick_pct(nights, ladder), float(cap))
            if pct <= 0:
                continue
            total = float(b.get("total_price") or 0)
            if total <= 0:
                skipped += 1
                continue
            discount = round(total * pct / 100, 2)
            new_total = round(total - discount, 2)
            await db.bookings.update_one(
                {"id": b["id"]},
                {"$set": {
                    "long_stay_discount_applied": True,
                    "long_stay_discount_pct": pct,
                    "long_stay_discount_amount": discount,
                    "total_price_before_long_stay": total,
                    "total_price": new_total,
                    "updated_at": _now(),
                }},
            )
            await db.folio_charges.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": b["id"],
                "category": "discount",
                "description": f"Long-stay discount · {pct}% off ({nights} nights)",
                "amount": -discount,
                "currency": b.get("currency", "GBP"),
                "posted_at": _now(),
                "posted_by": "long-stay-sweep",
            })
            await db.long_stay_log.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": b.get("property_id", ""),
                "booking_id": b["id"],
                "guest_name": b.get("guest_name", ""),
                "nights": nights,
                "discount_pct": pct,
                "discount_amount": discount,
                "applied_at": _now(),
            })
            applied += 1
        return {"ok": True, "scanned": len(bookings), "applied": applied, "skipped": skipped}

    @router.get("/long-stay/{property_id}/log")
    async def log(property_id: str, days: int = 90,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.long_stay_log.find(
            {"property_id": property_id, "applied_at": {"$gte": since}}, {"_id": 0}
        ).sort("applied_at", -1).to_list(500)
        return {"items": rows, "count": len(rows),
                 "discounts_total": round(sum(float(r.get("discount_amount") or 0) for r in rows), 2),
                 "nights_total": sum(int(r.get("nights") or 0) for r in rows)}

    return router
