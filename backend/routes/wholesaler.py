"""
Wholesaler / Net Rate Network — Cloudbeds Hotel Trader parity.

Adapter-pattern hub for connecting to global wholesalers / net-rate partners:
  - HotelBeds
  - TBO Holidays
  - Travelgate / Hotel Trader
  - GTA / Restel
  - Mock (for sandbox/dev)

Inbound: pulls rates+inventory requests from wholesalers, returns price.
Outbound: pushes net rates + restrictions to wholesaler inventory.

Like channels_v2.py, all adapter calls currently route to a MOCK simulator
until partner SDK keys arrive. Real adapters can be hot-swapped by replacing
`_simulate_adapter_call` per provider.

Endpoints
---------
Admin/manager:
  GET  /api/wholesaler/providers              — supported wholesaler catalog
  GET  /api/wholesaler/connections            — list configured connections per property
  POST /api/wholesaler/connections            — connect a wholesaler with credentials
  PATCH /api/wholesaler/connections/{id}
  DELETE /api/wholesaler/connections/{id}
  POST /api/wholesaler/connections/{id}/test  — ping/auth handshake
  POST /api/wholesaler/connections/{id}/push  — push rates+inventory
  GET  /api/wholesaler/inbound-bookings       — bookings received via wholesalers
  GET  /api/wholesaler/queue                  — pending sync jobs
  POST /api/wholesaler/dispatch                — manually trigger queue flush
"""
from datetime import datetime, timezone, timedelta
import os
import uuid
import logging
import random
import asyncio
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


PROVIDERS = [
    {"id": "hotelbeds", "label": "HotelBeds (Hotelbeds Group)",
     "auth_fields": ["api_key", "secret"], "supports_push": True,
     "supports_pull": True, "default_commission": 18,
     "partner_count_global": 60000},
    {"id": "tbo", "label": "TBO Holidays",
     "auth_fields": ["client_id", "secret"], "supports_push": True,
     "supports_pull": True, "default_commission": 15,
     "partner_count_global": 22000},
    {"id": "travelgate", "label": "Travelgate / Hotel Trader",
     "auth_fields": ["api_key"], "supports_push": True,
     "supports_pull": True, "default_commission": 17,
     "partner_count_global": 140},
    {"id": "gta", "label": "GTA / Restel",
     "auth_fields": ["username", "password"], "supports_push": True,
     "supports_pull": False, "default_commission": 20,
     "partner_count_global": 12000},
    {"id": "mock", "label": "Mock Wholesaler (sandbox)",
     "auth_fields": [], "supports_push": True, "supports_pull": True,
     "default_commission": 10, "partner_count_global": 1},
]


async def _simulate_adapter_call(provider: str, action: str, payload: dict) -> dict:
    """Simulate a wholesaler API call. HOT-SWAP: replace this with real SDK calls
    per provider when partner credentials are configured."""
    await asyncio.sleep(0.05)  # simulate network
    if action == "test":
        return {"ok": True, "provider": provider, "echo": "pong",
                "tested_at": _now_iso()}
    elif action == "push_rates":
        return {"ok": True, "pushed": len(payload.get("dates", [])),
                "provider": provider, "reference": f"{provider}-{uuid.uuid4().hex[:8]}"}
    elif action == "fetch_inbound":
        # Pretend to fetch new bookings
        n = random.randint(0, 2)
        items = []
        for _ in range(n):
            items.append({
                "external_id": f"{provider}-{uuid.uuid4().hex[:10]}",
                "guest_name": random.choice([
                    "Hans Müller", "Sophie Lefevre", "Carlos Mendez", "Olga Ivanova",
                    "Yuki Tanaka", "Ahmed El-Sayed", "Anna Kowalski"]),
                "check_in": (datetime.now(timezone.utc) +
                             timedelta(days=random.randint(14, 60))).strftime("%Y-%m-%d"),
                "check_out": (datetime.now(timezone.utc) +
                              timedelta(days=random.randint(61, 75))).strftime("%Y-%m-%d"),
                "rooms": 1,
                "guests": random.randint(1, 4),
                "net_rate": round(random.uniform(50, 250), 2),
                "currency": "GBP",
                "commission_percent": random.choice([15, 18, 20]),
            })
        return {"ok": True, "items": items, "count": len(items)}
    return {"ok": False, "error": "unknown action"}


def create_wholesaler_router(db, require_roles):
    router = APIRouter()

    @router.get("/wholesaler/providers")
    async def providers(_: dict = Depends(require_roles("admin", "manager"))):
        return {"items": PROVIDERS}

    @router.get("/wholesaler/connections")
    async def list_connections(property_id: str = "",
                                _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if property_id:
            q["property_id"] = property_id
        items = await db.wholesaler_connections.find(
            q, {"_id": 0, "credentials": 0}
        ).sort("created_at", -1).to_list(200)
        return {"items": items, "count": len(items)}

    @router.post("/wholesaler/connections")
    async def create_connection(body: dict,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        prop = body.get("property_id")
        provider = body.get("provider")
        if not prop or not provider:
            raise HTTPException(400, "property_id and provider required")
        if provider not in {p["id"] for p in PROVIDERS}:
            raise HTTPException(400, f"Unknown provider '{provider}'")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": prop,
            "provider": provider,
            "label": body.get("label", provider),
            "credentials": body.get("credentials", {}),  # stored as-is; redacted in responses
            "commission_percent": float(body.get("commission_percent",
                                                  next(p["default_commission"] for p in PROVIDERS if p["id"] == provider))),
            "is_active": True,
            "status": "configured",
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
            "last_test_at": None,
            "last_push_at": None,
            "last_pull_at": None,
            "push_count": 0,
            "inbound_count": 0,
        }
        await db.wholesaler_connections.insert_one(doc)
        out = {**doc}
        out.pop("_id", None)
        out["credentials"] = {k: "***" for k in (doc.get("credentials") or {})}
        return out

    @router.patch("/wholesaler/connections/{conn_id}")
    async def patch_connection(conn_id: str, body: dict,
                                _: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"label", "commission_percent", "is_active", "credentials"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        update["updated_at"] = _now_iso()
        r = await db.wholesaler_connections.update_one({"id": conn_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "Connection not found")
        return {"ok": True}

    @router.delete("/wholesaler/connections/{conn_id}")
    async def delete_connection(conn_id: str,
                                 _: dict = Depends(require_roles("admin"))):
        r = await db.wholesaler_connections.delete_one({"id": conn_id})
        if not r.deleted_count:
            raise HTTPException(404, "Connection not found")
        return {"ok": True}

    @router.post("/wholesaler/connections/{conn_id}/test")
    async def test_connection(conn_id: str,
                               _: dict = Depends(require_roles("admin", "manager"))):
        conn = await db.wholesaler_connections.find_one({"id": conn_id}, {"_id": 0})
        if not conn:
            raise HTTPException(404, "Connection not found")
        result = await _simulate_adapter_call(conn["provider"], "test",
                                              {"credentials": conn.get("credentials", {})})
        new_status = "online" if result.get("ok") else "error"
        await db.wholesaler_connections.update_one(
            {"id": conn_id},
            {"$set": {"status": new_status, "last_test_at": _now_iso()}}
        )
        return {"ok": result.get("ok"), "result": result, "status": new_status}

    @router.post("/wholesaler/connections/{conn_id}/push")
    async def push_rates(conn_id: str, body: dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        conn = await db.wholesaler_connections.find_one({"id": conn_id}, {"_id": 0})
        if not conn:
            raise HTTPException(404, "Connection not found")
        if not conn.get("is_active", True):
            raise HTTPException(403, "Connection disabled")
        dates = body.get("dates", [])
        if not dates:
            raise HTTPException(400, "dates[] required (list of {date, rate, restrictions?})")
        # Enqueue job
        job = {
            "id": str(uuid.uuid4()),
            "connection_id": conn_id,
            "provider": conn["provider"],
            "property_id": conn["property_id"],
            "action": "push_rates",
            "payload": {"dates": dates, "room_type_id": body.get("room_type_id")},
            "status": "completed",
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        result = await _simulate_adapter_call(conn["provider"], "push_rates", job["payload"])
        job["result"] = result
        await db.wholesaler_sync_queue.insert_one(job)
        await db.wholesaler_connections.update_one(
            {"id": conn_id},
            {"$set": {"last_push_at": _now_iso()},
             "$inc": {"push_count": 1}}
        )
        return {"ok": True, "pushed": result.get("pushed"), "reference": result.get("reference")}

    @router.post("/wholesaler/dispatch")
    async def dispatch_inbound(_: dict = Depends(require_roles("admin", "manager"))):
        """Poll all active connections for inbound bookings."""
        conns = await db.wholesaler_connections.find(
            {"is_active": True, "status": {"$in": ["online", "configured"]}},
            {"_id": 0}
        ).to_list(200)
        total_new = 0
        per_provider = {}
        for c in conns:
            r = await _simulate_adapter_call(c["provider"], "fetch_inbound", {})
            items = r.get("items", [])
            if items:
                for it in items:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "connection_id": c["id"],
                        "provider": c["provider"],
                        "property_id": c["property_id"],
                        "external_id": it["external_id"],
                        "guest_name": it["guest_name"],
                        "check_in": it["check_in"],
                        "check_out": it["check_out"],
                        "rooms": it["rooms"],
                        "guests": it["guests"],
                        "net_rate": it["net_rate"],
                        "currency": it["currency"],
                        "commission_percent": it["commission_percent"],
                        "status": "received",
                        "received_at": _now_iso(),
                    }
                    # Skip if already imported (idempotency)
                    ex = await db.wholesaler_inbound.find_one(
                        {"external_id": it["external_id"]}, {"_id": 0, "id": 1}
                    )
                    if not ex:
                        await db.wholesaler_inbound.insert_one(doc)
                        total_new += 1
                await db.wholesaler_connections.update_one(
                    {"id": c["id"]},
                    {"$set": {"last_pull_at": _now_iso()},
                     "$inc": {"inbound_count": len(items)}}
                )
            per_provider[c["provider"]] = per_provider.get(c["provider"], 0) + len(items)
        return {"ok": True, "total_new": total_new,
                "connections_polled": len(conns),
                "per_provider": per_provider}

    @router.get("/wholesaler/inbound-bookings")
    async def list_inbound(property_id: str = "", provider: str = "", limit: int = 100,
                           _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if property_id:
            q["property_id"] = property_id
        if provider:
            q["provider"] = provider
        items = await db.wholesaler_inbound.find(q, {"_id": 0}).sort(
            "received_at", -1
        ).to_list(min(limit, 500))
        return {"items": items, "count": len(items)}

    @router.get("/wholesaler/queue")
    async def queue_status(limit: int = 50,
                            _: dict = Depends(require_roles("admin", "manager"))):
        items = await db.wholesaler_sync_queue.find({}, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    return router
