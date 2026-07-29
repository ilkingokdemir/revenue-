"""
Property Onboarding — first-run wizard state tracking.
All actual resource creation goes through the existing endpoints (properties,
room_types, rate_products, tax_profiles, bookings). This module tracks
which steps a property has completed so the wizard UI can resume where the
user left off.

Collection:
- property_onboarding: { property_id, steps_completed[], completed_at?,
                         created_at, updated_at, updated_by }

Endpoints (/api/property-onboarding/*):
- GET /status/{property_id}                → { each step bool + overall }
- POST /step-complete/{property_id}/{step} → mark step done
- POST /complete/{property_id}             → mark onboarding finished
- POST /reset/{property_id}                → clear wizard state (dev/testing)
"""
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel

from auth import require_perm


STEPS = ["property", "rooms", "rates", "tax", "sample"]

VAT_DEFAULTS = {"TRY": 20, "GBP": 20, "EUR": 10, "CHF": 3.8, "USD": 0, "AED": 5, "JPY": 10}

QUICK_ROOMS = [
    {"name": "Standard Double", "bed_type": "double", "max_guests": 2, "mult": 1.0, "total_rooms": 10},
    {"name": "Deluxe King", "bed_type": "king", "max_guests": 2, "mult": 1.35, "total_rooms": 6},
    {"name": "Family Suite", "bed_type": "suite", "max_guests": 4, "mult": 1.8, "total_rooms": 4},
]

QUICK_GUESTS = [
    ("James Whitfield", "james.w@guest.example", "GB"), ("Sofia Rossi", "s.rossi@guest.example", "IT"),
    ("Aiko Tanaka", "aiko.t@guest.example", "JP"), ("Lukas Brandt", "l.brandt@guest.example", "DE"),
    ("Mehmet Yilmaz", "m.yilmaz@guest.example", "TR"), ("Marion Dubois", "marion.d@guest.example", "FR"),
    ("Zara Ahmed", "z.ahmed@guest.example", "AE"), ("Anna Kowalska", "a.kowalska@guest.example", "PL"),
]


class QuickStartIn(BaseModel):
    property_name: Optional[str] = None
    city: Optional[str] = None
    currency: Optional[str] = None
    base_price: float = 120
    seed_bookings: int = 15


def create_onboarding_router(db):
    router = APIRouter(prefix="/property-onboarding")

    async def _status_doc(property_id: str) -> dict:
        doc = await db.property_onboarding.find_one({"property_id": property_id}, {"_id": 0})
        return doc or {
            "property_id": property_id,
            "steps_completed": [],
            "completed_at": None,
        }

    @router.get("/status/{property_id}")
    async def status(
        property_id: str,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        wiz = await _status_doc(property_id)

        # Probe actual data so the wizard can detect progress made outside it
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1, "currency": 1})
        rooms_n = await db.room_types.count_documents({"property_id": property_id})
        rates_n = await db.rate_products.count_documents({"property_id": property_id})
        taxes_n = await db.tax_profiles.count_documents({"property_id": property_id})
        bookings_n = await db.bookings.count_documents({"property_id": property_id})

        has_property = bool(prop and prop.get("name"))
        steps = {
            "property": has_property or "property" in wiz["steps_completed"],
            "rooms": rooms_n > 0 or "rooms" in wiz["steps_completed"],
            "rates": rates_n > 0 or "rates" in wiz["steps_completed"],
            "tax": taxes_n > 0 or "tax" in wiz["steps_completed"],
            "sample": bookings_n > 0 or "sample" in wiz["steps_completed"],
        }
        completed_count = sum(1 for v in steps.values() if v)
        pct = int(completed_count / len(STEPS) * 100)
        return {
            "property_id": property_id,
            "steps": steps,
            "completed_count": completed_count,
            "total": len(STEPS),
            "percent": pct,
            "completed_at": wiz.get("completed_at"),
            "counts": {"rooms": rooms_n, "rate_products": rates_n,
                       "tax_profiles": taxes_n, "bookings": bookings_n},
        }

    @router.post("/step-complete/{property_id}/{step}")
    async def mark_step(
        property_id: str, step: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        if step not in STEPS:
            raise HTTPException(400, f"Unknown step. Valid: {STEPS}")
        now = datetime.now(timezone.utc).isoformat()
        await db.property_onboarding.update_one(
            {"property_id": property_id},
            {
                "$setOnInsert": {"property_id": property_id, "created_at": now},
                "$addToSet": {"steps_completed": step},
                "$set": {"updated_at": now, "updated_by": current_user.get("email", "")},
            },
            upsert=True,
        )
        return {"ok": True, "step": step}

    @router.post("/complete/{property_id}")
    async def complete(
        property_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        now = datetime.now(timezone.utc).isoformat()
        await db.property_onboarding.update_one(
            {"property_id": property_id},
            {
                "$setOnInsert": {"property_id": property_id, "created_at": now},
                "$set": {"completed_at": now, "steps_completed": STEPS,
                         "updated_at": now, "updated_by": current_user.get("email", "")},
            },
            upsert=True,
        )
        return {"ok": True, "completed_at": now}

    @router.post("/quick-start/{property_id}")
    async def quick_start(
        property_id: str,
        body: QuickStartIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """One-click setup: rooms, rate plans, tax profile and demo bookings in one shot."""
        now = datetime.now(timezone.utc).isoformat()
        created = {"rooms": 0, "rate_products": 0, "tax_profiles": 0, "bookings": 0}

        prop_update = {}
        if body.property_name:
            prop_update["name"] = body.property_name
        if body.city:
            prop_update["city"] = body.city
        if body.currency:
            prop_update["currency"] = body.currency
        if prop_update:
            await db.properties.update_one({"id": property_id}, {"$set": prop_update}, upsert=False)

        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1})
        currency = body.currency or (prop or {}).get("currency") or "GBP"
        base = max(10.0, float(body.base_price or 120))

        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        if not rooms:
            docs = []
            for r in QUICK_ROOMS:
                docs.append({
                    "id": str(uuid.uuid4()), "property_id": property_id,
                    "name": r["name"], "description": "", "max_guests": r["max_guests"],
                    "bed_type": r["bed_type"], "size_sqm": 0, "amenities": [], "photos": [],
                    "base_price": round(base * r["mult"], 2), "currency": currency,
                    "is_active": True, "total_rooms": r["total_rooms"],
                    "free_cancellation": True, "breakfast_included": True,
                    "created_at": now,
                })
            await db.room_types.insert_many([dict(d) for d in docs])
            rooms = docs
            created["rooms"] = len(docs)

        rates_n = await db.rate_products.count_documents({"property_id": property_id})
        if rates_n == 0:
            rate_docs = [
                {"id": str(uuid.uuid4()), "property_id": property_id, "name": "Best Available Rate",
                 "code": "BAR", "kind": "flex", "room_type_ids": [], "inclusions": ["breakfast"],
                 "meal_plan": "bed_breakfast", "cancellation_policy": "free_24h",
                 "cancellation_fee_pct": 0, "min_los": 1, "max_los": 30, "min_advance_days": 0,
                 "max_advance_days": 365, "active": True, "notes": "Quick Start",
                 "created_at": now, "created_by": current_user.get("email", "")},
                {"id": str(uuid.uuid4()), "property_id": property_id, "name": "Non-Refundable",
                 "code": "NR", "kind": "non_refundable", "room_type_ids": [], "inclusions": [],
                 "meal_plan": "room_only", "cancellation_policy": "non_refundable",
                 "cancellation_fee_pct": 100, "min_los": 1, "max_los": 30, "min_advance_days": 0,
                 "max_advance_days": 365, "active": True, "notes": "Quick Start",
                 "created_at": now, "created_by": current_user.get("email", "")},
            ]
            await db.rate_products.insert_many([dict(d) for d in rate_docs])
            created["rate_products"] = 2

        taxes_n = await db.tax_profiles.count_documents({"property_id": property_id})
        if taxes_n == 0:
            vat = VAT_DEFAULTS.get(currency, 10)
            rules = []
            if vat > 0:
                rules.append({"kind": "vat", "label": f"VAT {vat}%", "basis": "percent",
                              "rate": vat, "applies_to": ["room", "fnb"], "channels": [],
                              "included_in_rate": False})
            await db.tax_profiles.insert_one({
                "id": str(uuid.uuid4()), "property_id": property_id,
                "name": "Default Tax Profile", "rules": rules, "active": True,
                "notes": "Quick Start", "created_at": now,
            })
            created["tax_profiles"] = 1

        seed_n = max(0, min(int(body.seed_bookings or 0), 50))
        if seed_n:
            today = datetime.now(timezone.utc).date()
            today_iso = today.isoformat()
            inserts = []
            for _ in range(seed_n):
                guest = random.choice(QUICK_GUESTS)
                room = random.choice(rooms)
                check_in_d = today + timedelta(days=random.randint(-10, 30))
                los = random.choices([1, 2, 3, 4], weights=[25, 40, 22, 13])[0]
                check_out_d = check_in_d + timedelta(days=los)
                check_in, check_out = check_in_d.isoformat(), check_out_d.isoformat()
                nightly = round(float(room.get("base_price") or base) * random.uniform(0.9, 1.1), 2)
                if check_out < today_iso:
                    status = "checked_out"
                elif check_in <= today_iso <= check_out:
                    status = "checked_in"
                else:
                    status = "confirmed"
                inserts.append({
                    "id": str(uuid.uuid4()), "property_id": property_id,
                    "room_type_id": room["id"], "guest_name": guest[0],
                    "guest_email": guest[1], "guest_phone": "", "guest_country": guest[2],
                    "check_in": check_in, "check_out": check_out,
                    "adults": random.choice([1, 2, 2, 3]), "children": 0, "rooms": 1,
                    "total_price": round(nightly * los, 2), "currency": currency,
                    "status": status, "payment_status": "paid" if status != "confirmed" else "unpaid",
                    "channel": random.choice(["direct", "booking_com", "booking_com", "expedia", "airbnb"]),
                    "source": "quick_start", "is_demo": True,
                    "created_at": now, "created_by": current_user.get("email", "quick-start"),
                })
            await db.bookings.insert_many([dict(d) for d in inserts])
            created["bookings"] = len(inserts)

        await db.property_onboarding.update_one(
            {"property_id": property_id},
            {"$setOnInsert": {"property_id": property_id, "created_at": now},
             "$set": {"completed_at": now, "steps_completed": STEPS,
                      "updated_at": now, "updated_by": current_user.get("email", ""),
                      "quick_start": True}},
            upsert=True,
        )
        return {"ok": True, "property_id": property_id, "currency": currency, "created": created}

    @router.post("/reset/{property_id}")
    async def reset(
        property_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        await db.property_onboarding.delete_one({"property_id": property_id})
        return {"ok": True}

    return router
