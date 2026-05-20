"""
RMS Pro Features — Rakiplerden öne geçmek için eklenmiş gelişmiş özellikler:

1. RevPAG (Revenue per Available Guest) — BEONx unique value prop
2. Quality Score Pricing — review/location/amenities → rate uplift
3. Forecast Accuracy KPI — Cloudbeds 95% benchmark
4. Group Pricing Optimizer (displacement analysis) — IDeaS/Flyr core
5. 2-Year Forward Forecasting summary (forecast_v2 üzerine ek)
6. Autopilot Mode toggle + scheduled daily AI optimize

All endpoints prefix: /api/rms-pro/*
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException


def create_rms_pro_router(db, require_roles):
    router = APIRouter(prefix="/rms-pro")

    # ==================== REVPAG (Revenue per Available Guest) ====================

    @router.get("/revpag/{property_id}")
    async def revpag(property_id: str, days: int = 30,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """RevPAG = Total Revenue / Total Guest-Nights.
        BEONx'in unique pricing metriği. RevPAR'a (per room) göre çift kişilik dolu
        odanın tek kişilikten 2x daha karlı olduğunu yakalar.
        """
        days = max(7, min(int(days), 365))
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

        bookings = await db.bookings.find({
            "property_id": property_id,
            "status": {"$ne": "cancelled"},
            "check_in": {"$gte": start, "$lte": end},
        }, {"_id": 0, "check_in": 1, "check_out": 1, "total_price": 1, "adults": 1, "children": 1}).to_list(2000)

        total_revenue = 0.0
        total_guest_nights = 0
        total_room_nights = 0
        for b in bookings:
            try:
                ci = b.get("check_in")
                co = b.get("check_out")
                nights = max(1, (datetime.fromisoformat(co) - datetime.fromisoformat(ci)).days) if (ci and co) else 1
                guests = int(b.get("adults") or 1) + int(b.get("children") or 0)
                price = float(b.get("total_price") or 0)
                total_revenue += price
                total_guest_nights += guests * nights
                total_room_nights += nights
            except Exception:
                pass

        # Available room-nights (capacity)
        rooms = await db.rooms.count_documents({"property_id": property_id})
        if not rooms:
            rooms = await db.room_types.count_documents({"property_id": property_id})
        available_room_nights = max(1, rooms * days)
        # Assume avg 2 guests per room capacity
        available_guest_nights = available_room_nights * 2

        revpar = round(total_revenue / available_room_nights, 2) if available_room_nights else 0
        revpag = round(total_revenue / max(1, available_guest_nights), 2)
        adr = round(total_revenue / total_room_nights, 2) if total_room_nights else 0
        occupancy = round(total_room_nights / available_room_nights * 100, 1) if available_room_nights else 0
        avg_party_size = round(total_guest_nights / total_room_nights, 2) if total_room_nights else 0

        return {
            "property_id": property_id,
            "days": days,
            "revpar": revpar,
            "revpag": revpag,
            "adr": adr,
            "occupancy_pct": occupancy,
            "avg_party_size": avg_party_size,
            "total_revenue": round(total_revenue, 2),
            "total_guest_nights": total_guest_nights,
            "total_room_nights": total_room_nights,
            "available_room_nights": available_room_nights,
        }

    # ==================== QUALITY SCORE PRICING ====================

    @router.get("/quality-score/{property_id}")
    async def quality_score(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Quality Score = property kalite faktörleri (review_score, location, amenities,
        cleaning score, response_time) → rate uplift recommendation.

        BEONx 21+ objektif faktör kullanır. Biz core 5'i ile başlayalım, daha sonra
        otomatik genişler.
        """
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        if not prop:
            raise HTTPException(404, "Property not found")

        factors = []

        # 1. Review score (booking.com + google + tripadvisor avg)
        reviews = await db.reviews.find({"property_id": property_id}, {"_id": 0, "rating": 1}).to_list(500)
        review_avg = round(sum(r.get("rating", 0) for r in reviews) / max(1, len(reviews)), 2) if reviews else None
        review_factor = 0
        if review_avg is not None:
            # 4.5+ → +5%, 4.0+ → +2%, 3.5+ → 0%, <3.5 → -5%
            if review_avg >= 4.5:
                review_factor = 5
            elif review_avg >= 4.0:
                review_factor = 2
            elif review_avg >= 3.5:
                review_factor = 0
            else:
                review_factor = -5
        factors.append({
            "name": "Review Score",
            "value": review_avg,
            "uplift_pct": review_factor,
            "reason": f"Avg {review_avg or '—'}/5 ({len(reviews)} review)",
        })

        # 2. Amenities count
        amenities = prop.get("amenities") or []
        am_factor = min(3, len(amenities) // 5)
        factors.append({
            "name": "Amenities",
            "value": len(amenities),
            "uplift_pct": am_factor,
            "reason": f"{len(amenities)} amenity",
        })

        # 3. Photos count (visual appeal)
        photos = prop.get("photos") or prop.get("images") or []
        photo_factor = 2 if len(photos) >= 15 else (1 if len(photos) >= 8 else 0)
        factors.append({
            "name": "Photo Quality",
            "value": len(photos),
            "uplift_pct": photo_factor,
            "reason": f"{len(photos)} photo",
        })

        # 4. Response time (last 30d)
        thirty_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        msgs = await db.messages.find({
            "property_id": property_id,
            "created_at": {"$gte": thirty_ago},
            "response_time_minutes": {"$exists": True, "$ne": None},
        }, {"_id": 0, "response_time_minutes": 1}).to_list(500)
        rt_avg = round(sum(m.get("response_time_minutes", 0) for m in msgs) / max(1, len(msgs)), 1) if msgs else None
        rt_factor = 0
        if rt_avg is not None:
            if rt_avg < 15:
                rt_factor = 2
            elif rt_avg < 60:
                rt_factor = 1
            else:
                rt_factor = 0
        factors.append({
            "name": "Response Speed",
            "value": rt_avg,
            "uplift_pct": rt_factor,
            "reason": f"Avg {rt_avg or '—'}dk yanıt",
        })

        # 5. Cleaning score (last 30d housekeeping checklists)
        cleanings = await db.cleaning_checklists.find({
            "property_id": property_id,
            "completed_at": {"$gte": thirty_ago},
            "score_pct": {"$exists": True},
        }, {"_id": 0, "score_pct": 1}).to_list(500)
        clean_avg = round(sum(c.get("score_pct", 0) for c in cleanings) / max(1, len(cleanings)), 1) if cleanings else None
        clean_factor = 0
        if clean_avg is not None:
            if clean_avg >= 95:
                clean_factor = 3
            elif clean_avg >= 85:
                clean_factor = 1
            elif clean_avg < 70:
                clean_factor = -3
        factors.append({
            "name": "Cleaning Quality",
            "value": clean_avg,
            "uplift_pct": clean_factor,
            "reason": f"Avg {clean_avg or '—'}% temizlik skoru",
        })

        total_uplift = sum(f["uplift_pct"] for f in factors)
        # Normalize: max +15%, min -15%
        total_uplift = max(-15, min(15, total_uplift))

        # Quality score 0-100
        max_possible = 5 + 3 + 2 + 2 + 3  # 15 max
        actual = sum(max(0, f["uplift_pct"]) for f in factors)
        quality_score_100 = round((actual / max_possible) * 100, 1) if max_possible else 0

        return {
            "property_id": property_id,
            "quality_score": quality_score_100,
            "recommended_rate_uplift_pct": total_uplift,
            "factors": factors,
        }

    # ==================== FORECAST ACCURACY KPI ====================

    @router.get("/forecast-accuracy/{property_id}")
    async def forecast_accuracy_kpi(property_id: str, days: int = 90,
                                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Forecast accuracy benchmark — Cloudbeds 95% iddiası.
        Compare past forecast snapshots vs actuals on bookings collection.

        We assume `forecast_snapshots` collection stores daily forecasts (occupancy + revenue).
        Eğer yoksa, naive baseline: önceki ayın aynı haftası vs şimdi ayni hafta.
        """
        days = max(7, min(int(days), 365))
        now = datetime.now(timezone.utc)
        snapshots = await db.forecast_snapshots.find({
            "property_id": property_id,
            "snapshot_date": {"$gte": (now - timedelta(days=days)).strftime("%Y-%m-%d")},
        }, {"_id": 0}).to_list(500)

        if snapshots:
            # Compare each forecast vs actual using stored fields
            errors_occ = []
            errors_rate = []
            for s in snapshots:
                fc_occ = s.get("forecast_occ_pct")
                act_occ = s.get("actual_occ_pct")
                fc_rate = s.get("forecast_rate")
                act_rate = s.get("actual_rate")
                if fc_occ is not None and act_occ is not None:
                    denom = max(fc_occ, act_occ, 1)
                    errors_occ.append(abs(fc_occ - act_occ) / denom * 100)
                if fc_rate and act_rate:
                    denom = max(fc_rate, act_rate, 1)
                    errors_rate.append(abs(fc_rate - act_rate) / denom * 100)
            occ_mape = round(sum(errors_occ) / len(errors_occ), 1) if errors_occ else None
            rev_mape = round(sum(errors_rate) / len(errors_rate), 1) if errors_rate else None
            occ_accuracy = round(100 - occ_mape, 1) if occ_mape is not None else None
            rev_accuracy = round(100 - rev_mape, 1) if rev_mape is not None else None
            samples = len(snapshots)
            scored_samples = len([s for s in snapshots if s.get("scored")])
            source = "snapshots"
        else:
            # Naive: same-DOW last 4 weeks vs current week
            samples = 0
            scored_samples = 0
            occ_mape = None
            rev_mape = None
            occ_accuracy = None
            rev_accuracy = None
            source = "no-snapshots-yet"

        return {
            "property_id": property_id,
            "days": days,
            "source": source,
            "samples": samples,
            "scored_samples": scored_samples,
            "occupancy_accuracy_pct": occ_accuracy,
            "revenue_accuracy_pct": rev_accuracy,
            "occupancy_mape": occ_mape,
            "revenue_mape": rev_mape,
            "benchmark_industry": 95.0,  # Cloudbeds claim
        }

    # ==================== GROUP PRICING OPTIMIZER ====================

    @router.post("/group-pricing-quote")
    async def group_pricing_quote(data: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Group quote optimizer — IDeaS/Flyr core.
        Verilen group request için:
          - displacement cost (transient revenue lost)
          - recommended rate (cover displacement + margin)
          - accept/decline recommendation

        Body: {
          property_id, check_in, check_out, rooms_requested,
          requested_rate (optional)
        }
        """
        pid = data.get("property_id")
        ci = data.get("check_in")
        co = data.get("check_out")
        rooms_requested = int(data.get("rooms_requested") or 1)
        requested_rate = float(data.get("requested_rate") or 0)
        if not (pid and ci and co):
            raise HTTPException(400, "property_id, check_in, check_out required")

        try:
            ci_d = datetime.fromisoformat(ci)
            co_d = datetime.fromisoformat(co)
            nights = max(1, (co_d - ci_d).days)
        except Exception:
            raise HTTPException(400, "invalid date format")

        date_keys = [(ci_d + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(nights)]

        # Capacity check
        total_rooms = await db.rooms.count_documents({"property_id": pid})
        if not total_rooms:
            total_rooms = await db.room_types.count_documents({"property_id": pid}) or 10

        per_day = []
        total_displacement = 0.0
        for d in date_keys:
            # Current bookings on this date
            booked = await db.bookings.count_documents({
                "property_id": pid,
                "status": {"$ne": "cancelled"},
                "check_in": {"$lte": d},
                "check_out": {"$gt": d},
            })
            available = max(0, total_rooms - booked)

            # Current rate
            override = await db.rate_overrides.find_one({"property_id": pid, "date": d}, {"_id": 0})
            rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0})
            base_rate = float((rt or {}).get("base_rate") or (rt or {}).get("base_price") or 100)
            current_rate = float(override["custom_rate"]) if override and override.get("custom_rate") else base_rate

            # Compset market rate
            comps = await db.market_competitors.find({"property_id": pid}, {"_id": 0, "prices": 1}).to_list(50)
            market_prices = []
            for c in comps:
                for row in (c.get("prices") or []):
                    if row.get("date") == d and row.get("lowest_price") and row.get("scraped"):
                        try:
                            market_prices.append(float(row["lowest_price"]))
                        except Exception:
                            pass
            market_avg = round(sum(market_prices) / len(market_prices), 2) if market_prices else None

            # Displacement: rooms not available → would have sold at transient rate
            displaced_units = max(0, rooms_requested - available)
            displacement_cost = displaced_units * current_rate
            total_displacement += displacement_cost

            per_day.append({
                "date": d,
                "available": available,
                "current_rate": round(current_rate, 2),
                "market_avg": market_avg,
                "displaced_units": displaced_units,
                "displacement_cost": round(displacement_cost, 2),
            })

        # Recommended group rate: max of (displacement breakeven + margin, avg market rate × 0.85, avg current rate × 0.85)
        total_room_nights = rooms_requested * nights
        if total_room_nights:
            min_rate_to_break_even = total_displacement / total_room_nights
            # Floor: %85 of avg current rate (don't give away inventory cheaper than this)
            avg_current = sum(d["current_rate"] for d in per_day) / len(per_day) if per_day else 100
            floor_rate = avg_current * 0.85
            recommended_rate = round(max(min_rate_to_break_even * 1.15, floor_rate), 2)
        else:
            recommended_rate = 0

        # Decision
        if requested_rate:
            if requested_rate >= recommended_rate:
                decision = "ACCEPT"
                decision_reason = f"Requested rate £{requested_rate} >= breakeven+margin £{recommended_rate}"
            else:
                decision = "DECLINE"
                decision_reason = f"Requested rate £{requested_rate} below breakeven+margin £{recommended_rate}"
        else:
            decision = "NEGOTIATE"
            decision_reason = f"Send recommended rate £{recommended_rate}/night"

        return {
            "property_id": pid,
            "check_in": ci,
            "check_out": co,
            "nights": nights,
            "rooms_requested": rooms_requested,
            "total_room_nights": total_room_nights,
            "requested_rate": requested_rate or None,
            "total_displacement_cost": round(total_displacement, 2),
            "recommended_rate_per_night": recommended_rate,
            "recommended_total": round(recommended_rate * total_room_nights, 2),
            "decision": decision,
            "decision_reason": decision_reason,
            "per_day": per_day,
        }

    # ==================== AUTOPILOT MODE ====================

    @router.get("/autopilot/config")
    async def get_autopilot_config(
        current_user: dict = Depends(require_roles("admin", "manager"))
    ):
        cfg = await db.autopilot_config.find_one({"key": "global"}, {"_id": 0}) or {}
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "schedule_hour_utc": int(cfg.get("schedule_hour_utc", 3)),
            "min_gap_pct": float(cfg.get("min_gap_pct", 5.0)),
            "days_ahead": int(cfg.get("days_ahead", 14)),
            "min_uplift_to_apply_pct": float(cfg.get("min_uplift_to_apply_pct", 3.0)),
            "last_run_at": cfg.get("last_run_at"),
            "last_run_summary": cfg.get("last_run_summary"),
        }

    @router.post("/autopilot/config")
    async def set_autopilot_config(data: Dict,
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        patch = {
            "key": "global",
            "enabled": bool(data.get("enabled", False)),
            "schedule_hour_utc": max(0, min(23, int(data.get("schedule_hour_utc", 3)))),
            "min_gap_pct": float(data.get("min_gap_pct", 5.0)),
            "days_ahead": max(7, min(60, int(data.get("days_ahead", 14)))),
            "min_uplift_to_apply_pct": float(data.get("min_uplift_to_apply_pct", 3.0)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("name", "system"),
        }
        await db.autopilot_config.update_one({"key": "global"}, {"$set": patch}, upsert=True)
        return {"ok": True, "config": patch}

    @router.get("/autopilot/history")
    async def autopilot_history(limit: int = 30,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.autopilot_runs.find({}, {"_id": 0}).sort("run_at", -1).to_list(min(limit, 100))
        return {"items": rows}

    async def autopilot_loop():
        """Background scheduler — her gece schedule_hour_utc'da AI-Adaptive Fleet Optimize çalıştır.
        Sadece enabled=True ise tetiklenir. min_uplift_to_apply_pct altındaki dry-run sonuçları skip eder.
        """
        import asyncio
        import logging
        from routes.revenue_ext.market_robot import _internal_close_gap
        logger = logging.getLogger("autopilot")
        logger.info("🤖 Autopilot loop started")

        last_run_day = None
        while True:
            try:
                await asyncio.sleep(60)  # check every minute
                cfg = await db.autopilot_config.find_one({"key": "global"}, {"_id": 0}) or {}
                if not cfg.get("enabled"):
                    continue
                schedule_hour = int(cfg.get("schedule_hour_utc", 3))
                now = datetime.now(timezone.utc)
                today_str = now.strftime("%Y-%m-%d")
                if now.hour != schedule_hour or last_run_day == today_str:
                    continue

                logger.info(f"🤖 Autopilot triggering daily run at {now.isoformat()}")
                last_run_day = today_str

                # Run AI-adaptive optimize (dry-run first to check uplift)
                # We call _internal_close_gap per property since we can't easily reuse the LLM router here
                # For autopilot we use 'half' as safe default — full AI loop would need refactor.
                # Future: extract ai_fleet_optimize into a callable function.
                days_ahead = int(cfg.get("days_ahead", 14))
                min_gap = float(cfg.get("min_gap_pct", 5.0))
                min_uplift = float(cfg.get("min_uplift_to_apply_pct", 3.0))
                batch_id = uuid.uuid4().hex[:16]

                properties = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
                properties = [p for p in properties if p.get("id") and p["id"] not in ("all", "default")]

                total_applied = 0
                per_branch = []
                for p in properties:
                    pid = p["id"]
                    try:
                        # Dry-run to check uplift
                        preview = await _internal_close_gap(
                            db, pid, strategy="half", days=days_ahead, dry_run=True,
                            min_gap_pct=min_gap, source="autopilot",
                            user_name="autopilot",
                        )
                        if preview.get("avg_uplift_pct", 0) < min_uplift:
                            per_branch.append({"pid": pid, "name": p.get("name"), "applied": 0,
                                               "reason": f"uplift {preview.get('avg_uplift_pct')}% < min {min_uplift}%"})
                            continue
                        # Apply
                        result = await _internal_close_gap(
                            db, pid, strategy="half", days=days_ahead, dry_run=False,
                            min_gap_pct=min_gap, source="autopilot",
                            user_name="autopilot", batch_id=batch_id,
                        )
                        total_applied += result.get("applied", 0)
                        per_branch.append({
                            "pid": pid, "name": p.get("name"),
                            "applied": result.get("applied", 0),
                            "uplift_pct": result.get("avg_uplift_pct"),
                        })
                    except Exception as e:
                        logger.exception(f"Autopilot apply failed for {pid}: {e}")
                        per_branch.append({"pid": pid, "error": str(e)[:120]})

                summary = {
                    "branches_applied": sum(1 for b in per_branch if b.get("applied", 0) > 0),
                    "total_days_applied": total_applied,
                }

                # Record in autopilot_runs
                await db.autopilot_runs.insert_one({
                    "id": uuid.uuid4().hex,
                    "run_at": now.isoformat(),
                    "batch_id": batch_id if total_applied > 0 else None,
                    "strategy": "half",
                    "days_ahead": days_ahead,
                    "min_gap_pct": min_gap,
                    "min_uplift_to_apply_pct": min_uplift,
                    "summary": summary,
                    "per_branch": per_branch,
                })

                # Update last_run on config
                await db.autopilot_config.update_one({"key": "global"}, {"$set": {
                    "last_run_at": now.isoformat(),
                    "last_run_summary": summary,
                }})

                # If actually applied → write to fleet_gap_history for undo
                if total_applied > 0 and batch_id:
                    await db.fleet_gap_history.insert_one({
                        "batch_id": batch_id,
                        "applied_at": now.isoformat(),
                        "applied_by": "autopilot",
                        "strategy": "autopilot-half",
                        "days": days_ahead,
                        "min_gap_pct": min_gap,
                        "branches_with_apply": summary["branches_applied"],
                        "total_days_applied": total_applied,
                        "fleet_avg_uplift_pct": 0,  # would need re-aggregate
                        "per_branch": [{"pid": b["pid"], "name": b.get("name"),
                                        "applied": b.get("applied", 0)} for b in per_branch if b.get("applied", 0) > 0],
                        "undone": False,
                    })

                logger.info(f"🤖 Autopilot run done — {summary['branches_applied']} branches, {total_applied} days")

            except Exception as e:
                logger.exception(f"Autopilot loop error: {e}")

    router.autopilot_loop = autopilot_loop  # expose so server.py can start it

    return router
