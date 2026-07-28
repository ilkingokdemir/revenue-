"""
Baz Fiyat Eğrisi (18 Ay) — RoomPriceGenie "18 months future pricing" paritesi.

Tek base fiyat + haftanın günü çarpanları + sezon çarpanları ile 540 güne kadar
fiyat eğrisi üretir. "Apply" mevcut override'ı olmayan tarihlere baz fiyat yazar;
yakın vadede AI motoru bu fiyatların üzerinde optimizasyona devam eder.

Collections: base_price_curves, rate_overrides (set_by="base-curve")
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict

DOW_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DEFAULT_DOW = {"mon": 1.0, "tue": 1.0, "wed": 1.0, "thu": 1.05, "fri": 1.15, "sat": 1.2, "sun": 0.95}
DEFAULT_SEASONS = [
    {"name": "Kış (Düşük Sezon)", "start": "11-01", "end": "02-28", "factor": 0.85},
    {"name": "Yaz (Yüksek Sezon)", "start": "06-01", "end": "09-15", "factor": 1.25},
]
MAX_HORIZON = 540


def _season_factor(mm_dd: str, seasons: list) -> tuple:
    for s in seasons:
        start, end = s.get("start", ""), s.get("end", "")
        if not start or not end:
            continue
        if start <= end:
            if start <= mm_dd <= end:
                return float(s.get("factor", 1.0)), s.get("name")
        else:  # wraps year end (e.g. 11-01 → 02-28)
            if mm_dd >= start or mm_dd <= end:
                return float(s.get("factor", 1.0)), s.get("name")
    return 1.0, None


def _build_curve(cfg: dict, days: int) -> list:
    base = float(cfg["base_price"])
    pmin = float(cfg["min_price"])
    pmax = float(cfg["max_price"])
    dow_f = {**DEFAULT_DOW, **(cfg.get("dow_factors") or {})}
    seasons = cfg.get("seasons") or []
    today = datetime.now(timezone.utc).date()
    rows = []
    for i in range(days):
        d = today + timedelta(days=i)
        dk = DOW_KEYS[d.weekday()]
        df = float(dow_f.get(dk, 1.0))
        sf, sname = _season_factor(d.strftime("%m-%d"), seasons)
        price = round(max(pmin, min(pmax, base * df * sf)), 2)
        rows.append({"date": d.strftime("%Y-%m-%d"), "dow": dk, "dow_factor": df,
                     "season_factor": sf, "season": sname, "price": price})
    return rows


def create_base_price_curve_router(db, require_roles):
    router = APIRouter(prefix="/base-curve", tags=["base-price-curve"])

    async def _get_cfg(property_id: str) -> dict:
        cfg = await db.base_price_curves.find_one({"property_id": property_id}, {"_id": 0})
        if cfg:
            return cfg
        rts = await db.room_types.find({"property_id": property_id}, {"_id": 0, "base_rate": 1}).to_list(50)
        base = round(sum(float(r.get("base_rate", 0) or 0) for r in rts) / len(rts), 2) if rts else 130.0
        base = base or 130.0
        cfg = {
            "property_id": property_id,
            "base_price": base,
            "min_price": round(base * 0.6, 2),
            "max_price": round(base * 2.5, 2),
            "dow_factors": dict(DEFAULT_DOW),
            "seasons": [dict(s) for s in DEFAULT_SEASONS],
            "horizon_days": MAX_HORIZON,
            "applied_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.base_price_curves.insert_one(dict(cfg))
        return cfg

    @router.get("/{property_id}/config")
    async def get_config(property_id: str,
                         _u: dict = Depends(require_roles("admin", "manager"))):
        return await _get_cfg(property_id)

    @router.put("/{property_id}/config")
    async def put_config(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        base = float(data.get("base_price", 0))
        pmin = float(data.get("min_price", 0))
        pmax = float(data.get("max_price", 0))
        if base <= 0 or pmin <= 0 or pmax <= 0:
            raise HTTPException(400, "base/min/max fiyatları pozitif olmalı")
        if not (pmin <= base <= pmax):
            raise HTTPException(400, "min_price <= base_price <= max_price olmalı")
        dow = data.get("dow_factors") or {}
        for k, v in dow.items():
            if k not in DOW_KEYS:
                raise HTTPException(400, f"Geçersiz gün: {k}")
            if not (0.3 <= float(v) <= 3.0):
                raise HTTPException(400, f"{k} çarpanı 0.3..3.0 aralığında olmalı")
        seasons = data.get("seasons") or []
        for s in seasons:
            if not (0.3 <= float(s.get("factor", 1.0)) <= 3.0):
                raise HTTPException(400, "Sezon çarpanı 0.3..3.0 aralığında olmalı")
        horizon = max(30, min(MAX_HORIZON, int(data.get("horizon_days", MAX_HORIZON))))
        payload = {
            "property_id": property_id,
            "base_price": base, "min_price": pmin, "max_price": pmax,
            "dow_factors": {**DEFAULT_DOW, **{k: float(v) for k, v in dow.items()}},
            "seasons": [{"name": s.get("name", ""), "start": s.get("start", ""),
                         "end": s.get("end", ""), "factor": float(s.get("factor", 1.0))} for s in seasons],
            "horizon_days": horizon,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("email"),
        }
        await db.base_price_curves.update_one({"property_id": property_id}, {"$set": payload}, upsert=True)
        return await _get_cfg(property_id)

    @router.get("/{property_id}/preview")
    async def preview(property_id: str, days: int = MAX_HORIZON,
                      _u: dict = Depends(require_roles("admin", "manager"))):
        days = max(7, min(MAX_HORIZON, days))
        cfg = await _get_cfg(property_id)
        rows = _build_curve(cfg, days)
        prices = [r["price"] for r in rows]
        return {"property_id": property_id, "days": days, "rows": rows,
                "summary": {"min": min(prices), "max": max(prices),
                            "avg": round(sum(prices) / len(prices), 2)}}

    @router.post("/{property_id}/apply")
    async def apply_curve(property_id: str, data: Dict = None,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await _get_cfg(property_id)
        days = max(30, min(MAX_HORIZON, int((data or {}).get("days", cfg.get("horizon_days", MAX_HORIZON)))))
        rows = _build_curve(cfg, days)
        today_str = rows[0]["date"]
        end_str = rows[-1]["date"]
        existing = await db.rate_overrides.find(
            {"property_id": property_id, "date": {"$gte": today_str, "$lte": end_str},
             "set_by": {"$ne": "base-curve"}},
            {"_id": 0, "date": 1},
        ).to_list(5000)
        protected = {e["date"] for e in existing}
        now_iso = datetime.now(timezone.utc).isoformat()
        written = 0
        for r in rows:
            if r["date"] in protected:
                continue
            await db.rate_overrides.update_one(
                {"property_id": property_id, "date": r["date"], "room_type_id": ""},
                {"$set": {"property_id": property_id, "room_type_id": "", "date": r["date"],
                          "custom_rate": r["price"], "set_by": "base-curve",
                          "reason": f"Baz eğri · {r['dow']} ×{r['dow_factor']}"
                                    + (f" · {r['season']} ×{r['season_factor']}" if r["season"] else ""),
                          "updated_at": now_iso}},
                upsert=True,
            )
            written += 1
        await db.base_price_curves.update_one(
            {"property_id": property_id},
            {"$set": {"applied_at": now_iso, "applied_by": current_user.get("email"),
                      "applied_days": days, "applied_count": written}})
        return {"ok": True, "days": days, "written": written,
                "skipped_protected": len(protected)}

    return router
