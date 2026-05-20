"""
Channel Sync Queue with Exponential Backoff (Iter 162)

Every push to an OTA (rate, availability, restriction) is enqueued here instead
of calling the OTA directly. A background worker (wired via the scheduler
engine) picks up `status=pending` items whose `next_retry_at` has passed, runs
them, and either marks `succeeded` or reschedules with exponential backoff.

Backoff schedule (attempts → wait):
  0: immediate
  1: 1 minute
  2: 5 minutes
  3: 15 minutes
  4: 1 hour
  5: 4 hours
  6 (dead letter): manual re-queue or clear

The actual OTA push is MOCKED here (same as existing channel_manager.py).
When real partner credentials arrive, swap the `_execute_task` implementation.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import random
import logging

logger = logging.getLogger(__name__)

BACKOFF_MINUTES = [0, 1, 5, 15, 60, 240]  # idx == attempt number
MAX_ATTEMPTS = len(BACKOFF_MINUTES)


def _next_retry_time(attempts: int) -> str:
    if attempts >= MAX_ATTEMPTS:
        return ""  # dead letter
    wait = BACKOFF_MINUTES[attempts]
    return (datetime.now(timezone.utc) + timedelta(minutes=wait)).isoformat()


async def _execute_task(db, task: Dict) -> Dict:
    """MOCK OTA push. Simulates a realistic 90% success rate, 10% transient fail."""
    # In production: replace with real OTA API call here based on task['channel_id'].
    await _async_sleep(0.1)
    if random.random() < 0.9:
        return {"ok": True, "ota_ref": f"OTA-{uuid.uuid4().hex[:8].upper()}"}
    return {"ok": False, "error": "OTA temporary 503 (mocked)"}


async def _async_sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)


def create_sync_queue_router(db, require_roles):
    router = APIRouter()

    @router.get("/sync-queue/{property_id}")
    async def list_queue(property_id: str, status: str = "", limit: int = 200,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.sync_queue.find(q, {"_id": 0}).sort("created_at", -1).to_list(int(limit))

        # counts
        all_rows = await db.sync_queue.find(
            {} if property_id == "all" else {"property_id": property_id},
            {"_id": 0, "status": 1},
        ).to_list(10000)
        counts = {"pending": 0, "processing": 0, "succeeded": 0, "failed": 0, "dead_letter": 0}
        for r in all_rows:
            counts[r.get("status", "pending")] = counts.get(r.get("status", "pending"), 0) + 1
        return {"rows": rows, "counts": counts, "total": len(all_rows)}

    @router.post("/sync-queue/{property_id}/enqueue")
    async def enqueue(property_id: str, data: Dict,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Body: {channel_id, kind: rate|avail|restriction, payload: {...}}"""
        if data.get("kind") not in ("rate", "avail", "restriction"):
            raise HTTPException(400, "kind must be rate|avail|restriction")
        task = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "channel_id": data.get("channel_id"),
            "kind": data["kind"],
            "payload": data.get("payload") or {},
            "status": "pending",
            "attempts": 0,
            "max_attempts": MAX_ATTEMPTS,
            "next_retry_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
            "result": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.sync_queue.insert_one(task)
        task.pop("_id", None)
        return task

    @router.post("/sync-queue/{task_id}/retry")
    async def retry_now(task_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """Manual re-queue (useful for dead-lettered items)."""
        task = await db.sync_queue.find_one({"id": task_id}, {"_id": 0})
        if not task:
            raise HTTPException(404, "Not found")
        await db.sync_queue.update_one(
            {"id": task_id},
            {"$set": {
                "status": "pending",
                "attempts": 0,
                "next_retry_at": datetime.now(timezone.utc).isoformat(),
                "error": None,
                "retried_at": datetime.now(timezone.utc).isoformat(),
                "retried_by": current_user.get("name", ""),
            }},
        )
        return {"status": "requeued"}

    @router.post("/sync-queue/{property_id}/clear-dead-letter")
    async def clear_dead(property_id: str,
                         current_user: dict = Depends(require_roles("admin"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        q["status"] = "dead_letter"
        res = await db.sync_queue.delete_many(q)
        return {"deleted": res.deleted_count}

    @router.post("/sync-queue/run-tick")
    async def run_tick(current_user: dict = Depends(require_roles("admin"))):
        """Manual invocation of the worker — processes up to 20 due tasks now."""
        return await process_due_tasks(db, max_tasks=20)

    return router


async def process_due_tasks(db, max_tasks: int = 20) -> Dict:
    """Worker body. Call me from the scheduler every minute."""
    now = datetime.now(timezone.utc).isoformat()
    due = await db.sync_queue.find({
        "status": "pending",
        "next_retry_at": {"$lte": now},
    }, {"_id": 0}).sort("next_retry_at", 1).to_list(max_tasks)
    processed = succeeded = failed = dead = 0

    for task in due:
        await db.sync_queue.update_one(
            {"id": task["id"]},
            {"$set": {"status": "processing", "processing_started_at": now}},
        )
        try:
            result = await _execute_task(db, task)
        except Exception as e:
            result = {"ok": False, "error": str(e)}

        attempts_new = task.get("attempts", 0) + 1
        if result.get("ok"):
            await db.sync_queue.update_one(
                {"id": task["id"]},
                {"$set": {
                    "status": "succeeded", "attempts": attempts_new,
                    "result": result, "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": None,
                }},
            )
            succeeded += 1
        else:
            if attempts_new >= MAX_ATTEMPTS:
                await db.sync_queue.update_one(
                    {"id": task["id"]},
                    {"$set": {
                        "status": "dead_letter", "attempts": attempts_new,
                        "error": result.get("error", "unknown"),
                        "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                dead += 1
            else:
                await db.sync_queue.update_one(
                    {"id": task["id"]},
                    {"$set": {
                        "status": "pending", "attempts": attempts_new,
                        "error": result.get("error", "unknown"),
                        "next_retry_at": _next_retry_time(attempts_new),
                    }},
                )
                failed += 1
        processed += 1
    return {
        "processed": processed,
        "succeeded": succeeded,
        "rescheduled": failed,
        "dead_lettered": dead,
    }
