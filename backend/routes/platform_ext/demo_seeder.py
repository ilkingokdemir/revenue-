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


# Senaryo profilleri — count/fiyat çarpanı/tarih dağılımı/kanal ve grup davranışı
SCENARIOS = {
    "balanced": {"count": 25, "rate_mult": (0.88, 1.12), "offset": (-14, 45), "cancel_pct": 0.08},
    "high_season": {"count": 45, "rate_mult": (1.15, 1.45), "offset": (-7, 21), "cancel_pct": 0.03},
    "low_occupancy": {"count": 8, "rate_mult": (0.75, 0.95), "offset": (-14, 60), "cancel_pct": 0.15},
    "group_heavy": {"count": 30, "rate_mult": (0.85, 1.05), "offset": (-7, 45), "cancel_pct": 0.05},
}

GROUP_NAMES = [
    ("TechSummit 2026 Konferansı", "groups@techsummit.example"),
    ("Yilmaz Ailesi Düğünü", "wedding@yilmaz.example"),
    ("EuroTour Seyahat Acentesi", "ops@eurotour.example"),
    ("FC United Takım Kampı", "team@fcunited.example"),
]


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
        count: int = 0,
        scenario: str = "balanced",
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        if scenario not in SCENARIOS:
            raise HTTPException(422, f"scenario: {'|'.join(SCENARIOS)}")
        prof = SCENARIOS[scenario]
        count = max(1, min(int(count or prof["count"]), 200))

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

        for i in range(count):
            is_group = scenario == "group_heavy" and i < int(count * 0.6)
            if is_group:
                grp = GROUP_NAMES[i % len(GROUP_NAMES)]
                guest = (grp[0], grp[1], "+90 850 000 0000", "TR")
            else:
                guest = random.choice(GUESTS)
            room = random.choice(rooms)
            # Senaryoya göre check-in penceresi
            offset = random.randint(*prof["offset"])
            check_in_date = today + timedelta(days=offset)
            los = _pick_los()
            check_out_date = check_in_date + timedelta(days=los)
            check_in = check_in_date.isoformat()
            check_out = check_out_date.isoformat()
            adults = random.choices([1, 2, 2, 2, 3, 4], weights=[10, 25, 25, 20, 12, 8])[0]
            children = random.choices([0, 0, 0, 1, 2], weights=[55, 20, 10, 10, 5])[0]
            rooms_booked = random.randint(2, 4) if is_group else 1

            base_price = float(room.get("base_price") or 120)
            nightly = round(base_price * random.uniform(*prof["rate_mult"]), 2)
            total_price = round(nightly * los * rooms_booked, 2)

            bstatus = _status_for(check_in, check_out, today_iso)
            if bstatus == "cancelled" and random.random() > prof["cancel_pct"] / 0.08:
                bstatus = "confirmed"
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
                "channel": "group" if is_group else _pick_channel(),
                "source": "demo_seed",
                "is_demo": True,
                "is_group": is_group,
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
            "scenario": scenario,
            "property_id": property_id,
            "currency": currency,
            "date_range": {"from": (today - timedelta(days=14)).isoformat(),
                           "to": (today + timedelta(days=45)).isoformat()},
            "sample": sample,
        }

    @router.post("/compare/{property_id}")
    async def compare_scenarios(
        property_id: str,
        a: str = "high_season",
        b: str = "low_occupancy",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        """İki senaryoyu bellek-içi simüle eder (DB'ye yazmaz) — 30 günlük gelir/doluluk kıyası."""
        if a not in SCENARIOS or b not in SCENARIOS:
            raise HTTPException(422, f"a/b: {'|'.join(SCENARIOS)}")
        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        if not rooms:
            raise HTTPException(400, "Önce en az bir oda tipi ekleyin")
        total_rooms = await db.rooms.count_documents({"property_id": property_id})
        if not total_rooms:
            total_rooms = sum(int(r.get("total_rooms") or 0) for r in rooms) or 10
        today = datetime.now(timezone.utc).date()
        days = [(today + timedelta(days=i)).isoformat() for i in range(30)]

        def simulate(scenario: str) -> dict:
            prof = SCENARIOS[scenario]
            rng = random.Random(f"{property_id}-{scenario}")
            occ = {d: 0 for d in days}
            rev = {d: 0.0 for d in days}
            for i in range(prof["count"]):
                is_group = scenario == "group_heavy" and i < int(prof["count"] * 0.6)
                room = rng.choice(rooms)
                offset = rng.randint(*prof["offset"])
                ci = today + timedelta(days=offset)
                los = rng.choices([1, 2, 3, 4, 5, 7], weights=[20, 35, 22, 12, 6, 5])[0]
                rooms_booked = rng.randint(2, 4) if is_group else 1
                nightly = float(room.get("base_price") or 120) * rng.uniform(*prof["rate_mult"])
                for n in range(los):
                    d = (ci + timedelta(days=n)).isoformat()
                    if d in occ:
                        occ[d] = min(occ[d] + rooms_booked, total_rooms)
                        rev[d] += nightly * rooms_booked
            total_rev = sum(rev.values())
            occupied_nights = sum(occ.values())
            return {"scenario": scenario,
                    "daily_occ_pct": [round(occ[d] * 100 / total_rooms, 1) for d in days],
                    "daily_rev": [round(rev[d], 2) for d in days],
                    "total_rev": round(total_rev, 2),
                    "avg_occ_pct": round(occupied_nights * 100 / (total_rooms * len(days)), 1),
                    "adr": round(total_rev / occupied_nights, 2) if occupied_nights else 0}

        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "currency": 1})
        return {"property_id": property_id, "days": days, "total_rooms": total_rooms,
                "currency": (prop or {}).get("currency", "GBP"),
                "a": simulate(a), "b": simulate(b)}

    @router.post("/apply-scenario/{property_id}")
    async def apply_scenario(
        property_id: str,
        payload: dict,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """Kazanan senaryodan 30 günlük fiyat ÖNERİSİ üretir (pending batch — fiyatlara henüz dokunmaz)."""
        scenario = payload.get("scenario") or "high_season"
        if scenario not in SCENARIOS:
            raise HTTPException(422, f"scenario: {'|'.join(SCENARIOS)}")
        prof = SCENARIOS[scenario]
        rooms = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        if not rooms:
            raise HTTPException(400, "Önce en az bir oda tipi ekleyin")
        total_rooms = await db.rooms.count_documents({"property_id": property_id}) or \
            sum(int(r.get("total_rooms") or 0) for r in rooms) or 10
        today = datetime.now(timezone.utc).date()
        # senaryonun günlük doluluk profili (compare ile aynı deterministik simülasyon)
        rng = random.Random(f"{property_id}-{scenario}")
        occ = {}
        for i in range(prof["count"]):
            is_group = scenario == "group_heavy" and i < int(prof["count"] * 0.6)
            offset = rng.randint(*prof["offset"])
            ci = today + timedelta(days=offset)
            los = rng.choices([1, 2, 3, 4, 5, 7], weights=[20, 35, 22, 12, 6, 5])[0]
            rb = rng.randint(2, 4) if is_group else 1
            _ = rng.choice(rooms), rng.uniform(*prof["rate_mult"])
            for n in range(los):
                d = (ci + timedelta(days=n)).isoformat()
                occ[d] = occ.get(d, 0) + rb
        mult_mid = (prof["rate_mult"][0] + prof["rate_mult"][1]) / 2
        items = []
        for i in range(30):
            ds = (today + timedelta(days=i)).isoformat()
            occ_pct = min(occ.get(ds, 0) * 100 / total_rooms, 100)
            demand_factor = 0.95 + (occ_pct / 100) * 0.25
            for rt in rooms:
                base = float(rt.get("base_rate") or rt.get("base_price") or 120)
                cur_doc = await db.rate_overrides.find_one(
                    {"property_id": property_id, "date": ds, "room_type_id": rt.get("id", "")},
                    {"_id": 0, "custom_rate": 1}, sort=[("updated_at", -1)])
                current = float(cur_doc["custom_rate"]) if cur_doc and cur_doc.get("custom_rate") else base
                suggested = round(base * mult_mid * demand_factor, 2)
                items.append({"date": ds, "room_type_id": rt.get("id", ""), "room_name": rt.get("name", ""),
                              "current_rate": round(current, 2), "suggested_rate": suggested,
                              "change_pct": round((suggested - current) * 100 / current, 1) if current else 0})
        batch = {"id": str(uuid.uuid4()), "property_id": property_id, "scenario": scenario,
                 "status": "pending", "created_by": current_user.get("email", ""),
                 "created_at": datetime.now(timezone.utc).isoformat(), "items": items}
        await db.scenario_rate_suggestions.insert_one({**batch})
        avg_change = round(sum(i["change_pct"] for i in items) / len(items), 1) if items else 0
        return {"batch_id": batch["id"], "scenario": scenario, "days": 30, "rooms": len(rooms),
                "suggestions": len(items), "avg_change_pct": avg_change,
                "preview": items[:6]}

    @router.post("/apply-scenario/{property_id}/confirm")
    async def confirm_scenario(
        property_id: str,
        payload: dict,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """Onaylanan öneri batch'ini RMS fiyatlarına (rate_overrides) yazar."""
        batch = await db.scenario_rate_suggestions.find_one(
            {"id": payload.get("batch_id"), "property_id": property_id, "status": "pending"}, {"_id": 0})
        if not batch:
            raise HTTPException(404, "Bekleyen öneri bulunamadı")
        now = datetime.now(timezone.utc).isoformat()
        for it in batch["items"]:
            await db.rate_overrides.update_one(
                {"property_id": property_id, "date": it["date"], "room_type_id": it["room_type_id"]},
                {"$set": {"property_id": property_id, "room_type_id": it["room_type_id"],
                          "date": it["date"], "custom_rate": it["suggested_rate"],
                          "set_by": "scenario-simulator",
                          "reason": f"🏆 {batch['scenario']} senaryosu simülasyonundan onaylandı",
                          "updated_at": now}}, upsert=True)
        await db.scenario_rate_suggestions.update_one(
            {"id": batch["id"]}, {"$set": {"status": "applied", "applied_at": now}})
        return {"ok": True, "applied": len(batch["items"]), "scenario": batch["scenario"]}

    @router.post("/clear/{property_id}")
    async def clear(
        property_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        r = await db.bookings.delete_many({"property_id": property_id, "is_demo": True})
        # Also clear any demo folio charges if attached (none today — placeholder)
        await db.folio_charges.delete_many({"is_demo": True})
        return {"ok": True, "deleted": r.deleted_count}

    @router.post("/seed-occupancy/{property_id}")
    async def seed_occupancy(
        property_id: str,
        occupancy: int = 65,
        days: int = 30,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """Generate a realistic last-N-day booking distribution that hits a target
        occupancy percentage. Used to populate the Robot Performance Report and any
        other revenue dashboards with believable seed data so the `actual` occupancy
        badge lights up green during demos.

        Body params (querystring):
          - occupancy: target occupancy %, clamped to 1–100 (default 65)
          - days: trailing window length in days, max 90 (default 30)
        """
        occupancy = max(1, min(int(occupancy or 65), 100))
        days = max(1, min(int(days or 30), 90))
        occ_factor = occupancy / 100.0

        rooms = await db.room_types.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        if not rooms:
            raise HTTPException(400, "Add at least one room type before seeding demo data")

        total_rooms = sum(int(r.get("total_rooms", 0) or 0) for r in rooms) or 10
        target_rn = round(total_rooms * days * occ_factor)
        if target_rn <= 0:
            return {"ok": True, "created": 0, "note": "target_room_nights=0"}

        prop = await db.properties.find_one(
            {"id": property_id}, {"_id": 0, "currency": 1}
        )
        currency = (prop or {}).get("currency", "GBP")

        today = datetime.now(timezone.utc).date()
        window_start = today - timedelta(days=days)
        produced_rn = 0
        inserts = []
        guard = 0
        # Generate bookings until we hit target room-nights. Each booking
        # consumes (los × rooms_booked) room-nights from the window.
        while produced_rn < target_rn and guard < 4 * target_rn:
            guard += 1
            guest = random.choice(GUESTS)
            room = random.choice(rooms)
            los = _pick_los()
            # Random check-in inside window such that the full stay still fits
            max_ci_offset = max(1, days - 1)
            ci_offset = random.randint(0, max_ci_offset)
            check_in_date = window_start + timedelta(days=ci_offset)
            check_out_date = check_in_date + timedelta(days=los)
            # Clip room-nights to the analysis window so produced_rn ≈ target_rn
            overlap = max(0, min((check_out_date - max(check_in_date, window_start)).days, days - ci_offset))
            if overlap <= 0:
                continue

            adults = random.choices([1, 2, 2, 2, 3, 4], weights=[10, 25, 25, 20, 12, 8])[0]
            children = random.choices([0, 0, 0, 1, 2], weights=[55, 20, 10, 10, 5])[0]
            rooms_booked = 1

            base_price = float(room.get("base_rate") or room.get("base_price") or 120)
            nightly = round(base_price * random.uniform(0.92, 1.18), 2)
            total_price = round(nightly * los * rooms_booked, 2)

            # Always "checked_out" for historical demo data so finance/occupancy
            # treats it as realized revenue.
            bstatus = "checked_out"
            doc = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "room_type_id": room["id"],
                "guest_name": guest[0],
                "guest_email": guest[1],
                "guest_phone": guest[2],
                "guest_country": guest[3],
                "check_in": check_in_date.isoformat(),
                "check_out": check_out_date.isoformat(),
                "adults": adults,
                "children": children,
                "rooms": rooms_booked,
                "total_price": total_price,
                "currency": currency,
                "status": bstatus,
                "payment_status": "paid",
                "channel": _pick_channel(),
                "source": "demo_seed_occupancy",
                "is_demo": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user.get("email", "demo-seeder"),
            }
            inserts.append(doc)
            produced_rn += overlap * rooms_booked

        if inserts:
            await db.bookings.insert_many([dict(d) for d in inserts])

        return {
            "ok": True,
            "created": len(inserts),
            "property_id": property_id,
            "target_room_nights": target_rn,
            "produced_room_nights": produced_rn,
            "target_occupancy_pct": occupancy,
            "actual_occupancy_pct": round((produced_rn / (total_rooms * days)) * 100, 1),
            "window": {"from": window_start.isoformat(), "to": today.isoformat()},
        }

    return router
