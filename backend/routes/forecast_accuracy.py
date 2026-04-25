"""
Forecast Accuracy Tracker — meta-RM feature most competitors lack.

Snapshots forecasts (occupancy + AI-suggested rate) on the day they were made,
and at "actuals time" compares them to what really happened. Lets the revenue
manager see whether the AI engine is being too aggressive or too cautious —
and gives a quantified "trust score" for the recommendations.

Marketing Automation Triggers — birthday / abandoned-booking / win-back email
queue. Pure rule engine. The actual delivery channel (SMTP/Resend/Twilio) is
plugged in later; for now the queue ships ready-to-send drafts that can also
be downloaded as a CSV by the marketing manager.

Endpoints:
- POST /api/forecast/snapshot/{property_id}            (cron / button)
- GET  /api/forecast/accuracy/{property_id}?days=60
- POST /api/marketing/automation/run/{property_id}     (cron / button)
- GET  /api/marketing/automation/queue/{property_id}
- POST /api/marketing/automation/{queue_id}/sent       (mark dispatched)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


def create_forecast_accuracy_router(db, require_roles):
    router = APIRouter()

    # =========================================================
    # FORECAST ACCURACY TRACKER
    # =========================================================
    @router.post("/forecast/snapshot/{property_id}")
    async def take_snapshot(property_id: str, days: int = 30,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Save today's view of next-N-days occupancy + AI rates.
        These rows get scored against actuals once the date passes.
        """
        days = max(7, min(int(days), 90))
        today = datetime.now(timezone.utc).date()
        snap_id = str(uuid.uuid4())

        # Total rooms
        rooms = await db.room_types.aggregate([
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": None, "t": {"$sum": "$total_rooms"}}}
        ]).to_list(1)
        total_rooms = int((rooms[0]["t"] if rooms else 0) or 20)

        rows = []
        for i in range(days):
            d = today + timedelta(days=i)
            ds = d.isoformat()
            booked = await db.bookings.count_documents({
                "property_id": property_id, "check_in": {"$lte": ds},
                "check_out": {"$gt": ds}, "status": {"$nin": ["cancelled"]}
            })
            forecast_occ = round(min(100, booked / total_rooms * 100), 1)
            # Find latest AI override for that date
            ovr = await db.rate_overrides.find_one(
                {"property_id": property_id, "date": ds, "set_by": {"$in": ["ai-v2", "ai-dynamic-pricing"]}},
                {"_id": 0, "custom_rate": 1, "set_by": 1},
                sort=[("updated_at", -1)],
            )
            forecast_rate = float(ovr.get("custom_rate")) if ovr else None
            rows.append({
                "snapshot_id": snap_id,
                "property_id": property_id,
                "snapshot_date": today.isoformat(),
                "target_date": ds,
                "lead_days": i,
                "total_rooms": total_rooms,
                "forecast_booked": booked,
                "forecast_occ_pct": forecast_occ,
                "forecast_rate": forecast_rate,
                "rate_set_by": (ovr or {}).get("set_by"),
                "actual_booked": None,
                "actual_occ_pct": None,
                "actual_rate": None,
                "abs_occ_error": None,
                "rate_error_pct": None,
                "scored": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        if rows:
            await db.forecast_snapshots.insert_many(rows)
        return {"snapshot_id": snap_id, "rows_saved": len(rows), "days": days}

    @router.get("/forecast/accuracy/{property_id}")
    async def get_accuracy(property_id: str, days: int = 60,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        """Score past snapshots whose target_date has passed and surface metrics.

        For each row where target_date < today and not yet scored:
          - actual_booked  = bookings on that date that are NOT cancelled at lookup time
          - actual_rate    = avg paid rate (from bookings.total_price / nights_or_rooms)
          - abs_occ_error  = |forecast - actual|
          - rate_error_pct = (forecast_rate - actual_rate) / actual_rate * 100
        """
        today = datetime.now(timezone.utc).date()
        cutoff = (today - timedelta(days=int(days))).isoformat()

        # --- Score unscored, past-target rows ---
        unscored = await db.forecast_snapshots.find(
            {"property_id": property_id, "scored": False,
             "target_date": {"$lt": today.isoformat()}},
            {"_id": 0}
        ).to_list(5000)
        for r in unscored:
            ds = r["target_date"]
            actual_booked = await db.bookings.count_documents({
                "property_id": property_id, "check_in": {"$lte": ds},
                "check_out": {"$gt": ds}, "status": {"$nin": ["cancelled"]}
            })
            actual_occ = round(min(100, actual_booked / max(r["total_rooms"], 1) * 100), 1)
            # Avg paid rate
            avg_rate = None
            pipeline = [
                {"$match": {"property_id": property_id, "check_in": {"$lte": ds},
                            "check_out": {"$gt": ds}, "status": {"$nin": ["cancelled"]}}},
                {"$group": {"_id": None, "avg": {"$avg": "$total_price"}}},
            ]
            async for d in db.bookings.aggregate(pipeline):
                avg_rate = round(d.get("avg") or 0, 2)
            abs_occ = abs(r["forecast_occ_pct"] - actual_occ)
            rate_err = None
            if r.get("forecast_rate") and avg_rate:
                rate_err = round(((r["forecast_rate"] - avg_rate) / avg_rate) * 100, 1)
            await db.forecast_snapshots.update_one(
                {"snapshot_id": r["snapshot_id"], "target_date": ds},
                {"$set": {
                    "actual_booked": actual_booked,
                    "actual_occ_pct": actual_occ,
                    "actual_rate": avg_rate,
                    "abs_occ_error": abs_occ,
                    "rate_error_pct": rate_err,
                    "scored": True,
                    "scored_at": datetime.now(timezone.utc).isoformat(),
                }}
            )

        # --- Aggregate scored rows for the response window ---
        rows = await db.forecast_snapshots.find(
            {"property_id": property_id, "scored": True,
             "target_date": {"$gte": cutoff, "$lt": today.isoformat()}},
            {"_id": 0}
        ).sort("target_date", -1).to_list(2000)

        if not rows:
            return {
                "property_id": property_id, "rows": [], "samples": 0,
                "metrics": {"mae_occ": None, "trust_score": None,
                            "avg_rate_error_pct": None, "bias": None},
                "by_lead_days": [],
            }

        mae = round(sum(r["abs_occ_error"] for r in rows) / len(rows), 2)
        rate_errs = [r["rate_error_pct"] for r in rows if r.get("rate_error_pct") is not None]
        avg_rate_err = round(sum(rate_errs) / len(rate_errs), 2) if rate_errs else None
        # Trust score: 100 minus 2× MAE, clamped 0-100. Heuristic but interpretable.
        trust = max(0, min(100, round(100 - 2 * mae)))
        bias = "balanced"
        if avg_rate_err is not None:
            if avg_rate_err > 5: bias = "too_aggressive"
            elif avg_rate_err < -5: bias = "too_cautious"

        # By lead-time bucket
        buckets = {"0-3d": [], "4-7d": [], "8-14d": [], "15-30d": [], "31d+": []}
        for r in rows:
            ld = r.get("lead_days", 0)
            key = ("0-3d" if ld <= 3 else "4-7d" if ld <= 7 else
                   "8-14d" if ld <= 14 else "15-30d" if ld <= 30 else "31d+")
            buckets[key].append(r)
        by_lead = [
            {"bucket": k, "n": len(v),
             "mae_occ": round(sum(x["abs_occ_error"] for x in v) / len(v), 2) if v else None,
             "avg_rate_err_pct":
                 round(sum(x["rate_error_pct"] for x in v if x.get("rate_error_pct") is not None) /
                       max(sum(1 for x in v if x.get("rate_error_pct") is not None), 1), 2) if v else None,
            }
            for k, v in buckets.items()
        ]

        return {
            "property_id": property_id,
            "samples": len(rows),
            "metrics": {"mae_occ": mae, "trust_score": trust,
                        "avg_rate_error_pct": avg_rate_err, "bias": bias},
            "by_lead_days": by_lead,
            "rows": rows[:200],   # cap payload
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

    # =========================================================
    # MARKETING AUTOMATION TRIGGERS
    # =========================================================
    @router.post("/marketing/automation/run/{property_id}")
    async def run_automation(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate queue items for three trigger types. Idempotent — won't
        re-queue the same (guest_id, trigger_type, date_key)."""
        today = datetime.now(timezone.utc).date()
        guests = await db.guest_profiles.find({}, {"_id": 0}).to_list(2000)
        queued = {"birthday": 0, "abandoned": 0, "win_back": 0}

        # ---- 1. BIRTHDAY (next 7 days) ----
        for g in guests:
            dob = g.get("date_of_birth") or g.get("dob")
            if not dob: continue
            try:
                bd = datetime.fromisoformat(dob.split("T")[0]).date()
            except Exception:
                continue
            for i in range(7):
                tgt = today + timedelta(days=i)
                if bd.month == tgt.month and bd.day == tgt.day:
                    key = f"birthday_{tgt.isoformat()}"
                    if not await db.marketing_queue.find_one(
                        {"guest_id": g["id"], "trigger": "birthday", "date_key": key}
                    ):
                        await db.marketing_queue.insert_one(_compose(
                            property_id, g, "birthday", key,
                            subject=f"🎉 Happy birthday, {g.get('name','').split()[0] or 'friend'}!",
                            body=("Wishing you a wonderful birthday! Use code "
                                  "BDAY15 for 15% off your next stay this month.")
                        ))
                        queued["birthday"] += 1

        # ---- 2. ABANDONED BOOKING (started, never paid, >30 min) ----
        cutoff_iso = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        old_iso = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        async for b in db.bookings.find(
            {"property_id": property_id,
             "status": "pending_payment",
             "created_at": {"$lte": cutoff_iso, "$gte": old_iso}},
            {"_id": 0}
        ):
            email = b.get("guest_email") or ""
            if not email: continue
            key = f"abandoned_{b.get('id','')}"
            if not await db.marketing_queue.find_one({"trigger": "abandoned", "date_key": key}):
                await db.marketing_queue.insert_one(_compose(
                    property_id, {"id": email, "name": b.get("guest_name", ""), "email": email},
                    "abandoned", key,
                    subject="Forgot something? Your room is still available",
                    body=(f"Hi {b.get('guest_name','').split()[0] or 'there'}, your room for "
                          f"{b.get('check_in','')} is still available. Complete the booking and "
                          "we'll throw in a complimentary welcome drink. Code WELCOMEBACK10."),
                    booking_id=b.get("id", ""),
                ))
                queued["abandoned"] += 1

        # ---- 3. WIN-BACK (last stay 6-12 months ago) ----
        win_low  = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        win_high = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        async for g in db.guest_profiles.find({"last_stay": {"$gte": win_low, "$lte": win_high}}, {"_id": 0}):
            key = f"winback_{today.strftime('%Y-%m')}"   # max once per month
            if not await db.marketing_queue.find_one(
                {"guest_id": g["id"], "trigger": "win_back", "date_key": key}
            ):
                await db.marketing_queue.insert_one(_compose(
                    property_id, g, "win_back", key,
                    subject="We miss you — 20% off your return stay",
                    body=(f"Hi {g.get('name','').split()[0] or 'there'}, it's been a while! "
                          "Use code WELCOMEBACK20 for 20% off any stay in the next 60 days. "
                          "We'd love to host you again."),
                ))
                queued["win_back"] += 1

        return {"queued": queued, "total": sum(queued.values()),
                "as_of": datetime.now(timezone.utc).isoformat()}

    @router.get("/marketing/automation/queue/{property_id}")
    async def get_queue(property_id: str, status: str = "",
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.marketing_queue.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        # Stats
        all_rows = await db.marketing_queue.find(
            {"property_id": property_id}, {"_id": 0, "trigger": 1, "status": 1}
        ).to_list(2000)
        by_trigger = {"birthday": 0, "abandoned": 0, "win_back": 0}
        by_status  = {"pending": 0, "sent": 0, "skipped": 0}
        for r in all_rows:
            by_trigger[r.get("trigger", "")] = by_trigger.get(r.get("trigger", ""), 0) + 1
            by_status[r.get("status", "pending")] = by_status.get(r.get("status", "pending"), 0) + 1
        return {"queue": rows, "by_trigger": by_trigger, "by_status": by_status, "total": len(all_rows)}

    @router.post("/marketing/automation/{queue_id}/sent")
    async def mark_sent(queue_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.marketing_queue.update_one(
            {"id": queue_id},
            {"$set": {"status": "sent",
                      "sent_at": datetime.now(timezone.utc).isoformat(),
                      "sent_by": current_user.get("name", "")}}
        )
        if r.modified_count == 0:
            raise HTTPException(404, "Not found")
        return {"ok": True}

    @router.post("/marketing/automation/{queue_id}/skip")
    async def mark_skip(queue_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.marketing_queue.update_one(
            {"id": queue_id},
            {"$set": {"status": "skipped",
                      "skipped_at": datetime.now(timezone.utc).isoformat(),
                      "skipped_by": current_user.get("name", "")}}
        )
        if r.modified_count == 0:
            raise HTTPException(404, "Not found")
        return {"ok": True}

    return router


def _compose(property_id, guest, trigger, date_key, subject, body, booking_id=""):
    return {
        "id": str(uuid.uuid4()),
        "property_id": property_id,
        "guest_id": guest.get("id", ""),
        "guest_name": guest.get("name", ""),
        "guest_email": guest.get("email", ""),
        "trigger": trigger,
        "date_key": date_key,
        "subject": subject,
        "body": body,
        "booking_id": booking_id,
        "status": "pending",
        "channel": "email",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
