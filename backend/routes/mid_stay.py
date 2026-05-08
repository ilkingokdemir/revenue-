"""
Mid-stay Surveys (P1)
---------------------
Pulse survey sent on day 2 of a multi-night stay to catch issues *while we
can still fix them*, before the post-stay review hits Google or Booking.com.

Mechanic
--------
* Cron sweeper enrolls every booking that has slept 2 nights and has 2+ nights
  remaining. One-time invite stored in `mid_stay_invites`.
* Guest opens the public link with `invite_id`, submits 1-5 score + freeform
  comment + an optional category (room | clean | food | front_desk | wifi |
  noise | other). Result lands in `mid_stay_responses`.
* If score <= 3 a `service_recovery_tickets` row is auto-opened so a manager
  is paged and can compensate before checkout.

Endpoints
---------
POST /mid-stay/sweep                     Cron — enroll eligible bookings
GET  /mid-stay/{property_id}/invites     Recent invites
GET  /mid-stay/invite/{invite_id}        Public — fetch survey context
POST /mid-stay/invite/{invite_id}/submit Public — submit response
GET  /mid-stay/{property_id}/responses   Recent responses (with NPS-style stats)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def create_mid_stay_router(db, require_roles):
    router = APIRouter()

    @router.post("/mid-stay/sweep")
    async def sweep(data: Optional[Dict] = None,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Find bookings on day 2+ with 2+ nights remaining; enroll once."""
        property_id = (data or {}).get("property_id", "")
        q: Dict = {"status": "checked_in"}
        if property_id:
            q["property_id"] = property_id
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(5000)
        today = _today().isoformat()
        enrolled = 0
        for b in bookings:
            ci = (b.get("check_in") or "")[:10]
            co = (b.get("check_out") or "")[:10]
            if not ci or not co:
                continue
            try:
                ci_d = date.fromisoformat(ci)
                co_d = date.fromisoformat(co)
            except ValueError:
                continue
            slept = (_today() - ci_d).days
            remaining = (co_d - _today()).days
            if slept < 2 or remaining < 2:
                continue
            existing = await db.mid_stay_invites.find_one({"booking_id": b["id"]}, {"_id": 0})
            if existing:
                continue
            await db.mid_stay_invites.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": b.get("property_id", ""),
                "booking_id": b["id"],
                "guest_name": b.get("guest_name", ""),
                "guest_email": b.get("guest_email", ""),
                "room_number": b.get("room_number", ""),
                "check_in": ci, "check_out": co,
                "sent_at": _now(),
                "responded": False,
            })
            enrolled += 1
        return {"ok": True, "scanned": len(bookings), "enrolled": enrolled, "today": today}

    @router.get("/mid-stay/{property_id}/invites")
    async def list_invites(property_id: str, days: int = 14,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.mid_stay_invites.find(
            {"property_id": property_id, "sent_at": {"$gte": since}}, {"_id": 0}
        ).sort("sent_at", -1).to_list(500)
        responded = sum(1 for r in rows if r.get("responded"))
        rate = round(responded * 100 / max(len(rows), 1), 1)
        return {"items": rows, "count": len(rows), "responded": responded, "response_rate": rate}

    @router.get("/mid-stay/invite/{invite_id}")
    async def get_invite(invite_id: str):
        invite = await db.mid_stay_invites.find_one({"id": invite_id}, {"_id": 0})
        if not invite:
            raise HTTPException(404, "Survey link not found or expired")
        prop = await db.properties.find_one({"id": invite["property_id"]}, {"_id": 0}) or {}
        return {
            "invite_id": invite_id,
            "guest_name": invite["guest_name"],
            "hotel_name": prop.get("name", ""),
            "room_number": invite.get("room_number", ""),
            "already_responded": invite.get("responded", False),
        }

    @router.post("/mid-stay/invite/{invite_id}/submit")
    async def submit(invite_id: str, data: Dict):
        invite = await db.mid_stay_invites.find_one({"id": invite_id}, {"_id": 0})
        if not invite:
            raise HTTPException(404, "Survey link not found")
        if invite.get("responded"):
            raise HTTPException(400, "Response already recorded for this invite")
        score = int(data.get("score") or 0)
        if score < 1 or score > 5:
            raise HTTPException(400, "score must be 1-5")
        category = (data.get("category") or "other").strip()
        comment = (data.get("comment") or "").strip()[:1000]

        response = {
            "id": str(uuid.uuid4()),
            "invite_id": invite_id,
            "property_id": invite["property_id"],
            "booking_id": invite["booking_id"],
            "guest_name": invite["guest_name"],
            "room_number": invite.get("room_number", ""),
            "score": score,
            "category": category,
            "comment": comment,
            "submitted_at": _now(),
        }
        await db.mid_stay_responses.insert_one(dict(response))
        await db.mid_stay_invites.update_one({"id": invite_id}, {"$set": {"responded": True, "responded_at": _now()}})

        # Auto-recovery if low
        if score <= 3:
            await db.service_recovery_tickets.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": invite["property_id"],
                "booking_id": invite["booking_id"],
                "guest_name": invite["guest_name"],
                "room_number": invite.get("room_number", ""),
                "category": category,
                "score": score,
                "comment": comment,
                "source": "mid_stay_survey",
                "status": "open",
                "priority": "high" if score <= 2 else "medium",
                "opened_at": _now(),
            })
        response.pop("_id", None)
        return {"ok": True, "response": response, "service_recovery_opened": score <= 3}

    @router.get("/mid-stay/{property_id}/responses")
    async def list_responses(property_id: str, days: int = 30,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.mid_stay_responses.find(
            {"property_id": property_id, "submitted_at": {"$gte": since}}, {"_id": 0}
        ).sort("submitted_at", -1).to_list(500)
        if not rows:
            return {"items": [], "count": 0, "avg_score": 0, "by_category": {}, "low_count": 0}
        avg = round(sum(r["score"] for r in rows) / len(rows), 2)
        by_cat: Dict[str, Dict[str, float]] = {}
        for r in rows:
            c = r.get("category") or "other"
            cell = by_cat.setdefault(c, {"count": 0, "sum": 0})
            cell["count"] += 1
            cell["sum"] += r["score"]
        for c, v in by_cat.items():
            v["avg"] = round(v["sum"] / v["count"], 2)
        low_count = sum(1 for r in rows if r["score"] <= 3)
        return {"items": rows, "count": len(rows), "avg_score": avg, "by_category": by_cat, "low_count": low_count}

    return router
