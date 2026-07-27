"""
Smart Rooms — IoT Oda Kontrol Merkezi (simülasyon)

Oda başına cihaz durumu (ışık, termostat, klima modu, perde, DND, TV),
sahneler (welcome / eco / night / checkout) ve boş odalar için tek-tık
Eco Sweep enerji tasarrufu otomasyonu.

Collections:
  smart_room_states     {property_id, room_id, room_name, devices{}, scene, updated_at}
  smart_room_actions    {property_id, room_id, action, detail, at, by}
  smart_room_energy_log {property_id, rooms_affected, kwh_saved, at, triggered_by}
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import uuid

DEFAULT_DEVICES = {
    "lights": False,
    "thermostat": 21.0,
    "ac_mode": "auto",
    "curtains": "open",
    "dnd": False,
    "tv": False,
}

SCENES = {
    "welcome":  {"lights": True,  "thermostat": 22.0, "ac_mode": "cool", "curtains": "open",   "dnd": False, "tv": True},
    "eco":      {"lights": False, "thermostat": 18.0, "ac_mode": "off",  "curtains": "closed", "dnd": False, "tv": False},
    "night":    {"lights": False, "thermostat": 20.0, "ac_mode": "auto", "curtains": "closed", "dnd": True,  "tv": False},
    "checkout": {"lights": False, "thermostat": 19.0, "ac_mode": "off",  "curtains": "open",   "dnd": False, "tv": False},
}

AC_MODES = {"off", "cool", "heat", "auto"}
CURTAIN_STATES = {"open", "closed"}
BOOL_DEVICES = {"lights", "dnd", "tv"}
KWH_PER_ECO_ROOM = 1.5
GBP_PER_KWH = 0.28


class ControlReq(BaseModel):
    device: str
    value: Any


class SceneReq(BaseModel):
    scene: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_smart_rooms_router(db, require_roles):
    router = APIRouter(prefix="/smart-rooms", tags=["smart-rooms"])
    ROLES = ("admin", "manager", "receptionist", "housekeeping")

    async def _log(property_id: str, room_id: str, action: str, detail: str, by: str):
        await db.smart_room_actions.insert_one({
            "id": str(uuid.uuid4()), "property_id": property_id, "room_id": room_id,
            "action": action, "detail": detail, "at": _now(), "by": by,
        })

    @router.get("/{property_id}")
    async def list_rooms(property_id: str,
                         current_user: dict = Depends(require_roles(*ROLES))):
        rooms = await db.rooms.find(
            {"property_id": property_id},
            {"_id": 0, "id": 1, "name": 1, "floor": 1, "status": 1, "housekeeping": 1},
        ).sort("name", 1).to_list(300)
        states = await db.smart_room_states.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(300)
        state_map = {s["room_id"]: s for s in states}
        out = []
        for r in rooms:
            st = state_map.get(r["id"], {})
            out.append({
                "room_id": r["id"],
                "name": r.get("name"),
                "floor": r.get("floor"),
                "status": r.get("status", "available"),
                "housekeeping": r.get("housekeeping"),
                "devices": {**DEFAULT_DEVICES, **(st.get("devices") or {})},
                "scene": st.get("scene"),
                "updated_at": st.get("updated_at"),
            })
        return {"rooms": out, "count": len(out)}

    @router.post("/{property_id}/{room_id}/control")
    async def control_device(property_id: str, room_id: str, req: ControlReq,
                             current_user: dict = Depends(require_roles(*ROLES))):
        device, value = req.device, req.value
        if device in BOOL_DEVICES:
            value = bool(value)
        elif device == "thermostat":
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise HTTPException(400, "thermostat must be a number")
            if value < 16 or value > 30:
                raise HTTPException(400, "thermostat must be 16..30")
        elif device == "ac_mode":
            if value not in AC_MODES:
                raise HTTPException(400, f"ac_mode must be one of {sorted(AC_MODES)}")
        elif device == "curtains":
            if value not in CURTAIN_STATES:
                raise HTTPException(400, f"curtains must be one of {sorted(CURTAIN_STATES)}")
        else:
            raise HTTPException(400, f"Unknown device: {device}")

        room = await db.rooms.find_one({"id": room_id, "property_id": property_id}, {"_id": 0, "name": 1})
        if not room:
            raise HTTPException(404, "Room not found")

        st = await db.smart_room_states.find_one(
            {"property_id": property_id, "room_id": room_id}, {"_id": 0, "devices": 1})
        devices = {**DEFAULT_DEVICES, **((st or {}).get("devices") or {})}
        devices[device] = value
        await db.smart_room_states.update_one(
            {"property_id": property_id, "room_id": room_id},
            {"$set": {"property_id": property_id, "room_id": room_id,
                      "room_name": room.get("name"), "devices": devices,
                      "scene": None, "updated_at": _now()}},
            upsert=True,
        )
        await _log(property_id, room_id, "control",
                   f"{room.get('name')}: {device} → {value}", current_user.get("email", ""))
        return {"ok": True, "room_id": room_id, "devices": devices}

    @router.post("/{property_id}/{room_id}/scene")
    async def apply_scene(property_id: str, room_id: str, req: SceneReq,
                          current_user: dict = Depends(require_roles(*ROLES))):
        if req.scene not in SCENES:
            raise HTTPException(400, f"scene must be one of {sorted(SCENES)}")
        room = await db.rooms.find_one({"id": room_id, "property_id": property_id}, {"_id": 0, "name": 1})
        if not room:
            raise HTTPException(404, "Room not found")
        devices = {**DEFAULT_DEVICES, **SCENES[req.scene]}
        await db.smart_room_states.update_one(
            {"property_id": property_id, "room_id": room_id},
            {"$set": {"property_id": property_id, "room_id": room_id,
                      "room_name": room.get("name"), "devices": devices,
                      "scene": req.scene, "updated_at": _now()}},
            upsert=True,
        )
        await _log(property_id, room_id, "scene",
                   f"{room.get('name')}: sahne → {req.scene}", current_user.get("email", ""))
        return {"ok": True, "room_id": room_id, "scene": req.scene, "devices": devices}

    @router.post("/{property_id}/eco-sweep")
    async def eco_sweep(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rooms = await db.rooms.find(
            {"property_id": property_id, "status": {"$ne": "occupied"}},
            {"_id": 0, "id": 1, "name": 1},
        ).to_list(300)
        states = await db.smart_room_states.find(
            {"property_id": property_id, "scene": "eco"}, {"_id": 0, "room_id": 1}
        ).to_list(300)
        already_eco = {s["room_id"] for s in states}
        targets = [r for r in rooms if r["id"] not in already_eco]
        now = _now()
        devices = {**DEFAULT_DEVICES, **SCENES["eco"]}
        for r in targets:
            await db.smart_room_states.update_one(
                {"property_id": property_id, "room_id": r["id"]},
                {"$set": {"property_id": property_id, "room_id": r["id"],
                          "room_name": r.get("name"), "devices": dict(devices),
                          "scene": "eco", "updated_at": now}},
                upsert=True,
            )
        kwh = round(len(targets) * KWH_PER_ECO_ROOM, 2)
        if targets:
            await db.smart_room_energy_log.insert_one({
                "id": str(uuid.uuid4()), "property_id": property_id,
                "rooms_affected": len(targets), "kwh_saved": kwh,
                "at": now, "triggered_by": current_user.get("email", ""),
            })
            await _log(property_id, "*", "eco_sweep",
                       f"{len(targets)} boş oda eco moda alındı ({kwh} kWh)",
                       current_user.get("email", ""))
        return {"ok": True, "rooms_affected": len(targets), "kwh_saved": kwh,
                "already_eco": len(already_eco)}

    @router.get("/{property_id}/energy/summary")
    async def energy_summary(property_id: str,
                             current_user: dict = Depends(require_roles(*ROLES))):
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        logs = await db.smart_room_energy_log.find(
            {"property_id": property_id, "at": {"$gte": since}}, {"_id": 0}
        ).to_list(1000)
        kwh = round(sum(l.get("kwh_saved", 0) for l in logs), 2)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        actions_today = await db.smart_room_actions.count_documents(
            {"property_id": property_id, "at": {"$gte": today_start}})
        eco_rooms = await db.smart_room_states.count_documents(
            {"property_id": property_id, "scene": "eco"})
        return {
            "kwh_saved_30d": kwh,
            "cost_saved_30d": round(kwh * GBP_PER_KWH, 2),
            "currency": "GBP",
            "sweeps_30d": len(logs),
            "actions_today": actions_today,
            "eco_rooms": eco_rooms,
        }

    @router.get("/{property_id}/actions/log")
    async def actions_log(property_id: str, limit: int = 50,
                          current_user: dict = Depends(require_roles(*ROLES))):
        limit = max(1, min(200, limit))
        rows = await db.smart_room_actions.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("at", -1).limit(limit).to_list(limit)
        return {"rows": rows, "count": len(rows)}

    return router
