"""
Google Business Profile publish queue (PENDING-APPROVAL / MOCK mode).

Live GBP API access requires Google project approval (60+ day verified
Business Profile, quota grant). Until GBP_LIVE=true and OAuth credentials
are configured, approved review replies are queued with status
PENDING_APPROVAL instead of being pushed to Google.
"""
from datetime import datetime, timezone
import logging
import os

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def create_gbp_router(db, require_roles):
    router = APIRouter()

    def _live() -> bool:
        return os.environ.get("GBP_LIVE", "false").lower() == "true"

    @router.get("/gbp/status")
    async def status(property_id: str = "",
                     _: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id} if property_id else {}
        pending = await db.gbp_publish_queue.count_documents({**q, "status": "PENDING_APPROVAL"})
        published = await db.gbp_publish_queue.count_documents({**q, "status": "PUBLISHED"})
        return {"live": _live(), "mode": "live" if _live() else "mock_pending_approval",
                "connected": bool(await db.google_tokens.count_documents({})),
                "queue_pending": pending, "published": published}

    @router.get("/gbp/queue")
    async def queue(property_id: str = "", limit: int = 50,
                    _: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id} if property_id else {}
        items = await db.gbp_publish_queue.find(q, {"_id": 0}).sort(
            "created_at", -1).to_list(min(limit, 200))
        return {"items": items, "count": len(items)}

    @router.post("/gbp/publish/{queue_id}")
    async def publish(queue_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        item = await db.gbp_publish_queue.find_one({"id": queue_id}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Kuyruk kaydı bulunamadı")
        if not _live():
            return {"mode": "mock", "status": "PENDING_APPROVAL",
                    "message": ("Google Business Profile API erişimi henüz onaylanmadı. "
                                "Yanıt kuyruğa kaydedildi; canlı mod (GBP_LIVE=true) "
                                "aktifleşince otomatik yayınlanacak.")}
        # Live path: requires OAuth refresh token in db.google_tokens (post-approval).
        raise HTTPException(501, "Canlı GBP yayını için OAuth bağlantısı henüz yapılandırılmadı")

    @router.delete("/gbp/queue/{queue_id}")
    async def remove(queue_id: str,
                     _: dict = Depends(require_roles("admin", "manager"))):
        res = await db.gbp_publish_queue.update_one(
            {"id": queue_id},
            {"$set": {"status": "CANCELLED",
                      "cancelled_at": datetime.now(timezone.utc).isoformat()}})
        if not res.matched_count:
            raise HTTPException(404, "Kayıt bulunamadı")
        return {"ok": True}

    return router
