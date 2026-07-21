"""
Channel Push History (iter 427) — timeline of rate/availability pushes per
channel with latency stats, plus a channel x date freshness matrix showing
when each future date was last pushed.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta, date
from typing import Dict
import logging

logger = logging.getLogger(__name__)


def _age_hours(iso: str) -> float:
    try:
        return round((datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 3600, 1)
    except (ValueError, TypeError):
        return None


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

    return router
