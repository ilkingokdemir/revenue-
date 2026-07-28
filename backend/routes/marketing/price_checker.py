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

        await db.price_check_leads.insert_one({
            "id": str(uuid.uuid4()),
            "city": req.city.strip(),
            "hotel_name": (req.hotel_name or "").strip() or None,
            "room_count": req.room_count,
            "email": email or None,
            "ip": ip,
            "crm_lead": lead_created,
            "result": dict(result),
            "created_at": now_iso,
        })
        return {**result, "lead_created": lead_created}

    return router
