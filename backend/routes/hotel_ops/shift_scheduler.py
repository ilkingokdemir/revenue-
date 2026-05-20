"""
Shift Scheduler — Weekly Gantt with staff roles, daily rates, bulk publish.
Reception Report — Track receptionist activity.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

ROLE_RATES = {"receptionist": 50, "housekeeper": 80, "maintenance": 100}
SHIFT_PRESETS = {
    "morning": {"start": "07:00", "end": "15:00", "color": "#22c55e"},
    "afternoon": {"start": "12:00", "end": "20:00", "color": "#06b6d4"},
    "evening": {"start": "15:00", "end": "23:00", "color": "#8b5cf6"},
    "night": {"start": "23:00", "end": "07:00", "color": "#ef4444"},
    "full": {"start": "09:00", "end": "17:00", "color": "#f59e0b"},
}


def create_shift_scheduler_router(db, require_roles):
    router = APIRouter()

    @router.get("/operations/shifts/{property_id}")
    async def get_shifts(property_id: str, week_start: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if week_start:
            ws = datetime.strptime(week_start, "%Y-%m-%d")
        else:
            ws = now - timedelta(days=now.weekday())
        we = ws + timedelta(days=6)
        ws_str = ws.strftime("%Y-%m-%d")
        we_str = we.strftime("%Y-%m-%d")

        staff = await db.users.find(
            {"role": {"$in": ["receptionist", "housekeeper", "maintenance"]}},
            {"_id": 0}
        ).to_list(50)

        shifts = await db.shifts.find({"week_start": ws_str}, {"_id": 0}).to_list(500)
        shift_map = {}
        for s in shifts:
            shift_map[f"{s.get('staff_id', '')}_{s.get('date', '')}"] = s

        days = []
        for i in range(7):
            d = ws + timedelta(days=i)
            days.append({"date": d.strftime("%Y-%m-%d"), "dow": d.strftime("%a"), "day": d.day, "month": d.strftime("%b")})

        staff_schedule = []
        for s in staff:
            sid = s.get("id", s.get("email", ""))
            daily = []
            for day in days:
                shift = shift_map.get(f"{sid}_{day['date']}")
                if shift:
                    daily.append({"date": day["date"], "shift_start": shift.get("shift_start", ""), "shift_end": shift.get("shift_end", ""), "status": shift.get("status", "planned"), "color": shift.get("color", "#22c55e"), "id": shift.get("id", "")})
                else:
                    daily.append({"date": day["date"], "shift_start": "", "shift_end": "", "status": "none"})
            staff_schedule.append({"id": sid, "name": s.get("name", ""), "role": s.get("role", ""), "daily_rate": ROLE_RATES.get(s.get("role", ""), 50), "shifts": daily})

        return {"week_start": ws_str, "week_end": we_str, "days": days, "staff": staff_schedule, "total_staff": len(staff_schedule)}

    @router.post("/operations/shifts/{property_id}/assign")
    async def assign_shift(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        staff_id = data.get("staff_id", "")
        date = data.get("date", "")
        preset = data.get("preset", "")
        if preset and preset in SHIFT_PRESETS:
            p = SHIFT_PRESETS[preset]
            shift_start, shift_end, color = p["start"], p["end"], p["color"]
        else:
            shift_start = data.get("shift_start", "09:00")
            shift_end = data.get("shift_end", "17:00")
            color = data.get("color", "#22c55e")

        d = datetime.strptime(date, "%Y-%m-%d")
        ws_str = (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")

        shift = {"id": str(uuid.uuid4()), "property_id": property_id, "staff_id": staff_id, "date": date, "week_start": ws_str, "shift_start": shift_start, "shift_end": shift_end, "color": color, "status": "planned", "created_at": datetime.now(timezone.utc).isoformat(), "created_by": current_user.get("name", "")}
        await db.shifts.update_one({"staff_id": staff_id, "date": date, "week_start": ws_str}, {"$set": shift}, upsert=True)
        return shift

    @router.post("/operations/shifts/{property_id}/bulk-publish")
    async def bulk_publish(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        action = data.get("action", "publish")
        new_status = {"publish": "published", "approve": "approved", "complete": "completed"}.get(action, "published")
        result = await db.shifts.update_many({"week_start": week_start, "status": {"$in": ["planned", "draft", "published"]}}, {"$set": {"status": new_status}})
        return {"updated": result.modified_count, "status": new_status}

    @router.delete("/operations/shifts/{property_id}/clear-week")
    async def clear_week(property_id: str, week_start: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        result = await db.shifts.delete_many({"week_start": week_start})
        return {"deleted": result.deleted_count}

    @router.get("/operations/reception-report/{property_id}")
    async def reception_report(property_id: str, start: str = "", end: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        if not start:
            start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        if not end:
            end = now.strftime("%Y-%m-%d")

        bk_query = {}
        if property_id != "all":
            bk_query["property_id"] = property_id

        bookings_created = await db.bookings.find({**bk_query, "created_at": {"$gte": start}}, {"_id": 0, "id": 1, "guest_name": 1, "created_at": 1, "source": 1}).to_list(500)
        checkins = await db.bookings.find({**bk_query, "check_in": {"$gte": start, "$lte": end}, "status": {"$in": ["checked_in", "checked_out"]}}, {"_id": 0, "id": 1, "guest_name": 1, "check_in": 1}).to_list(500)
        checkouts = await db.bookings.find({**bk_query, "check_out": {"$gte": start, "$lte": end}, "status": "checked_out"}, {"_id": 0, "id": 1, "guest_name": 1, "check_out": 1}).to_list(500)
        cancellations = await db.bookings.find({**bk_query, "status": "cancelled"}, {"_id": 0, "id": 1, "guest_name": 1}).to_list(500)
        routines = await db.routine_runs.find({"started_at": {"$gte": start}}, {"_id": 0}).to_list(100)

        return {
            "period": {"start": start, "end": end},
            "kpis": {"bookings_created": len(bookings_created), "check_ins": len(checkins), "check_outs": len(checkouts), "cancellations": len(cancellations), "routine_runs": len(routines)},
            "bookings_created": [{"guest": b.get("guest_name", ""), "created_at": b.get("created_at", ""), "source": b.get("source", "")} for b in bookings_created[:20]],
            "check_ins": [{"guest": b.get("guest_name", ""), "date": b.get("check_in", "")} for b in checkins[:20]],
            "check_outs": [{"guest": b.get("guest_name", ""), "date": b.get("check_out", "")} for b in checkouts[:20]],
            "cancellations": [{"guest": b.get("guest_name", "")} for b in cancellations[:20]],
            "routine_runs": [{"user": r.get("started_by", ""), "date": r.get("started_at", ""), "status": r.get("status", "")} for r in routines[:20]],
        }

    return router
