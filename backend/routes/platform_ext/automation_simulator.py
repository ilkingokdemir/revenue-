"""
Automation Impact Simulator (iter 415) — dry-run "what if" analysis for motor
parameters: shows how many guests/bookings WOULD be targeted with given
thresholds, without sending anything.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict
import logging

from routes.ai.ai_predictions import _score_cancel_risk, _score_upsell_propensity, _days_between
from routes.ai.upsell_autopilot import _offer_price

logger = logging.getLogger(__name__)

BUCKETS = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]


def _histogram(scores):
    out = []
    for lo, hi in BUCKETS:
        out.append({"bucket": f"{lo}-{hi if hi <= 100 else 100}",
                    "count": sum(1 for s in scores if lo <= s < hi)})
    return out


def create_automation_simulator_router(db, require_roles, risk_for):
    router = APIRouter()

    async def _sim_cancel_save(pq: Dict, params: Dict) -> Dict:
        threshold = int(params.get("risk_threshold", 65))
        discount = float(params.get("discount_pct", 10))
        today = date.today()
        start = (today + timedelta(days=3)).isoformat()
        horizon = (today + timedelta(days=45)).isoformat()
        bookings = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "pending_payment"]},
             "check_in": {"$gte": start, "$lte": horizon}},
            {"_id": 0}).to_list(2000)
        past = await db.bookings.find(
            {**pq, "status": {"$in": ["checked_out", "checked_in"]}},
            {"_id": 0, "total_price": 1, "check_in": 1, "check_out": 1}).limit(200).to_list(200)
        rev = sum(float(p.get("total_price") or 0) for p in past)
        nts = sum(max(1, _days_between(p.get("check_in", ""), p.get("check_out", ""))) for p in past)
        avg_rate = rev / nts if nts else 0
        scores, targets, value = [], 0, 0.0
        for b in bookings:
            guest = await db.guest_profiles.find_one({"id": b.get("guest_id")}, {"_id": 0}) or {}
            s = _score_cancel_risk(b, guest, avg_rate)["score"]
            scores.append(s)
            if s >= threshold:
                targets += 1
                value += float(b.get("total_price") or 0)
        return {"targets": targets, "scanned": len(bookings),
                "value_estimate": round(value, 2),
                "cost_estimate": round(value * discount / 100, 2),
                "histogram": _histogram(scores),
                "detail": f"Skor ≥{threshold} olan {targets} rezervasyona kupon giderdi "
                          f"(risk altındaki gelir ~£{value:,.0f}, maks. kupon maliyeti ~£{value * discount / 100:,.0f})"}

    async def _sim_upsell(pq: Dict, params: Dict) -> Dict:
        min_score = int(params.get("min_score", 60))
        days_ahead = int(params.get("days_ahead", 14))
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        bookings = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "checked_in", "pending_payment"]},
             "check_in": {"$gte": today, "$lte": horizon}},
            {"_id": 0}).to_list(2000)
        scores, targets, value = [], 0, 0.0
        for b in bookings:
            guest = await db.guest_profiles.find_one({"id": b.get("guest_id")}, {"_id": 0}) or {}
            r = _score_upsell_propensity(b, guest)
            scores.append(r["top_score"])
            if r["top_score"] >= min_score:
                targets += 1
                value += _offer_price(r["top_recommendation"], max(int(b.get("nights") or 1), 1))
        return {"targets": targets, "scanned": len(bookings),
                "value_estimate": round(value, 2), "cost_estimate": 0,
                "histogram": _histogram(scores),
                "detail": f"Skor ≥{min_score} ile {days_ahead} günlük pencerede {targets} misafire "
                          f"teklif giderdi (potansiyel upsell geliri ~£{value:,.0f})"}

    async def _sim_deposit(pq: Dict, params: Dict) -> Dict:
        days_ahead = int(params.get("days_ahead", 14))
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()
        arrivals = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "pending_payment", "pending"]},
             "check_in": {"$gte": today, "$lte": horizon},
             "guest_email": {"$nin": [None, ""]}},
            {"_id": 0, "id": 1, "guest_email": 1, "total_price": 1,
             "check_in": 1, "check_out": 1}).to_list(1000)
        scores, targets, value = [], 0, 0.0
        cache = {}
        for b in arrivals:
            email = (b.get("guest_email") or "").lower()
            if email not in cache:
                cache[email] = await risk_for(email)
            r = cache[email]
            scores.append(r["score"])
            if r["level"] == "high":
                targets += 1
                total = float(b.get("total_price") or 0)
                nights = max(1, _days_between(b.get("check_in", ""), b.get("check_out", "")))
                value += round(total / nights, 2) if total > 0 else 50.0
        return {"targets": targets, "scanned": len(arrivals),
                "value_estimate": round(value, 2), "cost_estimate": 0,
                "histogram": _histogram(scores),
                "detail": f"{days_ahead} günlük varış penceresinde {targets} yüksek riskli misafire "
                          f"depozito talebi giderdi (~£{value:,.0f} güvence)"}

    async def _sim_nudge(pq: Dict, params: Dict) -> Dict:
        up_hours = int(params.get("upsell_nudge_hours", 24))
        cp_hours = int(params.get("coupon_nudge_hours", 72))
        now = datetime.now(timezone.utc)
        up_cutoff = (now - timedelta(hours=up_hours)).isoformat()
        cp_cutoff = (now - timedelta(hours=cp_hours)).isoformat()
        up = await db.upsell_offers.count_documents(
            {**pq, "source": "autopilot", "status": "sent",
             "created_at": {"$lt": up_cutoff},
             "viewed_at": {"$in": [None, ""]}, "nudged_at": {"$exists": False}})
        cp = await db.rebook_dispatches.count_documents(
            {**pq, "status": "sent", "clicked": False,
             "scheduled_for": {"$lt": cp_cutoff}, "nudged_at": {"$exists": False}})
        return {"targets": up + cp, "scanned": up + cp,
                "value_estimate": 0, "cost_estimate": 0, "histogram": None,
                "detail": f"Şu an {up} upsell + {cp} kupon hatırlatması giderdi "
                          f"(gecikmeler: {up_hours}s / {cp_hours}s)"}

    async def _sim_review(pq: Dict, params: Dict) -> Dict:
        max_per_run = int(params.get("max_per_run", 10))
        pending = await db.reviews.count_documents({**pq, "response_status": "pending"})
        would = min(pending, max_per_run)
        return {"targets": would, "scanned": pending,
                "value_estimate": 0, "cost_estimate": 0, "histogram": None,
                "detail": f"Bekleyen {pending} yorumdan {would} tanesi bir sonraki çalışmada yanıtlanırdı"}

    SIMULATORS = {
        "cancel_save": _sim_cancel_save,
        "upsell_autopilot": _sim_upsell,
        "deposit_autopilot": _sim_deposit,
        "email_nudge": _sim_nudge,
        "review_autopilot": _sim_review,
    }

    @router.post("/automation/simulate/{job}")
    async def simulate(job: str, data: Dict = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        sim = SIMULATORS.get(job)
        if not sim:
            raise HTTPException(status_code=404, detail=f"Simülasyon desteklenmiyor: {job}")
        body = data or {}
        pid = body.get("property_id", "")
        pq: Dict = {} if not pid or pid == "all" else {"property_id": pid}
        result = await sim(pq, body.get("params") or {})
        return {"job": job, "simulated_at": datetime.now(timezone.utc).isoformat(), **result}

    return router
