"""
Tax Configuration
-----------------
Centralised multi-region tax profiles. Each property can have multiple tax lines
that apply to Room revenue, F&B, Spa, etc. Supports percentage-of-total, per-night
per-guest flat fees, and flat-per-stay. Per-channel overrides for OTAs that include
tax in their commission model.

Collections:
- tax_profiles: { id, property_id, name, rules[{kind, label, basis, rate, applies_to[], channels[], included_in_rate}], active, notes }

Endpoints (all /api/tax-config/*):
- GET    /profiles?property_id=
- POST   /profiles
- PUT    /profiles/{id}
- DELETE /profiles/{id}
- POST   /calculate           → { property_id, channel, base_amount, nights, guests } → tax breakdown
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List, Dict
import uuid

from auth import require_perm


class TaxRule(BaseModel):
    kind: str = "vat"          # vat | city_tax | tourist_tax | service_charge | resort_fee | other
    label: str                 # human readable e.g. "VAT 20%", "City Tax £1.50/night"
    basis: str = "percent"     # percent | per_night_per_guest | per_night | flat
    rate: float = 0            # 20 for 20%, 1.5 for £1.50
    applies_to: List[str] = Field(default_factory=lambda: ["room"])  # room | fnb | spa | parking | all
    channels: List[str] = Field(default_factory=list)  # empty = all channels
    included_in_rate: bool = False  # true = tax is inside the displayed rate (OTA commonly)


class TaxProfileIn(BaseModel):
    property_id: str = "default"
    name: str
    rules: List[TaxRule] = Field(default_factory=list)
    active: bool = True
    notes: Optional[str] = ""


class TaxCalcIn(BaseModel):
    property_id: str = "default"
    channel: Optional[str] = ""
    base_amount: float           # pre-tax subtotal (room rate × nights)
    nights: int = 1
    guests: int = 1
    category: str = "room"       # room | fnb | spa ...


def _calculate_taxes(profile: dict, base_amount: float, nights: int, guests: int,
                     channel: str, category: str):
    """Evaluate rules and return list of applied taxes + totals."""
    applied = []
    tax_added_total = 0.0      # taxes added on top of base
    tax_included_total = 0.0   # taxes already inside the base
    for rule in profile.get("rules", []):
        applies_to = rule.get("applies_to") or ["room"]
        if "all" not in applies_to and category not in applies_to:
            continue
        channels = rule.get("channels") or []
        if channels and channel and channel not in channels:
            continue

        basis = rule.get("basis", "percent")
        rate = float(rule.get("rate", 0))
        amount = 0.0
        if basis == "percent":
            amount = round(base_amount * rate / 100, 2)
        elif basis == "per_night_per_guest":
            amount = round(rate * max(nights, 1) * max(guests, 1), 2)
        elif basis == "per_night":
            amount = round(rate * max(nights, 1), 2)
        elif basis == "flat":
            amount = round(rate, 2)

        applied.append({
            "kind": rule.get("kind"),
            "label": rule.get("label"),
            "basis": basis,
            "rate": rate,
            "amount": amount,
            "included_in_rate": bool(rule.get("included_in_rate")),
        })
        if rule.get("included_in_rate"):
            tax_included_total += amount
        else:
            tax_added_total += amount

    return {
        "base": round(base_amount, 2),
        "taxes_added": round(tax_added_total, 2),
        "taxes_included": round(tax_included_total, 2),
        "grand_total": round(base_amount + tax_added_total, 2),
        "applied": applied,
    }


def create_tax_config_router(db):
    router = APIRouter(prefix="/tax-config")

    @router.get("/profiles")
    async def list_profiles(
        property_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.tax_profiles.find(q, {"_id": 0}).sort("name", 1).to_list(200)
        return rows

    @router.post("/profiles")
    async def create_profile(
        data: TaxProfileIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        doc = data.model_dump()
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["created_by"] = current_user.get("email", "")
        await db.tax_profiles.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/profiles/{profile_id}")
    async def update_profile(
        profile_id: str, data: TaxProfileIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        update = data.model_dump()
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.tax_profiles.update_one({"id": profile_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Profile not found")
        return {"updated": True, "id": profile_id}

    @router.delete("/profiles/{profile_id}")
    async def delete_profile(
        profile_id: str,
        current_user: dict = Depends(require_perm("delete_bookings")),
    ):
        r = await db.tax_profiles.delete_one({"id": profile_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Profile not found")
        return {"deleted": True}

    @router.post("/calculate")
    async def calculate(
        data: TaxCalcIn,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """Dry-run tax calculation for a given base amount + context. Uses the first active
        profile for the property."""
        q = {"active": True}
        if data.property_id and data.property_id != "all":
            q["property_id"] = data.property_id
        profile = await db.tax_profiles.find_one(q, {"_id": 0})
        if not profile:
            return {"base": data.base_amount, "taxes_added": 0, "taxes_included": 0,
                    "grand_total": round(data.base_amount, 2), "applied": [], "profile": None}
        result = _calculate_taxes(profile, data.base_amount, data.nights, data.guests,
                                   data.channel or "", data.category)
        result["profile"] = {"id": profile["id"], "name": profile["name"]}
        return result

    return router
