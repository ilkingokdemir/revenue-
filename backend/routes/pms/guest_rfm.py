"""
Guest RFM Segmentation (P1) — Recency / Frequency / Monetary scoring of all
guests with stay history. Used by revenue managers for VIP identification,
winback campaigns, and churn analysis.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def create_rfm_router(db, require_roles):
    router = APIRouter()

    @router.get("/guests/rfm/{property_id}")
    async def rfm(property_id: str,
                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Compute RFM scores across guests. Each dimension 1-5, composite 3-15. Segments:
        - Champions (13-15): high R, high F, high M — VIPs
        - Loyal (10-12): regular high-value guests
        - Potential Loyalists (7-9): recent but not yet repeat
        - At Risk (4-6): haven't booked in a while
        - Lost (3): long gone
        """
        today = datetime.now(timezone.utc).date()
        pq = {} if property_id == "all" else {"property_id": property_id}
        bookings = await db.bookings.find({
            **pq, "status": {"$nin": ["cancelled", "no_show"]}
        }, {"_id": 0}).to_list(50000)

        # Aggregate by guest email (fallback: guest_name)
        by_guest = {}
        for b in bookings:
            key = (b.get("guest_email") or "").strip().lower() or f"name:{(b.get('guest_name') or '').strip().lower()}"
            if not key or key == "name:":
                continue
            g = by_guest.setdefault(key, {
                "key": key,
                "guest_email": b.get("guest_email", ""),
                "guest_name": b.get("guest_name", ""),
                "stays": 0, "total_spent": 0.0, "last_stay": None, "first_stay": None,
            })
            g["stays"] += 1
            g["total_spent"] += float(b.get("total_price") or 0)
            check_out = b.get("check_out")
            if check_out:
                try:
                    dt = datetime.strptime(check_out, "%Y-%m-%d").date()
                    if not g["last_stay"] or dt > g["last_stay"]:
                        g["last_stay"] = dt
                    if not g["first_stay"] or dt < g["first_stay"]:
                        g["first_stay"] = dt
                except ValueError:
                    pass

        guests = list(by_guest.values())
        if not guests:
            return {"segments": [], "guests": [], "summary": {"total": 0}}

        # Compute R/F/M raw values
        for g in guests:
            g["recency_days"] = (today - g["last_stay"]).days if g["last_stay"] else 9999
            g["frequency"] = g["stays"]
            g["monetary"] = round(g["total_spent"], 2)

        # Quintile scoring (1 worst, 5 best)
        def quintile(values, reverse=False):
            # returns lookup: value → score 1-5
            if not values:
                return {}
            s = sorted(values, reverse=reverse)
            n = len(s)
            cuts = [s[int(n * i / 5)] for i in range(5)] + [s[-1]]
            def score(v):
                for i in range(5):
                    if (v <= cuts[i + 1]) if not reverse else (v >= cuts[i + 1]):
                        return i + 1
                return 5
            return score

        # For Recency: lower days = better → reverse-rank for scoring
        rec_vals = [g["recency_days"] for g in guests]
        freq_vals = [g["frequency"] for g in guests]
        mon_vals = [g["monetary"] for g in guests]
        # Recency: sort ascending (0 days = best). Rank accordingly.
        sorted_rec = sorted(rec_vals)
        sorted_freq = sorted(freq_vals)
        sorted_mon = sorted(mon_vals)

        def rank_score(val, sorted_asc, inverse=False):
            # percentile rank in ascending sort
            n = len(sorted_asc)
            pos = 0
            for i, v in enumerate(sorted_asc):
                if v >= val:
                    pos = i
                    break
            else:
                pos = n - 1
            pct = pos / max(n - 1, 1)
            score = 1 + int(pct * 4.99)
            if inverse:
                score = 6 - score
            return max(1, min(5, score))

        SEGMENTS = [
            (13, 15, "Champions", "bg-emerald-500"),
            (10, 12, "Loyal", "bg-sky-500"),
            (7, 9, "Potential Loyalists", "bg-violet-500"),
            (4, 6, "At Risk", "bg-amber-500"),
            (0, 3, "Lost", "bg-stone-500"),
        ]

        out = []
        seg_counts = {name: 0 for _, _, name, _ in SEGMENTS}
        seg_revenue = {name: 0.0 for _, _, name, _ in SEGMENTS}
        for g in guests:
            r = rank_score(g["recency_days"], sorted_rec, inverse=True)
            f = rank_score(g["frequency"], sorted_freq)
            m = rank_score(g["monetary"], sorted_mon)
            composite = r + f + m
            segment = "Lost"
            for lo, hi, name, _color in SEGMENTS:
                if lo <= composite <= hi:
                    segment = name
                    break
            seg_counts[segment] = seg_counts.get(segment, 0) + 1
            seg_revenue[segment] = seg_revenue.get(segment, 0) + g["monetary"]
            out.append({
                "guest_email": g["guest_email"],
                "guest_name": g["guest_name"],
                "recency_days": g["recency_days"],
                "frequency": g["frequency"],
                "monetary": g["monetary"],
                "r_score": r, "f_score": f, "m_score": m,
                "composite": composite,
                "segment": segment,
            })

        segments_out = [
            {"name": name, "range": f"{lo}-{hi}", "count": seg_counts.get(name, 0),
             "revenue": round(seg_revenue.get(name, 0), 2), "color": color}
            for lo, hi, name, color in SEGMENTS
        ]
        # Sort guests descending by composite
        out.sort(key=lambda r: -r["composite"])

        return {
            "summary": {
                "total": len(guests),
                "total_revenue": round(sum(g["monetary"] for g in guests), 2),
                "avg_stays": round(sum(g["frequency"] for g in guests) / len(guests), 2),
            },
            "segments": segments_out,
            "guests": out[:500],
        }

    return router
