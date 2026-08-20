"""Canlı sonrası sistem sağlığı — istek metrikleri, hata oranı, yavaş uçlar (bellek-içi, hafif)."""
import re
import time
import collections
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

STARTED = time.time()
REQS = collections.deque(maxlen=5000)   # (ts, method, norm_path, status, dur_ms)
ERRORS = collections.deque(maxlen=50)   # dict

_ID_SEG = re.compile(r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{24}|\d+)$", re.I)


def _normalize(path: str) -> str:
    return "/".join("{id}" if _ID_SEG.match(seg) else seg for seg in path.split("/"))


def record_request(method: str, path: str, status: int, dur_ms: float):
    now = time.time()
    norm = _normalize(path)
    REQS.append((now, method, norm, status, dur_ms))
    if status >= 400:
        ERRORS.append({"ts": datetime.now(timezone.utc).isoformat(), "method": method,
                       "path": path, "status": status, "dur_ms": round(dur_ms, 1)})


def create_system_health_router(db, require_roles):
    router = APIRouter()

    @router.get("/system-health/status")
    async def health_status(user=Depends(require_roles("admin", "manager"))):
        now = time.time()
        hour = [r for r in REQS if now - r[0] <= 3600]
        total = len(hour)
        e4 = sum(1 for r in hour if 400 <= r[3] < 500)
        e5 = sum(1 for r in hour if r[3] >= 500)
        durs = sorted(r[4] for r in hour)
        avg_ms = round(sum(durs) / total, 1) if total else 0
        p95_ms = round(durs[int(total * 0.95) - 1], 1) if total >= 2 else avg_ms
        # uç bazında grupla
        agg = {}
        for _, m, p, s, d in hour:
            k = f"{m} {p}"
            a = agg.setdefault(k, {"endpoint": k, "count": 0, "sum": 0.0, "max_ms": 0.0, "errors": 0})
            a["count"] += 1
            a["sum"] += d
            a["max_ms"] = max(a["max_ms"], d)
            if s >= 400:
                a["errors"] += 1
        slowest = sorted(agg.values(), key=lambda a: a["sum"] / a["count"], reverse=True)[:8]
        for a in slowest:
            a["avg_ms"] = round(a["sum"] / a["count"], 1)
            a["max_ms"] = round(a["max_ms"], 1)
            del a["sum"]
        # DB gecikmesi
        t0 = time.perf_counter()
        try:
            await db.command("ping")
            db_ping_ms = round((time.perf_counter() - t0) * 1000, 1)
        except Exception:
            db_ping_ms = None
        err5_rate = round(e5 * 100 / total, 2) if total else 0.0
        status = "healthy"
        if db_ping_ms is None or err5_rate >= 5:
            status = "unhealthy"
        elif err5_rate >= 1 or (db_ping_ms and db_ping_ms > 250) or p95_ms > 3000:
            status = "degraded"
        return {"status": status, "uptime_s": int(now - STARTED),
                "window": "son 1 saat", "requests": total,
                "avg_ms": avg_ms, "p95_ms": p95_ms,
                "errors_4xx": e4, "errors_5xx": e5, "error_5xx_rate_pct": err5_rate,
                "db_ping_ms": db_ping_ms,
                "slowest_endpoints": slowest,
                "recent_errors": list(ERRORS)[-15:][::-1],
                "as_of": datetime.now(timezone.utc).isoformat()}

    return router
