"""Bağlantı Kataloğu — sektördeki PMS/Channel Manager/OTA konnektörleri; seç ve bağlan."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

CATALOG = [
    # --- PMS / All-in-one ---
    {"key": "cloudbeds", "name": "Cloudbeds", "category": "PMS", "api_type": "open", "panel": "cloudbeds-live"},
    {"key": "mews", "name": "Mews", "category": "PMS", "api_type": "open", "panel": "pms-connect"},
    {"key": "apaleo", "name": "Apaleo", "category": "PMS", "api_type": "open", "panel": "pms-connect"},
    {"key": "eviivo", "name": "eviivo Suite", "category": "PMS", "api_type": "partner", "panel": "pms-connect"},
    {"key": "elektraweb", "name": "Elektraweb", "category": "PMS", "api_type": "partner", "panel": "pms-connect"},
    {"key": "booking-factory", "name": "The Booking Factory", "category": "PMS", "api_type": "open", "panel": None},
    {"key": "opera-cloud", "name": "Oracle OPERA Cloud (OHIP)", "category": "PMS", "api_type": "partner", "panel": "pms-connect"},
    {"key": "protel", "name": "protel (Planet)", "category": "PMS", "api_type": "partner", "panel": None},
    {"key": "guestline", "name": "Guestline Rezlynx", "category": "PMS", "api_type": "partner", "panel": None},
    {"key": "little-hotelier", "name": "Little Hotelier", "category": "PMS", "api_type": "closed", "panel": None},
    {"key": "sirvoy", "name": "Sirvoy", "category": "PMS", "api_type": "open", "panel": None},
    {"key": "beds24", "name": "Beds24", "category": "PMS", "api_type": "open", "panel": None},
    {"key": "clock-pms", "name": "Clock PMS+", "category": "PMS", "api_type": "open", "panel": None},
    {"key": "hotelogix", "name": "Hotelogix", "category": "PMS", "api_type": "partner", "panel": None},
    {"key": "rms-cloud", "name": "RMS Cloud", "category": "PMS", "api_type": "partner", "panel": None},
    # --- Channel Manager ---
    {"key": "siteminder", "name": "SiteMinder", "category": "Channel Manager", "api_type": "partner", "panel": "siteminder"},
    {"key": "hotelrunner", "name": "HotelRunner", "category": "Channel Manager", "api_type": "open", "panel": "hotelrunner-live"},
    {"key": "d-edge", "name": "D-EDGE", "category": "Channel Manager", "api_type": "partner", "panel": None},
    {"key": "rategain", "name": "RateGain", "category": "Channel Manager", "api_type": "partner", "panel": None},
    {"key": "cubilis", "name": "Cubilis (Stardekk)", "category": "Channel Manager", "api_type": "partner", "panel": None},
    {"key": "wubook", "name": "WuBook", "category": "Channel Manager", "api_type": "open", "panel": None},
    {"key": "octorate", "name": "Octorate", "category": "Channel Manager", "api_type": "open", "panel": None},
    {"key": "hotel-spider", "name": "Hotel-Spider", "category": "Channel Manager", "api_type": "partner", "panel": None},
    # --- OTA Direct (gelecek) ---
    {"key": "booking-com", "name": "Booking.com (Direct Connect)", "category": "OTA Direct", "api_type": "partner", "panel": None, "coming_soon": True},
    {"key": "expedia", "name": "Expedia (EPS Rapid)", "category": "OTA Direct", "api_type": "partner", "panel": None, "coming_soon": True},
    {"key": "airbnb", "name": "Airbnb (Direct)", "category": "OTA Direct", "api_type": "partner", "panel": None, "coming_soon": True},
    {"key": "agoda", "name": "Agoda (YCS)", "category": "OTA Direct", "api_type": "partner", "panel": None, "coming_soon": True},
    # --- Kendi Kanalları ---
    {"key": "hotel-website", "name": "Kendi Otel Web Sitesi (Booking Engine)", "category": "Direkt Kanal", "api_type": "open", "panel": "booking-engine-v2"},
]


def create_connector_catalog_router(db, require_roles):
    router = APIRouter(prefix="/connector-catalog", tags=["connector-catalog"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def get_catalog(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cb = await db.cloudbeds_config.find_one({"property_id": pid}, {"_id": 0, "api_key": 1})
        pms_conns = await db.pms_connections.find({"property_id": pid}, {"_id": 0, "vendor": 1, "status": 1}).to_list(20)
        conn_vendors = {c.get("vendor", "").lower() for c in pms_conns if c.get("status") in ("connected", "live")}
        reqs = {r["key"] async for r in db.connector_requests.find({"property_id": pid}, {"_id": 0, "key": 1})}
        from routes.distribution.pms_connect import PROVIDERS, _has_creds
        pc_cfgs = {c["provider"]: c async for c in db.pms_connect_config.find({"property_id": pid}, {"_id": 0})}
        pc_connected = {k for k, c in pc_cfgs.items() if k in PROVIDERS and _has_creds(k, c)}
        pc_tested = {k: (c.get("last_test") or {}).get("ok") for k, c in pc_cfgs.items()}
        out = []
        for c in CATALOG:
            item = dict(c)
            if c["key"] == "cloudbeds":
                item["status"] = "connected" if (cb or {}).get("api_key") else "ready"
            elif c["key"] in PROVIDERS:
                item["status"] = "connected" if (c["key"] in pc_connected or (c["key"] == "mews" and "mews" in conn_vendors)) else "ready"
                item["last_test_ok"] = pc_tested.get(c["key"])
            elif c.get("coming_soon"):
                item["status"] = "coming_soon"
            elif c.get("panel"):
                item["status"] = "ready"
            else:
                item["status"] = "requested" if c["key"] in reqs else "available"
            out.append(item)
        return {"property_id": pid, "connectors": out,
                "counts": {"total": len(out),
                           "ready": sum(1 for o in out if o["status"] in ("ready", "connected")),
                           "connected": sum(1 for o in out if o["status"] == "connected")},
                "note": "Hazır olanlar panelinden bağlanır; diğerleri için 'Talep Et' — öncelik sırasına alınır."}

    @router.get("/requests/summary/all")
    async def requests_summary(_u: dict = Depends(require_roles("admin", "manager"))):
        """Admin: konnektör taleplerini oy sayısıyla sıralar — geliştirme önceliği."""
        agg = await db.connector_requests.aggregate([
            {"$group": {"_id": "$key", "votes": {"$sum": 1},
                        "last_at": {"$max": "$requested_at"}}},
            {"$sort": {"votes": -1, "last_at": -1}}]).to_list(50)
        names = {c["key"]: c["name"] for c in CATALOG}
        return {"requests": [{"key": a["_id"], "name": names.get(a["_id"], a["_id"]),
                              "votes": a["votes"], "last_at": a["last_at"]} for a in agg],
                "note": "Her tesis bir konnektörü 1 kez talep edebilir — oy = kaç tesisin istediği."}

    @router.post("/{pid}/request")
    async def request_connector(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        key = str(data.get("key", "")).strip()
        if not any(c["key"] == key for c in CATALOG):
            return {"ok": False, "error": "Bilinmeyen konnektör"}
        await db.connector_requests.update_one(
            {"property_id": pid, "key": key},
            {"$set": {"property_id": pid, "key": key,
                      "requested_by": str(_u.get("email") or ""),
                      "requested_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "key": key, "message": "Talep alındı — bu konnektör geliştirme sırasına eklendi."}

    return router
