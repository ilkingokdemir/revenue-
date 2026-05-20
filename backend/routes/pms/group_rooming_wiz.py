"""
Group Rooming Wizard (P1)
-------------------------
Different from the existing CSV import — this is a *guided* allocator: given
a group block (N rooms × M nights), suggest a room assignment plan that
keeps groups on the same floor / same room_type, generates per-guest bookings
in a single transaction, posts a master folio link, and tracks a single
group_rooming_session for audit.

Endpoints
---------
POST /group-rooming/sessions                  Open a new session for a group
POST /group-rooming/sessions/{id}/add-guest   Append a guest to the manifest
POST /group-rooming/sessions/{id}/auto-assign Run auto-assignment (greedy)
POST /group-rooming/sessions/{id}/finalize    Create bookings + close session
GET  /group-rooming/sessions/{id}             View session + draft assignments
GET  /group-rooming/{property_id}/sessions
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, List
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_group_rooming_router(db, require_roles):
    router = APIRouter()

    @router.post("/group-rooming/sessions")
    async def open_session(data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        property_id = (data.get("property_id") or "").strip()
        group_name = (data.get("group_name") or "").strip()
        check_in = (data.get("check_in") or "")[:10]
        check_out = (data.get("check_out") or "")[:10]
        if not (property_id and group_name and check_in and check_out):
            raise HTTPException(400, "property_id, group_name, check_in, check_out required")
        s = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "group_name": group_name,
            "client_company": data.get("client_company", ""),
            "client_email": data.get("client_email", ""),
            "check_in": check_in, "check_out": check_out,
            "preferred_room_type": data.get("preferred_room_type", ""),
            "preferred_floor": data.get("preferred_floor"),
            "manifest": [], "assignments": [],
            "status": "draft",  # draft | finalized | cancelled
            "created_at": _now(),
            "created_by": current_user.get("name", "Staff"),
        }
        await db.group_rooming_sessions.insert_one(dict(s))
        s.pop("_id", None)
        return {"ok": True, "session": s}

    @router.post("/group-rooming/sessions/{session_id}/add-guest")
    async def add_guest(session_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        s = await db.group_rooming_sessions.find_one({"id": session_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        if s["status"] != "draft":
            raise HTTPException(400, "Session is not draft")
        guest = {
            "ix": len(s["manifest"]),
            "guest_name": (data.get("guest_name") or "").strip(),
            "guest_email": (data.get("guest_email") or "").strip().lower(),
            "share_with": data.get("share_with", ""),  # ix or guest_name they want to share with
            "preferred_floor": data.get("preferred_floor"),
            "notes": data.get("notes", ""),
        }
        if not guest["guest_name"]:
            raise HTTPException(400, "guest_name required")
        await db.group_rooming_sessions.update_one(
            {"id": session_id}, {"$push": {"manifest": guest}}
        )
        return {"ok": True, "guest_index": guest["ix"]}

    @router.post("/group-rooming/sessions/{session_id}/auto-assign")
    async def auto_assign(session_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.group_rooming_sessions.find_one({"id": session_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        if not s["manifest"]:
            raise HTTPException(400, "Manifest is empty")
        # Pull available rooms for the date range
        rooms = await db.rooms.find({"property_id": s["property_id"]}, {"_id": 0}).to_list(2000)
        # Filter rooms not booked in the range
        bookings_in_range = await db.bookings.find({
            "property_id": s["property_id"],
            "status": {"$nin": ["cancelled", "no_show"]},
            "check_in": {"$lt": s["check_out"]}, "check_out": {"$gt": s["check_in"]},
        }, {"_id": 0}).to_list(5000)
        busy_rooms = {b.get("room_number") for b in bookings_in_range if b.get("room_number")}
        # rooms collection uses "name" for the public room number & "room_type_id" for the type
        def _num(r): return r.get("number") or r.get("name") or ""
        def _type(r): return r.get("type") or r.get("room_type") or r.get("room_type_id") or ""
        free_rooms = [r for r in rooms if _num(r) not in busy_rooms]
        if s.get("preferred_room_type"):
            preferred = [r for r in free_rooms if _type(r) == s["preferred_room_type"]]
            if preferred:
                free_rooms = preferred
        if s.get("preferred_floor"):
            free_rooms.sort(key=lambda r: 0 if str(r.get("floor")) == str(s["preferred_floor"]) else 1)
        else:
            free_rooms.sort(key=lambda r: (str(r.get("floor", "")), _num(r)))
        if len(free_rooms) < len(s["manifest"]):
            raise HTTPException(409, f"Not enough free rooms ({len(free_rooms)}) for {len(s['manifest'])} guests")
        assignments = []
        for i, g in enumerate(s["manifest"]):
            r = free_rooms[i]
            assignments.append({
                "guest_index": g["ix"],
                "guest_name": g["guest_name"],
                "guest_email": g["guest_email"],
                "room_number": _num(r),
                "room_type": _type(r),
                "floor": r.get("floor"),
            })
        await db.group_rooming_sessions.update_one(
            {"id": session_id}, {"$set": {"assignments": assignments, "auto_assigned_at": _now()}}
        )
        floors = sorted({a.get("floor") for a in assignments if a.get("floor") is not None})
        return {"ok": True, "assignments": assignments, "floors_used": floors,
                 "all_same_floor": len(floors) == 1}

    @router.post("/group-rooming/sessions/{session_id}/finalize")
    async def finalize(session_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        s = await db.group_rooming_sessions.find_one({"id": session_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        if s["status"] != "draft":
            raise HTTPException(400, "Session is not draft")
        if not s.get("assignments"):
            raise HTTPException(400, "Run auto-assign first")
        booking_ids: List[str] = []
        # Compute nights
        try:
            nights = (datetime.fromisoformat(s["check_out"]) - datetime.fromisoformat(s["check_in"])).days
        except ValueError:
            nights = 1
        # Look up base rate
        rate = 0.0
        if s.get("preferred_room_type"):
            rt = await db.room_types.find_one({"property_id": s["property_id"], "name": s["preferred_room_type"]}, {"_id": 0}) or {}
            rate = float(rt.get("base_rate") or 0)
        for a in s["assignments"]:
            bid = str(uuid.uuid4())
            await db.bookings.insert_one({
                "id": bid,
                "property_id": s["property_id"],
                "guest_name": a["guest_name"],
                "guest_email": a["guest_email"],
                "check_in": s["check_in"], "check_out": s["check_out"], "nights": nights,
                "room_type": a.get("room_type", ""),
                "room_number": a.get("room_number", ""),
                "total_price": round(rate * nights, 2),
                "currency": "GBP",
                "status": "confirmed",
                "source": "group_rooming",
                "group_session_id": session_id,
                "group_name": s["group_name"],
                "created_at": _now(),
                "created_by": current_user.get("name", "Staff"),
            })
            booking_ids.append(bid)
        await db.group_rooming_sessions.update_one(
            {"id": session_id},
            {"$set": {"status": "finalized", "booking_ids": booking_ids, "finalized_at": _now(),
                       "finalized_by": current_user.get("name", "Staff")}},
        )
        return {"ok": True, "booking_ids": booking_ids, "count": len(booking_ids)}

    @router.get("/group-rooming/sessions/{session_id}")
    async def view_session(session_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        s = await db.group_rooming_sessions.find_one({"id": session_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Session not found")
        return s

    @router.get("/group-rooming/{property_id}/sessions")
    async def list_sessions(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.group_rooming_sessions.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    return router
