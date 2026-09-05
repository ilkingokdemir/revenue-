import uuid
import os
"""
Lightweight Scheduler (Iter 159) — async periodic background tasks.
No third-party deps (no APScheduler). A single asyncio task started at FastAPI
startup polls every 60s and runs any enabled nightly job whose cron time has
passed and hasn't run yet today.

Currently supports:
- auto_deposit_capture — runs the Deposit Automation batch against all bookings
  matching active policies that have cards on file.

Future jobs slot into the same model by adding a handler to JOB_HANDLERS.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Callable, Awaitable
import asyncio
import logging

logger = logging.getLogger(__name__)


def create_scheduler_router(db, require_roles, job_handlers: Dict[str, Callable[[str], Awaitable[dict]]]):
    router = APIRouter()

    @router.get("/scheduler/config")
    async def list_configs(property_id: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id} if property_id else {}
        rows = await db.scheduler_config.find(q, {"_id": 0}).sort("property_id", 1).to_list(500)
        return rows

    @router.put("/scheduler/config/{property_id}/{job}")
    async def update_config(property_id: str, job: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Body: {enabled: bool, cron_hour: 0-23, cron_minute: 0-59,
        cron_dow?: 0-6|null  (0=Monday, 6=Sunday; null/missing = every day),
        notes?}"""
        if job not in job_handlers:
            raise HTTPException(status_code=400, detail=f"Unknown job: {job}")
        hour = int(data.get("cron_hour", 2))
        minute = int(data.get("cron_minute", 0))
        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            raise HTTPException(status_code=400, detail="cron_hour 0-23, cron_minute 0-59")
        cron_dow = data.get("cron_dow")
        if cron_dow is not None:
            cron_dow = int(cron_dow)
            if not (0 <= cron_dow <= 6):
                raise HTTPException(status_code=400, detail="cron_dow 0-6 (0=Mon, 6=Sun)")

        await db.scheduler_config.update_one(
            {"property_id": property_id, "job": job},
            {"$set": {
                "property_id": property_id,
                "job": job,
                "enabled": bool(data.get("enabled", False)),
                "cron_hour": hour,
                "cron_minute": minute,
                "cron_dow": cron_dow,
                "notes": (data.get("notes") or "").strip(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_user.get("name", ""),
            }},
            upsert=True,
        )
        return await db.scheduler_config.find_one({"property_id": property_id, "job": job}, {"_id": 0})

    @router.get("/scheduler/history")
    async def history(property_id: str = "", limit: int = 50,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id} if property_id else {}
        rows = await db.scheduler_history.find(q, {"_id": 0}).sort("ran_at", -1).to_list(int(limit))
        return rows

    @router.get("/scheduler/queue")
    async def queue_status(property_id: str = "", limit: int = 30, status: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if property_id: q["property_id"] = property_id
        if status: q["status"] = status
        counts = {}
        async for row in db.job_queue.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            counts[row["_id"]] = row["n"]
        items = await db.job_queue.find(q, {"_id": 0, "history": 0}).sort("created_at", -1).to_list(int(limit))
        for it in items:
            if isinstance(it.get("finished_at"), datetime): it["finished_at"] = it["finished_at"].isoformat()
        return {"counts": counts, "items": items, "concurrency": int(os.environ.get("JOB_QUEUE_CONCURRENCY", "3"))}

    @router.post("/scheduler/queue/{queue_id}/retry")
    async def queue_retry(queue_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.job_queue.update_one({"id": queue_id, "status": {"$in": ["failed", "failed_soft", "done"]}},
                                          {"$set": {"status": "queued", "run_after": datetime.now(timezone.utc).isoformat(), "attempts": 0}, "$unset": {"finished_at": ""}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Queue item not found or still running")
        return {"ok": True}

    @router.post("/scheduler/trigger/{property_id}/{job}")
    async def manual_trigger(property_id: str, job: str, background: bool = False,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Run a scheduled job right now. background=true → kuyruğa al (retry/backoff ile)."""
        if job not in job_handlers:
            raise HTTPException(status_code=400, detail=f"Unknown job: {job}")
        if background:
            q = await enqueue_job(db, job, property_id, priority=8, source=f"manual:{current_user.get('name', '')}")
            return {"status": "queued", "queue_id": q["id"], "deduped": q.get("deduped", False)}
        result = await job_handlers[job](property_id)
        await db.scheduler_history.insert_one({
            "property_id": property_id, "job": job, "trigger": "manual",
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "ran_by": current_user.get("name", ""),
            "result": result,
        })
        return {"status": "triggered", "result": result}

    return router


# ==================== Kalıcı iş kuyruğu (retry + backoff, atomik claim) ====================
QUEUE_MAX_ATTEMPTS = 3
QUEUE_BACKOFF_SEC = (30, 120, 600)


async def enqueue_job(db, job: str, property_id: str = "", payload: Optional[dict] = None,
                      priority: int = 5, source: str = "api", dedupe: bool = True) -> dict:
    """Kuyruğa iş ekle. dedupe=True → aynı job+property için bekleyen kayıt varsa onu döndürür."""
    now = datetime.now(timezone.utc).isoformat()
    if dedupe:
        ex = await db.job_queue.find_one({"job": job, "property_id": property_id, "status": {"$in": ["queued", "running"]}}, {"_id": 0})
        if ex:
            return {**ex, "deduped": True}
    doc = {"id": str(uuid.uuid4()), "job": job, "property_id": property_id, "payload": payload or {}, "priority": int(priority),
           "status": "queued", "attempts": 0, "max_attempts": QUEUE_MAX_ATTEMPTS, "source": source,
           "run_after": now, "created_at": now, "history": []}
    await db.job_queue.insert_one(dict(doc))
    return doc


async def _claim_next(db):
    now = datetime.now(timezone.utc).isoformat()
    return await db.job_queue.find_one_and_update(
        {"status": "queued", "run_after": {"$lte": now}},
        {"$set": {"status": "running", "started_at": now}, "$inc": {"attempts": 1}},
        sort=[("priority", -1), ("run_after", 1)], projection={"_id": 0})


async def _run_queued(db, item: dict, job_handlers):
    now = datetime.now(timezone.utc)
    handler = job_handlers.get(item["job"])
    t0 = now.timestamp()
    try:
        if not handler:
            raise RuntimeError(f"Unknown job: {item['job']}")
        result = await asyncio.wait_for(handler(item.get("property_id", "")), timeout=float(os.environ.get("JOB_TIMEOUT_SEC", "900")))
        ok = not (isinstance(result, dict) and result.get("ok") is False)
        dur = round(datetime.now(timezone.utc).timestamp() - t0, 2)
        await db.job_queue.update_one({"id": item["id"]}, {
            "$set": {"status": "done" if ok else "failed_soft", "result": result, "duration_sec": dur, "finished_at": datetime.now(timezone.utc)},
            "$push": {"history": {"attempt": item["attempts"], "ok": ok, "duration_sec": dur, "at": now.isoformat()}}})
        await db.scheduler_history.insert_one({"property_id": item.get("property_id", ""), "job": item["job"], "trigger": f"queue:{item.get('source', 'api')}",
                                               "ran_at": now.isoformat(), "result": result, "duration_sec": dur, "queue_id": item["id"]})
    except Exception as e:
        dur = round(datetime.now(timezone.utc).timestamp() - t0, 2)
        attempt = item["attempts"]
        retry = attempt < item.get("max_attempts", QUEUE_MAX_ATTEMPTS)
        back = QUEUE_BACKOFF_SEC[min(attempt - 1, len(QUEUE_BACKOFF_SEC) - 1)]
        upd = {"status": "queued" if retry else "failed", "last_error": str(e)[:300], "duration_sec": dur}
        if retry:
            upd["run_after"] = (datetime.now(timezone.utc) + timedelta(seconds=back)).isoformat()
        else:
            upd["finished_at"] = datetime.now(timezone.utc)
        await db.job_queue.update_one({"id": item["id"]}, {"$set": upd, "$push": {"history": {"attempt": attempt, "ok": False, "error": str(e)[:200], "at": now.isoformat(), "retry_in_sec": back if retry else None}}})
        logger.warning(f"queue job {item['job']} attempt {attempt} failed: {e} (retry={retry})")
        await db.scheduler_history.insert_one({"property_id": item.get("property_id", ""), "job": item["job"], "trigger": f"queue:{item.get('source', 'api')}",
                                               "ran_at": now.isoformat(), "error": str(e)[:300], "attempt": attempt, "queue_id": item["id"]})


async def queue_worker_loop(db, job_handlers, concurrency: int = 3, poll_sec: float = 3.0):
    """Kuyruk işçisi: en fazla `concurrency` eşzamanlı iş; boşta poll_sec bekler."""
    running: set = set()
    logger.info(f"🧵 Job queue worker started (concurrency={concurrency})")
    # restart sonrası askıda kalan 'running' kayıtları geri kuyruğa al
    await db.job_queue.update_many({"status": "running"}, {"$set": {"status": "queued", "run_after": datetime.now(timezone.utc).isoformat()}})
    while True:
        try:
            running = {t for t in running if not t.done()}
            picked = False
            while len(running) < concurrency:
                item = await _claim_next(db)
                if not item:
                    break
                picked = True
                running.add(asyncio.create_task(_run_queued(db, item, job_handlers)))
            if not picked:
                await asyncio.sleep(poll_sec)
            else:
                await asyncio.sleep(0.2)
        except Exception as e:
            logger.exception(f"queue worker error: {e}")
            await asyncio.sleep(poll_sec)


async def scheduler_loop(db, job_handlers: Dict[str, Callable[[str], Awaitable[dict]]]):
    """Runs forever in background. Checks every 60s for due jobs."""
    logger.info("🕐 Scheduler loop started")
    while True:
        try:
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            configs = await db.scheduler_config.find({"enabled": True}, {"_id": 0}).to_list(500)
            for cfg in configs:
                job = cfg.get("job")
                if job not in job_handlers:
                    continue
                # Day-of-week gate (weekly cron). None/missing → every day.
                cron_dow = cfg.get("cron_dow")
                if cron_dow is not None and int(cron_dow) != now.weekday():
                    continue
                cron_time = cfg.get("cron_hour", 2) * 60 + cfg.get("cron_minute", 0)
                now_mins = now.hour * 60 + now.minute
                # Only trigger if we've passed the cron time AND haven't run today
                if now_mins < cron_time:
                    continue
                if cfg.get("last_run_date") == today:
                    continue

                logger.info(f"⏰ Enqueue scheduled job {job} for {cfg.get('property_id')}")
                try:
                    q = await enqueue_job(db, job, cfg["property_id"], priority=5, source="scheduled")
                    await db.scheduler_config.update_one(
                        {"property_id": cfg["property_id"], "job": job},
                        {"$set": {"last_run_date": today, "last_run_at": now.isoformat(),
                                  "last_run_result": {"queued": True, "queue_id": q["id"]}}}
                    )
                except Exception as e:
                    logger.exception(f"Scheduled job {job} failed: {e}")
                    await db.scheduler_history.insert_one({
                        "property_id": cfg["property_id"], "job": job, "trigger": "scheduled",
                        "ran_at": now.isoformat(), "error": str(e),
                    })
        except Exception as e:
            logger.exception(f"Scheduler loop error: {e}")
        await asyncio.sleep(60)
