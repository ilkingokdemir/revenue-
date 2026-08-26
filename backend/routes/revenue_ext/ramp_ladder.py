"""
Misafir-Onaylı Zam Merdiveni (Guest-Approved Ramp Ladder) — RevenueIQ gap P1.
İlk zam talep kanıtıyla (doluluk eşiği) atılır. İKİNCİ ve sonraki basamaklar için
YENİ REZERVASYON şarttır: kimsenin ödemediği fiyata tırmanış matematiksel olarak kapalıdır.
Tavan (standard_max_rate) aşılmaz; tavan yoksa güvenlik sınırı çapa×1.25.
Pencere D2+ (D0-D1 son-gün merdivenine aittir — tek yazıcı). Kira-çit kilidiyle yazar.
Collections: ramp_config, ramp_state, ramp_steps
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import asyncio
import logging

from routes.revenue_ext.write_lease import acquire_lease, lease_holder

logger = logging.getLogger(__name__)

ACTOR = "ramp-ladder"
DEFAULT_CFG = {"enabled": False, "window_start": 2, "window_end": 21,
               "step_pct": 5.0, "max_steps": 3, "occ_threshold": 70.0,
               "cadence_hours": 12}
SAFETY_CAP_MULT = 1.25


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
    for offset in range(int(cfg["window_start"]), int(cfg["window_end"]) + 1):
        day = (today + timedelta(days=offset)).isoformat()
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
            if occ < float(cfg["occ_threshold"]):
                if step_no == 0:
                    continue
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
            if not force and last_step_at:
                elapsed = (now - datetime.fromisoformat(last_step_at)).total_seconds() / 3600
                if elapsed < float(cfg["cadence_hours"]):
                    continue

            # --- MİSAFİR ONAYI: 2. basamak ve sonrası yeni rezervasyon ister ---
            if step_no >= 1:
                if bookings_at_last is None or sold <= int(bookings_at_last):
                    skips.append({"date": day, "room_type": rt.get("name", ""),
                                  "reason": "awaiting_guest_approval",
                                  "detail": (f"Kademe {step_no} fiyatında henüz yeni rezervasyon yok "
                                             f"({sold} = {bookings_at_last}) — misafir onayı gelmeden tırmanış KAPALI")})
                    continue

            if anchor <= 0:
                anchor = await _effective_rate(db, pid, rt_id, day, rt.get("base_price", 0))
            if anchor <= 0:
                continue
            ceiling = await _ceiling_for(db, pid, rt_id, anchor)
            new_step = step_no + 1
            new_rate = round(anchor * ((1 + step_p) ** new_step), 2)
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

            await db.rate_overrides.update_one(
                {"property_id": pid, "room_type_id": rt_id, "date": day},
                {"$set": {"custom_rate": new_rate, "set_by": ACTOR,
                          "reason": f"Zam merdiveni kademe {new_step}: doluluk %{occ:.0f}"
                                    + (f", misafir onayı: +{sold - int(bookings_at_last)} yeni rezervasyon" if step_no >= 1 else " (talep kanıtı)"),
                          "updated_at": now.isoformat()}}, upsert=True)
            log = {"id": str(uuid.uuid4()), "property_id": pid, "stay_date": day,
                   "room_type_id": rt_id, "room_type": rt.get("name", ""),
                   "step_no": new_step, "from_step": step_no, "rate": new_rate,
                   "occ": round(occ, 1), "sold": sold, "ceiling": ceiling,
                   "direction": "up",
                   "guest_approved": step_no >= 1,
                   "reason": "guest_approved_step" if step_no >= 1 else "demand_evidence_step",
                   "created_at": now.isoformat()}
            await db.ramp_steps.insert_one(dict(log))
            await db.ramp_state.update_one(
                {"property_id": pid, "stay_date": day, "room_type_id": rt_id},
                {"$set": {"step_no": new_step, "anchor_rate": anchor,
                          "bookings_at_last_step": sold, "last_step_at": now.isoformat()}},
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
