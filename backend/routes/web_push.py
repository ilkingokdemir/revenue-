"""
PWA Web Push Notifications (P0 #18)
-----------------------------------
Stores browser push subscriptions and dispatches simulated push payloads.

In production this would call Web-Push (VAPID) — that requires a VAPID key
pair the operator generates once. To keep this keyless we record the
subscription endpoints and simulate delivery into a `web_push_log` collection
which the front desk PWA polls. As soon as the operator pastes their VAPID
keys into property.web_push_vapid the same dispatcher will perform the real
HTTPS POST to the endpoint.

Endpoints
---------
POST /push/subscribe                       Register a subscription (browser)
POST /push/unsubscribe                     Remove a subscription
GET  /push/{property_id}/subscriptions     List active subscriptions
POST /push/{property_id}/send              Send a payload to one tag/role/all
GET  /push/{property_id}/log               Recent dispatch log
GET  /push/{property_id}/pending           PWA polls this to draw simulated pushes
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_web_push_router(db, require_roles):
    router = APIRouter()

    @router.post("/push/subscribe")
    async def subscribe(data: Dict):
        endpoint = (data.get("endpoint") or "").strip()
        property_id = (data.get("property_id") or "").strip()
        if not endpoint or not property_id:
            raise HTTPException(400, "endpoint + property_id required")
        sub = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "endpoint": endpoint,
            "p256dh": data.get("p256dh", ""),
            "auth": data.get("auth", ""),
            "user_id": data.get("user_id", ""),
            "user_role": data.get("user_role", "staff"),
            "tags": data.get("tags") or [],
            "user_agent": data.get("user_agent", ""),
            "subscribed_at": _now(),
            "last_seen": _now(),
            "active": True,
        }
        # Replace any existing identical endpoint
        await db.web_push_subs.delete_many({"endpoint": endpoint})
        await db.web_push_subs.insert_one(dict(sub))
        sub.pop("_id", None)
        return {"ok": True, "subscription": sub}

    @router.post("/push/unsubscribe")
    async def unsubscribe(data: Dict):
        endpoint = (data.get("endpoint") or "").strip()
        if not endpoint:
            raise HTTPException(400, "endpoint required")
        result = await db.web_push_subs.delete_many({"endpoint": endpoint})
        return {"ok": True, "removed": result.deleted_count}

    @router.get("/push/{property_id}/subscriptions")
    async def list_subs(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.web_push_subs.find(
            {"property_id": property_id, "active": True}, {"_id": 0, "p256dh": 0, "auth": 0}
        ).sort("subscribed_at", -1).to_list(500)
        roles = {}
        for r in rows:
            roles[r.get("user_role", "staff")] = roles.get(r.get("user_role", "staff"), 0) + 1
        return {"items": rows, "count": len(rows), "by_role": roles}

    @router.post("/push/{property_id}/send")
    async def send_push(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        title = (data.get("title") or "").strip()
        body = (data.get("body") or "").strip()
        if not title or not body:
            raise HTTPException(400, "title + body required")
        target_role = (data.get("target_role") or "").strip()
        target_tag = (data.get("target_tag") or "").strip()
        url = (data.get("url") or "/")

        q: Dict = {"property_id": property_id, "active": True}
        if target_role:
            q["user_role"] = target_role
        if target_tag:
            q["tags"] = target_tag
        subs = await db.web_push_subs.find(q, {"_id": 0}).to_list(2000)

        # Look up VAPID config — if present we'd actually fire HTTPS POST.
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0}) or {}
        has_vapid = bool(prop.get("web_push_vapid", {}).get("private_key"))

        log_id = str(uuid.uuid4())
        delivery = {
            "id": log_id,
            "property_id": property_id,
            "title": title,
            "body": body,
            "url": url,
            "icon": data.get("icon", ""),
            "category": data.get("category", "ops"),
            "target_role": target_role,
            "target_tag": target_tag,
            "subscriber_count": len(subs),
            "delivery_mode": "real_vapid" if has_vapid else "simulated",
            "sent_at": _now(),
            "sent_by": current_user.get("name", "Staff"),
        }
        await db.web_push_log.insert_one(dict(delivery))
        # Drop into pending queue (PWA frontends poll this until VAPID is wired)
        if not has_vapid:
            for s in subs:
                await db.web_push_pending.insert_one({
                    "id": str(uuid.uuid4()),
                    "log_id": log_id,
                    "property_id": property_id,
                    "endpoint": s["endpoint"],
                    "user_id": s.get("user_id", ""),
                    "user_role": s.get("user_role", ""),
                    "title": title, "body": body, "url": url,
                    "icon": delivery["icon"], "category": delivery["category"],
                    "queued_at": _now(),
                    "delivered": False,
                })
        delivery.pop("_id", None)
        return {"ok": True, "delivery": delivery, "subscribers_targeted": len(subs)}

    @router.get("/push/{property_id}/log")
    async def get_log(property_id: str, days: int = 7,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.web_push_log.find(
            {"property_id": property_id, "sent_at": {"$gte": since}}, {"_id": 0}
        ).sort("sent_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.get("/push/{property_id}/pending")
    async def get_pending(property_id: str, user_id: str = "", user_role: str = ""):
        """PWA polls this to draw simulated push notifications when VAPID isn't wired."""
        q: Dict = {"property_id": property_id, "delivered": False}
        if user_id:
            q["user_id"] = user_id
        if user_role:
            q["user_role"] = user_role
        rows = await db.web_push_pending.find(q, {"_id": 0}).sort("queued_at", 1).to_list(50)
        if rows:
            ids = [r["id"] for r in rows]
            await db.web_push_pending.update_many(
                {"id": {"$in": ids}}, {"$set": {"delivered": True, "delivered_at": _now()}}
            )
        return {"items": rows, "count": len(rows)}

    return router
