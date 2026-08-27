"""730 Gün Tahmin Ufku — mevsimsellik bazlı uzun vadeli talep eğrisi (Atomize paritesi)."""
import calendar
from datetime import datetime, timezone, timedelta, date as ddate
from fastapi import APIRouter, Depends

ACTIVE = {"$nin": ["cancelled", "no_show", "pending", "pending_payment"]}


def create_forecast_730_router(db, require_roles):
    router = APIRouter(prefix="/forecast-730", tags=["forecast-730"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def forecast(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cap = 0
        for rt in await db.room_types.find({"property_id": pid},
                                           {"_id": 0, "total_rooms": 1}).to_list(100):
            cap += int(rt.get("total_rooms", 0))
        cap = cap or 20
        today = ddate.today()
        hist_start = (today - timedelta(days=730)).isoformat()
        # tarihsel oda-gece → ay-of-year mevsimsellik endeksi
        month_rn: dict = {}
        async for b in db.bookings.find(
                {"property_id": pid, "status": ACTIVE,
                 "check_in": {"$gte": hist_start, "$lt": today.isoformat()}},
                {"_id": 0, "check_in": 1, "check_out": 1, "rooms": 1}):
            try:
                ci = ddate.fromisoformat(b["check_in"][:10])
                co = ddate.fromisoformat(b["check_out"][:10])
            except Exception:
                continue
            r = max(int(b.get("rooms", 1) or 1), 1)
            d = ci
            while d < co and d < today:
                k = f"{d.year:04d}-{d.month:02d}"
                month_rn[k] = month_rn.get(k, 0) + r
                d += timedelta(days=1)
        # ay-of-year ortalama doluluk
        moy: dict = {}
        for k, rn in month_rn.items():
            y, m = int(k[:4]), int(k[5:7])
            occ = rn / (cap * calendar.monthrange(y, m)[1])
            moy.setdefault(m, []).append(occ)
        moy_avg = {m: sum(v) / len(v) for m, v in moy.items()}
        overall = (sum(moy_avg.values()) / len(moy_avg)) if moy_avg else 0.5
        # OTB: gelecek konaklamalar
        otb: dict = {}
        async for b in db.bookings.find(
                {"property_id": pid, "status": ACTIVE,
                 "check_out": {"$gt": today.isoformat()}},
                {"_id": 0, "check_in": 1, "check_out": 1, "rooms": 1}):
            try:
                ci = max(ddate.fromisoformat(b["check_in"][:10]), today)
                co = ddate.fromisoformat(b["check_out"][:10])
            except Exception:
                continue
            r = max(int(b.get("rooms", 1) or 1), 1)
            d = ci
            while d < co:
                k = f"{d.year:04d}-{d.month:02d}"
                otb[k] = otb.get(k, 0) + r
                d += timedelta(days=1)
        out = []
        for i in range(24):
            y, m = today.year, today.month + i
            while m > 12:
                m -= 12
                y += 1
            dim = calendar.monthrange(y, m)[1]
            avail = cap * dim
            season = round(moy_avg.get(m, overall) / overall, 2) if overall else 1.0
            proj_occ = round(min(moy_avg.get(m, overall), 1.0) * 100, 1)
            otb_rn = otb.get(f"{y:04d}-{m:02d}", 0)
            otb_occ = round(min(otb_rn / avail, 1.0) * 100, 1)
            if season >= 1.15:
                stance = "güçlü sezon — fiyatı yüksek tutun, erken indirimden kaçının"
            elif season <= 0.85:
                stance = "zayıf sezon — erken rezervasyon teşviki ve LOS indirimi değerlendirin"
            else:
                stance = "normal sezon — baz stratejiyi koruyun"
            out.append({"month": f"{y:04d}-{m:02d}", "days_out": i * 30,
                        "seasonality_idx": season, "projected_occ_pct": proj_occ,
                        "otb_room_nights": otb_rn, "otb_occ_pct": otb_occ,
                        "capacity": avail, "stance": stance})
        return {"property_id": pid, "capacity": cap, "horizon_days": 730,
                "history_months": len(month_rn), "months": out,
                "note": "Mevsimsellik = ay-of-year tarihsel doluluk / genel ortalama (son 730 gün). OTB = şu an defterdeki oda-gece. 1.0 üzeri endeks = güçlü ay."}

    return router
