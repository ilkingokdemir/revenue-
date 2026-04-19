"""
Demo Data Seeder
----------------
One-click generator that populates a property with realistic bookings across
a ±45 day window so new accounts immediately see populated calendars, finance
dashboards, and charts. All records are tagged with is_demo=True for one-click
cleanup.

Endpoints (/api/demo-seeder/*):
- POST /seed/{property_id}?count=20 → create N realistic bookings
- POST /clear/{property_id}          → delete every demo record
- GET  /status/{property_id}         → { demo_booking_count }
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import require_perm


GUESTS = [
    ("James Whitfield", "james.w@guest.example", "+44 7700 900111", "GB"),
    ("Sofia Rossi", "s.rossi@guest.example", "+39 331 555 1234", "IT"),
    ("Aiko Tanaka", "aiko.t@guest.example", "+81 90 1234 5678", "JP"),
    ("Lukas Brandt", "l.brandt@guest.example", "+49 176 22334455", "DE"),
    ("Marion Dubois", "marion.d@guest.example", "+33 6 12 34 56 78", "FR"),
    ("Carlos Vega", "c.vega@guest.example", "+34 611 223 344", "ES"),
    ("Noah Bergström", "noah.b@guest.example", "+46 70 123 4567", "SE"),
    ("Emma Jóhannsdóttir", "emma.j@guest.example", "+354 660 1234", "IS"),
    ("Priya Mehta", "p.mehta@guest.example", "+91 98200 12345", "IN"),
    ("Daniel O'Sullivan", "d.osullivan@guest.example", "+353 87 123 4567", "IE"),
    ("Chen Wei", "w.chen@guest.example", "+86 139 0000 1234", "CN"),
    ("Anna Kowalska", "a.kowalska@guest.example", "+48 600 123 456", "PL"),
    ("Mehmet Yilmaz", "m.yilmaz@guest.example", "+90 532 123 4567", "TR"),
    ("Isabela Santos", "i.santos@guest.example", "+55 21 91234 5678", "BR"),
    ("Oliver Thompson", "o.thompson@guest.example", "+44 7700 900222", "GB"),
    ("Zara Ahmed", "z.ahmed@guest.example", "+971 50 123 4567", "AE"),
    ("Helena Novak", "h.novak@guest.example", "+420 602 123 456", "CZ"),
    ("Viktor Popov", "v.popov@guest.example", "+7 903 123 45 67", "RU"),
]

# Weighted channel distribution (must sum to 100)
CHANNELS = [
    ("direct",       30),
    ("booking_com",  35),
    ("expedia",      15),
    ("airbnb",       10),
    ("walk_in",       5),
    ("corporate",     5),
]


def _pick_channel() -> str:
    roll = random.randint(1, 100)
    total = 0
    for name, w in CHANNELS:
        total += w
        if roll <= total:
            return name
    return "direct"


def _pick_los() -> int:
    """Realistic LOS distribution: mostly 1-2 nights, long tail to 7."""
    return random.choices([1, 2, 3, 4, 5, 7], weights=[20, 35, 22, 12, 6, 5])[0]


def _status_for(check_in: str, check_out: str, today: str) -> str:
    if check_out < today:
        return "checked_out"
    if check_in <= today <= check_out:
        return "checked_in"
    # Small chance of cancellation on future bookings
    if random.random() < 0.08:
        return "cancelled"
    return "confirmed"


def _payment_status(booking_status: str) -> str:
    if booking_status in ("checked_out", "checked_in"):
        return "paid"
    if booking_status == "cancelled":
        return random.choice(["refunded", "unpaid"])
    # Future: pre-paid or pay-at-property
    return random.choice(["paid", "paid", "partial", "unpaid"])


def create_demo_seeder_router(db):
    router = APIRouter(prefix="/demo-seeder")

    @router.get("/status/{property_id}")
    async def status(
        property_id: str,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        n = await db.bookings.count_documents({"property_id": property_id, "is_demo": True})
        return {"property_id": property_id, "demo_booking_count": n}

    @router.post("/seed/{property_id}")
    async def seed(
        property_id: str,
        count: int = 20,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        count = max(1, min(int(count or 20), 200))

        # Need at least one room type
        rooms = await db.room_types.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        if not rooms:
            raise HTTPException(400, "Add at least one room type before seeding demo data")

        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "currency": 1, "name": 1}
        )
        currency = (prop or {}).get("currency", "GBP")

        today = datetime.now(timezone.utc).date()
        today_iso = today.isoformat()
        inserts = []

        for _ in range(count):
            guest = random.choice(GUESTS)
            room = random.choice(rooms)
            # Check-in between today-14 and today+45
            offset = random.randint(-14, 45)
            check_in_date = today + timedelta(days=offset)
            los = _pick_los()
            check_out_date = check_in_date + timedelta(days=los)
            check_in = check_in_date.isoformat()
            check_out = check_out_date.isoformat()
            adults = random.choices([1, 2, 2, 2, 3, 4], weights=[10, 25, 25, 20, 12, 8])[0]
            children = random.choices([0, 0, 0, 1, 2], weights=[55, 20, 10, 10, 5])[0]
            rooms_booked = 1

            base_price = float(room.get("base_price") or 120)
            # Small ±12% noise on nightly rate
            nightly = round(base_price * random.uniform(0.88, 1.12), 2)
            total_price = round(nightly * los * rooms_booked, 2)

            bstatus = _status_for(check_in, check_out, today_iso)
            pstatus = _payment_status(bstatus)

            doc = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "room_type_id": room["id"],
                "guest_name": guest[0],
                "guest_email": guest[1],
                "guest_phone": guest[2],
                "guest_country": guest[3],
                "check_in": check_in,
                "check_out": check_out,
                "adults": adults,
                "children": children,
                "rooms": rooms_booked,
                "total_price": total_price,
                "currency": currency,
                "status": bstatus,
                "payment_status": pstatus,
                "channel": _pick_channel(),
                "source": "demo_seed",
                "is_demo": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user.get("email", "demo-seeder"),
            }
            inserts.append(doc)

        await db.bookings.insert_many([dict(d) for d in inserts])

        # Drop _id added by Mongo so we can return a preview sample
        sample = []
        for d in inserts[:3]:
            d.pop("_id", None)
            sample.append(d)

        return {
            "ok": True,
            "created": len(inserts),
            "property_id": property_id,
            "currency": currency,
            "date_range": {"from": (today - timedelta(days=14)).isoformat(),
                           "to": (today + timedelta(days=45)).isoformat()},
            "sample": sample,
        }

    @router.post("/clear/{property_id}")
    async def clear(
        property_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        r = await db.bookings.delete_many({"property_id": property_id, "is_demo": True})
        # Also clear any demo folio charges if attached (none today — placeholder)
        await db.folio_charges.delete_many({"is_demo": True})
        return {"ok": True, "deleted": r.deleted_count}

    return router
