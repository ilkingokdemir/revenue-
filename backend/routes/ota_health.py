"""
OTA Health Dashboard (Iter 161) — single composite score pulling from:
  - Parity Monitor (Iter 160)
  - Commission Reconciliation (Iter 156)
  - Payment Mix / Direct Capture (Iter 155)
  - Channel booking volume / revenue share (live query)
Returns A+/A/B/C/D/F grade plus 4 sub-scores for board reporting.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


def create_ota_health_router(db, require_roles):
    router = APIRouter()

    @router.get("/ota-health/{property_id}")
    async def ota_health(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        period_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        period_end = now.strftime("%Y-%m-%d")

        pq = {} if property_id == "all" else {"property_id": property_id}

        # --- 1. Parity (reuse same logic as channel_parity.py, lite version)
        channels = await db.channel_connections.find(
            {} if property_id == "all" else {"property_id": property_id},
            {"_id": 0},
        ).to_list(30)
        direct = next((c for c in channels if c.get("channel_id") == "direct"), None)
        rt = await db.room_types.find_one(pq, {"_id": 0})
        base_rate = float(rt.get("base_rate", 100) or 100) if rt else 100.0

        # Compute parity across next 14 days, ±5% tolerance
        parity_days = 14
        parity_tolerance = 5.0
        parity_violations = 0
        parity_total_checks = 0
        for i in range(parity_days):
            d = (now + timedelta(days=i)).strftime("%Y-%m-%d")
            override = await db.rate_overrides.find_one(
                {"property_id": property_id, "date": d} if property_id != "all" else {"date": d},
                {"_id": 0},
            )
            base = float(override.get("custom_rate", base_rate)) if override else base_rate
            direct_rate = base
            if direct:
                rule = direct.get("rate_rule", "same")
                markup = float(direct.get("rate_markup_pct", 0))
                if rule == "markup":
                    direct_rate = round(base * (1 + markup / 100), 2)
                elif rule == "undercut":
                    direct_rate = round(base * (1 - markup / 100), 2)
            for ch in channels:
                if ch.get("channel_id") == "direct":
                    continue
                rule = ch.get("rate_rule", "same")
                markup = float(ch.get("rate_markup_pct", 0))
                if rule == "markup":
                    ch_rate = round(base * (1 + markup / 100), 2)
                elif rule == "undercut":
                    ch_rate = round(base * (1 - markup / 100), 2)
                else:
                    ch_rate = base
                parity_total_checks += 1
                if direct_rate > 0 and abs((ch_rate - direct_rate) / direct_rate * 100) > parity_tolerance:
                    parity_violations += 1
        parity_pct = round((parity_total_checks - parity_violations) / parity_total_checks * 100, 1) if parity_total_checks else 100.0
        parity_score = int(parity_pct)  # 100 parity = score 100

        # --- 2. Commission Match (reuse from commission_recon.py recent statements)
        stmts = await db.commission_statements.find(pq, {"_id": 0}).sort("uploaded_at", -1).limit(6).to_list(6)
        total_lines = sum((s.get("summary") or {}).get("lines_total", 0) for s in stmts)
        var_lines = sum((s.get("summary") or {}).get("variance", 0) + (s.get("summary") or {}).get("unmatched", 0) for s in stmts)
        commission_pct = round((total_lines - var_lines) / total_lines * 100, 1) if total_lines else 100.0
        commission_score = int(commission_pct) if total_lines else 85  # no data → neutral

        # --- 3. Direct Capture (payment mix last 30d)
        booking_ids = [b["id"] for b in await db.bookings.find(pq, {"_id": 0, "id": 1}).to_list(20000)]
        payments = await db.folio_items.find({
            "booking_id": {"$in": booking_ids}, "type": "payment",
            "created_at": {"$gte": period_start, "$lte": period_end + "T99:99:99"},
        }, {"_id": 0}).to_list(20000)
        buckets = {"cash": 0.0, "card": 0.0, "bank_transfer": 0.0, "channel_collection": 0.0}
        for p in payments:
            m = (p.get("payment_method") or p.get("category") or "card").lower()
            if m in buckets:
                buckets[m] += float(p.get("amount", 0))
        total_pay = sum(buckets.values())
        direct_sum = buckets["cash"] + buckets["card"] + buckets["bank_transfer"]
        direct_pct = round((direct_sum / total_pay) * 100, 1) if total_pay > 0 else 0.0
        # target 80%+ direct
        direct_score = min(100, int((direct_pct / 80) * 100)) if total_pay > 0 else 50

        # --- 4. Channel mix balance (no single OTA > 60% of bookings)
        bookings_30d = await db.bookings.find({
            **pq,
            "check_in": {"$gte": period_start, "$lte": period_end},
            "status": {"$nin": ["cancelled", "no_show"]},
        }, {"_id": 0, "source": 1, "total_price": 1}).to_list(20000)
        channel_rev = {}
        for b in bookings_30d:
            src = (b.get("source") or "Direct").strip() or "Direct"
            channel_rev[src] = channel_rev.get(src, 0.0) + float(b.get("total_price") or 0)
        total_rev = sum(channel_rev.values())
        max_share = max((v / total_rev for v in channel_rev.values()), default=0) if total_rev > 0 else 0
        # If any single channel > 60%, over-concentrated. Score linearly: 60% → 100, 100% → 0.
        if total_rev == 0:
            balance_score = 50
        elif max_share <= 0.60:
            balance_score = 100
        else:
            balance_score = max(0, int(100 - (max_share - 0.60) * 250))
        mix_pct = round(max_share * 100, 1)

        # --- Overall
        overall = round((parity_score + commission_score + direct_score + balance_score) / 4)
        if overall >= 90: grade = "A+"
        elif overall >= 80: grade = "A"
        elif overall >= 70: grade = "B"
        elif overall >= 60: grade = "C"
        elif overall >= 50: grade = "D"
        else: grade = "F"

        sorted_channels = sorted(
            [{"channel": k, "revenue": round(v, 2), "share_pct": round(v / total_rev * 100, 1) if total_rev > 0 else 0}
             for k, v in channel_rev.items()],
            key=lambda r: -r["revenue"],
        )

        return {
            "property_id": property_id,
            "as_of": now.isoformat(),
            "period_start": period_start, "period_end": period_end,
            "overall_score": overall,
            "grade": grade,
            "metrics": [
                {"key": "parity", "label": "Rate Parity", "score": parity_score,
                 "value": parity_pct, "unit": "%", "target": 95,
                 "summary": f"{parity_violations}/{parity_total_checks} rate points outside ±{parity_tolerance}% tolerance (next {parity_days} days)",
                 "color": "sky"},
                {"key": "commission", "label": "Commission Match", "score": commission_score,
                 "value": commission_pct, "unit": "%", "target": 100,
                 "summary": f"{var_lines}/{total_lines} variance lines across last {len(stmts)} OTA statements" if total_lines else "No commission statements reconciled yet",
                 "color": "fuchsia"},
                {"key": "direct_capture", "label": "Direct Capture", "score": direct_score,
                 "value": direct_pct, "unit": "%", "target": 80,
                 "summary": f"{direct_pct}% of payments direct (cash/card/bank) in last 30d",
                 "color": "emerald"},
                {"key": "channel_balance", "label": "Channel Balance", "score": balance_score,
                 "value": mix_pct, "unit": "% concentration", "target": 60,
                 "summary": f"Largest channel = {mix_pct}% of revenue — {'over-concentrated' if max_share > 0.60 else 'well-balanced'}",
                 "color": "violet"},
            ],
            "channel_mix": sorted_channels,
            "total_revenue_30d": round(total_rev, 2),
        }

    return router
