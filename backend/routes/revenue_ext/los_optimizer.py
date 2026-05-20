"""
Length of Stay Optimizer — Analyzes booking patterns to optimize
minimum stays, stay restrictions, and pricing by length of stay.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
from collections import defaultdict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_los_optimizer_router(db, require_roles):
    router = APIRouter()

    @router.get("/revenue/los-optimizer/{property_id}")
    async def get_los_analysis(property_id: str, days: int = 90,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Analyze length-of-stay patterns and recommend optimizations."""
        query = {"room_id": {"$exists": True, "$ne": ""}}
        if property_id != "all":
            query["property_id"] = property_id

        bookings = await db.bookings.find(query, {"_id": 0}).to_list(2000)

        if not bookings:
            return {"error": "No booking data available", "recommendations": []}

        # LOS distribution
        los_counts = defaultdict(int)
        los_revenue = defaultdict(float)
        total_revenue = 0
        total_room_nights = 0

        for b in bookings:
            n = int(b.get("nights", 1) or 1)
            rpn = float(b.get("rate_per_night", 0) or 0)
            total = float(b.get("total_price", 0) or 0)
            if not total and rpn:
                total = rpn * n

            los_counts[n] += 1
            los_revenue[n] += total
            total_revenue += total
            total_room_nights += n

        avg_los = round(total_room_nights / max(len(bookings), 1), 1)
        avg_rate = round(total_revenue / max(total_room_nights, 1), 2)

        # Build distribution
        distribution = []
        max_los = max(los_counts.keys()) if los_counts else 1
        for n in range(1, min(max_los + 1, 15)):
            count = los_counts.get(n, 0)
            rev = los_revenue.get(n, 0)
            pct = round((count / max(len(bookings), 1)) * 100, 1)
            avg_rpn = round(rev / max(count * n, 1), 2) if count else 0
            distribution.append({
                "nights": n,
                "bookings": count,
                "pct_of_total": pct,
                "total_revenue": round(rev, 2),
                "avg_rate_per_night": avg_rpn,
                "room_nights": count * n,
            })

        # DOW pattern analysis
        dow_los = defaultdict(list)
        for b in bookings:
            ci = b.get("check_in", "")
            if ci:
                try:
                    d = datetime.strptime(ci[:10], "%Y-%m-%d")
                    dow_los[d.strftime("%a")].append(int(b.get("nights", 1) or 1))
                except ValueError:
                    pass

        dow_analysis = []
        for dow in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            stays = dow_los.get(dow, [])
            if stays:
                dow_analysis.append({
                    "dow": dow,
                    "avg_los": round(sum(stays) / len(stays), 1),
                    "bookings": len(stays),
                    "most_common": max(set(stays), key=stays.count),
                })
            else:
                dow_analysis.append({"dow": dow, "avg_los": 0, "bookings": 0, "most_common": 0})

        # Source analysis
        source_los = defaultdict(list)
        for b in bookings:
            src = b.get("source", "Direct")
            source_los[src].append(int(b.get("nights", 1) or 1))

        source_analysis = []
        for src, stays in sorted(source_los.items(), key=lambda x: -len(x[1])):
            source_analysis.append({
                "source": src,
                "bookings": len(stays),
                "avg_los": round(sum(stays) / len(stays), 1),
                "total_room_nights": sum(stays),
            })

        # Generate recommendations
        recommendations = []

        # 1. Short stay penalty
        one_night_pct = (los_counts.get(1, 0) / max(len(bookings), 1)) * 100
        if one_night_pct > 40:
            recommendations.append({
                "type": "min_stay",
                "priority": "high",
                "title": "Consider 2-Night Minimum on Weekends",
                "description": f"{one_night_pct:.0f}% of bookings are 1-night stays. Setting a 2-night minimum on Fri-Sat could increase RevPAR by 15-25%.",
                "impact": "high",
                "metric": f"{one_night_pct:.0f}% 1-night stays",
            })

        # 2. Extended stay discount
        long_stay_pct = sum(los_counts.get(n, 0) for n in range(5, 15)) / max(len(bookings), 1) * 100
        if long_stay_pct < 10:
            recommendations.append({
                "type": "extended_discount",
                "priority": "medium",
                "title": "Introduce Extended Stay Discount (5+ nights)",
                "description": f"Only {long_stay_pct:.0f}% of bookings are 5+ nights. Offering 10-15% discount for extended stays can fill gaps and reduce turnover costs.",
                "impact": "medium",
                "metric": f"{long_stay_pct:.0f}% extended stays",
            })

        # 3. Weekend optimization
        fri_avg = next((d["avg_los"] for d in dow_analysis if d["dow"] == "Fri"), 0)
        sat_avg = next((d["avg_los"] for d in dow_analysis if d["dow"] == "Sat"), 0)
        if fri_avg < 2 and sat_avg < 2:
            recommendations.append({
                "type": "weekend_package",
                "priority": "high",
                "title": "Weekend Package (Fri-Sun)",
                "description": f"Weekend check-ins average only {fri_avg:.1f} nights. Create a 2-night weekend package with added value to increase weekend stay length.",
                "impact": "high",
                "metric": f"Fri avg: {fri_avg:.1f}n, Sat avg: {sat_avg:.1f}n",
            })

        # 4. Rate ladder
        two_night_rate = next((d["avg_rate_per_night"] for d in distribution if d["nights"] == 2), 0)
        three_night_rate = next((d["avg_rate_per_night"] for d in distribution if d["nights"] == 3), 0)
        if two_night_rate and three_night_rate and three_night_rate >= two_night_rate:
            recommendations.append({
                "type": "rate_ladder",
                "priority": "medium",
                "title": "Implement Rate Ladder (Lower Rate for Longer Stays)",
                "description": f"3-night rate (£{three_night_rate:.0f}) is not lower than 2-night (£{two_night_rate:.0f}). Guests should save per night as stays increase.",
                "impact": "medium",
                "metric": f"2n: £{two_night_rate:.0f}, 3n: £{three_night_rate:.0f}",
            })

        # 5. Gap night filler
        if avg_los < 2:
            recommendations.append({
                "type": "gap_filler",
                "priority": "low",
                "title": "Gap Night Strategy",
                "description": f"Average LOS is {avg_los:.1f} nights. Consider offering discounted 'add a night' rates at checkout to fill gap nights between bookings.",
                "impact": "low",
                "metric": f"Avg LOS: {avg_los:.1f} nights",
            })

        # Get current LOS restrictions
        restrictions = await db.los_restrictions.find(
            {"property_id": property_id} if property_id != "all" else {},
            {"_id": 0}
        ).to_list(50)

        return {
            "total_bookings": len(bookings),
            "avg_los": avg_los,
            "avg_rate": avg_rate,
            "total_revenue": round(total_revenue, 2),
            "total_room_nights": total_room_nights,
            "distribution": distribution,
            "dow_analysis": dow_analysis,
            "source_analysis": source_analysis,
            "recommendations": recommendations,
            "restrictions": restrictions,
        }

    @router.post("/revenue/los-optimizer/{property_id}/restriction")
    async def set_los_restriction(property_id: str, data: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Set a minimum/maximum stay restriction."""
        restriction = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "type": data.get("type", "min_stay"),
            "value": int(data.get("value", 2)),
            "applies_to": data.get("applies_to", "all"),
            "days": data.get("days", []),
            "date_from": data.get("date_from", ""),
            "date_to": data.get("date_to", ""),
            "enabled": data.get("enabled", True),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.los_restrictions.insert_one(restriction)
        restriction.pop("_id", None)
        return restriction

    return router
