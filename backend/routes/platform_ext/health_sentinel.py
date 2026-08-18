"""Sağlık Nöbetçisi — modül API'lerini yoklar, sorun bulursa bildirim düşer."""
import uuid
import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends

BASE = "http://localhost:8001/api"

# Modül ailesi -> temsili endpoint (GET). 2xx/401/403 = sağlıklı, 404/5xx/timeout = sorun.
HEALTH_ENDPOINTS = [
    ("Ön Büro / Rezervasyon", "/bookings?property_id=default"),
    ("Oda Tipleri", "/room-types?property_id=default"),
    ("Fiyat Takvimi", "/revenue/rate-calendar/default"),
    ("Misafir Segmentleri", "/guests/segments/summary"),
    ("Housekeeping", "/housekeeping/tasks/default"),
    ("Bakım / Arıza", "/maintenance/issues/default"),
    ("Gelir Tahmini", "/revenue/intelligence/default/forecast"),
    ("Doluluk Kuralı", "/demand-signals/default/occupancy-rule"),
    ("Rakip Fiyat Tetiği", "/demand-signals/default/comp-trigger"),
    ("Pazarla Makas Özeti", "/demand-signals/default/comp-trigger/summary"),
    ("AI Pricing", "/revenue/ai-pricing/default/config"),
    ("Compset", "/compset/default"),
    ("Rakip İstihbaratı", "/revenue/compset-intel/default"),
    ("Kanal Gelirleri", "/channel-revenue/channels/default"),
    ("PMS Connect", "/pms-connect/pdf-center/default"),
    ("Muhasebe / P&L", "/accounting/pnl/default"),
    ("Gece Denetimi", "/night-audit/latest/default"),
    ("POS Folio", "/pos/room-folios/default"),
    ("Zamanlı Raporlar", "/scheduled-reports/default"),
    ("Bildirimler", "/notifications?limit=1"),
    ("Görevlerim", "/my-tasks"),
    ("Kampanyalar", "/campaigns/default"),
    ("Sadakat", "/loyalty/leaderboard/default"),
    ("POS Siparişleri", "/pos/orders/default"),
    ("Etkinlik Sinyalleri", "/revenue/events/default"),
    ("Personel", "/staff/default/active"),
    ("Şubeler", "/properties"),
    ("Hata Nöbetçisi", "/client-errors"),
    ("Kimlik / Oturum", "/auth/me"),
]


async def run_health_sentinel(db, notify: bool = True) -> dict:
    started = datetime.now(timezone.utc)
    results, failures = [], []
    async with httpx.AsyncClient(timeout=10) as client:
        for name, path in HEALTH_ENDPOINTS:
            try:
                r = await client.get(BASE + path)
                code = r.status_code
                ok = code < 400 or code in (401, 403, 422)
            except Exception:
                code, ok = 0, False
            item = {"module": name, "path": path, "status": code, "ok": ok}
            results.append(item)
            if not ok:
                failures.append(item)
    doc = {"id": str(uuid.uuid4()), "at": started.isoformat(),
           "ok_count": len(results) - len(failures), "fail_count": len(failures),
           "failures": failures, "results": results,
           "duration_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000)}
    await db.health_checks.insert_one({**doc})
    if failures and notify:
        day = started.date().isoformat()
        dup = await db.notifications.find_one(
            {"created_by": "Sağlık Nöbetçisi", "day": day}, {"_id": 1})
        if not dup:
            lines = [f"• {f['module']} ({f['path']}) → {f['status'] or 'zaman aşımı'}" for f in failures[:8]]
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "type": "error",
                "title": f"🩺 Sağlık Nöbetçisi: {len(failures)} modül API'sinde sorun",
                "message": "Gece taramasında yanıt vermeyen/hatalı modül API'leri:\n"
                           + "\n".join(lines)
                           + "\nDetay: Ayarlar → Hata Nöbetçisi → Sağlık Nöbetçisi kartı.",
                "category": "system", "target_user": "", "target_role": "admin",
                "link_to": "error-sentinel", "priority": "high", "read": False,
                "day": day, "created_by": "Sağlık Nöbetçisi",
                "created_at": datetime.now(timezone.utc).isoformat()})
    return doc


async def health_sentinel_loop(db, interval_seconds: int = 24 * 3600):
    await asyncio.sleep(180)
    while True:
        try:
            await run_health_sentinel(db)
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


def create_health_sentinel_router(db, require_roles):
    router = APIRouter(prefix="/health-sentinel", tags=["health-sentinel"])
    ROLES = ("admin", "manager")

    @router.get("/status")
    async def status(_u: dict = Depends(require_roles(*ROLES))):
        last = await db.health_checks.find_one({}, {"_id": 0}, sort=[("at", -1)])
        return {"last_run": last, "endpoints": len(HEALTH_ENDPOINTS),
                "note": "Robot her gece tüm modül API'lerini yoklar; sorun bulursa zil bildirimine düşer."}

    @router.post("/run")
    async def run_now(_u: dict = Depends(require_roles(*ROLES))):
        return await run_health_sentinel(db, notify=True)

    return router
