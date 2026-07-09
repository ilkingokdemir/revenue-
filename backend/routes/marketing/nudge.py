"""
Email Nudge (iter 400) — one automatic reminder with a different subject line
for unopened upsell offers (24h, before early-bird expires) and unclicked
rebook coupons (72h). Max 1 nudge per offer/dispatch.
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends

from routes.ai.upsell_autopilot import CATEGORY_TR, _early_bird, _send_email

logger = logging.getLogger(__name__)

UPSELL_NUDGE_HOURS = 24
COUPON_NUDGE_HOURS = 72


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsell_nudge_html(guest_name: str, title: str, price: float, accept_url: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#292524;">
      <h2 style="color:#dc2626;">Son fırsat: %10 indiriminizin süresi doluyor ⏳</h2>
      <p>Merhaba {guest_name or 'değerli misafirimiz'},</p>
      <p>Size özel <b>{title}</b> teklifinizdeki erken kabul indirimi yakında sona eriyor.</p>
      <p style="text-align:center;margin:20px 0;">
        <a href="{accept_url}" style="background:#dc2626;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block;">
          İndirimli Kabul Et — £{price:.0f}
        </a>
      </p>
    </div>
    """


def _coupon_nudge_html(guest_name: str, pct: float, coupon: str, book_url: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#292524;">
      <h2 style="color:#0e7490;">Kuponunuz hâlâ sizi bekliyor 🎁</h2>
      <p>Merhaba {guest_name or 'değerli misafirimiz'},</p>
      <p>%{int(pct)} indirim kuponunuz <b>{coupon}</b> henüz kullanılmadı. Kaçırmayın:</p>
      <p style="text-align:center;margin:20px 0;">
        <a href="{book_url}" style="background:#0891b2;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block;">
          İndirimle Rezervasyon Yap
        </a>
      </p>
    </div>
    """


def create_nudge_router(db, require_roles):
    router = APIRouter()

    async def _nudge_core(property_id: str = "") -> dict:
        now = datetime.now(timezone.utc)
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        pq: Dict = {} if not property_id or property_id == "all" else {"property_id": property_id}

        # 1. Upsell offers: sent, unviewed, older than 24h, never nudged
        up_cutoff = (now - timedelta(hours=UPSELL_NUDGE_HOURS)).isoformat()
        offers = await db.upsell_offers.find(
            {**pq, "source": "autopilot", "status": "sent",
             "created_at": {"$lt": up_cutoff},
             "viewed_at": {"$in": [None, ""]},
             "nudged_at": {"$exists": False}},
            {"_id": 0}).to_list(1000)
        upsell_nudged = 0
        for o in offers:
            b = await db.bookings.find_one({"id": o["booking_id"]}, {"_id": 0, "guest_email": 1, "guest_name": 1}) or {}
            if not b.get("guest_email") or not o.get("accept_token"):
                continue
            price, _, _ = _early_bird(o)
            title, _p = CATEGORY_TR.get(o.get("category"), ("Özel Teklif", ""))
            result = await _send_email(
                b["guest_email"],
                f"⏳ Son fırsat: {title} indirimi doluyor",
                _upsell_nudge_html(b.get("guest_name", ""), title, price, f"{base}/offer/{o['accept_token']}"))
            await db.upsell_offers.update_one(
                {"accept_token": o["accept_token"]},
                {"$set": {"nudged_at": _now(), "nudge_result": result}})
            upsell_nudged += 1

        # 2. Rebook dispatches: sent, unclicked, older than 72h, never nudged
        cp_cutoff = (now - timedelta(hours=COUPON_NUDGE_HOURS)).isoformat()
        dispatches = await db.rebook_dispatches.find(
            {**pq, "status": "sent", "clicked": False,
             "scheduled_for": {"$lt": cp_cutoff},
             "nudged_at": {"$exists": False}},
            {"_id": 0}).to_list(1000)
        coupon_nudged = 0
        for d in dispatches:
            if not d.get("guest_email") or not d.get("coupon_code"):
                continue
            book_url = f"{base}/book/{d.get('property_id') or 'default'}?coupon={d['coupon_code']}&rebook={d.get('token', '')}"
            result = await _send_email(
                d["guest_email"],
                f"🎁 %{int(d.get('loyalty_discount_pct', 10))} indirim kuponunuz hâlâ geçerli",
                _coupon_nudge_html(d.get("guest_name", ""), d.get("loyalty_discount_pct", 10),
                                   d["coupon_code"], book_url))
            await db.rebook_dispatches.update_one(
                {"id": d["id"]}, {"$set": {"nudged_at": _now(), "nudge_result": result}})
            coupon_nudged += 1

        return {"ok": True, "upsell_nudged": upsell_nudged, "coupon_nudged": coupon_nudged,
                "scanned": {"upsell": len(offers), "coupon": len(dispatches)}}

    @router.post("/automation/nudge/run")
    async def run_nudge(data: Optional[Dict] = None,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _nudge_core((data or {}).get("property_id", ""))

    @router.get("/automation/nudge/stats/{property_id}")
    async def nudge_stats(property_id: str, days: int = 30,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}

        ups = await db.upsell_offers.find(
            {**pq, "nudged_at": {"$gte": since}},
            {"_id": 0, "nudged_at": 1, "viewed_at": 1, "status": 1, "accepted_at": 1}).to_list(5000)
        up_recovered = sum(1 for u in ups if (
            (u.get("viewed_at") or "") > u["nudged_at"] or
            (u.get("status") == "accepted" and (u.get("accepted_at") or "") > u["nudged_at"])))

        dps = await db.rebook_dispatches.find(
            {**pq, "nudged_at": {"$gte": since}},
            {"_id": 0, "nudged_at": 1, "clicked": 1, "clicked_at": 1}).to_list(5000)
        cp_recovered = sum(1 for d in dps if d.get("clicked") and (d.get("clicked_at") or "") > d["nudged_at"])

        def rate(a, b): return round(a * 100 / max(b, 1), 1)
        return {"property_id": property_id, "days": days,
                "upsell": {"nudged": len(ups), "recovered": up_recovered,
                           "recovery_rate": rate(up_recovered, len(ups))},
                "coupon": {"nudged": len(dps), "recovered": cp_recovered,
                           "recovery_rate": rate(cp_recovered, len(dps))}}

    router.run_nudge_internal = _nudge_core
    return router
