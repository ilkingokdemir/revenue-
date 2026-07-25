"""
Two-Way OTA Sync (iter 431) — closes the loop on inbound reservations:
  1. Ripple Availability: when a reservation arrives from one OTA, the
     availability change is instantly pushed to ALL other connected channels
     via the sync queue (prevents double-selling).
  2. Overbooking Guard: detects overlapping active bookings on the same room
     and raises a conflict record + in-app alert for staff resolution.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

MAX_RIPPLE_NIGHTS = 30


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nights(check_in: str, check_out: str):
    try:
        ci = date.fromisoformat(check_in[:10])
        co = date.fromisoformat(check_out[:10])
    except (ValueError, TypeError):
        return []
    n = min((co - ci).days, MAX_RIPPLE_NIGHTS)
    return [(ci + timedelta(days=i)).isoformat() for i in range(max(n, 0))]


async def _connected_channels(db, exclude: str = ""):
    conns = await db.channel_connections.find(
        {"channel_id": {"$ne": "direct"}, "connected": True},
        {"_id": 0, "channel_id": 1}).to_list(50)
    seen = {c["channel_id"] for c in conns}
    seen.discard(exclude)
    return sorted(seen)


async def ripple_availability(db, booking: Dict, source_channel: str, event_type: str) -> Dict:
    """Push availability delta to every connected channel except the source."""
    from routes.integrations_pkg.sync_queue import process_due_tasks
    nights = _nights(booking.get("check_in", ""), booking.get("check_out", ""))
    channels = await _connected_channels(db, exclude=source_channel)
    delta = 1 if event_type == "cancellation" else -1
    now = _now()
    task_ids = []
    for ch in channels:
        for d in nights:
            task = {"id": str(uuid.uuid4()), "property_id": booking.get("property_id"),
                    "channel_id": ch, "kind": "avail",
                    "payload": {"date": d, "delta": delta,
                                "source": "two_way_ripple",
                                "booking_id": booking.get("id"),
                                "trigger_channel": source_channel},
                    "status": "pending", "attempts": 0, "max_attempts": 6,
                    "next_retry_at": now, "error": None, "result": None,
                    "created_at": now, "created_by": f"ripple:{source_channel}"}
            await db.sync_queue.insert_one(task)
            task_ids.append(task["id"])

    await process_due_tasks(db, max_tasks=len(task_ids) + 5)
    succeeded = await db.sync_queue.count_documents(
        {"id": {"$in": task_ids}, "status": "succeeded"}) if task_ids else 0

    event = {"id": str(uuid.uuid4()), "property_id": booking.get("property_id"),
             "booking_id": booking.get("id"), "guest_name": booking.get("guest_name"),
             "source_channel": source_channel, "event_type": event_type,
             "check_in": booking.get("check_in"), "check_out": booking.get("check_out"),
             "nights": len(nights), "channels": channels,
             "tasks_total": len(task_ids), "tasks_succeeded": succeeded,
             "created_at": now}
    await db.ripple_events.insert_one(event)
    event.pop("_id", None)
    return event


async def detect_overbooking(db, booking: Dict) -> Optional[Dict]:
    """Overlapping active booking on same property + room → conflict record."""
    room = booking.get("room_number")
    ci, co = booking.get("check_in"), booking.get("check_out")
    if not room or not ci or not co:
        return None
    other = await db.bookings.find_one({
        "property_id": booking.get("property_id"),
        "room_number": room,
        "id": {"$ne": booking.get("id")},
        "status": {"$nin": ["cancelled", "no_show"]},
        "check_in": {"$lt": co}, "check_out": {"$gt": ci},
    }, {"_id": 0, "id": 1, "channel": 1, "source": 1, "guest_name": 1,
        "check_in": 1, "check_out": 1})
    if not other:
        return None
    pair = sorted([booking.get("id", ""), other["id"]])
    existing = await db.sync_conflicts.find_one(
        {"pair_key": ":".join(pair), "status": "open"}, {"_id": 0, "id": 1})
    if existing:
        return None
    conflict = {"id": str(uuid.uuid4()), "pair_key": ":".join(pair),
                "property_id": booking.get("property_id"), "room_number": room,
                "booking_a": {"id": booking.get("id"),
                              "channel": booking.get("channel") or booking.get("source"),
                              "guest_name": booking.get("guest_name"),
                              "check_in": ci, "check_out": co},
                "booking_b": {"id": other["id"],
                              "channel": other.get("channel") or other.get("source"),
                              "guest_name": other.get("guest_name"),
                              "check_in": other.get("check_in"),
                              "check_out": other.get("check_out")},
                "status": "open", "created_at": _now()}
    await db.sync_conflicts.insert_one(conflict)
    conflict.pop("_id", None)
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()), "type": "error",
        "title": "Overbooking Riski!",
        "message": f"Oda {room}: {booking.get('guest_name')} ({ci}) ile {other.get('guest_name')} ({other.get('check_in')}) rezervasyonları çakışıyor.",
        "category": "ota_sync", "target_user": "", "target_role": "manager",
        "link_to": "channel-health", "priority": "high",
        "read": False, "created_by": "Two-Way Sync Guard", "created_at": _now()})
    return conflict


async def run_two_way_side_effects(db, booking: Dict, source_channel: str, event_type: str) -> Dict:
    """Called after every inbound OTA reservation/cancellation."""
    conflict = None
    if event_type == "reservation":
        try:
            conflict = await detect_overbooking(db, booking)
        except Exception as e:
            logger.warning(f"overbooking detect failed: {e}")
    try:
        ripple = await ripple_availability(db, booking, source_channel, event_type)
    except Exception as e:
        logger.warning(f"ripple failed: {e}")
        ripple = {"error": str(e)}
    return {"ripple": ripple, "conflict": conflict}


def create_two_way_sync_router(db, require_roles):
    router = APIRouter()

    @router.get("/two-way-sync/{property_id}")
    async def status(property_id: str, limit: int = 30,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}
        events = await db.ripple_events.find(pq, {"_id": 0}) \
            .sort("created_at", -1).to_list(int(limit))
        conflicts = await db.sync_conflicts.find(pq, {"_id": 0}) \
            .sort("created_at", -1).to_list(int(limit))
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        ripple_24h = await db.ripple_events.count_documents(
            {**pq, "created_at": {"$gte": cutoff}})
        return {"property_id": property_id,
                "summary": {
                    "ripple_24h": ripple_24h,
                    "ripple_total": await db.ripple_events.count_documents(pq),
                    "conflicts_open": await db.sync_conflicts.count_documents({**pq, "status": "open"}),
                    "conflicts_total": await db.sync_conflicts.count_documents(pq),
                    "channels": await _connected_channels(db),
                },
                "ripple_events": events, "conflicts": conflicts}

    @router.post("/two-way-sync/conflicts/{conflict_id}/resolve")
    async def resolve_conflict(conflict_id: str, data: Dict = None,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.sync_conflicts.update_one(
            {"id": conflict_id, "status": "open"},
            {"$set": {"status": "resolved", "resolved_at": _now(),
                      "resolved_by": current_user.get("name", ""),
                      "resolution_note": (data or {}).get("note", "")}})
        if r.modified_count == 0:
            raise HTTPException(404, "Açık çakışma bulunamadı")
        return {"ok": True}

    @router.post("/two-way-sync/simulate")
    async def simulate(data: Dict = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Demo: creates a mock inbound OTA reservation and runs the full
        two-way pipeline (conflict guard + ripple). force_conflict=true reuses
        an existing booked room+dates to trigger the overbooking guard."""
        body = data or {}
        channel = body.get("channel", "expedia")
        force_conflict = bool(body.get("force_conflict"))
        pid = body.get("property_id")
        if not pid or pid == "all":
            prop = await db.properties.find_one({}, {"_id": 0, "id": 1})
            pid = (prop or {}).get("id", "default")

        ci = (date.today() + timedelta(days=3)).isoformat()
        co = (date.today() + timedelta(days=5)).isoformat()
        room_number = None
        if force_conflict:
            existing = await db.bookings.find_one(
                {"property_id": pid, "room_number": {"$nin": [None, ""]},
                 "status": {"$nin": ["cancelled", "no_show"]},
                 "check_out": {"$gte": date.today().isoformat()}},
                {"_id": 0, "room_number": 1, "check_in": 1, "check_out": 1})
            if existing:
                room_number = existing["room_number"]
                ci, co = existing["check_in"], existing["check_out"]

        booking = {"id": str(uuid.uuid4()),
                   "channel_key": f"{channel}:SIM-{uuid.uuid4().hex[:6].upper()}",
                   "channel": channel, "property_id": pid,
                   "guest_name": f"Simülasyon Misafiri {uuid.uuid4().hex[:4].upper()}",
                   "check_in": ci, "check_out": co,
                   "room_number": room_number,
                   "status": "confirmed", "source": f"ota:{channel}",
                   "simulated": True,
                   "created_at": _now(), "updated_at": _now()}
        await db.bookings.insert_one(booking)
        booking.pop("_id", None)
        result = await run_two_way_side_effects(db, booking, channel, "reservation")
        return {"ok": True, "booking_id": booking["id"], "simulated": True,
                "room_number": room_number, "check_in": ci, "check_out": co, **result}

    return router
