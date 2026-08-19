"""Tesis Tipi Preset'leri — hostel/apart/extended-stay/şehir/resort hazır kurulum şablonları."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

PRESETS = {
    "city_hotel": {"name": "Şehir Oteli", "desc": "Standart + Deluxe odalar, iş seyahati odaklı, günlük fiyat dalgalanması",
                   "room_types": [{"name": "Standard Room", "base_rate": 110, "total": 10},
                                  {"name": "Deluxe Room", "base_rate": 150, "total": 6}],
                   "rms": {"base_price": 110, "min_rate": 75, "max_rate": 320, "mode": "copilot"}},
    "resort": {"name": "Resort", "desc": "Sezonluk fiyatlama, aile odaları, uzun rezervasyon penceresi",
               "room_types": [{"name": "Garden View", "base_rate": 140, "total": 12},
                              {"name": "Sea View Suite", "base_rate": 220, "total": 6}],
               "rms": {"base_price": 140, "min_rate": 90, "max_rate": 500, "mode": "copilot"}},
    "hostel": {"name": "Hostel", "desc": "Yatak bazlı satış (dorm), düşük fiyat, yüksek doluluk hedefi",
               "room_types": [{"name": "8-Bed Dorm (per bed)", "base_rate": 22, "total": 16},
                              {"name": "Private Twin", "base_rate": 65, "total": 4}],
               "rms": {"base_price": 22, "min_rate": 14, "max_rate": 60, "mode": "autopilot"}},
    "apart": {"name": "Apart / Serviced Apartment", "desc": "Ünite bazlı, temizlik ücreti, min konaklama kuralları",
              "room_types": [{"name": "Studio Apartment", "base_rate": 95, "total": 8},
                             {"name": "1-Bedroom Apartment", "base_rate": 130, "total": 5}],
              "rms": {"base_price": 95, "min_rate": 65, "max_rate": 260, "mode": "copilot"}},
    "extended_stay": {"name": "Uzun Konaklama", "desc": "Haftalık/aylık indirim kademeleri, düşük devir",
                      "room_types": [{"name": "Extended Studio", "base_rate": 80, "total": 10}],
                      "rms": {"base_price": 80, "min_rate": 55, "max_rate": 180, "mode": "manual"}},
}


def create_presets_router(db, require_roles):
    router = APIRouter(prefix="/property-presets", tags=["presets"])
    ROLES = ("admin", "manager")

    @router.get("")
    async def catalog(_u: dict = Depends(require_roles(*ROLES))):
        return {"presets": [{"id": k, **{x: v[x] for x in ("name", "desc")},
                             "room_types": v["room_types"], "rms": v["rms"]} for k, v in PRESETS.items()]}

    @router.post("/apply/{pid}")
    async def apply(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        key = data.get("preset")
        p = PRESETS.get(key)
        if not p:
            raise HTTPException(422, f"preset: {'|'.join(PRESETS)}")
        now = datetime.now(timezone.utc).isoformat()
        created = 0
        existing = await db.room_types.count_documents({"property_id": pid})
        if existing == 0 or data.get("force_rooms"):
            for rt in p["room_types"]:
                await db.room_types.insert_one({"id": str(uuid.uuid4()), "property_id": pid,
                                                "name": rt["name"], "base_rate": rt["base_rate"],
                                                "total": rt["total"], "created_at": now})
                created += 1
        r = p["rms"]
        await db.rms_setup.update_one({"property_id": pid}, {"$set": {
            "base_price": r["base_price"], "min_rate": r["min_rate"], "max_rate": r["max_rate"],
            "mode": r["mode"], "preset": key, "updated_at": now}}, upsert=True)
        await db.properties.update_one({"id": pid}, {"$set": {"property_type": key, "preset": key}})
        return {"ok": True, "preset": key, "room_types_created": created,
                "rooms_skipped": existing > 0 and not data.get("force_rooms"),
                "rms_defaults": r}

    return router
