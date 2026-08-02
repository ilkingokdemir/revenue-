"""
Monthly Automation Report Card (iter 410) — "your platform earned you £X this
month": consolidated monthly summary of all autonomous revenue engines,
emailed to owners/managers on the 1st of each month.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional

from fastapi import APIRouter, Depends

from routes.ai.upsell_autopilot import _send_email

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_report_card_router(db, require_roles):
    router = APIRouter()

    async def _report_data(property_id: str, days: int = 30) -> dict:
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=days)).isoformat()
        today = date.today().isoformat()
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}

        # 1. Coupon revenue (rebook / comeback / OTA→direct redemptions)
        coupons = await db.direct_conversion_offers.find(
            {**pq, "created_at": {"$gte": since}},
            {"_id": 0, "status": 1, "redeemed_booking_value": 1, "channel": 1}).to_list(20000)
        coupon_sent = len(coupons)
        redeemed = [c for c in coupons if c.get("status") == "redeemed"]
        coupon_revenue = round(sum(float(c.get("redeemed_booking_value") or 0) for c in redeemed), 2)

        # 2. Upsell revenue (accepted)
        ups_logs = await db.upsell_log.find(
            {"accepted_at": {"$gte": since}}, {"_id": 0, "revenue": 1, "booking_id": 1}).to_list(20000)
        if property_id != "all" and ups_logs:
            bids = list({l.get("booking_id") for l in ups_logs if l.get("booking_id")})
            ok = {b["id"] for b in await db.bookings.find(
                {"id": {"$in": bids}, "property_id": property_id}, {"_id": 0, "id": 1}).to_list(len(bids))}
            ups_logs = [l for l in ups_logs if l.get("booking_id") in ok]
        upsell_revenue = round(sum(float(l.get("revenue") or 0) for l in ups_logs), 2)
        ups_offers = await db.upsell_offers.find(
            {**pq, "source": "autopilot", "created_at": {"$gte": since}},
            {"_id": 0, "status": 1}).to_list(20000)
        upsell_sent = len(ups_offers)
        upsell_accepted = sum(1 for o in ups_offers if o.get("status") == "accepted")

        # 3. Cancel-save (saved bookings)
        saves = await db.save_offers.find(
            {**pq, "source": "autopilot", "created_at": {"$gte": since}},
            {"_id": 0, "booking_id": 1}).to_list(5000)
        saved_count, saved_revenue = 0, 0.0
        for s in saves:
            b = await db.bookings.find_one({"id": s["booking_id"]},
                                           {"_id": 0, "status": 1, "check_in": 1, "total_price": 1})
            if b and (b.get("status") in ("checked_in", "checked_out") or
                      (b.get("status") not in ("cancelled",) and (b.get("check_in") or "") <= today)):
                saved_count += 1
                saved_revenue += float(b.get("total_price") or 0)
        saved_revenue = round(saved_revenue, 2)

        # 4. No-show fees posted
        ns = await db.folio_items.find(
            {**pq, "category": "no_show", "created_at": {"$gte": since}},
            {"_id": 0, "amount": 1}).to_list(10000)
        noshow_posted = round(sum(float(x.get("amount") or 0) for x in ns), 2)

        # 5. Leakage closed by sweeps
        sweeps = await db.leakage_sweep_log.find(
            {**pq, "ran_at": {"$gte": since}}, {"_id": 0, "closed_total": 1}).to_list(1000)
        leakage_closed = round(sum(float(s.get("closed_total") or 0) for s in sweeps), 2)

        # 6. Nudges
        nudged_up = await db.upsell_offers.count_documents({**pq, "nudged_at": {"$gte": since}})
        nudged_cp = await db.rebook_dispatches.count_documents({**pq, "nudged_at": {"$gte": since}})

        # 7. Pickup — hedef vs gerçekleşen (bu ay)
        month_key = now.strftime("%Y-%m")
        pickup_actual = 0
        async for r in db.bookings.aggregate([
                {"$match": {**pq, "status": {"$nin": ["cancelled"]},
                            "created_at": {"$gte": f"{month_key}-01", "$lte": now.isoformat()}}},
                {"$group": {"_id": None, "rooms": {"$sum": {"$ifNull": ["$rooms", 1]}}}}]):
            pickup_actual = int(r.get("rooms") or 0)
        tgt_doc = await db.pickup_targets.find_one(
            {"property_id": property_id if property_id != "all" else "all", "month": month_key},
            {"_id": 0, "target_rooms": 1})
        pickup_target = int((tgt_doc or {}).get("target_rooms") or 0)

        grand_total = round(coupon_revenue + upsell_revenue + saved_revenue + noshow_posted, 2)
        return {"property_id": property_id, "days": days,
                "period_start": since[:10], "period_end": now.date().isoformat(),
                "grand_total": grand_total,
                "sections": {
                    "coupons": {"sent": coupon_sent, "redeemed": len(redeemed), "revenue": coupon_revenue},
                    "upsell": {"sent": upsell_sent, "accepted": upsell_accepted, "revenue": upsell_revenue},
                    "cancel_save": {"offers": len(saves), "saved": saved_count, "revenue": saved_revenue},
                    "noshow": {"posted": noshow_posted},
                    "leakage": {"closed": leakage_closed},
                    "nudges": {"sent": nudged_up + nudged_cp},
                    "pickup": {"month": month_key, "actual_rooms": pickup_actual,
                               "target_rooms": pickup_target,
                               "progress_pct": round(pickup_actual * 100 / pickup_target, 1) if pickup_target else None},
                }}

    def _pickup_html(d: dict) -> str:
        p = d["sections"].get("pickup") or {}
        if not p:
            return ""
        tgt = p.get("target_rooms") or 0
        prog = p.get("progress_pct")
        bar = ""
        if tgt and prog is not None:
            col = "#4ade80" if prog >= 100 else ("#818cf8" if prog >= 60 else "#fbbf24")
            bar = f"""<div style="background:#e7e5e4;border-radius:6px;height:8px;margin-top:8px;">
              <div style="background:{col};height:8px;border-radius:6px;width:{min(100, prog)}%;"></div></div>
              <div style="font-size:11px;color:#78716c;margin-top:4px;">Hedefin %{prog}'i tamamlandı</div>"""
        detail = f"{p.get('actual_rooms', 0)} oda satıldı" + (f" / hedef {tgt}" if tgt else " (hedef belirlenmedi)")
        return f"""
          <div style="border:1px solid #e7e5e4;border-radius:10px;padding:14px 16px;margin-top:6px;background:#fafaf9;">
            <div style="font-weight:bold;font-size:13px;">🎯 Aylık Pickup — {p.get('month', '')}</div>
            <div style="font-size:12px;color:#57534e;margin-top:2px;">{detail}</div>
            {bar}
          </div>"""

    def _report_html(d: dict, hotel_name: str) -> str:
        s = d["sections"]
        cell = "padding:12px 16px;border-radius:10px;background:#fafaf9;border:1px solid #e7e5e4;"
        rows = [
            ("Kupon kampanyaları (rebook · sepet · OTA→direkt)",
             f"{s['coupons']['redeemed']}/{s['coupons']['sent']} kullanım", s['coupons']['revenue']),
            ("Upsell Auto-Pilot", f"{s['upsell']['accepted']}/{s['upsell']['sent']} kabul", s['upsell']['revenue']),
            ("İptal Kurtarma", f"{s['cancel_save']['saved']} rezervasyon kurtarıldı", s['cancel_save']['revenue']),
            ("No-show tahsilatı", "folyoya işlendi", s['noshow']['posted']),
            ("Sızıntı taraması", "otomatik kapatıldı", s['leakage']['closed']),
        ]
        rows_html = "".join(
            f"""<tr><td style="{cell}">{name}<div style="font-size:11px;color:#78716c;">{detail}</div></td>
            <td style="{cell}text-align:right;font-weight:bold;">£{val:,.0f}</td></tr>"""
            for name, detail, val in rows)
        return f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#292524;">
          <h2>📊 Otomasyon Karnesi — {hotel_name}</h2>
          <p style="font-size:13px;color:#78716c;">{d['period_start']} → {d['period_end']}</p>
          <div style="background:#292524;color:#fff;border-radius:14px;padding:22px;text-align:center;margin:16px 0;">
            <div style="font-size:12px;color:#a8a29e;">Platformunuz bu dönemde size</div>
            <div style="font-size:34px;font-weight:bold;color:#4ade80;">£{d['grand_total']:,.0f}</div>
            <div style="font-size:12px;color:#a8a29e;">kazandırdı / kurtardı</div>
          </div>
          <table style="width:100%;border-collapse:separate;border-spacing:6px;">{rows_html}</table>
          {_pickup_html(d)}
          <p style="font-size:12px;color:#78716c;">Ayrıca {d['sections']['nudges']['sent']} akıllı hatırlatma
          e-postası otomatik gönderildi.</p>
        </div>
        """

    async def _send_core(property_id: str = "", force: bool = False) -> dict:
        pid = property_id or "default"
        month_key = date.today().strftime("%Y-%m")
        if not force and date.today().day != 1:
            return {"ok": True, "skipped": "not_first_of_month"}
        if not force and await db.report_card_log.find_one({"property_id": pid, "month": month_key}):
            return {"ok": True, "skipped": "already_sent_this_month"}
        d = await _report_data(pid, 30)
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        hotel_name = prop.get("name") or "Oteliniz"
        recipients = await db.users.find(
            {"role": {"$in": ["admin", "manager"]}, "email": {"$not": {"$regex": "@hotel.test$"}}},
            {"_id": 0, "email": 1}).to_list(50)
        html = _report_html(d, hotel_name)
        sent = 0
        for u in recipients:
            if await _send_email(u["email"], f"📊 Otomasyon Karnesi · {hotel_name} · {month_key}", html) in ("sent", "mock"):
                sent += 1
        await db.report_card_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "month": month_key,
            "sent_to": sent, "grand_total": d["grand_total"], "sent_at": _now()})
        return {"ok": True, "sent_to": sent, "grand_total": d["grand_total"]}

    @router.get("/automation/report-card/preview/{property_id}")
    async def preview(property_id: str, days: int = 30,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _report_data(property_id, min(max(days, 7), 365))

    @router.post("/automation/report-card/send")
    async def send_now(data: Optional[Dict] = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        return await _send_core(body.get("property_id") or "default", force=bool(body.get("force")))

    router.run_report_card_internal = _send_core
    return router
