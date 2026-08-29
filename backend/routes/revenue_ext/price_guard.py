"""Fiyat Güvenlik Sınırları — tüm otomatik fiyat yazımları için merkezi korkuluk.
Kurallar: tek hamlede max %X (vars. 10), 72 saatte kümülatif max %Y (vars. 25),
elle kilitlenen (owner-override) gecelere dokunulmaz."""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

DEFAULTS = {"enabled": True, "max_single_pct": 10.0, "max_72h_pct": 25.0}


def _now():
    return datetime.now(timezone.utc)


async def _guard_cfg(db, pid: str) -> dict:
    doc = await db.price_guard_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULTS, **{k: doc[k] for k in DEFAULTS if k in doc}}


async def guard_rate_change(db, pid: str, rt_id: str, date: str,
                            old_rate: float, new_rate: float, actor: str) -> dict:
    """Merkezi korkuluk. Dönen: {allowed, rate, clamped, blocked_reason}."""
    cfg = await _guard_cfg(db, pid)
    if not cfg["enabled"] or old_rate <= 0:
        return {"allowed": True, "rate": new_rate, "clamped": False, "blocked_reason": None}

    # 1) Elle kilitli gece — dokunma
    lock = await db.rate_overrides.find_one(
        {"property_id": pid, "room_type_id": rt_id, "date": date, "set_by": "owner-override"},
        {"_id": 0, "set_by": 1})
    if lock and actor != "owner-override":
        return {"allowed": False, "rate": old_rate, "clamped": False,
                "blocked_reason": "Gece elle kilitli (owner-override) — otomatik aktörler dokunamaz"}

    result_rate, clamped = new_rate, False

    # 2) Tek hamle limiti
    max_single = float(cfg["max_single_pct"]) / 100.0
    change = (new_rate - old_rate) / old_rate
    if abs(change) > max_single:
        result_rate = round(old_rate * (1 + (max_single if change > 0 else -max_single)), 2)
        clamped = True

    # 3) 72 saatlik kümülatif artış limiti (yalnız zamlar)
    if result_rate > old_rate:
        since = (_now() - timedelta(hours=72)).isoformat()
        base = None
        async for lg in db.price_guard_log.find(
                {"property_id": pid, "room_type_id": rt_id, "date": date,
                 "at": {"$gte": since}}, {"_id": 0, "old_rate": 1, "at": 1}).sort("at", 1).limit(1):
            base = float(lg["old_rate"])
        base = base if base and base > 0 else old_rate
        max_cum = float(cfg["max_72h_pct"]) / 100.0
        cum_ceiling = round(base * (1 + max_cum), 2)
        if result_rate > cum_ceiling:
            if cum_ceiling <= old_rate:
                return {"allowed": False, "rate": old_rate, "clamped": False,
                        "blocked_reason": f"72 saatlik kümülatif artış limiti (%{cfg['max_72h_pct']}) doldu — taban £{base}, tavan £{cum_ceiling}"}
            result_rate = cum_ceiling
            clamped = True

    await db.price_guard_log.insert_one({
        "id": str(uuid.uuid4()), "property_id": pid, "room_type_id": rt_id, "date": date,
        "old_rate": old_rate, "requested_rate": new_rate, "final_rate": result_rate,
        "clamped": clamped, "actor": actor, "at": _now().isoformat()})
    if clamped:
        await _maybe_alert_repeated_clamps(db, pid, actor)
    return {"allowed": True, "rate": result_rate, "clamped": clamped, "blocked_reason": None}


async def _maybe_alert_repeated_clamps(db, pid: str, actor: str):
    """Aynı aktör 24 saatte ≥3 kez kırpıldıysa yöneticiye bir kez uyarı gönder."""
    since = (_now() - timedelta(hours=24)).isoformat()
    clamps = await db.price_guard_log.count_documents(
        {"property_id": pid, "actor": actor, "clamped": True, "at": {"$gte": since}})
    if clamps < 3:
        return
    key = {"property_id": pid, "actor": actor}
    alert = await db.price_guard_alerts.find_one(key, {"_id": 0, "last_alert_at": 1})
    if alert and alert.get("last_alert_at", "") >= since:
        return
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "title": "🛡 Fiyat korkuluğu sık devreye giriyor",
        "message": (f"{pid}: '{actor}' aktörü son 24 saatte {clamps} kez güvenlik sınırına takıldı. "
                    "Motor limitlerin üzerinde fiyat istiyor — güvenlik ayarlarını (tek hamle % / 72s %) "
                    "veya motorun adım büyüklüğünü gözden geçirin."),
        "category": "revenue", "priority": "high", "read": False, "created_at": _now().isoformat()})
    await db.price_guard_alerts.update_one(key, {"$set": {"last_alert_at": _now().isoformat(),
                                                          "clamps_24h": clamps}}, upsert=True)


def create_price_guard_router(db, require_roles):
    router = APIRouter(tags=["price-guard"])
    ROLES = ("admin", "manager")

    @router.get("/price-guard/{property_id}")
    async def get_settings(property_id: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _guard_cfg(db, property_id)
        recent = await db.price_guard_log.find(
            {"property_id": property_id}, {"_id": 0}).sort("at", -1).to_list(20)
        clamps = sum(1 for r in recent if r.get("clamped"))
        return {**cfg, "recent_log": recent, "recent_clamps": clamps}

    @router.put("/price-guard/{property_id}")
    async def put_settings(property_id: str, body: dict, _u: dict = Depends(require_roles(*ROLES))):
        sets = {}
        if "enabled" in body:
            sets["enabled"] = bool(body["enabled"])
        for key, lo, hi in (("max_single_pct", 1, 50), ("max_72h_pct", 5, 100)):
            if key in body:
                try:
                    v = float(body[key])
                except (TypeError, ValueError):
                    raise HTTPException(422, f"{key} sayı olmalı")
                if not lo <= v <= hi:
                    raise HTTPException(422, f"{key} {lo}-{hi} arası olmalı")
                sets[key] = v
        if not sets:
            raise HTTPException(422, "Güncellenecek alan yok")
        sets["updated_at"] = _now().isoformat()
        sets["updated_by"] = _u.get("email", "")
        await db.price_guard_settings.update_one({"property_id": property_id}, {"$set": sets}, upsert=True)
        return {"ok": True, **(await _guard_cfg(db, property_id))}

    @router.get("/price-timeline/{property_id}")
    async def price_timeline(property_id: str, date: str,
                             _u: dict = Depends(require_roles(*ROLES))):
        """Bir gecenin fiyat yolculuğu — kademe kademe, gerekçeli, tek zaman çizelgesi."""
        events = []
        async for s in db.ramp_steps.find(
                {"property_id": property_id, "stay_date": date}, {"_id": 0}):
            events.append({"at": s.get("created_at"), "type": "ladder",
                           "rate": s.get("rate"), "room_type": s.get("room_type", ""),
                           "title": (f"DEMAND_STRONG piyasa kademesi {s.get('step_no')}" if s.get("reason") == "DEMAND_STRONG"
                                     else f"{'Kademe geri alındı' if s.get('direction') == 'down' else 'Zam merdiveni kademe ' + str(s.get('step_no'))}"),
                           "detail": (f"Doluluk %{s.get('occ')} · {s.get('sold')} satış · tavan £{s.get('ceiling')}"
                                      + (" · güvenlik sınırı uygulandı" if s.get("guard_clamped") else "")),
                           "reason": s.get("reason", "")})
        async for g in db.price_guard_log.find(
                {"property_id": property_id, "date": date, "clamped": True}, {"_id": 0}):
            events.append({"at": g.get("at"), "type": "guard", "rate": g.get("final_rate"),
                           "room_type": g.get("room_type_id", ""),
                           "title": "Güvenlik sınırı kırptı",
                           "detail": f"İstenen £{g.get('requested_rate')} → yayınlanan £{g.get('final_rate')} ({g.get('actor')})",
                           "reason": "price_guard"})
        async for o in db.rate_overrides.find(
                {"property_id": property_id, "date": date}, {"_id": 0}):
            events.append({"at": o.get("updated_at") or o.get("created_at"), "type": "override",
                           "rate": o.get("custom_rate"), "room_type": o.get("room_type_id", ""),
                           "title": f"Güncel fiyat ({o.get('set_by', '?')})",
                           "detail": o.get("reason", ""), "reason": o.get("set_by", "")})
        fresh = (_now() - timedelta(hours=48)).isoformat()
        comps = [float(s.get("rate") or 0) async for s in db.comp_rate_snapshots.find(
            {"property_id": {"$in": [property_id, "default"]}, "date": date,
             "scanned_at": {"$gte": fresh}}, {"_id": 0, "rate": 1})]
        comps = sorted([c for c in comps if c > 0])
        comp_median = (comps[len(comps) // 2] if len(comps) % 2 else
                       (comps[len(comps) // 2 - 1] + comps[len(comps) // 2]) / 2) if comps else None
        events = [e for e in events if e.get("at")]
        events.sort(key=lambda e: e["at"])
        return {"date": date, "events": events, "comp_median": comp_median, "comp_count": len(comps)}

    return router
