"""Otopark RMS — IDeaS Car Park RMS paritesi (niş).
Otel doluluğunu talep vekili olarak kullanıp otopark alanı için dinamik fiyat önerir."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from typing import Dict


def create_parking_rms_router(db, require_roles):
    router = APIRouter(prefix="/parking-rms", tags=["parking-rms"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def suggestions(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        from routes.revenue_ext.ml_pickup import _stay_counts
        s = await db.parking_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
        spaces = int(s.get("spaces") or 20)
        base_rate = float(s.get("base_rate") or 15.0)
        cap = await db.rooms.count_documents({"property_id": pid}) or 20
        today = datetime.now(timezone.utc).date()
        days = []
        for i in range(14):
            ds = (today + timedelta(days=i)).isoformat()
            otb = (await _stay_counts(db, pid, ds))["otb"]
            occ = otb / cap * 100
            dow = (today + timedelta(days=i)).weekday()
            factor = 0.8 + (occ / 100) * 0.6 + (0.1 if dow >= 5 else 0)
            price = round(base_rate * factor, 1)
            util = min(occ * 0.7 + 15, 100)
            days.append({"date": ds, "hotel_occ": round(occ, 1),
                         "suggested_price": price,
                         "current_price": base_rate,
                         "delta_pct": round((price / base_rate - 1) * 100, 1),
                         "expected_utilization": round(util, 1),
                         "revpas": round(price * util / 100, 2)})
        avg_revpas = round(sum(d["revpas"] for d in days) / len(days), 2)
        return {"property_id": pid, "spaces": spaces, "base_rate": base_rate,
                "days": days, "avg_revpas": avg_revpas,
                "note": "RevPAS = kullanılabilir park yeri başına gelir. Fiyat = baz × (0.8 + otel doluluğu×0.6 + hafta sonu +0.1)."}

    @router.post("/{pid}/settings")
    async def save_settings(pid: str, body: Dict, _u: dict = Depends(require_roles(*ROLES))):
        spaces = max(int(body.get("spaces") or 20), 1)
        base_rate = max(float(body.get("base_rate") or 15.0), 1.0)
        await db.parking_settings.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "spaces": spaces, "base_rate": base_rate,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "spaces": spaces, "base_rate": base_rate}

    return router
