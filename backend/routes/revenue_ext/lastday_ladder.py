"""
Son-Gün Merdiveni (Last-Minute Ladder) — RevenueIQ gap P0.
Varışa 0-N gün kala satılmamış odalar cadence aralıklarıyla kademeli iner (~%8/kademe);
oda satılınca yön DÖNER (bir kademe geri çıkar). Operatör tabanının (min_rate_floors)
altına asla inmez — taban tanımlı değilse fail-closed: hiç dokunmaz.
Manuel/pin override'a saygı: başka aktör yakın zamanda yazdıysa o gece atlanır.
Collections: ladder_config, ladder_state, ladder_steps
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
import uuid
import asyncio
import logging

from routes.revenue_ext.write_lease import acquire_lease, lease_holder

logger = logging.getLogger(__name__)

ACTOR = "lastday-ladder"
DEFAULT_CFG = {"enabled": False, "window_days": 1, "cadence_hours": 4,
               "step_pct": 8.0, "max_steps": 3}


def _now():
    return datetime.now(timezone.utc)


async def _get_cfg(db, pid: str) -> Dict:
    doc = await db.ladder_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULT_CFG, **{k: doc[k] for k in DEFAULT_CFG if k in doc}}


async def _floor_for(db, pid: str, rt_id: str):
    rule = (await db.min_rate_floors.find_one({"property_id": pid, "room_type_id": rt_id}, {"_id": 0})
            or await db.min_rate_floors.find_one({"property_id": pid, "room_type_id": "all"}, {"_id": 0}))
    if not rule:
        return None
    near = rule.get("near_term_min_rate")
    std = rule.get("standard_min_rate")
    if near is not None:
        return float(near)
    if std is not None:
        return float(std)
    return None


async def _effective_rate(db, pid: str, rt_id: str, day: str, base_price: float) -> float:
    for q_rt in (rt_id, ""):
        ov = await db.rate_overrides.find_one(
            {"property_id": pid, "room_type_id": q_rt, "date": day}, {"_id": 0})
        if ov and ov.get("custom_rate"):
            return float(ov["custom_rate"])
    return float(base_price or 0)


async def _sold_count(db, pid: str, rt_id: str, day: str) -> int:
    return await db.bookings.count_documents({
        "property_id": pid, "room_type_id": rt_id,
        "status": {"$nin": ["cancelled", "no_show"]},
        "check_in": {"$lte": day}, "check_out": {"$gt": day}})


async def _write_rate(db, pid: str, rt_id: str, day: str, rate: float, reason: str):
    await db.rate_overrides.update_one(
        {"property_id": pid, "room_type_id": rt_id, "date": day},
        {"$set": {"custom_rate": round(rate, 2), "set_by": ACTOR,
                  "reason": reason, "updated_at": _now().isoformat()}},
        upsert=True)


async def scan_property(db, pid: str, force: bool = False) -> Dict:
    cfg = await _get_cfg(db, pid)
    if not cfg["enabled"]:
        return {"property_id": pid, "skipped": "disabled", "actions": []}
    now = _now()
    today = now.date()
    room_types = await db.room_types.find(
        {"property_id": pid}, {"_id": 0, "id": 1, "name": 1, "base_price": 1, "total_rooms": 1}).to_list(50)
    actions, skips = [], []
    for offset in range(0, int(cfg["window_days"]) + 1):
        day = (today + timedelta(days=offset)).isoformat()
        for rt in room_types:
            rt_id = rt["id"]
            total = int(rt.get("total_rooms", 0))
            if total <= 0:
                continue
            sold = await _sold_count(db, pid, rt_id, day)
            unsold = total - sold
            st = await db.ladder_state.find_one(
                {"property_id": pid, "stay_date": day, "room_type_id": rt_id}, {"_id": 0}) or {}
            step_no = int(st.get("step_no", 0))
            anchor = float(st.get("anchor_rate") or 0)
            last_step_at = st.get("last_step_at")
            last_sold = int(st.get("last_sold", sold))
            floor = await _floor_for(db, pid, rt_id)
            step_p = float(cfg["step_pct"]) / 100.0

            # --- REVERSAL: satış geldiyse bir kademe geri çık ---
            if sold > last_sold and step_no > 0:
                if await acquire_lease(db, pid, rt_id, day, ACTOR) is None:
                    skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "lease_held",
                                  "detail": f"Hücre kirası '{await lease_holder(db, pid, rt_id, day)}' aktöründe"})
                    continue
                new_step = step_no - 1
                new_rate = anchor * ((1 - step_p) ** new_step)
                if floor is not None:
                    new_rate = max(new_rate, floor)
                await _write_rate(db, pid, rt_id, day, new_rate,
                                  f"Son-gün merdiveni: satış geldi — kademe {step_no}→{new_step} (geri çıkış)")
                log = {"id": str(uuid.uuid4()), "property_id": pid, "stay_date": day,
                       "room_type_id": rt_id, "room_type": rt.get("name", ""),
                       "direction": "up", "step_no": new_step, "from_step": step_no,
                       "rate": round(new_rate, 2), "sold": sold, "unsold": unsold,
                       "reason": "sale_reversal", "created_at": now.isoformat()}
                await db.ladder_steps.insert_one(dict(log))
                await db.ladder_state.update_one(
                    {"property_id": pid, "stay_date": day, "room_type_id": rt_id},
                    {"$set": {"step_no": new_step, "last_sold": sold,
                              "last_step_at": now.isoformat(), "anchor_rate": anchor}}, upsert=True)
                actions.append(log)
                continue

            if unsold <= 0:
                await db.ladder_state.update_one(
                    {"property_id": pid, "stay_date": day, "room_type_id": rt_id},
                    {"$set": {"last_sold": sold}}, upsert=True)
                continue

            # --- FAIL-CLOSED: taban yoksa dokunma ---
            if floor is None:
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "floor_missing",
                              "detail": "Minimum fiyat tabanı tanımlı değil — fail-closed, merdiven pas geçti"})
                continue

            if step_no >= int(cfg["max_steps"]):
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "max_steps"})
                continue

            # cadence kontrolü
            if not force and last_step_at:
                elapsed = (now - datetime.fromisoformat(last_step_at)).total_seconds() / 3600
                if elapsed < float(cfg["cadence_hours"]):
                    continue

            # pin/manuel saygısı: başka aktör bizden sonra yazdıysa atla
            pin = None
            for q_rt in (rt_id, ""):
                ov = await db.rate_overrides.find_one(
                    {"property_id": pid, "room_type_id": q_rt, "date": day}, {"_id": 0})
                if ov and ov.get("set_by") and ov["set_by"] != ACTOR:
                    if not last_step_at or (ov.get("updated_at") or "") > last_step_at:
                        pin = ov["set_by"]
                        break
            if pin and step_no > 0:
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "pin_respected",
                              "detail": f"'{pin}' fiyatı sabitledi — merdiven dokunmuyor (açıkça raporlanır)"})
                continue

            if anchor <= 0:
                anchor = await _effective_rate(db, pid, rt_id, day, rt.get("base_price", 0))
            if anchor <= 0:
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "no_rate"})
                continue

            new_step = step_no + 1
            new_rate = anchor * ((1 - step_p) ** new_step)
            if new_rate < floor:
                new_rate = floor
            current = anchor * ((1 - step_p) ** step_no)
            if round(new_rate, 2) >= round(max(current, floor), 2) and step_no > 0:
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "at_floor"})
                continue

            if await acquire_lease(db, pid, rt_id, day, ACTOR) is None:
                skips.append({"date": day, "room_type": rt.get("name", ""), "reason": "lease_held",
                              "detail": f"Hücre kirası '{await lease_holder(db, pid, rt_id, day)}' aktöründe — çit yazımı engelledi"})
                continue
            await _write_rate(db, pid, rt_id, day, new_rate,
                              f"Son-gün merdiveni: kademe {new_step}/{cfg['max_steps']} (−%{cfg['step_pct']}) — {unsold} oda boş")
            log = {"id": str(uuid.uuid4()), "property_id": pid, "stay_date": day,
                   "room_type_id": rt_id, "room_type": rt.get("name", ""),
                   "direction": "down", "step_no": new_step, "from_step": step_no,
                   "rate": round(new_rate, 2), "floor": floor, "sold": sold, "unsold": unsold,
                   "reason": "unsold_step", "created_at": now.isoformat()}
            await db.ladder_steps.insert_one(dict(log))
            await db.ladder_state.update_one(
                {"property_id": pid, "stay_date": day, "room_type_id": rt_id},
                {"$set": {"step_no": new_step, "anchor_rate": anchor, "last_sold": sold,
                          "last_step_at": now.isoformat()}}, upsert=True)
            actions.append(log)

    if actions:
        downs = sum(1 for a in actions if a["direction"] == "down")
        ups = len(actions) - downs
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "category": "lastday_ladder",
            "priority": "medium", "target_user": "", "target_role": "manager",
            "title": f"🪜 Son-gün merdiveni: {downs} indirim kademesi, {ups} geri çıkış",
            "message": "Detaylar Son-Gün Merdiveni panelinde. Taban koruması aktif, pin'ler dokunulmadı.",
            "read": False, "created_at": _now().isoformat()})
    # eski state temizliği
    await db.ladder_state.delete_many({"property_id": pid, "stay_date": {"$lt": today.isoformat()}})
    return {"property_id": pid, "actions": actions, "skips": skips}


async def run_ladder_scan(db, property_id: str = "") -> Dict:
    pids = [property_id] if property_id and property_id != "all" else await db.properties.distinct("id")
    out, total = [], 0
    for pid in pids:
        r = await scan_property(db, pid)
        if r.get("actions") or r.get("skips"):
            total += len(r.get("actions", []))
            out.append(r)
    return {"properties_scanned": len(pids), "actions": total, "details": out}


async def lastday_ladder_loop(db, interval_seconds: int = 1800):
    await asyncio.sleep(120)
    while True:
        try:
            r = await run_ladder_scan(db)
            if r["actions"]:
                logger.info("Lastday ladder: %s kademe", r["actions"])
        except Exception as ex:
            logger.warning("Lastday ladder loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_lastday_ladder_router(db, require_roles):
    router = APIRouter(prefix="/lastday-ladder", tags=["lastday-ladder"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _get_cfg(db, pid)
        q = {} if pid == "all" else {"property_id": pid}
        steps = await db.ladder_steps.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
        states = await db.ladder_state.find(q, {"_id": 0}).to_list(200)
        last24 = (_now() - timedelta(hours=24)).isoformat()
        return {"config": cfg, "steps": steps,
                "rules": {"asymmetric_time": ("İndirim için zaman geçmesi kanıttır: D0-D1'de bekleyen boş oda "
                                              "her ritimde bir kademe iner. Zam yönü ise yalnız SATIŞ kanıtıyla döner — "
                                              "geçen süre asla fiyatı yukarı itmez.")},
                "owned_dates": sorted({s["stay_date"] for s in states if s.get("step_no", 0) > 0}),
                "summary": {"steps_24h": sum(1 for s in steps if s["created_at"] >= last24),
                            "reversals": sum(1 for s in steps if s["direction"] == "up"),
                            "active_ladders": sum(1 for s in states if s.get("step_no", 0) > 0)}}

    @router.put("/{pid}/config")
    async def put_config(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {}
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        for k, lo, hi in (("window_days", 0, 3), ("cadence_hours", 1, 12), ("max_steps", 1, 6)):
            if k in data and data[k] is not None:
                upd[k] = max(lo, min(int(data[k]), hi))
        if data.get("step_pct") is not None:
            upd["step_pct"] = max(1.0, min(float(data["step_pct"]), 20.0))
        if upd:
            await db.ladder_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, "config": await _get_cfg(db, pid)}

    @router.post("/{pid}/scan")
    async def manual_scan(pid: str, force: bool = True, _u: dict = Depends(require_roles(*ROLES))):
        if pid == "all":
            return await run_ladder_scan(db)
        return await scan_property(db, pid, force=force)

    return router
