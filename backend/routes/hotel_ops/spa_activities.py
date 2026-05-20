"""
Spa & Activities Booking — services, providers, time-slots, allocations.

Endpoints:
  GET   /api/spa/services                       — list services
  POST  /api/spa/services                       — create service
  GET   /api/spa/providers                      — list therapists/instructors
  POST  /api/spa/providers                      — create provider
  GET   /api/spa/bookings                       — list bookings
  POST  /api/spa/bookings                       — create booking with auto-allocate
  PATCH /api/spa/bookings/{id}                  — update / cancel
  GET   /api/spa/schedule                       — daily schedule view
"""
from datetime import datetime, timezone, timedelta
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class ServiceIn(BaseModel):
    name: str
    category: str = "spa"       # spa | activity | fitness | tour
    duration_minutes: int = 60
    price: float = 0
    description: str = ""
    property_id: str = "all"
    skills_required: list = []
    active: bool = True


class ProviderIn(BaseModel):
    name: str
    role: str = "therapist"
    property_id: str = "all"
    skills: list = []
    working_hours: dict = {}    # {"mon": "09:00-18:00", ...}
    active: bool = True


class SpaBookingIn(BaseModel):
    service_id: str
    guest_name: str
    guest_email: str = ""
    booking_ref: str = ""
    start_at: str               # ISO datetime
    provider_id: str = ""       # if empty → auto-allocate
    notes: str = ""


def create_spa_router(db, require_roles):
    router = APIRouter(prefix="/spa")

    @router.get("/services")
    async def list_services(property_id: str = "", active_only: bool = True,
                            _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["$or"] = [{"property_id": property_id}, {"property_id": "all"}]
        if active_only:
            q["active"] = True
        services = await db.spa_services.find(q, {"_id": 0}).sort("name", 1).to_list(200)
        return {"services": services, "count": len(services)}

    @router.post("/services")
    async def create_service(body: ServiceIn,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), **body.dict(),
               "created_by": current_user.get("name", ""), "created_at": now}
        await db.spa_services.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/providers")
    async def list_providers(property_id: str = "",
                             _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["$or"] = [{"property_id": property_id}, {"property_id": "all"}]
        providers = await db.spa_providers.find(q, {"_id": 0}).sort("name", 1).to_list(200)
        return {"providers": providers, "count": len(providers)}

    @router.post("/providers")
    async def create_provider(body: ProviderIn,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), **body.dict(),
               "created_by": current_user.get("name", ""), "created_at": now}
        await db.spa_providers.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/bookings")
    async def list_spa_bookings(date: str = "", status: str = "",
                                _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: dict = {}
        if date:
            q["start_at"] = {"$regex": f"^{date}"}
        if status:
            q["status"] = status
        items = await db.spa_bookings.find(q, {"_id": 0}).sort("start_at", 1).to_list(500)
        return {"bookings": items, "count": len(items)}

    @router.post("/bookings")
    async def create_spa_booking(body: SpaBookingIn,
                                 current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        service = await db.spa_services.find_one({"id": body.service_id}, {"_id": 0})
        if not service:
            raise HTTPException(404, "Service not found")
        start = datetime.fromisoformat(body.start_at.replace("Z", "+00:00"))
        end = start + timedelta(minutes=service.get("duration_minutes", 60))
        # Auto-allocate provider if not given
        provider_id = body.provider_id
        if not provider_id:
            # Find any active provider not already booked at this slot
            providers = await db.spa_providers.find({"active": True}, {"_id": 0}).to_list(50)
            for p in providers:
                conflict = await db.spa_bookings.find_one({
                    "provider_id": p["id"],
                    "start_at": {"$lt": end.isoformat()},
                    "end_at": {"$gt": start.isoformat()},
                    "status": {"$ne": "cancelled"},
                })
                if not conflict:
                    provider_id = p["id"]
                    break
            if not provider_id:
                raise HTTPException(409, "No available providers at this time")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            **body.dict(),
            "provider_id": provider_id,
            "service_name": service["name"],
            "duration_minutes": service.get("duration_minutes", 60),
            "price": service.get("price", 0),
            "end_at": end.isoformat(),
            "status": "confirmed",
            "created_by": current_user.get("name", ""),
            "created_at": now,
        }
        await db.spa_bookings.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/bookings/{booking_id}")
    async def patch_spa_booking(booking_id: str, body: dict,
                                _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        body["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.spa_bookings.update_one({"id": booking_id}, {"$set": body})
        if r.matched_count == 0:
            raise HTTPException(404, "Booking not found")
        return {"updated": True}

    @router.get("/schedule")
    async def daily_schedule(date: str = "",
                             _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        bookings = await db.spa_bookings.find(
            {"start_at": {"$regex": f"^{date}"}, "status": {"$ne": "cancelled"}},
            {"_id": 0}
        ).sort("start_at", 1).to_list(500)
        # Group by provider
        by_provider: dict = {}
        for b in bookings:
            by_provider.setdefault(b.get("provider_id", "unassigned"), []).append(b)
        return {"date": date, "bookings": bookings, "by_provider": by_provider,
                "total_revenue": sum(b.get("price", 0) for b in bookings)}

    return router
