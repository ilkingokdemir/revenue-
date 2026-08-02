"""24-Hour Pickup Pulse — son 24 saatte satılan odalar, pickup %, hedefler ve haftalık rapor."""
import asyncio
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_perm

_PROJ = {"_id": 0, "booking_ref": 1, "guest_name": 1, "check_in": 1, "check_out": 1,
         "rooms": 1, "nights": 1, "total_price": 1, "currency": 1, "source": 1,
         "created_at": 1, "property_id": 1, "status": 1}


class TargetIn(BaseModel):
    property_id: str = "all"
    month: str = ""
    target_rooms: int


async def _week_stats(db, property_id: str = ""):
    now = datetime.now(timezone.utc)
    cut7 = (now - timedelta(days=7)).isoformat()
    q = {"status": {"$nin": ["cancelled"]}, "created_at": {"$gte": cut7, "$lte": now.isoformat()}}
    if property_id and property_id != "all":
        q["property_id"] = property_id
    rows = await db.bookings.find(q, {"_id": 0, "rooms": 1, "nights": 1, "total_price": 1,
                                      "created_at": 1, "source": 1, "property_id": 1}).to_list(5000)
    by_day, by_prop, by_source = defaultdict(int), defaultdict(int), defaultdict(int)
    rooms = room_nights = 0
    revenue = 0.0
    for b in rows:
        r = int(b.get("rooms") or 1)
        rooms += r
        room_nights += r * int(b.get("nights") or 1)
        revenue += float(b.get("total_price") or 0)
        by_day[(b.get("created_at") or "")[:10]] += r
        by_prop[b.get("property_id") or "?"] += r
        by_source[b.get("source") or "Direct"] += r
    days = [(now - timedelta(days=i)).date().isoformat() for i in range(6, -1, -1)]
    return {
        "week_start": (now - timedelta(days=7)).date().isoformat(),
        "week_end": now.date().isoformat(),
        "rooms": rooms, "room_nights": room_nights, "revenue": round(revenue, 2),
        "adr": round(revenue / room_nights, 2) if room_nights else 0,
        "by_day": [{"date": d, "rooms": by_day.get(d, 0)} for d in days],
        "by_property": sorted(({"property_id": k, "rooms": v} for k, v in by_prop.items()),
                              key=lambda x: -x["rooms"]),
        "by_source": sorted(({"source": k, "rooms": v} for k, v in by_source.items()),
                            key=lambda x: -x["rooms"])[:6],
    }


async def run_weekly_pickup_report(db, property_id: str = "") -> dict:
    """Haftalık pickup özetini üretir, kaydeder ve admin/manager'lara e-postalar (mock-safe)."""
    stats = await _week_stats(db, property_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    report = {"id": str(uuid.uuid4()), "property_id": property_id or "all",
              **stats, "created_at": now_iso}
    await db.pickup_weekly_reports.insert_one({**report})
    admins = await db.users.find({"role": {"$in": ["admin", "manager"]}},
                                 {"_id": 0, "email": 1}).to_list(20)
    emails = [a["email"] for a in admins if a.get("email")]
    day_rows = "".join(
        f"<tr><td style='padding:4px 12px'>{d['date']}</td><td style='padding:4px 12px;text-align:right'><b>{d['rooms']}</b></td></tr>"
        for d in stats["by_day"])
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px">
      <h2 style="color:#1c1917">Haftalık Pickup Raporu</h2>
      <p style="color:#57534e">{stats['week_start']} → {stats['week_end']}</p>
      <p><b>{stats['rooms']}</b> oda · <b>{stats['room_nights']}</b> oda-gecesi ·
         <b>£{stats['revenue']:,.0f}</b> gelir · ADR £{stats['adr']}</p>
      <table style="border-collapse:collapse;font-size:13px">{day_rows}</table>
    </div>"""
    api_key = os.environ.get("RESEND_API_KEY", "")
    mocked = not api_key or api_key == "re_123456789"
    sent = 0
    if not mocked and emails:
        resend.api_key = api_key
        for e in emails:
            try:
                await asyncio.to_thread(resend.Emails.send, {
                    "from": os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
                    "to": [e], "subject": f"Haftalık Pickup Raporu — {stats['rooms']} oda",
                    "html": html})
                sent += 1
            except Exception:
                pass
    await db.pickup_weekly_reports.update_one(
        {"id": report["id"]},
        {"$set": {"emailed_to": emails, "email_mocked": mocked or sent == 0, "emails_sent": sent}})
    return {"ok": True, "rooms": stats["rooms"], "revenue": stats["revenue"],
            "recipients": emails, "mocked": mocked or sent == 0}


def create_pickup_pulse_router(db):
    router = APIRouter()

    @router.get("/pulse/pickup-24h")
    async def pickup_24h(property_id: str = "",
                         current_user: dict = Depends(require_perm("view_bookings", "view_dashboard", mode="any"))):
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        cut24 = (now - timedelta(hours=24)).isoformat()
        cut48 = (now - timedelta(hours=48)).isoformat()
        q = {"status": {"$nin": ["cancelled"]}}
        rooms_q = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
            rooms_q["property_id"] = property_id

        cur = await db.bookings.find({**q, "created_at": {"$gte": cut24, "$lte": now_iso}}, _PROJ)\
            .sort("created_at", -1).to_list(1000)
        prev = await db.bookings.find({**q, "created_at": {"$gte": cut48, "$lt": cut24}},
                                      {"_id": 0, "rooms": 1}).to_list(1000)
        total_rooms = await db.rooms.count_documents(rooms_q)

        cut14 = (now - timedelta(days=14)).isoformat()
        daily = {}
        async for r in db.bookings.aggregate([
                {"$match": {**q, "created_at": {"$gte": cut14, "$lte": now_iso}}},
                {"$group": {"_id": {"$substr": ["$created_at", 0, 10]},
                            "rooms": {"$sum": {"$ifNull": ["$rooms", 1]}}}}]):
            daily[r["_id"]] = int(r["rooms"])
        daily_trend = []
        for i in range(13, -1, -1):
            d = (now - timedelta(days=i)).date().isoformat()
            daily_trend.append({"date": d, "rooms": daily.get(d, 0)})

        rooms_sold = sum(int(b.get("rooms") or 1) for b in cur)
        prev_rooms_sold = sum(int(b.get("rooms") or 1) for b in prev)
        room_nights = sum(int(b.get("rooms") or 1) * int(b.get("nights") or 1) for b in cur)
        revenue = sum(float(b.get("total_price") or 0) for b in cur)
        pickup_pct = round(room_nights * 100 / (total_rooms * 30), 1) if total_rooms else 0
        strong_day = pickup_pct >= 5 and rooms_sold > prev_rooms_sold

        by_source = defaultdict(int)
        by_stay_date = defaultdict(int)
        for b in cur:
            by_source[b.get("source") or "Direct"] += int(b.get("rooms") or 1)
            if b.get("check_in"):
                by_stay_date[b["check_in"]] += int(b.get("rooms") or 1)

        # Aylık hedef + MTD ilerleme
        month = now.strftime("%Y-%m")
        tgt = await db.pickup_targets.find_one(
            {"property_id": property_id or "all", "month": month}, {"_id": 0})
        mtd_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        mtd_rooms = 0
        async for r in db.bookings.aggregate([
                {"$match": {**q, "created_at": {"$gte": mtd_start, "$lte": now_iso}}},
                {"$group": {"_id": None, "rooms": {"$sum": {"$ifNull": ["$rooms", 1]}}}}]):
            mtd_rooms = int(r.get("rooms") or 0)
        target_rooms = int((tgt or {}).get("target_rooms") or 0)
        import calendar
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        forecast_rooms = round(mtd_rooms / max(now.day, 1) * days_in_month)
        target = {"month": month, "target_rooms": target_rooms, "mtd_rooms": mtd_rooms,
                  "progress_pct": round(mtd_rooms * 100 / target_rooms, 1) if target_rooms else 0,
                  "forecast_rooms": forecast_rooms,
                  "on_track": forecast_rooms >= target_rooms if target_rooms else None}

        return {
            "rooms_sold_24h": rooms_sold,
            "prev_rooms_sold_24h": prev_rooms_sold,
            "trend": rooms_sold - prev_rooms_sold,
            "pickup_pct": pickup_pct,
            "strong_day": strong_day,
            "daily_trend": daily_trend,
            "target": target,
            "total_rooms": total_rooms,
            "room_nights_24h": room_nights,
            "revenue_24h": round(revenue, 2),
            "adr_24h": round(revenue / room_nights, 2) if room_nights else 0,
            "by_source": sorted(({"source": k, "rooms": v} for k, v in by_source.items()),
                                key=lambda x: -x["rooms"])[:6],
            "by_stay_date": sorted(({"date": k, "rooms": v} for k, v in by_stay_date.items()),
                                   key=lambda x: x["date"])[:14],
            "recent_bookings": cur[:15],
            "as_of": now.isoformat(),
        }

    @router.put("/pulse/pickup-target")
    async def set_target(body: TargetIn,
                         current_user: dict = Depends(require_perm("edit_bookings"))):
        if body.target_rooms < 0:
            raise HTTPException(400, "target_rooms >= 0 olmalı")
        month = body.month or datetime.now(timezone.utc).strftime("%Y-%m")
        await db.pickup_targets.update_one(
            {"property_id": body.property_id or "all", "month": month},
            {"$set": {"property_id": body.property_id or "all", "month": month,
                      "target_rooms": int(body.target_rooms),
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": current_user.get("email", "")}},
            upsert=True)
        return {"status": "saved", "month": month, "target_rooms": int(body.target_rooms)}

    @router.get("/pulse/weekly-report")
    async def weekly_report(property_id: str = "",
                            current_user: dict = Depends(require_perm("view_bookings", "view_dashboard", mode="any"))):
        stats = await _week_stats(db, property_id)
        last = await db.pickup_weekly_reports.find_one(
            {"property_id": property_id or "all"}, {"_id": 0, "created_at": 1, "emails_sent": 1, "email_mocked": 1},
            sort=[("created_at", -1)])
        return {**stats, "last_sent": last}

    @router.get("/pulse/weekly-reports")
    async def weekly_reports_archive(property_id: str = "", limit: int = 12,
                                     current_user: dict = Depends(require_perm("view_bookings", "view_dashboard", mode="any"))):
        q = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        return await db.pickup_weekly_reports.find(
            q, {"_id": 0, "id": 1, "property_id": 1, "week_start": 1, "week_end": 1,
                "rooms": 1, "room_nights": 1, "revenue": 1, "adr": 1,
                "emailed_to": 1, "emails_sent": 1, "email_mocked": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(min(int(limit), 50))

    @router.post("/pulse/weekly-report/send")
    async def send_weekly_report(property_id: str = "",
                                 current_user: dict = Depends(require_perm("edit_bookings"))):
        return await run_weekly_pickup_report(db, property_id)

    return router
