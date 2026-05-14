"""
Audit Trail Routes
- Read-only visibility into every RBAC-denied request.
- Used by the Admin-only Audit Trail Panel for enterprise security monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Optional

from auth import require_perm, get_current_user


def create_audit_trail_router(db):
    router = APIRouter()

    def _admin_only(user: dict):
        # Audit trail is admin-only. RBAC v2 "settings_roles_view" also grants access.
        if user.get("role") == "admin":
            return True
        return False

    @router.get("/audit-trail")
    async def list_audit_trail(
        request: Request,
        user_email: str = "",
        result: str = "",
        path_contains: str = "",
        days: int = 7,
        limit: int = 200,
        current_user: dict = Depends(get_current_user),
    ):
        """Return the most recent audit trail entries, filterable."""
        if not _admin_only(current_user):
            raise HTTPException(status_code=403, detail="Admin only")

        query: dict = {}
        if user_email:
            query["user_email"] = {"$regex": user_email, "$options": "i"}
        if result:
            query["result"] = result
        if path_contains:
            query["path"] = {"$regex": path_contains, "$options": "i"}
        if days and days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query["ts"] = {"$gte": cutoff}

        rows = await (
            db.audit_trail.find(query, {"_id": 0})
            .sort("ts", -1)
            .limit(min(max(limit, 1), 1000))
            .to_list(length=1000)
        )
        return rows

    @router.get("/audit-trail/stats")
    async def audit_stats(
        days: int = 7,
        current_user: dict = Depends(get_current_user),
    ):
        """Aggregated counters for the Audit Trail dashboard header."""
        if not _admin_only(current_user):
            raise HTTPException(status_code=403, detail="Admin only")

        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(days, 1))).isoformat()
        base_match = {"ts": {"$gte": cutoff}}

        total = await db.audit_trail.count_documents(base_match)
        denied = await db.audit_trail.count_documents({**base_match, "result": "denied"})

        # Top offenders (users with most denials)
        top_users_cur = db.audit_trail.aggregate([
            {"$match": {**base_match, "result": "denied"}},
            {"$group": {
                "_id": {"email": "$user_email", "role": "$user_role", "name": "$user_name"},
                "count": {"$sum": 1},
                "last_attempt": {"$max": "$ts"},
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ])
        top_users = []
        async for row in top_users_cur:
            top_users.append({
                "email": (row["_id"] or {}).get("email") or "unknown",
                "role": (row["_id"] or {}).get("role") or "—",
                "name": (row["_id"] or {}).get("name") or "—",
                "count": row["count"],
                "last_attempt": row["last_attempt"],
            })

        # Top blocked paths
        top_paths_cur = db.audit_trail.aggregate([
            {"$match": {**base_match, "result": "denied"}},
            {"$group": {
                "_id": "$path",
                "count": {"$sum": 1},
                "unique_users": {"$addToSet": "$user_email"},
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ])
        top_paths = []
        async for row in top_paths_cur:
            top_paths.append({
                "path": row["_id"] or "unknown",
                "count": row["count"],
                "unique_users": len(row.get("unique_users") or []),
            })

        # Daily trend (deny count per day)
        trend_cur = db.audit_trail.aggregate([
            {"$match": {**base_match, "result": "denied"}},
            {"$group": {
                "_id": {"$substr": ["$ts", 0, 10]},  # YYYY-MM-DD
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id": 1}},
        ])
        trend = []
        async for row in trend_cur:
            trend.append({"date": row["_id"], "count": row["count"]})

        # Most-attempted missing permissions
        perm_cur = db.audit_trail.aggregate([
            {"$match": {**base_match, "result": "denied"}},
            {"$unwind": "$missing_perms"},
            {"$group": {
                "_id": "$missing_perms",
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ])
        top_perms = []
        async for row in perm_cur:
            top_perms.append({"perm": row["_id"], "count": row["count"]})

        return {
            "window_days": days,
            "total_events": total,
            "denied_events": denied,
            "allowed_events": max(total - denied, 0),
            "top_users": top_users,
            "top_paths": top_paths,
            "trend": trend,
            "top_missing_perms": top_perms,
        }

    @router.delete("/audit-trail/purge")
    async def purge_old_entries(
        older_than_days: int = 90,
        current_user: dict = Depends(get_current_user),
    ):
        """Purge entries older than N days (admin-only retention control)."""
        if not _admin_only(current_user):
            raise HTTPException(status_code=403, detail="Admin only")
        if older_than_days < 7:
            raise HTTPException(status_code=400, detail="Cannot purge entries newer than 7 days")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        result = await db.audit_trail.delete_many({"ts": {"$lt": cutoff}})
        return {"deleted": result.deleted_count, "cutoff": cutoff}

    return router
