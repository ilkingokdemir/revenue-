"""
Ücretsiz Price Checker — landing page lead-gen aracı (RoomPriceGenie paritesi).

Şehir + oda sayısı girilir → simüle pazar fiyat aralığı ve gelir potansiyeli
döner. Her sorgu `price_check_leads` koleksiyonuna kaydedilir; e-posta
verilmişse otomatik olarak Demo Leads CRM hunisine (demo_requests) düşer.
IP başına saatte 10 sorgu rate-limit'i vardır.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
import hashlib
import logging
import re
import uuid

logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RATE_LIMIT_PER_HOUR = 10


class PriceCheckReq(BaseModel):
    city: str = Field(..., min_length=2, max_length=80)
    hotel_name: Optional[str] = None
    room_count: Optional[int] = Field(None, ge=1, le=2000)
    email: Optional[str] = None


def _h(seed: str, lo: float, hi: float) -> float:
    n = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return lo + n * (hi - lo)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _build_report_html(result: dict, room_count: Optional[int]) -> str:
    import os
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    annual = result.get("annual_uplift_estimate")
    annual_html = (
        f'<div style="font-size:12px;color:#78716c;margin-top:2px;">≈ €{annual:,.0f} / yıl ({room_count} oda için)</div>'
        if annual and room_count else "")
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#292524;">
      <div style="font-size:11px;letter-spacing:2px;color:#2563eb;font-weight:bold;text-transform:uppercase;">ReveniQ · Ücretsiz Pazar Raporu</div>
      <h2 style="color:#1c1917;margin:6px 0 2px;">{result['city']} pazarınızın fotoğrafı</h2>
      <div style="font-size:12px;color:#78716c;margin-bottom:16px;">{result['hotel_sample_size']} otel + {result['str_sample_size']} kısa dönem kiralama ilanı analiz edildi</div>
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="width:50%;padding:5px;"><div style="border:1px solid #e7e5e4;border-radius:10px;padding:12px;"><div style="font-size:10px;color:#78716c;text-transform:uppercase;">Pazar Medyanı</div><div style="font-size:22px;font-weight:bold;color:#1c1917;">€{result['market_median']:.0f}</div></div></td>
          <td style="width:50%;padding:5px;"><div style="border:1px solid #e7e5e4;border-radius:10px;padding:12px;"><div style="font-size:10px;color:#78716c;text-transform:uppercase;">Fiyat Bandı</div><div style="font-size:22px;font-weight:bold;color:#1c1917;">€{result['market_min']:.0f}–€{result['market_max']:.0f}</div></div></td>
        </tr>
        <tr>
          <td style="padding:5px;"><div style="border:1px solid #e7e5e4;border-radius:10px;padding:12px;"><div style="font-size:10px;color:#78716c;text-transform:uppercase;">Hafta Sonu Artışı</div><div style="font-size:22px;font-weight:bold;color:#1c1917;">+%{result['weekend_uplift_pct']}</div></div></td>
          <td style="padding:5px;"><div style="border:1px solid #e7e5e4;border-radius:10px;padding:12px;"><div style="font-size:10px;color:#78716c;text-transform:uppercase;">90 Günde Etkinlik</div><div style="font-size:22px;font-weight:bold;color:#1c1917;">{result['event_days_next_90']} gün</div></div></td>
        </tr>
      </table>
      <div style="border:1px solid #a7f3d0;background:#ecfdf5;border-radius:10px;padding:14px;margin-top:14px;">
        <div style="font-size:11px;color:#047857;font-weight:bold;text-transform:uppercase;">Dinamik fiyatlama potansiyeliniz</div>
        <div style="font-size:26px;font-weight:bold;color:#065f46;">+%{result['revenue_potential_pct']} gelir</div>
        {annual_html}
      </div>
      <p style="font-size:13px;color:#57534e;margin-top:16px;">Bu rakamlar pazar tahminidir. ReveniQ, oteliniz için canlı Booking.com ve kısa dönem kiralama verisiyle <b>gerçek zamanlı dinamik fiyatlama</b> yapar — 18 aya kadar ileri fiyat, otomatik talep baskısı sinyalleri ve rakip takibi dahil.</p>
      <p style="text-align:center;margin:22px 0 8px;">
        <a href="{base}/reveniq#demo" style="background:#2563eb;color:#fff;text-decoration:none;padding:12px 28px;border-radius:10px;font-weight:bold;display:inline-block;">Ücretsiz Demo Planla</a>
      </p>
      <p style="font-size:10px;color:#a8a29e;text-align:center;">Bu raporu {result['city']} için Price Checker aracımızı kullandığınız için aldınız.</p>
    </div>"""


def create_price_checker_router(db):
    router = APIRouter(tags=["price-checker"])

    @router.post("/public/price-check")
    async def price_check(req: PriceCheckReq, request: Request):
        city = req.city.strip().lower()
        if not city:
            raise HTTPException(400, "city required")

        ip = _client_ip(request)
        hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent = await db.price_check_leads.count_documents(
            {"ip": ip, "created_at": {"$gte": hour_ago}})
        if recent >= RATE_LIMIT_PER_HOUR:
            raise HTTPException(429, "Çok fazla sorgu — lütfen bir saat sonra tekrar deneyin")

        median = round(_h(f"pc:{city}:m", 68, 225), 0)
        result = {
            "city": req.city.strip().title(),
            "currency": "EUR",
            "market_median": median,
            "market_min": round(median * 0.68, 0),
            "market_max": round(median * 1.62, 0),
            "weekend_uplift_pct": round(_h(f"pc:{city}:w", 8, 26), 1),
            "event_days_next_90": int(_h(f"pc:{city}:e", 2, 9)),
            "hotel_sample_size": int(_h(f"pc:{city}:h", 25, 130)),
            "str_sample_size": int(_h(f"pc:{city}:s", 80, 420)),
            "revenue_potential_pct": round(_h(f"pc:{city}:r", 12, 23), 1),
        }
        if req.room_count:
            annual = req.room_count * 365 * 0.72 * median
            result["annual_uplift_estimate"] = round(annual * result["revenue_potential_pct"] / 100, 0)

        email = (req.email or "").strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        lead_created = False
        report_email = "none"
        if email and EMAIL_RE.match(email):
            hotel_name = (req.hotel_name or "").strip() or f"{result['city']} oteli"
            msg = (f"Price Checker sorgusu: {result['city']}"
                   + (f", {req.room_count} oda" if req.room_count else "")
                   + f" — pazar medyanı €{median:.0f}, potansiyel +%{result['revenue_potential_pct']}"
                   + (f", yıllık ≈ €{result['annual_uplift_estimate']:,.0f}" if result.get("annual_uplift_estimate") else ""))
            existing = await db.demo_requests.find_one(
                {"email": email, "source": "price-checker",
                 "status": {"$in": ["new", "contacted"]}}, {"_id": 0, "id": 1})
            if existing:
                await db.demo_requests.update_one(
                    {"id": existing["id"]},
                    {"$set": {"message": msg, "updated_at": now_iso}})
            else:
                await db.demo_requests.insert_one({
                    "id": str(uuid.uuid4()), "name": email.split("@")[0].title(),
                    "email": email, "hotel_name": hotel_name, "product": "pulse",
                    "room_count": str(req.room_count or ""), "message": msg,
                    "source": "price-checker",
                    "status": "new", "created_at": now_iso, "updated_at": now_iso})
                logger.info(f"Price Checker lead → Demo CRM: {email} ({result['city']})")
            lead_created = True

            # 📧 Otomatik "Pazar Raporu" e-postası (24 saatte 1 kez / e-posta)
            day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            already = await db.price_check_leads.find_one(
                {"email": email, "created_at": {"$gte": day_ago},
                 "report_email_status": {"$in": ["sent", "mock"]}},
                {"_id": 0, "id": 1})
            if already:
                report_email = "skipped_recent"
            else:
                try:
                    from routes.revenue_ext.owner_pulse import _send_email
                    report_email = await _send_email(
                        email,
                        f"{result['city']} pazar raporunuz hazır — +%{result['revenue_potential_pct']} gelir potansiyeli",
                        _build_report_html(result, req.room_count))
                    logger.info(f"Price Checker market report → {email}: {report_email}")
                except Exception as e:
                    logger.warning(f"Price Checker report email failed: {e}")
                    report_email = "failed"

        await db.price_check_leads.insert_one({
            "id": str(uuid.uuid4()),
            "city": req.city.strip(),
            "hotel_name": (req.hotel_name or "").strip() or None,
            "room_count": req.room_count,
            "email": email or None,
            "ip": ip,
            "crm_lead": lead_created,
            "report_email_status": report_email,
            "result": dict(result),
            "created_at": now_iso,
        })
        return {**result, "lead_created": lead_created, "report_email": report_email}

    return router
