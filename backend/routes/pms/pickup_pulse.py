"""24-Hour Pickup Pulse — son 24 saatte satılan odalar ve pickup %."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from auth import require_perm

_PROJ = {"_id": 0, "booking_ref": 1, "guest_name": 1, "check_in": 1, "check_out": 1,
         "rooms": 1, "nights": 1, "total_price": 1, "currency": 1, "source": 1,
         "created_at": 1, "property_id": 1, "status": 1}


def create_pickup_pulse_router(db):
    router = APIRouter()

    @router.get("/pulse/pickup-24h")
    async def pickup_24h(property_id: str = "",
                         current_user: dict = Depends(require_perm("view_bookings", "view_dashboard", mode="any"))):
        now = datetime.now(timezone.utc)
        cut24 = (now - timedelta(hours=24)).isoformat()
        cut48 = (now - timedelta(hours=48)).isoformat()
        q = {"status": {"$nin": ["cancelled"]}}
        rooms_q = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
            rooms_q["property_id"] = property_id

        cur = await db.bookings.find({**q, "created_at": {"$gte": cut24}}, _PROJ)\
            .sort("created_at", -1).to_list(1000)
        prev = await db.bookings.find({**q, "created_at": {"$gte": cut48, "$lt": cut24}},
                                      {"_id": 0, "rooms": 1}).to_list(1000)
        total_rooms = await db.rooms.count_documents(rooms_q)

        rooms_sold = sum(int(b.get("rooms") or 1) for b in cur)
        prev_rooms_sold = sum(int(b.get("rooms") or 1) for b in prev)
        room_nights = sum(int(b.get("rooms") or 1) * int(b.get("nights") or 1) for b in cur)
        revenue = sum(float(b.get("total_price") or 0) for b in cur)

        by_source = defaultdict(int)
        by_stay_date = defaultdict(int)
        for b in cur:
            by_source[b.get("source") or "Direct"] += int(b.get("rooms") or 1)
            if b.get("check_in"):
                by_stay_date[b["check_in"]] += int(b.get("rooms") or 1)

        return {
            "rooms_sold_24h": rooms_sold,
            "prev_rooms_sold_24h": prev_rooms_sold,
            "trend": rooms_sold - prev_rooms_sold,
            "pickup_pct": round(room_nights * 100 / (total_rooms * 30), 1) if total_rooms else 0,
            "total_rooms": total_rooms,
            "room_nights_24h": room_nights,
            "revenue_24h": round(revenue, 2),
            "adr_24h": round(revenue / room_nights, 2) if room_nights else 0,
            "by_source": sorted(({"source": k, "rooms": v} for k, v in by_source.items()),
                                key=lambda x: -x["rooms"])[:6],
            "by_stay_date": sorted(({"date": k, "rooms": v} for k, v in by_stay_date.items()),
                                   key=lambda x: x["date"])[:14],
            "recent_bookings": cur[:15],
            "as_of": now.isoformat(),
        }

    return router
