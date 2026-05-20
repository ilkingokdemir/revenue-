"""
Guest CRM 360 — Revinate-killer guest insights & segmentation.

Per-guest 360° view aggregated from bookings + reviews + folio history.
Auto-computed segments (VIP, lapsed, advocate, at-risk).
Lifecycle stages (lead → first-time → repeat → champion).
Win-back campaign builder (queues emails for when Resend integrates).

Endpoints:
  GET    /api/crm/profile/{guest_email}             — 360° view
  GET    /api/crm/segments                          — segments dashboard
  GET    /api/crm/winback/candidates                — dormant guests
  POST   /api/crm/winback/queue                     — queue win-back emails
"""
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException


VIP_LIFETIME_VALUE = 5000.0
CHAMPION_STAYS = 5
REPEAT_STAYS = 2
LAPSED_DAYS = 365
DORMANT_DAYS = 180


async def _profile(db, guest_email: str) -> dict:
    bookings = await db.bookings.find(
        {"guest_email": guest_email,
         "status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]}},
        {"_id": 0}
    ).sort("check_in", -1).to_list(200)

    total_stays = len(bookings)
    lifetime_value = round(sum(float(b.get("total_price", 0) or 0) for b in bookings), 2)
    total_nights = sum(int(b.get("nights", 1) or 1) for b in bookings)
    last_stay = bookings[0]["check_in"] if bookings else ""
    first_stay = bookings[-1]["check_in"] if bookings else ""
    properties_visited = sorted({b.get("property_id") for b in bookings if b.get("property_id")})
    sources: dict = {}
    for b in bookings:
        s = b.get("source", "direct") or "direct"
        sources[s] = sources.get(s, 0) + 1

    reviews = await db.reviews.find({"guest_email": guest_email}, {"_id": 0}).to_list(50)
    avg_rating = round(sum(r.get("rating", 0) for r in reviews) / max(1, len(reviews)), 2) if reviews else None

    today = datetime.now(timezone.utc).date()
    days_since_last = None
    if last_stay:
        try:
            days_since_last = (today - datetime.strptime(last_stay, "%Y-%m-%d").date()).days
        except Exception:
            pass

    segments = []
    if total_stays == 0:
        lifecycle = "lead"
    elif total_stays == 1:
        lifecycle = "first-time"
    elif total_stays >= CHAMPION_STAYS:
        lifecycle = "champion"
    elif total_stays >= REPEAT_STAYS:
        lifecycle = "repeat"
    else:
        lifecycle = "guest"

    if lifetime_value >= VIP_LIFETIME_VALUE:
        segments.append("vip")
    if days_since_last is not None and days_since_last > LAPSED_DAYS:
        segments.append("lapsed")
    elif days_since_last is not None and days_since_last > DORMANT_DAYS:
        segments.append("dormant")
    if avg_rating and avg_rating >= 4.5:
        segments.append("advocate")
    if avg_rating and avg_rating <= 3.0:
        segments.append("at-risk")

    guest_name = bookings[0].get("guest_name", "") if bookings else ""
    return {
        "guest_email": guest_email,
        "guest_name": guest_name,
        "lifecycle": lifecycle,
        "segments": segments,
        "stats": {
            "total_stays": total_stays,
            "total_nights": total_nights,
            "lifetime_value": lifetime_value,
            "last_stay": last_stay,
            "first_stay": first_stay,
            "days_since_last_stay": days_since_last,
            "avg_rating": avg_rating,
            "review_count": len(reviews),
            "properties_visited": properties_visited,
            "favorite_source": max(sources.items(), key=lambda x: x[1])[0] if sources else None,
            "source_breakdown": sources,
        },
        "recent_bookings": [
            {k: b.get(k) for k in ["booking_ref", "check_in", "check_out", "total_price",
                                    "property_id", "status"]}
            for b in bookings[:10]
        ],
    }


def create_crm360_router(db, require_roles):
    router = APIRouter(prefix="/crm")

    @router.get("/profile/{guest_email}")
    async def get_profile(guest_email: str,
                          _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await _profile(db, guest_email)

    @router.get("/segments")
    async def list_segments(_: dict = Depends(require_roles("admin", "manager"))):
        emails = await db.bookings.distinct(
            "guest_email",
            {"status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]}}
        )
        buckets: dict = {
            "vip": [], "champion": [], "advocate": [], "repeat": [],
            "first-time": [], "lapsed": [], "dormant": [], "at-risk": [],
        }
        total = 0
        # Limit to first 500 emails for performance
        for em in [e for e in emails if e][:500]:
            p = await _profile(db, em)
            total += 1
            mini = {
                "guest_email": em,
                "guest_name": p["guest_name"],
                "lifecycle": p["lifecycle"],
                "lifetime_value": p["stats"]["lifetime_value"],
                "last_stay": p["stats"]["last_stay"],
                "total_stays": p["stats"]["total_stays"],
            }
            for seg in p["segments"]:
                if seg in buckets:
                    buckets[seg].append(mini)
            if p["lifecycle"] in buckets:
                buckets[p["lifecycle"]].append(mini)
        return {
            "total_guests_scanned": total,
            "segments": {k: {"count": len(v), "members": v[:50]} for k, v in buckets.items()},
        }

    @router.get("/winback/candidates")
    async def winback_candidates(days_inactive: int = 90,
                                 _: dict = Depends(require_roles("admin", "manager"))):
        emails = await db.bookings.distinct(
            "guest_email",
            {"status": {"$in": ["confirmed", "checked_in", "checked_out", "completed"]}}
        )
        candidates = []
        for em in [e for e in emails if e][:1000]:
            p = await _profile(db, em)
            days = p["stats"]["days_since_last_stay"]
            if days and days >= days_inactive:
                candidates.append({
                    "guest_email": em, "guest_name": p["guest_name"],
                    "days_inactive": days, "lifetime_value": p["stats"]["lifetime_value"],
                    "total_stays": p["stats"]["total_stays"], "lifecycle": p["lifecycle"],
                })
        candidates.sort(key=lambda c: c["lifetime_value"], reverse=True)
        return {"count": len(candidates), "candidates": candidates[:200]}

    @router.post("/winback/queue")
    async def winback_queue(body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        emails = body.get("guest_emails") or []
        template = body.get("template", "We miss you! Here's 10% off your next stay.")
        if not emails:
            raise HTTPException(400, "guest_emails required")
        now = datetime.now(timezone.utc).isoformat()
        queued = []
        for em in emails:
            doc = {
                "id": str(uuid.uuid4()), "guest_email": em, "campaign": "winback",
                "template": template, "status": "queued",
                "queued_by": current_user.get("name", ""), "queued_at": now,
            }
            await db.guest_campaigns.insert_one(doc)
            queued.append(em)
        return {"queued_count": len(queued), "queued": queued,
                "note": "Real send requires Resend API key"}

    return router
