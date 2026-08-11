"""Background tick workers moved out of server.py (ROADMAP P1)."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_TASK_DONE = {"done", "completed", "closed", "resolved"}


async def complaint_sla_loop(db, interval_seconds: int = 300):
    """Yanıt süresi hedefi (SLA) aşılan şikayetlerde yöneticiyi uyar."""
    while True:
        try:
            cfgs = {}
            async for c in db.review_agent_config.find(
                    {}, {"_id": 0, "property_id": 1, "sla_minutes": 1}):
                cfgs[c["property_id"]] = int(c.get("sla_minutes", 60))
            now = datetime.now(timezone.utc)
            open_c = await db.guest_complaints.find(
                {"status": {"$nin": ["resolved", "closed"]},
                 "sla_alerted": {"$ne": True},
                 "$or": [{"guest_response_text": {"$exists": False}},
                         {"guest_response_text": ""}]},
                {"_id": 0, "id": 1, "property_id": 1, "guest_name": 1,
                 "created_at": 1, "category": 1}).to_list(300)
            breached = 0
            for c in open_c:
                sla = cfgs.get(c.get("property_id"), 60)
                try:
                    dt = datetime.fromisoformat((c.get("created_at") or "").replace("Z", "+00:00"))
                except Exception:
                    continue
                if (now - dt).total_seconds() / 60 > sla:
                    await db.guest_complaints.update_one(
                        {"id": c["id"]},
                        {"$set": {"sla_breached": True, "sla_alerted": True,
                                  "sla_alerted_at": now.isoformat()}})
                    try:
                        from routes.platform_ext.mobile_push import send_expo_push
                        await send_expo_push(
                            db, "⏰ Yanıt süresi aşıldı",
                            f"{c.get('guest_name') or 'Misafir'} şikayeti {sla} dk içinde yanıtlanmadı ({c.get('category', '')})",
                            {"type": "sla_breach", "id": c["id"]}, kind="sla_breach")
                    except Exception:
                        pass
                    breached += 1
            if breached:
                logger.info(f"complaint_sla: {breached} SLA breach alerted")
        except Exception as e:
            logger.warning(f"complaint_sla error: {e}")
        await asyncio.sleep(interval_seconds)


async def complaint_task_sync_loop(db, interval_seconds: int = 300):
    """Şikayetten oluşan departman görevi kapanınca şikayeti otomatik çözüldü yap."""
    while True:
        try:
            open_complaints = await db.guest_complaints.find(
                {"routed_task_id": {"$exists": True, "$ne": ""},
                 "status": {"$nin": ["resolved", "closed"]}},
                {"_id": 0, "id": 1, "routed_task_id": 1, "routed_collection": 1,
                 "routed_department": 1}).to_list(300)
            resolved = 0
            for c in open_complaints:
                coll = getattr(db, c.get("routed_collection") or "staff_tasks", None)
                if coll is None:
                    continue
                task = await coll.find_one({"id": c["routed_task_id"]}, {"_id": 0, "status": 1})
                if task and (task.get("status") or "").lower() in _TASK_DONE:
                    now = datetime.now(timezone.utc).isoformat()
                    await db.guest_complaints.update_one(
                        {"id": c["id"]},
                        {"$set": {"status": "resolved", "resolved_at": now,
                                  "resolved_by": f"auto ({c.get('routed_department', 'departman')} görevi tamamlandı)",
                                  "resolution_notes": "Departman görevi kapatıldığı için otomatik çözüldü."}})
                    resolved += 1
            if resolved:
                logger.info(f"complaint_task_sync: auto-resolved {resolved} complaints")
        except Exception as e:
            logger.warning(f"complaint_task_sync error: {e}")
        await asyncio.sleep(interval_seconds)


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


async def revenue_brain_loop(db, interval_seconds: int = 21600):
    """Revenue Brain öğrenme döngüsü — 20 saatte bir sonuç ölç + ağırlık öğren + ders üret."""
    import logging
    logger = logging.getLogger(__name__)
    while True:
        try:
            from routes.revenue_ext.revenue_brain import run_learning_cycle
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
            props = await db.properties.find(
                {"is_active": {"$ne": False}}, {"_id": 0, "id": 1}).to_list(50)
            for p in props:
                state = await db.revenue_brain_state.find_one(
                    {"property_id": p["id"]}, {"_id": 0, "last_cycle_at": 1})
                if state and (state.get("last_cycle_at") or "") > cutoff:
                    continue
                res = await run_learning_cycle(db, p["id"])
                logger.info(f"revenue_brain_loop: {p['id']} → {res}")
        except Exception as e:
            logger.warning(f"revenue_brain_loop error: {e}")
        await asyncio.sleep(interval_seconds)


async def onboarding_drip_loop(db, interval_seconds: int = 1800):
    """İlk 7 Gün aktivasyon e-posta serisi — 30 dk'da bir süresi gelenleri gönderir."""
    import logging
    logger = logging.getLogger(__name__)
    while True:
        try:
            from routes.platform_ext.onboarding_drip import process_due_drips
            res = await process_due_drips(db)
            if res.get("sent"):
                logger.info(f"onboarding_drip_loop: {res}")
        except Exception as e:
            logger.warning(f"onboarding_drip_loop error: {e}")
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
