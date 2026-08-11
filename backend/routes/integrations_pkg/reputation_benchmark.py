"""
Reputation Benchmark — rakip otellerin Google puanlarını takip et, kıyasla.

GOOGLE_PLACES_API_KEY varsa gerçek rating/userRatingCount; yoksa deterministik
SIMULATED değerler. Günlük snapshot → trend. GuestRevu paritesi (5 rakip).
"""
from datetime import datetime, timezone
import hashlib
import logging
import os
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

_BENCH = {}


async def run_reputation_scan(property_id: str = "all") -> dict:
    fn = _BENCH.get("fn")
    if not fn:
        return {"error": "reputation router not initialized"}
    return await fn(property_id)


def create_reputation_router(db, require_roles):
    router = APIRouter()

    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _sim_rating(name: str):
        h = int(hashlib.sha1(f"{name}{datetime.now().strftime('%Y-%W')}".encode()).hexdigest(), 16)
        return round(3.4 + (h % 140) / 100, 1), 150 + (h % 900)

    async def _fetch_rating(place_id: str, name: str):
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
        if api_key and place_id:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(
                        f"https://places.googleapis.com/v1/places/{place_id}",
                        headers={"X-Goog-Api-Key": api_key,
                                 "X-Goog-FieldMask": "rating,userRatingCount"})
                if r.status_code == 200:
                    d = r.json()
                    return d.get("rating"), d.get("userRatingCount"), "live"
            except Exception as e:
                logger.warning(f"places rating fetch failed: {e}")
        rating, count = _sim_rating(name)
        return rating, count, "simulated"

    async def _self_rating(pid: str):
        agg = await db.reviews.aggregate([
            {"$match": {"property_id": pid, "rating": {"$type": ["int", "double", "long"]}}},
            {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "n": {"$sum": 1}}},
        ]).to_list(1)
        return (round(agg[0]["avg"], 1), agg[0]["n"]) if agg else (None, 0)

    async def _scan_property(pid: str) -> dict:
        cfg = await db.reputation_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = []
        self_rating, self_n = await _self_rating(pid)
        rows.append({"entity": "self", "name": "Bizim Otel", "rating": self_rating,
                     "review_count": self_n, "mode": "internal"})
        for comp in (cfg.get("competitors") or [])[:5]:
            rating, count, mode = await _fetch_rating(comp.get("place_id", ""), comp.get("name", ""))
            rows.append({"entity": "competitor", "name": comp.get("name", "?"),
                         "rating": rating, "review_count": count, "mode": mode})
        for row in rows:
            await db.reputation_snapshots.update_one(
                {"property_id": pid, "name": row["name"], "date": today},
                {"$set": {**row, "property_id": pid, "date": today, "created_at": _now()}},
                upsert=True)
        return {"property_id": pid, "date": today, "rows": rows}

    async def _scan_all(property_id: str) -> dict:
        if property_id and property_id != "all":
            pids = [property_id]
        else:
            pids = [c["property_id"] for c in await db.reputation_config.find(
                {}, {"_id": 0, "property_id": 1}).to_list(100)]
        out = []
        for pid in pids:
            try:
                out.append(await _scan_property(pid))
            except Exception as e:
                logger.warning(f"reputation scan failed {pid}: {e}")
        return {"scanned": len(out)}

    _BENCH["fn"] = _scan_all

    @router.get("/reputation/benchmark/{property_id}")
    async def benchmark(property_id: str, days: int = 30,
                        _: dict = Depends(require_roles("admin", "manager"))):
        from datetime import timedelta
        cfg = await db.reputation_config.find_one({"property_id": property_id}, {"_id": 0}) or {}
        cutoff = (datetime.now(timezone.utc) - timedelta(days=min(days, 90))).strftime("%Y-%m-%d")
        snaps = await db.reputation_snapshots.find(
            {"property_id": property_id, "date": {"$gte": cutoff}},
            {"_id": 0}).sort("date", 1).to_list(1000)
        latest_by_name, series = {}, {}
        for s in snaps:
            latest_by_name[s["name"]] = s
            series.setdefault(s["name"], []).append({"date": s["date"], "rating": s.get("rating")})
        table = sorted(latest_by_name.values(),
                       key=lambda x: (x.get("rating") or 0), reverse=True)
        for i, row in enumerate(table):
            row["rank"] = i + 1
            pts = series.get(row["name"], [])
            row["trend"] = (round((pts[-1]["rating"] or 0) - (pts[0]["rating"] or 0), 1)
                            if len(pts) >= 2 and pts[0]["rating"] and pts[-1]["rating"] else 0)
        return {"property_id": property_id,
                "competitors": cfg.get("competitors", []),
                "table": table, "series": series,
                "google_live": bool(os.environ.get("GOOGLE_PLACES_API_KEY"))}

    @router.put("/reputation/config/{property_id}")
    async def set_config(property_id: str, body: dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        comps = []
        for c in (body.get("competitors") or [])[:5]:
            name = str(c.get("name", "")).strip()[:80]
            if name:
                comps.append({"name": name, "place_id": str(c.get("place_id", "")).strip()[:120]})
        await db.reputation_config.update_one(
            {"property_id": property_id},
            {"$set": {"property_id": property_id, "competitors": comps,
                      "updated_at": _now(), "updated_by": current_user.get("email", "")}},
            upsert=True)
        return {"property_id": property_id, "competitors": comps}

    @router.post("/reputation/scan/{property_id}")
    async def scan_now(property_id: str,
                       _: dict = Depends(require_roles("admin", "manager"))):
        return await _scan_property(property_id)

    return router
