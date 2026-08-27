"""Anlık Re-Price Olay Köprüsü — rezervasyon/iptal/denial anında merdivenleri tetikler."""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)


async def trigger_instant_reprice(db, pid: str, reason: str, ref: str = ""):
    from routes.revenue_ext.lastday_ladder import scan_property as ladder_scan
    from routes.revenue_ext.ramp_ladder import scan_property as ramp_scan
    t0 = datetime.now(timezone.utc)
    try:
        l = await ladder_scan(db, pid)
        r = await ramp_scan(db, pid)
        actions = len(l.get("actions", [])) + len(r.get("actions", []))
        await db.reprice_events.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "reason": reason, "ref": ref,
            "actions": actions,
            "latency_ms": int((datetime.now(timezone.utc) - t0).total_seconds() * 1000),
            "created_at": t0.isoformat()})
        logger.info("Instant reprice %s (%s): %s aksiyon", pid, reason, actions)
    except Exception as ex:
        logger.warning("Instant reprice error: %s", ex)


def fire_reprice(db, pid: str, reason: str, ref: str = ""):
    """Ateşle-unut: çağıran akışı asla bloklamaz."""
    try:
        asyncio.create_task(trigger_instant_reprice(db, pid, reason, ref))
    except Exception:
        pass


def create_reprice_bridge_router(db, require_roles):
    router = APIRouter(prefix="/reprice-bridge", tags=["reprice-bridge"])

    @router.get("/{pid}/events")
    async def events(pid: str, _u: dict = Depends(require_roles("admin", "manager"))):
        ev = await db.reprice_events.find({"property_id": pid}, {"_id": 0}).sort(
            "created_at", -1).to_list(30)
        return {"events": ev, "total": len(ev)}

    @router.post("/{pid}/trigger")
    async def manual(pid: str, _u: dict = Depends(require_roles("admin", "manager"))):
        await trigger_instant_reprice(db, pid, "manual_test")
        ev = await db.reprice_events.find_one({"property_id": pid}, {"_id": 0},
                                              sort=[("created_at", -1)])
        return {"ok": True, "event": ev}

    return router
