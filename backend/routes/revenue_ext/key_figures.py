"""
Key Figures Report (iter 422) — eviivo-style consolidated KPI report for a
date range: nights sold/unsold, occupancy, ADR, booking window, stay length,
online share, guests, revenue breakdown, commission costs, deposits.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, date, timedelta
from typing import Dict
import logging

from routes.integrations_pkg.ota_commission import DEFAULT_RATES

logger = logging.getLogger(__name__)

ONLINE_CHANNELS = {"booking_com", "expedia", "airbnb", "agoda", "trip_com", "direct"}
NON_ROOM_CATS = ["extra", "minibar", "late_checkout", "upsell", "resort_fee", "misc"]
NOSHOW_CATS = ["no_show", "no_show_fee"]
TAX_CATS = ["tourist_tax"]


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def create_key_figures_router(db, require_roles):
    router = APIRouter()

    @router.get("/key-figures/{property_id}")
    async def key_figures(property_id: str, start: str, end: str, basis: str = "staying",
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        try:
            d_start, d_end = _d(start), _d(end)
        except ValueError:
            raise HTTPException(status_code=400, detail="start/end YYYY-MM-DD olmalı")
        if d_end < d_start:
            raise HTTPException(status_code=400, detail="end >= start olmalı")
        days = (d_end - d_start).days + 1
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}

        active = {"status": {"$nin": ["cancelled", "no_show"]}}
        if basis == "booked":
            q = {**pq, **active,
                 "created_at": {"$gte": d_start.isoformat(), "$lte": d_end.isoformat() + "T99"}}
        else:
            q = {**pq, **active,
                 "check_in": {"$lte": d_end.isoformat()},
                 "check_out": {"$gt": d_start.isoformat()}}
        bookings = await db.bookings.find(
            q, {"_id": 0, "id": 1, "check_in": 1, "check_out": 1, "created_at": 1,
                "total_price": 1, "guest_count": 1, "channel": 1, "nights": 1}).to_list(20000)

        cancelled = await db.bookings.count_documents(
            {**pq, "status": {"$in": ["cancelled", "no_show"]},
             ("created_at" if basis == "booked" else "check_in"):
                 {"$gte": d_start.isoformat(), "$lte": d_end.isoformat() + ("T99" if basis == "booked" else "")}})

        rates_saved = {r["channel"]: float(r["rate"]) for r in
                       await db.ota_commission_rates.find({}, {"_id": 0}).to_list(100)}

        sold_nights, revenue, guests = 0, 0.0, 0
        windows, stays = [], []
        online_b, website_b, commission = 0, 0, 0.0
        booking_ids = []
        for b in bookings:
            booking_ids.append(b["id"])
            try:
                ci, co = _d(b.get("check_in", "")), _d(b.get("check_out", ""))
            except ValueError:
                continue
            full_nights = max((co - ci).days, 1)
            if basis == "staying":
                clip_start, clip_end = max(ci, d_start), min(co, d_end + timedelta(days=1))
                nights = max((clip_end - clip_start).days, 0)
                rev = float(b.get("total_price") or 0) * nights / full_nights
            else:
                nights = full_nights
                rev = float(b.get("total_price") or 0)
            sold_nights += nights
            revenue += rev
            guests += int(b.get("guest_count") or 1)
            stays.append(full_nights)
            try:
                created = _d(b.get("created_at", ""))
                windows.append(max((ci - created).days, 0))
            except ValueError:
                pass
            ch = (b.get("channel") or "direct").lower()
            if ch in ONLINE_CHANNELS:
                online_b += 1
            if ch == "direct":
                website_b += 1
            rate = rates_saved.get(ch, DEFAULT_RATES.get(ch, 0.0))
            commission += rev * rate

        rooms = await db.rooms.count_documents(pq)
        capacity = rooms * days
        unsold_nights = max(capacity - sold_nights, 0)
        total_b = len(bookings)

        # folio breakdown for these bookings
        fq = {"booking_id": {"$in": booking_ids}} if booking_ids else {"booking_id": "__none__"}
        pipeline = [
            {"$match": {**fq, "type": {"$in": ["charge", "adjustment"]}}},
            {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
        ]
        by_cat = {r["_id"]: float(r["total"] or 0) async for r in db.folio_items.aggregate(pipeline)}
        non_room = round(sum(by_cat.get(c, 0) for c in NON_ROOM_CATS), 2)
        noshow_fees = round(sum(by_cat.get(c, 0) for c in NOSHOW_CATS), 2)
        taxes = round(sum(by_cat.get(c, 0) for c in TAX_CATS), 2)

        deposits = await db.deposit_requests.find(
            {"status": "paid", "created_at": {"$gte": d_start.isoformat(),
                                              "$lte": d_end.isoformat() + "T99"}},
            {"_id": 0, "amount": 1}).to_list(5000)
        adv_deposits = round(sum(float(d.get("amount") or 0) for d in deposits), 2)

        total_revenue = round(revenue + non_room + noshow_fees + taxes, 2)
        return {
            "property_id": property_id, "start": start, "end": end,
            "basis": basis, "days": days, "rooms": rooms,
            "tiles": {
                "nights_sold": sold_nights,
                "nights_unsold": unsold_nights,
                "avg_occupancy_pct": round(sold_nights / capacity * 100, 1) if capacity else 0,
                "avg_price_per_night": round(revenue / sold_nights, 2) if sold_nights else 0,
                "avg_booking_window_days": round(sum(windows) / len(windows), 1) if windows else 0,
                "avg_stay_nights": round(sum(stays) / len(stays), 1) if stays else 0,
                "total_online_pct": round(online_b / total_b * 100, 1) if total_b else 0,
                "my_website_pct": round(website_b / total_b * 100, 1) if total_b else 0,
                "guest_count": guests,
                "total_revenue": total_revenue,
                "cancellation_pct": round(cancelled / (total_b + cancelled) * 100, 1) if (total_b + cancelled) else 0,
                "commission_costs": round(commission, 2),
            },
            "breakdown": {
                "room_revenue": round(revenue, 2),
                "non_room_revenue": non_room,
                "no_show_fees": noshow_fees,
                "taxes_collected": taxes,
                "total_revenue": total_revenue,
                "costs": {
                    "commissions": round(commission, 2),
                    "advanced_deposits": adv_deposits,
                },
            },
            "booking_count": total_b, "cancelled_count": cancelled,
        }

    return router
