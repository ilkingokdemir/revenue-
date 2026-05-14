"""
Automation Analytics Dashboard — ROI per rule.

For each rule:
  - runs in last 30d / 90d
  - estimated time saved (configurable per action type)
  - estimated revenue impact (push_to_ota → OTA bookings, upsell → revenue)

Endpoints:
  GET   /api/automation/v2/analytics            — dashboard
  GET   /api/automation/v2/analytics/{rule_id}  — per-rule deep dive
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException


# Estimated time-saved per action (minutes)
TIME_SAVED_PER_ACTION = {
    "create_task": 5, "create_glitch": 4, "notify_role": 3,
    "amenity_request": 8, "set_room_status": 2, "tag_booking": 2,
    "push_to_ota": 10, "post_to_chat": 2,
}


def create_automation_analytics_router(db, require_roles):
    router = APIRouter(prefix="/automation/v2/analytics")

    @router.get("")
    async def dashboard(days: int = 30,
                        _: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rules = await db.automation_rules.find({}, {"_id": 0}).to_list(200)
        rule_rows = []
        total_runs = 0
        total_minutes = 0
        for rule in rules:
            runs = await db.automation_runs.find(
                {"rule_id": rule["id"], "created_at": {"$gte": since}}, {"_id": 0}
            ).to_list(1000)
            n_runs = len(runs)
            ok_runs = sum(1 for r in runs if r.get("ok"))
            # Time saved
            minutes_saved = 0
            for r in runs:
                for a in r.get("actions") or []:
                    minutes_saved += TIME_SAVED_PER_ACTION.get(a.get("action"), 1) if a.get("ok") else 0
            total_runs += n_runs
            total_minutes += minutes_saved
            rule_rows.append({
                "id": rule["id"], "name": rule["name"],
                "trigger": rule["trigger"], "enabled": rule.get("enabled", True),
                "runs_count": n_runs, "success_count": ok_runs,
                "success_rate": round(ok_runs / max(1, n_runs), 3),
                "minutes_saved": minutes_saved,
                "hours_saved": round(minutes_saved / 60, 1),
            })
        rule_rows.sort(key=lambda r: r["runs_count"], reverse=True)
        return {
            "period_days": days,
            "total_rules": len(rules),
            "total_runs": total_runs,
            "total_hours_saved": round(total_minutes / 60, 1),
            "total_minutes_saved": total_minutes,
            "rules": rule_rows,
        }

    @router.get("/{rule_id}")
    async def deep_dive(rule_id: str, days: int = 90,
                        _: dict = Depends(require_roles("admin", "manager"))):
        rule = await db.automation_rules.find_one({"id": rule_id}, {"_id": 0})
        if not rule:
            raise HTTPException(404, "Rule not found")
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        runs = await db.automation_runs.find(
            {"rule_id": rule_id, "created_at": {"$gte": since}}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        # Per-day series
        by_day: dict = {}
        for r in runs:
            day = r.get("created_at", "")[:10]
            d = by_day.setdefault(day, {"day": day, "runs": 0, "ok": 0})
            d["runs"] += 1
            if r.get("ok"):
                d["ok"] += 1
        series = sorted(by_day.values(), key=lambda x: x["day"])
        return {"rule": rule, "period_days": days,
                "total_runs": len(runs), "series": series,
                "recent_runs": runs[:20]}

    return router
