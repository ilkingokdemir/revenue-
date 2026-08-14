"""
Operational Overbooking & Wash Control — rapor orta vade maddesi (b).
Kaynak + lead-time bazlı no-show/iptal modeli → günlük güvenli overbooking limiti,
walk (başka otele gönderme) risk maliyeti ve acil stop-sell tetiği.

Endpoints:
  GET  /api/overbooking-control/{property_id}?days=14
  POST /api/overbooking-control/{property_id}/apply   ← önerilen limitleri 1 tıkla kanallara uygular
"""
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends

NOSHOW_STATUSES = ["no_show", "no-show", "noshow"]


async def _compute_analysis(db, property_id: str, days: int) -> dict:
    days = max(3, min(days, 30))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()

    # 1. Kaynak bazlı no-show + iptal oranları (180g)
    stats = {}
    async for b in db.bookings.find(
            {"property_id": property_id, "created_at": {"$gte": cutoff}},
            {"_id": 0, "source": 1, "status": 1, "check_in": 1, "created_at": 1}):
        src = (b.get("source") or "direct").lower()
        s = stats.setdefault(src, {"total": 0, "no_show": 0, "cancelled": 0})
        s["total"] += 1
        if b.get("status") in NOSHOW_STATUSES:
            s["no_show"] += 1
        elif b.get("status") == "cancelled":
            s["cancelled"] += 1
    rates = {src: {"no_show_pct": round(v["no_show"] / v["total"] * 100, 2),
                   "cancel_pct": round(v["cancelled"] / v["total"] * 100, 2),
                   "sample": v["total"]}
             for src, v in stats.items() if v["total"] >= 5}

    # 2. Kapasite ve ADR
    cap = 0
    async for rt in db.room_types.find({"property_id": property_id},
                                       {"_id": 0, "total_rooms": 1, "count": 1}):
        cap += int(rt.get("total_rooms") or rt.get("count") or 0)
    cap = cap or 20
    adr_rows = [float(b.get("rate") or 0) async for b in db.bookings.find(
        {"property_id": property_id, "rate": {"$gt": 0}}, {"_id": 0, "rate": 1}).limit(500)]
    adr = round(sum(adr_rows) / len(adr_rows), 2) if adr_rows else 100.0
    walk_cost = round(adr * 1.5 + 50, 2)  # başka otel + transfer + itibar tazminatı

    # 3. Önümüzdeki günler: beklenen no-show → güvenli limit
    today = datetime.now(timezone.utc).date()
    rows = []
    for i in range(days):
        d = (today + timedelta(days=i)).isoformat()
        sold, exp_ns = 0, 0.0
        async for b in db.bookings.find(
                {"property_id": property_id, "status": {"$nin": ["cancelled"]},
                 "check_in": {"$lte": d}, "check_out": {"$gt": d}},
                {"_id": 0, "rooms": 1, "source": 1}):
            r = int(b.get("rooms", 1) or 1)
            sold += r
            src = (b.get("source") or "direct").lower()
            exp_ns += r * (rates.get(src, {}).get("no_show_pct", 2.0) / 100)
        occ = round(sold / cap * 100, 1)
        limit = max(int(exp_ns * 0.7), 0)  # beklenen no-show'un %70'i güvenli tampon
        walk_risk = round(max(exp_ns * 0.3, 0) * walk_cost * (occ / 100), 2)
        gain = round(limit * adr, 2)
        emergency = occ >= 98 and limit == 0
        rows.append({"date": d, "rooms_sold": sold, "occupancy_pct": occ,
                     "expected_no_shows": round(exp_ns, 2),
                     "recommended_overbooking_limit": limit,
                     "expected_gain": gain, "walk_risk_cost": walk_risk,
                     "net_expected": round(gain - walk_risk, 2),
                     "emergency_stop_sell": emergency})
    alerts = [r["date"] for r in rows if r["emergency_stop_sell"]]
    return {"property_id": property_id, "capacity": cap, "adr": adr,
            "walk_cost_per_guest": walk_cost, "source_rates": rates,
            "days": rows, "emergency_dates": alerts,
            "note": "Limit = beklenen no-show × 0.7. Walk maliyeti = 1.5×ADR + 50 transfer."}


def create_overbooking_control_router(db, require_roles):
    router = APIRouter(prefix="/overbooking-control", tags=["overbooking-control"])

    @router.get("/{property_id}")
    async def analysis(property_id: str, days: int = 14,
                       _: dict = Depends(require_roles("admin", "manager"))):
        data = await _compute_analysis(db, property_id, days)
        applied = {}
        async for a in db.overbooking_limits.find(
                {"property_id": property_id, "is_active": True},
                {"_id": 0, "date": 1, "limit": 1, "applied_at": 1}):
            applied[a["date"]] = a
        for r in data["days"]:
            ap = applied.get(r["date"])
            r["applied_limit"] = ap["limit"] if ap else None
            r["applied_at"] = ap["applied_at"] if ap else None
        data["applied_count"] = sum(1 for r in data["days"] if r["applied_limit"] is not None)
        return data

    @router.post("/{property_id}/apply")
    async def apply_limits(property_id: str, body: dict = None,
                           user: dict = Depends(require_roles("admin", "manager"))):
        """Önerilen overbooking limitlerini 1 tıkla tüm kanallara uygula."""
        days = int((body or {}).get("days", 14) or 14)
        data = await _compute_analysis(db, property_id, days)
        now = datetime.now(timezone.utc).isoformat()
        applied, extra_capacity = 0, 0
        for r in data["days"]:
            limit = r["recommended_overbooking_limit"]
            await db.overbooking_limits.update_one(
                {"property_id": property_id, "date": r["date"]},
                {"$set": {"property_id": property_id, "date": r["date"],
                          "limit": limit, "capacity": data["capacity"],
                          "sell_limit": data["capacity"] + limit,
                          "is_active": True, "source": "1-click",
                          "applied_at": now, "applied_by": user.get("name") or user.get("email", "")},
                 "$setOnInsert": {"id": str(uuid.uuid4())}},
                upsert=True)
            applied += 1
            extra_capacity += limit
        await db.channel_push_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id,
            "type": "overbooking_limits", "days": applied,
            "extra_capacity": extra_capacity, "pushed_at": now,
            "channels": ["direct", "booking", "expedia", "airbnb", "agoda"],
            "pushed_by": user.get("name") or user.get("email", "")})
        return {"ok": True, "applied_days": applied, "extra_capacity": extra_capacity,
                "expected_extra_revenue": round(extra_capacity * data["adr"], 2),
                "applied_at": now}

    return router
