"""
Tier-1 Master Operations Dashboard (P1+)
----------------------------------------
A single endpoint that aggregates KPIs from every keyless feature built in
Batches 1-10 so a manager sees the operational value of the whole platform
on one screen.

GET /tier1-dashboard/{property_id}?days=30
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_tier1_dashboard_router(db, require_roles):
    router = APIRouter()

    @router.get("/tier1-dashboard/{property_id}")
    async def dashboard(property_id: str, days: int = 30,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        out: Dict = {"property_id": property_id, "window_days": days, "computed_at": _now(),
                       "kpis": {}}

        # ---- Pre-Auth Holds (P0)
        ph = await db.preauth_holds.find({"property_id": property_id, "authorized_at": {"$gte": since}}, {"_id": 0}).to_list(2000)
        out["kpis"]["preauth"] = {
            "total_holds": len(ph),
            "currently_held": round(sum(float(h.get("amount") or 0) for h in ph if h.get("status") == "authorized"), 2),
            "captured": round(sum(float(h.get("captured_amount") or 0) for h in ph if h.get("status") == "captured"), 2),
        }

        # ---- Chargeback (P0)
        cb = await db.chargebacks.find({"property_id": property_id, "opened_at": {"$gte": since}}, {"_id": 0}).to_list(500)
        won = sum(1 for c in cb if c.get("status") == "won")
        lost = sum(1 for c in cb if c.get("status") == "lost")
        out["kpis"]["chargeback"] = {"cases": len(cb), "won": won, "lost": lost,
                                       "win_rate_pct": round(won * 100 / max(won + lost, 1), 1),
                                       "amount_at_risk": round(sum(float(c.get("amount") or 0) for c in cb if c.get("status") in ("pending", "submitted")), 2)}

        # ---- Web Push (P0)
        subs = await db.web_push_subs.count_documents({"property_id": property_id, "active": True})
        push_log = await db.web_push_log.count_documents({"property_id": property_id, "sent_at": {"$gte": since}})
        out["kpis"]["web_push"] = {"active_subscribers": subs, "pushes_sent": push_log}

        # ---- PMS-CRS (P0)
        crs_count = await db.crs_index.count_documents({"property_id": property_id})
        pms_count = await db.bookings.count_documents({"property_id": property_id})
        out["kpis"]["pms_crs"] = {"pms_bookings": pms_count, "crs_records": crs_count, "drift": pms_count - crs_count}

        # ---- Public API (P0)
        keys_active = await db.dev_api_keys.count_documents({"property_id": property_id, "active": True})
        api_calls = await db.dev_api_calls.count_documents({"property_id": property_id, "at": {"$gte": since}})
        out["kpis"]["public_api"] = {"active_keys": keys_active, "calls_in_window": api_calls}

        # ---- Mid-stay (P1)
        ms_resp = await db.mid_stay_responses.find({"property_id": property_id, "submitted_at": {"$gte": since}}, {"_id": 0}).to_list(2000)
        avg_score = round(sum(r.get("score", 0) for r in ms_resp) / max(len(ms_resp), 1), 2) if ms_resp else 0
        low = sum(1 for r in ms_resp if r.get("score", 5) <= 3)
        out["kpis"]["mid_stay"] = {"responses": len(ms_resp), "avg_score": avg_score, "low_scores": low}

        # ---- A/B Tests (P1)
        ab_active = await db.ab_experiments.count_documents({"property_id": property_id, "active": True})
        ab_events = await db.ab_events.count_documents({"key": {"$exists": True}, "at": {"$gte": since}})
        out["kpis"]["ab_test"] = {"active_experiments": ab_active, "events_in_window": ab_events}

        # ---- Pre-arrival drip (P1)
        pa_disp = await db.pre_arrival_dispatches.count_documents({"property_id": property_id, "scheduled_for": {"$gte": since}})
        pa_sent = await db.pre_arrival_dispatches.count_documents({"property_id": property_id, "status": "sent", "scheduled_for": {"$gte": since}})
        out["kpis"]["pre_arrival"] = {"dispatches": pa_disp, "sent": pa_sent}

        # ---- SR Voucher (P1) — covers birthday too via source=birthday
        srv = await db.service_recovery_vouchers.find({"property_id": property_id, "issued_at": {"$gte": since}}, {"_id": 0}).to_list(2000)
        sr_redeemed = sum(1 for v in srv if v.get("redeemed"))
        bday = sum(1 for v in srv if v.get("source") == "birthday")
        out["kpis"]["sr_voucher"] = {"issued": len(srv), "redeemed": sr_redeemed,
                                       "redeem_rate_pct": round(sr_redeemed * 100 / max(len(srv), 1), 1),
                                       "birthday_issued": bday}

        # ---- Folio split (P1)
        fs_settle = await db.folio_split_settlements.count_documents({"settled_at": {"$gte": since}})
        out["kpis"]["folio_split"] = {"settlements_in_window": fs_settle}

        # ---- Loyalty auto (P1)
        loy = await db.loyalty_auto_log.find({"property_id": property_id, "changed_at": {"$gte": since}}, {"_id": 0}).to_list(500)
        out["kpis"]["loyalty"] = {"upgrades": sum(1 for l in loy if l.get("action") == "upgrade"),
                                    "downgrades": sum(1 for l in loy if l.get("action") == "downgrade")}

        # ---- Late checkout (P1)
        lc = await db.late_checkout_offers.find({"property_id": property_id, "created_at": {"$gte": since}}, {"_id": 0}).to_list(500)
        lc_accept = [o for o in lc if o.get("status") == "accepted"]
        out["kpis"]["late_checkout"] = {"offers": len(lc), "accepted": len(lc_accept),
                                          "revenue": round(sum(float(o.get("accepted_price") or 0) for o in lc_accept), 2)}

        # ---- OTA forecast (P1) — recommended count over horizon
        cfg = await db.ota_forecast_config.find_one({"property_id": property_id}, {"_id": 0}) or {"horizon_days": 14}
        out["kpis"]["ota_forecast"] = {"horizon_days": cfg.get("horizon_days", 14)}

        # ---- Low stock (P1)
        ls_open = await db.inventory_alerts.count_documents({"property_id": property_id, "status": "open"})
        out["kpis"]["low_stock"] = {"open_alerts": ls_open}

        # ---- Rebook CTA (P1)
        rb = await db.rebook_dispatches.find({"property_id": property_id, "scheduled_for": {"$gte": since}}, {"_id": 0}).to_list(500)
        rb_clicked = sum(1 for r in rb if r.get("clicked"))
        out["kpis"]["rebook"] = {"sent": len(rb), "clicked": rb_clicked,
                                   "click_rate_pct": round(rb_clicked * 100 / max(len(rb), 1), 1)}

        # ---- Stay extensions (P1)
        se = await db.stay_extensions_log.find({"property_id": property_id, "applied_at": {"$gte": since}}, {"_id": 0}).to_list(500)
        out["kpis"]["stay_ext"] = {"extensions": len(se),
                                     "extra_nights": sum(int(r.get("extra_nights") or 0) for r in se),
                                     "extra_revenue": round(sum(float(r.get("charge") or 0) for r in se), 2)}

        # ---- Long-stay discount (P1)
        lst = await db.long_stay_log.find({"property_id": property_id, "applied_at": {"$gte": since}}, {"_id": 0}).to_list(500)
        out["kpis"]["long_stay"] = {"applied": len(lst),
                                      "discount_total": round(sum(float(r.get("discount_amount") or 0) for r in lst), 2)}

        # ---- Cancel insurance (P1)
        ins = await db.cancel_insurance_policies.find({"property_id": property_id, "purchased_at": {"$gte": since}}, {"_id": 0}).to_list(500)
        ins_claimed = sum(1 for p in ins if p.get("status") == "claimed")
        ins_revenue = round(sum(float(p.get("fee") or 0) for p in ins), 2)
        ins_loss = round(sum(float(p.get("fee") or 0) for p in ins if p.get("status") == "claimed"), 2)
        out["kpis"]["cancel_insurance"] = {"policies": len(ins), "claimed": ins_claimed,
                                              "fee_revenue": ins_revenue, "claim_loss_estimate": ins_loss,
                                              "net_pl": round(ins_revenue - ins_loss, 2)}

        # ---- Group rooming (P1)
        grp = await db.group_rooming_sessions.count_documents({"property_id": property_id, "status": "finalized", "created_at": {"$gte": since}})
        out["kpis"]["group_rooming"] = {"finalized_sessions": grp}

        # ---- CI slots (P1)
        cis = await db.ci_slot_reservations.count_documents({"property_id": property_id, "created_at": {"$gte": since}})
        cis_early = await db.ci_slot_reservations.count_documents({"property_id": property_id, "is_early": True, "created_at": {"$gte": since}})
        out["kpis"]["ci_slots"] = {"reservations": cis, "early_paid": cis_early}

        # ---- Highlights summary (top 5 wins)
        out["highlights"] = []
        if out["kpis"]["late_checkout"]["revenue"] > 0:
            out["highlights"].append({"label": "Late-checkout revenue captured", "value": f"£{out['kpis']['late_checkout']['revenue']}", "kind": "win"})
        if out["kpis"]["cancel_insurance"]["net_pl"] > 0:
            out["highlights"].append({"label": "Cancellation insurance net P&L", "value": f"£{out['kpis']['cancel_insurance']['net_pl']}", "kind": "win"})
        if out["kpis"]["stay_ext"]["extra_revenue"] > 0:
            out["highlights"].append({"label": "Stay-extension extra revenue", "value": f"£{out['kpis']['stay_ext']['extra_revenue']}", "kind": "win"})
        if out["kpis"]["mid_stay"]["low_scores"] > 0:
            out["highlights"].append({"label": "Mid-stay low scores caught early", "value": f"{out['kpis']['mid_stay']['low_scores']}", "kind": "alert"})
        if out["kpis"]["chargeback"]["win_rate_pct"] >= 50 and out["kpis"]["chargeback"]["cases"] > 0:
            out["highlights"].append({"label": "Chargeback win rate", "value": f"{out['kpis']['chargeback']['win_rate_pct']}%", "kind": "win"})
        if out["kpis"]["loyalty"]["upgrades"] > 0:
            out["highlights"].append({"label": "Loyalty tier upgrades", "value": f"{out['kpis']['loyalty']['upgrades']}", "kind": "win"})
        if out["kpis"]["low_stock"]["open_alerts"] > 0:
            out["highlights"].append({"label": "Open low-stock alerts", "value": f"{out['kpis']['low_stock']['open_alerts']}", "kind": "alert"})

        return out

    return router
