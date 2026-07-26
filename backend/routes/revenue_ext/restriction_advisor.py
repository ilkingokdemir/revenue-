"""
AI Kısıtlama Danışmanı (Restriction Advisor) — FLYR "AI-driven restriction
recommendations" paritesi. Yüksek talepli geceleri tespit eder, MLOS (min konaklama)
ve CTA (varışa kapalı) önerileri üretir; kabulde tüm bağlı kanallara kısıtlama
yazar ve OTA sync kuyruğunu tetikler.
Collection: restriction_recommendations {id, property_id, date, occupancy_pct,
  rec_type: mlos|cta, min_los, rationale, status: pending|accepted|rejected}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

DEFAULTS = {"days_ahead": 60, "mlos2_occ": 80, "mlos3_occ": 92, "cta_occ": 95}


def _iso():
    return datetime.now(timezone.utc).isoformat()


async def _total_rooms(db, property_id: str) -> int:
    total = 0
    for rt in await db.room_types.find({"property_id": property_id}, {"_id": 0, "total_rooms": 1}).to_list(50):
        total += int(rt.get("total_rooms", 0))
    return total


async def scan_property(db, property_id: str, cfg: Dict = None) -> Dict:
    cfg = {**DEFAULTS, **(cfg or {})}
    total = await _total_rooms(db, property_id)
    if total <= 0:
        return {"property_id": property_id, "recommendations": 0, "skipped": "no rooms"}
    today = ddate.today()
    horizon_end = (today + timedelta(days=int(cfg["days_ahead"]))).isoformat()
    bookings = await db.bookings.find({
        "property_id": property_id, "status": {"$in": ["confirmed", "checked_in"]},
        "check_in": {"$lte": horizon_end}, "check_out": {"$gt": today.isoformat()},
    }, {"_id": 0, "check_in": 1, "check_out": 1}).to_list(8000)
    occ_by_date: Dict[str, int] = {}
    for b in bookings:
        try:
            ci = ddate.fromisoformat(b["check_in"][:10])
            co = ddate.fromisoformat(b["check_out"][:10])
        except Exception:
            continue
        d = max(ci, today)
        while d < co and d <= today + timedelta(days=int(cfg["days_ahead"])):
            occ_by_date[d.isoformat()] = occ_by_date.get(d.isoformat(), 0) + 1
            d += timedelta(days=1)

    existing = {}
    async for r in db.channel_restrictions.find({
            "property_id": property_id, "date": {"$gte": today.isoformat(), "$lte": horizon_end}},
            {"_id": 0, "date": 1, "min_los": 1, "closed_to_arrival": 1}):
        e = existing.setdefault(r["date"], {"min_los": 0, "cta": False})
        e["min_los"] = max(e["min_los"], int(r.get("min_los") or 0))
        e["cta"] = e["cta"] or bool(r.get("closed_to_arrival"))

    recent_rejects = set()
    reject_after = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    async for r in db.restriction_recommendations.find({
            "property_id": property_id, "status": "rejected", "created_at": {"$gte": reject_after}},
            {"_id": 0, "date": 1, "rec_type": 1}):
        recent_rejects.add((r["date"], r["rec_type"]))

    await db.restriction_recommendations.delete_many({"property_id": property_id, "status": "pending"})
    created = 0
    for ds in sorted(occ_by_date):
        occ = round(occ_by_date[ds] / total * 100, 1)
        ex = existing.get(ds, {"min_los": 0, "cta": False})
        rec_mlos = 3 if occ >= cfg["mlos3_occ"] else (2 if occ >= cfg["mlos2_occ"] else 0)
        if rec_mlos and ex["min_los"] < rec_mlos and (ds, "mlos") not in recent_rejects:
            await db.restriction_recommendations.insert_one({
                "id": str(uuid.uuid4()), "property_id": property_id, "date": ds,
                "occupancy_pct": occ, "rec_type": "mlos", "min_los": rec_mlos,
                "rationale": f"Doluluk %{occ} — tek gecelik rezervasyonlar yüksek talepli geceyi bölmesin; min {rec_mlos} gece önerilir.",
                "status": "pending", "created_at": _iso()})
            created += 1
        if occ >= cfg["cta_occ"] and not ex["cta"] and (ds, "cta") not in recent_rejects:
            await db.restriction_recommendations.insert_one({
                "id": str(uuid.uuid4()), "property_id": property_id, "date": ds,
                "occupancy_pct": occ, "rec_type": "cta", "min_los": 0,
                "rationale": f"Doluluk %{occ} — neredeyse dolu; yeni varışlara kapatıp kalan odaları uzun konaklamalara/upgrade'e saklayın.",
                "status": "pending", "created_at": _iso()})
            created += 1
    return {"property_id": property_id, "recommendations": created,
            "dates_scanned": len(occ_by_date)}


async def run_restriction_advisor(db, property_id: str = "") -> Dict:
    pids = [property_id] if property_id and property_id != "all" else await db.properties.distinct("id")
    total, details = 0, []
    for pid in pids:
        r = await scan_property(db, pid)
        if r.get("recommendations"):
            total += r["recommendations"]
            details.append(r)
    for d in details:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": d["property_id"],
            "category": "restriction_advisor", "priority": "normal",
            "target_user": "", "target_role": "manager",
            "title": f"🔒 {d['recommendations']} yeni kısıtlama önerisi (MLOS/CTA)",
            "message": "AI yüksek talepli geceler için minimum konaklama / varışa kapama önerileri hazırladı.",
            "read": False, "created_at": _iso()})
    return {"properties_scanned": len(pids), "recommendations": total, "details": details}


def create_restriction_advisor_router(db, require_roles):
    router = APIRouter(prefix="/restriction-advisor")
    router.run_internal = lambda pid="": run_restriction_advisor(db, pid)

    @router.get("/{property_id}")
    async def list_recs(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        rows = await db.restriction_recommendations.find(q, {"_id": 0}).sort([("status", 1), ("date", 1)]).to_list(300)
        s = {"pending": 0, "accepted": 0, "rejected": 0}
        for r in rows:
            s[r["status"]] = s.get(r["status"], 0) + 1
        return {"recommendations": rows, "summary": s}

    @router.post("/{property_id}/scan")
    async def manual_scan(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_restriction_advisor(db, property_id)

    @router.post("/recs/{rec_id}/accept")
    async def accept(rec_id: str,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        rec = await db.restriction_recommendations.find_one({"id": rec_id}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Öneri bulunamadı")
        if rec["status"] != "pending":
            return {"ok": True, "already": rec["status"]}
        from routes.distribution.two_way_sync import _connected_channels
        channels = await _connected_channels(db) or ["direct"]
        now = _iso()
        updates = {"updated_at": now, "updated_by": f"AI Advisor ({current_user.get('name','')})"}
        if rec["rec_type"] == "mlos":
            updates["min_los"] = int(rec["min_los"])
        else:
            updates["closed_to_arrival"] = True
        for ch in channels:
            await db.channel_restrictions.update_one(
                {"property_id": rec["property_id"], "channel_id": ch,
                 "date": rec["date"], "room_type_id": "all"},
                {"$set": updates, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
            await db.sync_queue.insert_one({
                "id": str(uuid.uuid4()), "property_id": rec["property_id"],
                "channel_id": ch, "kind": "restriction",
                "payload": {"date": rec["date"],
                            "min_los": updates.get("min_los"),
                            "closed_to_arrival": updates.get("closed_to_arrival"),
                            "source": "restriction_advisor"},
                "status": "pending", "attempts": 0, "max_attempts": 6,
                "next_retry_at": now, "error": None, "result": None,
                "created_at": now, "created_by": "restriction_advisor"})
        try:
            from routes.integrations_pkg.sync_queue import process_due_tasks
            await process_due_tasks(db, max_tasks=len(channels) + 3)
        except Exception as ex:
            logger.warning("Restriction sync processing failed: %s", ex)
        await db.restriction_recommendations.update_one({"id": rec_id}, {"$set": {
            "status": "accepted", "accepted_at": now,
            "accepted_by": current_user.get("name", ""), "channels": channels}})
        return {"ok": True, "applied_channels": channels}

    @router.post("/recs/{rec_id}/reject")
    async def reject(rec_id: str,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.restriction_recommendations.update_one(
            {"id": rec_id, "status": "pending"},
            {"$set": {"status": "rejected", "rejected_at": _iso(),
                      "rejected_by": current_user.get("name", "")}})
        if not r.matched_count:
            raise HTTPException(404, "Bekleyen öneri bulunamadı")
        return {"ok": True}

    return router
