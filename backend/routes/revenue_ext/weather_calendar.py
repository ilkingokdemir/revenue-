"""Hava Durumu + Resmi Tatil Sinyalleri — open-meteo & Nager.Date (anahtarsız), fiyat motoru çarpanı."""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)

WMO_BAD = {65, 66, 67, 75, 82, 86, 95, 96, 99}

DEFAULT_SIGNAL_CFG = {"holiday_pct": 5.0, "eve_pct": 3.0, "sunny_weekend_pct": 3.0,
                      "bad_weather_pct": 3.0, "enabled": True}


async def get_signal_cfg(db, pid: str) -> dict:
    doc = await db.demand_signal_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULT_SIGNAL_CFG, **{k: doc[k] for k in DEFAULT_SIGNAL_CFG if k in doc}}


async def _geocode(db, pid: str, city: str):
    cached = await db.property_geo.find_one({"property_id": pid}, {"_id": 0})
    if cached and cached.get("lat") is not None:
        return cached
    if not city:
        return None
    try:
        async with httpx.AsyncClient(timeout=12) as cl:
            r = await cl.get("https://geocoding-api.open-meteo.com/v1/search",
                             params={"name": city, "count": 1, "language": "en"})
        res = (r.json().get("results") or [None])[0]
    except Exception as e:
        logger.warning(f"geocode fail {city}: {e}")
        return None
    if not res:
        return None
    geo = {"property_id": pid, "city": city, "lat": res["latitude"], "lon": res["longitude"],
           "country_code": (res.get("country_code") or "GB").upper(),
           "resolved_name": res.get("name"),
           "cached_at": datetime.now(timezone.utc).isoformat()}
    await db.property_geo.update_one({"property_id": pid}, {"$set": geo}, upsert=True)
    return geo


async def _holidays(db, country: str, years) -> dict:
    out = {}
    for y in years:
        key = f"{country}:{y}"
        doc = await db.holiday_cache.find_one({"key": key}, {"_id": 0})
        if not doc:
            try:
                async with httpx.AsyncClient(timeout=12) as cl:
                    r = await cl.get(f"https://date.nager.at/api/v3/PublicHolidays/{y}/{country}")
                rows = r.json() if r.status_code == 200 else []
            except Exception as e:
                logger.warning(f"nager fail {key}: {e}")
                rows = []
            doc = {"key": key,
                   "rows": [{"date": h["date"], "name": h.get("localName") or h.get("name")} for h in rows],
                   "cached_at": datetime.now(timezone.utc).isoformat()}
            await db.holiday_cache.update_one({"key": key}, {"$set": doc}, upsert=True)
        for h in doc["rows"]:
            out[h["date"]] = h["name"]
    return out


async def refresh_signals(db, pid: str, days: int = 21) -> dict:
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "city": 1}) or {}
    city = (prop.get("city") or "London").strip()
    geo = await _geocode(db, pid, city)
    today = datetime.now(timezone.utc).date()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(days)]
    weather_map = {}
    if geo:
        try:
            async with httpx.AsyncClient(timeout=15) as cl:
                r = await cl.get("https://api.open-meteo.com/v1/forecast",
                                 params={"latitude": geo["lat"], "longitude": geo["lon"],
                                         "daily": "weathercode,temperature_2m_max,precipitation_sum",
                                         "forecast_days": min(days, 16), "timezone": "UTC"})
            dd = r.json().get("daily", {})
            times = dd.get("time", [])
            for i, ds in enumerate(times):
                weather_map[ds] = {"code": (dd.get("weathercode") or [None] * len(times))[i],
                                   "tmax": (dd.get("temperature_2m_max") or [None] * len(times))[i],
                                   "precip": (dd.get("precipitation_sum") or [None] * len(times))[i]}
        except Exception as e:
            logger.warning(f"open-meteo fail: {e}")
    country = (geo or {}).get("country_code", "GB")
    hols = await _holidays(db, country, sorted({int(d[:4]) for d in dates}))
    cfg = await get_signal_cfg(db, pid)
    hp, ep, sp, bp = cfg["holiday_pct"], cfg["eve_pct"], cfg["sunny_weekend_pct"], cfg["bad_weather_pct"]
    now_iso = datetime.now(timezone.utc).isoformat()
    for ds in dates:
        mult, reasons = 1.0, []
        hol = hols.get(ds)
        if not cfg["enabled"]:
            hol = hols.get(ds)
        elif hol:
            mult *= 1 + hp / 100
            reasons.append(f"Resmi tatil: {hol} (+%{hp:g})")
        nxt = (datetime.strptime(ds, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
        if cfg["enabled"] and not hol and hols.get(nxt):
            mult *= 1 + ep / 100
            reasons.append(f"Tatil arifesi: {hols[nxt]} (+%{ep:g})")
        w = weather_map.get(ds)
        weekend = datetime.strptime(ds, "%Y-%m-%d").weekday() >= 4
        if cfg["enabled"] and w:
            if (w.get("code") in WMO_BAD) or ((w.get("precip") or 0) >= 15):
                mult *= 1 - bp / 100
                reasons.append(f"Şiddetli hava (yağış {w.get('precip') or 0:.0f}mm) (−%{bp:g})")
            elif weekend and (w.get("tmax") or 0) >= 22 and (w.get("precip") or 0) < 1:
                mult *= 1 + sp / 100
                reasons.append(f"Güneşli hafta sonu ({w.get('tmax'):.0f}°C) (+%{sp:g})")
        await db.demand_calendar_signals.update_one(
            {"property_id": pid, "date": ds},
            {"$set": {"property_id": pid, "date": ds, "multiplier": round(mult, 3),
                      "reasons": reasons, "holiday": hol, "weather": w,
                      "refreshed_at": now_iso}}, upsert=True)
    return {"refreshed": len(dates), "city": city, "geo_found": bool(geo), "country": country,
            "holidays_in_window": sum(1 for d in dates if hols.get(d))}


async def get_signal_map(db, pid: str, dates: list) -> dict:
    rows = await db.demand_calendar_signals.find(
        {"property_id": pid, "date": {"$in": dates}, "multiplier": {"$ne": 1.0}},
        {"_id": 0, "date": 1, "multiplier": 1, "reasons": 1}).to_list(200)
    return {r["date"]: {"mult": float(r["multiplier"]), "reasons": r.get("reasons") or []} for r in rows}


async def compute_impact_report(db, pid: str, weeks: int = 4) -> dict:
    """Hava/tatil çarpanlarının gelire kattığı tahmini farkı haftalık ölçer."""
    from routes.revenue_ext.ml_pickup import _stay_counts
    weeks = max(1, min(8, weeks))
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    prop = await db.properties.find_one({"id": pid}, {"_id": 0, "currency": 1}) or {}
    out, total_impact, total_days = [], 0.0, 0
    for w in range(weeks - 1, -1, -1):
        ws = monday - timedelta(weeks=w)
        days = [(ws + timedelta(days=i)).isoformat() for i in range(7)]
        sigs = await db.demand_calendar_signals.find(
            {"property_id": pid, "date": {"$in": days}, "multiplier": {"$ne": 1.0}},
            {"_id": 0, "date": 1, "multiplier": 1, "reasons": 1}).to_list(7)
        week_impact, rn_sum, details = 0.0, 0, []
        for s in sigs:
            rn = (await _stay_counts(db, pid, s["date"]))["otb"]
            bs = await db.bookings.aggregate([
                {"$match": {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
                            "check_in": s["date"]}},
                {"$group": {"_id": None, "rev": {"$sum": "$total_price"}, "n": {"$sum": 1}}}]).to_list(1)
            adr = ((bs[0]["rev"] or 0) / max(rn, bs[0]["n"])) if (bs and bs[0]["n"]) else 0.0
            m = float(s["multiplier"])
            imp = round(rn * adr * (m - 1) / m, 2) if (rn and adr) else 0.0
            week_impact += imp
            rn_sum += rn
            details.append({"date": s["date"], "mult": m, "room_nights": rn,
                            "adr": round(adr, 2), "est_impact": imp,
                            "reasons": s.get("reasons") or []})
        out.append({"week_start": days[0], "week": ws.strftime("%G-W%V"),
                    "signal_days": len(sigs), "room_nights": rn_sum,
                    "est_impact": round(week_impact, 2), "details": details})
        total_impact += week_impact
        total_days += len(sigs)
    return {"property_id": pid, "weeks": out, "currency": prop.get("currency", "GBP"),
            "total_est_impact": round(total_impact, 2), "total_signal_days": total_days,
            "note": "Tahmin: sinyal çarpanı uygulanan günlerde satılan oda-gece × ADR × (çarpan−1)/çarpan. Çarpanın öneriye yansıdığı ve önerinin uygulandığı varsayımıyla üst sınır tahminidir."}


def create_weather_calendar_router(db, require_roles):
    router = APIRouter(prefix="/demand-signals", tags=["demand-signals"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def signals(pid: str, days: int = 14, _u: dict = Depends(require_roles(*ROLES))):
        days = max(7, min(21, days))
        today = datetime.now(timezone.utc).date()
        dates = [(today + timedelta(days=i)).isoformat() for i in range(days)]
        stale = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        fresh = await db.demand_calendar_signals.find_one(
            {"property_id": pid, "refreshed_at": {"$gte": stale}}, {"_id": 1})
        auto_refreshed = False
        if not fresh:
            await refresh_signals(db, pid, 21)
            auto_refreshed = True
        rows = await db.demand_calendar_signals.find(
            {"property_id": pid, "date": {"$in": dates}}, {"_id": 0}).sort("date", 1).to_list(30)
        geo = await db.property_geo.find_one({"property_id": pid}, {"_id": 0})
        return {"property_id": pid, "rows": rows, "geo": geo, "auto_refreshed": auto_refreshed,
                "note": "Hava (open-meteo) + resmi tatil (Nager.Date) sinyalleri fiyat motoruna çarpan olarak girer: tatil +%5, arife +%3, güneşli hafta sonu +%3, şiddetli hava −%3."}

    @router.post("/{pid}/refresh")
    async def refresh(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return {"ok": True, **(await refresh_signals(db, pid, 21))}

    @router.get("/{pid}/impact-report")
    async def impact_report(pid: str, weeks: int = 4, _u: dict = Depends(require_roles(*ROLES))):
        return await compute_impact_report(db, pid, weeks)

    @router.get("/{pid}/holidays")
    async def upcoming_holidays(pid: str, days: int = 90, _u: dict = Depends(require_roles(*ROLES))):
        """Önümüzdeki N günün resmi tatilleri (fiyat takvimi bandı için)."""
        days = max(7, min(365, days))
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "city": 1}) or {}
        geo = await _geocode(db, pid, (prop.get("city") or "London").strip())
        country = (geo or {}).get("country_code", "GB")
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=days)
        hols = await _holidays(db, country, sorted({today.year, end.year}))
        rows = [{"date": d, "name": n} for d, n in sorted(hols.items())
                if today.isoformat() <= d <= end.isoformat()]
        return {"property_id": pid, "country": country, "days": days, "holidays": rows}

    @router.get("/{pid}/config")
    async def get_config(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return {"property_id": pid, **(await get_signal_cfg(db, pid)),
                "defaults": DEFAULT_SIGNAL_CFG}

    @router.put("/{pid}/config")
    async def put_config(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {}
        for k in ("holiday_pct", "eve_pct", "sunny_weekend_pct", "bad_weather_pct"):
            if k in data:
                try:
                    upd[k] = max(0.0, min(15.0, float(data[k])))
                except (TypeError, ValueError):
                    pass
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        if upd:
            upd["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.demand_signal_config.update_one(
                {"property_id": pid}, {"$set": {"property_id": pid, **upd}}, upsert=True)
        await refresh_signals(db, pid, 21)
        return {"ok": True, "property_id": pid, **(await get_signal_cfg(db, pid))}

    return router
