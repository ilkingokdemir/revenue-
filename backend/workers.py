"""Background tick workers moved out of server.py (ROADMAP P1)."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

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


async def otb_snapshot_loop(db, interval_seconds: int = 21600):
    """Günlük OTB snapshot arşivi — gerçek pickup/pace hesapları için (idempotent, günde 1)."""
    from datetime import timedelta
    while True:
        try:
            today = datetime.now(timezone.utc).date()
            scan_date = today.isoformat()
            exists = await db.otb_daily_snapshots.find_one({"scan_date": scan_date}, {"_id": 1})
            if not exists:
                props = await db.properties.find({}, {"_id": 0, "id": 1}).to_list(200)
                total_docs = 0
                for p in props:
                    pid = p.get("id")
                    if not pid:
                        continue
                    day_counts = {}
                    async for b in db.bookings.find(
                            {"property_id": pid, "status": {"$ne": "cancelled"},
                             "check_out": {"$gt": scan_date}},
                            {"_id": 0, "check_in": 1, "check_out": 1}):
                        try:
                            ci = datetime.strptime(b["check_in"][:10], "%Y-%m-%d").date()
                            co = datetime.strptime(b["check_out"][:10], "%Y-%m-%d").date()
                        except (ValueError, TypeError, KeyError):
                            continue
                        d = max(ci, today)
                        end = min(co, today + timedelta(days=90))
                        while d < end:
                            day_counts[d.isoformat()] = day_counts.get(d.isoformat(), 0) + 1
                            d += timedelta(days=1)
                    if day_counts:
                        docs = [{"property_id": pid, "scan_date": scan_date, "date": k,
                                 "rooms_booked": v, "created_at": datetime.now(timezone.utc).isoformat()}
                                for k, v in day_counts.items()]
                        await db.otb_daily_snapshots.insert_many(docs)
                        total_docs += len(docs)
                # 180 günden eski snapshot'ları temizle
                purge_before = (today - timedelta(days=180)).isoformat()
                await db.otb_daily_snapshots.delete_many({"scan_date": {"$lt": purge_before}})
                logger.info(f"OTB snapshot: {scan_date} için {total_docs} satır arşivlendi")
        except Exception as e:
            logger.warning(f"OTB snapshot tick error: {e}")
        await asyncio.sleep(interval_seconds)


async def str_scan_loop(db, interval_seconds: int = 3600):
    """Gece STR taraması — canlı Booking.com STR verisini 20 saatte bir tazeler."""
    import logging
    logger = logging.getLogger(__name__)
    while True:
        try:
            from routes.revenue_ext.str_market import run_str_scan
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
            props = await db.properties.find(
                {"is_active": {"$ne": False}, "latitude": {"$ne": None}},
                {"_id": 0, "id": 1}).to_list(50)
            for p in props:
                pid = p["id"]
                status = await db.str_scan_status.find_one({"property_id": pid}, {"_id": 0})
                if status and status.get("status") == "running":
                    continue
                if status and (status.get("finished_at") or "") > cutoff:
                    continue
                await db.str_scan_status.update_one(
                    {"property_id": pid},
                    {"$set": {"property_id": pid, "status": "running", "scanned": 0,
                              "live_ok": 0, "started_at": datetime.now(timezone.utc).isoformat(),
                              "finished_at": None, "started_by": "cron"}},
                    upsert=True)
                res = await run_str_scan(db, pid)
                logger.info(f"str_scan_loop: {pid} → {res}")
                await asyncio.sleep(10)
        except Exception as e:
            logger.warning(f"str_scan_loop error: {e}")
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
