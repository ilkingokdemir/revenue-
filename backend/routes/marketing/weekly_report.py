"""
Weekly Management Report (iter 424) — Monday morning email with last week's
key figures vs the previous week (deltas), reusing the Key Figures engine.
"""
import logging
import io
import csv
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional

from fastapi import APIRouter, Depends

from routes.ai.upsell_autopilot import _send_email

logger = logging.getLogger(__name__)

TILE_TR = [
    ("nights_sold", "Satılan gece", ""),
    ("avg_occupancy_pct", "Ortalama doluluk", "%"),
    ("avg_price_per_night", "Gecelik ortalama fiyat (ADR)", "£"),
    ("avg_booking_window_days", "Rezervasyon penceresi (gün)", ""),
    ("avg_stay_nights", "Ortalama konaklama (gece)", ""),
    ("total_online_pct", "Toplam online", "%"),
    ("guest_count", "Misafir sayısı", ""),
    ("spaces_revenue", "Alan geliri (Spaces)", "£"),
    ("total_revenue", "Toplam gelir", "£"),
    ("cancellation_pct", "İptal / no-show oranı", "%"),
    ("commission_costs", "Komisyon maliyeti", "£"),
]
BAD_UP = {"cancellation_pct", "commission_costs"}


def _fmt(key: str, unit: str, v) -> str:
    if unit == "£":
        return f"£{float(v):,.0f}"
    if unit == "%":
        return f"%{v}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def create_weekly_report_router(db, require_roles, compute_key_figures):
    router = APIRouter()

    async def _report_data(property_id: str) -> dict:
        today = date.today()
        end = today - timedelta(days=1)
        start = end - timedelta(days=6)
        p_end = start - timedelta(days=1)
        p_start = p_end - timedelta(days=6)
        pq: Dict = {} if not property_id or property_id in ("all", "default") else {"property_id": property_id}
        cur = await compute_key_figures(pq, start, end, "staying")
        prev = await compute_key_figures(pq, p_start, p_end, "staying")
        rows = []
        for key, label, unit in TILE_TR:
            v, pv = cur["tiles"].get(key, 0), prev["tiles"].get(key, 0)
            pct = round((v - pv) / pv * 100, 1) if pv else None
            rows.append({"key": key, "label": label, "unit": unit,
                         "value": v, "prev": pv, "pct": pct})
        return {"start": start.isoformat(), "end": end.isoformat(),
                "prev_start": p_start.isoformat(), "prev_end": p_end.isoformat(),
                "rows": rows, "breakdown": cur["breakdown"],
                "booking_count": cur["booking_count"]}

    def _report_html(d: dict, hotel_name: str) -> str:
        trs = []
        for r in d["rows"]:
            pct = r["pct"]
            if pct is None:
                delta = "<span style='color:#a8a29e;'>—</span>"
            else:
                up = pct >= 0
                good = (not up) if r["key"] in BAD_UP else up
                color = "#15803d" if good else "#b91c1c"
                arrow = "▲" if up else "▼"
                delta = f"<span style='color:{color};font-weight:bold;'>{arrow} %{abs(pct)}</span>"
            trs.append(f"""
            <tr>
              <td style="padding:8px 12px;font-size:13px;color:#292524;border-bottom:1px solid #f5f5f4;">{r['label']}</td>
              <td style="padding:8px 12px;font-size:13px;font-weight:bold;text-align:right;border-bottom:1px solid #f5f5f4;">{_fmt(r['key'], r['unit'], r['value'])}</td>
              <td style="padding:8px 12px;font-size:12px;color:#78716c;text-align:right;border-bottom:1px solid #f5f5f4;">{_fmt(r['key'], r['unit'], r['prev'])}</td>
              <td style="padding:8px 12px;font-size:12px;text-align:right;border-bottom:1px solid #f5f5f4;">{delta}</td>
            </tr>""")
        b = d["breakdown"]
        return f"""
        <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#292524;">
          <h2 style="color:#292524;">📊 Haftalık Yönetim Raporu — {hotel_name}</h2>
          <p style="font-size:13px;color:#78716c;">{d['start']} → {d['end']} · önceki hafta ({d['prev_start']} → {d['prev_end']}) ile karşılaştırmalı · {d['booking_count']} rezervasyon</p>
          <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e7e5e4;border-radius:10px;">
            <tr style="background:#fafaf9;">
              <th style="padding:8px 12px;font-size:11px;color:#78716c;text-align:left;">GÖSTERGE</th>
              <th style="padding:8px 12px;font-size:11px;color:#78716c;text-align:right;">BU HAFTA</th>
              <th style="padding:8px 12px;font-size:11px;color:#78716c;text-align:right;">ÖNCEKİ</th>
              <th style="padding:8px 12px;font-size:11px;color:#78716c;text-align:right;">DEĞİŞİM</th>
            </tr>
            {''.join(trs)}
          </table>
          <h3 style="font-size:14px;margin-top:18px;">Gelir dökümü (bu hafta)</h3>
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <tr><td style="padding:4px 12px;color:#57534e;">Oda geliri</td><td style="text-align:right;font-weight:bold;">£{b['room_revenue']:,.0f}</td></tr>
            <tr><td style="padding:4px 12px;color:#57534e;">Oda dışı gelir</td><td style="text-align:right;">£{b['non_room_revenue']:,.0f}</td></tr>
            <tr><td style="padding:4px 12px;color:#57534e;">Komisyonlar</td><td style="text-align:right;color:#b91c1c;">−£{b['costs']['commissions']:,.0f}</td></tr>
            <tr><td style="padding:4px 12px;font-weight:bold;">Net (komisyon sonrası)</td><td style="text-align:right;font-weight:bold;">£{b['total_revenue'] - b['costs']['commissions']:,.0f}</td></tr>
          </table>
          <p style="font-size:11px;color:#a8a29e;margin-top:16px;">Bu rapor her pazartesi otomatik gönderilir — Otomasyon Ayarları'ndan yönetebilirsiniz.</p>
        </div>
        """

    async def _report_core(property_id: str = "") -> dict:
        pid = property_id or "all"
        week_key = date.today().strftime("%G-W%V")
        if await db.weekly_report_log.find_one({"property_id": pid, "week": week_key}):
            return {"ok": True, "skipped": "already_sent_this_week"}
        d = await _report_data(pid)
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        hotel_name = prop.get("name") or "Tüm Tesisler"
        recipients = await db.users.find(
            {"role": {"$in": ["admin", "manager"]}, "email": {"$not": {"$regex": "@hotel.test$"}}},
            {"_id": 0, "email": 1}).to_list(50)
        html = _report_html(d, hotel_name)
        sent = 0
        for u in recipients:
            result = await _send_email(
                u["email"], f"📊 Haftalık Yönetim Raporu · {hotel_name} · {d['start']} – {d['end']}", html)
            if result in ("sent", "mock"):
                sent += 1
        await db.weekly_report_log.insert_one({
            "property_id": pid, "week": week_key, "sent_to": sent,
            "data": d, "sent_at": datetime.now(timezone.utc).isoformat()})
        return {"ok": True, "sent_to": sent, "week": week_key, "data": d}

    @router.get("/reports/weekly-management/preview/{property_id}")
    async def preview(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _report_data(property_id)

    @router.post("/reports/weekly-management/send")
    async def send_now(data: Optional[Dict] = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        pid = body.get("property_id") or "all"
        if body.get("force"):
            await db.weekly_report_log.delete_one(
                {"property_id": pid, "week": date.today().strftime("%G-W%V")})
        return await _report_core(pid)

    router.run_weekly_report_internal = _report_core
    return router
