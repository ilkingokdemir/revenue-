"""Tesis Provizyonu — her otel hesabı TÜM modüllere hazır açılır (idempotent seed)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends


async def provision_property(db, pid: str, name: str = "") -> dict:
    """Bir tesisi tüm modüller çalışacak şekilde hazırlar. Var olan veriye dokunmaz."""
    now = datetime.now(timezone.utc).isoformat()
    seeded = []

    await db.properties.update_one(
        {"id": pid},
        {"$set": {"modules_enabled": "all", "plan": "full", "provisioned_at": now}})
    seeded.append("plan=full (tüm modüller)")

    if not await db.room_types.find_one({"property_id": pid}, {"_id": 1}):
        await db.room_types.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "name": "Standard Room",
            "description": "Varsayılan oda tipi — Ayarlar'dan düzenleyin",
            "base_rate": 100.0, "total_rooms": 10, "max_guests": 2,
            "is_active": True, "created_at": now})
        seeded.append("örnek oda tipi")

    if not await db.comp_trigger.find_one({"property_id": pid}, {"_id": 1}):
        await db.comp_trigger.insert_one({
            "property_id": pid, "threshold_pct": 10.0, "enabled": False,
            "trend_weeks": 2, "trend_step_pp": 1.0, "created_at": now})
        seeded.append("rakip fiyat tetiği (varsayılan ±%10)")

    if not await db.occupancy_rules.find_one({"property_id": pid}, {"_id": 1}):
        await db.occupancy_rules.insert_one({
            "property_id": pid, "enabled": False, "threshold_pct": 90, "extra_pct": 10,
            "low_threshold_pct": 30, "low_discount_pct": 10, "created_at": now})
        seeded.append("doluluk kuralları (kapalı, hazır)")

    if not await db.cloudbeds_config.find_one({"property_id": pid}, {"_id": 1}):
        await db.cloudbeds_config.insert_one({
            "property_id": pid, "auto_push": False, "auto_push_days": 14,
            "rate_map": {}, "created_at": now})
        seeded.append("cloudbeds bağlantı iskeleti")

    if not await db.template_settings.find_one({"property_id": pid}, {"_id": 1}):
        await db.template_settings.insert_one({
            "property_id": pid, "retention_months": 12, "created_at": now})
        seeded.append("rapor şablon ayarları")

    if not await db.notifications.find_one(
            {"property_id": pid, "created_by": "Provizyon"}, {"_id": 1}):
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "success",
            "title": f"🎉 {name or pid} — hesabınız tüm modüllerle hazır",
            "message": "Rezervasyon, gelir yönetimi, kanal bağlantıları, raporlar ve 280+ modülün "
                       "tamamı bu tesis için aktif. Sol menüde PRO moda geçerek hepsine ulaşabilirsiniz.",
            "category": "system", "target_role": "admin", "link_to": "dashboard",
            "priority": "normal", "read": False, "property_id": pid,
            "created_by": "Provizyon", "created_at": now})
        seeded.append("hoş geldin bildirimi")

    return {"property_id": pid, "seeded": seeded}


def create_provisioning_router(db, require_roles):
    router = APIRouter(prefix="/provisioning", tags=["provisioning"])

    @router.get("/status")
    async def status(_u: dict = Depends(require_roles("admin", "manager"))):
        props = await db.properties.find({"is_active": {"$ne": False}},
                                         {"_id": 0, "id": 1, "name": 1, "plan": 1,
                                          "modules_enabled": 1, "provisioned_at": 1}).to_list(100)
        return {"properties": props,
                "full_count": sum(1 for p in props if p.get("plan") == "full"),
                "total": len(props),
                "note": "plan=full → tesis 280+ modülün tamamını kullanabilir. "
                        "Yeni açılan her tesis otomatik provizyonlanır."}

    @router.post("/apply-all")
    async def apply_all(_u: dict = Depends(require_roles("admin"))):
        """Tüm aktif tesisleri tam modül erişimiyle provizyonlar (idempotent)."""
        props = await db.properties.find({"is_active": {"$ne": False}},
                                         {"_id": 0, "id": 1, "name": 1}).to_list(100)
        results = []
        for p in props:
            results.append(await provision_property(db, p["id"], p.get("name", "")))
        return {"ok": True, "provisioned": len(results), "results": results}

    return router
