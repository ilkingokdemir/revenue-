"""
Guest Services — Digital Check-in Registration, Invoice/Folio Management, Scheduled Reports.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_guest_services_router(db, require_roles):
    router = APIRouter()

    # ===========================
    # 1. DIGITAL CHECK-IN / REGISTRATION CARD
    # ===========================

    @router.get("/guest-checkin/{booking_id}")
    async def get_checkin_form(booking_id: str):
        """Public endpoint — guest accesses via link (no auth required)."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        reg = await db.guest_registrations.find_one({"booking_id": booking_id}, {"_id": 0})

        room_type = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0})
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0})

        return {
            "booking": {
                "id": booking["id"],
                "guest_name": booking.get("guest_name", ""),
                "guest_email": booking.get("guest_email", ""),
                "guest_phone": booking.get("guest_phone", ""),
                "check_in": booking.get("check_in", ""),
                "check_out": booking.get("check_out", ""),
                "nights": booking.get("nights", 1),
                "adults": booking.get("adults", 1),
                "children": booking.get("children", 0),
                "room_type": room_type.get("name", "") if room_type else "",
                "status": booking.get("status", ""),
            },
            "property": {
                "name": prop.get("name", "") if prop else "",
                "id": prop.get("id", "") if prop else "",
            },
            "registration": reg,
            "completed": reg is not None and reg.get("status") == "completed",
        }

    @router.post("/guest-checkin/{booking_id}")
    async def submit_checkin(booking_id: str, data: Dict):
        """Public endpoint — guest submits registration form."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        now_iso = datetime.now(timezone.utc).isoformat()
        reg = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "property_id": booking.get("property_id", ""),
            "guest_name": data.get("guest_name", booking.get("guest_name", "")),
            "email": data.get("email", booking.get("guest_email", "")),
            "phone": data.get("phone", booking.get("guest_phone", "")),
            "nationality": data.get("nationality", ""),
            "passport_number": data.get("passport_number", ""),
            "id_type": data.get("id_type", "passport"),
            "id_number": data.get("id_number", ""),
            "date_of_birth": data.get("date_of_birth", ""),
            "address": data.get("address", ""),
            "city": data.get("city", ""),
            "country": data.get("country", ""),
            "postcode": data.get("postcode", ""),
            "emergency_contact_name": data.get("emergency_contact_name", ""),
            "emergency_contact_phone": data.get("emergency_contact_phone", ""),
            "special_requests": data.get("special_requests", ""),
            "arrival_time": data.get("arrival_time", ""),
            "vehicle_reg": data.get("vehicle_reg", ""),
            "signature": data.get("signature", ""),
            "terms_accepted": data.get("terms_accepted", False),
            "marketing_consent": data.get("marketing_consent", False),
            "status": "completed",
            "submitted_at": now_iso,
        }

        await db.guest_registrations.update_one(
            {"booking_id": booking_id}, {"$set": reg}, upsert=True
        )

        # Update booking with registration data
        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "registration_completed": True,
            "registration_at": now_iso,
        }})

        return {"status": "completed", "registration_id": reg["id"]}

    @router.get("/guest-registrations/{property_id}")
    async def list_registrations(property_id: str, limit: int = 50,
                                 current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Admin view — all guest registrations for a property."""
        query = {} if property_id == "all" else {"property_id": property_id}
        regs = await db.guest_registrations.find(query, {"_id": 0}).sort("submitted_at", -1).to_list(limit)
        total = await db.guest_registrations.count_documents(query)
        completed = await db.guest_registrations.count_documents({**query, "status": "completed"})
        return {"registrations": regs, "total": total, "completed": completed}

    @router.post("/guest-checkin/send-link/{booking_id}")
    async def send_checkin_link(booking_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Send check-in link to guest via notification log."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        link = f"/checkin/{booking_id}"
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "type": "info",
            "title": f"Check-in link sent to {booking.get('guest_name', 'Guest')}",
            "message": f"Digital registration link sent for booking {booking_id[:8]}. Check-in: {booking.get('check_in', '')}",
            "category": "guest_checkin",
            "target_user": "", "target_role": "",
            "link_to": link,
            "priority": "normal",
            "read": False,
            "created_by": current_user.get("name", "System"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {"status": "sent", "link": link, "guest_email": booking.get("guest_email", "")}

    # ===========================
    # 2. INVOICE / FOLIO MANAGEMENT
    # ===========================

    @router.get("/folio/{booking_id}")
    async def get_folio(booking_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Get full folio for a booking."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        room_type = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0})
        room = await db.rooms.find_one({"id": booking.get("room_id", "")}, {"_id": 0})
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0})

        # Get folio items (charges + payments)
        items = await db.folio_items.find({"booking_id": booking_id}, {"_id": 0}).sort("created_at", 1).to_list(100)

        # Auto-generate room charge if no items exist
        if not items:
            nights = int(booking.get("nights", 1) or 1)
            rate = float(booking.get("rate_per_night", 0) or 0)
            total = float(booking.get("total_price", 0) or 0)
            if not total and rate:
                total = rate * nights

            room_charge = {
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "type": "charge",
                "category": "room",
                "description": f"Room: {room_type.get('name', 'Room') if room_type else 'Room'} x {nights} night{'s' if nights > 1 else ''}",
                "quantity": nights,
                "unit_price": rate,
                "amount": total,
                "currency": booking.get("currency", "GBP"),
                "created_at": booking.get("created_at", datetime.now(timezone.utc).isoformat()),
                "created_by": "System",
            }
            await db.folio_items.insert_one(dict(room_charge))
            items.append(room_charge)

        total_charges = sum(i["amount"] for i in items if i.get("type") == "charge")
        total_payments = sum(i["amount"] for i in items if i.get("type") == "payment")
        total_adjustments = sum(i["amount"] for i in items if i.get("type") == "adjustment")
        balance = round(total_charges - total_payments + total_adjustments, 2)

        # Invoice number
        inv_num = f"INV-{booking_id[:8].upper()}"

        return {
            "invoice_number": inv_num,
            "booking": {
                "id": booking["id"],
                "guest_name": booking.get("guest_name", ""),
                "guest_email": booking.get("guest_email", ""),
                "check_in": booking.get("check_in", ""),
                "check_out": booking.get("check_out", ""),
                "nights": booking.get("nights", 1),
                "status": booking.get("status", ""),
                "source": booking.get("source", ""),
                "payment_status": booking.get("payment_status", "pending"),
            },
            "property": {
                "name": prop.get("name", "") if prop else "",
                "id": prop.get("id", "") if prop else "",
            },
            "room": {
                "type": room_type.get("name", "") if room_type else "",
                "name": room.get("name", "") if room else "",
                "floor": room.get("floor", "") if room else "",
            },
            "items": items,
            "totals": {
                "charges": round(total_charges, 2),
                "payments": round(total_payments, 2),
                "adjustments": round(total_adjustments, 2),
                "balance_due": balance,
            },
            "currency": booking.get("currency", "GBP"),
        }

    @router.post("/folio/{booking_id}/add-charge")
    async def add_folio_charge(booking_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Add a charge to the folio (minibar, room service, etc)."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        qty = int(data.get("quantity", 1))
        unit = float(data.get("unit_price", 0))
        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "charge",
            "category": data.get("category", "extra"),
            "description": data.get("description", "Additional charge"),
            "quantity": qty,
            "unit_price": unit,
            "amount": round(qty * unit, 2),
            "currency": booking.get("currency", "GBP"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.folio_items.insert_one(item)
        item.pop("_id", None)
        return item

    @router.post("/folio/{booking_id}/add-payment")
    async def add_folio_payment(booking_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Record a payment against the folio."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "payment",
            "category": data.get("method", "card"),
            "description": data.get("description", f"Payment ({data.get('method', 'card')})"),
            "quantity": 1,
            "unit_price": float(data.get("amount", 0)),
            "amount": float(data.get("amount", 0)),
            "currency": booking.get("currency", "GBP"),
            "reference": data.get("reference", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.folio_items.insert_one(item)
        item.pop("_id", None)

        # Update booking payment status
        folio_items = await db.folio_items.find({"booking_id": booking_id}, {"_id": 0}).to_list(100)
        total_charges = sum(i["amount"] for i in folio_items if i.get("type") == "charge")
        total_payments = sum(i["amount"] for i in folio_items if i.get("type") == "payment")
        new_status = "paid" if total_payments >= total_charges else "partial"
        await db.bookings.update_one({"id": booking_id}, {"$set": {"payment_status": new_status}})

        return item

    @router.post("/folio/{booking_id}/adjust")
    async def add_folio_adjustment(booking_id: str, data: Dict,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        """Add an adjustment (discount, refund, correction)."""
        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "adjustment",
            "category": data.get("reason", "discount"),
            "description": data.get("description", "Adjustment"),
            "quantity": 1,
            "unit_price": float(data.get("amount", 0)),
            "amount": float(data.get("amount", 0)),
            "currency": data.get("currency", "GBP"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.folio_items.insert_one(item)
        item.pop("_id", None)
        return item

    # ===========================
    # 3. SCHEDULED REPORTS
    # ===========================

    @router.get("/scheduled-reports/{property_id}")
    async def get_scheduled_reports(property_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """List all scheduled report configs."""
        query = {} if property_id == "all" else {"property_id": property_id}
        reports = await db.scheduled_reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"reports": reports}

    @router.post("/scheduled-reports/{property_id}")
    async def create_scheduled_report(property_id: str, data: Dict,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Create a new scheduled report."""
        now_iso = datetime.now(timezone.utc).isoformat()
        report = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "name": data.get("name", "Daily Report"),
            "type": data.get("type", "daily_summary"),
            "frequency": data.get("frequency", "daily"),
            "time": data.get("time", "08:00"),
            "recipients": data.get("recipients", []),
            "sections": data.get("sections", ["occupancy", "revenue", "arrivals", "departures"]),
            "enabled": data.get("enabled", True),
            "format": data.get("format", "pdf"),
            "created_by": current_user.get("name", ""),
            "created_at": now_iso,
            "last_sent": None,
        }
        await db.scheduled_reports.insert_one(report)
        report.pop("_id", None)
        return report

    @router.put("/scheduled-reports/{property_id}/{report_id}")
    async def update_scheduled_report(property_id: str, report_id: str, data: Dict,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Update a scheduled report."""
        update = {k: v for k, v in data.items() if k in [
            "name", "type", "frequency", "time", "recipients", "sections", "enabled", "format"
        ]}
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.scheduled_reports.update_one({"id": report_id}, {"$set": update})
        return {"status": "updated", "id": report_id}

    @router.delete("/scheduled-reports/{property_id}/{report_id}")
    async def delete_scheduled_report(property_id: str, report_id: str,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.scheduled_reports.delete_one({"id": report_id})
        return {"status": "deleted"}

    @router.post("/scheduled-reports/{property_id}/generate-now/{report_id}")
    async def generate_report_now(property_id: str, report_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate and return a report preview immediately."""
        report_config = await db.scheduled_reports.find_one({"id": report_id}, {"_id": 0})
        if not report_config:
            raise HTTPException(status_code=404, detail="Report not found")

        report_data = await _generate_report_data(db, property_id, report_config)

        await db.scheduled_reports.update_one(
            {"id": report_id},
            {"$set": {"last_sent": datetime.now(timezone.utc).isoformat()}}
        )

        return report_data

    @router.post("/scheduled-reports/{property_id}/preview")
    async def preview_report(property_id: str, data: Dict = {},
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate a quick preview with default sections."""
        config = {
            "type": data.get("type", "daily_summary"),
            "sections": data.get("sections", ["occupancy", "revenue", "arrivals", "departures", "housekeeping"]),
        }
        return await _generate_report_data(db, property_id, config)

    return router


async def _generate_report_data(db, property_id, config):
    """Generate report data based on config sections."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sections = config.get("sections", [])

    props_query = {} if property_id == "all" else {"id": property_id}
    props = await db.properties.find(props_query, {"_id": 0}).to_list(50)
    prop_ids = [p.get("id", "") for p in props]
    prop_name = props[0].get("name", "Hotel") if props else "Hotel"

    result = {
        "report_type": config.get("type", "daily_summary"),
        "property": prop_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": today,
        "sections": {},
    }

    bk_query = {"status": {"$nin": ["cancelled"]}}
    if property_id != "all":
        bk_query["property_id"] = property_id

    if "occupancy" in sections:
        total_rooms = 0
        for pid in prop_ids:
            total_rooms += await db.rooms.count_documents({"property_id": pid})
        if total_rooms == 0:
            for pid in prop_ids:
                rt_count = await db.room_types.count_documents({"property_id": pid})
                total_rooms += rt_count * 3

        booked_today = await db.bookings.count_documents({
            **bk_query, "check_in": {"$lte": today}, "check_out": {"$gt": today}
        })
        occ = round((booked_today / max(total_rooms, 1)) * 100)
        result["sections"]["occupancy"] = {
            "total_rooms": total_rooms, "booked": booked_today,
            "available": max(0, total_rooms - booked_today), "occupancy_pct": occ,
        }

    if "revenue" in sections:
        bookings = await db.bookings.find(
            {**bk_query, "check_in": {"$lte": today}, "check_out": {"$gt": today}},
            {"_id": 0, "total_price": 1, "rate_per_night": 1}
        ).to_list(500)
        total_rev = sum(float(b.get("rate_per_night", 0) or 0) for b in bookings)
        avg_rate = round(total_rev / max(len(bookings), 1), 2)
        result["sections"]["revenue"] = {
            "todays_revenue": round(total_rev, 2), "avg_daily_rate": avg_rate,
            "bookings_count": len(bookings),
        }

    if "arrivals" in sections:
        arrivals = await db.bookings.find(
            {**bk_query, "check_in": today}, {"_id": 0, "guest_name": 1, "room_type_id": 1, "nights": 1, "status": 1}
        ).to_list(100)
        result["sections"]["arrivals"] = {
            "count": len(arrivals),
            "guests": [{"name": a.get("guest_name", ""), "nights": a.get("nights", 1), "status": a.get("status", "")} for a in arrivals[:20]],
        }

    if "departures" in sections:
        departures = await db.bookings.find(
            {**bk_query, "check_out": today}, {"_id": 0, "guest_name": 1, "status": 1}
        ).to_list(100)
        result["sections"]["departures"] = {
            "count": len(departures),
            "guests": [{"name": d.get("guest_name", ""), "status": d.get("status", "")} for d in departures[:20]],
        }

    if "housekeeping" in sections:
        dirty = await db.rooms.count_documents({"housekeeping": "dirty"})
        clean = await db.rooms.count_documents({"housekeeping": "clean"})
        inspected = await db.rooms.count_documents({"housekeeping": "inspected"})
        result["sections"]["housekeeping"] = {
            "clean": clean, "dirty": dirty, "inspected": inspected,
        }

    return result
