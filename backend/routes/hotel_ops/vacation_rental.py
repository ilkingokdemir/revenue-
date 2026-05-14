"""
Vacation Rental Dedicated View — Eviivo + Lighthouse parity.

A unified dashboard for short-term rental / apartment properties:
- Filter properties by property_type='apartment'
- KPI summary: total units, occupancy avg, ADR avg, RevPAR
- Owner distribution snapshot (link to owner portal)
- Calendar grid for next 30 days per unit

Single endpoint that aggregates existing collections for vacation-rental focus.

Endpoints
---------
  GET /api/vacation-rental/summary?year=YYYY    — KPI roll-up across VR properties
  GET /api/vacation-rental/units?days=30        — per-unit occupancy grid
  GET /api/vacation-rental/calendar?date=YYYY-MM-DD&days=14 — heatmap-ready calendar
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_vacation_rental_router(db, require_roles):
    router = APIRouter()

    async def _vr_properties() -> list:
        items = await db.properties.find(
            {"property_type": "apartment", "is_active": True}, {"_id": 0}
        ).to_list(500)
        return items

    @router.get("/vacation-rental/summary")
    async def summary(year: str = "",
                      _: dict = Depends(require_roles("admin", "manager"))):
        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        props = await _vr_properties()
        prop_ids = [p["id"] for p in props]
        if not prop_ids:
            return {"properties": [], "kpis": {}, "year": year}
        # Aggregate bookings
        bookings = await db.bookings.find(
            {"property_id": {"$in": prop_ids},
             "status": {"$nin": ["cancelled"]},
             "check_in": {"$regex": f"^{year}"}},
            {"_id": 0}
        ).to_list(5000)
        total_revenue = sum(float(b.get("total_price") or 0) for b in bookings)
        total_nights = sum(int(b.get("nights") or 1) for b in bookings)
        # Get total room inventory across VR properties
        rooms = await db.rooms.find(
            {"property_id": {"$in": prop_ids}, "is_active": {"$ne": False}},
            {"_id": 0, "id": 1, "property_id": 1}
        ).to_list(5000)
        available_room_nights = len(rooms) * 365
        adr = (total_revenue / total_nights) if total_nights else 0
        occupancy = (total_nights / available_room_nights) if available_room_nights else 0
        revpar = adr * occupancy
        return {
            "year": year,
            "properties": props,
            "kpis": {
                "property_count": len(props),
                "unit_count": len(rooms),
                "total_revenue": round(total_revenue, 2),
                "total_nights": total_nights,
                "occupancy_percent": round(occupancy * 100, 1),
                "adr": round(adr, 2),
                "revpar": round(revpar, 2),
                "booking_count": len(bookings),
            },
        }

    @router.get("/vacation-rental/units")
    async def units(days: int = 30,
                    _: dict = Depends(require_roles("admin", "manager"))):
        props = await _vr_properties()
        prop_ids = [p["id"] for p in props]
        rooms = await db.rooms.find(
            {"property_id": {"$in": prop_ids}, "is_active": {"$ne": False}},
            {"_id": 0}
        ).to_list(2000)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        end = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
        bookings = await db.bookings.find(
            {"property_id": {"$in": prop_ids},
             "status": {"$nin": ["cancelled"]},
             "check_in": {"$gte": today, "$lte": end}},
            {"_id": 0, "room_id": 1, "check_in": 1, "check_out": 1,
             "guest_name": 1, "total_price": 1}
        ).to_list(5000)
        # Group bookings per room
        from collections import defaultdict
        per_room = defaultdict(list)
        for b in bookings:
            per_room[b.get("room_id")].append(b)
        # Property name map
        pmap = {p["id"]: p.get("name") for p in props}
        for r in rooms:
            r["property_name"] = pmap.get(r.get("property_id"), "")
            r["bookings"] = per_room.get(r["id"], [])
            r["booked_nights"] = sum(int(b.get("nights") or 1) for b in r["bookings"])
        return {"items": rooms, "count": len(rooms), "days": days}

    @router.get("/vacation-rental/calendar")
    async def calendar(date: str = "", days: int = 14,
                       _: dict = Depends(require_roles("admin", "manager"))):
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            start = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            start = datetime.now(timezone.utc).replace(tzinfo=None)
        dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(days)]
        props = await _vr_properties()
        prop_ids = [p["id"] for p in props]
        rooms = await db.rooms.find(
            {"property_id": {"$in": prop_ids}, "is_active": {"$ne": False}},
            {"_id": 0, "id": 1, "room_number": 1, "property_id": 1}
        ).to_list(2000)
        bookings = await db.bookings.find(
            {"property_id": {"$in": prop_ids},
             "status": {"$nin": ["cancelled"]},
             "$or": [
                 {"check_in": {"$lte": dates[-1]}, "check_out": {"$gte": dates[0]}},
             ]},
            {"_id": 0, "room_id": 1, "check_in": 1, "check_out": 1,
             "guest_name": 1}
        ).to_list(5000)
        # Build grid: per room → per date → status (free/booked)
        grid = []
        pmap = {p["id"]: p.get("name") for p in props}
        for r in rooms:
            row = {
                "room_id": r["id"],
                "room_number": r.get("room_number"),
                "property_id": r["property_id"],
                "property_name": pmap.get(r["property_id"], ""),
                "cells": [],
            }
            for d in dates:
                booked = next(
                    (b for b in bookings
                     if b.get("room_id") == r["id"]
                     and (b.get("check_in") or "")[:10] <= d
                     and (b.get("check_out") or "")[:10] > d),
                    None,
                )
                row["cells"].append({
                    "date": d,
                    "status": "booked" if booked else "free",
                    "guest_name": (booked or {}).get("guest_name", ""),
                })
            grid.append(row)
        return {"dates": dates, "rooms": grid, "count": len(grid)}

    return router
