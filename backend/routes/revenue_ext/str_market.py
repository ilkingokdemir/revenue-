"""
Airbnb / STR Pazar Verisi — RoomPriceGenie "hundreds of local Airbnbs" paritesi.

Yerel kısa dönem kiralama (Airbnb/Vrbo) arzını ve medyan gecelik fiyatlarını
deterministik simülasyonla üretir (gerçek scraper entegrasyonu P2).
Otel compset'ine STR fiyat farkı ve arz baskısı sinyali ekler.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
import hashlib
import math


def _h(seed: str, lo: float, hi: float) -> float:
    n = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return lo + n * (hi - lo)


def create_str_market_router(db, require_roles):
    router = APIRouter(prefix="/str-market", tags=["str-market"])

    @router.get("/{property_id}/overview")
    async def overview(property_id: str, days: int = 60,
                       _u: dict = Depends(require_roles("admin", "manager"))):
        days = max(7, min(180, days))
        rts = await db.room_types.find({"property_id": property_id},
                                       {"_id": 0, "base_rate": 1}).to_list(50)
        hotel_base = (sum(float(r.get("base_rate", 0) or 0) for r in rts) / len(rts)) if rts else 130.0
        hotel_base = hotel_base or 130.0

        listings_total = int(_h(f"{property_id}:listings", 60, 240))
        entire_pct = round(_h(f"{property_id}:entire", 55, 80), 1)

        today = datetime.now(timezone.utc).date()
        rows = []
        for i in range(days):
            d = today + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            dow = d.weekday()
            dow_mult = 1.18 if dow in (4, 5) else (0.95 if dow == 6 else 1.0)
            season_mult = 1.0 + 0.18 * math.sin((d.timetuple().tm_yday / 365.0) * 2 * math.pi - 1.6)
            jitter = _h(f"{property_id}:{ds}:j", 0.94, 1.06)
            median_rate = round(hotel_base * 0.62 * dow_mult * season_mult * jitter, 2)
            active = int(listings_total * _h(f"{property_id}:{ds}:s", 0.72, 0.95))
            occ = round(_h(f"{property_id}:{ds}:o", 42, 88) * dow_mult / 1.05, 1)
            rows.append({"date": ds, "median_rate": median_rate,
                         "active_listings": active, "occupancy_proxy": min(occ, 97.0)})

        med_avg = round(sum(r["median_rate"] for r in rows) / len(rows), 2)
        gap_pct = round((hotel_base - med_avg) / med_avg * 100, 1) if med_avg else 0
        weekend_rows = [r for r in rows if datetime.strptime(r["date"], "%Y-%m-%d").weekday() in (4, 5)]
        weekend_uplift = 0.0
        if weekend_rows:
            weekend_uplift = round(
                (sum(r["median_rate"] for r in weekend_rows) / len(weekend_rows) - med_avg) / med_avg * 100, 1)
        high_occ_days = [r["date"] for r in rows if r["occupancy_proxy"] >= 80][:5]

        findings = [
            f"Bölgede ~{listings_total} aktif STR ilanı var (%{entire_pct} tüm ev/daire).",
            f"STR medyan gecelik fiyat £{med_avg} — otel baz fiyatınız STR pazarının %{abs(gap_pct)} {'üzerinde' if gap_pct >= 0 else 'altında'}.",
            f"Hafta sonu STR fiyatları medyana göre %{weekend_uplift} yukarıda — Cuma/Cumartesi fiyat tavanınızı gözden geçirin.",
        ]
        if high_occ_days:
            findings.append(
                f"STR doluluk sinyali yüksek günler: {', '.join(high_occ_days[:3])} — bu tarihlerde talep baskısı otele taşabilir, fiyat yükseltme fırsatı.")

        return {
            "property_id": property_id,
            "days": days,
            "rows": rows,
            "summary": {
                "listings_total": listings_total,
                "entire_home_pct": entire_pct,
                "median_rate_avg": med_avg,
                "hotel_base_rate": round(hotel_base, 2),
                "hotel_vs_str_gap_pct": gap_pct,
                "weekend_uplift_pct": weekend_uplift,
            },
            "findings": findings,
            "source": "simulated",
        }

    return router
