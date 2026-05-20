"""
Channel Restrictions (Iter 160) — MinLOS / MaxLOS / CTA / CTD / StopSell per
channel × date. The missing enterprise piece of the Channel Manager.
Restrictions are sent to OTAs alongside rates. Stored per date so revenue
managers can run yield strategies like "min 3 nights for F-S on Booking.com".
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import uuid
import logging

logger = logging.getLogger(__name__)


def create_channel_restrictions_router(db, require_roles):
    router = APIRouter()

    @router.get("/channel-restrictions/{property_id}")
    async def list_restrictions(property_id: str, from_date: str = "", to_date: str = "",
                                channel_id: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Return all restrictions in the date range. Grouped by channel.
        If from/to not given, defaults to next 30 days.
        """
        now = datetime.now(timezone.utc)
        if not from_date:
            from_date = now.strftime("%Y-%m-%d")
        if not to_date:
            to_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")

        q = {"property_id": property_id, "date": {"$gte": from_date, "$lte": to_date}}
        if channel_id:
            q["channel_id"] = channel_id
        rows = await db.channel_restrictions.find(q, {"_id": 0}).to_list(5000)

        # Build date range for the grid
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range((end - start).days + 1)]

        # Channels (re-use channel connections)
        channels = await db.channel_connections.find(
            {"property_id": property_id}, {"_id": 0, "channel_id": 1, "name": 1, "color": 1, "connected": 1}
        ).to_list(30)

        # Build a sparse grid for UI
        index: Dict[str, Dict[str, Dict]] = {}
        for r in rows:
            index.setdefault(r["channel_id"], {})[r["date"]] = r

        return {
            "from_date": from_date, "to_date": to_date,
            "dates": dates,
            "channels": channels,
            "restrictions": rows,
            "index": index,
            "count": len(rows),
        }

    @router.put("/channel-restrictions/{property_id}/bulk")
    async def bulk_upsert(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bulk upsert restrictions across a date range × channel list.
        Body: {
          from_date, to_date,
          channel_ids: [str],
          room_type_id: "all" | "<room_type_id>",
          min_los, max_los,  // null to leave unchanged
          closed_to_arrival, closed_to_departure, stop_sell,  // null = unchanged
          days_of_week: [0-6]  // optional, default all
        }
        Returns count of upserts.
        """
        from_date = data.get("from_date")
        to_date = data.get("to_date")
        if not from_date or not to_date:
            raise HTTPException(400, "from_date and to_date required")
        channel_ids: List[str] = data.get("channel_ids") or []
        if not channel_ids:
            raise HTTPException(400, "channel_ids required (non-empty)")

        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        if end < start:
            raise HTTPException(400, "to_date < from_date")

        dow_filter = set(data.get("days_of_week") or list(range(7)))
        room_type_id = data.get("room_type_id") or "all"
        now = datetime.now(timezone.utc).isoformat()

        count = 0
        updates = {"updated_at": now, "updated_by": current_user.get("name", "")}
        for field in ("min_los", "max_los"):
            if data.get(field) is not None:
                updates[field] = int(data[field])
        for field in ("closed_to_arrival", "closed_to_departure", "stop_sell"):
            if data.get(field) is not None:
                updates[field] = bool(data[field])

        for i in range((end - start).days + 1):
            d = start + timedelta(days=i)
            if d.weekday() not in dow_filter:
                continue
            ds = d.strftime("%Y-%m-%d")
            for ch in channel_ids:
                res = await db.channel_restrictions.update_one(
                    {"property_id": property_id, "channel_id": ch,
                     "date": ds, "room_type_id": room_type_id},
                    {"$set": updates,
                     "$setOnInsert": {"id": str(uuid.uuid4())}},
                    upsert=True,
                )
                count += res.upserted_id is not None or res.modified_count
        return {"upserted": count, "from_date": from_date, "to_date": to_date,
                "channels": len(channel_ids)}

    @router.delete("/channel-restrictions/{restriction_id}")
    async def delete_one(restriction_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.channel_restrictions.delete_one({"id": restriction_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    @router.post("/channel-restrictions/{property_id}/clear-range")
    async def clear_range(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Clear all restrictions in a range. Body: {from_date, to_date, channel_ids?}"""
        q = {
            "property_id": property_id,
            "date": {"$gte": data.get("from_date"), "$lte": data.get("to_date")},
        }
        if data.get("channel_ids"):
            q["channel_id"] = {"$in": data["channel_ids"]}
        res = await db.channel_restrictions.delete_many(q)
        return {"deleted": res.deleted_count}

    return router
