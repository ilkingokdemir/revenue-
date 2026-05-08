"""
Tax / City-Tax Preset Library
-----------------------------
Most properties don't know what tax stack to set up. We ship a curated
preset library covering UK, EU, US, TR (and more) with industry-standard
rates as of 2026. One click on a preset → creates an active tax_profile
that the existing `tax_config` engine evaluates on every booking.

Endpoints (under /api/tax-presets):
- GET  /                          — list available country presets
- POST /apply                     — apply a preset to a property (creates profile)
- GET  /resort-fees               — common resort/destination-fee templates
- POST /quick-resort-fee          — one-click create flat resort-fee rule
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, List
import uuid


# Preset library — pulled from official tax authorities + industry reports.
# Add new entries here as new markets onboard.
PRESETS: Dict[str, dict] = {
    "GB": {
        "name": "United Kingdom",
        "currency": "GBP",
        "rules": [
            {"kind": "vat", "label": "VAT 20%", "basis": "percent", "rate": 20.0,
             "applies_to": ["room", "fnb", "spa"], "included_in_rate": True},
        ],
    },
    "GB-LON": {
        "name": "London (UK + Westminster TfL levy)",
        "currency": "GBP",
        "rules": [
            {"kind": "vat", "label": "VAT 20%", "basis": "percent", "rate": 20.0,
             "applies_to": ["room", "fnb", "spa"], "included_in_rate": True},
            {"kind": "city_tax", "label": "Westminster levy £1/night", "basis": "per_night",
             "rate": 1.0, "applies_to": ["room"], "included_in_rate": False},
        ],
    },
    "FR": {
        "name": "France (Taxe de Séjour)",
        "currency": "EUR",
        "rules": [
            {"kind": "vat", "label": "TVA 10% (room)", "basis": "percent", "rate": 10.0,
             "applies_to": ["room"], "included_in_rate": True},
            {"kind": "vat", "label": "TVA 20% (F&B)", "basis": "percent", "rate": 20.0,
             "applies_to": ["fnb", "spa"], "included_in_rate": True},
            {"kind": "tourist_tax", "label": "Taxe de séjour €2.30/night/adult",
             "basis": "per_night_per_guest", "rate": 2.30, "applies_to": ["room"]},
        ],
    },
    "IT": {
        "name": "Italy (Tassa di Soggiorno)",
        "currency": "EUR",
        "rules": [
            {"kind": "vat", "label": "IVA 10%", "basis": "percent", "rate": 10.0,
             "applies_to": ["room"], "included_in_rate": True},
            {"kind": "tourist_tax", "label": "Tassa €3/night/adult (max 7 nights)",
             "basis": "per_night_per_guest", "rate": 3.0, "applies_to": ["room"]},
        ],
    },
    "ES": {
        "name": "Spain (Impuesto Turístico)",
        "currency": "EUR",
        "rules": [
            {"kind": "vat", "label": "IVA 10%", "basis": "percent", "rate": 10.0,
             "applies_to": ["room"], "included_in_rate": True},
            {"kind": "tourist_tax", "label": "Tasa turística €2/night/adult",
             "basis": "per_night_per_guest", "rate": 2.0, "applies_to": ["room"]},
        ],
    },
    "DE": {
        "name": "Germany (Bettensteuer)",
        "currency": "EUR",
        "rules": [
            {"kind": "vat", "label": "USt 7% (room)", "basis": "percent", "rate": 7.0,
             "applies_to": ["room"], "included_in_rate": True},
            {"kind": "vat", "label": "USt 19% (F&B)", "basis": "percent", "rate": 19.0,
             "applies_to": ["fnb", "spa"], "included_in_rate": True},
            {"kind": "city_tax", "label": "Bettensteuer 5%", "basis": "percent",
             "rate": 5.0, "applies_to": ["room"]},
        ],
    },
    "NL": {
        "name": "Netherlands (Toeristenbelasting)",
        "currency": "EUR",
        "rules": [
            {"kind": "vat", "label": "BTW 9%", "basis": "percent", "rate": 9.0,
             "applies_to": ["room"], "included_in_rate": True},
            {"kind": "tourist_tax", "label": "Tourist tax 7%", "basis": "percent",
             "rate": 7.0, "applies_to": ["room"]},
        ],
    },
    "TR": {
        "name": "Türkiye (Konaklama Vergisi)",
        "currency": "TRY",
        "rules": [
            {"kind": "vat", "label": "KDV 10% (oda)", "basis": "percent", "rate": 10.0,
             "applies_to": ["room"], "included_in_rate": True},
            {"kind": "vat", "label": "KDV 20% (F&B)", "basis": "percent", "rate": 20.0,
             "applies_to": ["fnb", "spa"], "included_in_rate": True},
            {"kind": "tourist_tax", "label": "Konaklama Vergisi 2%", "basis": "percent",
             "rate": 2.0, "applies_to": ["room"]},
        ],
    },
    "US-NV": {
        "name": "USA — Nevada / Las Vegas",
        "currency": "USD",
        "rules": [
            {"kind": "city_tax", "label": "Lodging tax 13.38%", "basis": "percent",
             "rate": 13.38, "applies_to": ["room"]},
            {"kind": "resort_fee", "label": "Resort fee $45/night", "basis": "per_night",
             "rate": 45.0, "applies_to": ["room"]},
        ],
    },
    "US-NY": {
        "name": "USA — New York City",
        "currency": "USD",
        "rules": [
            {"kind": "city_tax", "label": "NYC hotel tax 14.75%", "basis": "percent",
             "rate": 14.75, "applies_to": ["room"]},
            {"kind": "city_tax", "label": "NYC occupancy fee $3.50/night", "basis": "per_night",
             "rate": 3.50, "applies_to": ["room"]},
        ],
    },
    "US-CA": {
        "name": "USA — California",
        "currency": "USD",
        "rules": [
            {"kind": "city_tax", "label": "Transient occupancy tax 14%", "basis": "percent",
             "rate": 14.0, "applies_to": ["room"]},
            {"kind": "resort_fee", "label": "Resort fee $35/night", "basis": "per_night",
             "rate": 35.0, "applies_to": ["room"]},
        ],
    },
    "AE": {
        "name": "UAE — Dubai (Tourism Dirham)",
        "currency": "AED",
        "rules": [
            {"kind": "vat", "label": "VAT 5%", "basis": "percent", "rate": 5.0,
             "applies_to": ["room", "fnb", "spa"], "included_in_rate": True},
            {"kind": "city_tax", "label": "Dubai Tourism Dirham 10/night/room",
             "basis": "per_night", "rate": 10.0, "applies_to": ["room"]},
            {"kind": "city_tax", "label": "Service charge 10%", "basis": "percent",
             "rate": 10.0, "applies_to": ["room"]},
        ],
    },
}

RESORT_FEE_TEMPLATES = [
    {"label": "Wi-Fi + gym + pool",            "rate": 25.0, "currency": "USD"},
    {"label": "Resort amenity fee (mid-range)", "rate": 35.0, "currency": "USD"},
    {"label": "Luxury resort fee",              "rate": 50.0, "currency": "USD"},
    {"label": "Destination fee — boutique",     "rate": 18.0, "currency": "GBP"},
    {"label": "Destination fee — Las Vegas",    "rate": 45.0, "currency": "USD"},
]


def create_tax_presets_router(db, require_roles):
    router = APIRouter(prefix="/tax-presets")

    @router.get("/")
    async def list_presets(current_user: dict = Depends(require_roles("admin", "manager"))):
        return {"presets": [
            {"code": code, **{k: v for k, v in p.items() if k != "rules"},
             "rule_count": len(p["rules"]),
             "preview": [r["label"] for r in p["rules"]]}
            for code, p in PRESETS.items()
        ]}

    @router.get("/{code}")
    async def get_preset(code: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        p = PRESETS.get(code)
        if not p:
            raise HTTPException(404, "Preset not found")
        return {"code": code, **p}

    @router.post("/apply")
    async def apply_preset(data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        code = (data.get("preset_code") or "").strip()
        replace_existing = bool(data.get("replace_existing"))
        if not property_id or not code:
            raise HTTPException(400, "property_id and preset_code required")
        preset = PRESETS.get(code)
        if not preset:
            raise HTTPException(404, "Preset not found")

        if replace_existing:
            await db.tax_profiles.update_many(
                {"property_id": property_id, "active": True},
                {"$set": {"active": False, "deactivated_at": datetime.now(timezone.utc).isoformat()}},
            )

        profile = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "name": preset["name"],
            "rules": preset["rules"],
            "active": True,
            "preset_code": code,
            "currency": preset.get("currency", ""),
            "notes": f"Created from preset {code} on {datetime.now(timezone.utc).date()}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("email", ""),
        }
        await db.tax_profiles.insert_one(dict(profile))
        profile.pop("_id", None)
        return {"ok": True, "profile": profile}

    @router.get("/resort-fees/templates")
    async def list_resort_templates(current_user: dict = Depends(require_roles("admin", "manager"))):
        return {"templates": RESORT_FEE_TEMPLATES}

    @router.post("/resort-fee/quick-add")
    async def quick_add_resort_fee(data: Dict,
                                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Add a resort/destination fee rule. Either appends to active profile or creates a new one."""
        property_id = (data.get("property_id") or "").strip()
        label = (data.get("label") or "Resort fee").strip()
        rate = float(data.get("rate") or 0)
        if not property_id or rate <= 0:
            raise HTTPException(400, "property_id and rate>0 required")

        rule = {
            "kind": "resort_fee", "label": label, "basis": "per_night",
            "rate": rate, "applies_to": ["room"], "included_in_rate": False,
        }
        existing = await db.tax_profiles.find_one(
            {"property_id": property_id, "active": True}, {"_id": 0}
        )
        if existing:
            await db.tax_profiles.update_one(
                {"id": existing["id"]},
                {"$push": {"rules": rule},
                 "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            return {"ok": True, "profile_id": existing["id"], "added": rule}

        # No active profile — create one.
        profile = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "name": "Resort fees",
            "rules": [rule],
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.tax_profiles.insert_one(dict(profile))
        profile.pop("_id", None)
        return {"ok": True, "profile_id": profile["id"], "added": rule}

    return router
