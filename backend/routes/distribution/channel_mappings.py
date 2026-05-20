"""
Channel Mappings (Iter 162) — our internal room_type / rate_plan IDs to the
channel-specific IDs (Booking.com room_id, Expedia rateplan_id, etc).

Without these mappings, rate/availability pushes would land in a void.
Every time we push rates, the outgoing payload is rewritten per-channel using
these mappings. Think of it as the "translation layer" between our PMS and the OTA.

Collections:
  - channel_mappings  {id, property_id, channel_id, kind (room|rate_plan),
                       internal_id, external_id, external_label, active}

UI: matrix showing all internal room_types × all connected channels, with
the external_id editable inline. Same for rate_plans.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, List
import uuid
import logging

logger = logging.getLogger(__name__)


def create_channel_mappings_router(db, require_roles):
    router = APIRouter()

    @router.get("/channel-mappings/{property_id}")
    async def get_mappings(property_id: str, kind: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Returns full matrix: internal items × channels × external IDs.
        kind filter: "room" or "rate_plan" (default: both).
        """
        # Internal catalog
        room_types = await db.room_types.find(
            {} if property_id == "all" else {"property_id": property_id},
            {"_id": 0},
        ).to_list(200)
        rate_plans = await db.rate_plans.find(
            {} if property_id == "all" else {"property_id": property_id},
            {"_id": 0},
        ).to_list(200)
        channels = await db.channel_connections.find(
            {} if property_id == "all" else {"property_id": property_id},
            {"_id": 0},
        ).to_list(30)

        # Existing mappings
        q = {"property_id": property_id}
        if kind:
            q["kind"] = kind
        mappings = await db.channel_mappings.find(q, {"_id": 0}).to_list(5000)

        # Index by (kind, internal_id, channel_id)
        index: Dict[str, Dict[str, Dict[str, Dict]]] = {}
        for m in mappings:
            index.setdefault(m["kind"], {}).setdefault(m["internal_id"], {})[m["channel_id"]] = m

        # Stats
        total_expected = len(channels) * (len(room_types) + len(rate_plans))
        total_mapped = sum(1 for m in mappings if m.get("external_id"))

        return {
            "property_id": property_id,
            "channels": channels,
            "room_types": room_types,
            "rate_plans": rate_plans,
            "mappings": mappings,
            "index": index,
            "stats": {
                "total_mappings_expected": total_expected,
                "total_mapped": total_mapped,
                "coverage_pct": round(total_mapped / total_expected * 100, 1) if total_expected else 0,
            },
        }

    @router.put("/channel-mappings/{property_id}/upsert")
    async def upsert_mapping(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Body: {kind: room|rate_plan, internal_id, channel_id, external_id, external_label, active}"""
        kind = data.get("kind")
        if kind not in ("room", "rate_plan"):
            raise HTTPException(400, "kind must be 'room' or 'rate_plan'")
        for f in ("internal_id", "channel_id"):
            if not data.get(f):
                raise HTTPException(400, f"{f} required")
        ext_id = (data.get("external_id") or "").strip()
        now = datetime.now(timezone.utc).isoformat()
        if not ext_id:
            # Empty external_id = remove mapping
            await db.channel_mappings.delete_one({
                "property_id": property_id, "kind": kind,
                "internal_id": data["internal_id"], "channel_id": data["channel_id"],
            })
            return {"status": "deleted"}
        res = await db.channel_mappings.update_one(
            {"property_id": property_id, "kind": kind,
             "internal_id": data["internal_id"], "channel_id": data["channel_id"]},
            {"$set": {
                "property_id": property_id, "kind": kind,
                "internal_id": data["internal_id"], "channel_id": data["channel_id"],
                "external_id": ext_id,
                "external_label": (data.get("external_label") or "").strip(),
                "active": bool(data.get("active", True)),
                "updated_at": now,
                "updated_by": current_user.get("name", ""),
            },
             "$setOnInsert": {"id": str(uuid.uuid4())}},
            upsert=True,
        )
        return {"status": "upserted", "matched": res.matched_count, "modified": res.modified_count}

    @router.delete("/channel-mappings/{mapping_id}")
    async def delete_mapping(mapping_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.channel_mappings.delete_one({"id": mapping_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    @router.post("/channel-mappings/{property_id}/bulk-set-channel")
    async def bulk_set_channel(property_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bulk write mappings for one channel at once.
        Body: {channel_id, kind, entries: [{internal_id, external_id, external_label}]}"""
        channel_id = data.get("channel_id")
        kind = data.get("kind")
        entries: List[Dict] = data.get("entries") or []
        if not channel_id or kind not in ("room", "rate_plan"):
            raise HTTPException(400, "channel_id + kind required")
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for e in entries:
            if not e.get("internal_id"):
                continue
            ext = (e.get("external_id") or "").strip()
            if not ext:
                await db.channel_mappings.delete_one({
                    "property_id": property_id, "kind": kind,
                    "internal_id": e["internal_id"], "channel_id": channel_id,
                })
            else:
                await db.channel_mappings.update_one(
                    {"property_id": property_id, "kind": kind,
                     "internal_id": e["internal_id"], "channel_id": channel_id},
                    {"$set": {
                        "property_id": property_id, "kind": kind,
                        "internal_id": e["internal_id"], "channel_id": channel_id,
                        "external_id": ext,
                        "external_label": (e.get("external_label") or "").strip(),
                        "active": True, "updated_at": now,
                        "updated_by": current_user.get("name", ""),
                    }, "$setOnInsert": {"id": str(uuid.uuid4())}},
                    upsert=True,
                )
                count += 1
        return {"upserted": count, "channel_id": channel_id, "kind": kind}

    return router
