"""
Gün-İçi Yeniden Fiyatlama (Intraday Re-price) — FLYR "hourly optimization" paritesi.
Son N saatte tek bir konaklama tarihine olağandışı pickup (sıçrama) algılanırsa
AI fiyatlama motorunu ANINDA tetikler (auto-apply açıksa uygular, kapalıysa
resepsiyona/yöneticiye fırsat bildirimi düşer). Cooldown ile tarih başına spam engellenir.
Collections: intraday_reprice_config, intraday_reprice_events
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

DEFAULT_CFG = {"enabled": True, "window_hours": 3, "spike_rooms": 3, "cooldown_hours": 6}


def _now():
    return datetime.now(timezone.utc)


async def _get_cfg(db, property_id: str) -> Dict:
    doc = await db.intraday_reprice_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
    return {**DEFAULT_CFG, **{k: doc[k] for k in DEFAULT_CFG if k in doc}}


async def _occupancy(db, property_id: str, stay_date: str) -> float:
    total = 0
    for rt in await db.room_types.find({"property_id": property_id}, {"_id": 0, "total_rooms": 1}).to_list(50):
        total += int(rt.get("total_rooms", 0))
    if total <= 0:
        return 0.0
    booked = await db.bookings.count_documents({
        "property_id": property_id, "status": {"$in": ["confirmed", "checked_in"]},
        "check_in": {"$lte": stay_date}, "check_out": {"$gt": stay_date}})
    return round(booked / total * 100, 1)


async def scan_property(db, property_id: str, auto_apply_fn=None) -> Dict:
    """Tek tesis için sıçrama taraması; spike bulursa re-price tetikler."""
    cfg = await _get_cfg(db, property_id)
    if not cfg["enabled"]:
        return {"property_id": property_id, "skipped": "disabled", "spikes": []}
    now = _now()
    since = (now - timedelta(hours=int(cfg["window_hours"]))).isoformat()
    today = now.strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"property_id": property_id, "created_at": {"$gte": since},
                    "status": {"$in": ["confirmed", "checked_in"]},
                    "check_in": {"$gte": today}}},
        {"$group": {"_id": "$check_in", "rooms": {"$sum": 1}}},
    ]
    spikes = []
    async for r in db.bookings.aggregate(pipeline):
        if int(r["rooms"]) >= int(cfg["spike_rooms"]):
            spikes.append({"date": r["_id"], "rooms": int(r["rooms"])})
    results = []
    for sp in spikes:
        cooldown_after = (now - timedelta(hours=int(cfg["cooldown_hours"]))).isoformat()
        recent = await db.intraday_reprice_events.find_one({
            "property_id": property_id, "stay_date": sp["date"],
            "created_at": {"$gte": cooldown_after}}, {"_id": 0})
        if recent:
            continue
        occ = await _occupancy(db, property_id, sp["date"])
        action, applied = "suggested", 0
        if auto_apply_fn:
            try:
                res = await auto_apply_fn(property_id)
                applied = int(res.get("applied", 0))
                if applied > 0:
                    action = "auto_applied"
            except Exception as ex:
                logger.warning("Intraday auto-apply failed: %s", ex)
        event = {"id": str(uuid.uuid4()), "property_id": property_id,
                 "stay_date": sp["date"], "rooms_picked": sp["rooms"],
                 "window_hours": cfg["window_hours"], "occupancy_pct": occ,
                 "action": action, "applied_count": applied,
                 "created_at": now.isoformat()}
        await db.intraday_reprice_events.insert_one(dict(event))
        event.pop("_id", None)
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id,
            "category": "intraday_reprice", "priority": "high",
            "target_user": "", "target_role": "manager",
            "title": f"⚡ Pickup sıçraması — {sp['date']}: {sp['rooms']} oda / {cfg['window_hours']} saat",
            "message": (f"Doluluk %{occ}. " +
                        (f"AI {applied} fiyat güncellemesini otomatik uyguladı."
                         if action == "auto_applied"
                         else "AI fiyat önerileri hazır — AI Pricing panelinden inceleyin.")),
            "read": False, "created_at": now.isoformat()})
        results.append(event)
    return {"property_id": property_id, "window_hours": cfg["window_hours"],
            "spikes_detected": len(spikes), "actions": results}


async def run_intraday_scan(db, auto_apply_fn=None, property_id: str = "") -> Dict:
    if property_id and property_id != "all":
        pids = [property_id]
    else:
        pids = await db.properties.distinct("id")
    out, total_actions = [], 0
    for pid in pids:
        r = await scan_property(db, pid, auto_apply_fn)
        if r.get("actions"):
            total_actions += len(r["actions"])
            out.append(r)
    return {"properties_scanned": len(pids), "properties_with_spikes": len(out),
            "actions": total_actions, "details": out}


async def intraday_reprice_loop(db, auto_apply_fn=None, interval_seconds: int = 1800):
    await asyncio.sleep(90)
    while True:
        try:
            r = await run_intraday_scan(db, auto_apply_fn)
            if r["actions"]:
                logger.info("Intraday reprice: %s aksiyon", r["actions"])
        except Exception as ex:
            logger.warning("Intraday reprice loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_intraday_reprice_router(db, require_roles, auto_apply_fn=None):
    router = APIRouter(prefix="/intraday-reprice")
    router.run_scan_internal = lambda pid="": run_intraday_scan(db, auto_apply_fn, pid)

    @router.get("/{property_id}")
    async def status(property_id: str,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await _get_cfg(db, property_id if property_id != "all" else "all")
        q = {} if property_id == "all" else {"property_id": property_id}
        events = await db.intraday_reprice_events.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
        last24 = (_now() - timedelta(hours=24)).isoformat()
        return {"config": cfg, "events": events,
                "summary": {"events_24h": sum(1 for e in events if e["created_at"] >= last24),
                            "auto_applied_total": sum(e.get("applied_count", 0) for e in events),
                            "total_events": len(events)}}

    @router.put("/{property_id}/config")
    async def put_config(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = {}
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        for k, lo, hi in (("window_hours", 1, 12), ("spike_rooms", 2, 20), ("cooldown_hours", 1, 24)):
            if k in data and data[k] is not None:
                upd[k] = max(lo, min(int(data[k]), hi))
        if upd:
            await db.intraday_reprice_config.update_one(
                {"property_id": property_id}, {"$set": upd}, upsert=True)
        return {"ok": True, "config": await _get_cfg(db, property_id)}

    @router.post("/{property_id}/scan")
    async def manual_scan(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_intraday_scan(db, auto_apply_fn, property_id)

    return router
