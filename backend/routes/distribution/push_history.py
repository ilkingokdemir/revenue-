"""
Channel Push History (iter 427) — timeline of rate/availability pushes per
channel with latency stats, plus a channel x date freshness matrix showing
when each future date was last pushed.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def _age_hours(iso: str) -> float:
    try:
        return round((datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 3600, 1)
    except (ValueError, TypeError):
        return None


async def resolve_rate(db, pid: str, target_date: str):
    """Rate resolution chain: last push -> monthly ADR -> 90d booking ADR -> default."""
    last = await db.sync_queue.find_one(
        {"property_id": pid, "kind": "rate", "status": "succeeded",
         "payload.date": target_date, "payload.rate": {"$gt": 0}},
        {"_id": 0, "payload": 1}, sort=[("completed_at", -1)])
    if last:
        return float(last["payload"]["rate"]), "son_push"
    monthly = await db.property_monthly_prices.find_one(
        {"property_id": pid, "month_key": target_date[:7]}, {"_id": 0, "adr": 1})
    if monthly and monthly.get("adr"):
        return float(monthly["adr"]), "aylik_adr"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    recent = await db.bookings.find(
        {"property_id": pid, "status": {"$nin": ["cancelled", "no_show"]},
         "created_at": {"$gte": cutoff}, "total_price": {"$gt": 0}},
        {"_id": 0, "total_price": 1, "nights": 1}).to_list(200)
    if recent:
        total = sum(float(b["total_price"]) for b in recent)
        nts = sum(max(int(b.get("nights") or 1), 1) for b in recent)
        return round(total / nts, 2), "son_90g_adr"
    return 100.0, "varsayilan"


def create_push_history_router(db, require_roles):
    router = APIRouter()

    @router.get("/push-history/{property_id}")
    async def push_history(property_id: str, channel: str = "all", days: int = 7,
                           limit: int = 100,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}
        if channel != "all":
            pq["channel_id"] = channel
        tasks = await db.sync_queue.find(
            {**pq, "created_at": {"$gte": cutoff}},
            {"_id": 0}).sort("created_at", -1).to_list(int(limit))
        timeline = []
        stats: Dict[str, Dict] = {}
        for t in tasks:
            ch = t.get("channel_id", "?")
            lat = None
            if t.get("completed_at") and t.get("created_at"):
                try:
                    lat = round((datetime.fromisoformat(t["completed_at"]) -
                                 datetime.fromisoformat(t["created_at"])).total_seconds(), 1)
                except ValueError:
                    pass
            payload = t.get("payload") or {}
            timeline.append({
                "id": t.get("id"), "channel": ch, "kind": t.get("kind"),
                "status": t.get("status"), "date": payload.get("date"),
                "rate": payload.get("rate"), "availability": payload.get("availability"),
                "attempts": t.get("attempts", 0), "error": t.get("error"),
                "created_at": t.get("created_at"), "completed_at": t.get("completed_at"),
                "latency_sec": lat,
            })
            s = stats.setdefault(ch, {"total": 0, "succeeded": 0, "failed": 0, "lat": []})
            s["total"] += 1
            if t.get("status") == "succeeded":
                s["succeeded"] += 1
                if lat is not None:
                    s["lat"].append(lat)
            elif t.get("status") in ("failed", "dead_letter"):
                s["failed"] += 1
        stat_rows = []
        for ch, s in sorted(stats.items()):
            stat_rows.append({
                "channel": ch, "total": s["total"], "succeeded": s["succeeded"],
                "failed": s["failed"],
                "avg_latency_sec": round(sum(s["lat"]) / len(s["lat"]), 1) if s["lat"] else None,
                "max_latency_sec": max(s["lat"]) if s["lat"] else None,
            })
        return {"property_id": property_id, "days": days,
                "timeline": timeline, "stats": stat_rows}

    @router.get("/push-history/{property_id}/freshness")
    async def freshness(property_id: str, days: int = 14,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}
        today = date.today()
        dates = [(today + timedelta(days=i)).isoformat() for i in range(int(days))]
        conns = await db.channel_connections.find(
            {**pq, "channel_id": {"$ne": "direct"}}, {"_id": 0, "channel_id": 1}).to_list(50)
        channels = sorted({c["channel_id"] for c in conns})
        pipeline = [
            {"$match": {**pq, "status": "succeeded",
                        "payload.date": {"$gte": dates[0], "$lte": dates[-1]}}},
            {"$group": {"_id": {"ch": "$channel_id", "d": "$payload.date"},
                        "last": {"$max": "$completed_at"}}},
        ]
        cells = {}
        async for r in db.sync_queue.aggregate(pipeline):
            cells[(r["_id"]["ch"], r["_id"]["d"])] = r["last"]
        matrix = []
        for ch in channels:
            row = {"channel": ch, "cells": []}
            for d in dates:
                last = cells.get((ch, d))
                row["cells"].append({"date": d, "last_pushed_at": last,
                                     "age_hours": _age_hours(last) if last else None})
            matrix.append(row)
        return {"property_id": property_id, "dates": dates, "matrix": matrix}

    @router.post("/push-history/{property_id}/push-now")
    async def push_now(property_id: str, data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        from routes.integrations_pkg.sync_queue import process_due_tasks
        import uuid
        channel = (data or {}).get("channel")
        target_date = (data or {}).get("date")
        if not channel or not target_date:
            raise HTTPException(status_code=400, detail="channel ve date zorunlu")
        pid = property_id
        if pid == "all":
            conn = await db.channel_connections.find_one(
                {"channel_id": channel}, {"_id": 0, "property_id": 1})
            pid = (conn or {}).get("property_id") or "aldgate-flats"

        rate, source = await resolve_rate(db, pid, target_date)

        now = datetime.now(timezone.utc).isoformat()
        task = {"id": str(uuid.uuid4()), "property_id": pid, "channel_id": channel,
                "kind": "rate", "payload": {"date": target_date, "rate": rate},
                "status": "pending", "attempts": 0, "max_attempts": 6,
                "next_retry_at": now, "error": None, "result": None,
                "created_at": now, "created_by": f"push-now:{current_user.get('name', '')}"}
        await db.sync_queue.insert_one(task)
        tick = await process_due_tasks(db, max_tasks=5)
        final = await db.sync_queue.find_one({"id": task["id"]}, {"_id": 0, "status": 1, "error": 1})
        return {"ok": final.get("status") == "succeeded", "task_id": task["id"],
                "channel": channel, "date": target_date, "rate": rate,
                "rate_source": source, "status": final.get("status"),
                "error": final.get("error"), "tick": tick}

    return router
