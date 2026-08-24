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
        return await compute_health(db)

    return router


async def compute_health(db) -> dict:
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


_ALERT_STATE = {"last": "healthy", "last_alert_ts": 0.0}


async def check_and_alert(db) -> dict:
    """Sağlığı hesaplar; 🔴 duruma geçişte adminlere bildirim + e-posta (30 dk cooldown)."""
    import uuid as _uuid
    h = await compute_health(db)
    now = time.time()
    if h["status"] == "unhealthy" and (_ALERT_STATE["last"] != "unhealthy"
                                       or now - _ALERT_STATE["last_alert_ts"] > 1800):
        from routes.platform_ext.mailer import send_email
        detail = (f"5xx oranı: %{h['error_5xx_rate_pct']} ({h['errors_5xx']} hata) · "
                  f"P95: {h['p95_ms']} ms · DB ping: {h['db_ping_ms']} ms")
        await db.notifications.insert_one({
            "id": str(_uuid.uuid4()), "type": "alert",
            "title": "🔴 Sistem sağlığı KRİTİK",
            "message": f"Platform sorunlu duruma geçti — {detail}. Sistem Sağlığı sayfasını kontrol edin.",
            "category": "platform", "target_user": "", "target_role": "admin",
            "link_to": "system-health", "priority": "high", "read": False,
            "created_by": "Sağlık Nöbetçisi", "created_at": datetime.now(timezone.utc).isoformat()})
        admins = await db.users.find({"role": "admin", "is_active": {"$ne": False}},
                                     {"_id": 0, "email": 1}).to_list(20)
        html = (f"<h3>🔴 Sistem sağlığı KRİTİK duruma geçti</h3><p>{detail}</p>"
                "<p>Lütfen panelde <b>Sistem Sağlığı</b> sayfasını kontrol edin.</p>")
        for a in admins:
            if a.get("email"):
                await send_email(db, a["email"], "🔴 MyHotelBox — Sistem sağlığı kritik!", html,
                                 kind="health_alert")
        _ALERT_STATE["last_alert_ts"] = now
    if h["status"] == "healthy" and _ALERT_STATE["last"] == "unhealthy":
        await db.notifications.insert_one({
            "id": str(_uuid.uuid4()), "type": "info", "title": "🟢 Sistem sağlığı normale döndü",
            "message": "Platform tekrar sağlıklı duruma geçti.",
            "category": "platform", "target_user": "", "target_role": "admin",
            "link_to": "system-health", "priority": "normal", "read": False,
            "created_by": "Sağlık Nöbetçisi", "created_at": datetime.now(timezone.utc).isoformat()})
    _ALERT_STATE["last"] = h["status"]
    return h


async def health_alert_loop(db, interval_seconds: int = 300):
    import asyncio
    import logging
    log = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await check_and_alert(db)
        except Exception as e:
            log.warning(f"health_alert_loop error: {e}")
