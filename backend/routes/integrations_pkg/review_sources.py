"""
Review Source Connectors — Google / Booking yorumlarını gelen kutusuna çeker.

Google: GOOGLE_PLACES_API_KEY varsa Places API (New) place details (en alakalı
5 yorum) ile GERÇEK veri; yoksa SIMULATED mod (bir kerelik deterministik demo).
Booking: partner API'si public olmadığından SIMULATED.
Dedupe: reviews.external_id. Scheduler job: review_source_sync (05:30, sabah
taslaklarından önce).
"""
from datetime import datetime, timezone
import hashlib
import logging
import os
import uuid

import httpx
from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)

_SYNC = {}

SIM_REVIEWS = {
    "Google": [
        ("Sophie Laurent", 5, "Wonderful stay! The rooftop breakfast and friendly staff made our anniversary special."),
        ("Burak Şen", 3, "Konum iyi ama odalar biraz yorgun. Kahvaltı çeşitliliği artabilir."),
        ("Hans Weber", 4, "Sauberes Zimmer, gute Lage. Der Check-in hat etwas lange gedauert."),
    ],
    "Booking.com": [
        ("Anna Kowalska", 4, "Great value for money, very clean rooms. WiFi could be faster."),
        ("Mehmet Aydın", 2, "Rezervasyonumda oda tipi karışıklığı oldu, çözülmesi uzun sürdü."),
    ],
}


async def run_review_source_sync(property_id: str = "all") -> dict:
    fn = _SYNC.get("fn")
    if not fn:
        return {"error": "review_sources router not initialized"}
    return await fn(property_id)


def create_review_sources_router(db, require_roles):
    router = APIRouter()

    def _now():
        return datetime.now(timezone.utc).isoformat()

    async def _insert_review(pid, platform, author, rating, comment, external_id, source):
        if await db.reviews.find_one({"external_id": external_id}, {"_id": 1}):
            return False
        await db.reviews.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid,
            "platform": platform, "author": author, "guest_name": author,
            "rating": int(rating) if rating else 3,
            "comment": comment, "review_text": comment,
            "response_status": "pending",
            "response_text": "", "external_id": external_id,
            "source": source, "created_at": _now(),
        })
        return True

    async def _fetch_google_real(pid, place_id, api_key):
        url = f"https://places.googleapis.com/v1/places/{place_id}"
        headers = {"X-Goog-Api-Key": api_key,
                   "X-Goog-FieldMask": "id,displayName,rating,userRatingCount,reviews"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            return {"ok": False, "error": f"Places API {resp.status_code}", "new": 0}
        new = 0
        for r in resp.json().get("reviews", []):
            author = (r.get("authorAttribution") or {}).get("displayName", "Google user")
            text = ((r.get("text") or {}).get("text")
                    or (r.get("originalText") or {}).get("text") or "")
            if not text:
                continue
            ext = r.get("googleMapsUri") or hashlib.sha1(
                f"{author}{r.get('publishTime', '')}".encode()).hexdigest()
            if await _insert_review(pid, "Google", author, r.get("rating"),
                                    text, f"gplaces-{ext}", "google_places_api"):
                new += 1
        return {"ok": True, "mode": "live", "new": new}

    async def _fetch_simulated(pid, platform):
        new = 0
        for i, (author, rating, comment) in enumerate(SIM_REVIEWS[platform]):
            ext = f"sim-{pid}-{platform.lower().replace('.', '')}-{i}"
            if await _insert_review(pid, platform, author, rating, comment, ext, "simulated"):
                new += 1
        return {"ok": True, "mode": "simulated", "new": new}

    async def _sync_property(pid: str) -> dict:
        cfg = await db.review_source_config.find_one({"property_id": pid}, {"_id": 0}) or {}
        if cfg.get("enabled") is False:
            return {"property_id": pid, "skipped": True}
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
        results = {}
        if api_key and cfg.get("google_place_id"):
            try:
                results["google"] = await _fetch_google_real(pid, cfg["google_place_id"], api_key)
            except Exception as e:
                logger.warning(f"google places fetch failed {pid}: {e}")
                results["google"] = {"ok": False, "error": str(e), "new": 0}
        else:
            results["google"] = await _fetch_simulated(pid, "Google")
        results["booking"] = await _fetch_simulated(pid, "Booking.com")
        total_new = sum(r.get("new", 0) for r in results.values())
        await db.review_source_config.update_one(
            {"property_id": pid},
            {"$set": {"property_id": pid, "last_sync_at": _now(),
                      "last_result": {"total_new": total_new, **results}}},
            upsert=True)
        return {"property_id": pid, "total_new": total_new, **results}

    async def _sync_all(property_id: str) -> dict:
        if property_id and property_id != "all":
            pids = [property_id]
        else:
            pids = [p["id"] async for p in db.properties.find({}, {"_id": 0, "id": 1})]
        out = []
        for pid in pids:
            try:
                out.append(await _sync_property(pid))
            except Exception as e:
                logger.warning(f"review sync failed {pid}: {e}")
        return {"synced": len(out), "total_new": sum(o.get("total_new", 0) for o in out),
                "details": out[:20]}

    _SYNC["fn"] = _sync_all

    @router.get("/review-sources/{property_id}")
    async def get_config(property_id: str,
                         _: dict = Depends(require_roles("admin", "manager"))):
        cfg = await db.review_source_config.find_one(
            {"property_id": property_id}, {"_id": 0}) or {}
        return {"property_id": property_id,
                "google_place_id": cfg.get("google_place_id", ""),
                "booking_url": cfg.get("booking_url", ""),
                "tripadvisor_url": cfg.get("tripadvisor_url", ""),
                "enabled": cfg.get("enabled", True),
                "last_sync_at": cfg.get("last_sync_at", ""),
                "last_result": cfg.get("last_result", {}),
                "google_live": bool(os.environ.get("GOOGLE_PLACES_API_KEY"))}

    @router.put("/review-sources/{property_id}")
    async def set_config(property_id: str, body: dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = {"property_id": property_id, "updated_at": _now(),
               "updated_by": current_user.get("email", "")}
        if "google_place_id" in body:
            upd["google_place_id"] = str(body["google_place_id"]).strip()[:120]
        if "booking_url" in body:
            upd["booking_url"] = str(body["booking_url"]).strip()[:300]
        if "tripadvisor_url" in body:
            upd["tripadvisor_url"] = str(body["tripadvisor_url"]).strip()[:300]
        if "enabled" in body:
            upd["enabled"] = bool(body["enabled"])
        await db.review_source_config.update_one(
            {"property_id": property_id}, {"$set": upd}, upsert=True)
        return await get_config(property_id, _={})

    @router.post("/review-sources/{property_id}/sync-now")
    async def sync_now(property_id: str,
                       _: dict = Depends(require_roles("admin", "manager"))):
        return await _sync_property(property_id)

    return router
