"""
Open Pricing (Duetto parity) — segment × channel × room-type rate matrix.

Augments existing per-property and per-room-type override system with
a multi-dimensional matrix: any combination of (segment, channel,
room_type, date) can have its own override.

Lookup precedence (highest wins):
  1. (segment, channel, room_type, date) exact match
  2. (segment, room_type, date)
  3. (channel, room_type, date)
  4. (room_type, date)              ← existing per-room-type override
  5. (date)                          ← existing property-wide override
  6. base rate

Endpoints
---------
  GET  /api/open-pricing/matrix/{property_id}?date=YYYY-MM-DD
       Returns active overrides for date grouped by dimension.
  POST /api/open-pricing/override
       Body: {property_id, room_type_id?, segment?, channel?, date, rate, reason?}
  DELETE /api/open-pricing/override/{id}
  GET  /api/open-pricing/lookup
       Body/query: property_id, date, room_type_id?, segment?, channel?
       Returns: {rate, source} — useful for booking engine / rate engine integration
  GET  /api/open-pricing/segments   — segment catalog (TRANSIENT, CORPORATE, GROUP, OTA, DIRECT, PACKAGE)
  GET  /api/open-pricing/channels   — channel catalog
"""
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException

SEGMENTS = [
    {"id": "transient",  "label": "Bireysel", "color": "#0c0a09"},
    {"id": "corporate",  "label": "Kurumsal", "color": "#1e40af"},
    {"id": "group",      "label": "Grup",     "color": "#7c3aed"},
    {"id": "package",    "label": "Paket",    "color": "#db2777"},
    {"id": "leisure",    "label": "Tatil",    "color": "#059669"},
    {"id": "government", "label": "Resmi",    "color": "#a16207"},
]

CHANNELS = [
    {"id": "direct",     "label": "Direkt Web"},
    {"id": "booking",    "label": "Booking.com"},
    {"id": "expedia",    "label": "Expedia"},
    {"id": "airbnb",     "label": "Airbnb"},
    {"id": "agoda",      "label": "Agoda"},
    {"id": "agency",     "label": "Acenta (TÜRSAB)"},
    {"id": "walk_in",    "label": "Walk-in"},
    {"id": "phone",      "label": "Telefon"},
]


def create_open_pricing_router(db, require_roles):
    router = APIRouter()

    @router.get("/open-pricing/segments")
    async def segments(_: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return {"items": SEGMENTS}

    @router.get("/open-pricing/channels")
    async def channels(_: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return {"items": CHANNELS}

    @router.get("/open-pricing/matrix/{property_id}")
    async def get_matrix(property_id: str, date: str = "",
                         _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {"property_id": property_id, "is_active": True}
        if date:
            q["date"] = date
        items = await db.open_pricing_overrides.find(q, {"_id": 0}).to_list(2000)
        return {"property_id": property_id, "date": date, "items": items,
                "count": len(items),
                "segments": SEGMENTS, "channels": CHANNELS}

    @router.post("/open-pricing/override")
    async def create_override(body: dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        prop = body.get("property_id")
        date = body.get("date")
        rate = body.get("rate")
        if not all([prop, date, rate is not None]):
            raise HTTPException(400, "property_id, date, rate required")
        # Validate segment/channel against catalogs (optional)
        seg = body.get("segment")
        ch = body.get("channel")
        if seg and seg not in {s["id"] for s in SEGMENTS}:
            raise HTTPException(400, f"Invalid segment '{seg}'")
        if ch and ch not in {c["id"] for c in CHANNELS}:
            raise HTTPException(400, f"Invalid channel '{ch}'")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": prop,
            "room_type_id": body.get("room_type_id"),
            "segment": seg,
            "channel": ch,
            "date": date,
            "rate": float(rate),
            "reason": body.get("reason", ""),
            "scope_label": _scope_label(body),
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.open_pricing_overrides.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/open-pricing/override/{override_id}")
    async def delete_override(override_id: str,
                              _: dict = Depends(require_roles("admin", "manager"))):
        r = await db.open_pricing_overrides.delete_one({"id": override_id})
        if not r.deleted_count:
            raise HTTPException(404, "Override not found")
        return {"ok": True}

    @router.post("/open-pricing/lookup")
    async def lookup(body: dict):
        """Return the best matching rate for a tuple. Public for internal use."""
        prop = body.get("property_id")
        date = body.get("date")
        rt = body.get("room_type_id")
        seg = body.get("segment")
        ch = body.get("channel")
        if not prop or not date:
            raise HTTPException(400, "property_id and date required")
        # Build query with precedence
        candidates = [
            {"property_id": prop, "date": date, "is_active": True,
             "segment": seg, "channel": ch, "room_type_id": rt,
             "_score": 100, "_source": "segment+channel+room+date"},
            {"property_id": prop, "date": date, "is_active": True,
             "segment": seg, "channel": None, "room_type_id": rt,
             "_score": 80, "_source": "segment+room+date"},
            {"property_id": prop, "date": date, "is_active": True,
             "segment": None, "channel": ch, "room_type_id": rt,
             "_score": 70, "_source": "channel+room+date"},
            {"property_id": prop, "date": date, "is_active": True,
             "segment": None, "channel": None, "room_type_id": rt,
             "_score": 60, "_source": "room+date"},
            {"property_id": prop, "date": date, "is_active": True,
             "segment": None, "channel": None, "room_type_id": None,
             "_score": 50, "_source": "property+date"},
        ]
        for c in candidates:
            score = c.pop("_score")
            source = c.pop("_source")
            doc = await db.open_pricing_overrides.find_one(c, {"_id": 0})
            if doc:
                return {"found": True, "rate": doc["rate"],
                        "source": source, "score": score,
                        "override_id": doc["id"], "scope_label": doc.get("scope_label")}
        return {"found": False, "rate": None, "source": "fallback_to_grid"}

    return router


def _scope_label(body: dict) -> str:
    parts = []
    if body.get("segment"):
        parts.append(f"seg:{body['segment']}")
    if body.get("channel"):
        parts.append(f"ch:{body['channel']}")
    if body.get("room_type_id"):
        parts.append("room-type")
    if not parts:
        return "property-wide"
    return " × ".join(parts)
