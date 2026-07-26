"""
Competitor parity & morning brief — Tier-1 features missing from typical PMS UIs:

1. Future Date Heatmap (`GET /api/parity/heatmap/{property_id}?days=60`)
   Per-day grid: our base rate vs competitor average + min/max + delta_pct +
   "underpriced/parity/overpriced" classification. Powers a calendar heatmap.

2. Daily Briefing (`GET /api/morning-brief/{property_id}`)
   One-shot digest combining pace, AI pricing alerts, arrivals, reputation —
   the screen revenue managers want at 8 AM with their coffee.

3. Pricing Autopilot (`/api/autopilot/pricing/{property_id}`)
   Schedule + last-run + last-recommendations record. Persisted in collection
   `pricing_autopilot`. Scheduler tick is wired in `routes/scheduler.py`.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def create_competitor_parity_router(db, require_roles):
    router = APIRouter()

    # ============================================================
    # 1. FUTURE DATE HEATMAP
    # ============================================================
    @router.get("/parity/heatmap/{property_id}")
    async def heatmap(property_id: str, days: int = 60,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        days = max(7, min(int(days), 180))
        today = datetime.now(timezone.utc).date()

        # Pull our base rate from the cheapest room type
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0, "base_rate": 1, "name": 1})
        base_rate = float((rt or {}).get("base_rate", 100) or 100)

        # Rate overrides (current selling price)
        end_iso = (today + timedelta(days=days)).isoformat()
        today_iso = today.isoformat()
        overrides = await db.rate_overrides.find(
            {"property_id": property_id,
             "date": {"$gte": today_iso, "$lte": end_iso}},
            {"_id": 0, "date": 1, "custom_rate": 1, "set_by": 1}
        ).to_list(2000)
        ours_by_date = {}
        for o in overrides:
            ds = o.get("date")
            if ds:
                # Lowest override per date wins (= what guest sees)
                cur = ours_by_date.get(ds)
                if cur is None or float(o.get("custom_rate") or base_rate) < cur["rate"]:
                    ours_by_date[ds] = {"rate": float(o.get("custom_rate") or base_rate),
                                         "set_by": o.get("set_by", "")}

        # Competitor prices
        competitors = await db.market_competitors.find(
            {"property_id": property_id}, {"_id": 0, "name": 1, "prices": 1}
        ).to_list(50)
        comp_by_date = {}
        for c in competitors:
            for p in (c.get("prices") or []):
                ds = p.get("date")
                lp = p.get("lowest_price")
                if not ds or not lp or not p.get("scraped"):
                    continue
                comp_by_date.setdefault(ds, []).append({"name": c.get("name", ""), "price": float(lp)})

        # Bookings (occupancy weight)
        booking_count_pipeline = [
            {"$match": {"property_id": property_id,
                        "check_in": {"$lte": end_iso}, "check_out": {"$gt": today_iso},
                        "status": {"$nin": ["cancelled"]}}}
        ]
        bookings = await db.bookings.aggregate(booking_count_pipeline).to_list(5000)

        room_count = await db.room_types.aggregate([
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": None, "total": {"$sum": "$total_rooms"}}}
        ]).to_list(1)
        total_rooms = int((room_count[0]["total"] if room_count else 0) or 20)

        cells = []
        for i in range(days):
            d = today + timedelta(days=i)
            ds = d.isoformat()
            our = ours_by_date.get(ds)
            our_rate = our["rate"] if our else base_rate
            comp_rows = comp_by_date.get(ds, [])
            comp_prices = [r["price"] for r in comp_rows]
            comp_avg = round(sum(comp_prices) / len(comp_prices), 2) if comp_prices else None
            comp_min = round(min(comp_prices), 2) if comp_prices else None
            comp_max = round(max(comp_prices), 2) if comp_prices else None
            delta_pct = round(((our_rate - comp_avg) / comp_avg) * 100, 1) if comp_avg else None
            # Classification
            if delta_pct is None:
                cls = "no_data"
            elif delta_pct < -10:
                cls = "underpriced"      # we're way cheaper → leaving money on table
            elif delta_pct > 10:
                cls = "overpriced"       # likely losing share
            else:
                cls = "parity"
            # Occupancy on this date
            booked = sum(1 for b in bookings if b.get("check_in", "") <= ds < b.get("check_out", ""))
            occ_pct = round(min(100, (booked / total_rooms) * 100), 1)

            cells.append({
                "date": ds,
                "dow": d.strftime("%a"),
                "is_weekend": d.weekday() >= 5,
                "our_rate": round(our_rate, 2),
                "our_set_by": (our or {}).get("set_by", ""),
                "comp_avg": comp_avg,
                "comp_min": comp_min,
                "comp_max": comp_max,
                "comp_count": len(comp_rows),
                "competitors": comp_rows[:6],
                "delta_pct": delta_pct,
                "class": cls,
                "occ_pct": occ_pct,
            })

        # Roll-up
        valid = [c for c in cells if c["delta_pct"] is not None]
        avg_delta = round(sum(c["delta_pct"] for c in valid) / len(valid), 1) if valid else None
        return {
            "property_id": property_id,
            "base_rate": base_rate,
            "room_type": (rt or {}).get("name", ""),
            "days": days,
            "cells": cells,
            "summary": {
                "avg_delta_pct": avg_delta,
                "underpriced_days": sum(1 for c in cells if c["class"] == "underpriced"),
                "overpriced_days": sum(1 for c in cells if c["class"] == "overpriced"),
                "parity_days": sum(1 for c in cells if c["class"] == "parity"),
                "no_data_days": sum(1 for c in cells if c["class"] == "no_data"),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ============================================================
    # 2. DAILY MORNING BRIEF
    # ============================================================
    @router.get("/morning-brief/{property_id}")
    async def morning_brief(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        today = datetime.now(timezone.utc).date()
        today_iso = today.isoformat()

        # Today arrivals + departures
        arrivals = await db.bookings.count_documents({
            "property_id": property_id, "check_in": today_iso,
            "status": {"$nin": ["cancelled"]}
        })
        departures = await db.bookings.count_documents({
            "property_id": property_id, "check_out": today_iso,
            "status": {"$nin": ["cancelled"]}
        })
        in_house = await db.bookings.count_documents({
            "property_id": property_id,
            "check_in": {"$lte": today_iso}, "check_out": {"$gt": today_iso},
            "status": {"$nin": ["cancelled"]}
        })

        # 7-day pickup (revenue made this week)
        pipeline = [
            {"$match": {"property_id": property_id,
                        "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()},
                        "status": {"$nin": ["cancelled"]}}},
            {"$group": {"_id": None, "count": {"$sum": 1}, "revenue": {"$sum": "$total_price"}}},
        ]
        pickup = {"count": 0, "revenue": 0}
        async for d in db.bookings.aggregate(pipeline):
            pickup = {"count": d.get("count", 0), "revenue": round(d.get("revenue") or 0, 2)}

        # STLY snapshot for next 7 days
        ty_rooms = ly_rooms = 0
        for i in range(7):
            tgt = (today + timedelta(days=i)).isoformat()
            ly = (today + timedelta(days=i) - timedelta(days=365)).isoformat()
            ty_rooms += await db.bookings.count_documents({
                "property_id": property_id, "check_in": {"$lte": tgt},
                "check_out": {"$gt": tgt}, "status": {"$nin": ["cancelled"]}
            })
            ly_rooms += await db.bookings.count_documents({
                "property_id": property_id, "check_in": {"$lte": ly},
                "check_out": {"$gt": ly}, "status": {"$nin": ["cancelled"]}
            })

        # New unread reviews
        new_reviews = await db.reviews.find(
            {"property_id": property_id, "responded": {"$ne": True}},
            {"_id": 0, "platform": 1, "rating": 1, "guest_name": 1, "text": 1, "sentiment": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(10)

        # Open logbook items
        open_log = await db.logbook_entries.count_documents({
            "property_id": property_id, "status": "open"
        })

        # Latest autopilot recommendation summary if any
        autopilot = await db.pricing_autopilot.find_one(
            {"property_id": property_id}, {"_id": 0}, sort=[("last_run_at", -1)]
        )

        # Unread inbox messages
        unread_inbox = await db.unified_messages.count_documents({"direction": "inbound", "read": False})

        # AI Night Shift — son 24 saatte AI motorlarının yaptıkları
        since24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        idr_events = await db.intraday_reprice_events.find(
            {"property_id": property_id, "created_at": {"$gte": since24}},
            {"_id": 0, "applied_count": 1}).to_list(200)
        ra_pending = await db.restriction_recommendations.count_documents(
            {"property_id": property_id, "status": "pending"})
        ra_new = await db.restriction_recommendations.count_documents(
            {"property_id": property_id, "created_at": {"$gte": since24}})
        gap_drafts = await db.gap_campaigns.count_documents(
            {"property_id": property_id, "status": "draft"})
        gap_new = await db.gap_campaigns.count_documents(
            {"property_id": property_id, "created_at": {"$gte": since24}})
        allot_released = 0
        async for r in db.allotment_releases.aggregate([
                {"$match": {"property_id": property_id, "run_at": {"$gte": since24}}},
                {"$group": {"_id": None, "rooms": {"$sum": "$rooms_released"}}}]):
            allot_released = int(r.get("rooms", 0))
        ai_night_shift = {
            "intraday_spikes_24h": len(idr_events),
            "intraday_prices_applied_24h": sum(int(e.get("applied_count", 0)) for e in idr_events),
            "restriction_recs_pending": ra_pending,
            "restriction_recs_new_24h": ra_new,
            "gap_campaign_drafts": gap_drafts,
            "gap_campaigns_new_24h": gap_new,
            "allotment_rooms_released_24h": allot_released,
        }

        return {
            "property_id": property_id,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "today": {"date": today_iso, "arrivals": arrivals, "departures": departures, "in_house": in_house},
            "pickup_7d": pickup,
            "stly_7d": {"ty_rooms": ty_rooms, "ly_rooms": ly_rooms,
                        "delta": ty_rooms - ly_rooms,
                        "delta_pct": round(((ty_rooms - ly_rooms) / ly_rooms) * 100, 1) if ly_rooms else 0},
            "alerts": {
                "open_logbook": open_log,
                "unread_inbox": unread_inbox,
                "unanswered_reviews": len(new_reviews),
            },
            "new_reviews": new_reviews,
            "autopilot": autopilot or None,
            "ai_night_shift": ai_night_shift,
        }

    # ============================================================
    # 3. PRICING AUTOPILOT
    # ============================================================
    @router.get("/autopilot/pricing/{property_id}")
    async def get_autopilot(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.pricing_autopilot.find_one({"property_id": property_id}, {"_id": 0})
        if not doc:
            doc = {
                "property_id": property_id,
                "enabled": False,
                "schedule": "daily_03",   # 03:00 UTC daily
                "days_window": 14,
                "auto_apply": False,      # if true, applies recommendations directly
                "last_run_at": "",
                "last_summary": "",
                "last_recommendations": [],
            }
        return doc

    @router.post("/autopilot/pricing/{property_id}")
    async def update_autopilot(property_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        update = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", False)),
            "schedule": data.get("schedule", "daily_03"),
            "days_window": int(data.get("days_window", 14) or 14),
            "auto_apply": bool(data.get("auto_apply", False)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("name", current_user.get("email", "")),
        }
        await db.pricing_autopilot.update_one(
            {"property_id": property_id}, {"$set": update}, upsert=True
        )
        return {"ok": True, "config": update}

    @router.post("/autopilot/pricing/{property_id}/run-now")
    async def run_autopilot_now(property_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        """Manual trigger — calls AI v2 endpoint internally and stores result."""
        cfg = await db.pricing_autopilot.find_one({"property_id": property_id}, {"_id": 0})
        days_window = int((cfg or {}).get("days_window", 14))

        # Stamp run-now metadata; UI subsequently calls /ai-v2/recommend and /save-run
        await db.pricing_autopilot.update_one(
            {"property_id": property_id},
            {"$set": {"last_run_at": datetime.now(timezone.utc).isoformat(),
                      "last_summary": "Run-now triggered. UI will request recommendations and save summary.",
                      "last_run_by": current_user.get("name", "")}},
            upsert=True,
        )
        return {"ok": True, "days_window": days_window, "message": "Run-now triggered — UI fetches recommendations next."}

    @router.post("/autopilot/pricing/{property_id}/save-run")
    async def save_autopilot_run(property_id: str, data: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """UI calls this after fetching v2 recommendations to persist a brief snapshot."""
        recs = (data.get("recommendations") or [])[:30]
        await db.pricing_autopilot.update_one(
            {"property_id": property_id},
            {"$set": {
                "last_run_at": datetime.now(timezone.utc).isoformat(),
                "last_summary": data.get("summary", ""),
                "last_recommendations": [
                    {"date": r.get("date"), "suggested_rate": r.get("suggested_rate"),
                     "delta_pct": r.get("delta_pct"), "confidence": r.get("confidence"),
                     "reasoning": (r.get("reasoning") or "")[:160]}
                    for r in recs
                ],
                "last_recommendation_count": len(recs),
            }},
            upsert=True,
        )
        return {"ok": True, "saved": len(recs)}

    return router
