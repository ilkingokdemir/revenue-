"""Hava Durumu + Resmi Tatil Sinyalleri — open-meteo & Nager.Date (anahtarsız), fiyat motoru çarpanı."""
import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

WMO_BAD = {65, 66, 67, 75, 82, 86, 95, 96, 99}

PDF_ARCHIVE_KEYS = ("weekly", "executive")

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


async def _log_markup(db, pid: str, action: str, kind: str, detail: str, by: str = "", count: int = 1):
    await db.markup_history.insert_one({
        "id": str(_uuid.uuid4()), "property_id": pid, "action": action, "kind": kind,
        "detail": detail[:220], "count": count, "by": by or "sistem",
        "at": datetime.now(timezone.utc).isoformat()})


async def send_weekly_signal_digest(db, pid: str, force: bool = False) -> dict:
    """Haftanın tatil/etkinlik/hava sinyallerini pazartesi sabahı yöneticiye özetler."""
    import uuid as _uuid
    now = datetime.now(timezone.utc)
    week_key = now.strftime("%G-W%V")
    dup = await db.notifications.find_one(
        {"created_by": "Sinyal Özeti Robotu", "property_id": pid, "week": week_key}, {"_id": 1})
    if dup and not force:
        return {"sent": False, "reason": f"{week_key} özeti zaten gönderildi"}
    await refresh_signals(db, pid, 21)
    today = now.date()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(7)]
    sigs = await db.demand_calendar_signals.find(
        {"property_id": pid, "date": {"$in": dates}}, {"_id": 0}).sort("date", 1).to_list(10)
    evs = await db.public_events.find(
        {"date": {"$gte": dates[0], "$lte": dates[-1]}},
        {"_id": 0, "date": 1, "title": 1}).to_list(50)
    lines = []
    for s in sigs:
        if s.get("holiday"):
            lines.append(f"🎌 {s['date']}: {s['holiday']}")
        w = s.get("weather") or {}
        if (w.get("precip") or 0) >= 15:
            lines.append(f"🌧 {s['date']}: şiddetli yağış beklentisi ({w['precip']:.0f}mm)")
        elif s.get("multiplier", 1) > 1 and not s.get("holiday") and s.get("reasons"):
            lines.append(f"☀️ {s['date']}: {s['reasons'][0]}")
    ev_by_date = {}
    for e in evs:
        ev_by_date.setdefault(e["date"], []).append(e.get("title") or "Etkinlik")
    for d, titles in sorted(ev_by_date.items()):
        lines.append(f"🎪 {d}: {', '.join(titles[:2])}")
    msg = ("Bu hafta sinyal yok — nötr talep haftası." if not lines
           else "Bu haftanın talep sinyalleri:\n" + "\n".join(lines[:10])
           + "\n\nFiyat takviminde tatil/etkinlik bantlarından tek tıkla zam uygulayabilirsiniz.")
    gap_included = False
    try:
        wks = await _weekly_trend(db, pid, 4)
        if wks:
            iso = now.date().isocalendar()
            cur_key = f"{iso[0]}-W{iso[1]:02d}"
            idx = next((i for i, w in enumerate(wks) if w["week"] >= cur_key), 0)
            this_w = wks[idx]
            nxt = wks[idx + 1] if len(wks) > idx + 1 else None
            direction = "stabil →"
            if nxt:
                diff = abs(nxt["avg_dev"]) - abs(this_w["avg_dev"])
                direction = "açılıyor 📈" if diff >= 0.5 else ("kapanıyor 📉" if diff <= -0.5 else "stabil →")
            msg += (f"\n\n📡 Pazarla Makas Durumu:\nBu hafta ort. %{this_w['avg_dev']:+g} "
                    f"({'pazardan pahalıyız' if this_w['avg_dev'] >= 0 else 'pazardan ucuzuz'}) · makas {direction}\n"
                    + " · ".join(f"{w['week'].split('-')[1]}: %{w['avg_dev']:+g}" for w in wks)
                    + "\nDetay: AI Pricing → Rakip Fiyat Tetiği → 📈 Trend")
            gap_included = True
    except Exception:
        pass
    await db.notifications.insert_one({
        "id": str(_uuid.uuid4()), "type": "info",
        "title": f"📅 Haftalık Sinyal Özeti ({week_key})",
        "message": msg, "category": "revenue", "target_user": "", "target_role": "manager",
        "link_to": "revenue", "priority": "normal", "read": False,
        "property_id": pid, "week": week_key,
        "created_by": "Sinyal Özeti Robotu", "created_at": now.isoformat()})
    email_status = "skipped"
    try:
        from routes.revenue_ext.owner_pulse import _send_email
        mgrs = await db.users.find({"role": {"$in": ["admin", "manager"]}},
                                   {"_id": 0, "email": 1}).to_list(10)
        html = "<h3>📅 Haftalık Sinyal Özeti (" + week_key + ")</h3><pre style='font-family:sans-serif'>" + msg + "</pre>"
        statuses = [await _send_email(m["email"], f"Haftalık Sinyal Özeti ({week_key})", html)
                    for m in mgrs if m.get("email")]
        email_status = ",".join(statuses) or "no-recipients"
    except Exception as e:
        email_status = f"error: {e}"
    return {"sent": True, "week": week_key, "signal_lines": len(lines),
            "gap_included": gap_included, "email_status": email_status}


async def apply_occupancy_rule(db, pid: str, by: str = "", force: bool = False) -> dict:
    """Doluluk eşiğini aşan günlere ek zam, düşük doluluk günlerine indirim uygular (30 gün)."""
    rule = await db.occupancy_rules.find_one({"property_id": pid}, {"_id": 0}) or {}
    enabled = bool(rule.get("enabled", False))
    if not enabled and not force:
        return {"ran": False, "reason": "kural pasif"}
    threshold = float(rule.get("threshold_pct", 90))
    extra = float(rule.get("extra_pct", 10))
    low_enabled = bool(rule.get("low_enabled", False))
    low_threshold = min(float(rule.get("low_threshold_pct", 40)), threshold - 10)
    discount = float(rule.get("low_discount_pct", 10))
    room_types = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
    rt = room_types[0] if room_types else {"id": "default", "base_rate": 100}
    rt_id = rt.get("id", "")
    base_rate = float(rt.get("base_rate", 100) or 100)
    total_rooms = await db.rooms.count_documents({"property_id": pid}) or 10
    today = datetime.now(timezone.utc).date()
    now_iso = datetime.now(timezone.utc).isoformat()
    applied, discounted, details = 0, 0, []
    zam_delta, ind_delta = 0, 0
    for i in range(30):
        ds = (today + timedelta(days=i)).isoformat()
        booked = await db.bookings.count_documents(
            {"property_id": pid, "check_in": {"$lte": ds}, "check_out": {"$gt": ds},
             "status": {"$ne": "cancelled"}})
        occ = min(100, round(booked / max(total_rooms, 1) * 100))
        is_high = occ >= threshold
        is_low = low_enabled and occ <= low_threshold
        if not is_high and not is_low:
            continue
        ovr = await db.rate_overrides.find_one(
            {"property_id": pid, "date": ds, "room_type_id": rt_id}, {"_id": 0})
        if ovr and not ovr.get("markup_kind") and not ovr.get("holiday_markup"):
            continue
        mult = 1.4 if occ >= 90 else 1.2 if occ >= 75 else 1.0 if occ >= 50 else 0.85 if occ >= 25 else 0.7
        if is_high:
            new_rate = round(base_rate * mult * (1 + extra / 100))
            name = f"Doluluk %{occ} ≥ %{threshold:g}"
        else:
            new_rate = round(base_rate * mult * (1 - discount / 100))
            name = f"Düşük doluluk %{occ} ≤ %{low_threshold:g} (−%{discount:g})"
        if ovr and ovr.get("markup_kind") == "occupancy" and ovr.get("custom_rate") == float(new_rate):
            continue
        await db.rate_overrides.update_one(
            {"property_id": pid, "date": ds, "room_type_id": rt_id},
            {"$set": {"property_id": pid, "date": ds, "room_type_id": rt_id,
                      "custom_rate": float(new_rate), "markup_kind": "occupancy",
                      "markup_name": name,
                      "prev_custom_rate": None, "set_by": "Doluluk Kuralı Robotu",
                      "updated_at": now_iso}}, upsert=True)
        if is_high:
            applied += 1
            zam_delta += new_rate - round(base_rate * mult)
        else:
            discounted += 1
            ind_delta += round(base_rate * mult) - new_rate
        details.append({"date": ds, "occ_pct": occ, "new_rate": new_rate,
                        "action": "zam" if is_high else "indirim"})
    if applied or discounted:
        await db.occupancy_rule_impact.insert_one({
            "id": str(_uuid.uuid4()), "property_id": pid,
            "month": datetime.now(timezone.utc).strftime("%Y-%m"),
            "zam_days": applied, "indirim_days": discounted,
            "zam_delta_sum": zam_delta, "indirim_delta_sum": ind_delta,
            "at": now_iso})
        await _log_markup(db, pid, "apply", "occupancy",
                          f"Doluluk kuralı (eşik %{threshold:g}/+%{extra:g}"
                          + (f", düşük %{low_threshold:g}/−%{discount:g}" if low_enabled else "")
                          + f") · {applied} zam, {discounted} indirim",
                          by=by, count=applied + discounted)
    pms_push = None
    if (applied or discounted) and bool(rule.get("push_to_pms", False)):
        try:
            from routes.distribution.pms_connect import run_auto_night_push
            pr = await run_auto_night_push(db, pid)
            _res = pr.get("results", [])
            pms_push = {"channels": len(_res),
                        "pushed_days": sum(r.get("pushed_days", 0) for r in _res),
                        "live": sum(1 for r in _res if r.get("mode") == "live")}
        except Exception as e:
            pms_push = {"error": str(e)[:120]}
    return {"ran": True, "threshold_pct": threshold, "extra_pct": extra,
            "low_enabled": low_enabled, "low_threshold_pct": low_threshold,
            "low_discount_pct": discount, "applied": applied, "discounted": discounted,
            "days": details, "enabled": enabled, "pms_push": pms_push}


async def run_competitor_price_trigger(db, pid: str, force: bool = False) -> dict:
    """Rakip ortalaması bizden eşik %'den fazla saparsa fiyat önerisi bildirimi bırakır."""
    cfg = await db.comp_trigger.find_one({"property_id": pid}, {"_id": 0}) or {}
    if not cfg.get("enabled", False) and not force:
        return {"ran": False, "reason": "tetik pasif"}
    threshold = float(cfg.get("threshold_pct", 10))
    rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0}) or {"base_rate": 100}
    base_rate = float(rt.get("base_rate", 100) or 100)
    today = datetime.now(timezone.utc).date()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(14)]
    snaps = await db.market_supply.aggregate([
        {"$match": {"property_id": pid, "scan_type": "geo", "date": {"$in": dates}}},
        {"$sort": {"scanned_at": -1}},
        {"$group": {"_id": "$date", "avg_price": {"$first": "$avg_price"}}}]).to_list(20)
    deviations = []
    for s in snaps:
        mk = float(s.get("avg_price") or 0)
        if mk <= 0:
            continue
        ovr = await db.rate_overrides.find_one(
            {"property_id": pid, "date": s["_id"]}, {"_id": 0, "custom_rate": 1})
        ours = float(ovr["custom_rate"]) if ovr and ovr.get("custom_rate") else base_rate
        dev = (ours - mk) / mk * 100
        if abs(dev) >= threshold:
            deviations.append({"date": s["_id"], "ours": round(ours, 2), "market": round(mk, 2),
                               "dev_pct": round(dev, 1),
                               "suggestion": round(mk * (1.02 if dev < 0 else 0.98), 2)})
    deviations.sort(key=lambda x: -abs(x["dev_pct"]))
    trend_alert = await check_trend_alert(db, pid)
    sent = False
    if deviations:
        day_key = today.isoformat()
        dup = await db.notifications.find_one(
            {"created_by": "Rakip Fiyat Tetiği", "property_id": pid, "day": day_key}, {"_id": 1})
        if not dup or force:
            top = deviations[:5]
            lines = [f"{d['date']}: biz {d['ours']:g} / pazar {d['market']:g} (%{d['dev_pct']:+g}) → öneri {d['suggestion']:g}"
                     for d in top]
            await db.notifications.insert_one({
                "id": str(_uuid.uuid4()), "type": "warning",
                "title": f"📡 Rakip Fiyat Tetiği: {len(deviations)} günde ±%{threshold:g} sapma",
                "message": "Rakip ortalamasından sapan günler ve fiyat önerileri:\n" + "\n".join(lines),
                "category": "revenue", "target_user": "", "target_role": "manager",
                "link_to": "revenue", "priority": "high", "read": False,
                "property_id": pid, "day": day_key,
                "created_by": "Rakip Fiyat Tetiği", "created_at": datetime.now(timezone.utc).isoformat()})
            sent = True
    return {"ran": True, "threshold_pct": threshold, "deviations": deviations[:10],
            "deviation_days": len(deviations), "notified": sent, "trend_alert": trend_alert}


async def _weekly_trend(db, pid: str, weeks: int = 8) -> list:
    """Konaklama tarihine göre haftalık ort/min/max sapma bucket'ları."""
    weeks = max(2, min(16, weeks))
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=14)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(14 + weeks * 7)]
    rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0}) or {"base_rate": 100}
    base_rate = float(rt.get("base_rate", 100) or 100)
    rt_id = rt.get("id", "")
    snaps = await db.market_supply.aggregate([
        {"$match": {"property_id": pid, "scan_type": "geo", "date": {"$in": dates}}},
        {"$sort": {"scanned_at": -1}},
        {"$group": {"_id": "$date", "avg_price": {"$first": "$avg_price"}}}]).to_list(200)
    buckets = {}
    for s in snaps:
        mk = float(s.get("avg_price") or 0)
        if mk <= 0:
            continue
        ovr = await db.rate_overrides.find_one(
            {"property_id": pid, "date": s["_id"], "room_type_id": rt_id},
            {"_id": 0, "custom_rate": 1})
        ours = float(ovr["custom_rate"]) if ovr and ovr.get("custom_rate") else base_rate
        dev = (ours - mk) / mk * 100
        iso = datetime.fromisoformat(s["_id"]).date().isocalendar()
        buckets.setdefault(f"{iso[0]}-W{iso[1]:02d}", []).append(dev)
    return [{"week": k, "avg_dev": round(sum(v) / len(v), 1), "min_dev": round(min(v), 1),
             "max_dev": round(max(v), 1), "days": len(v)}
            for k, v in sorted(buckets.items())]


async def check_trend_alert(db, pid: str) -> bool:
    """Makas (|ort. sapma|) üst üste N hafta açılıyorsa bildirim gönderir (haftada 1 dedupe)."""
    cfg = await db.comp_trigger.find_one({"property_id": pid}, {"_id": 0}) or {}
    n_weeks = int(cfg.get("trend_weeks", 2))
    step_pp = float(cfg.get("trend_step_pp", 1.0))
    wks = await _weekly_trend(db, pid, 8)
    hit = None
    for i in range(len(wks) - n_weeks):
        window = wks[i:i + n_weeks + 1]
        if all(abs(window[j + 1]["avg_dev"]) >= abs(window[j]["avg_dev"]) + step_pp
               for j in range(n_weeks)):
            hit = window
    if not hit:
        return False
    iso = datetime.now(timezone.utc).date().isocalendar()
    week_key = f"{iso[0]}-W{iso[1]:02d}"
    dup = await db.notifications.find_one(
        {"created_by": "Trend Uyarısı", "property_id": pid, "week": week_key}, {"_id": 1})
    if dup:
        return False
    lines = [f"{w['week']}: ort. %{w['avg_dev']:+g} (makas %{abs(w['avg_dev']):g})" for w in hit]
    await db.notifications.insert_one({
        "id": str(_uuid.uuid4()), "type": "warning",
        "title": f"📉 Trend Uyarısı: pazarla makas {n_weeks} haftadır açılıyor",
        "message": f"Haftalık ortalama sapma üst üste (adım ≥{step_pp:g} puan) büyüyor — fiyat stratejinizi gözden geçirin:\n"
                   + "\n".join(lines)
                   + "\nAI Pricing → Rakip Fiyat Tetiği → 📈 Trend'den detayları inceleyebilirsiniz.",
        "category": "revenue", "target_user": "", "target_role": "manager",
        "link_to": "revenue", "priority": "high", "read": False,
        "property_id": pid, "week": week_key,
        "created_by": "Trend Uyarısı", "created_at": datetime.now(timezone.utc).isoformat()})
    return True


async def _month_deviations(db, pid: str, year: int, month: int, room_type_id: str = "") -> dict:
    from calendar import monthrange
    n = monthrange(year, month)[1]
    dates = [f"{year:04d}-{month:02d}-{dd:02d}" for dd in range(1, n + 1)]
    rts = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
    ref = rts[0] if rts else {"id": "", "base_rate": 100}
    rt = next((r for r in rts if r.get("id") == room_type_id), ref) if room_type_id else ref
    ref_rate = float(ref.get("base_rate", 100) or 100)
    rt_rate = float(rt.get("base_rate", 100) or 100)
    ratio = rt_rate / max(ref_rate, 1)
    snaps = await db.market_supply.aggregate([
        {"$match": {"property_id": pid, "scan_type": "geo", "date": {"$in": dates}}},
        {"$sort": {"scanned_at": -1}},
        {"$group": {"_id": "$date", "avg_price": {"$first": "$avg_price"}}}]).to_list(40)
    out = {}
    for s in snaps:
        mk = float(s.get("avg_price") or 0) * ratio
        if mk <= 0:
            continue
        q = {"property_id": pid, "date": s["_id"], "room_type_id": rt.get("id", "")}
        ovr = await db.rate_overrides.find_one(q, {"_id": 0, "custom_rate": 1})
        ours = float(ovr["custom_rate"]) if ovr and ovr.get("custom_rate") else rt_rate
        out[s["_id"]] = {"dev_pct": round((ours - mk) / mk * 100, 1),
                         "market": round(mk, 2), "ours": round(ours, 2)}
    return out


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

    @router.get("/{pid}/events")
    async def upcoming_events(pid: str, days: int = 90, _u: dict = Depends(require_roles(*ROLES))):
        """Önümüzdeki N günün etkinlik sinyalleri (fiyat takvimi mor bandı için)."""
        days = max(7, min(180, days))
        t0 = datetime.now(timezone.utc).date()
        evs = await db.public_events.find(
            {"date": {"$gte": t0.isoformat(), "$lte": (t0 + timedelta(days=days)).isoformat()}},
            {"_id": 0, "date": 1, "title": 1, "capacity": 1, "distance_km": 1}).to_list(500)
        by_date = {}
        for e in evs:
            capw = min(int(e.get("capacity") or 0) / 2000.0, 1.0) * 0.15
            dist = e.get("distance_km")
            decay = max(0.25, 1 - float(dist) / 10.0) if dist is not None else 1.0
            d = by_date.setdefault(e["date"], {"date": e["date"], "titles": [], "boost_pct": 0.0})
            d["titles"].append(e.get("title") or "Etkinlik")
            d["boost_pct"] = round(min(d["boost_pct"] + capw * decay * 100, 25.0), 1)
        rows = sorted(by_date.values(), key=lambda x: x["date"])
        for r in rows:
            r["titles"] = r["titles"][:3]
        return {"property_id": pid, "days": days, "events": rows}

    @router.post("/{pid}/apply-holiday-markup")
    async def apply_holiday_markup(pid: str, data: dict,
                                   _u: dict = Depends(require_roles(*ROLES))):
        """90 gündeki tüm resmi tatillere önerilen zammı topluca uygular (manuel override'lara dokunmaz)."""
        room_type_id = (data.get("room_type_id") or "").strip()
        cfg = await get_signal_cfg(db, pid)
        pct = float(cfg["holiday_pct"])
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "city": 1}) or {}
        geo = await _geocode(db, pid, (prop.get("city") or "London").strip())
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=90)
        hols = await _holidays(db, (geo or {}).get("country_code", "GB"),
                               sorted({today.year, end.year}))
        targets = {d: n for d, n in hols.items() if today.isoformat() <= d <= end.isoformat()}
        room_types = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
        rt = next((r for r in room_types if r.get("id") == room_type_id), None) or \
            (room_types[0] if room_types else {"id": "default", "base_rate": 100})
        rt_id = rt.get("id", "")
        base_rate = float(rt.get("base_rate", 100) or 100)
        total_rooms = await db.rooms.count_documents({"property_id": pid}) or 10
        now_iso = datetime.now(timezone.utc).isoformat()
        applied, skipped = [], []
        for ds, name in sorted(targets.items()):
            ovr = await db.rate_overrides.find_one(
                {"property_id": pid, "date": ds,
                 "room_type_id": {"$in": [rt_id, "", "default"]}}, {"_id": 0})
            if ovr and not ovr.get("holiday_markup"):
                skipped.append({"date": ds, "name": name, "reason": "manuel override var"})
                continue
            booked = await db.bookings.count_documents(
                {"property_id": pid, "check_in": {"$lte": ds}, "check_out": {"$gt": ds},
                 "status": {"$ne": "cancelled"}})
            occ = min(100, round(booked / max(total_rooms, 1) * 100))
            mult = 1.4 if occ >= 90 else 1.2 if occ >= 75 else 1.0 if occ >= 50 else 0.85 if occ >= 25 else 0.7
            recommended = round(base_rate * mult, 2)
            new_rate = round(recommended * (1 + pct / 100))
            await db.rate_overrides.update_one(
                {"property_id": pid, "date": ds, "room_type_id": rt_id},
                {"$set": {"property_id": pid, "date": ds, "room_type_id": rt_id,
                          "custom_rate": float(new_rate), "holiday_markup": True,
                          "holiday_name": name, "set_by": "Tatil Zam Robotu",
                          "updated_at": now_iso}}, upsert=True)
            applied.append({"date": ds, "name": name, "base": recommended, "new_rate": new_rate})
        if applied:
            await _log_markup(db, pid, "apply", "holiday",
                              f"Toplu tatil zammı %{pct:g} · {len(applied)} gün",
                              by=str(_u.get("email") or ""), count=len(applied))
        return {"ok": True, "pct": pct, "room_type_id": rt_id,
                "applied": applied, "skipped": skipped,
                "note": f"%{pct:g} tatil zammı uygulandı. Manuel override'lı günler atlandı; tatil zamları tekrar çalıştırılırsa güncellenir."}

    @router.post("/{pid}/apply-markup")
    async def apply_markup(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        """Tek güne tatil/etkinlik zammı uygular; eski fiyatı geri alma için saklar."""
        ds = (data.get("date") or "").strip()
        kind = data.get("kind") if data.get("kind") in ("holiday", "event") else "holiday"
        try:
            new_rate = float(data.get("new_rate"))
        except (TypeError, ValueError):
            raise HTTPException(400, "new_rate gerekli")
        if not ds:
            raise HTTPException(400, "date gerekli")
        rt_id = (data.get("room_type_id") or "").strip()
        existing = await db.rate_overrides.find_one(
            {"property_id": pid, "date": ds, "room_type_id": rt_id}, {"_id": 0})
        prev = None
        if existing:
            prev = existing.get("prev_custom_rate") if existing.get("markup_kind") else existing.get("custom_rate")
        await db.rate_overrides.update_one(
            {"property_id": pid, "date": ds, "room_type_id": rt_id},
            {"$set": {"property_id": pid, "date": ds, "room_type_id": rt_id,
                      "custom_rate": new_rate, "markup_kind": kind,
                      "holiday_markup": kind == "holiday",
                      "markup_name": (data.get("name") or "")[:80],
                      "prev_custom_rate": prev, "set_by": "Zam Robotu",
                      "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        await _log_markup(db, pid, "apply", kind,
                          f"{ds} · {data.get('name') or ''} · yeni {new_rate:g}"
                          + (f" (önceki {prev:g})" if prev is not None else ""),
                          by=str(_u.get("email") or ""))
        return {"ok": True, "date": ds, "kind": kind, "new_rate": new_rate, "prev_custom_rate": prev}

    @router.post("/{pid}/undo-markups")
    async def undo_markups(pid: str, data: dict = None, _u: dict = Depends(require_roles(*ROLES))):
        """Zamları eski fiyata döndürür; 'kind' verilirse sadece o tür geri alınır."""
        kind = (data or {}).get("kind")
        if kind == "holiday":
            q = {"property_id": pid,
                 "$or": [{"markup_kind": "holiday"}, {"holiday_markup": True}]}
        elif kind in ("event", "season", "occupancy", "comp_trigger"):
            q = {"property_id": pid, "markup_kind": kind}
        else:
            kind = None
            q = {"property_id": pid,
                 "$or": [{"markup_kind": {"$exists": True}}, {"holiday_markup": True}]}
        if data and data.get("date"):
            q["date"] = data["date"]
        restored, removed = 0, 0
        async for o in db.rate_overrides.find(q):
            prev = o.get("prev_custom_rate")
            if prev is not None:
                await db.rate_overrides.update_one(
                    {"_id": o["_id"]},
                    {"$set": {"custom_rate": float(prev), "set_by": "Zam Geri Alma",
                              "updated_at": datetime.now(timezone.utc).isoformat()},
                     "$unset": {"markup_kind": "", "holiday_markup": "", "markup_name": "",
                                "prev_custom_rate": "", "holiday_name": ""}})
                restored += 1
            else:
                await db.rate_overrides.delete_one({"_id": o["_id"]})
                removed += 1
        if restored + removed:
            await _log_markup(db, pid, "undo", kind or "all",
                              f"{restored} manuel fiyata, {removed} otomatik fiyata döndü"
                              + (f" (tür: {kind})" if kind else ""),
                              by=str(_u.get("email") or ""), count=restored + removed)
        return {"ok": True, "kind": kind, "restored_manual": restored, "reverted_to_auto": removed,
                "total": restored + removed}

    @router.get("/{pid}/markup-history")
    async def markup_history(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.markup_history.find({"property_id": pid}, {"_id": 0}).sort("at", -1).to_list(50)
        return {"property_id": pid, "history": rows}

    @router.get("/{pid}/season-templates")
    async def season_templates(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.season_templates.find({"property_id": pid}, {"_id": 0}).to_list(30)
        if not rows:
            y = datetime.now(timezone.utc).year
            prop = await db.properties.find_one({"id": pid}, {"_id": 0, "city": 1}) or {}
            geo = await _geocode(db, pid, (prop.get("city") or "London").strip())
            hols = await _holidays(db, (geo or {}).get("country_code", "GB"), [y, y + 1])
            today = datetime.now(timezone.utc).date().isoformat()
            nxt = next((d for d in sorted(hols) if d >= today), None)
            seeds = [
                {"name": "Yaz Sezonu", "start_date": f"{y}-06-01", "end_date": f"{y}-08-31", "adjustment_pct": 15},
                {"name": "Kış Sezonu", "start_date": f"{y}-11-01", "end_date": f"{y + 1}-02-28", "adjustment_pct": -10},
            ]
            if nxt:
                d0 = datetime.strptime(nxt, "%Y-%m-%d").date()
                seeds.append({"name": f"Bayram: {hols[nxt]}", "adjustment_pct": 20,
                              "start_date": (d0 - timedelta(days=1)).isoformat(),
                              "end_date": (d0 + timedelta(days=1)).isoformat()})
            for s in seeds:
                s.update({"id": str(_uuid.uuid4()), "property_id": pid, "seeded": True,
                          "created_at": datetime.now(timezone.utc).isoformat()})
                await db.season_templates.insert_one(dict(s))
            rows = await db.season_templates.find({"property_id": pid}, {"_id": 0}).to_list(30)
        return {"templates": rows}

    @router.post("/{pid}/season-templates")
    async def create_season(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        try:
            pct = max(-50.0, min(100.0, float(data.get("adjustment_pct"))))
        except (TypeError, ValueError):
            raise HTTPException(400, "adjustment_pct gerekli")
        name = (data.get("name") or "").strip()[:60]
        sd, ed = (data.get("start_date") or "").strip(), (data.get("end_date") or "").strip()
        if not name or not sd or not ed or ed < sd:
            raise HTTPException(400, "name, start_date, end_date gerekli (bitiş ≥ başlangıç)")
        doc = {"id": str(_uuid.uuid4()), "property_id": pid, "name": name,
               "start_date": sd, "end_date": ed, "adjustment_pct": pct,
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.season_templates.insert_one(dict(doc))
        return {"ok": True, "template": doc}

    @router.delete("/{pid}/season-templates/{tid}")
    async def delete_season(pid: str, tid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.season_templates.delete_one({"property_id": pid, "id": tid})
        return {"ok": True}

    @router.post("/{pid}/season-templates/{tid}/apply")
    async def apply_season(pid: str, tid: str, data: dict = None,
                           _u: dict = Depends(require_roles(*ROLES))):
        tpl = await db.season_templates.find_one({"property_id": pid, "id": tid}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Şablon bulunamadı")
        dry_run = bool((data or {}).get("dry_run"))
        pct = float(tpl["adjustment_pct"])
        room_type_id = ((data or {}).get("room_type_id") or "").strip()
        room_types = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
        rt = next((r for r in room_types if r.get("id") == room_type_id), None) or \
            (room_types[0] if room_types else {"id": "default", "base_rate": 100})
        rt_id = rt.get("id", "")
        base_rate = float(rt.get("base_rate", 100) or 100)
        total_rooms = await db.rooms.count_documents({"property_id": pid}) or 10
        d0 = max(datetime.strptime(tpl["start_date"], "%Y-%m-%d").date(),
                 datetime.now(timezone.utc).date())
        d1 = datetime.strptime(tpl["end_date"], "%Y-%m-%d").date()
        now_iso = datetime.now(timezone.utc).isoformat()
        applied, skipped, cursor, days = 0, 0, d0, []
        while cursor <= d1 and applied + skipped < 190:
            ds = cursor.isoformat()
            cursor += timedelta(days=1)
            ovr = await db.rate_overrides.find_one(
                {"property_id": pid, "date": ds, "room_type_id": rt_id}, {"_id": 0})
            if ovr and not ovr.get("markup_kind") and not ovr.get("holiday_markup"):
                skipped += 1
                if len(days) < 60:
                    days.append({"date": ds, "current": ovr.get("custom_rate"),
                                 "new_rate": None, "skipped": True})
                continue
            booked = await db.bookings.count_documents(
                {"property_id": pid, "check_in": {"$lte": ds}, "check_out": {"$gt": ds},
                 "status": {"$ne": "cancelled"}})
            occ = min(100, round(booked / max(total_rooms, 1) * 100))
            mult = 1.4 if occ >= 90 else 1.2 if occ >= 75 else 1.0 if occ >= 50 else 0.85 if occ >= 25 else 0.7
            current = round(base_rate * mult, 2)
            new_rate = round(current * (1 + pct / 100))
            if len(days) < 60:
                days.append({"date": ds, "current": current, "new_rate": new_rate, "skipped": False})
            if not dry_run:
                await db.rate_overrides.update_one(
                    {"property_id": pid, "date": ds, "room_type_id": rt_id},
                    {"$set": {"property_id": pid, "date": ds, "room_type_id": rt_id,
                              "custom_rate": float(new_rate), "markup_kind": "season",
                              "markup_name": tpl["name"], "prev_custom_rate": None,
                              "set_by": "Sezon Şablonu", "updated_at": now_iso}}, upsert=True)
            applied += 1
        if not dry_run and applied:
            await _log_markup(db, pid, "apply", "season",
                              f"{tpl['name']} ({tpl['start_date']}→{tpl['end_date']}, %{pct:+g}) · {applied} gün",
                              by=str(_u.get("email") or ""), count=applied)
        return {"ok": True, "template": tpl["name"], "pct": pct, "dry_run": dry_run,
                "applied": applied, "skipped_manual": skipped, "days": days,
                "note": "Manuel fiyatlar korundu. '↩ Zamları Geri Al' ile tümü geri alınabilir."}

    @router.get("/{pid}/occupancy-rule")
    async def get_occupancy_rule(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        doc = await db.occupancy_rules.find_one({"property_id": pid}, {"_id": 0}) or {}
        return {"property_id": pid, "threshold_pct": float(doc.get("threshold_pct", 90)),
                "extra_pct": float(doc.get("extra_pct", 10)),
                "enabled": bool(doc.get("enabled", False)),
                "low_enabled": bool(doc.get("low_enabled", False)),
                "low_threshold_pct": float(doc.get("low_threshold_pct", 40)),
                "low_discount_pct": float(doc.get("low_discount_pct", 10)),
                "push_to_pms": bool(doc.get("push_to_pms", False)),
                "note": "Aktifken robot her gün önümüzdeki 30 günü tarar; doluluk eşiği aşan günlere otomatik ek zam uygular (manuel fiyatlar korunur)."}

    @router.put("/{pid}/occupancy-rule")
    async def set_occupancy_rule(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {}
        for k, lo, hi in (("threshold_pct", 50, 100), ("extra_pct", 1, 50),
                          ("low_threshold_pct", 5, 80), ("low_discount_pct", 1, 40)):
            if k in data:
                try:
                    upd[k] = max(lo, min(hi, float(data[k])))
                except (TypeError, ValueError):
                    pass
        for k in ("enabled", "low_enabled", "push_to_pms"):
            if k in data:
                upd[k] = bool(data[k])
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.occupancy_rules.update_one(
            {"property_id": pid}, {"$set": {"property_id": pid, **upd}}, upsert=True)
        doc = await db.occupancy_rules.find_one({"property_id": pid}, {"_id": 0})
        return {"ok": True, **{k: doc.get(k) for k in
                               ("threshold_pct", "extra_pct", "enabled",
                                "low_enabled", "low_threshold_pct", "low_discount_pct", "push_to_pms")}}

    @router.post("/{pid}/occupancy-rule/run")
    async def run_occupancy_rule(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await apply_occupancy_rule(db, pid, by=str(_u.get("email") or ""), force=True)

    @router.get("/{pid}/occupancy-rule/impact")
    async def occupancy_rule_impact(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.occupancy_rule_impact.aggregate([
            {"$match": {"property_id": pid}},
            {"$group": {"_id": "$month", "zam_days": {"$sum": "$zam_days"},
                        "indirim_days": {"$sum": "$indirim_days"},
                        "zam_delta": {"$sum": "$zam_delta_sum"},
                        "indirim_delta": {"$sum": "$indirim_delta_sum"},
                        "runs": {"$sum": 1}}},
            {"$sort": {"_id": -1}}, {"$limit": 6}]).to_list(6)
        months = [{"month": r["_id"], "zam_days": r["zam_days"], "indirim_days": r["indirim_days"],
                   "zam_delta": r["zam_delta"], "indirim_delta": r["indirim_delta"],
                   "net": r["zam_delta"] - r["indirim_delta"], "runs": r["runs"]} for r in rows]
        return {"property_id": pid, "months": months,
                "note": "Delta = kuralın taban fiyata göre oda-gece başına değiştirdiği tutar toplamı (üst sınır tahmini)."}

    @router.get("/{pid}/comp-trigger")
    async def get_comp_trigger(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        doc = await db.comp_trigger.find_one({"property_id": pid}, {"_id": 0}) or {}
        return {"property_id": pid, "threshold_pct": float(doc.get("threshold_pct", 10)),
                "enabled": bool(doc.get("enabled", False)),
                "trend_weeks": int(doc.get("trend_weeks", 2)),
                "trend_step_pp": float(doc.get("trend_step_pp", 1.0))}

    @router.put("/{pid}/comp-trigger")
    async def set_comp_trigger(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if "threshold_pct" in data:
            try:
                upd["threshold_pct"] = max(3.0, min(50.0, float(data["threshold_pct"])))
            except (TypeError, ValueError):
                pass
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        if "trend_weeks" in data:
            try:
                upd["trend_weeks"] = max(2, min(6, int(data["trend_weeks"])))
            except (TypeError, ValueError):
                pass
        if "trend_step_pp" in data:
            try:
                upd["trend_step_pp"] = max(0.5, min(10.0, float(data["trend_step_pp"])))
            except (TypeError, ValueError):
                pass
        await db.comp_trigger.update_one({"property_id": pid},
                                         {"$set": {"property_id": pid, **upd}}, upsert=True)
        doc = await db.comp_trigger.find_one({"property_id": pid}, {"_id": 0})
        return {"ok": True, "threshold_pct": doc.get("threshold_pct", 10),
                "enabled": doc.get("enabled", False),
                "trend_weeks": int(doc.get("trend_weeks", 2)),
                "trend_step_pp": float(doc.get("trend_step_pp", 1.0))}

    @router.get("/{pid}/comp-trigger/summary")
    async def comp_trigger_summary(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Dashboard mini kartı: güncel hafta makası + yön (açılıyor/kapanıyor/stabil)."""
        wks = await _weekly_trend(db, pid, 6)
        iso = datetime.now(timezone.utc).date().isocalendar()
        cur_key = f"{iso[0]}-W{iso[1]:02d}"
        idx = next((i for i, w in enumerate(wks) if w["week"] >= cur_key), 0) if wks else 0
        this_w = wks[idx] if wks else None
        next_w = wks[idx + 1] if len(wks) > idx + 1 else None
        direction = "stabil"
        if this_w and next_w:
            diff = abs(next_w["avg_dev"]) - abs(this_w["avg_dev"])
            direction = "açılıyor" if diff >= 0.5 else ("kapanıyor" if diff <= -0.5 else "stabil")
        alert = await db.notifications.find_one(
            {"created_by": "Trend Uyarısı", "property_id": pid, "week": cur_key}, {"_id": 1})
        return {"property_id": pid, "this_week": this_w, "next_week": next_w,
                "direction": direction, "weeks": wks, "alert_active": bool(alert),
                "note": "Konaklama haftalarına göre pazarla ortalama fiyat makası."}

    @router.post("/{pid}/comp-trigger/run")
    async def run_comp_trigger(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await run_competitor_price_trigger(db, pid, force=True)

    @router.post("/{pid}/comp-trigger/apply")
    async def apply_comp_trigger(pid: str, data: dict = None,
                                 _u: dict = Depends(require_roles(*ROLES))):
        """Rakip tetiği önerilerini takvime uygular; 'dates' verilirse sadece seçili günler."""
        r = await run_competitor_price_trigger(db, pid, force=True)
        sel = set((data or {}).get("dates") or [])
        devs = [d for d in r.get("deviations", []) if not sel or d["date"] in sel]
        room_types = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
        if not room_types:
            room_types = [{"id": "", "base_rate": 100}]
        ref_rate = float(room_types[0].get("base_rate", 100) or 100)
        now_iso = datetime.now(timezone.utc).isoformat()
        applied, writes = [], 0
        for d in devs:
            applied.append({"date": d["date"], "new_rate": d["suggestion"]})
            for rt in room_types:
                rt_id = rt.get("id", "")
                ratio = float(rt.get("base_rate", 100) or 100) / max(ref_rate, 1)
                new_rate = round(float(d["suggestion"]) * ratio, 2)
                existing = await db.rate_overrides.find_one(
                    {"property_id": pid, "date": d["date"], "room_type_id": rt_id}, {"_id": 0})
                prev = None
                if existing:
                    prev = existing.get("prev_custom_rate") if existing.get("markup_kind") else existing.get("custom_rate")
                await db.rate_overrides.update_one(
                    {"property_id": pid, "date": d["date"], "room_type_id": rt_id},
                    {"$set": {"property_id": pid, "date": d["date"], "room_type_id": rt_id,
                              "custom_rate": new_rate, "markup_kind": "comp_trigger",
                              "markup_name": f"Rakip tetiği (pazar {d['market']:g}, %{d['dev_pct']:+g})",
                              "prev_custom_rate": prev, "set_by": "Rakip Fiyat Tetiği",
                              "updated_at": now_iso}}, upsert=True)
                writes += 1
        if applied:
            await _log_markup(db, pid, "apply", "comp_trigger",
                              f"Rakip tetiği önerileri · {len(applied)} gün × {len(room_types)} oda tipi takvime uygulandı",
                              by=str(_u.get("email") or ""), count=len(applied))
        return {"ok": True, "applied": len(applied), "room_types": len(room_types),
                "writes": writes, "days": applied,
                "note": "Oda tipi fiyatları taban fiyat oranına göre ölçeklendi. '↩ Zamları Geri Al' ile geri alınabilir."}

    @router.get("/{pid}/comp-trigger/trend")
    async def comp_trigger_trend(pid: str, weeks: int = 8,
                                 _u: dict = Depends(require_roles(*ROLES))):
        """Haftalık ortalama sapma trendi (konaklama tarihine göre, geçmiş 2 hafta + gelecek N hafta)."""
        out = await _weekly_trend(db, pid, weeks)
        return {"property_id": pid, "weeks": out,
                "note": "Konaklama tarihine göre haftalık ortalama sapma — pozitif: pazardan pahalıyız, negatif: ucuzuz. Sıfır çizgisine yakınlık pazarla uyumu gösterir."}

    @router.get("/{pid}/comp-deviations")
    async def comp_deviations(pid: str, year: int, month: int, room_type_id: str = "",
                              _u: dict = Depends(require_roles(*ROLES))):
        """Ay bazlı rakip sapma ısı haritası verisi (tüm sapmalar, eşiksiz, oda tipi seçilebilir)."""
        out = await _month_deviations(db, pid, year, month, room_type_id)
        return {"property_id": pid, "year": year, "month": month,
                "room_type_id": room_type_id, "deviations": out}

    @router.get("/{pid}/heatmap-pdf")
    async def heatmap_pdf(pid: str, year: int = 0, month: int = 0, room_type_id: str = "",
                          _u: dict = Depends(require_roles(*ROLES))):
        """Aylık rakip sapma ısı haritası PDF'i — takvim ızgarası + özet."""
        from calendar import monthrange
        from io import BytesIO
        from fastapi.responses import StreamingResponse
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as pc
        from reportlab.lib.units import mm
        today = datetime.now(timezone.utc).date()
        year = year or today.year
        month = month or today.month
        devs = await _month_deviations(db, pid, year, month, room_type_id)
        rt_doc = await db.room_types.find_one({"property_id": pid, "id": room_type_id},
                                              {"_id": 0, "name": 1}) if room_type_id else None
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        _t = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        months_tr = ["", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran",
                     "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]
        buf = BytesIO()
        c = pc.Canvas(buf, pagesize=A4)
        w, hh = A4
        c.setFillColorRGB(0.05, 0.09, 0.16)
        c.rect(0, hh - 34 * mm, w, 34 * mm, fill=1, stroke=0)
        try:
            from routes.platform_ext.branding import get_logo_reader, draw_logo
            _logo = await get_logo_reader(db, pid)
            if _logo:
                draw_logo(c, _logo, w, hh, mm)
        except Exception:
            pass
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 17)
        c.drawString(18 * mm, hh - 15 * mm, "Rakip Sapma Isi Haritasi")
        c.setFont("Helvetica", 10)
        c.drawString(18 * mm, hh - 23 * mm,
                     f"{(prop.get('name') or pid).translate(_t)} · {months_tr[month]} {year} · "
                     + (f"{(rt_doc.get('name') or '').translate(_t)} · " if rt_doc else "")
                     + f"{len(devs)} gunde pazar verisi")
        n_days = monthrange(year, month)[1]
        first_dow = datetime(year, month, 1).weekday()
        cw = (w - 36 * mm) / 7
        ch = 20 * mm
        top = hh - 44 * mm
        c.setFont("Helvetica-Bold", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        for i, dn in enumerate(["Pzt", "Sal", "Car", "Per", "Cum", "Cmt", "Paz"]):
            c.drawCentredString(18 * mm + i * cw + cw / 2, top, dn)
        top -= 4 * mm
        for day in range(1, n_days + 1):
            idx = first_dow + day - 1
            row, col = idx // 7, idx % 7
            x = 18 * mm + col * cw
            y = top - (row + 1) * ch
            ds = f"{year:04d}-{month:02d}-{day:02d}"
            d = devs.get(ds)
            if d:
                t = min(abs(d["dev_pct"]) / 40, 1.0) * 0.85
                base = (0.96, 0.25, 0.37) if d["dev_pct"] >= 0 else (0.05, 0.65, 0.91)
                c.setFillColorRGB(*(1 + (b - 1) * t for b in base))
            else:
                c.setFillColorRGB(0.97, 0.97, 0.96)
            c.rect(x, y, cw - 1, ch - 1, fill=1, stroke=0)
            c.setFillColorRGB(0.15, 0.15, 0.15)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(x + 1.5 * mm, y + ch - 5 * mm, str(day))
            if d:
                c.setFont("Helvetica-Bold", 8)
                c.drawString(x + 1.5 * mm, y + ch - 10 * mm,
                             f"{'+' if d['dev_pct'] >= 0 else ''}{d['dev_pct']:g}%")
                c.setFont("Helvetica", 6)
                c.setFillColorRGB(0.3, 0.3, 0.3)
                c.drawString(x + 1.5 * mm, y + ch - 14 * mm, f"Biz {d['ours']:g}")
                c.drawString(x + 1.5 * mm, y + ch - 17.5 * mm, f"Pzr {d['market']:g}")
        rows_used = (first_dow + n_days + 6) // 7
        y = top - rows_used * ch - 10 * mm
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(18 * mm, y, "Ozet")
        y -= 7 * mm
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        if devs:
            vals = [d["dev_pct"] for d in devs.values()]
            avg = round(sum(vals) / len(vals), 1)
            over = sorted(devs.items(), key=lambda kv: -kv[1]["dev_pct"])[:3]
            under = sorted(devs.items(), key=lambda kv: kv[1]["dev_pct"])[:3]
            lines = [
                f"Ortalama sapma: {'+' if avg >= 0 else ''}{avg}% · "
                f"{sum(1 for v in vals if v >= 0)} gun pazardan pahali, {sum(1 for v in vals if v < 0)} gun ucuz",
                "En pahali gunler: " + ", ".join(f"{k} ({v['dev_pct']:+g}%)" for k, v in over if v["dev_pct"] > 0),
                "En ucuz gunler: " + ", ".join(f"{k} ({v['dev_pct']:+g}%)" for k, v in under if v["dev_pct"] < 0),
            ]
        else:
            lines = ["Bu ay icin pazar tarama verisi yok - Pazar Robotu'ndan tarama baslatabilirsiniz."]
        for ln in lines:
            c.drawString(18 * mm, y, ln.translate(_t)[:110])
            y -= 5.5 * mm
        y -= 3 * mm
        c.setFillColorRGB(0.96, 0.25, 0.37)
        c.rect(18 * mm, y, 4 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColorRGB(0.05, 0.65, 0.91)
        c.rect(60 * mm, y, 4 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.setFont("Helvetica", 8)
        c.drawString(24 * mm, y + 0.5 * mm, "Pazardan pahaliyiz")
        c.drawString(66 * mm, y + 0.5 * mm, "Pazardan ucuzuz · renk koyulugu = sapma buyuklugu")
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.setFont("Helvetica", 7)
        c.drawString(18 * mm, 12 * mm,
                     f"Olusturma: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC · RMS Rapor Merkezi")
        c.showPage()
        c.save()
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition":
                                          f'inline; filename="sapma-isi-haritasi-{year}-{month:02d}.pdf"'})

    @router.post("/{pid}/weekly-digest/run")
    async def weekly_digest_run(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await send_weekly_signal_digest(db, pid, force=True)

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
