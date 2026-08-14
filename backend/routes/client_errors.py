"""Hata Nöbetçisi — frontend ekran hatalarını referans koduyla otomatik toplar.
POST auth'suz (hata girişten önce de olabilir); listeleme admin/manager."""
import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from typing import Dict


def create_client_errors_router(db, require_roles):
    router = APIRouter(prefix="/client-errors", tags=["client-errors"])

    @router.post("")
    async def report(body: Dict):
        now = datetime.now(timezone.utc).isoformat()
        msg = str(body.get("message") or "")[:500]
        if not msg:
            return {"ok": False}
        doc = {
            "ref": str(body.get("ref") or "")[:24],
            "message": msg,
            "stack": str(body.get("stack") or "")[:2000],
            "component_stack": str(body.get("component_stack") or "")[:1500],
            "url": str(body.get("url") or "")[:300],
            "user_agent": str(body.get("user_agent") or "")[:200],
        }
        fp = hashlib.sha1(f"{msg}|{doc['url']}".encode()).hexdigest()[:16]
        existing = await db.client_errors.find_one({"fingerprint": fp, "resolved": {"$ne": True}}, {"_id": 0, "id": 1})
        if existing:
            await db.client_errors.update_one(
                {"id": existing["id"]},
                {"$inc": {"count": 1}, "$set": {"last_seen": now, "last_ref": doc["ref"]}})
            return {"ok": True, "deduped": True}
        await db.client_errors.insert_one({
            "id": str(uuid.uuid4())[:8], "fingerprint": fp, **doc,
            "count": 1, "resolved": False, "first_seen": now, "last_seen": now, "last_ref": doc["ref"]})
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "warning",
            "title": "Hata Nöbetçisi: yeni ekran hatası yakalandı",
            "message": f"[{doc['ref']}] {msg[:120]} — sayfa: {doc['url'][:80]}. Detay: Hata Nöbetçisi paneli.",
            "category": "system", "target_user": "", "target_role": "admin",
            "link_to": "error-sentinel", "priority": "high", "read": False,
            "created_by": "Hata Nöbetçisi", "created_at": now})
        return {"ok": True, "deduped": False}

    @router.get("")
    async def list_errors(include_resolved: bool = False,
                          _u: dict = Depends(require_roles("admin", "manager"))):
        q = {} if include_resolved else {"resolved": {"$ne": True}}
        items = await db.client_errors.find(q, {"_id": 0}).sort("last_seen", -1).to_list(100)
        return {"items": items, "count": len(items)}

    @router.post("/{eid}/resolve")
    async def resolve(eid: str, _u: dict = Depends(require_roles("admin", "manager"))):
        await db.client_errors.update_one(
            {"id": eid}, {"$set": {"resolved": True, "resolved_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True}

    return router
