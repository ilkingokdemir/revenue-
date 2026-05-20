"""
Public API Sandbox + Developer Portal (P0 #30)
----------------------------------------------
Exposes a controlled, read-only public surface so partner integrations
(channel managers, accounting tools, BI dashboards) can build against the
hotel's data with an issued API key.

Endpoints
---------
POST /developer/keys                         Issue a new API key (scoped, with optional expiry)
GET  /developer/keys                         List keys for current property (secret hash only)
DELETE /developer/keys/{key_id}              Revoke a key
POST /developer/keys/{key_id}/rotate         Rotate (issue new secret, keep id)
GET  /developer/spec                         Pointer to OpenAPI + sample requests
GET  /developer/sandbox/availability         Public sandbox: rate availability
GET  /developer/sandbox/booking/{id}         Public sandbox: booking lookup
POST /developer/sandbox/echo                 Echo endpoint for end-to-end auth tests
GET  /developer/usage/{property_id}          Per-key usage stats (last 30d)

Auth
----
Sandbox endpoints accept a header `X-API-Key:<key>`. The key is hashed
(SHA-256) on save and checked on every call. Each call writes a thin row
to `dev_api_calls` for the usage dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import hashlib
import secrets as pysecrets
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def create_public_api_router(db, require_roles):
    router = APIRouter()

    # ------------------ Key management (auth required) ------------------

    @router.post("/developer/keys")
    async def issue_key(data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        name = (data.get("name") or "Untitled key").strip()
        scopes = data.get("scopes") or ["read:availability", "read:bookings"]
        if not property_id:
            raise HTTPException(400, "property_id required")
        secret = "hk_" + pysecrets.token_urlsafe(28)
        record = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "name": name,
            "scopes": scopes,
            "secret_prefix": secret[:8],
            "secret_hash": _hash(secret),
            "active": True,
            "rate_per_min": int(data.get("rate_per_min") or 60),
            "expires_at": data.get("expires_at", ""),
            "created_at": _now(),
            "created_by": current_user.get("name", "Staff"),
            "last_used_at": "",
            "calls_total": 0,
        }
        await db.dev_api_keys.insert_one(dict(record))
        record.pop("_id", None)
        # Secret is only returned ONCE at creation time.
        return {"ok": True, "key": record, "secret": secret,
                 "warning": "Store this secret — it cannot be retrieved later."}

    @router.get("/developer/keys")
    async def list_keys(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.dev_api_keys.find(
            {"property_id": property_id}, {"_id": 0, "secret_hash": 0}
        ).sort("created_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.delete("/developer/keys/{key_id}")
    async def revoke_key(key_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await db.dev_api_keys.update_one(
            {"id": key_id}, {"$set": {"active": False, "revoked_at": _now(),
                                        "revoked_by": current_user.get("name", "Staff")}}
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Key not found")
        return {"ok": True, "key_id": key_id}

    @router.post("/developer/keys/{key_id}/rotate")
    async def rotate_key(key_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.dev_api_keys.find_one({"id": key_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Key not found")
        secret = "hk_" + pysecrets.token_urlsafe(28)
        await db.dev_api_keys.update_one(
            {"id": key_id},
            {"$set": {"secret_prefix": secret[:8], "secret_hash": _hash(secret),
                       "rotated_at": _now(), "rotated_by": current_user.get("name", "Staff")}}
        )
        return {"ok": True, "secret": secret,
                 "warning": "Old secret is now invalid. Update integrations."}

    @router.get("/developer/spec")
    async def get_spec():
        return {
            "openapi_url": "/api/openapi.json",
            "docs_url": "/api/docs",
            "redoc_url": "/api/redoc",
            "auth_scheme": "X-API-Key header",
            "sandbox_endpoints": [
                {"method": "GET",  "path": "/api/developer/sandbox/availability",
                 "params": {"property_id": "required", "check_in": "YYYY-MM-DD", "check_out": "YYYY-MM-DD"}},
                {"method": "GET",  "path": "/api/developer/sandbox/booking/{booking_id}", "params": {}},
                {"method": "POST", "path": "/api/developer/sandbox/echo",
                 "body": {"message": "string"}},
            ],
            "rate_limits": "Per-key, configurable (default 60 req/min).",
            "examples": {
                "curl_echo": "curl -X POST $URL/api/developer/sandbox/echo -H 'X-API-Key: hk_...' -d '{\"message\":\"hi\"}'",
            },
        }

    @router.get("/developer/usage/{property_id}")
    async def usage(property_id: str, days: int = 30,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.dev_api_calls.find(
            {"property_id": property_id, "at": {"$gte": since}}, {"_id": 0}
        ).to_list(20000)
        by_key: Dict[str, int] = {}
        by_endpoint: Dict[str, int] = {}
        errors = 0
        for r in rows:
            by_key[r.get("key_id", "?")] = by_key.get(r.get("key_id", "?"), 0) + 1
            by_endpoint[r.get("endpoint", "?")] = by_endpoint.get(r.get("endpoint", "?"), 0) + 1
            if int(r.get("status_code") or 200) >= 400:
                errors += 1
        return {
            "window_days": days, "calls": len(rows), "errors": errors,
            "by_key": by_key, "by_endpoint": by_endpoint,
        }

    # ------------------ Sandbox surface (key auth) ------------------

    async def _check_key(x_api_key: Optional[str], required_scope: str, endpoint: str,
                          property_id: str = "") -> dict:
        if not x_api_key:
            raise HTTPException(401, "X-API-Key header missing")
        key = await db.dev_api_keys.find_one({"secret_hash": _hash(x_api_key), "active": True}, {"_id": 0})
        if not key:
            raise HTTPException(401, "Invalid or revoked API key")
        if key.get("expires_at") and key["expires_at"] < _now():
            raise HTTPException(401, "API key expired")
        if required_scope not in (key.get("scopes") or []):
            raise HTTPException(403, f"Key lacks scope: {required_scope}")
        # Lightweight per-minute throttle
        one_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        recent = await db.dev_api_calls.count_documents({"key_id": key["id"], "at": {"$gte": one_min_ago}})
        if recent >= int(key.get("rate_per_min") or 60):
            raise HTTPException(429, "Rate limit exceeded")
        await db.dev_api_calls.insert_one({
            "id": str(uuid.uuid4()), "key_id": key["id"],
            "property_id": property_id or key["property_id"],
            "endpoint": endpoint, "at": _now(), "status_code": 200,
        })
        await db.dev_api_keys.update_one(
            {"id": key["id"]},
            {"$set": {"last_used_at": _now()}, "$inc": {"calls_total": 1}}
        )
        return key

    @router.get("/developer/sandbox/availability")
    async def sandbox_availability(property_id: str, check_in: str, check_out: str,
                                       x_api_key: Optional[str] = Header(None)):
        key = await _check_key(x_api_key, "read:availability", "sandbox/availability", property_id)
        if key["property_id"] != property_id:
            raise HTTPException(403, "Key does not have access to this property_id")
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(200)
        # Count bookings overlapping the requested window
        overlap_q = {"property_id": property_id, "status": {"$nin": ["cancelled", "no_show"]},
                      "check_in": {"$lt": check_out}, "check_out": {"$gt": check_in}}
        bookings = await db.bookings.find(overlap_q, {"_id": 0}).to_list(2000)
        avail = []
        for rt in room_types:
            taken = sum(1 for b in bookings if b.get("room_type") == rt.get("name"))
            avail.append({
                "room_type": rt.get("name"),
                "rate": rt.get("base_rate", 0),
                "currency": rt.get("currency", "GBP"),
                "total_inventory": rt.get("inventory", 0),
                "taken": taken,
                "available": max(0, int(rt.get("inventory") or 0) - taken),
            })
        return {"property_id": property_id, "check_in": check_in, "check_out": check_out,
                 "availability": avail}

    @router.get("/developer/sandbox/booking/{booking_id}")
    async def sandbox_booking(booking_id: str, x_api_key: Optional[str] = Header(None)):
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        await _check_key(x_api_key, "read:bookings", "sandbox/booking", b.get("property_id", ""))
        # Strip sensitive fields
        for f in ("card_token", "card_last4", "internal_notes"):
            b.pop(f, None)
        return {"booking": b}

    @router.post("/developer/sandbox/echo")
    async def sandbox_echo(data: Dict, x_api_key: Optional[str] = Header(None)):
        key = await _check_key(x_api_key, "read:availability", "sandbox/echo")
        return {
            "ok": True,
            "key_id": key["id"],
            "scopes": key.get("scopes", []),
            "echo": data,
            "server_time": _now(),
        }

    return router
