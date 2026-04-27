"""
AI Predictions — Cancellation Risk Scoring + Upsell Propensity Scoring.

Hybrid approach: rule-based signals + GPT-5.2 pattern-match via Emergent LLM key.
Heuristic-first for speed/low-cost; LLM only when admin explicitly asks "explain".

Cancellation Risk: For each confirmed future booking, compute risk [0..100] from
features like:
  - days_to_arrival (shorter = less risky)
  - lead_time_days (longer lead_time booked = higher cancel risk)
  - price_per_night vs property avg (extreme high = higher risk)
  - channel (OTA > direct historically)
  - unpaid deposit (huge risk)
  - modification_count (more edits = higher risk)
  - guest lifetime_stays (repeat = low risk)
  - season / DOW arrival

Upsell Propensity: For each upcoming arrival, score [0..100] receptivity to
upsells per category (room_upgrade / late_checkout / breakfast / spa / transport):
  - stay_length (longer = more likely to upgrade)
  - room category (standard can upgrade; suite cannot)
  - channel (direct = higher intent)
  - guest occasion tag (honeymoon/anniversary → high)
  - lifetime_revenue (past spend = predictor)
  - loyalty tier
  - LOS > 3 for late_checkout=not applicable
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date, timedelta
from typing import Optional, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class RiskExplainRequest(BaseModel):
    booking_id: str


def _days_between(d1: str, d2: str) -> int:
    try:
        a = datetime.strptime(d1, "%Y-%m-%d").date()
        b = datetime.strptime(d2, "%Y-%m-%d").date()
        return (b - a).days
    except Exception:
        return 0


def _score_cancel_risk(booking: dict, guest: dict, property_avg_rate: float) -> dict:
    """Rule-based cancellation risk in [0..100]."""
    score = 30  # baseline
    signals = []

    today = date.today().isoformat()
    days_to = _days_between(today, booking.get("check_in", today))
    lead_time = _days_between(booking.get("created_at", today)[:10], booking.get("check_in", today))

    # Lead time — longer lead times cancel more (well-known industry fact)
    if lead_time > 90:
        score += 25; signals.append({"name": "Uzun lead time (>90 gün)", "impact": +25})
    elif lead_time > 30:
        score += 12; signals.append({"name": "Orta lead time (30-90 gün)", "impact": +12})
    elif lead_time < 3:
        score -= 10; signals.append({"name": "Kısa lead time (<3 gün)", "impact": -10})

    # Proximity to arrival
    if days_to <= 2:
        score -= 20; signals.append({"name": "Varış yakın (≤2 gün)", "impact": -20})
    elif days_to <= 7:
        score -= 10; signals.append({"name": "Varış 1 hafta içi", "impact": -10})

    # Channel risk
    ch = (booking.get("channel") or booking.get("source") or "direct").lower()
    if "booking" in ch or "expedia" in ch or "agoda" in ch:
        score += 12; signals.append({"name": f"OTA kanalı ({ch})", "impact": +12})
    elif "direct" in ch or "website" in ch or "web" in ch:
        score -= 8; signals.append({"name": "Direkt rezervasyon", "impact": -8})

    # Payment status
    pay_status = (booking.get("payment_status") or "").lower()
    if pay_status in ("unpaid", "pending", "manual", ""):
        score += 18; signals.append({"name": "Ödeme alınmamış", "impact": +18})
    elif pay_status == "paid":
        score -= 15; signals.append({"name": "Peşin ödenmiş", "impact": -15})

    # Modification count
    mods = int(booking.get("modification_count") or 0)
    if mods >= 3:
        score += 15; signals.append({"name": f"Sık değiştirilmiş ({mods}x)", "impact": +15})
    elif mods == 2:
        score += 8; signals.append({"name": "2x değiştirilmiş", "impact": +8})

    # Price deviation (too-cheap flash deals cancel more)
    nights = max(1, _days_between(booking.get("check_in", today), booking.get("check_out", today)))
    ppn = (booking.get("total_price") or 0) / nights
    if property_avg_rate > 0:
        deviation = (ppn - property_avg_rate) / property_avg_rate
        if deviation < -0.3:
            score += 10; signals.append({"name": "Ortalamanın %30+ altında fiyat", "impact": +10})
        elif deviation > 0.5:
            score += 5; signals.append({"name": "Çok yüksek fiyat (+%50)", "impact": +5})

    # Guest loyalty (repeat customer = low risk)
    lifetime = int(guest.get("lifetime_stays") or 0)
    if lifetime >= 3:
        score -= 18; signals.append({"name": f"{lifetime}+ sadık misafir", "impact": -18})
    elif lifetime == 1:
        score -= 6; signals.append({"name": "Daha önce konaklamış", "impact": -6})

    # VIP
    tags = booking.get("tags", []) or []
    if "vip" in tags or "platinum" in tags:
        score -= 10; signals.append({"name": "VIP/Platinum", "impact": -10})

    score = max(0, min(100, score))
    if score >= 65:
        band = "high"
    elif score >= 40:
        band = "medium"
    else:
        band = "low"

    return {"score": score, "band": band, "signals": signals}


def _score_upsell_propensity(booking: dict, guest: dict) -> dict:
    """Per-category upsell propensity scores [0..100]."""
    today = date.today().isoformat()
    nights = max(1, _days_between(booking.get("check_in", today), booking.get("check_out", today)))
    ch = (booking.get("channel") or "direct").lower()
    occasion = (booking.get("occasion") or guest.get("occasion") or "").lower()
    tags = booking.get("tags", []) or []
    lifetime_rev = float(guest.get("lifetime_revenue") or 0)
    tier = (guest.get("loyalty_tier") or "bronze").lower()
    room_type = (booking.get("room_type_name") or "").lower()

    # Base
    direct_boost = 8 if ("direct" in ch or "web" in ch) else 0
    occ_boost = 15 if occasion in ("honeymoon", "anniversary", "birthday", "celebration") else 0
    tier_boost = {"silver": 5, "gold": 10, "platinum": 15}.get(tier, 0)
    rev_boost = min(15, int(lifetime_rev / 500))  # up to +15

    def clamp(x): return max(0, min(100, x))

    scores = {}

    # Room upgrade — high when lower tier room + short stay
    up_score = 25 + direct_boost + occ_boost + tier_boost + rev_boost
    if "suite" in room_type or "penthouse" in room_type:
        up_score = 0  # already top tier
    elif "standard" in room_type or "double" in room_type:
        up_score += 15
    if nights <= 3:
        up_score += 5
    scores["room_upgrade"] = clamp(up_score)

    # Late checkout
    lc = 35 + direct_boost + tier_boost
    if "business" in ch.lower() or "corporate" in tags:
        lc += 15
    if nights >= 2:
        lc += 5
    scores["late_checkout"] = clamp(lc)

    # Breakfast
    bf = 40 + occ_boost + rev_boost
    if "family" in tags or "group" in tags:
        bf += 15
    scores["breakfast"] = clamp(bf)

    # Spa / wellness
    spa = 20 + occ_boost + tier_boost + rev_boost
    if occasion in ("honeymoon", "anniversary"):
        spa += 20
    if nights >= 3:
        spa += 10
    scores["spa"] = clamp(spa)

    # Airport transport
    tr = 30 + direct_boost
    if "international" in tags or "long_haul" in tags:
        tr += 20
    scores["transport"] = clamp(tr)

    # Top recommendation
    top_cat = max(scores, key=scores.get)
    return {
        "scores": scores,
        "top_recommendation": top_cat,
        "top_score": scores[top_cat],
    }


def create_ai_predictions_router(db, require_roles, LlmChat=None, UserMessage=None):
    router = APIRouter()

    @router.get("/ai-predictions/cancel-risk/{property_id}")
    async def cancel_risk_list(property_id: str, days_ahead: int = 60,
                               min_score: int = 40, limit: int = 100,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Score all upcoming confirmed bookings for cancellation risk."""
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()

        bookings = await db.bookings.find({
            "property_id": property_id,
            "status": {"$in": ["confirmed", "pending_payment"]},
            "check_in": {"$gte": today, "$lte": horizon},
        }, {"_id": 0}).limit(500).to_list(500)

        # Property avg rate (cheap computation)
        past = await db.bookings.find({
            "property_id": property_id,
            "status": {"$in": ["checked_out", "checked_in"]},
        }, {"_id": 0, "total_price": 1, "check_in": 1, "check_out": 1}).limit(200).to_list(200)
        total_rev, total_nights = 0.0, 0
        for p in past:
            n = max(1, _days_between(p.get("check_in", ""), p.get("check_out", "")))
            total_rev += float(p.get("total_price") or 0)
            total_nights += n
        avg_rate = (total_rev / total_nights) if total_nights else 0

        scored = []
        for b in bookings:
            guest = await db.guest_profiles.find_one(
                {"id": b.get("guest_id")}, {"_id": 0}
            ) or {}
            r = _score_cancel_risk(b, guest, avg_rate)
            if r["score"] < min_score:
                continue
            scored.append({
                "booking_id": b.get("id"),
                "booking_ref": b.get("booking_ref"),
                "guest_name": b.get("guest_name"),
                "check_in": b.get("check_in"),
                "check_out": b.get("check_out"),
                "total_price": b.get("total_price"),
                "currency": b.get("currency", "GBP"),
                "channel": b.get("channel"),
                "payment_status": b.get("payment_status"),
                **r,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        scored = scored[:limit]

        # Aggregate
        by_band = {"high": 0, "medium": 0, "low": 0}
        at_risk_revenue = 0
        for s in scored:
            by_band[s["band"]] = by_band.get(s["band"], 0) + 1
            if s["band"] == "high":
                at_risk_revenue += float(s.get("total_price") or 0)

        return {
            "rows": scored,
            "count": len(scored),
            "by_band": by_band,
            "at_risk_revenue": round(at_risk_revenue, 2),
            "avg_rate_used": round(avg_rate, 2),
            "window_days": days_ahead,
        }

    @router.get("/ai-predictions/cancel-risk/booking/{booking_id}")
    async def cancel_risk_booking(booking_id: str,
                                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        guest = await db.guest_profiles.find_one({"id": b.get("guest_id")}, {"_id": 0}) or {}
        return _score_cancel_risk(b, guest, 0)

    @router.post("/ai-predictions/cancel-risk/{booking_id}/save-offer")
    async def trigger_save_offer(booking_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Queue a save-offer campaign (10% discount voucher + personal email draft)."""
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        voucher = f"STAY-{booking_id[:6].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        await db.save_offers.insert_one({
            "id": voucher,
            "booking_id": booking_id,
            "property_id": b.get("property_id"),
            "guest_name": b.get("guest_name"),
            "guest_email": b.get("guest_email"),
            "discount_pct": 10,
            "status": "queued",
            "voucher_code": voucher,
            "created_at": now,
            "created_by": current_user.get("email"),
        })
        await db.bookings.update_one(
            {"id": booking_id},
            {"$set": {"save_offer_sent_at": now, "save_offer_code": voucher}}
        )
        return {
            "booking_id": booking_id,
            "voucher_code": voucher,
            "discount_pct": 10,
            "status": "queued",
            "note": "Ready for email dispatch. Real send happens via Resend once key is configured.",
        }

    @router.get("/ai-predictions/upsell/{property_id}")
    async def upsell_list(property_id: str, days_ahead: int = 14,
                          category: Optional[str] = None, min_score: int = 50,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Score upcoming arrivals for per-category upsell receptivity."""
        today = date.today().isoformat()
        horizon = (date.today() + timedelta(days=days_ahead)).isoformat()

        bookings = await db.bookings.find({
            "property_id": property_id,
            "status": {"$in": ["confirmed", "pending_payment", "checked_in"]},
            "check_in": {"$gte": today, "$lte": horizon},
        }, {"_id": 0}).limit(500).to_list(500)

        rows = []
        for b in bookings:
            guest = await db.guest_profiles.find_one(
                {"id": b.get("guest_id")}, {"_id": 0}
            ) or {}
            r = _score_upsell_propensity(b, guest)
            score = r["scores"].get(category, r["top_score"]) if category else r["top_score"]
            if score < min_score:
                continue
            rows.append({
                "booking_id": b.get("id"),
                "booking_ref": b.get("booking_ref"),
                "guest_name": b.get("guest_name"),
                "check_in": b.get("check_in"),
                "check_out": b.get("check_out"),
                "room_type": b.get("room_type_name"),
                "loyalty_tier": guest.get("loyalty_tier", "bronze"),
                **r,
            })

        # Sort by filtered category score if given, else top_score
        def sort_key(x):
            return x["scores"].get(category, x["top_score"]) if category else x["top_score"]
        rows.sort(key=sort_key, reverse=True)

        # KPI aggregations
        total = len(rows)
        by_top_rec = {}
        for r in rows:
            by_top_rec[r["top_recommendation"]] = by_top_rec.get(r["top_recommendation"], 0) + 1

        return {
            "rows": rows[:100],
            "count": total,
            "by_top_recommendation": by_top_rec,
            "window_days": days_ahead,
            "category_filter": category,
        }

    @router.post("/ai-predictions/upsell/{booking_id}/send-offer")
    async def upsell_send(booking_id: str, category: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Queue an upsell offer for a specific category."""
        b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        valid_cats = {"room_upgrade", "late_checkout", "breakfast", "spa", "transport"}
        if category not in valid_cats:
            raise HTTPException(400, f"Invalid category. Must be one of: {sorted(valid_cats)}")
        now = datetime.now(timezone.utc).isoformat()
        offer_id = f"UP-{booking_id[:6].upper()}-{category[:3].upper()}"
        await db.upsell_offers.insert_one({
            "id": offer_id,
            "booking_id": booking_id,
            "property_id": b.get("property_id"),
            "category": category,
            "status": "queued",
            "created_at": now,
            "created_by": current_user.get("email"),
        })
        return {"offer_id": offer_id, "booking_id": booking_id, "category": category, "status": "queued"}

    return router
