"""
Aylık Sahip/Yatırımcı Özeti (Owner Executive Summary)
Key Figures + Spaces + VCC + tahsilatları tek sayfada toplar,
PDF üretir ve sahibe e-postalar (mock fallback). Cron: her ayın 1'i 08:00.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from datetime import datetime, timezone, date, timedelta
from typing import Dict
import uuid
import os
import io
import logging

try:
    import resend
except Exception:
    resend = None

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _month_range(month: str):
    y, m = int(month[:4]), int(month[5:7])
    start = date(y, m, 1)
    end = (date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)) - timedelta(days=1)
    return start, end


def _prev_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def create_owner_summary_router(db, require_roles, compute_kf):
    router = APIRouter()

    async def _month_summary(pid: str, month: str) -> Dict:
        pq: Dict = {} if pid == "all" else {"property_id": pid}
        start, end = _month_range(month)
        kf = await compute_kf(pq, start, end, "staying")
        rng = {"$gte": start.isoformat(), "$lte": end.isoformat() + "T99"}
        vcc = await db.vcc_cards.find({**pq, "status": "charged", "charged_at": rng},
                                      {"_id": 0, "amount": 1}).to_list(2000)
        inv_paid = await db.city_ledger_invoices.find(
            {"status": "paid", "paid_at": rng}, {"_id": 0, "amount": 1}).to_list(500)
        rec_disputes = await db.ota_disputes.find(
            {**pq, "status": "recovered", "resolved_at": rng},
            {"_id": 0, "recovered_amount": 1}).to_list(500)
        tiles = kf.get("tiles", {})
        return {"month": month,
                "occupancy_pct": tiles.get("avg_occupancy_pct", 0),
                "adr": tiles.get("avg_price_per_night", 0),
                "total_revenue": tiles.get("total_revenue", 0),
                "room_revenue": kf.get("breakdown", {}).get("room_revenue", 0),
                "spaces_revenue": tiles.get("spaces_revenue", 0),
                "guest_count": tiles.get("guest_count", 0),
                "nights_sold": tiles.get("nights_sold", 0),
                "cancellation_pct": tiles.get("cancellation_pct", 0),
                "commission_costs": tiles.get("commission_costs", 0),
                "online_share_pct": tiles.get("total_online_pct", 0),
                "vcc_collected": round(sum(v["amount"] for v in vcc), 2),
                "vcc_recovered": round(sum(float(r.get("recovered_amount") or 0) for r in rec_disputes), 2),
                "invoices_collected": round(sum(i.get("amount", 0) for i in inv_paid), 2)}

    async def _full(pid: str, month: str) -> Dict:
        cur = await _month_summary(pid, month)
        prev = await _month_summary(pid, _prev_month(month))
        deltas = {}
        for k in ("occupancy_pct", "adr", "total_revenue", "spaces_revenue", "nights_sold"):
            deltas[k] = round(cur[k] - prev[k], 2)
        prop = None
        if pid != "all":
            prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1})
        return {"property_id": pid,
                "property_name": (prop or {}).get("name", "Tüm Tesisler"),
                "current": cur, "previous": prev, "deltas": deltas}

    @router.get("/owner-summary/{property_id}")
    async def get_summary(property_id: str, month: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        month = month or date.today().strftime("%Y-%m")
        return await _full(property_id, month)

    @router.get("/owner-summary/{property_id}/pdf")
    async def get_pdf(property_id: str, month: str = "",
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        month = month or date.today().strftime("%Y-%m")
        data = await _full(property_id, month)
        pdf = _build_pdf(data)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition":
                                 f"attachment; filename=sahip-ozeti-{month}.pdf"})

    @router.post("/owner-summary/send")
    async def send_summary(payload: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        pid = (payload or {}).get("property_id", "all")
        month = (payload or {}).get("month") or date.today().strftime("%Y-%m")
        to_email = ((payload or {}).get("email") or "").strip()
        if not to_email:
            raise HTTPException(400, "email zorunlu")
        data = await _full(pid, month)
        status = await _email_summary(to_email, data)
        await db.owner_summary_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "month": month,
            "email": to_email, "email_status": status,
            "sent_by": current_user.get("name", ""), "created_at": _now()})
        return {"ok": True, "email_status": status}

    async def _email_summary(to_email: str, data: Dict) -> str:
        c = data["current"]
        subject = f"{data['property_name']} — {c['month']} Sahip Özeti"
        rows = "".join(
            f"<tr><td style='padding:6px 12px;color:#57534e;'>{label}</td>"
            f"<td style='padding:6px 12px;text-align:right;font-weight:bold;'>{val}</td></tr>"
            for label, val in [
                ("Toplam gelir", f"£{c['total_revenue']:,.0f}"),
                ("Doluluk", f"%{c['occupancy_pct']}"),
                ("Ortalama gecelik fiyat (ADR)", f"£{c['adr']:,.0f}"),
                ("Alan geliri (Spaces)", f"£{c['spaces_revenue']:,.0f}"),
                ("VCC tahsilatı", f"£{c['vcc_collected']:,.0f}"),
                ("Kurtarılan OTA geliri", f"£{c.get('vcc_recovered', 0):,.0f}"),
                ("Kurumsal fatura tahsilatı", f"£{c['invoices_collected']:,.0f}"),
                ("Satılan gece", f"{c['nights_sold']}"),
            ])
        html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#292524;">
          <h2 style="color:#0f766e;">{data['property_name']} — {c['month']} Özeti</h2>
          <table style="width:100%;border-collapse:collapse;background:#fafaf9;border-radius:12px;">{rows}</table>
          <p style="font-size:12px;color:#78716c;margin-top:14px;">Detaylı PDF için yönetim panelini ziyaret edin. — MyHotelBox</p>
        </div>"""
        api_key = os.environ.get("RESEND_API_KEY", "")
        if not resend or not api_key or api_key.startswith("re_1234"):
            logger.info(f"[MOCK EMAIL] Owner summary to {to_email}: {c['month']}")
            return "mock"
        try:
            resend.api_key = api_key
            resend.Emails.send({
                "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
                "to": [to_email], "subject": subject, "html": html})
            return "sent"
        except Exception as e:
            logger.warning(f"owner summary email failed: {e}")
            return "failed"

    def _build_pdf(data: Dict) -> bytes:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as pdfcanvas
        c_data, d = data["current"], data["deltas"]
        buf = io.BytesIO()
        c = pdfcanvas.Canvas(buf, pagesize=A4)
        w, h = A4
        c.setFillColorRGB(0.06, 0.09, 0.16)
        c.rect(0, h - 42 * mm, w, 42 * mm, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(20 * mm, h - 22 * mm, data["property_name"])
        c.setFont("Helvetica", 13)
        c.drawString(20 * mm, h - 30 * mm, f"Aylik Sahip Ozeti - {c_data['month']}")
        c.setFont("Helvetica", 8)
        c.drawRightString(w - 15 * mm, h - 30 * mm, f"Olusturma: {date.today().isoformat()}")

        def delta_str(key):
            v = d.get(key, 0)
            return f"({'+' if v >= 0 else ''}{v:,.0f} onceki aya gore)"

        items = [
            ("TOPLAM GELIR", f"£{c_data['total_revenue']:,.0f}", delta_str("total_revenue")),
            ("DOLULUK", f"%{c_data['occupancy_pct']}", delta_str("occupancy_pct")),
            ("ADR", f"£{c_data['adr']:,.0f}", delta_str("adr")),
            ("ODA GELIRI", f"£{c_data['room_revenue']:,.0f}", ""),
            ("ALAN GELIRI (SPACES)", f"£{c_data['spaces_revenue']:,.0f}", delta_str("spaces_revenue")),
            ("VCC TAHSILATI", f"£{c_data['vcc_collected']:,.0f}", ""),
            ("KURTARILAN OTA GELIRI", f"£{c_data.get('vcc_recovered', 0):,.0f}", ""),
            ("KURUMSAL TAHSILAT", f"£{c_data['invoices_collected']:,.0f}", ""),
            ("SATILAN GECE", f"{c_data['nights_sold']}", delta_str("nights_sold")),
            ("MISAFIR", f"{c_data['guest_count']}", ""),
            ("IPTAL ORANI", f"%{c_data['cancellation_pct']}", ""),
            ("ONLINE PAY", f"%{c_data['online_share_pct']}", ""),
            ("KOMISYON MALIYETI", f"£{c_data['commission_costs']:,.0f}", ""),
        ]
        y = h - 60 * mm
        col_w, row_h = (w - 40 * mm) / 3, 30 * mm
        for i, (label, val, delta) in enumerate(items):
            x = 20 * mm + (i % 3) * col_w
            yy = y - (i // 3) * row_h
            c.setFillColorRGB(0.97, 0.96, 0.95)
            c.roundRect(x, yy - 22 * mm, col_w - 5 * mm, 24 * mm, 3 * mm, stroke=0, fill=1)
            c.setFillColorRGB(0.45, 0.4, 0.38)
            c.setFont("Helvetica", 7)
            c.drawString(x + 4 * mm, yy - 5 * mm, label)
            c.setFillColorRGB(0.1, 0.1, 0.12)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(x + 4 * mm, yy - 12 * mm, val)
            if delta:
                c.setFillColorRGB(0.35, 0.55, 0.45)
                c.setFont("Helvetica", 7)
                c.drawString(x + 4 * mm, yy - 18 * mm, delta)
        c.setFillColorRGB(0.6, 0.55, 0.52)
        c.setFont("Helvetica", 8)
        c.drawCentredString(w / 2, 15 * mm, "MyHotelBox - Otomatik uretilen yonetim raporu")
        c.showPage()
        c.save()
        return buf.getvalue()

    async def monthly_job() -> Dict:
        if date.today().day != 1:
            return {"ok": True, "skipped": "ayın 1'i değil"}
        month = _prev_month(date.today().strftime("%Y-%m"))
        data = await _full("all", month)
        c = data["current"]
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": "info",
            "title": f"Aylık Sahip Özeti Hazır — {month}",
            "message": f"Toplam gelir £{c['total_revenue']:,.0f}, doluluk %{c['occupancy_pct']}. PDF'i Owner Summary panelinden indirebilir veya sahibe gönderebilirsiniz.",
            "category": "reports", "target_user": "", "target_role": "manager",
            "link_to": "owner-summary", "priority": "normal",
            "read": False, "created_by": "Owner Summary Bot", "created_at": _now()})
        return {"ok": True, "month": month, "total_revenue": c["total_revenue"]}

    router.run_monthly_internal = monthly_job
    return router
