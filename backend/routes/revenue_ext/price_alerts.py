"""
Price Intelligence Alerts — Scans competitor prices, demand shifts, supply compression
and generates smart notifications for revenue managers.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_price_alerts_router(db, require_roles):
    router = APIRouter()

    DEFAULT_RULES = {
        "comp_price_drop_pct": 5,
        "comp_price_drop_abs": 10,
        "comp_price_rise_pct": 8,
        "comp_price_rise_abs": 15,
        "demand_spike_pp": 10,
        "demand_drop_pp": 10,
        "supply_compression_pct": 15,
        "rate_parity_diff_pct": 12,
        "occupancy_threshold_high": 85,
        "occupancy_threshold_low": 20,
        "scan_window_days": 14,
        "enabled": True,
    }

    async def _get_rules(property_id):
        doc = await db.price_alert_rules.find_one({"property_id": property_id}, {"_id": 0})
        if doc:
            return doc
        return {**DEFAULT_RULES, "property_id": property_id}

    async def _base_rate(property_id):
        rt = await db.room_types.find_one({"property_id": property_id}, {"_id": 0})
        return float(rt.get("base_rate", 100) or 100) if rt else 100.0

    # ===== GET ALERT RULES =====
    @router.get("/revenue/price-alerts/config/{property_id}")
    async def get_alert_config(property_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        rules = await _get_rules(property_id)
        return rules

    # ===== UPDATE ALERT RULES =====
    @router.put("/revenue/price-alerts/config/{property_id}")
    async def update_alert_config(property_id: str, data: Dict,
                                  current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "property_id": property_id,
            "comp_price_drop_pct": data.get("comp_price_drop_pct", DEFAULT_RULES["comp_price_drop_pct"]),
            "comp_price_drop_abs": data.get("comp_price_drop_abs", DEFAULT_RULES["comp_price_drop_abs"]),
            "comp_price_rise_pct": data.get("comp_price_rise_pct", DEFAULT_RULES["comp_price_rise_pct"]),
            "comp_price_rise_abs": data.get("comp_price_rise_abs", DEFAULT_RULES["comp_price_rise_abs"]),
            "demand_spike_pp": data.get("demand_spike_pp", DEFAULT_RULES["demand_spike_pp"]),
            "demand_drop_pp": data.get("demand_drop_pp", DEFAULT_RULES["demand_drop_pp"]),
            "supply_compression_pct": data.get("supply_compression_pct", DEFAULT_RULES["supply_compression_pct"]),
            "rate_parity_diff_pct": data.get("rate_parity_diff_pct", DEFAULT_RULES["rate_parity_diff_pct"]),
            "occupancy_threshold_high": data.get("occupancy_threshold_high", DEFAULT_RULES["occupancy_threshold_high"]),
            "occupancy_threshold_low": data.get("occupancy_threshold_low", DEFAULT_RULES["occupancy_threshold_low"]),
            "scan_window_days": data.get("scan_window_days", DEFAULT_RULES["scan_window_days"]),
            "enabled": data.get("enabled", True),
            "updated_at": now,
            "updated_by": current_user.get("name", ""),
        }
        await db.price_alert_rules.update_one(
            {"property_id": property_id}, {"$set": update}, upsert=True
        )
        return update

    # ===== GET ALERT HISTORY =====
    @router.get("/revenue/price-alerts/{property_id}")
    async def get_price_alerts(property_id: str, limit: int = 50,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"category": "price_intelligence"}
        if property_id != "all":
            query["property_id"] = property_id
        alerts = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
        unread = await db.notifications.count_documents({**query, "read": False})
        return {"alerts": alerts, "unread_count": unread, "total": len(alerts)}

    # ===== SCAN & GENERATE PRICE ALERTS =====
    @router.post("/revenue/price-alerts/scan/{property_id}")
    async def scan_price_alerts(property_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        """Scan market data and generate price intelligence notifications."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        rules = await _get_rules(property_id)

        if not rules.get("enabled", True):
            return {"generated": 0, "message": "Alert scanning is disabled"}

        # Determine properties
        if property_id == "all":
            props = await db.properties.find({}, {"_id": 0}).to_list(50)
        else:
            prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
            props = [prop] if prop else []

        generated = 0
        alerts_created = []
        scan_days = rules.get("scan_window_days", 14)

        for prop in props:
            pid = prop.get("id", "")
            if not pid:
                continue

            base_rate = await _base_rate(pid)

            # Get overrides (our rates)
            overrides = await db.rate_overrides.find({"property_id": pid}, {"_id": 0}).to_list(500)
            override_map = {ov["date"]: float(ov.get("custom_rate", base_rate)) for ov in overrides}

            # Get supply data (demand) — check both property-specific and "all" aggregated
            supply_query = {"$or": [{"property_id": pid}, {"property_id": "all"}]}
            supply_docs = await db.market_supply.find(supply_query, {"_id": 0}).sort("scanned_at", -1).to_list(2000)
            supply_map = {}
            for s in supply_docs:
                if s["date"] not in supply_map:
                    supply_map[s["date"]] = s

            # Get competitors — check both property-specific and "all"
            comp_query = {"$or": [{"property_id": pid}, {"property_id": "all"}]}
            competitors = await db.market_competitors.find(comp_query, {"_id": 0}).to_list(20)
            comp_date_prices = {}
            for comp in competitors:
                cid = comp.get("id", "")
                cname = comp.get("name", "Competitor")
                for p in (comp.get("prices") or []):
                    if p.get("scraped") and p.get("lowest_price"):
                        dt = p["date"]
                        if dt not in comp_date_prices:
                            comp_date_prices[dt] = []
                        comp_date_prices[dt].append({
                            "comp_id": cid,
                            "comp_name": cname,
                            "price": float(p["lowest_price"]),
                        })

            # Previous scan prices (from snapshots)
            prev_snapshots = await db.price_alert_snapshots.find(
                {"property_id": pid}, {"_id": 0}
            ).sort("scanned_at", -1).to_list(1)
            prev_snap = prev_snapshots[0] if prev_snapshots else None
            prev_prices = prev_snap.get("comp_prices", {}) if prev_snap else {}
            prev_demand = prev_snap.get("demand_map", {}) if prev_snap else {}
            prev_supply = prev_snap.get("supply_map", {}) if prev_snap else {}

            # Current scan data for snapshot
            current_comp_prices = {}
            current_demand_map = {}
            current_supply_map = {}

            # Dedupe key: prevent duplicate alerts for same date+type within 24h
            day_ago = (now - timedelta(hours=24)).isoformat()

            for i in range(scan_days):
                d = now + timedelta(days=i)
                ds = d.strftime("%Y-%m-%d")
                our_rate = override_map.get(ds, base_rate)

                # Current competitor prices for this date
                comp_prices_today = comp_date_prices.get(ds, [])
                if comp_prices_today:
                    avg_comp = sum(cp["price"] for cp in comp_prices_today) / len(comp_prices_today)
                    current_comp_prices[ds] = avg_comp
                else:
                    avg_comp = None
                    current_comp_prices[ds] = None

                # Supply/demand
                sup = supply_map.get(ds, {})
                demand = sup.get("unavailable_pct") if sup else None
                avail = sup.get("available_est") if sup else None
                current_demand_map[ds] = demand
                current_supply_map[ds] = avail

                # ===== CHECK 1: Competitor Price DROP =====
                if avg_comp is not None and ds in prev_prices and prev_prices[ds] is not None:
                    old_comp = prev_prices[ds]
                    if old_comp > 0:
                        change_abs = old_comp - avg_comp
                        change_pct = (change_abs / old_comp) * 100
                        if change_abs >= rules["comp_price_drop_abs"] or change_pct >= rules["comp_price_drop_pct"]:
                            existing = await db.notifications.find_one({
                                "category": "price_intelligence",
                                "sub_type": "comp_price_drop",
                                "alert_date": ds,
                                "property_id": pid,
                                "created_at": {"$gt": day_ago}
                            })
                            if not existing:
                                date_label = d.strftime("%a %d %b")
                                alert = {
                                    "id": str(uuid.uuid4()),
                                    "type": "warning",
                                    "title": f"Competitor Price Drop — {date_label}",
                                    "message": f"Average competitor rate for {date_label} dropped by £{change_abs:.0f} ({change_pct:.0f}%) from £{old_comp:.0f} to £{avg_comp:.0f}. Your rate: £{our_rate:.0f}.",
                                    "category": "price_intelligence",
                                    "sub_type": "comp_price_drop",
                                    "severity": "high" if change_pct >= rules["comp_price_drop_pct"] * 2 else "medium",
                                    "property_id": pid,
                                    "alert_date": ds,
                                    "target_user": "", "target_role": "manager",
                                    "link_to": "demand-radar",
                                    "priority": "high",
                                    "read": False,
                                    "created_by": "Price Intelligence",
                                    "created_at": now_iso,
                                    "meta": {
                                        "old_comp_avg": round(old_comp, 2),
                                        "new_comp_avg": round(avg_comp, 2),
                                        "our_rate": our_rate,
                                        "change_abs": round(change_abs, 2),
                                        "change_pct": round(change_pct, 1),
                                    }
                                }
                                await db.notifications.insert_one(alert)
                                alert.pop("_id", None)
                                alerts_created.append(alert)
                                generated += 1

                # ===== CHECK 2: Competitor Price RISE =====
                if avg_comp is not None and ds in prev_prices and prev_prices[ds] is not None:
                    old_comp = prev_prices[ds]
                    if old_comp > 0:
                        change_abs = avg_comp - old_comp
                        change_pct = (change_abs / old_comp) * 100
                        if change_abs >= rules["comp_price_rise_abs"] or change_pct >= rules["comp_price_rise_pct"]:
                            existing = await db.notifications.find_one({
                                "category": "price_intelligence",
                                "sub_type": "comp_price_rise",
                                "alert_date": ds,
                                "property_id": pid,
                                "created_at": {"$gt": day_ago}
                            })
                            if not existing:
                                date_label = d.strftime("%a %d %b")
                                alert = {
                                    "id": str(uuid.uuid4()),
                                    "type": "success",
                                    "title": f"Competitor Price Rise — {date_label}",
                                    "message": f"Average competitor rate for {date_label} rose by £{change_abs:.0f} ({change_pct:.0f}%) from £{old_comp:.0f} to £{avg_comp:.0f}. Your rate: £{our_rate:.0f} — opportunity to increase.",
                                    "category": "price_intelligence",
                                    "sub_type": "comp_price_rise",
                                    "severity": "medium",
                                    "property_id": pid,
                                    "alert_date": ds,
                                    "target_user": "", "target_role": "manager",
                                    "link_to": "demand-radar",
                                    "priority": "normal",
                                    "read": False,
                                    "created_by": "Price Intelligence",
                                    "created_at": now_iso,
                                    "meta": {
                                        "old_comp_avg": round(old_comp, 2),
                                        "new_comp_avg": round(avg_comp, 2),
                                        "our_rate": our_rate,
                                        "change_abs": round(change_abs, 2),
                                        "change_pct": round(change_pct, 1),
                                    }
                                }
                                await db.notifications.insert_one(alert)
                                alert.pop("_id", None)
                                alerts_created.append(alert)
                                generated += 1

                # ===== CHECK 3: Demand Spike =====
                if demand is not None and ds in prev_demand and prev_demand[ds] is not None:
                    old_demand = prev_demand[ds]
                    demand_change = demand - old_demand
                    if demand_change >= rules["demand_spike_pp"]:
                        existing = await db.notifications.find_one({
                            "category": "price_intelligence",
                            "sub_type": "demand_spike",
                            "alert_date": ds,
                            "property_id": pid,
                            "created_at": {"$gt": day_ago}
                        })
                        if not existing:
                            date_label = d.strftime("%a %d %b")
                            alert = {
                                "id": str(uuid.uuid4()),
                                "type": "warning",
                                "title": f"Demand Spike — {date_label}",
                                "message": f"Market demand for {date_label} surged {demand_change:+.0f}pp to {demand}%. Consider raising rates — current rate: £{our_rate:.0f}.",
                                "category": "price_intelligence",
                                "sub_type": "demand_spike",
                                "severity": "high" if demand_change >= rules["demand_spike_pp"] * 2 else "medium",
                                "property_id": pid,
                                "alert_date": ds,
                                "target_user": "", "target_role": "manager",
                                "link_to": "demand-radar",
                                "priority": "high",
                                "read": False,
                                "created_by": "Price Intelligence",
                                "created_at": now_iso,
                                "meta": {"old_demand": old_demand, "new_demand": demand, "change_pp": round(demand_change)}
                            }
                            await db.notifications.insert_one(alert)
                            alert.pop("_id", None)
                            alerts_created.append(alert)
                            generated += 1

                # ===== CHECK 4: Demand Drop =====
                if demand is not None and ds in prev_demand and prev_demand[ds] is not None:
                    old_demand = prev_demand[ds]
                    demand_drop = old_demand - demand
                    if demand_drop >= rules["demand_drop_pp"]:
                        existing = await db.notifications.find_one({
                            "category": "price_intelligence",
                            "sub_type": "demand_drop",
                            "alert_date": ds,
                            "property_id": pid,
                            "created_at": {"$gt": day_ago}
                        })
                        if not existing:
                            date_label = d.strftime("%a %d %b")
                            alert = {
                                "id": str(uuid.uuid4()),
                                "type": "error",
                                "title": f"Demand Drop — {date_label}",
                                "message": f"Market demand for {date_label} dropped {demand_drop:.0f}pp to {demand}%. Consider promotional pricing or rate reduction.",
                                "category": "price_intelligence",
                                "sub_type": "demand_drop",
                                "severity": "medium",
                                "property_id": pid,
                                "alert_date": ds,
                                "target_user": "", "target_role": "manager",
                                "link_to": "demand-radar",
                                "priority": "normal",
                                "read": False,
                                "created_by": "Price Intelligence",
                                "created_at": now_iso,
                                "meta": {"old_demand": old_demand, "new_demand": demand, "drop_pp": round(demand_drop)}
                            }
                            await db.notifications.insert_one(alert)
                            alert.pop("_id", None)
                            alerts_created.append(alert)
                            generated += 1

                # ===== CHECK 5: Supply Compression =====
                if avail is not None and ds in prev_supply and prev_supply[ds] is not None:
                    old_avail = prev_supply[ds]
                    if old_avail > 0:
                        supply_drop_pct = ((old_avail - avail) / old_avail) * 100
                        if supply_drop_pct >= rules["supply_compression_pct"]:
                            existing = await db.notifications.find_one({
                                "category": "price_intelligence",
                                "sub_type": "supply_compression",
                                "alert_date": ds,
                                "property_id": pid,
                                "created_at": {"$gt": day_ago}
                            })
                            if not existing:
                                date_label = d.strftime("%a %d %b")
                                alert = {
                                    "id": str(uuid.uuid4()),
                                    "type": "warning",
                                    "title": f"Supply Compression — {date_label}",
                                    "message": f"Available supply for {date_label} dropped {supply_drop_pct:.0f}% ({old_avail} → {avail}). Fewer rooms available = pricing power for you.",
                                    "category": "price_intelligence",
                                    "sub_type": "supply_compression",
                                    "severity": "medium",
                                    "property_id": pid,
                                    "alert_date": ds,
                                    "target_user": "", "target_role": "manager",
                                    "link_to": "demand-radar",
                                    "priority": "normal",
                                    "read": False,
                                    "created_by": "Price Intelligence",
                                    "created_at": now_iso,
                                    "meta": {"old_supply": old_avail, "new_supply": avail, "drop_pct": round(supply_drop_pct, 1)}
                                }
                                await db.notifications.insert_one(alert)
                                alert.pop("_id", None)
                                alerts_created.append(alert)
                                generated += 1

                # ===== CHECK 6: Rate Parity Breach =====
                if avg_comp is not None and our_rate > 0:
                    diff_pct = ((our_rate - avg_comp) / avg_comp) * 100
                    if abs(diff_pct) >= rules["rate_parity_diff_pct"]:
                        existing = await db.notifications.find_one({
                            "category": "price_intelligence",
                            "sub_type": "rate_parity",
                            "alert_date": ds,
                            "property_id": pid,
                            "created_at": {"$gt": day_ago}
                        })
                        if not existing:
                            date_label = d.strftime("%a %d %b")
                            direction = "above" if diff_pct > 0 else "below"
                            alert = {
                                "id": str(uuid.uuid4()),
                                "type": "error" if diff_pct > 0 else "info",
                                "title": f"Rate Parity Breach — {date_label}",
                                "message": f"Your rate (£{our_rate:.0f}) is {abs(diff_pct):.0f}% {direction} the competitor average (£{avg_comp:.0f}) for {date_label}.",
                                "category": "price_intelligence",
                                "sub_type": "rate_parity",
                                "severity": "high" if abs(diff_pct) >= rules["rate_parity_diff_pct"] * 2 else "medium",
                                "property_id": pid,
                                "alert_date": ds,
                                "target_user": "", "target_role": "manager",
                                "link_to": "compset-intel",
                                "priority": "high" if diff_pct > 0 else "normal",
                                "read": False,
                                "created_by": "Price Intelligence",
                                "created_at": now_iso,
                                "meta": {"our_rate": our_rate, "comp_avg": round(avg_comp, 2), "diff_pct": round(diff_pct, 1), "direction": direction}
                            }
                            await db.notifications.insert_one(alert)
                            alert.pop("_id", None)
                            alerts_created.append(alert)
                            generated += 1

                # ===== CHECK 7: High Demand Alert (no history needed) =====
                if demand is not None and demand >= rules.get("occupancy_threshold_high", 85):
                    existing = await db.notifications.find_one({
                        "category": "price_intelligence",
                        "sub_type": "demand_spike",
                        "alert_date": ds,
                        "property_id": pid,
                        "created_at": {"$gt": day_ago}
                    })
                    if not existing:
                        date_label = d.strftime("%a %d %b")
                        alert = {
                            "id": str(uuid.uuid4()),
                            "type": "warning",
                            "title": f"High Demand Detected — {date_label}",
                            "message": f"Market demand for {date_label} is at {demand}% — well above threshold ({rules['occupancy_threshold_high']}%). Current rate: £{our_rate:.0f}. Strong pricing power.",
                            "category": "price_intelligence",
                            "sub_type": "demand_spike",
                            "severity": "high" if demand >= 90 else "medium",
                            "property_id": pid,
                            "alert_date": ds,
                            "target_user": "", "target_role": "manager",
                            "link_to": "demand-radar",
                            "priority": "high",
                            "read": False,
                            "created_by": "Price Intelligence",
                            "created_at": now_iso,
                            "meta": {"new_demand": demand, "threshold": rules["occupancy_threshold_high"], "our_rate": our_rate}
                        }
                        await db.notifications.insert_one(alert)
                        alert.pop("_id", None)
                        alerts_created.append(alert)
                        generated += 1

                # ===== CHECK 8: Low Demand Warning (no history needed) =====
                if demand is not None and demand <= rules.get("occupancy_threshold_low", 20):
                    existing = await db.notifications.find_one({
                        "category": "price_intelligence",
                        "sub_type": "demand_drop",
                        "alert_date": ds,
                        "property_id": pid,
                        "created_at": {"$gt": day_ago}
                    })
                    if not existing:
                        date_label = d.strftime("%a %d %b")
                        alert = {
                            "id": str(uuid.uuid4()),
                            "type": "error",
                            "title": f"Low Demand Warning — {date_label}",
                            "message": f"Market demand for {date_label} is only {demand}% — below threshold ({rules['occupancy_threshold_low']}%). Consider promotions or rate reduction. Current rate: £{our_rate:.0f}.",
                            "category": "price_intelligence",
                            "sub_type": "demand_drop",
                            "severity": "medium",
                            "property_id": pid,
                            "alert_date": ds,
                            "target_user": "", "target_role": "manager",
                            "link_to": "demand-radar",
                            "priority": "normal",
                            "read": False,
                            "created_by": "Price Intelligence",
                            "created_at": now_iso,
                            "meta": {"new_demand": demand, "threshold": rules["occupancy_threshold_low"], "our_rate": our_rate}
                        }
                        await db.notifications.insert_one(alert)
                        alert.pop("_id", None)
                        alerts_created.append(alert)
                        generated += 1

            # Save current snapshot for next comparison
            snapshot = {
                "property_id": pid,
                "comp_prices": current_comp_prices,
                "demand_map": current_demand_map,
                "supply_map": current_supply_map,
                "scanned_at": now_iso,
            }
            await db.price_alert_snapshots.update_one(
                {"property_id": pid}, {"$set": snapshot}, upsert=True
            )

        return {
            "generated": generated,
            "alerts": alerts_created,
            "scanned_properties": len(props),
            "scan_window_days": scan_days,
            "scanned_at": now_iso,
        }

    # ===== DISMISS / ARCHIVE ALERT =====
    @router.put("/revenue/price-alerts/{alert_id}/dismiss")
    async def dismiss_alert(alert_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.notifications.update_one(
            {"id": alert_id, "category": "price_intelligence"},
            {"$set": {"read": True, "dismissed": True, "dismissed_at": datetime.now(timezone.utc).isoformat(), "dismissed_by": current_user.get("name", "")}}
        )
        return {"status": "dismissed"}

    # ===== ACKNOWLEDGE WITH ACTION =====
    @router.put("/revenue/price-alerts/{alert_id}/action")
    async def action_alert(alert_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        action = data.get("action", "acknowledged")
        note = data.get("note", "")
        await db.notifications.update_one(
            {"id": alert_id, "category": "price_intelligence"},
            {"$set": {
                "read": True,
                "actioned": True,
                "action_taken": action,
                "action_note": note,
                "actioned_at": datetime.now(timezone.utc).isoformat(),
                "actioned_by": current_user.get("name", ""),
            }}
        )
        return {"status": "actioned", "action": action}

    return router
