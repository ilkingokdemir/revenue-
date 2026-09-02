"""
Misafir-Onaylı Zam Merdiveni (Guest-Approved Ramp Ladder) — RevenueIQ gap P1.
İlk zam talep kanıtıyla (doluluk eşiği) atılır. İKİNCİ ve sonraki basamaklar için
YENİ REZERVASYON şarttır: kimsenin ödemediği fiyata tırmanış matematiksel olarak kapalıdır.
Tavan (standard_max_rate) aşılmaz; tavan yoksa güvenlik sınırı çapa×1.25.
Pencere D2+ (D0-D1 son-gün merdivenine aittir — tek yazıcı). Kira-çit kilidiyle yazar.
Collections: ramp_config, ramp_state, ramp_steps
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta, date
from typing import Dict
import uuid
import asyncio
import logging

from routes.revenue_ext.write_lease import acquire_lease, lease_holder

logger = logging.getLogger(__name__)

ACTOR = "ramp-ladder"
DEFAULT_CFG = {"enabled": False, "window_start": 2, "window_end": 21,
               "step_pct": 5.0, "max_steps": 3, "occ_threshold": 70.0,
               "cadence_hours": 12, "forecast_boost": True,
               "event_premium": True, "event_min_score": 60}
SAFETY_CAP_MULT = 1.25
FORECAST_HOT_OCC, FORECAST_COLD_OCC, FORECAST_MIN_DAYS_OUT = 90.0, 50.0, 14


async def _event_map(db, pid: str, today: date, window_end: int, min_score: int) -> dict:
    """Büyük şehir etkinlikleri (market_events, demand_score ≥ eşik) → {stay_date: en güçlü etkinlik}."""
    last = (today + timedelta(days=window_end)).isoformat()
    evs = await db.market_events.find(
        {"property_id": {"$in": [pid, "all"]}, "date": {"$lte": last}, "end_date": {"$gte": today.isoformat()},
         "hotel_demand_score": {"$gte": int(min_score)}},
        {"_id": 0, "name": 1, "date": 1, "end_date": 1, "hotel_demand_score": 1, "category": 1}).to_list(200)
    out: dict = {}
    for e in evs:
        try:
            d0, d1 = date.fromisoformat(e["date"]), date.fromisoformat(e.get("end_date") or e["date"])
        except Exception:
            continue
        for i in range((d1 - d0).days + 1):
            k = (d0 + timedelta(days=i)).isoformat()
            if k not in out or e["hotel_demand_score"] > out[k]["hotel_demand_score"]:
                out[k] = e
    return out


async def _forecast_map(db, pid: str, days: int) -> dict:
    """ML pickup tahmini (LightGBM) → {stay_date: row}; model yoksa boş dict (sessiz)."""
    try:
        from routes.revenue_ext.ml_pickup import ml_pickup_forecast
        f = await ml_pickup_forecast(db, pid, days=days + 1)
        return {r["date"]: r for r in f.get("days", [])}
    except Exception as ex:
        logger.info("ramp forecast unavailable for %s: %s", pid, ex)
        return {}


def _forecast_signal(fc_row: dict | None) -> dict:
    """Uzak ufukta (T>14) tahmin 'sıcak' ise sönümlü kademe; 'boş gece' ise zam freni."""
    if not fc_row:
        return {"hot": False, "cold": False}
    occ = float(fc_row.get("ml_final_occ_pct") or 0)
    far = int(fc_row.get("days_out") or 0) > FORECAST_MIN_DAYS_OUT
    return {"hot": far and occ >= FORECAST_HOT_OCC, "cold": occ < FORECAST_COLD_OCC,
            "occ": occ, "days_out": fc_row.get("days_out"), "otb": fc_row.get("otb")}


def _now():
    return datetime.now(timezone.utc)


async def _get_cfg(db, pid: str) -> Dict:
    doc = await db.ramp_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULT_CFG, **{k: doc[k] for k in DEFAULT_CFG if k in doc}}


async def _ceiling_for(db, pid: str, rt_id: str, anchor: float) -> float:
    rule = (await db.min_rate_floors.find_one({"property_id": pid, "room_type_id": rt_id}, {"_id": 0})
            or await db.min_rate_floors.find_one({"property_id": pid, "room_type_id": "all"}, {"_id": 0}))
    cap = (rule or {}).get("standard_max_rate")
    return float(cap) if cap else round(anchor * SAFETY_CAP_MULT, 2)


async def _effective_rate(db, pid: str, rt_id: str, day: str, base_price: float) -> float:
    for q_rt in (rt_id, ""):
        ov = await db.rate_overrides.find_one(
            {"property_id": pid, "room_type_id": q_rt, "date": day}, {"_id": 0})
        if ov and ov.get("custom_rate"):
            return float(ov["custom_rate"])
    return float(base_price or 0)


from routes.revenue_ext.price_guard import guard_rate_change


async def _market_signal(db, pid: str, day: str) -> dict:
    """DEMAND_STRONG: rakip medyanı yükseliyor mu + rakip müsaitliği daralıyor mu (sönümlü ikinci anahtar)."""
    def _median(vals):
        s = sorted(vals)
        return (s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2) if s else 0
    now = _now()
    fresh_cut = (now - timedelta(hours=48)).isoformat()
    old_lo, old_hi = (now - timedelta(days=10)).isoformat(), (now - timedelta(days=5)).isoformat()
    q_pid = {"$in": [pid, "default"]}
    fresh, old, unavail = {}, {}, 0
    async for s in db.comp_rate_snapshots.find(
            {"property_id": q_pid, "date": day, "scanned_at": {"$gte": fresh_cut}},
            {"_id": 0, "comp_id": 1, "rate": 1, "sold_out": 1, "unavailable": 1}):
        fresh[s["comp_id"]] = float(s.get("rate") or 0)
        if s.get("sold_out") or s.get("unavailable"):
            unavail += 1
    async for s in db.comp_rate_snapshots.find(
            {"property_id": q_pid, "date": day, "scanned_at": {"$gte": old_lo, "$lt": old_hi}},
            {"_id": 0, "comp_id": 1, "rate": 1}):
        old.setdefault(s["comp_id"], float(s.get("rate") or 0))
    if len(fresh) < 2:
        return {"strong": False}
    med_new = _median([v for v in fresh.values() if v > 0])
    med_old = _median([v for v in old.values() if v > 0]) if old else 0
    rise_pct = round(100 * (med_new - med_old) / med_old, 1) if med_old else 0
    unavail_share = round(unavail / len(fresh), 2)
    strong = rise_pct >= 3.0 or unavail_share >= 0.5
    return {"strong": strong, "rise_pct": rise_pct, "unavail_share": unavail_share,
            "comps": len(fresh), "full_step": unavail_share >= 0.6}


async def scan_property(db, pid: str, force: bool = False) -> Dict:
    cfg = await _get_cfg(db, pid)
    if not cfg["enabled"]:
        return {"property_id": pid, "skipped": "disabled", "actions": []}
    now = _now()
    today = now.date()
    room_types = await db.room_types.find(
        {"property_id": pid}, {"_id": 0, "id": 1, "name": 1, "base_price": 1, "total_rooms": 1}).to_list(50)
    actions, skips = [], []
    step_p = float(cfg["step_pct"]) / 100.0
    fc_map = await _forecast_map(db, pid, int(cfg["window_end"])) if cfg.get("forecast_boost") else {}
    ev_map = await _event_map(db, pid, today, int(cfg["window_end"]), int(cfg.get("event_min_score", 60))) if cfg.get("event_premium", True) else {}
    for offset in range(int(cfg["window_start"]), int(cfg["window_end"]) + 1):
        day = (today + timedelta(days=offset)).isoformat()
        fsig = _forecast_signal(fc_map.get(day))
        ev = ev_map.get(day)
        for rt in room_types:
            rt_id = rt["id"]
            total = int(rt.get("total_rooms", 0))
            if total <= 0:
                continue
            sold = await db.bookings.count_documents({
                "property_id": pid, "room_type_id": rt_id,
                "status": {"$nin": ["cancelled", "no_show"]},
                "check_in": {"$lte": day}, "check_out": {"$gt": day}})
            occ = sold / total * 100
            st = await db.ramp_state.find_one(
                {"property_id": pid, "stay_date": day, "room_type_id": rt_id}, {"_id": 0}) or {}
            step_no = int(st.get("step_no", 0))
            anchor = float(st.get("anchor_rate") or 0)
            last_step_at = st.get("last_step_at")
            bookings_at_last = st.get("bookings_at_last_step")

            if step_no >= int(cfg["max_steps"]):
                continue
            event_step = False
            if occ < float(cfg["occ_threshold"]):
                if step_no == 0:
                    # --- EVENT_PREMIUM: büyük etkinlik gecesi → doluluk kanıtı beklemeden sönümlü ilk kademe (1 kez) ---
                    if ev and not st.get("event_step_at"):
                        event_step = True
                    else:
                        continue
                elif ev and st.get("event_step_at") and step_no <= 1:
                    continue  # etkinlik primi etkinlik sürdüğü sürece geri alınmaz
            if occ < float(cfg["occ_threshold"]) and not event_step:
                # --- YÖN DÖNÜŞÜ: talep söndü — kademeyi geri al, fiyatı indir ---
                if not force and last_step_at:
                    elapsed = (now - datetime.fromisoformat(last_step_at)).total_seconds() / 3600
                    if elapsed < float(cfg["cadence_hours"]):
                        continue
                if await acquire_lease(db, pid, rt_id, day, ACTOR) is None:
                    skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "lease_held"})
                    continue
                new_step = step_no - 1
                new_rate = round(anchor * ((1 + step_p) ** new_step), 2)
                await db.rate_overrides.update_one(
                    {"property_id": pid, "room_type_id": rt_id, "date": day},
                    {"$set": {"custom_rate": new_rate, "set_by": ACTOR,
                              "reason": f"Zam merdiveni yön dönüşü: doluluk %{occ:.0f} eşik altına indi — kademe {step_no}→{new_step}",
                              "updated_at": now.isoformat()}}, upsert=True)
                log = {"id": str(uuid.uuid4()), "property_id": pid, "stay_date": day,
                       "room_type_id": rt_id, "room_type": rt.get("name", ""),
                       "step_no": new_step, "from_step": step_no, "rate": new_rate,
                       "occ": round(occ, 1), "sold": sold, "direction": "down",
                       "guest_approved": False, "reason": "demand_faded_reversal",
                       "created_at": now.isoformat()}
                await db.ramp_steps.insert_one(dict(log))
                await db.ramp_state.update_one(
                    {"property_id": pid, "stay_date": day, "room_type_id": rt_id},
                    {"$set": {"step_no": new_step, "bookings_at_last_step": sold,
                              "last_step_at": now.isoformat()}}, upsert=True)
                log.pop("_id", None)
                actions.append(log)
                continue
            if not force and last_step_at and not event_step:
                elapsed = (now - datetime.fromisoformat(last_step_at)).total_seconds() / 3600
                if elapsed < float(cfg["cadence_hours"]):
                    continue

            # --- FORECAST_COLD freni: ML tahmini boş gece diyorsa yukarı kademe atılmaz ---
            if fsig["cold"] and step_no >= 1:
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "forecast_cold_brake",
                              "detail": f"ML tahmini nihai doluluk %{fsig['occ']:.0f} (<%{FORECAST_COLD_OCC:.0f}) — zam freni"})
                continue

            # --- MİSAFİR ONAYI + ASİMETRİK ZAMAN KURALI: zam için geçen süre kanıt DEĞİLDİR ---
            market_step = False
            forecast_step = False
            market = None
            if step_no >= 1:
                if bookings_at_last is None or sold <= int(bookings_at_last):
                    # --- DEMAND_STRONG ikinci anahtar: piyasa sıkılaşınca sönümlü kademe ---
                    last_mkt = st.get("market_step_at")
                    mkt_ok = not last_mkt or (now - datetime.fromisoformat(last_mkt)).total_seconds() >= 86400
                    market = await _market_signal(db, pid, day) if mkt_ok else {"strong": False}
                    # --- FORECAST_HOT üçüncü anahtar: uzak ufukta ML tahmini ≥%90 → sönümlü kademe (48 saatte 1) ---
                    last_fc = st.get("forecast_step_at")
                    fc_ok = not last_fc or (now - datetime.fromisoformat(last_fc)).total_seconds() >= 172800
                    if market.get("strong"):
                        market_step = True
                    elif fsig["hot"] and fc_ok:
                        forecast_step = True
                    else:
                        skips.append({"date": day, "room_type": rt.get("name", ""),
                                      "reason": "awaiting_guest_approval",
                                      "detail": (f"Kademe {step_no} fiyatında henüz yeni rezervasyon yok "
                                                 f"({sold} = {bookings_at_last}) — asimetrik zaman kuralı: "
                                                 "geçen süre zam kanıtı DEĞİLDİR, tırmanış KAPALI")})
                        continue

            if anchor <= 0:
                anchor = await _effective_rate(db, pid, rt_id, day, rt.get("base_price", 0))
            if anchor <= 0:
                continue
            ceiling = await _ceiling_for(db, pid, rt_id, anchor)
            new_step = step_no + 1
            # Piyasa/tahmin kaynaklı kademe SÖNÜMLÜdür: yarım adım (rakipler tükeniyorsa tam adım)
            damped = forecast_step or event_step or (market_step and not (market or {}).get("full_step"))
            eff_step_p = step_p / 2 if damped else step_p
            new_rate = round(anchor * ((1 + step_p) ** step_no) * (1 + eff_step_p), 2)
            if new_rate > ceiling:
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "at_ceiling",
                              "detail": f"Tavan {ceiling} — zam kademe atlanamadı"})
                continue

            # --- KİRA-ÇİT: hücre kirası al; başkası tutuyorsa yapısal olarak yazamayız ---
            token = await acquire_lease(db, pid, rt_id, day, ACTOR)
            if token is None:
                holder = await lease_holder(db, pid, rt_id, day)
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "lease_held",
                              "detail": f"Hücre kirası '{holder}' aktöründe — çit yazımı engelledi"})
                continue

            # --- GÜVENLİK SINIRLARI: tek hamle %X + 72s kümülatif %Y + kilit koruması ---
            cur_rate = await _effective_rate(db, pid, rt_id, day, rt.get("base_price", 0))
            guard = await guard_rate_change(db, pid, rt_id, day, cur_rate, new_rate, ACTOR)
            if not guard["allowed"]:
                skips.append({"date": day, "room_type": rt.get("name", ""),
                              "reason": "price_guard_blocked", "detail": guard["blocked_reason"]})
                continue
            new_rate = guard["rate"]

            await db.rate_overrides.update_one(
                {"property_id": pid, "room_type_id": rt_id, "date": day},
                {"$set": {"custom_rate": new_rate, "set_by": ACTOR,
                          "reason": (f"DEMAND_STRONG (piyasa) kademe {new_step}: rakip medyanı %{(market or {}).get('rise_pct', 0)} yükseldi, "
                                     f"rakip doluluk payı %{round(((market or {}).get('unavail_share') or 0) * 100)} — sönümlü adım"
                                     if market_step else
                                     f"FORECAST_HOT (ML tahmin) kademe {new_step}: {fsig.get('days_out')} gün kala nihai doluluk tahmini %{fsig.get('occ', 0):.0f} — sönümlü adım"
                                     if forecast_step else
                                     f"EVENT_PREMIUM kademe {new_step}: {(ev or {}).get('name', '')[:60]} (talep skoru {(ev or {}).get('hotel_demand_score', 0)}) — sönümlü etkinlik primi"
                                     if event_step else
                                     f"Zam merdiveni kademe {new_step}: doluluk %{occ:.0f}"
                                     + (f", misafir onayı: +{sold - int(bookings_at_last)} yeni rezervasyon" if step_no >= 1 else " (talep kanıtı)"))
                          + (" · güvenlik sınırı uygulandı" if guard["clamped"] else ""),
                          "updated_at": now.isoformat()}}, upsert=True)
            log = {"id": str(uuid.uuid4()), "property_id": pid, "stay_date": day,
                   "room_type_id": rt_id, "room_type": rt.get("name", ""),
                   "step_no": new_step, "from_step": step_no, "rate": new_rate,
                   "occ": round(occ, 1), "sold": sold, "ceiling": ceiling,
                   "direction": "up",
                   "guest_approved": step_no >= 1 and not market_step and not forecast_step,
                   "guard_clamped": guard["clamped"],
                   "market_signal": market if market_step else None,
                   "forecast_signal": fsig if forecast_step else None,
                   "event": {"name": ev.get("name"), "score": ev.get("hotel_demand_score"), "category": ev.get("category")} if event_step else None,
                   "reason": ("DEMAND_STRONG" if market_step else
                              "FORECAST_HOT" if forecast_step else
                              "EVENT_PREMIUM" if event_step else
                              "guest_approved_step" if step_no >= 1 else "demand_evidence_step"),
                   "created_at": now.isoformat()}
            await db.ramp_steps.insert_one(dict(log))
            await db.ramp_state.update_one(
                {"property_id": pid, "stay_date": day, "room_type_id": rt_id},
                {"$set": {"step_no": new_step, "anchor_rate": anchor,
                          "bookings_at_last_step": sold, "last_step_at": now.isoformat(),
                          **({"market_step_at": now.isoformat()} if market_step else {}),
                          **({"forecast_step_at": now.isoformat()} if forecast_step else {}),
                          **({"event_step_at": now.isoformat(), "event_name": ev.get("name")} if event_step else {})}},
                upsert=True)
            log.pop("_id", None)
            actions.append(log)

    if actions:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "category": "ramp_ladder",
            "priority": "medium", "target_user": "", "target_role": "manager",
            "title": f"📈 Zam merdiveni: {len(actions)} kademe yükseltildi",
            "message": "Her basamak talep kanıtı veya yeni rezervasyonla (misafir onayı) atıldı. Detay: Zam Merdiveni paneli.",
            "read": False, "created_at": _now().isoformat()})
    await db.ramp_state.delete_many({"property_id": pid, "stay_date": {"$lt": today.isoformat()}})
    return {"property_id": pid, "actions": actions, "skips": skips}


async def ramp_ladder_loop(db, interval_seconds: int = 3600):
    await asyncio.sleep(210)
    while True:
        try:
            for pid in await db.properties.distinct("id"):
                r = await scan_property(db, pid)
                if r.get("actions"):
                    logger.info("Ramp ladder %s: %s kademe", pid, len(r["actions"]))
        except Exception as ex:
            logger.warning("Ramp ladder loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_ramp_ladder_router(db, require_roles):
    router = APIRouter(prefix="/ramp-ladder", tags=["ramp-ladder"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _get_cfg(db, pid)
        q = {} if pid == "all" else {"property_id": pid}
        steps = await db.ramp_steps.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
        states = await db.ramp_state.find(q, {"_id": 0}).to_list(300)
        waiting = [s for s in states if s.get("step_no", 0) >= 1]
        return {"config": cfg, "steps": steps,
                "rules": {"asymmetric_time": ("Zam için zaman geçmesi kanıt DEĞİLDİR — her basamak "
                                              "talep kanıtı veya yeni rezervasyon (misafir onayı) ister. "
                                              "İndirim yönü ise (son-gün merdiveni) bekleyen boş oda + geçen süreyle çalışır.")},
                "summary": {"total_steps": len(steps),
                            "guest_approved_steps": sum(1 for s in steps if s.get("guest_approved")),
                            "reversals": sum(1 for s in steps if s.get("direction") == "down"),
                            "awaiting_approval": len(waiting)},
                "awaiting": [{"stay_date": s["stay_date"], "room_type_id": s["room_type_id"],
                              "step_no": s["step_no"], "bookings_at_last_step": s.get("bookings_at_last_step")}
                             for s in waiting]}

    @router.put("/{pid}/config")
    async def put_config(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {}
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        if "forecast_boost" in data:
            upd["forecast_boost"] = bool(data["forecast_boost"])
        if "event_premium" in data:
            upd["event_premium"] = bool(data["event_premium"])
        if "event_min_score" in data:
            upd["event_min_score"] = max(10, min(100, int(data["event_min_score"])))
        for k, lo, hi in (("window_start", 1, 30), ("window_end", 2, 60),
                          ("max_steps", 1, 6), ("cadence_hours", 1, 48)):
            if data.get(k) is not None:
                upd[k] = max(lo, min(int(data[k]), hi))
        if data.get("step_pct") is not None:
            upd["step_pct"] = max(1.0, min(float(data["step_pct"]), 15.0))
        if data.get("occ_threshold") is not None:
            upd["occ_threshold"] = max(30.0, min(float(data["occ_threshold"]), 95.0))
        if upd:
            await db.ramp_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, "config": await _get_cfg(db, pid)}

    @router.post("/{pid}/scan")
    async def manual_scan(pid: str, force: bool = True, _u: dict = Depends(require_roles(*ROLES))):
        return await scan_property(db, pid, force=force)

    return router
