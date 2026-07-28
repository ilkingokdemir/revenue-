"""
Ücretsiz Price Checker — landing page lead-gen aracı (RoomPriceGenie paritesi).

Şehir + oda sayısı girilir → simüle pazar fiyat aralığı ve gelir potansiyeli
döner. Her sorgu `price_check_leads` koleksiyonuna lead olarak kaydedilir.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
import hashlib
import uuid


class PriceCheckReq(BaseModel):
    city: str = Field(..., min_length=2, max_length=80)
    hotel_name: Optional[str] = None
    room_count: Optional[int] = Field(None, ge=1, le=2000)
    email: Optional[str] = None


def _h(seed: str, lo: float, hi: float) -> float:
    n = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return lo + n * (hi - lo)


def create_price_checker_router(db):
    router = APIRouter(tags=["price-checker"])

    @router.post("/public/price-check")
    async def price_check(req: PriceCheckReq):
        city = req.city.strip().lower()
        if not city:
            raise HTTPException(400, "city required")
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
        await db.price_check_leads.insert_one({
            "id": str(uuid.uuid4()),
            "city": req.city.strip(),
            "hotel_name": (req.hotel_name or "").strip() or None,
            "room_count": req.room_count,
            "email": (req.email or "").strip() or None,
            "result": dict(result),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return result

    return router
