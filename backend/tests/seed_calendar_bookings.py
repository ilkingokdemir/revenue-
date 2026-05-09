"""Seed fake bookings spanning the next 90 days for calendar testing.

Usage:
    cd /app/backend && python -m tests.seed_calendar_bookings
"""
import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as a stand-alone script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

GUEST_FIRST = [
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Mason", "Sophia", "Ethan",
    "Isabella", "Lucas", "Mia", "James", "Charlotte", "Aiden", "Amelia",
    "Yusuf", "Zeynep", "Mehmet", "Ayşe", "Defne", "Kerem", "Selin",
    "Hugo", "Léa", "Marco", "Giulia", "Hans", "Greta",
]
GUEST_LAST = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Yıldız", "Demir",
    "Kaya", "Şahin", "Çelik", "Rossi", "Bianchi", "Müller", "Schmidt",
]
SOURCES = [
    ("Booking.com", "BK"), ("Expedia", "EX"), ("Direct", "DI"),
    ("Airbnb", "AB"), ("Phone", "PH"), ("Walk-in", "WI"),
]
SPECIAL_REQ = [
    "", "", "", "Late check-in please", "Quiet room", "High floor",
    "Twin beds", "Allergic to feathers", "Anniversary celebration",
    "Early check-in if possible",
]
STATUSES = ["confirmed"] * 8 + ["pending"] * 2  # 80% confirmed


async def main():
    mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]

    # Properties + rooms inventory
    properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1, "currency": 1}).to_list(50)
    if not properties:
        print("No properties — abort")
        return

    inv: dict = {}
    for p in properties:
        rooms = await db.rooms.find({"property_id": p["id"]},
                                     {"_id": 0, "id": 1, "name": 1, "room_type_id": 1,
                                      "base_price": 1}).to_list(200)
        if rooms:
            inv[p["id"]] = {"prop": p, "rooms": rooms}

    if not inv:
        print("No rooms — abort")
        return

    today = datetime.now(timezone.utc).date()
    target_count = 60  # spread over 90 days
    created = 0
    inserted_ids = []

    for _ in range(target_count):
        prop_id = random.choice(list(inv.keys()))
        p = inv[prop_id]["prop"]
        rooms = inv[prop_id]["rooms"]
        room = random.choice(rooms)
        currency = p.get("currency") or "GBP"

        # Random check-in 0..85 days out, nights 1..7
        days_offset = random.randint(0, 85)
        nights = random.choice([1, 1, 2, 2, 3, 3, 4, 5, 7])
        ci = today + timedelta(days=days_offset)
        co = ci + timedelta(days=nights)

        # Skip if room is already heavily booked on this date (basic conflict avoidance)
        clash = await db.bookings.count_documents({
            "room_id": room["id"],
            "check_in": {"$lt": co.strftime("%Y-%m-%d")},
            "check_out": {"$gt": ci.strftime("%Y-%m-%d")},
            "status": {"$in": ["confirmed", "pending", "checked_in"]},
        })
        if clash > 0:
            continue

        rate = float(room.get("base_price") or random.choice([85, 95, 110, 130, 150, 180]))
        first = random.choice(GUEST_FIRST)
        last = random.choice(GUEST_LAST)
        guest = f"{first} {last}"
        src_name, src_code = random.choice(SOURCES)
        booking_ref = f"{src_code}-{uuid.uuid4().hex[:8].upper()}"
        adults = random.choice([1, 2, 2, 2, 3])
        booking_id = str(uuid.uuid4())
        booking = {
            "id": booking_id,
            "property_id": prop_id,
            "room_type_id": room.get("room_type_id", ""),
            "room_id": room["id"],
            "guest_name": guest,
            "guest_email": f"{first.lower()}.{last.lower()}@example.com",
            "guest_phone": f"+44791{random.randint(1000000, 9999999)}",
            "check_in": ci.strftime("%Y-%m-%d"),
            "check_out": co.strftime("%Y-%m-%d"),
            "nights": nights,
            "adults": adults,
            "children": random.choice([0, 0, 0, 1, 2]),
            "rooms": 1,
            "total_price": round(rate * nights, 2),
            "rate_per_night": rate,
            "currency": currency,
            "status": random.choice(STATUSES),
            "payment_status": random.choice(["paid", "paid", "pending", "deposit"]),
            "special_requests": random.choice(SPECIAL_REQ),
            "booking_ref": booking_ref,
            "source": src_name,
            "source_code": src_code,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.bookings.insert_one(booking)
        inserted_ids.append(booking_id)
        created += 1

    # Stats
    by_day: dict = {}
    for bid in inserted_ids:
        b = await db.bookings.find_one({"id": bid}, {"_id": 0, "check_in": 1, "property_id": 1})
        if b:
            by_day.setdefault(b["check_in"][:7], 0)
            by_day[b["check_in"][:7]] += 1

    print(f"\n✅ Created {created} bookings spread over the next 90 days")
    print("By month:")
    for k in sorted(by_day):
        print(f"  {k}: {by_day[k]}")


if __name__ == "__main__":
    asyncio.run(main())
