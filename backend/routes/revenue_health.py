"""
Revenue Health (Iter 157) — composite KPI tile pulling from 4 separate systems:
- Payment Mix (direct_percent)
- Deposit Liability (total_liability)
- Commission Variance (flagged variance count + sum)
- RFM (champion revenue share)

Single-panel revenue pulse for dashboards & board meetings.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def create_revenue_health_router(db, require_roles):
    router = APIRouter()

    @router.get("/revenue-health/{property_id}")
    async def revenue_health(property_id: str, from_date: str = "", to_date: str = "",
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Composite KPI. Scores each axis 0-100, rolls up to a health grade A/B/C/D/F."""
        now = datetime.now(timezone.utc)
        if not from_date:
            from_date = now.replace(day=1).strftime("%Y-%m-%d")
        if not to_date:
            import calendar
            last_day = calendar.monthrange(now.year, now.month)[1]
            to_date = now.replace(day=last_day).strftime("%Y-%m-%d")

        pq = {} if property_id == "all" else {"property_id": property_id}
        today_str = now.strftime("%Y-%m-%d")

        # --- 1. Payment Mix: direct capture %
        booking_ids = [b["id"] for b in await db.bookings.find(pq, {"_id": 0, "id": 1}).to_list(20000)]
        items = await db.folio_items.find({
            "booking_id": {"$in": booking_ids}, "type": "payment",
            "created_at": {"$gte": from_date, "$lte": to_date + "T99:99:99"},
        }, {"_id": 0}).to_list(20000)
        by_method = {"cash": 0.0, "card": 0.0, "bank_transfer": 0.0, "channel_collection": 0.0}
        for it in items:
            m = (it.get("payment_method") or it.get("category") or "card").lower()
            if m in by_method:
                by_method[m] += float(it.get("amount", 0))
        total_pay = sum(by_method.values())
        direct = by_method["cash"] + by_method["card"] + by_method["bank_transfer"]
        direct_pct = round((direct / total_pay) * 100, 1) if total_pay > 0 else 0
        # Score: 80%+ direct = 100. Linear below.
        payment_score = min(100, round((direct_pct / 80) * 100)) if total_pay > 0 else 50

        # --- 2. Deposit Liability
        future_bookings = await db.bookings.find({
            **pq, "check_out": {"$gt": today_str},
            "status": {"$nin": ["cancelled", "no_show"]},
        }, {"_id": 0, "id": 1, "total_price": 1}).to_list(20000)
        future_ids = [b["id"] for b in future_bookings]
        total_future_price = sum(float(b.get("total_price", 0) or 0) for b in future_bookings)
        paid_future = 0.0
        if future_ids:
            async for row in db.folio_items.aggregate([
                {"$match": {"booking_id": {"$in": future_ids}, "type": "payment"}},
                {"$group": {"_id": None, "sum": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}}}},
            ]):
                paid_future = float(row["sum"])
        deposit_ratio = round((paid_future / total_future_price) * 100, 1) if total_future_price > 0 else 0
        # 40%+ of future revenue pre-paid = 100
        deposit_score = min(100, round((deposit_ratio / 40) * 100)) if total_future_price > 0 else 50

        # --- 3. Commission Variance
        stmts = await db.commission_statements.find(pq, {"_id": 0}).sort("uploaded_at", -1).limit(6).to_list(6)
        total_lines = sum((s.get("summary") or {}).get("lines_total", 0) for s in stmts)
        variance_lines = sum((s.get("summary") or {}).get("variance", 0) + (s.get("summary") or {}).get("unmatched", 0) for s in stmts)
        variance_pct = round((variance_lines / total_lines) * 100, 1) if total_lines > 0 else 0
        # 0% variance = 100. 10%+ = 0.
        commission_score = max(0, round(100 - variance_pct * 10)) if total_lines > 0 else 75

        # --- 4. RFM Champion Revenue share
        # Quick estimate: sum spend of guests with multiple stays and recent activity
        champ_revenue = 0.0
        total_guest_revenue = 0.0
        by_email = {}
        all_bookings = await db.bookings.find({**pq, "status": {"$nin": ["cancelled", "no_show"]}},
                                              {"_id": 0, "guest_email": 1, "total_price": 1, "check_out": 1}).to_list(50000)
        for b in all_bookings:
            em = (b.get("guest_email") or "").strip().lower()
            if not em:
                continue
            g = by_email.setdefault(em, {"stays": 0, "spent": 0.0, "last": ""})
            g["stays"] += 1
            g["spent"] += float(b.get("total_price") or 0)
            if (b.get("check_out") or "") > g["last"]:
                g["last"] = b.get("check_out") or ""
        for g in by_email.values():
            total_guest_revenue += g["spent"]
            # Champion approx: 2+ stays AND last stay within 12 months
            if g["stays"] >= 2 and g["last"] >= (now.replace(year=now.year - 1)).strftime("%Y-%m-%d"):
                champ_revenue += g["spent"]
        champion_pct = round((champ_revenue / total_guest_revenue) * 100, 1) if total_guest_revenue > 0 else 0
        # 25%+ from Champions = 100
        rfm_score = min(100, round((champion_pct / 25) * 100)) if total_guest_revenue > 0 else 50

        # Overall
        overall = round((payment_score + deposit_score + commission_score + rfm_score) / 4)
        if overall >= 90: grade = "A+"
        elif overall >= 80: grade = "A"
        elif overall >= 70: grade = "B"
        elif overall >= 60: grade = "C"
        elif overall >= 50: grade = "D"
        else: grade = "F"

        return {
            "property_id": property_id,
            "from_date": from_date, "to_date": to_date,
            "overall_score": overall,
            "grade": grade,
            "metrics": [
                {"key": "direct_capture", "label": "Direct Capture", "score": payment_score,
                 "value": direct_pct, "unit": "%", "target": 80,
                 "summary": f"{direct_pct}% of payments are direct (cash/card/bank vs OTA)",
                 "color": "sky"},
                {"key": "deposits", "label": "Deposit Security", "score": deposit_score,
                 "value": deposit_ratio, "unit": "%", "target": 40,
                 "summary": f"{deposit_ratio}% of future revenue already collected ({round(paid_future, 2)}/{round(total_future_price, 2)})",
                 "color": "violet"},
                {"key": "commission_match", "label": "Commission Match", "score": commission_score,
                 "value": variance_pct, "unit": "% variance", "target": 0,
                 "summary": f"{variance_lines}/{total_lines} lines with variance across last {len(stmts)} statements" if total_lines else "No commission statements reconciled yet",
                 "color": "fuchsia"},
                {"key": "champion_revenue", "label": "Champion Revenue", "score": rfm_score,
                 "value": champion_pct, "unit": "%", "target": 25,
                 "summary": f"{champion_pct}% of revenue comes from repeat guests ({len([g for g in by_email.values() if g['stays'] >= 2])} repeaters)",
                 "color": "emerald"},
            ],
        }

    return router
