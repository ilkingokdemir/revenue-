"""
HK Auto-Dispatch — check-out sonrası odaları otomatik kat görevlilerine atar.
- İş yükü dengeleme: en az açık görevi olan görevliye atama
- Öncelik: aynı odaya/oda tipine BUGÜN varış varsa priority=urgent, öne alınır
- Canlı pano: görevli kolonları + görev durumları
Motor: hk_dispatch (JOB_REGISTRY). Dedupe: auto_dispatch + property + room + date.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def run_dispatch_internal(db, property_id: str = "") -> Dict:
    today = _today()
    pq = {} if not property_id or property_id == "all" else {"property_id": property_id}

    departures = await db.bookings.find({
        **pq, "check_out": today, "status": {"$in": ["checked_out", "checked_in"]},
    }, {"_id": 0, "id": 1, "property_id": 1, "room_number": 1, "room_type": 1, "guest_name": 1}).to_list(500)
    departures = [d for d in departures if d.get("room_number")]

    arrivals = await db.bookings.find({
        **pq, "check_in": today, "status": {"$in": ["confirmed", "pending", "pending_payment"]},
    }, {"_id": 0, "room_number": 1, "room_type": 1, "guest_name": 1, "property_id": 1}).to_list(500)
    arriving_rooms = {(a.get("property_id"), str(a.get("room_number"))) for a in arrivals if a.get("room_number")}
    arriving_types = {(a.get("property_id"), a.get("room_type"))
                      for a in arrivals if a.get("room_type") and not a.get("room_number")}

    housekeepers = await db.users.find(
        {"role": {"$in": ["housekeeper", "housekeeping"]}},
        {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(50)
    for h in housekeepers:
        h["id"] = h.get("id") or h.get("email") or h.get("name", "")
    housekeepers = [h for h in housekeepers if h["id"]]

    # Current open workload per housekeeper (today)
    load: Dict[str, int] = {h["id"]: 0 for h in housekeepers}
    open_tasks = await db.housekeeping_tasks.find(
        {"due_date": today, "status": {"$in": ["pending", "in_progress"]}},
        {"_id": 0, "assigned_to": 1}).to_list(2000)
    for t in open_tasks:
        if t.get("assigned_to") in load:
            load[t["assigned_to"]] += 1

    # Priority first: rooms with a same-day arrival get dispatched before others
    def _prio(d):
        key_room = (d.get("property_id"), str(d.get("room_number")))
        key_type = (d.get("property_id"), d.get("room_type"))
        return key_room in arriving_rooms or key_type in arriving_types

    departures.sort(key=lambda d: (not _prio(d)))
    now = datetime.now(timezone.utc).isoformat()
    created, skipped, urgent = [], 0, 0
    for d in departures:
        dup = await db.housekeeping_tasks.find_one({
            "property_id": d["property_id"], "due_date": today,
            "room_number": str(d["room_number"]), "auto_dispatch": True}, {"_id": 0, "id": 1})
        if dup:
            skipped += 1
            continue
        is_urgent = _prio(d)
        assignee = None
        if housekeepers:
            assignee = min(housekeepers, key=lambda h: load[h["id"]])
            load[assignee["id"]] += 1
        task = {
            "id": str(uuid.uuid4()), "property_id": d["property_id"],
            "room_number": str(d["room_number"]), "room_type_id": "",
            "task_type": "cleaning", "task_subtype": "checkout_clean",
            "priority": "urgent" if is_urgent else "high", "status": "pending",
            "assigned_to": (assignee or {}).get("id", ""),
            "assigned_name": (assignee or {}).get("name", ""),
            "notes": (f"⚡ ÖNCELİKLİ: bu odaya bugün varış var — {d.get('guest_name','')} check-out"
                      if is_urgent else f"Check-out temizliği — {d.get('guest_name','')}"),
            "estimated_minutes": 45, "checklist": [], "due_date": today,
            "completed_at": "", "auto_generated": True, "auto_dispatch": True,
            "booking_id": d.get("id", ""), "created_at": now,
        }
        await db.housekeeping_tasks.insert_one(dict(task))
        task.pop("_id", None)
        created.append(task)
        if is_urgent:
            urgent += 1
            if assignee and assignee.get("email"):
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "property_id": d["property_id"],
                    "category": "hk_dispatch", "priority": "high",
                    "target_user": assignee["email"], "target_role": "",
                    "title": f"⚡ Öncelikli temizlik — Oda {d['room_number']}",
                    "message": f"Bu odaya bugün varış var; öncelikli temizlenmeli. ({d.get('guest_name','')} check-out)",
                    "read": False, "created_at": now,
                })
    return {"date": today, "departures_scanned": len(departures), "tasks_created": len(created),
            "urgent": urgent, "skipped_duplicates": skipped,
            "housekeepers": len(housekeepers)}


def create_hk_dispatch_router(db, require_roles):
    router = APIRouter(prefix="/hk-dispatch")
    router.run_dispatch_internal = lambda pid="": run_dispatch_internal(db, pid)

    @router.post("/{property_id}/run")
    async def run_now(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await run_dispatch_internal(db, property_id)

    @router.get("/{property_id}/board")
    async def board(property_id: str,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        today = _today()
        pq = {} if property_id == "all" else {"property_id": property_id}
        tasks = await db.housekeeping_tasks.find(
            {**pq, "due_date": today}, {"_id": 0}).sort("created_at", 1).to_list(1000)
        housekeepers = await db.users.find(
            {"role": {"$in": ["housekeeper", "housekeeping"]}},
            {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(50)
        for h in housekeepers:
            h["id"] = h.get("id") or h.get("email") or h.get("name", "")
        housekeepers = [h for h in housekeepers if h["id"]]
        cols = []
        for h in housekeepers:
            mine = [t for t in tasks if t.get("assigned_to") == h["id"]]
            done = [t for t in mine if t.get("status") in ("clean", "done", "completed", "inspected")]
            cols.append({"id": h["id"], "name": h["name"], "tasks": mine,
                         "open": len(mine) - len(done), "done": len(done),
                         "minutes": sum(int(t.get("estimated_minutes", 30)) for t in mine if t not in done)})
        unassigned = [t for t in tasks if not t.get("assigned_to")]
        counts = {}
        for t in tasks:
            counts[t.get("status", "pending")] = counts.get(t.get("status", "pending"), 0) + 1
        return {"date": today, "columns": cols, "unassigned": unassigned, "counts": counts,
                "total": len(tasks),
                "urgent_rooms": [t["room_number"] for t in tasks if t.get("priority") == "urgent" and t.get("status") == "pending"]}

    return router
