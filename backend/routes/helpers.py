"""
Shared helper functions used across multiple route modules
"""
from datetime import datetime, timezone
import asyncio
import hashlib
import hmac as hmac_lib
import json
import uuid
import httpx


async def log_sync(db, platform: str, direction: str, status: str, message: str = "", ref_id: str = ""):
    """Log a sync event"""
    await db.sync_logs.insert_one({
        "id": str(uuid.uuid4()),
        "platform": platform,
        "direction": direction,
        "status": status,
        "message": message,
        "ref_id": ref_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def fire_webhooks(db, event: str, data: dict):
    """Fire active webhooks: HMAC-SHA256 imza + 3 deneme (exponential backoff)."""
    clean_data = {k: v for k, v in data.items() if k != "_id"}
    webhooks = await db.webhooks.find({"is_active": True}, {"_id": 0}).to_list(50)
    for wh in webhooks:
        if wh.get("events") and event not in wh["events"]:
            continue
        payload = {"event": event, "data": clean_data,
                   "timestamp": datetime.now(timezone.utc).isoformat()}
        body = json.dumps(payload, default=str)
        secret = wh.get("secret", "")
        signature = hmac_lib.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest() if secret else ""
        headers = {"Content-Type": "application/json",
                   "X-Webhook-Event": event,
                   "X-Webhook-Secret": secret,
                   "X-Webhook-Signature": f"sha256={signature}" if signature else ""}
        status_code, success, error, attempts = 0, False, "", 0
        start = datetime.now(timezone.utc)
        for attempt, delay in enumerate((0, 2, 5), start=1):
            attempts = attempt
            if delay:
                await asyncio.sleep(delay)
            try:
                async with httpx.AsyncClient(timeout=5.0) as c:
                    resp = await c.post(wh["url"], content=body, headers=headers)
                status_code = resp.status_code
                if resp.status_code < 400:
                    success = True
                    break
                error = f"HTTP {resp.status_code}"
            except Exception as e:
                error = str(e)[:200]
        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        await db.webhook_deliveries.insert_one({
            "id": str(uuid.uuid4()), "webhook_id": wh["id"], "event": event,
            "url": wh["url"], "status_code": status_code, "success": success,
            "attempts": attempts, "error": error if not success else "",
            "response_time_ms": elapsed_ms,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


def serialize_review(review: dict) -> dict:
    """Serialize review for JSON response"""
    for field in ['review_date', 'response_date', 'created_at']:
        if field in review and isinstance(review[field], datetime):
            review[field] = review[field].isoformat()
    return review


def deserialize_review(review: dict) -> dict:
    """Deserialize review from MongoDB"""
    for field in ['review_date', 'response_date', 'created_at']:
        if field in review and isinstance(review[field], str):
            review[field] = datetime.fromisoformat(review[field])
    return review
