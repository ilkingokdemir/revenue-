"""
Shared helper functions used across multiple route modules
"""
from datetime import datetime, timezone
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
    """Fire active webhooks for an event"""
    clean_data = {k: v for k, v in data.items() if k != "_id"}
    webhooks = await db.webhooks.find({"is_active": True}, {"_id": 0}).to_list(50)
    for wh in webhooks:
        if wh.get("events") and event not in wh["events"]:
            continue
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                await c.post(wh["url"], json={"event": event, "data": clean_data, "timestamp": datetime.now(timezone.utc).isoformat()},
                    headers={"X-Webhook-Secret": wh.get("secret", ""), "X-Webhook-Event": event})
            await db.webhook_deliveries.insert_one({
                "id": str(uuid.uuid4()), "webhook_id": wh["id"], "event": event,
                "url": wh["url"], "status_code": 200, "success": True,
                "response_time_ms": 0, "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception:
            pass


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
