"""
Spa & Activity Time-Slot Booking
--------------------------------
Time-slot reservation engine for spa treatments, gym classes, golf tee-times,
restaurant reservations and any time-bound on-site service. Charges land on
the room folio (or guest credit card for non-resident bookings).

Endpoints:
  GET  /api/timeslot-services/{property_id}                 — list services
  POST /api/timeslot-services/{property_id}                  — create / update service
  DELETE /api/timeslot-services/{property_id}/{service_id}
  GET  /api/timeslot-services/{property_id}/{service_id}/availability?date=YYYY-MM-DD
  POST /api/timeslot-bookings                                — book a slot
  GET  /api/timeslot-bookings/{property_id}                  — list bookings
  POST /api/timeslot-bookings/{id}/cancel
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date, time
from typing import Dict, List, Optional
import uuid


def create_timeslot_router(db, require_roles):
    router = APIRouter()

    @router.get("/timeslot-services/{property_id}")
    async def list_services(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "spa", "fnb"))):
        rows = await db.timeslot_services.find(
            {"property_id": property_id, "active": {"$ne": False}}, {"_id": 0}
        ).sort("name", 1).to_list(100)
        return rows

    @router.post("/timeslot-services/{property_id}")
    async def upsert_service(property_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        sid = data.get("id") or str(uuid.uuid4())
        update = {
            "id": sid,
            "property_id": property_id,
            "name": data.get("name", "Untitled service"),
            "category": data.get("category", "spa"),  # spa | gym | golf | restaurant | activity
            "duration_min": int(data.get("duration_min") or 60),
            "price": float(data.get("price") or 0),
            "currency": data.get("currency", "GBP"),
            "concurrent_capacity": int(data.get("concurrent_capacity") or 1),
            "open_hour":  int(data.get("open_hour", 9)),
            "close_hour": int(data.get("close_hour", 21)),
            "weekdays":   data.get("weekdays") or [0, 1, 2, 3, 4, 5, 6],
            "buffer_min": int(data.get("buffer_min") or 0),
            "description": data.get("description", ""),
            "active": bool(data.get("active", True)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.timeslot_services.update_one(
            {"id": sid}, {"$set": update, "$setOnInsert": {"created_at": update["updated_at"]}}, upsert=True
        )
        doc = await db.timeslot_services.find_one({"id": sid}, {"_id": 0})
        return {"ok": True, "service": doc}

    @router.delete("/timeslot-services/{property_id}/{service_id}")
    async def delete_service(property_id: str, service_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.timeslot_services.update_one(
            {"id": service_id, "property_id": property_id}, {"$set": {"active": False}}
        )
        return {"ok": True}

    def _slots_for(svc: dict, on_date: date) -> List[Dict]:
        if on_date.weekday() not in svc.get("weekdays", [0,1,2,3,4,5,6]):
            return []
        slots = []
        cursor = datetime.combine(on_date, time(svc["open_hour"], 0))
        end = datetime.combine(on_date, time(svc["close_hour"], 0))
        step = timedelta(minutes=svc["duration_min"] + svc.get("buffer_min", 0))
        while cursor + timedelta(minutes=svc["duration_min"]) <= end:
            slots.append({
                "start": cursor.isoformat(),
                "end": (cursor + timedelta(minutes=svc["duration_min"])).isoformat(),
            })
            cursor += step
        return slots

    @router.get("/timeslot-services/{property_id}/{service_id}/availability")
    async def availability(property_id: str, service_id: str, date: Optional[str] = None,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "spa", "fnb"))):
        from datetime import date as _date
        target = _date.fromisoformat(date) if date else _date.today()
        svc = await db.timeslot_services.find_one({"id": service_id}, {"_id": 0})
        if not svc:
            raise HTTPException(404, "Service not found")
        all_slots = _slots_for(svc, target)
        # Pull booked
        booked = await db.timeslot_bookings.find({
            "service_id": service_id,
            "start": {"$gte": target.isoformat() + "T00:00:00",
                       "$lt":  (target + timedelta(days=1)).isoformat() + "T00:00:00"},
            "status": {"$ne": "cancelled"},
        }, {"_id": 0, "start": 1}).to_list(500)
        cap = svc.get("concurrent_capacity", 1)
        booked_count: Dict[str, int] = {}
        for b in booked:
            booked_count[b["start"]] = booked_count.get(b["start"], 0) + 1
        for s in all_slots:
            taken = booked_count.get(s["start"], 0)
            s["available"] = max(0, cap - taken)
            s["booked"] = taken
            s["full"] = s["available"] == 0
        return {"service": svc, "date": target.isoformat(), "slots": all_slots}

    @router.post("/timeslot-bookings")
    async def book_slot(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "spa", "fnb"))):
        service_id = data.get("service_id", "")
        start = (data.get("start") or "").strip()
        guest_name = (data.get("guest_name") or "").strip()
        if not service_id or not start or not guest_name:
            raise HTTPException(400, "service_id, start, guest_name required")
        svc = await db.timeslot_services.find_one({"id": service_id}, {"_id": 0})
        if not svc:
            raise HTTPException(404, "Service not found")
        # Capacity check
        existing = await db.timeslot_bookings.count_documents({
            "service_id": service_id, "start": start, "status": {"$ne": "cancelled"}
        })
        if existing >= svc.get("concurrent_capacity", 1):
            raise HTTPException(409, "Slot full")

        end_dt = datetime.fromisoformat(start) + timedelta(minutes=svc["duration_min"])
        record = {
            "id": str(uuid.uuid4()),
            "property_id": svc["property_id"],
            "service_id": service_id,
            "service_name": svc["name"],
            "category": svc.get("category", ""),
            "guest_name": guest_name,
            "guest_email": data.get("guest_email", ""),
            "booking_id": data.get("booking_id", ""),  # optional link to room booking
            "room_number": data.get("room_number", ""),
            "start": start,
            "end": end_dt.isoformat(),
            "duration_min": svc["duration_min"],
            "price": float(data.get("price") or svc.get("price") or 0),
            "currency": svc.get("currency", "GBP"),
            "charge_to": data.get("charge_to", "room"),  # room | card | cash | comp
            "notes": data.get("notes", ""),
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", "Staff"),
        }
        await db.timeslot_bookings.insert_one(dict(record))
        record.pop("_id", None)

        # If charged to room, post to folio
        if record["charge_to"] == "room" and record["booking_id"] and record["price"] > 0:
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()),
                "booking_id": record["booking_id"],
                "property_id": record["property_id"],
                "type": "charge",
                "category": record["category"] or "service",
                "description": f"{record['service_name']} · {start[:16].replace('T',' ')}",
                "amount": record["price"],
                "currency": record["currency"],
                "posted_by": current_user.get("name", "Staff"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        return {"ok": True, "booking": record}

    @router.get("/timeslot-bookings/{property_id}")
    async def list_bookings(property_id: str, days: int = 7, category: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "spa", "fnb"))):
        from_dt = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        to_dt   = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "start": {"$gte": from_dt, "$lte": to_dt}}
        if category:
            q["category"] = category
        rows = await db.timeslot_bookings.find(q, {"_id": 0}).sort("start", 1).to_list(500)
        return rows

    @router.post("/timeslot-bookings/{booking_id}/cancel")
    async def cancel_booking(booking_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "spa", "fnb"))):
        await db.timeslot_bookings.update_one({"id": booking_id}, {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancelled_by": current_user.get("name", "Staff"),
        }})
        return {"ok": True}

    return router
