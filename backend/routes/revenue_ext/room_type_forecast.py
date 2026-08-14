"""
Oda Tipi Bazlı Bağımsız Forecast — rapor maddesi (d), IDeaS paritesi.
Her oda tipi için aynı-haftagünü son 8 hafta satış dağılımından bağımsız tahmin.

Endpoint: GET /api/room-type-forecast/{property_id}?days=14
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends


def create_room_type_forecast_router(db, require_roles):
    router = APIRouter(prefix="/room-type-forecast", tags=["room-type-forecast"])

    @router.get("/{property_id}")
    async def forecast(property_id: str, days: int = 14,
                       _: dict = Depends(require_roles("admin", "manager"))):
        days = max(3, min(days, 30))
        rts = await db.room_types.find(
            {"property_id": property_id},
            {"_id": 0, "id": 1, "name": 1, "total_rooms": 1, "count": 1}).to_list(30)
        today = datetime.now(timezone.utc).date()
        hist_start = (today - timedelta(days=60)).isoformat()
        horizon_end = (today + timedelta(days=days)).isoformat()

        # tek sorguda tüm ilgili rezervasyonlar → gece bazında oda tipi satışları
        sold = {}  # (date, rt_name_lower) -> rooms
        async for b in db.bookings.find(
                {"property_id": property_id, "status": {"$nin": ["cancelled"]},
                 "check_in": {"$lte": horizon_end}, "check_out": {"$gte": hist_start}},
                {"_id": 0, "check_in": 1, "check_out": 1, "rooms": 1, "room_type": 1}):
            try:
                ci = datetime.fromisoformat(b["check_in"]).date()
                co = datetime.fromisoformat(b["check_out"]).date()
            except (ValueError, KeyError, TypeError):
                continue
            rtn = (b.get("room_type") or "").strip().lower()
            r = int(b.get("rooms", 1) or 1)
            d = ci
            while d < co:
                key = (d.isoformat(), rtn)
                sold[key] = sold.get(key, 0) + r
                d += timedelta(days=1)

        out = []
        for rt in rts:
            name = (rt.get("name") or "").strip()
            nl = name.lower()
            cap = int(rt.get("total_rooms") or rt.get("count") or 0) or 5
            rows = []
            for i in range(days):
                d = today + timedelta(days=i)
                otb = sold.get((d.isoformat(), nl), 0)
                samples = [sold.get(((d - timedelta(days=7 * w)).isoformat(), nl), 0)
                           for w in range(1, 9)]
                avg_hist = sum(samples) / len(samples)
                fc = round(min(max(otb, avg_hist), cap), 1)
                rows.append({"date": d.isoformat(), "otb": otb,
                             "same_dow_avg": round(avg_hist, 1),
                             "forecast": fc, "capacity": cap,
                             "forecast_occ_pct": round(fc / cap * 100, 1)})
            avg_occ = round(sum(r["forecast_occ_pct"] for r in rows) / len(rows), 1)
            out.append({"room_type_id": rt.get("id"), "name": name, "capacity": cap,
                        "avg_forecast_occ_pct": avg_occ, "days": rows})
        out.sort(key=lambda x: -x["avg_forecast_occ_pct"])
        return {"property_id": property_id, "room_types": out,
                "note": "Tahmin = max(OTB, aynı-haftagünü 8 hafta ortalaması), kapasite ile sınırlı."}

    return router
