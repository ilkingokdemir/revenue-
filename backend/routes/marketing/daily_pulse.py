"""
Daily Pulse (iter 401) — 08:00 GM digest email: yesterday's revenue, today's
arrivals/departures, occupancy, automation-attributed revenue and open risks.
One email per property per day (daily_pulse_log dedupe).
"""
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional

from fastapi import APIRouter, Depends

from routes.ai.upsell_autopilot import _send_email
from routes.marketing.automation_roi import compute_automation_health

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_daily_pulse_router(db, require_roles):
    router = APIRouter()

    async def _pulse_data(property_id: str) -> dict:
        today = datetime.now(timezone.utc).date()
        today_iso = today.isoformat()
        yesterday = (today - timedelta(days=1)).isoformat()
        pq = {} if property_id == "all" else {"property_id": property_id}

        active = {"status": {"$nin": ["cancelled"]}}
        arrivals = await db.bookings.count_documents({**pq, **active, "check_in": today_iso})
        departures = await db.bookings.count_documents({**pq, **active, "check_out": today_iso})
        in_house = await db.bookings.count_documents(
            {**pq, **active, "check_in": {"$lte": today_iso}, "check_out": {"$gt": today_iso}})
        rooms = await db.rooms.count_documents(pq) or 0
        occupancy = round(in_house * 100 / rooms, 1) if rooms else None

        # yesterday's booked revenue (new bookings created yesterday)
        pipeline = [
            {"$match": {**pq, "created_at": {"$gte": yesterday, "$lt": today_iso},
                        "status": {"$nin": ["cancelled"]}}},
            {"$group": {"_id": None, "count": {"$sum": 1}, "revenue": {"$sum": "$total_price"}}},
        ]
        booked = {"count": 0, "revenue": 0.0}
        async for d in db.bookings.aggregate(pipeline):
            booked = {"count": d.get("count", 0), "revenue": round(d.get("revenue") or 0, 2)}

        # automation-attributed yesterday (redeemed coupons + accepted upsells)
        red = await db.direct_conversion_offers.find(
            {**pq, "status": "redeemed", "redeemed_at": {"$gte": yesterday, "$lt": today_iso}},
            {"_id": 0, "redeemed_booking_value": 1}).to_list(1000)
        ups = await db.upsell_log.find(
            {"accepted_at": {"$gte": yesterday, "$lt": today_iso}},
            {"_id": 0, "revenue": 1}).to_list(1000)
        auto_rev = round(sum(float(r.get("redeemed_booking_value") or 0) for r in red)
                         + sum(float(u.get("revenue") or 0) for u in ups), 2)

        open_log = await db.logbook_entries.count_documents({**pq, "status": "open"})
        unanswered = await db.reviews.count_documents({**pq, "response_status": "pending"})
        awaiting_approval = await db.reviews.count_documents({**pq, "response_status": "pending_approval"})
        health = await compute_automation_health(db, property_id)
        failing_jobs = [f"{r['label']}" for r in health["rows"] if r["status"] == "failing"]

        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        sweeps = await db.leakage_sweep_log.find(
            {**pq, "ran_at": {"$gte": week_ago}}, {"_id": 0, "closed_total": 1}).to_list(100)
        leakage_closed_7d = round(sum(float(s.get("closed_total") or 0) for s in sweeps), 2)

        return {"property_id": property_id, "date": today_iso,
                "today": {"arrivals": arrivals, "departures": departures,
                          "in_house": in_house, "occupancy_pct": occupancy},
                "yesterday": {"new_bookings": booked["count"], "booked_revenue": booked["revenue"],
                              "automation_revenue": auto_rev},
                "leakage_closed_7d": leakage_closed_7d,
                "risks": {"open_logbook": open_log, "unanswered_reviews": unanswered,
                          "reviews_awaiting_approval": awaiting_approval,
                          "failing_automations": failing_jobs}}

    def _pulse_html(d: dict, hotel_name: str) -> str:
        t, y, r = d["today"], d["yesterday"], d["risks"]
        occ = f"%{t['occupancy_pct']}" if t.get("occupancy_pct") is not None else "—"
        risk_items = []
        if r["open_logbook"]:
            risk_items.append(f"<li>{r['open_logbook']} açık logbook kaydı</li>")
        if r["unanswered_reviews"]:
            risk_items.append(f"<li>{r['unanswered_reviews']} yanıtlanmamış yorum</li>")
        if r.get("reviews_awaiting_approval"):
            risk_items.append(f"<li>{r['reviews_awaiting_approval']} AI yanıt taslağı onay bekliyor</li>")
        for j in r.get("failing_automations") or []:
            risk_items.append(f"<li>Otomasyon HATALI: {j}</li>")
        risks_html = f"<ul style='margin:6px 0;padding-left:18px;color:#b91c1c;font-size:13px;'>{''.join(risk_items)}</ul>" if risk_items else "<p style='font-size:13px;color:#15803d;'>Dikkat gerektiren risk yok ✓</p>"
        cell = "padding:10px 14px;border-radius:10px;background:#fafaf9;border:1px solid #e7e5e4;"
        return f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#292524;">
          <h2 style="color:#292524;">📬 Günlük Nabız — {hotel_name}</h2>
          <p style="font-size:13px;color:#78716c;">{d['date']}</p>
          <table style="width:100%;border-collapse:separate;border-spacing:6px;">
            <tr>
              <td style="{cell}"><div style="font-size:22px;font-weight:bold;">{t['arrivals']}</div><div style="font-size:12px;color:#78716c;">Bugünkü varış</div></td>
              <td style="{cell}"><div style="font-size:22px;font-weight:bold;">{t['departures']}</div><div style="font-size:12px;color:#78716c;">Bugünkü çıkış</div></td>
              <td style="{cell}"><div style="font-size:22px;font-weight:bold;">{t['in_house']}</div><div style="font-size:12px;color:#78716c;">Konaklayan</div></td>
              <td style="{cell}"><div style="font-size:22px;font-weight:bold;">{occ}</div><div style="font-size:12px;color:#78716c;">Doluluk</div></td>
            </tr>
          </table>
          <h3 style="font-size:14px;margin-top:18px;">Dün</h3>
          <table style="width:100%;border-collapse:separate;border-spacing:6px;">
            <tr>
              <td style="{cell}"><div style="font-size:18px;font-weight:bold;">£{y['booked_revenue']:.0f}</div><div style="font-size:12px;color:#78716c;">{y['new_bookings']} yeni rezervasyon</div></td>
              <td style="{cell}"><div style="font-size:18px;font-weight:bold;color:#b45309;">£{y['automation_revenue']:.0f}</div><div style="font-size:12px;color:#78716c;">Otomasyon kazancı (kupon + upsell)</div></td>
              <td style="{cell}"><div style="font-size:18px;font-weight:bold;color:#0e7490;">£{d.get('leakage_closed_7d', 0):.0f}</div><div style="font-size:12px;color:#78716c;">Kapatılan sızıntı (7 gün)</div></td>
            </tr>
          </table>
          <h3 style="font-size:14px;margin-top:18px;">Dikkat gerektirenler</h3>
          {risks_html}
        </div>
        """

    async def _pulse_core(property_id: str = "") -> dict:
        pid = property_id or "default"
        today_iso = date.today().isoformat()
        if await db.daily_pulse_log.find_one({"property_id": pid, "date": today_iso}):
            return {"ok": True, "skipped": "already_sent_today"}
        d = await _pulse_data(pid)
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        hotel_name = prop.get("name") or "Oteliniz"
        recipients = await db.users.find(
            {"role": {"$in": ["admin", "manager"]}, "email": {"$not": {"$regex": "@hotel.test$"}}},
            {"_id": 0, "email": 1}).to_list(50)
        sent = 0
        html = _pulse_html(d, hotel_name)
        for u in recipients:
            result = await _send_email(u["email"], f"📬 Günlük Nabız · {hotel_name} · {today_iso}", html)
            if result in ("sent", "mock"):
                sent += 1
        await db.daily_pulse_log.insert_one({
            "property_id": pid, "date": today_iso, "sent_to": sent,
            "data": d, "sent_at": _now()})
        return {"ok": True, "sent_to": sent, "data": d}

    @router.get("/automation/daily-pulse/preview/{property_id}")
    async def preview(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _pulse_data(property_id)

    @router.post("/automation/daily-pulse/send")
    async def send_now(data: Optional[Dict] = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        pid = body.get("property_id") or "default"
        if body.get("force"):
            await db.daily_pulse_log.delete_one({"property_id": pid, "date": date.today().isoformat()})
        return await _pulse_core(pid)

    router.run_pulse_internal = _pulse_core
    return router
