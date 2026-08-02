"""Mobil push bildirimleri — Expo Push API (anahtar gerektirmez, Expo Go ile çalışır)."""
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import require_perm

logger = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class PushTokenIn(BaseModel):
    token: str
    platform: str = "unknown"


class PushTestIn(BaseModel):
    title: str = "MyHotelBox"
    body: str = "Test bildirimi"


async def send_expo_push(db, title: str, body: str, data: dict | None = None) -> dict:
    tokens = [t["token"] async for t in db.mobile_push_tokens.find({}, {"_id": 0, "token": 1})]
    if not tokens:
        return {"sent": 0, "reason": "no_tokens"}
    messages = [{"to": t, "title": title, "body": body, "data": data or {}, "sound": "default"}
                for t in tokens[:100]]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(EXPO_PUSH_URL, json=messages)
            results = resp.json().get("data", [])
        bad = [tokens[i] for i, r in enumerate(results)
               if isinstance(r, dict) and r.get("details", {}).get("error") == "DeviceNotRegistered"]
        if bad:
            await db.mobile_push_tokens.delete_many({"token": {"$in": bad}})
        return {"sent": len(messages) - len(bad), "invalid_removed": len(bad)}
    except Exception as e:
        logger.warning(f"expo push failed: {e}")
        return {"sent": 0, "error": str(e)}


def create_mobile_push_router(db):
    router = APIRouter()

    @router.post("/mobile/push-token")
    async def register_token(body: PushTokenIn,
                             current_user: dict = Depends(require_perm("view_dashboard", "view_bookings", mode="any"))):
        await db.mobile_push_tokens.update_one(
            {"token": body.token},
            {"$set": {"token": body.token, "platform": body.platform,
                      "user_email": current_user.get("email", ""),
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        return {"status": "registered"}

    @router.post("/mobile/push-test")
    async def push_test(body: PushTestIn,
                        current_user: dict = Depends(require_perm("edit_bookings"))):
        return await send_expo_push(db, body.title, body.body, {"type": "test"})

    @router.get("/mobile/push-tokens")
    async def list_tokens(current_user: dict = Depends(require_perm("edit_bookings"))):
        return await db.mobile_push_tokens.find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)

    return router
