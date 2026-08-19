"""Fiyat Bekçileri: POBA (portföy doluluk zammı, PriceLabs paritesi) + Surge Koruması (RPG paritesi)."""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def _occupancy_map(db, pid: str, days: int) -> dict:
    total_rooms = await db.rooms.count_documents({"property_id": pid}) or 10
    today = datetime.now(timezone.utc).date()
    end = today + timedelta(days=days)
    bks = await db.bookings.find(
        {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
         "check_out": {"$gt": today.isoformat()}, "check_in": {"$lt": end.isoformat()}},
        {"_id": 0, "check_in": 1, "check_out": 1, "created_at": 1}).to_list(4000)
    out = {}
    for i in range(days):
        d = (today + timedelta(days=i)).isoformat()
        cnt = sum(1 for b in bks if str(b.get("check_in")) <= d < str(b.get("check_out")))
        out[d] = {"occ_pct": round(cnt / total_rooms * 100, 1), "rooms_sold": cnt, "total": total_rooms}
    return out


async def _base_and_guardrails(db, pid: str):
    setup = await db.rms_setup.find_one({"property_id": pid}, {"_id": 0}) or {}
    base = float(setup.get("base_price") or 0)
    if base <= 0:
        rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0, "base_rate": 1, "base_price": 1})
        base = float((rt or {}).get("base_rate") or (rt or {}).get("base_price") or 100)
    lo = float(setup.get("min_rate") or 0) or base * 0.6
    hi = float(setup.get("max_rate") or 0) or base * 3.0
    return base, lo, hi


async def run_price_guards(db, pid: str) -> dict:
    """POBA + Surge kontrolünü çalıştırır; aksiyonları log'lar. Worker ve API ortak kullanır."""
    cfg = await db.price_guards.find_one({"property_id": pid}, {"_id": 0}) or {}
    poba = cfg.get("poba") or {}
    surge = cfg.get("surge") or {}
    actions = []
    base, lo, hi = await _base_and_guardrails(db, pid)

    # ---- POBA: portföy doluluk eşiği aşılınca kalan envantere zam ----
    if poba.get("enabled"):
        days = int(poba.get("days_ahead") or 30)
        thr = float(poba.get("occ_threshold_pct") or 80)
        uplift = float(poba.get("uplift_pct") or 10)
        occ = await _occupancy_map(db, pid, days)
        for d, v in occ.items():
            if v["occ_pct"] < thr:
                continue
            existing = await db.rate_overrides.find_one(
                {"property_id": pid, "date": d, "room_type_id": ""}, {"_id": 0, "custom_rate": 1, "set_by": 1})
            cur = float((existing or {}).get("custom_rate") or base)
            new_rate = round(min(cur * (1 + uplift / 100), hi), 2)
            if new_rate <= cur or (existing or {}).get("set_by") == "poba_guard":
                continue
            await db.rate_overrides.update_one(
                {"property_id": pid, "date": d, "room_type_id": ""},
                {"$set": {"property_id": pid, "room_type_id": "", "date": d, "custom_rate": new_rate,
                          "set_by": "poba_guard",
                          "reason": f"POBA: doluluk %{v['occ_pct']} ≥ eşik %{thr} → +%{uplift}",
                          "updated_at": now_iso()}}, upsert=True)
            actions.append({"guard": "poba", "date": d, "occ_pct": v["occ_pct"],
                            "old_rate": cur, "new_rate": new_rate})

    # ---- SURGE: son 24 saatte ani pickup → alarm + koruma tavanı ----
    if surge.get("enabled"):
        horizon = int(surge.get("horizon_days") or 30)
        thr = int(surge.get("pickup_threshold") or 5)
        mult = float(surge.get("cap_multiplier") or 1.3)
        act = surge.get("action") or "alert_and_cap"
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        today = datetime.now(timezone.utc).date()
        end = (today + timedelta(days=horizon)).isoformat()
        recent = await db.bookings.find(
            {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
             "created_at": {"$gte": since}, "check_in": {"$gte": today.isoformat(), "$lt": end}},
            {"_id": 0, "check_in": 1}).to_list(2000)
        pickup = {}
        for b in recent:
            pickup[b["check_in"]] = pickup.get(b["check_in"], 0) + 1
        for d, cnt in pickup.items():
            if cnt < thr:
                continue
            already = await db.price_guard_log.find_one(
                {"property_id": pid, "guard": "surge", "date": d,
                 "created_at": {"$gte": since}}, {"_id": 1})
            if already:
                continue
            protect = round(min(base * mult, hi), 2)
            detail = {"guard": "surge", "date": d, "pickup_24h": cnt, "protect_rate": protect}
            if act == "alert_and_cap":
                await db.rate_overrides.update_one(
                    {"property_id": pid, "date": d, "room_type_id": ""},
                    {"$set": {"property_id": pid, "room_type_id": "", "date": d, "custom_rate": protect,
                              "set_by": "surge_guard",
                              "reason": f"Surge: 24 saatte {cnt} rezervasyon → koruma fiyatı",
                              "updated_at": now_iso()}}, upsert=True)
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "property_id": pid, "type": "surge_alert",
                "title": f"⚡ Talep sıçraması: {d}",
                "message": f"Son 24 saatte {cnt} yeni rezervasyon ({d}). "
                           + (f"Fiyat koruma tavanına çekildi: £{protect}" if act == "alert_and_cap" else "Fiyatı gözden geçirin."),
                "read": False, "created_at": now_iso()})
            actions.append(detail)

    for a in actions:
        await db.price_guard_log.insert_one({"id": str(uuid.uuid4()), "property_id": pid,
                                             **a, "created_at": now_iso()})
    return {"property_id": pid, "actions": actions, "count": len(actions)}


def create_price_guards_router(db, require_roles):
    router = APIRouter(prefix="/price-guards", tags=["price-guards"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def get_guards(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await db.price_guards.find_one({"property_id": pid}, {"_id": 0}) or {"property_id": pid}
        log = await db.price_guard_log.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(40)
        return {"config": cfg, "log": log}

    @router.post("/{pid}/poba")
    async def set_poba(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        cfg = {"enabled": bool(data.get("enabled")),
               "occ_threshold_pct": max(30, min(100, float(data.get("occ_threshold_pct") or 80))),
               "uplift_pct": max(1, min(50, float(data.get("uplift_pct") or 10))),
               "days_ahead": max(7, min(90, int(data.get("days_ahead") or 30)))}
        await db.price_guards.update_one({"property_id": pid},
                                         {"$set": {"property_id": pid, "poba": cfg, "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "poba": cfg}

    @router.post("/{pid}/surge")
    async def set_surge(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        action = data.get("action") or "alert_and_cap"
        if action not in ("alert_only", "alert_and_cap"):
            raise HTTPException(422, "action: alert_only|alert_and_cap")
        cfg = {"enabled": bool(data.get("enabled")),
               "pickup_threshold": max(2, min(50, int(data.get("pickup_threshold") or 5))),
               "horizon_days": max(7, min(90, int(data.get("horizon_days") or 30))),
               "cap_multiplier": max(1.05, min(3.0, float(data.get("cap_multiplier") or 1.3))),
               "action": action}
        await db.price_guards.update_one({"property_id": pid},
                                         {"$set": {"property_id": pid, "surge": cfg, "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "surge": cfg}

    @router.post("/{pid}/run")
    async def run_now(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await run_price_guards(db, pid)

    return router
