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

    return router
