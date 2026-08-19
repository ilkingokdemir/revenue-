"""AI Copilot çatısı — dağınık AI modüllerinin tek panel/marka özeti (Signals AI paritesi)."""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends


def create_ai_copilot_router(db, require_roles):
    router = APIRouter(prefix="/ai-copilot", tags=["ai-copilot"])

    @router.get("/summary/{pid}")
    async def summary(pid: str, _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        q = {} if pid == "all" else {"property_id": pid}
        return {
            "copilot_pending": await db.copilot_queue.count_documents({**q, "status": "pending"}),
            "guard_actions_24h": await db.price_guard_log.count_documents({**q, "created_at": {"$gte": since}}),
            "open_conflicts": await db.ical_conflicts.count_documents({**q, "status": "open"}),
            "unread_ai_alerts": await db.notifications.count_documents(
                {**q, "read": False, "type": {"$in": ["surge_alert", "ical_conflict", "trend_alert"]}}),
            "comp_triggers_on": await db.comp_trigger.count_documents({**q, "enabled": True}),
            "autopilot_on": await db.pricing_autopilot.count_documents({**q, "enabled": True}),
        }

    @router.get("/today/{pid}")
    async def today_actions(pid: str, _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """'Bugün ne yapmalıyım' — önceliklendirilmiş günlük aksiyon listesi."""
        q = {} if pid == "all" else {"property_id": pid}
        today = datetime.now(timezone.utc).date().isoformat()
        tasks = []
        n = await db.copilot_queue.count_documents({**q, "status": "pending"})
        if n:
            tasks.append({"severity": "high", "view": "rms-setup",
                          "title": f"{n} fiyat önerisi onayınızı bekliyor",
                          "detail": "Co-Pilot kuyruğunu inceleyin — talep değişti, fiyatlar güncellensin."})
        n = await db.ical_conflicts.count_documents({**q, "status": "open"})
        if n:
            tasks.append({"severity": "high", "view": "ical-sync",
                          "title": f"{n} çifte rezervasyon çakışması açık",
                          "detail": "Misafiri taşıyın veya kanalı kapatın — overbooking riski."})
        n = await db.bookings.count_documents({**q, "check_in": today,
                                               "status": {"$nin": ["cancelled", "no_show", "checked_in"]},
                                               "payment_status": {"$in": ["pending", "partial", None]}})
        if n:
            tasks.append({"severity": "medium", "view": "calendar",
                          "title": f"Bugün gelen {n} rezervasyonun ödemesi eksik",
                          "detail": "Check-in öncesi ödeme linki gönderin veya terminalden tahsil edin."})
        n = await db.notifications.count_documents({**q, "read": False,
                                                    "type": {"$in": ["surge_alert", "trend_alert"]}})
        if n:
            tasks.append({"severity": "medium", "view": "ai-pricing",
                          "title": f"{n} okunmamış talep/trend uyarısı",
                          "detail": "Surge ve trend sinyallerini gözden geçirin."})
        if pid != "all":
            setup = await db.rms_setup.find_one({"property_id": pid}, {"_id": 0, "min_rate": 1, "mode": 1})
            if not setup or not setup.get("min_rate"):
                tasks.append({"severity": "medium", "view": "rms-setup",
                              "title": "Fiyat koruması (guardrail) tanımlı değil",
                              "detail": "Min/max fiyat sınırlarını 2 dakikada kurun — AI sınır dışına çıkamasın."})
            site = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0, "published": 1})
            if not site or not site.get("published"):
                tasks.append({"severity": "low", "view": "site-builder",
                              "title": "Otel web siteniz henüz yayında değil",
                              "detail": "Şablon seçip tek tıkla yayınlayın — komisyonsuz direkt rezervasyon alın."})
            guards = await db.price_guards.find_one({"property_id": pid}, {"_id": 0})
            if not guards or not ((guards.get("poba") or {}).get("enabled") or (guards.get("surge") or {}).get("enabled")):
                tasks.append({"severity": "low", "view": "price-guards",
                              "title": "Fiyat Bekçileri kapalı",
                              "detail": "POBA ve Surge korumasını açın — fırsatlar otomatik yakalansın."})
        if not tasks:
            tasks.append({"severity": "ok", "view": "dashboard",
                          "title": "Harika! Bugün acil aksiyon yok",
                          "detail": "Tüm sistemler yeşil — dashboard'dan genel gidişatı izleyin."})
        return {"date": today, "tasks": tasks}

    return router
