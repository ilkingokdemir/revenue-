"""Partner operasyonları: webhook teslimatı + üstel geri çekilmeli yeniden deneme, API anahtarı süre uyarısı."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)
now_iso = lambda: datetime.now(timezone.utc).isoformat()
BACKOFF_MIN = (1, 5, 30, 120, 720)  # dakika: 5 deneme → ~14 saat
MAX_ATTEMPTS = len(BACKOFF_MIN) + 1


async def _send(url: str, payload: dict, secret: str) -> tuple:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(url, json=payload, headers={"X-Webhook-Secret": secret, "X-Webhook-Event": payload["event"], "X-Webhook-Delivery": payload["id"]})
        return r.status_code < 300, r.status_code, r.text[:200]
    except Exception as e:
        return False, 0, str(e)[:200]


async def _record(db, sub: dict, payload: dict, pid: str, ok: bool, code: int, err: str, prev: dict = None):
    attempt = int((prev or {}).get("attempts") or 0) + 1
    doc = {"id": (prev or {}).get("id") or str(uuid.uuid4()), "subscription_id": sub.get("id"), "event": payload["event"], "url": sub["url"], "property_id": pid,
           "payload": payload, "attempts": attempt, "ok": ok, "status_code": code, "last_error": "" if ok else err, "at": now_iso()}
    if ok:
        doc.update({"status": "delivered", "delivered_at": now_iso(), "next_retry_at": None})
    elif attempt < MAX_ATTEMPTS:
        doc.update({"status": "retrying", "next_retry_at": (datetime.now(timezone.utc) + timedelta(minutes=BACKOFF_MIN[attempt - 1])).isoformat()})
    else:
        doc.update({"status": "failed", "next_retry_at": None})
    await db.webhook_deliveries.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
    return doc


async def emit_webhook(db, pid: str, event: str, data: dict):
    """Giden webhook: abone URL'lere event POST'lar; başarısızsa üstel geri çekilmeyle yeniden denenir."""
    subs = await db.webhook_subscriptions.find(
        {"property_id": {"$in": [pid, "*"]}, "active": {"$ne": False}, "$or": [{"events": event}, {"events": "*"}]}, {"_id": 0}).to_list(20)
    if not subs:
        return 0
    sent = 0
    for s in subs:
        payload = {"id": str(uuid.uuid4()), "event": event, "property_id": pid, "created_at": now_iso(), "data": data}
        ok, code, err = await _send(s["url"], payload, s.get("secret", ""))
        await _record(db, s, payload, pid, ok, code, err)
        sent += 1 if ok else 0
    return sent


async def retry_due_webhooks(db, limit: int = 50) -> int:
    due = await db.webhook_deliveries.find({"status": "retrying", "next_retry_at": {"$lte": now_iso()}}, {"_id": 0}).sort("next_retry_at", 1).to_list(limit)
    n = 0
    for d in due:
        sub = await db.webhook_subscriptions.find_one({"id": d.get("subscription_id")}, {"_id": 0}) or {"id": d.get("subscription_id"), "url": d["url"], "secret": ""}
        if sub.get("active") is False:
            await db.webhook_deliveries.update_one({"id": d["id"]}, {"$set": {"status": "failed", "last_error": "abonelik pasif", "next_retry_at": None}})
            continue
        ok, code, err = await _send(sub["url"], d["payload"], sub.get("secret", ""))
        await _record(db, sub, d["payload"], d["property_id"], ok, code, err, prev=d)
        n += 1 if ok else 0
    return n


async def retry_delivery_now(db, delivery_id: str) -> dict:
    d = await db.webhook_deliveries.find_one({"id": delivery_id}, {"_id": 0})
    if not d or not d.get("payload"):
        return {}
    sub = await db.webhook_subscriptions.find_one({"id": d.get("subscription_id")}, {"_id": 0}) or {"id": d.get("subscription_id"), "url": d["url"], "secret": ""}
    ok, code, err = await _send(sub["url"], d["payload"], sub.get("secret", ""))
    return await _record(db, sub, d["payload"], d["property_id"], ok, code, err, prev=d)


async def webhook_retry_loop(db, interval_seconds: int = 60):
    await asyncio.sleep(30)
    while True:
        try:
            n = await retry_due_webhooks(db)
            if n:
                logger.info(f"webhook_retry_loop: {n} teslimat kurtarıldı")
        except Exception as e:
            logger.warning(f"webhook_retry_loop error: {e}")
        await asyncio.sleep(interval_seconds)


async def check_api_key_expiry(db, warn_days: int = 7) -> dict:
    """Süresi yaklaşan/dolan public API anahtarları → bildirim + MOCK e-posta (anahtar başına 1 kez)."""
    from routes.platform_ext.mailer import send_email
    now = datetime.now(timezone.utc)
    horizon = (now + timedelta(days=warn_days)).isoformat()
    warned = expired = 0
    async for k in db.public_api_keys.find({"active": {"$ne": False}, "expires_at": {"$nin": [None, ""], "$lte": horizon}}, {"_id": 0}):
        is_expired = k["expires_at"] <= now.isoformat()
        flag = "expired_notified" if is_expired else "expiry_warned"
        if k.get(flag):
            continue
        days_left = max(0, (datetime.fromisoformat(k["expires_at"]) - now).days)
        title = f"API anahtarı süresi doldu: {k.get('name')}" if is_expired else f"API anahtarı {days_left} gün içinde sona eriyor: {k.get('name')}"
        body = "Anahtar artık istekleri reddediyor; Süper Admin → Public API Anahtarları'ndan uzatın veya yenisini üretin." if is_expired else "Kesinti yaşamamak için süreyi uzatın ya da partneri yeni anahtara geçirin."
        await db.notifications.insert_one({"id": str(uuid.uuid4()), "property_id": k["property_id"], "type": "api_key_expiry", "title": title, "body": body, "read": False, "created_at": now_iso()})
        admins = await db.users.find({"role": {"$in": ["admin", "manager"]}}, {"_id": 0, "email": 1}).to_list(20)
        for a in admins[:5]:
            await send_email(db, a["email"], title, f"<div style='font-family:system-ui'><b>{title}</b><p>{body}</p><p>Anahtar: {k['key'][:12]}••• · Tesis: {k['property_id']}</p></div>", kind="api_key_expiry", meta={"key_id": k["id"]})
        await db.public_api_keys.update_one({"id": k["id"]}, {"$set": {flag: True, f"{flag}_at": now_iso()}})
        expired += is_expired; warned += not is_expired
    return {"warned": warned, "expired": expired}


async def api_key_expiry_loop(db, interval_seconds: int = 21600):
    await asyncio.sleep(90)
    while True:
        try:
            r = await check_api_key_expiry(db)
            if r["warned"] or r["expired"]:
                logger.info(f"api_key_expiry_loop: {r}")
        except Exception as e:
            logger.warning(f"api_key_expiry_loop error: {e}")
        await asyncio.sleep(interval_seconds)
