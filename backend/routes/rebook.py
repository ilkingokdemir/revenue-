"""
Quick Re-booking CTA (P1)
-------------------------
30 days after a guest checks out, send them a one-click "stay again" email
that includes their last room type pre-filled and a small loyalty discount.
The email has a tracked link `/rebook/{token}` that lands the guest in the
booking widget with parameters pre-populated.

Endpoints
---------
POST /rebook/sweep                           Cron — find eligible past guests, queue messages
GET  /rebook/{property_id}/dispatches
POST /rebook/dispatches/{id}/clicked         Tracking pixel / link
GET  /rebook/token/{token}                   Public — resolve to widget params
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
import secrets
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def create_rebook_router(db, require_roles):
    router = APIRouter()

    @router.post("/rebook/sweep")
    async def sweep(data: Optional[Dict] = None,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        property_id = body.get("property_id", "")
        days_after = int(body.get("days_after_checkout") or 30)
        # Bookings whose checkout was exactly N days ago
        target = (_today() - timedelta(days=days_after)).isoformat()
        q: Dict = {"check_out": {"$regex": f"^{target}"}, "status": "checked_out"}
        if property_id:
            q["property_id"] = property_id
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(5000)
        queued = 0
        for b in bookings:
            existing = await db.rebook_dispatches.find_one(
                {"booking_id": b["id"]}, {"_id": 0}
            )
            if existing:
                continue
            token = secrets.token_urlsafe(20)
            await db.rebook_dispatches.insert_one({
                "id": str(uuid.uuid4()),
                "token": token,
                "property_id": b.get("property_id", ""),
                "booking_id": b["id"],
                "guest_email": (b.get("guest_email") or "").lower(),
                "guest_name": b.get("guest_name", ""),
                "last_room_type": b.get("room_type", ""),
                "last_check_in": b.get("check_in", ""),
                "last_check_out": b.get("check_out", ""),
                "loyalty_discount_pct": float(body.get("loyalty_discount_pct") or 10.0),
                "channel": "email",
                "scheduled_for": _now(),
                "status": "pending",
                "clicked": False,
                "clicked_at": "",
            })
            queued += 1
        return {"ok": True, "scanned": len(bookings), "queued": queued, "target_date": target}

    @router.get("/rebook/{property_id}/dispatches")
    async def list_disp(property_id: str, days: int = 60,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.rebook_dispatches.find(
            {"property_id": property_id, "scheduled_for": {"$gte": since}}, {"_id": 0}
        ).sort("scheduled_for", -1).to_list(500)
        clicked = sum(1 for r in rows if r.get("clicked"))
        return {"items": rows, "count": len(rows), "clicked": clicked,
                 "click_rate": round(clicked * 100 / max(len(rows), 1), 1)}

    @router.post("/rebook/dispatches/{dispatch_id}/clicked")
    async def click(dispatch_id: str):
        await db.rebook_dispatches.update_one(
            {"id": dispatch_id}, {"$set": {"clicked": True, "clicked_at": _now()}}
        )
        return {"ok": True}

    @router.get("/rebook/token/{token}")
    async def resolve_token(token: str):
        d = await db.rebook_dispatches.find_one({"token": token}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Invalid token")
        await db.rebook_dispatches.update_one(
            {"token": token}, {"$set": {"clicked": True, "clicked_at": _now()}}
        )
        return {
            "property_id": d["property_id"],
            "guest_email": d["guest_email"],
            "guest_name": d["guest_name"],
            "preselect_room_type": d.get("last_room_type", ""),
            "loyalty_discount_pct": d.get("loyalty_discount_pct", 0),
        }

    return router
