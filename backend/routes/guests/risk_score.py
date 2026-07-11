"""
Guest Risk Score (iter 406) — flags risky guests (no-show / cancellation /
chargeback history) on upcoming arrivals so front desk can request deposits.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta, date
import logging

logger = logging.getLogger(__name__)


def _level(score: int) -> str:
    return "high" if score >= 60 else "medium" if score >= 30 else "low"


def _action(level: str) -> str:
    return {"high": "Ön ödeme veya kart pre-auth zorunlu tutun",
            "medium": "Depozito / kart bilgisi isteyin",
            "low": "Standart işlem"}[level]


def create_guest_risk_router(db, require_roles):
    router = APIRouter()

    async def _risk_for(email: str) -> dict:
        email = (email or "").lower()
        if not email:
            return {"score": 0, "level": "low", "reasons": [], "action": _action("low")}
        hist = await db.bookings.find(
            {"guest_email": email},
            {"_id": 0, "id": 1, "status": 1, "no_show_collected": 1, "no_show_charged": 1}).to_list(500)
        no_shows = sum(1 for b in hist if b.get("status") == "no_show")
        cancels = sum(1 for b in hist if b.get("status") == "cancelled")
        completed = sum(1 for b in hist if b.get("status") in ("checked_out", "completed"))
        unpaid_ns = sum(1 for b in hist if b.get("no_show_charged") and not b.get("no_show_collected"))
        bids = [b["id"] for b in hist]
        chargebacks = await db.chargebacks.count_documents({"booking_id": {"$in": bids}}) if bids else 0

        score = min(no_shows * 30, 60) + min(cancels * 10, 30) + min(chargebacks * 30, 60) + min(unpaid_ns * 10, 20)
        score = max(0, min(100, score - min(completed * 5, 20)))
        reasons = []
        if no_shows:
            reasons.append(f"{no_shows} no-show")
        if cancels:
            reasons.append(f"{cancels} iptal")
        if chargebacks:
            reasons.append(f"{chargebacks} chargeback")
        if unpaid_ns:
            reasons.append(f"{unpaid_ns} tahsil edilememiş no-show ücreti")
        if completed:
            reasons.append(f"{completed} sorunsuz konaklama")
        lvl = _level(score)
        return {"score": score, "level": lvl, "reasons": reasons, "action": _action(lvl),
                "history": {"no_shows": no_shows, "cancellations": cancels,
                            "chargebacks": chargebacks, "completed_stays": completed}}

    @router.get("/guests/risk/arrivals/{property_id}")
    async def risk_arrivals(property_id: str, days_ahead: int = 14,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        days_ahead = min(max(days_ahead, 1), 60)
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        pq = {} if property_id == "all" else {"property_id": property_id}
        arrivals = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "pending_payment", "pending"]},
             "check_in": {"$gte": today, "$lte": horizon}},
            {"_id": 0, "id": 1, "booking_ref": 1, "guest_name": 1, "guest_email": 1,
             "check_in": 1, "check_out": 1, "total_price": 1, "room_type_name": 1}).to_list(1000)
        rows = []
        cache = {}
        for b in arrivals:
            email = (b.get("guest_email") or "").lower()
            if email not in cache:
                cache[email] = await _risk_for(email)
            r = cache[email]
            rows.append({**{k: b.get(k) for k in ["id", "booking_ref", "guest_name", "guest_email",
                                                  "check_in", "check_out", "total_price", "room_type_name"]},
                         **r})
        rows.sort(key=lambda x: -x["score"])
        summary = {"high": 0, "medium": 0, "low": 0}
        for r in rows:
            summary[r["level"]] += 1
        value_at_risk = round(sum(float(r.get("total_price") or 0) for r in rows if r["level"] != "low"), 2)
        return {"property_id": property_id, "days_ahead": days_ahead,
                "rows": rows[:100], "summary": summary, "value_at_risk": value_at_risk}

    @router.get("/guests/risk/{guest_email}")
    async def guest_risk(guest_email: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return {"guest_email": guest_email.lower(), **(await _risk_for(guest_email))}

    return router
