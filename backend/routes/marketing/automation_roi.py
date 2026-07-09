"""
Automation ROI (iter 394) — one dashboard aggregating revenue attributed to
each automation loop: rebook, abandoned recovery, direct conversion (OTA→direct),
upsells and AI pricing (estimated uplift).
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
import logging

from routes.ai.ai_predictions import _score_upsell_propensity

logger = logging.getLogger(__name__)


def create_automation_roi_router(db, require_roles, runners=None):
    router = APIRouter()
    runners = runners or {}

    @router.get("/automation/roi/{property_id}")
    async def roi(property_id: str, days: int = 30,
                  current_user: dict = Depends(require_roles("admin", "manager"))):
        days = min(max(days, 7), 365)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        pq = {} if property_id == "all" else {"property_id": property_id}

        # redeemed coupons by channel
        offers = await db.direct_conversion_offers.find(
            {**pq, "status": "redeemed", "redeemed_at": {"$gte": since}},
            {"_id": 0, "channel": 1, "redeemed_booking_value": 1,
             "commission_saved_actual": 1, "discount_pct": 1}).to_list(5000)
        by_ch = {}
        for o in offers:
            ch = o.get("channel") or "direct"
            e = by_ch.setdefault(ch, {"count": 0, "revenue": 0.0, "commission_saved": 0.0})
            e["count"] += 1
            e["revenue"] += float(o.get("redeemed_booking_value") or 0)
            e["commission_saved"] += float(o.get("commission_saved_actual") or 0)

        rebook = by_ch.get("rebook", {"count": 0, "revenue": 0.0})
        comeback = by_ch.get("comeback", {"count": 0, "revenue": 0.0})
        dc = {"count": 0, "revenue": 0.0, "commission_saved": 0.0}
        for ch, e in by_ch.items():
            if ch not in ("rebook", "comeback"):
                dc["count"] += e["count"]
                dc["revenue"] += e["revenue"]
                dc["commission_saved"] += e["commission_saved"]

        # abandoned carts recovered (secondary signal, cart value)
        rec_carts = await db.abandoned_carts.find(
            {**pq, "recovered": True, "converted_at": {"$gte": since}},
            {"_id": 0, "rate": 1}).to_list(2000)
        comeback_cart_value = sum(float(c.get("rate") or 0) for c in rec_carts)

        # upsell revenue (upsell_log has no property_id → join via bookings)
        logs = await db.upsell_log.find(
            {"accepted_at": {"$gte": since}}, {"_id": 0, "booking_id": 1, "revenue": 1}).to_list(5000)
        upsell_count, upsell_rev = 0, 0.0
        if logs:
            if property_id == "all":
                upsell_count = len(logs)
                upsell_rev = sum(float(l.get("revenue") or 0) for l in logs)
            else:
                bids = list({l.get("booking_id") for l in logs if l.get("booking_id")})
                ok_ids = set()
                if bids:
                    bs = await db.bookings.find(
                        {"id": {"$in": bids}, "property_id": property_id},
                        {"_id": 0, "id": 1}).to_list(len(bids))
                    ok_ids = {b["id"] for b in bs}
                for l in logs:
                    if l.get("booking_id") in ok_ids:
                        upsell_count += 1
                        upsell_rev += float(l.get("revenue") or 0)

        # AI pricing — estimated uplift from positive auto-applied rate changes
        decs = await db.ai_pricing_decisions.find(
            {**pq, "decided_at": {"$gte": since}},
            {"_id": 0, "new_rate": 1, "prev_rate": 1}).to_list(10000)
        ai_count = len(decs)
        ai_uplift = sum(max(float(d.get("new_rate") or 0) - float(d.get("prev_rate") or 0), 0) for d in decs)

        rows = [
            {"key": "rebook", "name": "Rebook Kampanyası",
             "desc": "Check-out sonrası kuponlu tekrar rezervasyon e-postaları",
             "count": rebook["count"], "revenue": round(rebook["revenue"], 2), "estimated": False},
            {"key": "comeback", "name": "Terk Edilmiş Kurtarma",
             "desc": "Yarım kalan rezervasyonlara hatırlatma + kupon",
             "count": comeback["count"] + len(rec_carts),
             "revenue": round(comeback["revenue"] + (comeback_cart_value if comeback["revenue"] == 0 else 0), 2),
             "estimated": False},
            {"key": "direct_conversion", "name": "OTA → Direkt Dönüşüm",
             "desc": "OTA misafirini direkte çeviren kuponlar (komisyon tasarrufu dahil)",
             "count": dc["count"], "revenue": round(dc["revenue"], 2),
             "extra": round(dc["commission_saved"], 2), "estimated": False},
            {"key": "upsell", "name": "Upsell Motoru",
             "desc": "Oda yükseltme ve ek hizmet satışları",
             "count": upsell_count, "revenue": round(upsell_rev, 2), "estimated": False},
            {"key": "ai_pricing", "name": "AI Fiyatlama (tahmini)",
             "desc": "Pozitif fiyat optimizasyonlarının oda-gece başına tahmini katkısı",
             "count": ai_count, "revenue": round(ai_uplift, 2), "estimated": True},
        ]
        total_real = sum(r["revenue"] for r in rows if not r["estimated"]) + dc["commission_saved"]
        total_est = sum(r["revenue"] for r in rows if r["estimated"])
        return {"property_id": property_id, "days": days, "rows": rows,
                "total_attributed": round(total_real, 2),
                "total_estimated": round(total_est, 2),
                "commission_saved": round(dc["commission_saved"], 2)}

    @router.get("/automation/opportunities/{property_id}")
    async def opportunities(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Missed-revenue radar: what automations are NOT being used."""
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        pq = {} if property_id == "all" else {"property_id": property_id}

        # 1. Rebook: checked-out guests (7-90d ago) without a rebook dispatch
        since90 = (now - timedelta(days=90)).date().isoformat()
        until7 = (now - timedelta(days=7)).date().isoformat()
        outs = await db.bookings.find(
            {**pq, "status": "checked_out", "check_out": {"$gte": since90, "$lt": until7}},
            {"_id": 0, "id": 1, "total_price": 1}).to_list(5000)
        dispatched = set()
        if outs:
            ds = await db.rebook_dispatches.find(
                {"booking_id": {"$in": [b["id"] for b in outs]}},
                {"_id": 0, "booking_id": 1}).to_list(5000)
            dispatched = {d["booking_id"] for d in ds}
        missed_rebook = [b for b in outs if b["id"] not in dispatched]
        avg_price = (sum(float(b.get("total_price") or 0) for b in missed_rebook)
                     / max(len(missed_rebook), 1))
        rebook_potential = len(missed_rebook) * avg_price * 0.06  # ~6% rebook conversion

        # 2. Abandoned carts never emailed (last 14d)
        since14 = (now - timedelta(days=14)).isoformat()
        carts = await db.abandoned_carts.find(
            {**pq, "status": "abandoned", "email_sent": {"$ne": True},
             "$or": [{"email_sent_at": ""}, {"email_sent_at": None}, {"email_sent_at": {"$exists": False}}],
             "created_at": {"$gte": since14}},
            {"_id": 0, "total_price": 1, "rate": 1}).to_list(2000)
        cart_potential = sum(float(c.get("total_price") or c.get("rate") or 0) for c in carts) * 0.10  # ~10% recovery

        # 3. Upcoming arrivals (14d) without any upsell offer
        horizon = (now + timedelta(days=14)).date().isoformat()
        arrivals = await db.bookings.find(
            {**pq, "status": {"$in": ["confirmed", "checked_in", "pending_payment"]},
             "check_in": {"$gte": today, "$lte": horizon}},
            {"_id": 0}).to_list(2000)
        offered = set()
        if arrivals:
            offs = await db.upsell_offers.find(
                {"booking_id": {"$in": [b["id"] for b in arrivals]}},
                {"_id": 0, "booking_id": 1}).to_list(2000)
            offered = {o["booking_id"] for o in offs}
        no_offer = [b for b in arrivals if b["id"] not in offered]
        # only high-propensity (score>=60) arrivals — aligned with autopilot
        high = []
        for b in no_offer:
            guest = await db.guest_profiles.find_one({"id": b.get("guest_id")}, {"_id": 0}) or {}
            if _score_upsell_propensity(b, guest)["top_score"] >= 60:
                high.append(b)
        no_offer = high
        nightly = [float(b.get("total_price") or 0) / max(int(b.get("nights") or 1), 1) for b in no_offer]
        upsell_potential = sum(nightly) * 0.12  # ~12% of nightly rate per accepted upsell

        # 4. OTA guests (last 90d) never targeted with a direct-conversion coupon
        ota = await db.bookings.find(
            {**pq, "status": "checked_out", "check_out": {"$gte": since90, "$lt": today},
             "source": {"$nin": ["direct", "website", "booking_engine", None, ""]}},
            {"_id": 0, "guest_email": 1, "total_price": 1}).to_list(5000)
        emails = list({(b.get("guest_email") or "").lower() for b in ota if b.get("guest_email")})
        couponed = set()
        if emails:
            cs = await db.direct_conversion_offers.find(
                {"guest_email": {"$in": emails}}, {"_id": 0, "guest_email": 1}).to_list(5000)
            couponed = {c["guest_email"] for c in cs}
        missed_ota = [b for b in ota if (b.get("guest_email") or "").lower() not in couponed]
        commission_at_stake = sum(float(b.get("total_price") or 0) for b in missed_ota) * 0.18
        ota_potential = commission_at_stake * 0.20  # ~20% repeat-direct probability

        rows = [
            {"key": "rebook", "name": "Rebook Fırsatı",
             "desc": "Check-out yapmış ama rebook kuponu gönderilmemiş misafirler",
             "count": len(missed_rebook), "potential": round(rebook_potential, 2),
             "action": "Rebook taraması çalıştır", "view": "rebook"},
            {"key": "comeback", "name": "Kurtarılmamış Sepetler",
             "desc": "Son 14 günde e-posta gönderilmemiş terk edilmiş sepetler",
             "count": len(carts), "potential": round(cart_potential, 2),
             "action": "Kurtarma e-postalarını gönder", "view": "rebook"},
            {"key": "upsell", "name": "Tekliflendirilmemiş Varışlar",
             "desc": "Yüksek upsell potansiyelli (skor ≥60) teklif almamış yaklaşan varışlar",
             "count": len(no_offer), "potential": round(upsell_potential, 2),
             "action": "Upsell skorlarını gör", "view": "ai-predictions"},
            {"key": "direct_conversion", "name": "Dönüştürülmemiş OTA Misafirleri",
             "desc": "Direkt kanala çekilmemiş OTA misafirleri (komisyon riski)",
             "count": len(missed_ota), "potential": round(ota_potential, 2),
             "extra": round(commission_at_stake, 2),
             "action": "Dönüşüm kuponu kampanyası", "view": "direct-conversion"},
        ]
        return {"property_id": property_id, "rows": rows,
                "total_potential": round(sum(r["potential"] for r in rows), 2)}

    @router.get("/automation/roi/{property_id}/trend")
    async def roi_trend(property_id: str, weeks: int = 8,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        weeks = min(max(weeks, 4), 26)
        now = datetime.now(timezone.utc)
        pq = {} if property_id == "all" else {"property_id": property_id}
        since = (now - timedelta(weeks=weeks)).isoformat()

        offers = await db.direct_conversion_offers.find(
            {**pq, "status": "redeemed", "redeemed_at": {"$gte": since}},
            {"_id": 0, "redeemed_at": 1, "redeemed_booking_value": 1}).to_list(5000)
        logs = await db.upsell_log.find(
            {"accepted_at": {"$gte": since}},
            {"_id": 0, "accepted_at": 1, "revenue": 1, "booking_id": 1}).to_list(5000)
        if property_id != "all" and logs:
            bids = list({l.get("booking_id") for l in logs if l.get("booking_id")})
            bs = await db.bookings.find(
                {"id": {"$in": bids}, "property_id": property_id},
                {"_id": 0, "id": 1}).to_list(len(bids))
            ok = {b["id"] for b in bs}
            logs = [l for l in logs if l.get("booking_id") in ok]

        buckets = []
        for i in range(weeks - 1, -1, -1):
            start = now - timedelta(weeks=i + 1)
            end = now - timedelta(weeks=i)
            s, e = start.isoformat(), end.isoformat()
            coupon_rev = sum(float(o.get("redeemed_booking_value") or 0)
                             for o in offers if s <= (o.get("redeemed_at") or "") < e)
            upsell_rev = sum(float(l.get("revenue") or 0)
                             for l in logs if s <= (l.get("accepted_at") or "") < e)
            buckets.append({"week": end.strftime("%d %b"),
                            "coupon": round(coupon_rev, 2), "upsell": round(upsell_rev, 2)})
        return {"property_id": property_id, "weeks": weeks, "buckets": buckets}

    @router.get("/automation/funnel/{property_id}")
    async def funnel(property_id: str, days: int = 30,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        pq = {} if property_id == "all" else {"property_id": property_id}

        # coupon funnel (rebook + comeback + direct conversion)
        coupons = await db.direct_conversion_offers.find(
            {**pq, "created_at": {"$gte": since}}, {"_id": 0, "status": 1}).to_list(10000)
        coupon_sent = len(coupons)
        coupon_redeemed = sum(1 for c in coupons if c.get("status") == "redeemed")
        dispatches = await db.rebook_dispatches.find(
            {**pq, "scheduled_for": {"$gte": since}}, {"_id": 0, "clicked": 1}).to_list(10000)
        coupon_clicked = sum(1 for d in dispatches if d.get("clicked"))

        # upsell funnel (autopilot offers)
        ups = await db.upsell_offers.find(
            {**pq, "source": "autopilot", "created_at": {"$gte": since}},
            {"_id": 0, "status": 1, "viewed_at": 1}).to_list(10000)
        up_sent = len(ups)
        up_viewed = sum(1 for u in ups if u.get("viewed_at"))
        up_accepted = sum(1 for u in ups if u.get("status") == "accepted")
        up_declined = sum(1 for u in ups if u.get("status") == "declined")

        def rate(a, b): return round(a * 100 / max(b, 1), 1)
        return {"property_id": property_id, "days": days,
                "coupon": {"sent": coupon_sent, "clicked": coupon_clicked,
                           "redeemed": coupon_redeemed,
                           "click_rate": rate(coupon_clicked, coupon_sent),
                           "redeem_rate": rate(coupon_redeemed, coupon_sent)},
                "upsell": {"sent": up_sent, "viewed": up_viewed,
                           "accepted": up_accepted, "declined": up_declined,
                           "view_rate": rate(up_viewed, up_sent),
                           "accept_rate": rate(up_accepted, up_sent)}}

    @router.post("/automation/opportunities/{property_id}/auto-fix")
    async def auto_fix(property_id: str, body: dict = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """One-click: backfill rebook sweep (7-90d checkouts) + abandoned cart recovery."""
        actions = (body or {}).get("actions") or ["rebook", "comeback", "upsell"]
        pid = "" if property_id == "all" else property_id
        results = {}

        if "rebook" in actions and runners.get("rebook_sweep"):
            queued = sent = 0
            for d in range(7, 91):
                try:
                    r = await runners["rebook_sweep"](pid, d)
                    queued += int(r.get("queued") or 0)
                    sent += int(r.get("emails_sent") or 0)
                except Exception as e:
                    logger.warning(f"auto-fix rebook day {d}: {e}")
            results["rebook"] = {"queued": queued, "sent": sent}

        if "comeback" in actions and runners.get("abandoned_recovery"):
            try:
                r = await runners["abandoned_recovery"](pid)
                results["comeback"] = {k: r.get(k) for k in ("eligible", "emails_sent") if k in r} or r
            except Exception as e:
                results["comeback"] = {"error": str(e)}

        if "upsell" in actions and runners.get("upsell_autopilot"):
            try:
                r = await runners["upsell_autopilot"](pid)
                results["upsell"] = {k: r.get(k) for k in ("scanned", "offers_sent", "skipped_low_score") if k in r} or r
            except Exception as e:
                results["upsell"] = {"error": str(e)}

        await db.automation_fix_runs.insert_one({
            "property_id": property_id, "actions": actions, "results": results,
            "run_by": current_user.get("email"),
            "run_at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "results": results}

    return router
