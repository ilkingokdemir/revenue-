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
from datetime import datetime, timezone
from typing import Dict, Callable, Awaitable
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

    @router.post("/scheduler/trigger/{property_id}/{job}")
    async def manual_trigger(property_id: str, job: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Run a scheduled job right now (admin on-demand)."""
        if job not in job_handlers:
            raise HTTPException(status_code=400, detail=f"Unknown job: {job}")
        result = await job_handlers[job](property_id)
        await db.scheduler_history.insert_one({
            "property_id": property_id, "job": job, "trigger": "manual",
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "ran_by": current_user.get("name", ""),
            "result": result,
        })
        return {"status": "triggered", "result": result}

    return router


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

                logger.info(f"⏰ Running scheduled job {job} for {cfg.get('property_id')}")
                try:
                    result = await job_handlers[job](cfg["property_id"])
                    await db.scheduler_config.update_one(
                        {"property_id": cfg["property_id"], "job": job},
                        {"$set": {"last_run_date": today, "last_run_at": now.isoformat(),
                                  "last_run_result": result}}
                    )
                    await db.scheduler_history.insert_one({
                        "property_id": cfg["property_id"], "job": job, "trigger": "scheduled",
                        "ran_at": now.isoformat(), "result": result,
                    })
                except Exception as e:
                    logger.exception(f"Scheduled job {job} failed: {e}")
                    await db.scheduler_history.insert_one({
                        "property_id": cfg["property_id"], "job": job, "trigger": "scheduled",
                        "ran_at": now.isoformat(), "error": str(e),
                    })
        except Exception as e:
            logger.exception(f"Scheduler loop error: {e}")
        await asyncio.sleep(60)
