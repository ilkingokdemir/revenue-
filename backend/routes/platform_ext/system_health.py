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
    # günlük toplayıcı (haftalık özet için)
    d = datetime.now(timezone.utc).date().isoformat()
    agg = DAY_AGG.setdefault(d, {"count": 0, "e4": 0, "e5": 0, "sum_ms": 0.0, "eps": {}})
    agg["count"] += 1
    agg["sum_ms"] += dur_ms
    if 400 <= status < 500:
        agg["e4"] += 1
    elif status >= 500:
        agg["e5"] += 1
    ep = f"{method} {norm}"
    if ep in agg["eps"] or len(agg["eps"]) < 300:
        e = agg["eps"].setdefault(ep, [0, 0.0, 0.0, 0])
        e[0] += 1
        e[1] += dur_ms
        e[2] = max(e[2], dur_ms)
        if status >= 400:
            e[3] += 1


DAY_AGG = {}


async def flush_daily(db):
    """Bellekteki günlük toplamları db.health_daily'ye yazar (en yavaş 20 uçla)."""
    for d, agg in list(DAY_AGG.items()):
        eps = sorted(agg["eps"].items(), key=lambda kv: kv[1][1] / max(kv[1][0], 1), reverse=True)[:20]
        await db.health_daily.update_one({"date": d}, {"$set": {
            "date": d, "requests": agg["count"], "errors_4xx": agg["e4"], "errors_5xx": agg["e5"],
            "avg_ms": round(agg["sum_ms"] / max(agg["count"], 1), 1),
            "top_endpoints": [{"endpoint": k, "count": v[0], "avg_ms": round(v[1] / max(v[0], 1), 1),
                               "max_ms": round(v[2], 1), "errors": v[3]} for k, v in eps]}}, upsert=True)
    today = datetime.now(timezone.utc).date().isoformat()
    for d in [k for k in DAY_AGG if k != today]:
        DAY_AGG.pop(d, None)


def create_system_health_router(db, require_roles):
    router = APIRouter()

    @router.get("/system-health/status")
    async def health_status(user=Depends(require_roles("admin", "manager"))):
        return await compute_health(db)

    @router.post("/system-health/send-weekly-digest")
    async def trigger_digest(user=Depends(require_roles("admin"))):
        await flush_daily(db)
        return await send_weekly_digest(db, force=True)

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
            await flush_daily(db)
        except Exception as e:
            log.warning(f"health_alert_loop error: {e}")


async def send_weekly_digest(db, force: bool = False) -> dict:
    """Pazartesi sabahı: geçen 7 günün hata oranı + en yavaş uçlar özeti (adminlere e-posta)."""
    from datetime import timedelta
    from routes.platform_ext.mailer import send_email
    now = datetime.now(timezone.utc)
    week_key = f"{now.isocalendar().year}-W{now.isocalendar().week}"
    if not force and await db.health_digest_log.find_one({"week": week_key}):
        return {"skipped": True, "week": week_key}
    days = [(now.date() - timedelta(days=i)).isoformat() for i in range(0, 7)]
    docs = await db.health_daily.find({"date": {"$in": days}}, {"_id": 0}).to_list(10)
    total = sum(d["requests"] for d in docs)
    e5 = sum(d["errors_5xx"] for d in docs)
    e4 = sum(d["errors_4xx"] for d in docs)
    avg_ms = round(sum(d["avg_ms"] * d["requests"] for d in docs) / total, 1) if total else 0
    # uçları birleştir
    eps = {}
    for d in docs:
        for e in d.get("top_endpoints", []):
            a = eps.setdefault(e["endpoint"], {"count": 0, "sum": 0.0, "max_ms": 0.0, "errors": 0})
            a["count"] += e["count"]
            a["sum"] += e["avg_ms"] * e["count"]
            a["max_ms"] = max(a["max_ms"], e["max_ms"])
            a["errors"] += e["errors"]
    slowest = sorted(eps.items(), key=lambda kv: kv[1]["sum"] / max(kv[1]["count"], 1), reverse=True)[:5]
    rows = "".join(
        f"<tr><td style='padding:4px 8px;font-family:monospace;font-size:12px;'>{k}</td>"
        f"<td style='padding:4px 8px;font-size:12px;'>{v['count']}×</td>"
        f"<td style='padding:4px 8px;font-size:12px;'><b>{round(v['sum']/max(v['count'],1),1)} ms</b></td>"
        f"<td style='padding:4px 8px;font-size:12px;'>max {round(v['max_ms'],1)} ms</td></tr>"
        for k, v in slowest) or "<tr><td colspan='4' style='padding:8px;font-size:12px;'>Veri yok</td></tr>"
    e5_rate = round(e5 * 100 / total, 2) if total else 0
    html = f"""
    <h3>📊 Haftalık Sistem Sağlığı Özeti ({week_key})</h3>
    <p style="font-size:14px;">Son 7 gün: <b>{total}</b> istek · ort. yanıt <b>{avg_ms} ms</b> ·
    5xx hata: <b>{e5}</b> (%{e5_rate}) · 4xx: {e4}</p>
    <h4>🐢 En Yavaş 5 Uç</h4>
    <table style="border-collapse:collapse;background:#fafaf9;border-radius:8px;">{rows}</table>
    <p style="font-size:12px;color:#a8a29e;">Detay için panelde Sistem Sağlığı sayfasına bakın. — Sağlık Nöbetçisi</p>"""
    admins = await db.users.find({"role": "admin", "is_active": {"$ne": False}}, {"_id": 0, "email": 1}).to_list(20)
    sent = []
    for a in admins:
        if a.get("email"):
            st = await send_email(db, a["email"], f"📊 Haftalık Sistem Sağlığı Özeti — {week_key}", html,
                                  kind="health_digest")
            sent.append({"to": a["email"], "status": st})
    await db.health_digest_log.update_one({"week": week_key}, {"$set": {
        "week": week_key, "sent_at": now.isoformat(), "recipients": sent,
        "total_requests": total, "errors_5xx": e5}}, upsert=True)
    return {"week": week_key, "sent": sent, "total_requests": total, "errors_5xx": e5, "avg_ms": avg_ms}


async def weekly_digest_loop(db, interval_seconds: int = 3600):
    import asyncio
    import logging
    log = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            now = datetime.now(timezone.utc)
            if now.weekday() == 0 and now.hour >= 6:
                await send_weekly_digest(db)
        except Exception as e:
            log.warning(f"weekly_digest_loop error: {e}")
