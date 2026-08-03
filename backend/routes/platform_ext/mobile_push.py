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


class PushPrefsIn(BaseModel):
    payment_received: bool = True
    pickup_strong: bool = True
    channel_drop: bool = True


class PushTestIn(BaseModel):
    title: str = "MyHotelBox"
    body: str = "Test bildirimi"


async def send_expo_push(db, title: str, body: str, data: dict | None = None, kind: str | None = None) -> dict:
    token_docs = await db.mobile_push_tokens.find({}, {"_id": 0, "token": 1, "user_email": 1}).to_list(500)
    if kind:
        blocked = {p["user_email"] async for p in db.mobile_push_prefs.find(
            {f"prefs.{kind}": False}, {"_id": 0, "user_email": 1})}
        token_docs = [t for t in token_docs if t.get("user_email") not in blocked]
    tokens = [t["token"] for t in token_docs]
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


async def run_mobile_daily_pulse(db, property_id: str = "") -> dict:
    """Günlük 09:00 — güçlü pickup ve kanal düşüşü push'ları (tercihlere göre filtreli)."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    q = {"status": {"$nin": ["cancelled"]}}
    if property_id and property_id != "all":
        q["property_id"] = property_id
    sent = []
    # Güçlü pickup (son 24s vs önceki 24s)
    cut24 = (now - timedelta(hours=24)).isoformat()
    cut48 = (now - timedelta(hours=48)).isoformat()
    cur = await db.bookings.find({**q, "created_at": {"$gte": cut24, "$lte": now.isoformat()}},
                                 {"_id": 0, "rooms": 1, "nights": 1}).to_list(1000)
    prev = await db.bookings.find({**q, "created_at": {"$gte": cut48, "$lt": cut24}},
                                  {"_id": 0, "rooms": 1}).to_list(1000)
    rooms24 = sum(int(b.get("rooms") or 1) for b in cur)
    rn24 = sum(int(b.get("rooms") or 1) * int(b.get("nights") or 1) for b in cur)
    prev24 = sum(int(b.get("rooms") or 1) for b in prev)
    total_rooms = await db.rooms.count_documents(
        {"property_id": property_id} if property_id and property_id != "all" else {})
    pct = round(rn24 * 100 / (total_rooms * 30), 1) if total_rooms else 0
    if pct >= 5 and rooms24 > prev24:
        r = await send_expo_push(db, "Güçlü satış günü 🔥",
                                 f"Son 24 saatte {rooms24} oda satıldı (+{rooms24 - prev24})",
                                 {"type": "pickup_strong"}, kind="pickup_strong")
        sent.append({"kind": "pickup_strong", **r})
    # Kanal düşüşü (bu hafta vs geçen hafta)
    cut7 = (now - timedelta(days=7)).isoformat()
    cut14 = (now - timedelta(days=14)).isoformat()
    ch_cur, ch_prev = {}, {}
    async for r in db.bookings.aggregate([
            {"$match": {**q, "created_at": {"$gte": cut14, "$lte": now.isoformat()}}},
            {"$group": {"_id": {"src": "$source",
                                "wk": {"$cond": [{"$gte": ["$created_at", cut7]}, "cur", "prev"]}},
                        "rooms": {"$sum": {"$ifNull": ["$rooms", 1]}}}}]):
        src = r["_id"].get("src") or "Direct"
        if src.startswith("demo_seed"):
            continue
        (ch_cur if r["_id"]["wk"] == "cur" else ch_prev)[src] = int(r["rooms"])
    for src, pn in ch_prev.items():
        cn = ch_cur.get(src, 0)
        if pn >= 5 and cn <= pn * 0.6:
            r = await send_expo_push(db, "Kanal pickup düşüşü ⚠️",
                                     f"{src}: bu hafta {cn} oda (geçen hafta {pn})",
                                     {"type": "channel_drop", "source": src}, kind="channel_drop")
            sent.append({"kind": "channel_drop", "source": src, **r})
    return {"ok": True, "pushes": sent}


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

    @router.post("/mobile/push-prefs")
    async def set_prefs(body: PushPrefsIn,
                        current_user: dict = Depends(require_perm("view_dashboard", "view_bookings", mode="any"))):
        await db.mobile_push_prefs.update_one(
            {"user_email": current_user.get("email", "")},
            {"$set": {"user_email": current_user.get("email", ""),
                      "prefs": body.model_dump(),
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        return {"status": "saved", "prefs": body.model_dump()}

    @router.get("/mobile/push-prefs")
    async def get_prefs(current_user: dict = Depends(require_perm("view_dashboard", "view_bookings", mode="any"))):
        doc = await db.mobile_push_prefs.find_one(
            {"user_email": current_user.get("email", "")}, {"_id": 0, "prefs": 1})
        return (doc or {}).get("prefs") or {"payment_received": True, "pickup_strong": True, "channel_drop": True}

    @router.post("/mobile/push-test")
    async def push_test(body: PushTestIn,
                        current_user: dict = Depends(require_perm("edit_bookings"))):
        return await send_expo_push(db, body.title, body.body, {"type": "test"})

    @router.get("/mobile/push-tokens")
    async def list_tokens(current_user: dict = Depends(require_perm("edit_bookings"))):
        return await db.mobile_push_tokens.find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)

    return router
