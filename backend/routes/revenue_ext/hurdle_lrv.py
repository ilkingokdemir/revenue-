"""
Yield Guard — Hurdle Rate / Last Room Value (LRV) engine + data-driven
no-show forecast with overbooking suggestions.
Competitor gap: IDeaS "Last Room Value", Duetto hurdle pricing.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import logging

logger = logging.getLogger(__name__)

DEFAULT_MULTIPLIERS = [
    {"max_occ": 0.40, "factor": 0.80, "band": "low"},
    {"max_occ": 0.60, "factor": 0.92, "band": "moderate"},
    {"max_occ": 0.80, "factor": 1.00, "band": "healthy"},
    {"max_occ": 0.90, "factor": 1.18, "band": "high"},
    {"max_occ": 1.01, "factor": 1.40, "band": "peak"},
]
DOW_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def create_hurdle_lrv_router(db, require_roles):
    router = APIRouter()

    async def _get_config(property_id: str) -> dict:
        cfg = await db.hurdle_config.find_one({"property_id": property_id}, {"_id": 0})
        return cfg or {"property_id": property_id, "min_rate": 0.0,
                       "overbooking_cap": 3, "multipliers": DEFAULT_MULTIPLIERS}

    @router.get("/revenue/hurdle/{property_id}")
    async def hurdle_forecast(property_id: str, days: int = 30,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        days = min(max(days, 7), 90)
        cfg = await _get_config(property_id)
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=days)

        room_types = await db.room_types.find(
            {"property_id": property_id}, {"_id": 0, "id": 1, "total_rooms": 1, "base_price": 1}).to_list(50)
        capacity = sum(int(rt.get("total_rooms", 0) or 0) for rt in room_types) or 20
        weighted = [(int(rt.get("total_rooms", 0) or 1), float(rt.get("base_price", 0) or 0)) for rt in room_types]
        base_adr = (sum(n * p for n, p in weighted) / sum(n for n, _ in weighted)) if weighted else 100.0

        bookings = await db.bookings.find({
            "property_id": property_id,
            "status": {"$nin": ["cancelled", "no_show"]},
            "check_in": {"$lt": end.isoformat()},
            "check_out": {"$gt": today.isoformat()},
        }, {"_id": 0, "check_in": 1, "check_out": 1, "created_at": 1}).to_list(20000)

        # no-show rate by day-of-week (last 365 days history)
        yr_ago = (today - timedelta(days=365)).isoformat()
        hist = await db.bookings.find({
            "property_id": property_id, "check_in": {"$gte": yr_ago},
            "status": {"$in": ["no_show", "checked_out", "checked_in", "confirmed"]},
        }, {"_id": 0, "check_in": 1, "status": 1}).to_list(50000)
        dow_tot, dow_ns = [0] * 7, [0] * 7
        for h in hist:
            try:
                dw = datetime.fromisoformat(h["check_in"][:10]).weekday()
            except Exception:
                continue
            dow_tot[dw] += 1
            if h.get("status") == "no_show":
                dow_ns[dw] += 1
        noshow_by_dow = [round(dow_ns[i] / dow_tot[i], 3) if dow_tot[i] >= 5 else 0.05 for i in range(7)]

        recent_cut = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        mults = sorted(cfg.get("multipliers", DEFAULT_MULTIPLIERS), key=lambda m: m["max_occ"])
        out = []
        for i in range(days):
            d = today + timedelta(days=i)
            ds = d.isoformat()
            occ_cnt, pickup7 = 0, 0
            for b in bookings:
                if b.get("check_in", "") <= ds < b.get("check_out", ""):
                    occ_cnt += 1
                    if (b.get("created_at") or "") >= recent_cut:
                        pickup7 += 1
            occ = min(occ_cnt / capacity, 1.0)
            band = next((m for m in mults if occ < m["max_occ"]), mults[-1])
            pickup_boost = 1.0 + min(pickup7 / max(capacity, 1), 0.25)
            lrv = max(round(base_adr * band["factor"] * pickup_boost, 2), float(cfg.get("min_rate", 0) or 0))
            ns_rate = noshow_by_dow[d.weekday()]
            ob_suggest = min(int(round(capacity * ns_rate * 0.8)), int(cfg.get("overbooking_cap", 3)))
            actions = []
            if occ >= 0.90:
                actions.append("Tüm indirimli segmentleri kapat — sadece BAR/direkt satış")
            elif occ >= 0.80:
                actions.append("OTA mobil/genius indirimlerini kapat, LRV altı talepleri reddet")
            elif occ < 0.40 and i <= 14:
                actions.append("Talep düşük — kampanya/flash sale değerlendir")
            if ob_suggest > 0 and occ >= 0.85:
                actions.append(f"No-show tahmini %{round(ns_rate*100,1)} — {ob_suggest} oda overbooking güvenli")
            out.append({
                "date": ds, "dow": DOW_TR[d.weekday()],
                "occupancy": round(occ * 100, 1), "rooms_sold": occ_cnt,
                "rooms_left": max(capacity - occ_cnt, 0),
                "pickup_7d": pickup7,
                "band": band["band"], "lrv": lrv,
                "noshow_rate": ns_rate,
                "overbooking_suggested": ob_suggest if occ >= 0.85 else 0,
                "actions": actions,
            })
        return {"property_id": property_id, "capacity": capacity,
                "base_adr": round(base_adr, 2), "days": out,
                "noshow_by_dow": {DOW_TR[i]: noshow_by_dow[i] for i in range(7)},
                "config": cfg}

    @router.post("/revenue/hurdle/{property_id}/config")
    async def save_config(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = {
            "property_id": property_id,
            "min_rate": float(data.get("min_rate", 0) or 0),
            "overbooking_cap": int(data.get("overbooking_cap", 3) or 3),
            "multipliers": data.get("multipliers") or DEFAULT_MULTIPLIERS,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if cfg["min_rate"] < 0 or cfg["overbooking_cap"] < 0 or cfg["overbooking_cap"] > 20:
            raise HTTPException(status_code=422, detail="Geçersiz konfigürasyon değerleri")
        await db.hurdle_config.update_one({"property_id": property_id}, {"$set": cfg}, upsert=True)
        return cfg

    return router
