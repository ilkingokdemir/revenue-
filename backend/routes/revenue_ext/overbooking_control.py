"""
Operational Overbooking & Wash Control — rapor orta vade maddesi (b).
Kaynak + lead-time bazlı no-show/iptal modeli → günlük güvenli overbooking limiti,
walk (başka otele gönderme) risk maliyeti ve acil stop-sell tetiği.

Endpoint: GET /api/overbooking-control/{property_id}?days=14
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

NOSHOW_STATUSES = ["no_show", "no-show", "noshow"]


def create_overbooking_control_router(db, require_roles):
    router = APIRouter(prefix="/overbooking-control", tags=["overbooking-control"])

    @router.get("/{property_id}")
    async def analysis(property_id: str, days: int = 14,
                       _: dict = Depends(require_roles("admin", "manager"))):
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

    return router
