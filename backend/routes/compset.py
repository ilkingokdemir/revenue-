"""
Compset (Competitive Set) Auto-Discovery — find nearby hotels using
property location and type. Stores a competitive set per property.
Refresh weekly via cron job.

Endpoints:
  GET   /api/compset/{property_id}              — list competitive set
  POST  /api/compset/{property_id}/discover     — auto-discover nearby competitors
  POST  /api/compset/{property_id}/add          — manually add competitor
  DELETE /api/compset/{property_id}/{comp_id}   — remove from set
  GET   /api/compset/{property_id}/snapshot     — last rate snapshot
"""
from datetime import datetime, timezone
import random
import uuid
from fastapi import APIRouter, Depends, HTTPException


# Mock competitor pool (in real impl, source from OTA Insight, Lighthouse, or web scraping)
MOCK_COMPETITORS = [
    {"name": "The Boutique House", "stars": 4, "rooms": 80},
    {"name": "Grand Palace Hotel", "stars": 5, "rooms": 220},
    {"name": "City Inn Express", "stars": 3, "rooms": 60},
    {"name": "Harbor View Suites", "stars": 4, "rooms": 120},
    {"name": "Heritage Manor", "stars": 5, "rooms": 50},
    {"name": "Modern Loft Hotel", "stars": 4, "rooms": 95},
]


def create_compset_router(db, require_roles):
    router = APIRouter(prefix="/compset")

    @router.get("/{property_id}")
    async def list_compset(property_id: str,
                           _: dict = Depends(require_roles("admin", "manager"))):
        comp = await db.compset.find({"property_id": property_id}, {"_id": 0}) \
                               .sort("added_at", -1).to_list(100)
        return {"property_id": property_id, "competitors": comp, "count": len(comp)}

    @router.post("/{property_id}/discover")
    async def discover_compset(property_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Auto-discover nearby competitors based on property location & type.

        For now uses a mock pool — production version queries an external API
        (OTA Insight, Google Places, Booking.com nearby search)."""
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        if not prop:
            raise HTTPException(404, "Property not found")
        existing = {c["name"] for c in await db.compset.find({"property_id": property_id},
                                                              {"_id": 0, "name": 1}).to_list(100)}
        now = datetime.now(timezone.utc).isoformat()
        # Pick 5 random mock competitors not already in set
        candidates = [c for c in MOCK_COMPETITORS if c["name"] not in existing]
        random.shuffle(candidates)
        added = []
        for c in candidates[:5]:
            doc = {
                "id": str(uuid.uuid4()), "property_id": property_id,
                **c,
                "source": "auto-discover",
                "distance_km": round(random.uniform(0.2, 5.0), 2),
                "added_by": current_user.get("name", ""), "added_at": now,
            }
            await db.compset.insert_one(doc)
            added.append({k: doc[k] for k in ("id", "name", "stars", "distance_km")})
        return {"added": added, "count": len(added)}

    @router.post("/{property_id}/add")
    async def add_competitor(property_id: str, body: dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        if not body.get("name"):
            raise HTTPException(400, "name required")
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), "property_id": property_id, **body,
               "source": "manual", "added_by": current_user.get("name", ""), "added_at": now}
        await db.compset.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/{property_id}/{comp_id}")
    async def remove_competitor(property_id: str, comp_id: str,
                                _: dict = Depends(require_roles("admin", "manager"))):
        r = await db.compset.delete_one({"property_id": property_id, "id": comp_id})
        return {"deleted": r.deleted_count}

    @router.get("/{property_id}/snapshot")
    async def snapshot(property_id: str,
                       _: dict = Depends(require_roles("admin", "manager"))):
        """Last known rates for each competitor (stub — would call scanner in prod)."""
        comp = await db.compset.find({"property_id": property_id}, {"_id": 0}).to_list(100)
        for c in comp:
            # In real implementation, pull from market_scanner_snapshots
            c["last_rate"] = round(80 + random.uniform(-15, 80), 2)
            c["last_availability"] = random.choice(["available", "limited", "sold-out"])
            c["last_scanned_at"] = datetime.now(timezone.utc).isoformat()
        return {"property_id": property_id, "competitors": comp}

    return router
