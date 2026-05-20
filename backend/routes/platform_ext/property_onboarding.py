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
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Optional

from auth import require_perm


STEPS = ["property", "rooms", "rates", "tax", "sample"]


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

    @router.post("/reset/{property_id}")
    async def reset(
        property_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        await db.property_onboarding.delete_one({"property_id": property_id})
        return {"ok": True}

    return router
