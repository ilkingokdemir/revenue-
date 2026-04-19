"""
Rate Structure & OTA Mapping
----------------------------
Product-side rate management (distinct from dynamic pricing in rate_manager.py).
Supports the classic PMS stack:

- **Rate Products** — named offerings (BAR, Non-Refundable, Advance Purchase, Corporate,
  Package) with cancellation policy, inclusions, age restrictions, min/max LOS.
- **Derived Rates** — child products that float X% above/below a parent product.
- **Channel Codes** — OTA-side room/rate-plan code → internal mapping so channel
  manager pushes land on the right combination.
- **Promo Codes** — booking-engine discount codes with usage caps and date windows.

Collections:
- rate_products, derived_rates, channel_codes, promo_codes
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from auth import require_perm


class RateProductIn(BaseModel):
    property_id: str = "default"
    name: str                       # e.g. "Best Available Rate"
    code: str                       # e.g. "BAR" (short code for OTAs)
    kind: str = "flex"              # flex | non_refundable | advance_purchase | corporate | package
    room_type_ids: List[str] = Field(default_factory=list)   # empty = all rooms
    inclusions: List[str] = Field(default_factory=list)      # ["breakfast", "wifi"]
    meal_plan: str = "room_only"    # room_only | bed_breakfast | half_board | full_board | all_inclusive
    cancellation_policy: str = "free_24h"   # free_24h | free_48h | free_72h | non_refundable | custom
    cancellation_fee_pct: float = 0
    min_los: int = 1
    max_los: int = 30
    min_advance_days: int = 0
    max_advance_days: int = 365
    active: bool = True
    notes: Optional[str] = ""


class DerivedRateIn(BaseModel):
    property_id: str = "default"
    name: str                       # "BAR -10% Mobile"
    parent_product_id: str          # rate_products.id
    basis: str = "percent"          # percent | flat
    adjustment: float = 0           # -10 = 10% cheaper; 15 = +£15 etc.
    active: bool = True


class ChannelCodeIn(BaseModel):
    property_id: str = "default"
    channel: str                    # booking_com | expedia | airbnb | hotels_com | agoda
    external_room_code: str         # OTA's room code
    external_rate_code: Optional[str] = ""
    room_type_id: str               # internal room_types.id
    rate_product_id: Optional[str] = ""
    notes: Optional[str] = ""
    active: bool = True


class PromoCodeIn(BaseModel):
    property_id: str = "default"
    code: str                       # "SUMMER25"
    kind: str = "percent"           # percent | flat
    amount: float = 0
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    max_uses: int = 0               # 0 = unlimited
    used: int = 0
    min_nights: int = 1
    applies_to_products: List[str] = Field(default_factory=list)
    active: bool = True


def create_rate_structure_router(db):
    router = APIRouter(prefix="/rate-structure")

    # ------------------------- RATE PRODUCTS -------------------------
    @router.get("/products")
    async def list_products(
        property_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {} if not property_id or property_id == "all" else {"property_id": property_id}
        return await db.rate_products.find(q, {"_id": 0}).sort("name", 1).to_list(500)

    @router.post("/products")
    async def create_product(
        data: RateProductIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        doc = data.model_dump()
        doc["id"] = str(uuid.uuid4())
        doc["code"] = doc["code"].upper()
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["created_by"] = current_user.get("email", "")
        await db.rate_products.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/products/{product_id}")
    async def update_product(
        product_id: str, data: RateProductIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        update = data.model_dump(exclude_unset=True)
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "code" in update:
            update["code"] = update["code"].upper()
        r = await db.rate_products.update_one({"id": product_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Product not found")
        return {"ok": True}

    @router.delete("/products/{product_id}")
    async def delete_product(
        product_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        # Also cascade-delete derived rates hanging off this product
        await db.derived_rates.delete_many({"parent_product_id": product_id})
        r = await db.rate_products.delete_one({"id": product_id})
        return {"deleted": r.deleted_count}

    # ------------------------- DERIVED RATES -------------------------
    @router.get("/derived")
    async def list_derived(
        property_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {} if not property_id or property_id == "all" else {"property_id": property_id}
        rows = await db.derived_rates.find(q, {"_id": 0}).sort("name", 1).to_list(200)
        # Enrich with parent name
        for r in rows:
            p = await db.rate_products.find_one(
                {"id": r.get("parent_product_id", "")}, {"_id": 0, "name": 1, "code": 1}
            )
            if p:
                r["parent_name"] = p["name"]
                r["parent_code"] = p.get("code", "")
        return rows

    @router.post("/derived")
    async def create_derived(
        data: DerivedRateIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        if not await db.rate_products.find_one({"id": data.parent_product_id}, {"_id": 0}):
            raise HTTPException(404, "Parent product not found")
        doc = data.model_dump()
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.derived_rates.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.delete("/derived/{drate_id}")
    async def delete_derived(
        drate_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        r = await db.derived_rates.delete_one({"id": drate_id})
        return {"deleted": r.deleted_count}

    @router.post("/derived/{drate_id}/evaluate")
    async def evaluate_derived(
        drate_id: str, body: dict,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """Given a parent base rate (from body), compute the derived rate."""
        dr = await db.derived_rates.find_one({"id": drate_id}, {"_id": 0})
        if not dr:
            raise HTTPException(404, "Derived rate not found")
        base = float(body.get("base", 0))
        adj = float(dr.get("adjustment", 0))
        if dr.get("basis") == "percent":
            out = base * (1 + adj / 100)
        else:
            out = base + adj
        return {"base": round(base, 2), "derived": round(out, 2),
                "basis": dr.get("basis"), "adjustment": adj}

    # ------------------------- CHANNEL CODES -------------------------
    @router.get("/channel-codes")
    async def list_channel_codes(
        property_id: str = "", channel: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        if channel:
            q["channel"] = channel
        rows = await db.channel_codes.find(q, {"_id": 0}).sort([("channel", 1), ("external_room_code", 1)]).to_list(1000)
        # Enrich with room name + product name
        for r in rows:
            rt = await db.room_types.find_one({"id": r.get("room_type_id", "")}, {"_id": 0, "name": 1})
            r["room_type_name"] = rt.get("name") if rt else "—"
            if r.get("rate_product_id"):
                p = await db.rate_products.find_one({"id": r["rate_product_id"]}, {"_id": 0, "name": 1, "code": 1})
                r["rate_product_name"] = p.get("name") if p else "—"
        return rows

    @router.post("/channel-codes")
    async def create_channel_code(
        data: ChannelCodeIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        doc = data.model_dump()
        doc["id"] = str(uuid.uuid4())
        doc["channel"] = doc["channel"].lower()
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.channel_codes.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/channel-codes/{code_id}")
    async def update_channel_code(
        code_id: str, data: ChannelCodeIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        update = data.model_dump(exclude_unset=True)
        r = await db.channel_codes.update_one({"id": code_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Mapping not found")
        return {"ok": True}

    @router.delete("/channel-codes/{code_id}")
    async def delete_channel_code(
        code_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        r = await db.channel_codes.delete_one({"id": code_id})
        return {"deleted": r.deleted_count}

    # ------------------------- PROMO CODES -------------------------
    @router.get("/promo-codes")
    async def list_promo_codes(
        property_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {} if not property_id or property_id == "all" else {"property_id": property_id}
        return await db.promo_codes.find(q, {"_id": 0}).sort("code", 1).to_list(500)

    @router.post("/promo-codes")
    async def create_promo(
        data: PromoCodeIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        doc = data.model_dump()
        doc["code"] = doc["code"].upper()
        existing = await db.promo_codes.find_one(
            {"code": doc["code"], "property_id": doc["property_id"]}, {"_id": 0}
        )
        if existing:
            raise HTTPException(400, f"Code {doc['code']} already exists for this property")
        doc["id"] = str(uuid.uuid4())
        doc["used"] = 0
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.promo_codes.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/promo-codes/{promo_id}")
    async def update_promo(
        promo_id: str, data: PromoCodeIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        update = data.model_dump(exclude_unset=True)
        if "code" in update:
            update["code"] = update["code"].upper()
        r = await db.promo_codes.update_one({"id": promo_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Promo not found")
        return {"ok": True}

    @router.delete("/promo-codes/{promo_id}")
    async def delete_promo(
        promo_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        r = await db.promo_codes.delete_one({"id": promo_id})
        return {"deleted": r.deleted_count}

    @router.post("/promo-codes/validate")
    async def validate_promo(
        body: dict,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """Booking engine hook. Body: {code, nights, subtotal, product_id?, property_id?}"""
        code = (body.get("code") or "").upper()
        if not code:
            raise HTTPException(400, "Code required")
        q = {"code": code, "active": True}
        if body.get("property_id"):
            q["property_id"] = body["property_id"]
        p = await db.promo_codes.find_one(q, {"_id": 0})
        if not p:
            raise HTTPException(404, "Invalid or inactive promo code")
        today = datetime.now(timezone.utc).date().isoformat()
        if p.get("valid_from") and today < p["valid_from"]:
            raise HTTPException(400, "Promo not yet active")
        if p.get("valid_to") and today > p["valid_to"]:
            raise HTTPException(400, "Promo expired")
        if p.get("max_uses") and p.get("used", 0) >= p["max_uses"]:
            raise HTTPException(400, "Promo fully redeemed")
        nights = int(body.get("nights", 1))
        if nights < p.get("min_nights", 1):
            raise HTTPException(400, f"Requires minimum {p['min_nights']} nights")
        if p.get("applies_to_products") and body.get("product_id") not in p["applies_to_products"]:
            raise HTTPException(400, "Promo doesn't apply to this rate product")
        subtotal = float(body.get("subtotal", 0))
        if p.get("kind") == "percent":
            discount = round(subtotal * p.get("amount", 0) / 100, 2)
        else:
            discount = round(p.get("amount", 0), 2)
        return {
            "valid": True, "code": code, "discount": discount,
            "new_total": round(max(0, subtotal - discount), 2),
            "remaining_uses": (p["max_uses"] - p.get("used", 0)) if p.get("max_uses") else None,
        }

    return router
