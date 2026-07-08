"""
OTA Commission Analytics (iter 374) — Net Revenue Dashboard
============================================================
For every OTA booking, compute:
  - gross_revenue = total_price
  - commission    = gross_revenue × commission_rate(channel)
  - net_revenue   = gross_revenue - commission

Commission rates (industry standard, can be overridden per property/channel):
  Booking.com  15%
  Expedia      18%  (15-25% depending on program)
  Airbnb        3%  (host-only fee; typically low)
  Agoda        17%  (15-18%)
  Trip.com     15%
  Direct        0%  (own website, phone, walk-in)

Endpoints
---------
  GET  /api/ota-commission/summary        — property/date-range aggregates
  GET  /api/ota-commission/rates          — current rates (with property override)
  PUT  /api/ota-commission/rates          — admin can override rate per channel
  GET  /api/ota-commission/leaderboard    — top-earning channels + gross vs net
"""
from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


# Default industry rates (can be overridden in `ota_commission_rates`)
DEFAULT_RATES = {
    "booking_com": 0.15,
    "expedia":     0.18,
    "airbnb":      0.03,
    "agoda":       0.17,
    "trip_com":    0.15,
    "direct":      0.00,
}

# Human-friendly labels for UI
CHANNEL_LABELS = {
    "booking_com": "Booking.com",
    "expedia":     "Expedia",
    "airbnb":      "Airbnb",
    "agoda":       "Agoda",
    "trip_com":    "Trip.com",
    "direct":      "Direct (own site / walk-in)",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_channel(bk: dict) -> str:
    """Derive canonical channel key from a booking doc."""
    src = (bk.get("source") or "").lower()
    if src.startswith("ota:"):
        return src.replace("ota:", "")
    ch = (bk.get("channel") or bk.get("channel_key") or "").lower()
    if ":" in ch:
        ch = ch.split(":", 1)[0]
    return ch or "direct"


async def _get_rate(db, channel: str, property_id: Optional[str] = None) -> float:
    if property_id:
        row = await db.ota_commission_rates.find_one(
            {"channel": channel, "property_id": property_id}, {"_id": 0, "rate": 1}
        )
        if row:
            return float(row["rate"])
    row = await db.ota_commission_rates.find_one(
        {"channel": channel, "property_id": None}, {"_id": 0, "rate": 1}
    )
    if row:
        return float(row["rate"])
    return DEFAULT_RATES.get(channel, 0.0)


class RateOverride(BaseModel):
    channel:     str
    rate:        float
    property_id: Optional[str] = None


def create_ota_commission_router(db, require_roles):
    router = APIRouter(prefix="/ota-commission", tags=["ota-commission"])

    @router.get("/rates")
    async def get_rates(property_id: Optional[str] = None,
                          _: dict = Depends(require_roles("admin", "manager"))):
        out = []
        for ch, default in DEFAULT_RATES.items():
            rate = await _get_rate(db, ch, property_id)
            out.append({
                "channel":  ch,
                "label":    CHANNEL_LABELS.get(ch, ch),
                "rate":     rate,
                "default":  default,
                "overridden": rate != default,
            })
        return {"property_id": property_id, "items": out}

    @router.put("/rates")
    async def set_rate(body: RateOverride,
                         _: dict = Depends(require_roles("admin", "manager"))):
        if body.channel not in DEFAULT_RATES:
            raise HTTPException(400, f"Bilinmeyen kanal: {body.channel}")
        if not (0 <= body.rate <= 0.5):
            raise HTTPException(400, "rate 0..0.5 aralığında olmalı")
        q = {"channel": body.channel, "property_id": body.property_id}
        await db.ota_commission_rates.update_one(
            q, {"$set": {**q, "rate": body.rate, "updated_at": _now()}},
            upsert=True,
        )
        return {"ok": True, **q, "rate": body.rate}

    async def _summary_data(start: str, end: str, property_id: Optional[str]) -> dict:
        q: dict = {
            "check_in": {"$gte": start, "$lte": end},
            "status": {"$ne": "cancelled"},
        }
        if property_id:
            q["property_id"] = property_id
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(20000)

        rates: dict = {}
        for ch in list(DEFAULT_RATES.keys()):
            rates[ch] = await _get_rate(db, ch, property_id)

        agg: dict = {}
        for b in bookings:
            ch = _detect_channel(b)
            gross = float(b.get("total_price") or 0)
            rate = rates.get(ch, 0.0)
            commission = round(gross * rate, 2)
            net = round(gross - commission, 2)
            row = agg.setdefault(ch, {
                "channel":    ch,
                "label":      CHANNEL_LABELS.get(ch, ch.title()),
                "rate":       rate,
                "bookings":   0,
                "gross":      0.0,
                "commission": 0.0,
                "net":        0.0,
            })
            row["bookings"]   += 1
            row["gross"]      += gross
            row["commission"] += commission
            row["net"]        += net

        rows = []
        for r in agg.values():
            r["gross"]      = round(r["gross"], 2)
            r["commission"] = round(r["commission"], 2)
            r["net"]        = round(r["net"], 2)
            r["adr"]        = round(r["gross"] / r["bookings"], 2) if r["bookings"] else 0
            rows.append(r)
        rows.sort(key=lambda x: x["gross"], reverse=True)

        totals = {
            "bookings":   sum(r["bookings"] for r in rows),
            "gross":      round(sum(r["gross"] for r in rows), 2),
            "commission": round(sum(r["commission"] for r in rows), 2),
            "net":        round(sum(r["net"] for r in rows), 2),
        }
        totals["blended_commission_pct"] = round(totals["commission"] / totals["gross"] * 100, 2) if totals["gross"] else 0
        return {
            "range":  {"start": start, "end": end},
            "property_id": property_id,
            "rows":   rows,
            "totals": totals,
        }

    @router.get("/summary")
    async def summary(start: Optional[str] = None, end: Optional[str] = None,
                        property_id: Optional[str] = None,
                        _: dict = Depends(require_roles("admin", "manager"))):
        end_d = date.fromisoformat(end) if end else date.today()
        start_d = date.fromisoformat(start) if start else (end_d - timedelta(days=30))
        return await _summary_data(start_d.isoformat(), end_d.isoformat(), property_id)

    @router.get("/leaderboard")
    async def leaderboard(days: int = 90, property_id: Optional[str] = None,
                             _: dict = Depends(require_roles("admin", "manager"))):
        """Channels ranked by NET revenue over last N days."""
        end_d = date.today()
        start_d = end_d - timedelta(days=max(1, min(days, 365)))
        s = await _summary_data(start_d.isoformat(), end_d.isoformat(), property_id)
        ranked = sorted(s["rows"], key=lambda x: x["net"], reverse=True)
        for i, r in enumerate(ranked, 1):
            r["rank"] = i
        return {"days": days, "leaderboard": ranked, "totals": s["totals"]}

    return router
