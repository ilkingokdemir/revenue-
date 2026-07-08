"""
Predictive Housekeeping — 7-day workload forecast from bookings
(departures / stayovers / arrivals) with auto task generation and
staffing recommendations.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

MINUTES = {"checkout_clean": 45, "stayover_refresh": 20, "arrival_inspection": 10}
SHIFT_PRODUCTIVE_MIN = 360  # 6h productive per housekeeper/day


def create_predictive_hk_router(db, require_roles):
    router = APIRouter()

    async def _forecast_days(property_id: str, days: int):
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=days)
        pq = {} if property_id == "all" else {"property_id": property_id}
        bookings = await db.bookings.find({
            **pq,
            "status": {"$nin": ["cancelled", "no_show"]},
            "check_in": {"$lt": end.isoformat()},
            "check_out": {"$gte": today.isoformat()},
        }, {"_id": 0, "id": 1, "check_in": 1, "check_out": 1, "room_id": 1,
            "room_number": 1, "guest_name": 1, "property_id": 1}).to_list(5000)

        housekeepers = await db.users.find(
            {"role": "housekeeper"}, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(50)

        day_list = []
        for i in range(days):
            d = today + timedelta(days=i)
            ds = d.isoformat()
            departures, arrivals, stayovers = [], [], []
            for b in bookings:
                ci, co = b.get("check_in", ""), b.get("check_out", "")
                room = b.get("room_number") or b.get("room_id") or ""
                item = {"booking_id": b["id"], "room": room, "guest": b.get("guest_name", "")}
                if co == ds:
                    departures.append(item)
                elif ci == ds:
                    arrivals.append(item)
                elif ci < ds < co:
                    stayovers.append(item)
            workload = (len(departures) * MINUTES["checkout_clean"]
                        + len(stayovers) * MINUTES["stayover_refresh"]
                        + len(arrivals) * MINUTES["arrival_inspection"])
            staff_needed = max(1, -(-workload // SHIFT_PRODUCTIVE_MIN)) if workload else 0
            existing = await db.housekeeping_tasks.count_documents({
                **({} if property_id == "all" else {"property_id": property_id}),
                "due_date": ds, "auto_generated": True})
            day_list.append({
                "date": ds,
                "departures": departures, "arrivals": arrivals, "stayovers": stayovers,
                "departure_count": len(departures), "arrival_count": len(arrivals),
                "stayover_count": len(stayovers),
                "workload_minutes": workload,
                "workload_hours": round(workload / 60, 1),
                "staff_needed": staff_needed,
                "existing_auto_tasks": existing,
            })
        return day_list, housekeepers

    @router.get("/housekeeping/predictive/{property_id}")
    async def predictive_forecast(property_id: str, days: int = 7,
                                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        days = min(max(days, 1), 14)
        day_list, housekeepers = await _forecast_days(property_id, days)
        total_min = sum(d["workload_minutes"] for d in day_list)
        peak = max(day_list, key=lambda d: d["workload_minutes"]) if day_list else None
        return {
            "property_id": property_id, "days": days, "forecast": day_list,
            "housekeeper_count": len(housekeepers),
            "housekeepers": housekeepers,
            "total_workload_hours": round(total_min / 60, 1),
            "peak_day": peak["date"] if peak and peak["workload_minutes"] > 0 else None,
            "minutes_config": MINUTES,
        }

    @router.post("/housekeeping/predictive/{property_id}/generate")
    async def generate_tasks(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        target = data.get("date", "")
        try:
            date.fromisoformat(target)
        except Exception:
            raise HTTPException(status_code=422, detail="Geçerli bir tarih gerekli (YYYY-MM-DD)")
        if property_id == "all":
            raise HTTPException(status_code=400, detail="Görev üretmek için tek bir tesis seçin")

        today = datetime.now(timezone.utc).date()
        offset = (date.fromisoformat(target) - today).days
        if offset < 0 or offset > 13:
            raise HTTPException(status_code=400, detail="Tarih bugünden itibaren 14 gün içinde olmalı")
        day_list, housekeepers = await _forecast_days(property_id, offset + 1)
        day = day_list[offset]

        now = datetime.now(timezone.utc).isoformat()
        created, skipped = [], 0
        plan = ([("checkout_clean", "high", i) for i in day["departures"]]
                + [("stayover_refresh", "medium", i) for i in day["stayovers"]]
                + [("arrival_inspection", "medium", i) for i in day["arrivals"]])
        hk_idx = 0
        for kind, priority, item in plan:
            dup = await db.housekeeping_tasks.find_one({
                "property_id": property_id, "due_date": target,
                "room_number": item["room"], "task_subtype": kind,
                "auto_generated": True}, {"_id": 0, "id": 1})
            if dup:
                skipped += 1
                continue
            assignee = housekeepers[hk_idx % len(housekeepers)] if housekeepers else None
            hk_idx += 1
            task = {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "room_number": item["room"], "room_type_id": "",
                "task_type": "cleaning", "task_subtype": kind,
                "priority": priority, "status": "pending",
                "assigned_to": (assignee or {}).get("id", ""),
                "assigned_name": (assignee or {}).get("name", ""),
                "notes": {"checkout_clean": f"Check-out temizliği — {item['guest']}",
                          "stayover_refresh": f"Konaklama arası tazeleme — {item['guest']}",
                          "arrival_inspection": f"Varış öncesi kontrol — {item['guest']}"}[kind],
                "estimated_minutes": MINUTES[kind],
                "checklist": [], "due_date": target, "completed_at": "",
                "auto_generated": True, "booking_id": item["booking_id"],
                "created_at": now,
            }
            await db.housekeeping_tasks.insert_one(task)
            task.pop("_id", None)
            created.append(task)
        return {"date": target, "created": len(created), "skipped_duplicates": skipped,
                "tasks": created}

    @router.post("/housekeeping/predictive/{property_id}/suggest-shifts")
    async def suggest_shifts(property_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        """Create planned housekeeper shift entries matching the forecasted staff need."""
        target = data.get("date", "")
        try:
            date.fromisoformat(target)
        except Exception:
            raise HTTPException(status_code=422, detail="Geçerli bir tarih gerekli (YYYY-MM-DD)")
        if property_id == "all":
            raise HTTPException(status_code=400, detail="Vardiya önerisi için tek bir tesis seçin")
        today = datetime.now(timezone.utc).date()
        offset = (date.fromisoformat(target) - today).days
        if offset < 0 or offset > 13:
            raise HTTPException(status_code=400, detail="Tarih bugünden itibaren 14 gün içinde olmalı")

        day_list, housekeepers = await _forecast_days(property_id, offset + 1)
        need = day_list[offset]["staff_needed"]
        if need == 0:
            return {"date": target, "created": 0, "staff_needed": 0, "message": "Bu gün için personel ihtiyacı yok"}
        if not housekeepers:
            raise HTTPException(status_code=400, detail="Sistemde kat görevlisi (housekeeper) kullanıcı yok")

        d = date.fromisoformat(target)
        week_start = (d - timedelta(days=d.weekday())).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        created, skipped = [], 0
        for hk in housekeepers[:need]:
            dup = await db.shift_entries.find_one({
                "property_id": property_id, "date": target,
                "staff_id": hk.get("id", ""), "role": "housekeeper"}, {"_id": 0, "id": 1})
            if dup:
                skipped += 1
                continue
            entry = {
                "id": str(uuid.uuid4()), "property_id": property_id,
                "staff_id": hk.get("id", ""), "staff_name": hk.get("name", ""),
                "role": "housekeeper", "date": target, "week_start": week_start,
                "start_time": "09:00", "end_time": "17:00", "hours_worked": 8.0,
                "status": "planned",
                "notes": f"Tahminsel HK önerisi — iş yükü {day_list[offset]['workload_hours']} saat",
                "pay_type": "daily", "pay_rate": 0.0, "earned_amount": 0.0,
                "auto_suggested": True,
                "created_by": "Tahminsel HK", "created_at": now,
            }
            await db.shift_entries.insert_one(entry)
            entry.pop("_id", None)
            created.append(entry)
        return {"date": target, "staff_needed": need, "created": len(created),
                "skipped_existing": skipped, "shifts": created}

    return router
