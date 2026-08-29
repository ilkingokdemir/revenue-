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
    return {"allowed": True, "rate": result_rate, "clamped": clamped, "blocked_reason": None}


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

    return router
