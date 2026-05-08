"""
Collisions Detector — operations cockpit endpoint.

Scans all active bookings and returns same-room overlaps grouped by room.
Powers the Operations "Collisions" widget/panel so managers can spot
double-bookings across every property in one view.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from collections import defaultdict

from auth import require_perm


# Statuses we consider "active" for collision purposes — cancelled / no-show /
# checked-out bookings do not create a real occupancy conflict.
ACTIVE_STATUSES = {"pending", "confirmed", "checked_in", "hold"}


def _overlaps(a: dict, b: dict) -> bool:
    """Two date-ranges overlap if a.in < b.out AND b.in < a.out (exclusive checkout)."""
    try:
        return a["check_in"] < b["check_out"] and b["check_in"] < a["check_out"]
    except Exception:
        return False


def create_collisions_router(db):
    router = APIRouter()

    @router.get("/operations/collisions")
    async def list_collisions(
        property_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """Return every pair of overlapping bookings sharing a room.

        Response:
        {
          "scanned_bookings": 321,
          "total_collisions": 7,            # number of PAIRS in conflict
          "affected_rooms": 3,              # distinct rooms with at least one conflict
          "affected_properties": 2,
          "groups": [
            {
              "room_id": "...", "room_name": "Standard 04", "property_id": "...",
              "property_name": "Aldgate Flats",
              "collision_count": 2,
              "bookings": [ {id, booking_ref, guest_name, guest_email, check_in, check_out,
                              status, source, total_price, currency, nights} , ... ],
              "pairs": [ [booking_id_a, booking_id_b], ... ]
            }, ...
          ]
        }
        """
        query: dict = {"status": {"$in": list(ACTIVE_STATUSES)}}
        if property_id:
            query["property_id"] = property_id

        bookings = await db.bookings.find(
            query,
            {
                "_id": 0,
                "id": 1, "booking_ref": 1, "guest_name": 1, "guest_email": 1,
                "property_id": 1, "room_id": 1, "check_in": 1, "check_out": 1,
                "status": 1, "source": 1, "source_code": 1, "total_price": 1,
                "currency": 1, "nights": 1,
            }
        ).to_list(length=5000)

        # Index properties & rooms once for fast name lookup.
        prop_ids = {b.get("property_id") for b in bookings if b.get("property_id")}
        room_ids = {b.get("room_id") for b in bookings if b.get("room_id")}

        branches = await db.properties.find({"id": {"$in": list(prop_ids)}}, {"_id": 0, "id": 1, "name": 1}).to_list(length=1000)
        prop_name = {p["id"]: p.get("name", "Unknown") for p in branches}

        rooms = await db.room_types.find({"id": {"$in": list(room_ids)}}, {"_id": 0, "id": 1, "name": 1}).to_list(length=5000)
        room_name = {r["id"]: r.get("name", r["id"]) for r in rooms}

        # Group bookings by room_id
        by_room: dict = defaultdict(list)
        for b in bookings:
            rid = b.get("room_id")
            if rid:
                by_room[rid].append(b)

        groups: list = []
        total_collisions = 0
        for rid, bks in by_room.items():
            if len(bks) < 2:
                continue
            bks_sorted = sorted(bks, key=lambda x: (x.get("check_in") or ""))
            pairs = []
            colliding_ids = set()
            for i in range(len(bks_sorted)):
                for j in range(i + 1, len(bks_sorted)):
                    if _overlaps(bks_sorted[i], bks_sorted[j]):
                        pairs.append([bks_sorted[i]["id"], bks_sorted[j]["id"]])
                        colliding_ids.add(bks_sorted[i]["id"])
                        colliding_ids.add(bks_sorted[j]["id"])
            if not pairs:
                continue
            total_collisions += len(pairs)
            pid = bks[0].get("property_id")
            groups.append({
                "room_id": rid,
                "room_name": room_name.get(rid, rid),
                "property_id": pid,
                "property_name": prop_name.get(pid, "Unknown"),
                "collision_count": len(pairs),
                "bookings": [b for b in bks_sorted if b["id"] in colliding_ids],
                "pairs": pairs,
            })

        # Sort: most collisions first, then by property name
        groups.sort(key=lambda g: (-g["collision_count"], g["property_name"]))

        affected_properties = {g["property_id"] for g in groups}

        return {
            "scanned_bookings": len(bookings),
            "total_collisions": total_collisions,
            "affected_rooms": len(groups),
            "affected_properties": len(affected_properties),
            "groups": groups,
        }

    @router.get("/operations/collisions/stats")
    async def collision_stats(
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """Minimal KPI for dashboard badges."""
        query = {"status": {"$in": list(ACTIVE_STATUSES)}}
        bookings = await db.bookings.find(query, {"_id": 0, "room_id": 1, "check_in": 1, "check_out": 1, "property_id": 1}).to_list(length=5000)
        by_room: dict = defaultdict(list)
        for b in bookings:
            rid = b.get("room_id")
            if rid:
                by_room[rid].append(b)
        collisions = 0
        rooms_hit = set()
        props_hit = set()
        for rid, bks in by_room.items():
            if len(bks) < 2:
                continue
            local = 0
            for i in range(len(bks)):
                for j in range(i + 1, len(bks)):
                    if _overlaps(bks[i], bks[j]):
                        local += 1
            if local > 0:
                collisions += local
                rooms_hit.add(rid)
                if bks[0].get("property_id"):
                    props_hit.add(bks[0]["property_id"])
        return {
            "total_collisions": collisions,
            "affected_rooms": len(rooms_hit),
            "affected_properties": len(props_hit),
        }

    return router
