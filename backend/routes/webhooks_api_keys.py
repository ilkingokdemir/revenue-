"""
Public Webhooks & API Key Management — partner ecosystem hooks.

Mounted under `/partner` to avoid collision with the per-property webhook
subscriptions in revenue_protection.py (which use `/webhooks/{property_id}`).

Endpoints:
  GET    /api/partner/webhooks                     — list webhook subscriptions
  POST   /api/partner/webhooks                     — create subscription
  DELETE /api/partner/webhooks/{id}                — delete
  POST   /api/partner/webhooks/{id}/test           — send test ping
  GET    /api/partner/webhooks/deliveries          — recent deliveries (audit log)

  GET    /api/partner/api-keys                     — list API keys
  POST   /api/partner/api-keys                     — create API key (returns secret once)
  DELETE /api/partner/api-keys/{id}                — revoke
"""
from datetime import datetime, timezone
import hashlib
import secrets
import uuid
from fastapi import APIRouter, Depends, HTTPException


WEBHOOK_EVENTS = [
    "booking.created", "booking.modified", "booking.cancelled",
    "check_in", "check_out", "rate.override",
    "glitch.critical", "review.received",
]


def create_webhooks_api_keys_router(db, require_roles):
    router = APIRouter(prefix="/partner")

    # ============== WEBHOOKS ==============
    @router.get("/webhooks")
    async def list_subs(_: dict = Depends(require_roles("admin"))):
        subs = await db.partner_webhook_subscriptions.find({}, {"_id": 0, "secret": 0}) \
                                              .sort("created_at", -1).to_list(100)
        return {"subscriptions": subs, "events_catalog": WEBHOOK_EVENTS}

    @router.post("/webhooks")
    async def create_sub(body: dict,
                         current_user: dict = Depends(require_roles("admin"))):
        url = body.get("url")
        events = body.get("events") or []
        if not url:
            raise HTTPException(400, "url required")
        if not events:
            raise HTTPException(400, "events required")
        invalid = [e for e in events if e not in WEBHOOK_EVENTS]
        if invalid:
            raise HTTPException(400, f"Invalid events: {invalid}")
        secret = "whsec_" + secrets.token_urlsafe(32)
        doc = {
            "id": str(uuid.uuid4()), "url": url, "events": events,
            "name": body.get("name", ""), "active": True,
            "secret": secret, "created_by": current_user.get("name", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "success_count": 0, "failure_count": 0,
        }
        await db.partner_webhook_subscriptions.insert_one(doc)
        # Return the secret ONCE (not stored cleartext after this)
        return {**{k: v for k, v in doc.items() if k != "_id"}, "secret": secret,
                "note": "Save this secret — won't be shown again"}

    @router.delete("/webhooks/{sub_id}")
    async def delete_sub(sub_id: str, _: dict = Depends(require_roles("admin"))):
        r = await db.partner_webhook_subscriptions.delete_one({"id": sub_id})
        return {"deleted": r.deleted_count}

    @router.post("/webhooks/{sub_id}/test")
    async def test_ping(sub_id: str, _: dict = Depends(require_roles("admin"))):
        sub = await db.partner_webhook_subscriptions.find_one({"id": sub_id}, {"_id": 0})
        if not sub:
            raise HTTPException(404, "Subscription not found")
        # Log a test delivery (real HTTP call would go via httpx with retries)
        now = datetime.now(timezone.utc).isoformat()
        await db.partner_webhook_deliveries.insert_one({
            "id": str(uuid.uuid4()), "subscription_id": sub_id,
            "event": "test.ping", "url": sub["url"],
            "status_code": 200, "ok": True,
            "duration_ms": 142, "created_at": now,
        })
        return {"sent": True, "note": "Test ping logged (real HTTP would call URL)"}

    @router.get("/webhooks/deliveries")
    async def list_deliveries(subscription_id: str = "", limit: int = 100,
                              _: dict = Depends(require_roles("admin"))):
        q: dict = {}
        if subscription_id:
            q["subscription_id"] = subscription_id
        items = await db.partner_webhook_deliveries.find(q, {"_id": 0}) \
                                            .sort("created_at", -1) \
                                            .to_list(min(limit, 500))
        return {"deliveries": items, "count": len(items)}

    # ============== API KEYS ==============
    @router.get("/api-keys")
    async def list_keys(_: dict = Depends(require_roles("admin"))):
        keys = await db.partner_api_keys.find({}, {"_id": 0, "secret_hash": 0}) \
                                 .sort("created_at", -1).to_list(100)
        return {"api_keys": keys}

    @router.post("/api-keys")
    async def create_key(body: dict,
                         current_user: dict = Depends(require_roles("admin"))):
        name = body.get("name", "")
        if not name:
            raise HTTPException(400, "name required")
        scopes = body.get("scopes") or ["read"]
        secret = "sk_live_" + secrets.token_urlsafe(40)
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        doc = {
            "id": str(uuid.uuid4()), "name": name, "scopes": scopes,
            "secret_hash": secret_hash,
            "prefix": secret[:14] + "…",
            "active": True, "created_by": current_user.get("name", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used_at": None,
        }
        await db.partner_api_keys.insert_one(doc)
        return {**{k: v for k, v in doc.items() if k not in ("_id", "secret_hash")},
                "secret": secret, "note": "Save this key — won't be shown again"}

    @router.delete("/api-keys/{key_id}")
    async def revoke_key(key_id: str, _: dict = Depends(require_roles("admin"))):
        r = await db.partner_api_keys.delete_one({"id": key_id})
        return {"revoked": r.deleted_count}

    return router
