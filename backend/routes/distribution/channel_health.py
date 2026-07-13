"""
Channel Health Center + OTA Sync Watchdog (iter 420) — per-channel sync health
(success rate, staleness, dead letters) with an autopilot that auto-requeues
dead-lettered pushes and raises alerts for stale/failing channels.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import logging
import uuid
import httpx

from routes.platform_ext.automation_settings import get_params

logger = logging.getLogger(__name__)

CHANNEL_LABELS = {
    "booking_com": "Booking.com", "airbnb": "Airbnb", "expedia": "Expedia",
    "agoda": "Agoda", "hotels_com": "Hotels.com", "trip_com": "Trip.com",
    "google_hotels": "Google Hotels", "trivago": "Trivago", "direct": "Direct",
}
MAX_AUTO_REQUEUE_PER_TASK = 2


def create_channel_health_router(db, require_roles):
    router = APIRouter()

    async def _notify_alert(msg: str):
        """In-app notification + optional Slack-compatible webhook."""
        now = datetime.now(timezone.utc).isoformat()
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "warning",
            "title": "OTA Senkron Uyarısı", "message": msg,
            "category": "ota_sync", "target_user": "", "target_role": "manager",
            "link_to": "channel-health", "priority": "high",
            "read": False, "created_by": "OTA Watchdog", "created_at": now})
        cfg = await db.alert_webhook_config.find_one({"scope": "ota_sync"}, {"_id": 0}) or {}
        url = (cfg.get("webhook_url") or "").strip()
        if url:
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    resp = await client.post(url, json={"text": f"🚨 OTA Senkron Uyarısı: {msg}"})
                await db.alert_webhook_config.update_one(
                    {"scope": "ota_sync"},
                    {"$set": {"last_delivery_at": now, "last_delivery_status": resp.status_code}})
            except Exception as e:
                logger.warning(f"OTA alert webhook failed: {e}")
                await db.alert_webhook_config.update_one(
                    {"scope": "ota_sync"},
                    {"$set": {"last_delivery_at": now, "last_delivery_status": f"error: {e}"}})

    async def _channel_stats(pq: Dict, stale_hours: int):
        now = datetime.now(timezone.utc)
        day_ago = (now - timedelta(hours=24)).isoformat()
        conns = await db.channel_connections.find(
            {**pq, "channel_id": {"$ne": "direct"}}, {"_id": 0, "channel_id": 1}).to_list(50)
        channel_ids = sorted({c["channel_id"] for c in conns})
        rows = []
        for ch in channel_ids:
            cq = {**pq, "channel_id": ch}
            total_24h = await db.sync_queue.count_documents({**cq, "created_at": {"$gte": day_ago}})
            ok_24h = await db.sync_queue.count_documents(
                {**cq, "status": "succeeded", "created_at": {"$gte": day_ago}})
            pending = await db.sync_queue.count_documents({**cq, "status": "pending"})
            dead = await db.sync_queue.count_documents({**cq, "status": "dead_letter"})
            last_ok = await db.sync_queue.find_one(
                {**cq, "status": "succeeded"}, {"_id": 0, "completed_at": 1},
                sort=[("completed_at", -1)])
            ever = await db.sync_queue.count_documents(cq)
            last_success = (last_ok or {}).get("completed_at")
            stale_h = None
            if last_success:
                try:
                    stale_h = round((now - datetime.fromisoformat(last_success)).total_seconds() / 3600, 1)
                except ValueError:
                    stale_h = None
            success_rate = round(ok_24h / total_24h * 100, 1) if total_24h else None
            if ever == 0:
                status = "no_data"
            elif dead > 0 or (stale_h is not None and stale_h > stale_hours):
                status = "critical"
            elif (success_rate is not None and success_rate < 80) or pending > 20:
                status = "warning"
            else:
                status = "healthy"
            rows.append({"channel": ch, "label": CHANNEL_LABELS.get(ch, ch),
                         "total_24h": total_24h, "succeeded_24h": ok_24h,
                         "success_rate": success_rate, "pending": pending,
                         "dead_letter": dead, "last_success": last_success,
                         "staleness_hours": stale_h, "status": status})
        return rows

    async def _watchdog_core(property_id: str = "") -> dict:
        cfg = await get_params(db, "ota_sync_watchdog", {"stale_hours": 24, "max_requeue": 10})
        stale_hours = int(cfg["stale_hours"])
        max_requeue = int(cfg["max_requeue"])
        pq: Dict = {} if not property_id or property_id == "all" else {"property_id": property_id}
        now = datetime.now(timezone.utc).isoformat()

        # 1. auto-heal: requeue dead letters (bounded per task and per run)
        dead_tasks = await db.sync_queue.find(
            {**pq, "status": "dead_letter",
             "$or": [{"requeue_count": {"$exists": False}},
                     {"requeue_count": {"$lt": MAX_AUTO_REQUEUE_PER_TASK}}]},
            {"_id": 0, "id": 1}).to_list(max_requeue)
        requeued = 0
        for t in dead_tasks:
            await db.sync_queue.update_one(
                {"id": t["id"]},
                {"$set": {"status": "pending", "attempts": 0, "error": None,
                          "next_retry_at": now, "auto_requeued_at": now},
                 "$inc": {"requeue_count": 1}})
            requeued += 1

        # 2. per-channel status + alerts
        rows = await _channel_stats(pq, stale_hours)
        alerts_opened, alerts_resolved = 0, 0
        for r in rows:
            ch = r["channel"]
            problems = []
            if r["status"] == "critical":
                if r["dead_letter"] > 0:
                    problems.append(("dead_letter",
                                     f"{r['label']}: {r['dead_letter']} güncelleme kalıcı olarak başarısız (dead-letter)"))
                if r["staleness_hours"] is not None and r["staleness_hours"] > stale_hours:
                    problems.append(("stale",
                                     f"{r['label']}: {r['staleness_hours']} saattir başarılı senkron yok (eşik {stale_hours}s)"))
            for ptype, msg in problems:
                res = await db.ota_sync_alerts.update_one(
                    {"channel": ch, "type": ptype, "status": "open"},
                    {"$set": {"channel": ch, "type": ptype, "status": "open",
                              "message": msg, "updated_at": now},
                     "$setOnInsert": {"created_at": now}},
                    upsert=True)
                if res.upserted_id:
                    alerts_opened += 1
                    await _notify_alert(msg)
            if not problems:
                res = await db.ota_sync_alerts.update_many(
                    {"channel": ch, "status": "open"},
                    {"$set": {"status": "resolved", "resolved_at": now}})
                alerts_resolved += res.modified_count

        open_alerts = await db.ota_sync_alerts.count_documents({"status": "open"})
        critical = sum(1 for r in rows if r["status"] == "critical")
        return {"ok": True, "channels_checked": len(rows), "requeued": requeued,
                "critical_channels": critical, "alerts_opened": alerts_opened,
                "alerts_resolved": alerts_resolved, "open_alerts": open_alerts}

    @router.get("/channel-health/{property_id}")
    async def channel_health(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await get_params(db, "ota_sync_watchdog", {"stale_hours": 24, "max_requeue": 10})
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}
        rows = await _channel_stats(pq, int(cfg["stale_hours"]))
        alerts = await db.ota_sync_alerts.find(
            {"status": "open"}, {"_id": 0}).sort("updated_at", -1).to_list(50)
        dead = await db.sync_queue.find(
            {**pq, "status": "dead_letter"}, {"_id": 0}).sort("dead_lettered_at", -1).to_list(20)
        summary = {"healthy": 0, "warning": 0, "critical": 0, "no_data": 0}
        for r in rows:
            summary[r["status"]] += 1
        return {"property_id": property_id, "channels": rows, "summary": summary,
                "alerts": alerts, "dead_letters": dead,
                "stale_hours": int(cfg["stale_hours"])}

    @router.post("/channel-health/heal")
    async def heal_now(data: Dict = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _watchdog_core((data or {}).get("property_id", ""))

    @router.get("/channel-health/webhook-config/get")
    async def get_webhook_config(current_user: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.alert_webhook_config.find_one({"scope": "ota_sync"}, {"_id": 0}) or {}
        return {"webhook_url": cfg.get("webhook_url", ""),
                "last_delivery_at": cfg.get("last_delivery_at"),
                "last_delivery_status": cfg.get("last_delivery_status")}

    @router.put("/channel-health/webhook-config")
    async def set_webhook_config(data: Dict,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        url = (data.get("webhook_url") or "").strip()
        await db.alert_webhook_config.update_one(
            {"scope": "ota_sync"},
            {"$set": {"scope": "ota_sync", "webhook_url": url,
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("name", "")}},
            upsert=True)
        return {"ok": True}

    @router.post("/channel-health/webhook-test")
    async def test_webhook(current_user: dict = Depends(require_roles("admin", "manager"))):
        await _notify_alert("Test uyarısı — Kanal Sağlık Merkezi anlık bildirim yapılandırması çalışıyor ✓")
        cfg = await db.alert_webhook_config.find_one({"scope": "ota_sync"}, {"_id": 0}) or {}
        return {"ok": True, "webhook_configured": bool(cfg.get("webhook_url")),
                "last_delivery_status": cfg.get("last_delivery_status")}

    router.run_watchdog_internal = _watchdog_core
    return router
