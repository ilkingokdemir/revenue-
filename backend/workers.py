"""Background tick workers moved out of server.py (ROADMAP P1)."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def scheduled_checkout_loop(db, interval_seconds: int = 300):
    while True:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            ripe = await db.scheduled_checkouts.find(
                {"status": "pending", "checkout_at": {"$lte": now_iso}}, {"_id": 0}
            ).to_list(200)
            for row in ripe:
                b = await db.bookings.find_one({"id": row["booking_id"]}, {"_id": 0, "status": 1})
                if b and (b.get("status") or "").lower() not in {"checked_out", "cancelled"}:
                    await db.bookings.update_one(
                        {"id": row["booking_id"]},
                        {"$set": {
                            "status": "checked_out",
                            "checked_out_at": now_iso,
                            "checkout_channel": "scheduled_self_service",
                        }},
                    )
                await db.scheduled_checkouts.update_one(
                    {"booking_id": row["booking_id"]},
                    {"$set": {"status": "done", "executed_at": now_iso, "updated_at": now_iso}},
                )
            if ripe:
                logger.info(f"Scheduled-checkout tick: flushed {len(ripe)} rows")
        except Exception as e:
            logger.warning(f"Scheduled-checkout tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def reports_loop(db, interval_seconds: int = 300):
    while True:
        try:
            from routes.platform_ext.scheduled_reports import GENERATORS as _GENS, _next_run as _nr
            now_iso = datetime.now(timezone.utc).isoformat()
            due = await db.report_subscriptions.find(
                {"enabled": True, "next_run_at": {"$lte": now_iso}}, {"_id": 0}
            ).to_list(100)
            for sub in due:
                gen = _GENS.get(sub["report_key"])
                if not gen:
                    continue
                try:
                    payload, mime = await gen(db, sub.get("filters") or {}, sub.get("property_id"))
                    snap = {
                        "id":              str(uuid.uuid4()),
                        "subscription_id": sub["id"],
                        "report_key":      sub["report_key"],
                        "property_id":     sub.get("property_id"),
                        "email":           sub.get("email"),
                        "payload":         payload,
                        "mime_type":       mime,
                        "size_bytes":      len(payload.encode("utf-8")),
                        "created_at":      now_iso,
                        "delivery_status": "mocked_email_sent",
                    }
                    await db.report_snapshots.insert_one(snap)
                    await db.report_subscriptions.update_one(
                        {"id": sub["id"]},
                        {"$set": {
                            "last_run_at":      now_iso,
                            "last_snapshot_id": snap["id"],
                            "next_run_at":      _nr(sub["frequency"]),
                        }},
                    )
                except Exception as e:
                    logger.warning(f"Report gen failed for sub {sub['id']}: {e}")
            if due:
                logger.info(f"Scheduled-reports tick: processed {len(due)} subs")
        except Exception as e:
            logger.warning(f"Reports tick error: {e}")
        await asyncio.sleep(interval_seconds)
