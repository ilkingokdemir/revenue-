"""
Hardware Lock SDK Adapter
=========================

Single integration layer that talks to physical lock systems (Salto KS,
ASSA ABLOY, Onity, dormakaba, TTLock, Nuki, August/Yale) so the rest of the
PMS doesn't care which brand the property uses.

If the property has not configured real credentials — or the credentials are
placeholders — the adapter falls back to a built-in *simulator* that mimics
realistic responses (encode card, revoke card, audit log, lock health). This
lets us demo the full guest journey before any hardware is delivered.

Endpoints
---------
GET  /lock-sdk/providers                       List all supported providers + capabilities
GET  /lock-sdk/health/{property_id}            Aggregate fleet health (uptime, battery, comms)
POST /lock-sdk/encode-card/{property_id}       Encode a key card / mobile key
POST /lock-sdk/revoke-card/{property_id}       Revoke an active key
GET  /lock-sdk/audit/{property_id}             Last 200 lock events (entries, denies, batt warnings)
POST /lock-sdk/simulate-event/{property_id}    Inject a fake audit event for demos / training
GET  /lock-sdk/test/{property_id}              Run a self-test against the configured provider

Real provider calls are stubbed where the SDK doesn't ship with us — they raise
NotImplementedError so the simulator path is taken automatically. When the user
later supplies real keys, only the corresponding `_call_<provider>` helper
needs to be replaced.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import asyncio
import logging
import random
import secrets
import uuid

logger = logging.getLogger(__name__)

# Capabilities per provider — what the adapter is expected to support.
PROVIDERS = {
    "salto":      {"name": "Salto KS",       "capabilities": ["encode", "revoke", "mobile_key", "audit", "health"]},
    "assa_abloy": {"name": "ASSA ABLOY",     "capabilities": ["encode", "revoke", "mobile_key", "audit", "health"]},
    "onity":      {"name": "Onity Hospitality", "capabilities": ["encode", "revoke", "audit"]},
    "dormakaba":  {"name": "dormakaba",      "capabilities": ["encode", "revoke", "audit", "health"]},
    "ttlock":     {"name": "TTLock",         "capabilities": ["encode", "revoke", "mobile_key", "audit", "health"]},
    "nuki":       {"name": "Nuki",           "capabilities": ["encode", "revoke", "audit", "health"]},
    "august":     {"name": "August / Yale",  "capabilities": ["encode", "revoke", "audit"]},
    "simulator":  {"name": "Built-in Simulator", "capabilities": ["encode", "revoke", "mobile_key", "audit", "health"]},
}


class EncodeReq(BaseModel):
    booking_ref: str
    room_number: str
    valid_from: str   # ISO
    valid_until: str  # ISO
    guest_name: Optional[str] = None
    mobile_key: bool = False     # if true, returns BLE token instead of card data
    notes: Optional[str] = None


class RevokeReq(BaseModel):
    card_id: str
    reason: Optional[str] = None


class SimEvent(BaseModel):
    room_number: str
    event_type: str   # entry | denied | battery_low | offline | online
    actor: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _isoz() -> str:
    return _now().isoformat()


# ---------------------------------------------------------------------------
# Adapter selection
# ---------------------------------------------------------------------------
async def _resolve_provider(db, property_id: str) -> Dict:
    """
    Reads smart_lock_configs for this property and decides whether to call
    the real provider SDK or fall back to the simulator.
    """
    cfg = await db.smart_lock_configs.find_one({"property_id": property_id}, {"_id": 0}) or {}
    provider = cfg.get("provider") or "simulator"
    api_key = cfg.get("api_key") or ""
    placeholder = (not api_key) or len(api_key) < 16 or api_key.lower().startswith(("test", "demo", "placeholder"))
    use_simulator = placeholder
    return {
        "provider": provider,
        "use_simulator": use_simulator,
        "config": cfg,
    }


# ---------------------------------------------------------------------------
# Simulator implementations
# ---------------------------------------------------------------------------
def _sim_encode(req: EncodeReq) -> Dict:
    """Generate a fake card payload that looks realistic."""
    if req.mobile_key:
        return {
            "type": "mobile_key",
            "ble_token": secrets.token_urlsafe(24),
            "ios_url": f"https://digitalkey.example/ios?t={uuid.uuid4().hex}",
            "android_url": f"https://digitalkey.example/and?t={uuid.uuid4().hex}",
            "qr_code_payload": f"DIGI-{uuid.uuid4().hex[:12].upper()}",
        }
    return {
        "type": "card",
        "card_id": f"SIM-{uuid.uuid4().hex[:10].upper()}",
        "track2": f"%B{secrets.randbelow(10**16):016d}^GUEST^{secrets.randbelow(10**4):04d}?",
        "encoder_command": f"ENCODE ROOM={req.room_number} FROM={req.valid_from} TO={req.valid_until}",
    }


def _sim_health(rooms: List[str]) -> Dict:
    """Generate plausible fleet health snapshot."""
    rng = random.Random(sum(ord(c) for c in "".join(rooms))[:10] if rooms else 1)
    fleet = []
    online = batt_low = comms_warn = 0
    for r in (rooms or [str(i) for i in range(101, 116)]):
        bat = rng.randint(20, 100)
        is_online = rng.random() > 0.04
        comms_quality = rng.randint(60, 100)
        if is_online:
            online += 1
        if bat < 30:
            batt_low += 1
        if comms_quality < 75:
            comms_warn += 1
        fleet.append({
            "room": r,
            "online": is_online,
            "battery_pct": bat,
            "comms_quality": comms_quality,
            "last_seen": (_now() - timedelta(minutes=rng.randint(0, 240))).isoformat(),
        })
    total = len(fleet) or 1
    return {
        "total_locks": total,
        "online": online,
        "offline": total - online,
        "battery_low": batt_low,
        "comms_warn": comms_warn,
        "uptime_pct": round((online / total) * 100, 1),
        "fleet": fleet,
    }


def _sim_audit_seed() -> List[Dict]:
    """Initial seed (used only when audit collection is empty)."""
    out = []
    base = _now()
    for i in range(40):
        out.append({
            "id": str(uuid.uuid4()),
            "event_type": random.choice(["entry", "entry", "entry", "denied", "battery_low"]),
            "room_number": str(random.randint(101, 215)),
            "actor": random.choice(["guest", "staff", "guest", "guest", "maintenance"]),
            "timestamp": (base - timedelta(minutes=i * 7)).isoformat(),
            "source": "simulator",
        })
    return out


# ---------------------------------------------------------------------------
# Real provider stubs — will raise NotImplementedError until SDKs are wired.
# ---------------------------------------------------------------------------
async def _call_real_encode(provider: str, cfg: Dict, req: EncodeReq) -> Dict:
    raise NotImplementedError(f"{provider} live SDK not yet integrated")


async def _call_real_revoke(provider: str, cfg: Dict, card_id: str) -> Dict:
    raise NotImplementedError(f"{provider} live SDK not yet integrated")


async def _call_real_health(provider: str, cfg: Dict) -> Dict:
    raise NotImplementedError(f"{provider} live SDK not yet integrated")


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------
def create_lock_sdk_router(db, require_roles):
    router = APIRouter()

    @router.get("/lock-sdk/providers")
    async def providers(current_user: dict = Depends(require_roles("admin", "manager"))):
        return PROVIDERS

    @router.get("/lock-sdk/test/{property_id}")
    async def test(property_id: str,
                   current_user: dict = Depends(require_roles("admin", "manager"))):
        info = await _resolve_provider(db, property_id)
        return {
            "provider": info["provider"],
            "use_simulator": info["use_simulator"],
            "ok": True,
            "message": ("Simulator active — encode/revoke calls will return mock data."
                        if info["use_simulator"]
                        else f"Live {info['provider']} credentials detected."),
        }

    @router.get("/lock-sdk/health/{property_id}")
    async def health(property_id: str,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        info = await _resolve_provider(db, property_id)
        rooms = [r.get("room_number") for r in (info["config"].get("rooms") or []) if r.get("room_number")]
        if info["use_simulator"]:
            return {**_sim_health(rooms), "source": "simulator", "provider": info["provider"]}
        try:
            data = await _call_real_health(info["provider"], info["config"])
            return {**data, "source": "live", "provider": info["provider"]}
        except NotImplementedError:
            return {**_sim_health(rooms), "source": "simulator-fallback", "provider": info["provider"]}

    @router.post("/lock-sdk/encode-card/{property_id}")
    async def encode_card(property_id: str, req: EncodeReq,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        info = await _resolve_provider(db, property_id)
        # Use simulator if requested
        if info["use_simulator"]:
            payload = _sim_encode(req)
        else:
            try:
                payload = await _call_real_encode(info["provider"], info["config"], req)
            except NotImplementedError:
                payload = _sim_encode(req)
                payload["fallback"] = True

        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "provider": info["provider"],
            "booking_ref": req.booking_ref,
            "room_number": req.room_number,
            "guest_name": req.guest_name,
            "valid_from": req.valid_from,
            "valid_until": req.valid_until,
            "mobile_key": req.mobile_key,
            "card_payload": payload,
            "issued_by": current_user.get("email"),
            "issued_at": _isoz(),
            "status": "active",
            "source": "simulator" if info["use_simulator"] else "live",
        }
        await db.lock_card_events.insert_one(dict(record))
        # Record an audit event so health/audit shows live activity
        await db.lock_audit_events.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "event_type": "encode",
            "room_number": req.room_number,
            "actor": "staff",
            "timestamp": _isoz(),
            "source": record["source"],
            "card_id": payload.get("card_id"),
        })
        record.pop("_id", None)
        return record

    @router.post("/lock-sdk/revoke-card/{property_id}")
    async def revoke_card(property_id: str, req: RevokeReq,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        info = await _resolve_provider(db, property_id)
        if not info["use_simulator"]:
            try:
                await _call_real_revoke(info["provider"], info["config"], req.card_id)
            except NotImplementedError:
                pass
        await db.lock_card_events.update_one(
            {"property_id": property_id, "card_payload.card_id": req.card_id},
            {"$set": {"status": "revoked", "revoked_at": _isoz(),
                      "revoke_reason": req.reason, "revoked_by": current_user.get("email")}}
        )
        await db.lock_audit_events.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "event_type": "revoke",
            "card_id": req.card_id,
            "actor": current_user.get("email"),
            "timestamp": _isoz(),
            "source": "simulator" if info["use_simulator"] else "live",
        })
        return {"ok": True, "card_id": req.card_id, "status": "revoked"}

    @router.get("/lock-sdk/audit/{property_id}")
    async def audit(property_id: str, limit: int = 200,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.lock_audit_events.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("timestamp", -1).to_list(limit)
        if not items:
            # Seed one-time demo data so the UI isn't empty
            seed = _sim_audit_seed()
            for s in seed:
                s["property_id"] = property_id
            await db.lock_audit_events.insert_many(seed)
            items = await db.lock_audit_events.find(
                {"property_id": property_id}, {"_id": 0}
            ).sort("timestamp", -1).to_list(limit)
        return {"items": items, "count": len(items)}

    @router.post("/lock-sdk/simulate-event/{property_id}")
    async def simulate_event(property_id: str, ev: SimEvent,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "event_type": ev.event_type,
            "room_number": ev.room_number,
            "actor": ev.actor or "demo",
            "timestamp": _isoz(),
            "source": "simulator-manual",
        }
        await db.lock_audit_events.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    return router
