"""
Tur Operatörü Kontenjan (Allotment) Yönetimi — operatör kontratları, günlük
kontenjan takibi, pickup kaydı, stop-sale ve otomatik release (serbest bırakma).
Collections:
  allotment_contracts {id, property_id, operator_name, room_type, start_date,
    end_date, daily_allotment, release_days, rate, currency, status, stop_sale_dates[]}
  allotment_pickups  {id, contract_id, property_id, date, rooms, booking_ref, guest_name}
  allotment_releases {id, contract_id, property_id, date, rooms_released, run_at}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

STAFF = ("admin", "manager", "receptionist")


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse(d: str) -> ddate:
    return datetime.strptime(d, "%Y-%m-%d").date()


async def _contract_stats(db, c: Dict) -> Dict:
    """Computes pickup/release totals for a contract."""
    pipeline = [{"$match": {"contract_id": c["id"]}},
                {"$group": {"_id": None, "rooms": {"$sum": "$rooms"}}}]
    picked = 0
    async for r in db.allotment_pickups.aggregate(pipeline):
        picked = int(r.get("rooms", 0))
    released = 0
    async for r in db.allotment_releases.aggregate([
            {"$match": {"contract_id": c["id"]}},
            {"$group": {"_id": None, "rooms": {"$sum": "$rooms_released"}}}]):
        released = int(r.get("rooms", 0))
    try:
        days = (_parse(c["end_date"]) - _parse(c["start_date"])).days + 1
    except Exception:
        days = 0
    stop_days = len(c.get("stop_sale_dates") or [])
    total = max((days - stop_days) * int(c.get("daily_allotment", 0)), 0)
    pct = round(picked / total * 100, 1) if total else 0.0
    return {"total_room_nights": total, "picked": picked, "released": released,
            "remaining": max(total - picked - released, 0), "pickup_pct": pct}


async def _push_releases_to_ota(db, released_entries) -> int:
    """Release edilen odaları bağlı OTA kanallarına müsaitlik push'u olarak kuyruklar."""
    from routes.distribution.two_way_sync import _connected_channels
    from routes.integrations_pkg.sync_queue import process_due_tasks
    channels = await _connected_channels(db)
    if not channels or not released_entries:
        return 0
    now = _iso()
    task_ids = []
    for e in released_entries:
        for ch in channels:
            task = {"id": str(uuid.uuid4()), "property_id": e["property_id"],
                    "channel_id": ch, "kind": "avail",
                    "payload": {"date": e["date"], "delta": e["rooms"],
                                "source": "allotment_release",
                                "contract_id": e["contract_id"],
                                "operator": e["operator_name"]},
                    "status": "pending", "attempts": 0, "max_attempts": 6,
                    "next_retry_at": now, "error": None, "result": None,
                    "created_at": now, "created_by": "allotment_release"}
            await db.sync_queue.insert_one(task)
            task_ids.append(task["id"])
    try:
        await process_due_tasks(db, max_tasks=len(task_ids) + 5)
    except Exception as ex:
        logger.warning("Allotment OTA push processing failed: %s", ex)
    return len(task_ids)


async def run_allotment_release_internal(db, property_id: str = "") -> Dict:
    """Release penceresine giren satılmamış kontenjanları serbest bırakır."""
    today = _parse(_today())
    q = {"status": "active"}
    if property_id and property_id != "all":
        q["property_id"] = property_id
    contracts = await db.allotment_contracts.find(q, {"_id": 0}).to_list(200)
    total_released, touched = 0, 0
    by_prop: Dict[str, int] = {}
    released_entries = []
    for c in contracts:
        try:
            start, end = _parse(c["start_date"]), _parse(c["end_date"])
        except Exception:
            continue
        rel_days = int(c.get("release_days", 7))
        win_end = today + timedelta(days=rel_days - 1)
        d = max(start, today)
        contract_released = 0
        while d <= min(end, win_end):
            ds = d.strftime("%Y-%m-%d")
            d += timedelta(days=1)
            if ds in (c.get("stop_sale_dates") or []):
                continue
            already = await db.allotment_releases.find_one(
                {"contract_id": c["id"], "date": ds}, {"_id": 0})
            if already:
                continue
            picked = 0
            async for r in db.allotment_pickups.aggregate([
                    {"$match": {"contract_id": c["id"], "date": ds}},
                    {"$group": {"_id": None, "rooms": {"$sum": "$rooms"}}}]):
                picked = int(r.get("rooms", 0))
            free = max(int(c.get("daily_allotment", 0)) - picked, 0)
            if free <= 0:
                continue
            await db.allotment_releases.insert_one({
                "id": str(uuid.uuid4()), "contract_id": c["id"],
                "property_id": c["property_id"], "operator_name": c["operator_name"],
                "date": ds, "rooms_released": free, "run_at": _iso()})
            released_entries.append({"property_id": c["property_id"], "date": ds,
                                     "rooms": free, "contract_id": c["id"],
                                     "operator_name": c["operator_name"]})
            contract_released += free
        if contract_released:
            touched += 1
            total_released += contract_released
            by_prop[c["property_id"]] = by_prop.get(c["property_id"], 0) + contract_released
    ota_tasks = await _push_releases_to_ota(db, released_entries)
    for pid, rooms in by_prop.items():
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid,
            "category": "allotment_release", "priority": "normal",
            "target_user": "", "target_role": "manager",
            "title": f"🏷️ Kontenjan release: {rooms} oda serbest bırakıldı",
            "message": "Release penceresine giren satılmamış operatör kontenjanları genel satışa açıldı."
                       + (f" {ota_tasks} OTA müsaitlik push'u kuyruğa alındı." if ota_tasks else ""),
            "read": False, "created_at": _iso()})
    return {"contracts_scanned": len(contracts), "contracts_released": touched,
            "rooms_released": total_released, "ota_push_tasks": ota_tasks}


def create_allotments_router(db, require_roles):
    router = APIRouter(prefix="/allotments")
    router.run_release_internal = lambda pid="": run_allotment_release_internal(db, pid)

    @router.get("/{property_id}")
    async def list_contracts(property_id: str, status: Optional[str] = None,
                             current_user: dict = Depends(require_roles(*STAFF))):
        q = {} if property_id == "all" else {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.allotment_contracts.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
        today = _today()
        out = []
        agg = {"active": 0, "picked": 0, "total": 0, "released": 0}
        for c in rows:
            st = await _contract_stats(db, c)
            if c.get("status") == "active" and c.get("end_date", "") >= today:
                agg["active"] += 1
                agg["picked"] += st["picked"]
                agg["total"] += st["total_room_nights"]
                agg["released"] += st["released"]
            out.append({**c, **st})
        overall_pct = round(agg["picked"] / agg["total"] * 100, 1) if agg["total"] else 0.0
        return {"contracts": out, "summary": {
            "active_contracts": agg["active"], "overall_pickup_pct": overall_pct,
            "rooms_released": agg["released"],
            "operators": len({c["operator_name"] for c in rows})}}

    @router.post("/{property_id}")
    async def create_contract(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        op = (data.get("operator_name") or "").strip()
        rt = (data.get("room_type") or "").strip()
        start, end = data.get("start_date", ""), data.get("end_date", "")
        if not op or not rt:
            raise HTTPException(400, "operator_name ve room_type gerekli")
        try:
            if _parse(start) > _parse(end):
                raise ValueError()
        except Exception:
            raise HTTPException(400, "Geçerli start_date/end_date gerekli (YYYY-MM-DD)")
        daily = int(data.get("daily_allotment", 0) or 0)
        if daily < 1 or daily > 500:
            raise HTTPException(400, "daily_allotment 1-500 arasında olmalı")
        doc = {
            "id": str(uuid.uuid4()), "property_id": property_id,
            "operator_name": op, "room_type": rt,
            "start_date": start, "end_date": end,
            "daily_allotment": daily,
            "release_days": max(int(data.get("release_days", 7) or 7), 0),
            "rate": float(data.get("rate", 0) or 0),
            "currency": (data.get("currency") or "EUR").upper()[:3],
            "status": "active", "stop_sale_dates": [],
            "note": (data.get("note") or "")[:300], "created_at": _iso(),
        }
        await db.allotment_contracts.insert_one(dict(doc))
        return {"ok": True, "contract": doc}

    @router.put("/{property_id}/{contract_id}")
    async def update_contract(property_id: str, contract_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {k: data[k] for k in
                   ("operator_name", "room_type", "start_date", "end_date", "daily_allotment",
                    "release_days", "rate", "currency", "status", "note") if k in data}
        if not allowed:
            raise HTTPException(400, "Güncellenecek alan yok")
        r = await db.allotment_contracts.update_one(
            {"id": contract_id, "property_id": property_id}, {"$set": allowed})
        if not r.matched_count:
            raise HTTPException(404, "Kontrat bulunamadı")
        return {"ok": True}

    @router.delete("/{property_id}/{contract_id}")
    async def delete_contract(property_id: str, contract_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.allotment_contracts.delete_one({"id": contract_id, "property_id": property_id})
        if not r.deleted_count:
            raise HTTPException(404, "Kontrat bulunamadı")
        await db.allotment_pickups.delete_many({"contract_id": contract_id})
        await db.allotment_releases.delete_many({"contract_id": contract_id})
        return {"ok": True}

    @router.post("/{property_id}/{contract_id}/stop-sale")
    async def toggle_stop_sale(property_id: str, contract_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        ds = data.get("date", "")
        try:
            _parse(ds)
        except Exception:
            raise HTTPException(400, "Geçerli date gerekli (YYYY-MM-DD)")
        c = await db.allotment_contracts.find_one({"id": contract_id, "property_id": property_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Kontrat bulunamadı")
        stops = set(c.get("stop_sale_dates") or [])
        on = ds not in stops
        (stops.add if on else stops.discard)(ds)
        await db.allotment_contracts.update_one({"id": contract_id},
                                                {"$set": {"stop_sale_dates": sorted(stops)}})
        return {"ok": True, "stop_sale": on, "date": ds}

    @router.post("/{property_id}/{contract_id}/pickup")
    async def record_pickup(property_id: str, contract_id: str, data: Dict,
                            current_user: dict = Depends(require_roles(*STAFF))):
        c = await db.allotment_contracts.find_one({"id": contract_id, "property_id": property_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Kontrat bulunamadı")
        ds = data.get("date", "")
        try:
            d = _parse(ds)
        except Exception:
            raise HTTPException(400, "Geçerli date gerekli (YYYY-MM-DD)")
        if not (_parse(c["start_date"]) <= d <= _parse(c["end_date"])):
            raise HTTPException(400, "Tarih kontrat aralığı dışında")
        if ds in (c.get("stop_sale_dates") or []):
            raise HTTPException(400, "Bu tarih stop-sale — pickup kaydedilemez")
        rooms = int(data.get("rooms", 1) or 1)
        if rooms < 1:
            raise HTTPException(400, "rooms >= 1 olmalı")
        picked = 0
        async for r in db.allotment_pickups.aggregate([
                {"$match": {"contract_id": contract_id, "date": ds}},
                {"$group": {"_id": None, "rooms": {"$sum": "$rooms"}}}]):
            picked = int(r.get("rooms", 0))
        released = await db.allotment_releases.find_one({"contract_id": contract_id, "date": ds}, {"_id": 0})
        avail = int(c.get("daily_allotment", 0)) - picked - (int(released["rooms_released"]) if released else 0)
        if rooms > avail:
            raise HTTPException(400, f"Yetersiz kontenjan: bu tarihte kalan {max(avail,0)} oda")
        doc = {"id": str(uuid.uuid4()), "contract_id": contract_id,
               "property_id": property_id, "date": ds, "rooms": rooms,
               "booking_ref": (data.get("booking_ref") or "")[:60],
               "guest_name": (data.get("guest_name") or "")[:100],
               "created_at": _iso()}
        await db.allotment_pickups.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "pickup": doc, "remaining_on_date": avail - rooms}

    @router.get("/{property_id}/{contract_id}/calendar")
    async def contract_calendar(property_id: str, contract_id: str, days: int = 21,
                                current_user: dict = Depends(require_roles(*STAFF))):
        c = await db.allotment_contracts.find_one({"id": contract_id, "property_id": property_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Kontrat bulunamadı")
        start = max(_parse(c["start_date"]), _parse(_today()))
        end = min(_parse(c["end_date"]), start + timedelta(days=min(days, 60) - 1))
        pickups: Dict[str, int] = {}
        async for r in db.allotment_pickups.aggregate([
                {"$match": {"contract_id": contract_id}},
                {"$group": {"_id": "$date", "rooms": {"$sum": "$rooms"}}}]):
            pickups[r["_id"]] = int(r["rooms"])
        releases: Dict[str, int] = {}
        async for r in db.allotment_releases.find({"contract_id": contract_id}, {"_id": 0}):
            releases[r["date"]] = int(r["rooms_released"])
        rel_win_end = _parse(_today()) + timedelta(days=int(c.get("release_days", 7)) - 1)
        rows, d = [], start
        stops = set(c.get("stop_sale_dates") or [])
        while d <= end:
            ds = d.strftime("%Y-%m-%d")
            stop = ds in stops
            allot = 0 if stop else int(c.get("daily_allotment", 0))
            picked = pickups.get(ds, 0)
            rel = releases.get(ds, 0)
            rows.append({"date": ds, "allotment": allot, "picked": picked,
                         "released": rel, "remaining": max(allot - picked - rel, 0),
                         "stop_sale": stop, "in_release_window": d <= rel_win_end})
            d += timedelta(days=1)
        return {"contract": c, "days": rows}

    @router.get("/{property_id}/report/operators")
    async def operator_report(property_id: str,
                              current_user: dict = Depends(require_roles(*STAFF))):
        q = {} if property_id == "all" else {"property_id": property_id}
        contracts = await db.allotment_contracts.find(q, {"_id": 0}).to_list(200)
        ops: Dict[str, Dict] = {}
        months = set()
        for c in contracts:
            st = await _contract_stats(db, c)
            o = ops.setdefault(c["operator_name"], {
                "operator_name": c["operator_name"], "contracts": 0,
                "total_room_nights": 0, "picked": 0, "released": 0,
                "revenue": 0.0, "lost_revenue": 0.0,
                "currency": c.get("currency", "EUR"), "monthly": {}})
            o["contracts"] += 1
            o["total_room_nights"] += st["total_room_nights"]
            o["picked"] += st["picked"]
            o["released"] += st["released"]
            rate = float(c.get("rate", 0) or 0)
            o["revenue"] += st["picked"] * rate
            o["lost_revenue"] += st["released"] * rate
            async for r in db.allotment_pickups.aggregate([
                    {"$match": {"contract_id": c["id"]}},
                    {"$group": {"_id": {"$substr": ["$date", 0, 7]}, "rooms": {"$sum": "$rooms"}}}]):
                m = r["_id"]
                months.add(m)
                o["monthly"][m] = o["monthly"].get(m, 0) + int(r["rooms"])
        out = []
        for o in ops.values():
            o["pickup_pct"] = round(o["picked"] / o["total_room_nights"] * 100, 1) if o["total_room_nights"] else 0.0
            o["revenue"] = round(o["revenue"], 2)
            o["lost_revenue"] = round(o["lost_revenue"], 2)
            out.append(o)
        out.sort(key=lambda x: -x["revenue"])
        return {"operators": out, "months": sorted(months)}

    @router.post("/{property_id}/release-run")
    async def release_run(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_allotment_release_internal(db, property_id)

    return router
