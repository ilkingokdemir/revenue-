"""
Shift Scheduler — Weekly calendar, staff scheduling, payroll tracking, bulk actions
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_shifts_router(db, require_roles):
    router = APIRouter()

    # ==================== STAFF MEMBERS ====================

    @router.get("/shifts/staff/{property_id}")
    async def list_staff(property_id: str, role: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if role:
            query["role"] = role
        docs = await db.shift_staff.find(query, {"_id": 0}).sort("name", 1).to_list(200)
        return docs

    @router.post("/shifts/staff")
    async def create_staff(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        member = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": data.get("name", ""),
            "role": data.get("role", "housekeeper"),
            "pay_type": data.get("pay_type", "daily"),
            "pay_rate": data.get("pay_rate", 0),
            "currency": data.get("currency", "GBP"),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "is_active": True,
            "created_at": now,
        }
        await db.shift_staff.insert_one(member)
        member.pop("_id", None)
        return member

    @router.put("/shifts/staff/{staff_id}")
    async def update_staff(staff_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.shift_staff.update_one({"id": staff_id}, {"$set": updates})
        return await db.shift_staff.find_one({"id": staff_id}, {"_id": 0})

    @router.delete("/shifts/staff/{staff_id}")
    async def delete_staff(staff_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.shift_staff.delete_one({"id": staff_id})
        return {"status": "deleted"}

    # ==================== SHIFT ENTRIES ====================

    @router.get("/shifts/entries/{property_id}")
    async def list_shifts(property_id: str, week_start: str = "", status: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if week_start:
            query["week_start"] = week_start
        if status:
            query["status"] = status
        docs = await db.shift_entries.find(query, {"_id": 0}).sort("date", 1).to_list(500)
        return docs

    @router.post("/shifts/entries")
    async def create_shift(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        start_time = data.get("start_time", "09:00")
        end_time = data.get("end_time", "17:00")
        pay_type = data.get("pay_type", "daily")
        pay_rate = float(data.get("pay_rate", 0) or 0)

        # Auto-calculate hours and earned amount
        try:
            st = datetime.strptime(start_time, "%H:%M")
            en = datetime.strptime(end_time, "%H:%M")
            hours = round((en - st).seconds / 3600, 2)
        except Exception:
            hours = 8.0
        if pay_type == "hourly":
            earned = round(hours * pay_rate, 2)
        else:
            earned = round(pay_rate, 2)

        entry = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "staff_id": data.get("staff_id", ""),
            "staff_name": data.get("staff_name", ""),
            "role": data.get("role", ""),
            "date": data.get("date", ""),
            "week_start": data.get("week_start", ""),
            "start_time": start_time,
            "end_time": end_time,
            "hours_worked": hours,
            "status": data.get("status", "planned"),
            "notes": data.get("notes", ""),
            "pay_type": pay_type,
            "pay_rate": pay_rate,
            "earned_amount": earned,
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.shift_entries.insert_one(entry)
        entry.pop("_id", None)
        return entry

    @router.put("/shifts/entries/{shift_id}")
    async def update_shift(shift_id: str, updates: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.shift_entries.update_one({"id": shift_id}, {"$set": updates})
        return await db.shift_entries.find_one({"id": shift_id}, {"_id": 0})

    @router.delete("/shifts/entries/{shift_id}")
    async def delete_shift(shift_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.shift_entries.delete_one({"id": shift_id})
        return {"status": "deleted"}

    # ==================== BULK ACTIONS ====================

    @router.post("/shifts/bulk/copy-week")
    async def copy_week(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        source_week = data.get("source_week", "")
        target_week = data.get("target_week", "")
        property_id = data.get("property_id", "")
        if not source_week or not target_week:
            raise HTTPException(400, "source_week and target_week required")
        query = {"week_start": source_week}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        source_shifts = await db.shift_entries.find(query, {"_id": 0}).to_list(500)
        src_date = datetime.strptime(source_week, "%Y-%m-%d")
        tgt_date = datetime.strptime(target_week, "%Y-%m-%d")
        delta = (tgt_date - src_date).days
        now = datetime.now(timezone.utc).isoformat()
        new_shifts = []
        for s in source_shifts:
            ns = {**s}
            ns["id"] = str(uuid.uuid4())
            ns["week_start"] = target_week
            old_date = datetime.strptime(s["date"], "%Y-%m-%d")
            ns["date"] = (old_date + timedelta(days=delta)).strftime("%Y-%m-%d")
            ns["status"] = "planned"
            ns["created_at"] = now
            new_shifts.append(ns)
        if new_shifts:
            await db.shift_entries.insert_many(new_shifts)
            for ns in new_shifts:
                ns.pop("_id", None)
        return {"copied": len(new_shifts)}

    @router.post("/shifts/bulk/clear-week")
    async def clear_week(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"week_start": week_start}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        result = await db.shift_entries.delete_many(query)
        return {"deleted": result.deleted_count}

    @router.post("/shifts/bulk/publish-all")
    async def publish_all(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"week_start": week_start, "status": {"$in": ["draft", "planned"]}}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        result = await db.shift_entries.update_many(query, {"$set": {"status": "published"}})
        return {"published": result.modified_count}

    @router.post("/shifts/bulk/mark-completed")
    async def mark_completed(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"week_start": week_start, "status": {"$in": ["published", "planned"]}}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        result = await db.shift_entries.update_many(query, {"$set": {"status": "completed"}})
        return {"completed": result.modified_count}

    @router.post("/shifts/bulk/approve-completed")
    async def approve_completed(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"week_start": week_start, "status": "completed"}
        if property_id and property_id != "all":
            query["property_id"] = property_id
        result = await db.shift_entries.update_many(query, {"$set": {"status": "approved"}})
        return {"approved": result.modified_count}

    # ==================== PAYROLL SUMMARY ====================

    @router.get("/shifts/payroll/{property_id}")
    async def payroll_summary(property_id: str, week_start: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if week_start:
            query["week_start"] = week_start
        shifts = await db.shift_entries.find(query, {"_id": 0}).to_list(500)
        staff_totals = {}
        for s in shifts:
            sid = s.get("staff_id", "")
            if sid not in staff_totals:
                staff_totals[sid] = {"staff_id": sid, "staff_name": s.get("staff_name", ""), "role": s.get("role", ""),
                                     "total_shifts": 0, "total_hours": 0, "total_pay": 0, "currency": "GBP"}
            staff_totals[sid]["total_shifts"] += 1
            hours = float(s.get("hours_worked", 0) or 0)
            if hours == 0:
                try:
                    start = datetime.strptime(s.get("start_time", "09:00"), "%H:%M")
                    end = datetime.strptime(s.get("end_time", "17:00"), "%H:%M")
                    hours = (end - start).seconds / 3600
                except Exception:
                    hours = 8
            staff_totals[sid]["total_hours"] += hours
            earned = float(s.get("earned_amount", 0) or 0)
            if earned == 0:
                pay_type = s.get("pay_type", "daily")
                pay_rate = float(s.get("pay_rate", 0) or 0)
                earned = hours * pay_rate if pay_type == "hourly" else pay_rate
            staff_totals[sid]["total_pay"] += earned
        return list(staff_totals.values())

    # ==================== SYNC SHIFTS → EARNED SALARIES ====================

    @router.post("/shifts/sync-to-salaries")
    async def sync_shifts_to_salaries(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate earned salary entries from completed/approved shifts"""
        week_start = data.get("week_start", "")
        property_id = data.get("property_id", "")
        query = {"status": {"$in": ["completed", "approved"]}}
        if week_start:
            query["week_start"] = week_start
        if property_id and property_id != "all":
            query["property_id"] = property_id

        shifts = await db.shift_entries.find(query, {"_id": 0}).to_list(500)
        now = datetime.now(timezone.utc).isoformat()
        created = 0

        for s in shifts:
            # Check if already synced
            existing = await db.finance_earned_salaries.find_one({
                "shift_id": s.get("id", "")
            })
            if existing:
                continue

            hours = float(s.get("hours_worked", 0) or 0)
            if hours == 0:
                try:
                    st = datetime.strptime(s.get("start_time", "09:00"), "%H:%M")
                    en = datetime.strptime(s.get("end_time", "17:00"), "%H:%M")
                    hours = round((en - st).seconds / 3600, 2)
                except Exception:
                    hours = 8.0

            earned = float(s.get("earned_amount", 0) or 0)
            if earned == 0:
                pay_type = s.get("pay_type", "daily")
                pay_rate = float(s.get("pay_rate", 0) or 0)
                earned = round(hours * pay_rate, 2) if pay_type == "hourly" else round(pay_rate, 2)

            if earned <= 0:
                continue

            salary_entry = {
                "id": str(uuid.uuid4()),
                "shift_id": s.get("id", ""),
                "property_id": s.get("property_id", ""),
                "staff_id": s.get("staff_id", ""),
                "staff_name": s.get("staff_name", ""),
                "role": s.get("role", ""),
                "date": s.get("date", ""),
                "amount": earned,
                "hours": hours,
                "pay_type": s.get("pay_type", "daily"),
                "pay_rate": float(s.get("pay_rate", 0) or 0),
                "source": "shift",
                "notes": f"Shift {s.get('start_time','')}-{s.get('end_time','')} ({hours}h)",
                "created_at": now,
            }
            await db.finance_earned_salaries.insert_one(salary_entry)
            salary_entry.pop("_id", None)
            created += 1

        return {"synced": created, "total_shifts_processed": len(shifts)}

    return router


def create_shifts_v2_router(db, require_roles):
    """RotaPro v2 — Conflict detection, AI auto-schedule, occupancy-based staffing,
    time-off requests, clock-in/out, open shifts."""
    router = APIRouter()

    # ============== CONFLICT DETECTION ==============
    @router.get("/shifts/conflicts/{property_id}")
    async def detect_conflicts(property_id: str, week_start: str = "",
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        """Find overlapping shifts, overtime, back-to-back nights, double-booking."""
        query = {} if property_id == "all" else {"property_id": property_id}
        if week_start:
            query["week_start"] = week_start
        shifts = await db.shift_entries.find(query, {"_id": 0}).to_list(2000)
        # Get approved leaves to flag clashes
        leaves = await db.shift_leave_requests.find(
            {"status": "approved"}, {"_id": 0}
        ).to_list(500)
        leave_by_staff = {}
        for lv in leaves:
            leave_by_staff.setdefault(lv.get("staff_id"), []).append(lv)

        conflicts: list = []
        # Group by staff
        per_staff: dict = {}
        for s in shifts:
            per_staff.setdefault(s.get("staff_id"), []).append(s)

        for sid, items in per_staff.items():
            week_hours = 0
            night_dates = []
            by_date: dict = {}
            for s in items:
                hrs = float(s.get("hours_worked") or 0)
                week_hours += hrs
                by_date.setdefault(s.get("date"), []).append(s)
                # detect night shift (start >= 22:00 or end <= 07:00)
                st = s.get("start_time", "")
                en = s.get("end_time", "")
                if st >= "22:00" or en <= "07:00":
                    night_dates.append(s.get("date"))
                if hrs > 12:
                    conflicts.append({
                        "type": "long_shift",
                        "severity": "warning",
                        "staff_id": sid,
                        "staff_name": s.get("staff_name"),
                        "date": s.get("date"),
                        "message": f"{hrs} saatlik vardiya — günde 12 saat üzeri",
                    })
            # 45 hours/week TR İş Kanunu limit
            if week_hours > 45:
                conflicts.append({
                    "type": "weekly_overtime",
                    "severity": "danger",
                    "staff_id": sid,
                    "staff_name": items[0].get("staff_name"),
                    "message": f"Haftalık {week_hours:.1f} saat (TR İş Kanunu 45 saat sınırı aşıldı)",
                })
            # Same-day double booking
            for date, day_shifts in by_date.items():
                if len(day_shifts) > 1:
                    conflicts.append({
                        "type": "double_booking",
                        "severity": "danger",
                        "staff_id": sid,
                        "staff_name": day_shifts[0].get("staff_name"),
                        "date": date,
                        "message": f"{date} tarihinde {len(day_shifts)} ayrı vardiya",
                    })
            # Consecutive nights
            night_dates.sort()
            for i in range(1, len(night_dates)):
                d1 = datetime.strptime(night_dates[i - 1], "%Y-%m-%d")
                d2 = datetime.strptime(night_dates[i], "%Y-%m-%d")
                if (d2 - d1).days == 1:
                    conflicts.append({
                        "type": "consecutive_nights",
                        "severity": "warning",
                        "staff_id": sid,
                        "staff_name": items[0].get("staff_name"),
                        "message": f"Üst üste 2 gece vardiyası ({night_dates[i-1]} → {night_dates[i]})",
                    })
                    break
            # Leave clash
            for lv in leave_by_staff.get(sid, []):
                lv_start = lv.get("start_date")
                lv_end = lv.get("end_date")
                for s in items:
                    if lv_start <= s.get("date") <= lv_end:
                        conflicts.append({
                            "type": "leave_clash",
                            "severity": "danger",
                            "staff_id": sid,
                            "staff_name": s.get("staff_name"),
                            "date": s.get("date"),
                            "message": f"Onaylanmış izin ({lv_start} → {lv_end}) ile çakışıyor",
                        })

        return {"conflicts": conflicts, "count": len(conflicts)}

    # ============== OCCUPANCY-BASED STAFFING NEED ==============
    @router.get("/shifts/occupancy-needs/{property_id}")
    async def occupancy_needs(property_id: str, week_start: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Recommend staff count based on hotel occupancy forecast."""
        if not week_start:
            now = datetime.now(timezone.utc)
            week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        ws = datetime.strptime(week_start, "%Y-%m-%d")
        days = []
        for i in range(7):
            d = ws + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            bk_query = {"check_in": {"$lte": ds}, "check_out": {"$gt": ds},
                        "status": {"$in": ["confirmed", "checked_in"]}}
            if property_id != "all":
                bk_query["property_id"] = property_id
            in_house = await db.bookings.count_documents(bk_query)
            rooms = await db.rooms.count_documents(
                {} if property_id == "all" else {"property_id": property_id}
            )
            occ = round(in_house / rooms * 100, 1) if rooms else 0
            # Recommend: 1 housekeeper per 12 rooms, 1 receptionist always (2 if occ>70%),
            # 1 maintenance for every 30 rooms.
            housekeepers = max(1, round(in_house / 12)) if in_house else 1
            receptionists = 2 if occ > 70 else 1
            maintenance = max(1, round(rooms / 30)) if rooms else 1
            days.append({
                "date": ds,
                "dow": d.strftime("%a"),
                "in_house": in_house,
                "rooms": rooms,
                "occupancy_pct": occ,
                "needs": {
                    "housekeeper": housekeepers,
                    "receptionist": receptionists,
                    "maintenance": maintenance,
                },
            })
        return {"week_start": week_start, "days": days}

    # ============== AI AUTO-SCHEDULE ==============
    @router.post("/shifts/ai-suggest/{property_id}")
    async def ai_suggest(property_id: str, data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """LLM-powered schedule suggestion based on occupancy + staff."""
        import os
        import json
        week_start = data.get("week_start", "")
        if not week_start:
            now = datetime.now(timezone.utc)
            week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        # Fetch staff & occupancy
        staff = await db.shift_staff.find(
            {} if property_id == "all" else {"property_id": property_id}, {"_id": 0}
        ).to_list(100)
        if not staff:
            return {"suggestions": [], "note": "Personel listesi boş — önce personel ekleyin."}

        # Occupancy needs
        ws = datetime.strptime(week_start, "%Y-%m-%d")
        needs_per_day = []
        for i in range(7):
            d = ws + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            bk_query = {"check_in": {"$lte": ds}, "check_out": {"$gt": ds},
                        "status": {"$in": ["confirmed", "checked_in"]}}
            if property_id != "all":
                bk_query["property_id"] = property_id
            in_house = await db.bookings.count_documents(bk_query)
            needs_per_day.append({"date": ds, "dow": d.strftime("%A"), "in_house": in_house})

        api_key = os.environ.get("EMERGENT_LLM_KEY")
        suggestions = []
        if api_key:
            try:
                from emergentintegrations.llm.chat import LlmChat, UserMessage
                staff_summary = [{
                    "id": s["id"], "name": s["name"], "role": s["role"],
                    "pay_rate": s.get("pay_rate", 0), "pay_type": s.get("pay_type", "daily")
                } for s in staff]
                prompt = (
                    f"You are a hotel rota planner. Build a weekly schedule starting {week_start}. "
                    f"Staff: {json.dumps(staff_summary, ensure_ascii=False)}. "
                    f"Daily in-house guests: {json.dumps(needs_per_day, ensure_ascii=False)}. "
                    f"Rules: 1 receptionist always (2 if in_house>20), 1 housekeeper per 12 rooms, "
                    f"1 maintenance per day. Avoid >45h/week per person, no consecutive nights, "
                    f"prefer rotation. Return JSON array of {{staff_id, date, start_time, end_time, role}}."
                )
                chat = LlmChat(
                    api_key=api_key,
                    session_id=f"rota-{property_id}-{week_start}",
                    system_message="Return ONLY a JSON array, no markdown, no commentary."
                ).with_model("openai", "gpt-4o-mini")
                resp = await chat.send_message(UserMessage(text=prompt))
                txt = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
                # Extract JSON
                start = txt.find("[")
                end = txt.rfind("]")
                if start >= 0 and end > start:
                    suggestions = json.loads(txt[start:end + 1])
            except Exception as e:
                logger.error(f"AI suggest failed: {e}")
                suggestions = []

        # Fallback: deterministic round-robin
        if not suggestions:
            receptionists = [s for s in staff if s.get("role") == "receptionist"]
            housekeepers = [s for s in staff if s.get("role") == "housekeeper"]
            maint = [s for s in staff if s.get("role") == "maintenance"]
            for i, day in enumerate(needs_per_day):
                if receptionists:
                    suggestions.append({
                        "staff_id": receptionists[i % len(receptionists)]["id"],
                        "date": day["date"], "start_time": "07:00", "end_time": "15:00",
                        "role": "receptionist",
                    })
                if housekeepers:
                    suggestions.append({
                        "staff_id": housekeepers[i % len(housekeepers)]["id"],
                        "date": day["date"], "start_time": "09:00", "end_time": "17:00",
                        "role": "housekeeper",
                    })
                if maint and i % 2 == 0:
                    suggestions.append({
                        "staff_id": maint[i % len(maint)]["id"],
                        "date": day["date"], "start_time": "10:00", "end_time": "18:00",
                        "role": "maintenance",
                    })

        return {"week_start": week_start, "suggestions": suggestions, "count": len(suggestions)}

    @router.post("/shifts/ai-apply/{property_id}")
    async def ai_apply(property_id: str, data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Apply AI suggestions as draft shifts."""
        suggestions = data.get("suggestions", [])
        week_start = data.get("week_start", "")
        if not suggestions:
            return {"created": 0}
        now = datetime.now(timezone.utc).isoformat()
        # Pre-fetch staff for names + rates
        staff = await db.shift_staff.find({}, {"_id": 0}).to_list(200)
        smap = {s["id"]: s for s in staff}
        new_entries = []
        for sg in suggestions:
            sid = sg.get("staff_id")
            sm = smap.get(sid, {})
            try:
                st = datetime.strptime(sg.get("start_time", "09:00"), "%H:%M")
                en = datetime.strptime(sg.get("end_time", "17:00"), "%H:%M")
                hrs = round((en - st).seconds / 3600, 2)
            except Exception:
                hrs = 8.0
            pay_rate = float(sm.get("pay_rate", 0) or 0)
            earned = round(hrs * pay_rate, 2) if sm.get("pay_type") == "hourly" else round(pay_rate, 2)
            new_entries.append({
                "id": str(uuid.uuid4()),
                "property_id": property_id if property_id != "all" else sm.get("property_id", ""),
                "staff_id": sid,
                "staff_name": sm.get("name", ""),
                "role": sg.get("role") or sm.get("role", ""),
                "date": sg.get("date"),
                "week_start": week_start,
                "start_time": sg.get("start_time"),
                "end_time": sg.get("end_time"),
                "hours_worked": hrs,
                "status": "draft",
                "notes": "AI auto-schedule",
                "pay_type": sm.get("pay_type", "daily"),
                "pay_rate": pay_rate,
                "earned_amount": earned,
                "created_by": "AI",
                "created_at": now,
            })
        if new_entries:
            await db.shift_entries.insert_many(new_entries)
        return {"created": len(new_entries)}

    # ============== TIME-OFF / LEAVE REQUESTS ==============
    @router.get("/shifts/leaves/{property_id}")
    async def list_leaves(property_id: str, status: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if status:
            query["status"] = status
        docs = await db.shift_leave_requests.find(query, {"_id": 0}).sort("start_date", -1).to_list(200)
        return docs

    @router.post("/shifts/leaves")
    async def create_leave(data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        leave = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "staff_id": data.get("staff_id", ""),
            "staff_name": data.get("staff_name", ""),
            "leave_type": data.get("leave_type", "annual"),  # annual/sick/toil/unpaid
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "days": int(data.get("days", 1)),
            "reason": data.get("reason", ""),
            "status": data.get("status", "pending"),
            "created_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.shift_leave_requests.insert_one(leave)
        leave.pop("_id", None)
        return leave

    @router.put("/shifts/leaves/{leave_id}")
    async def update_leave(leave_id: str, updates: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.shift_leave_requests.update_one({"id": leave_id}, {"$set": updates})
        return await db.shift_leave_requests.find_one({"id": leave_id}, {"_id": 0})

    @router.get("/shifts/leave-balance/{property_id}")
    async def leave_balance(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """TR İş Kanunu: 1-5 yıl arası 14 gün, 5-15 yıl 20 gün, 15+ yıl 26 gün."""
        staff = await db.shift_staff.find(
            {} if property_id == "all" else {"property_id": property_id}, {"_id": 0}
        ).to_list(200)
        leaves = await db.shift_leave_requests.find(
            {"status": "approved", "leave_type": "annual"}, {"_id": 0}
        ).to_list(2000)
        used_by_staff: dict = {}
        for lv in leaves:
            used_by_staff[lv.get("staff_id")] = used_by_staff.get(lv.get("staff_id"), 0) + lv.get("days", 0)
        balances = []
        for s in staff:
            entitled = s.get("annual_leave_days") or 14  # default TR minimum
            used = used_by_staff.get(s["id"], 0)
            balances.append({
                "staff_id": s["id"],
                "staff_name": s.get("name", ""),
                "role": s.get("role", ""),
                "entitled": entitled,
                "used": used,
                "remaining": max(0, entitled - used),
            })
        return balances

    # ============== TIME CLOCK ==============
    @router.post("/shifts/clock-in")
    async def clock_in(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        now = datetime.now(timezone.utc)
        entry = {
            "id": str(uuid.uuid4()),
            "staff_id": data.get("staff_id", ""),
            "staff_name": data.get("staff_name", current_user.get("name", "")),
            "shift_id": data.get("shift_id", ""),
            "property_id": data.get("property_id", ""),
            "clock_in": now.isoformat(),
            "clock_out": None,
            "lat": data.get("lat"),
            "lng": data.get("lng"),
            "device": data.get("device", "web"),
        }
        await db.shift_clock_events.insert_one(entry)
        entry.pop("_id", None)
        return entry

    @router.post("/shifts/clock-out/{event_id}")
    async def clock_out(event_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        now = datetime.now(timezone.utc)
        evt = await db.shift_clock_events.find_one({"id": event_id}, {"_id": 0})
        if not evt:
            raise HTTPException(404, "clock event not found")
        ci = datetime.fromisoformat(evt["clock_in"])
        actual_hours = round((now - ci).total_seconds() / 3600, 2)
        await db.shift_clock_events.update_one(
            {"id": event_id},
            {"$set": {"clock_out": now.isoformat(), "actual_hours": actual_hours}}
        )
        return {"id": event_id, "clock_out": now.isoformat(), "actual_hours": actual_hours}

    @router.get("/shifts/clock-events/{property_id}")
    async def list_clock_events(property_id: str, days: int = 7,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = {"clock_in": {"$gte": cutoff}}
        if property_id != "all":
            query["property_id"] = property_id
        docs = await db.shift_clock_events.find(query, {"_id": 0}).sort("clock_in", -1).to_list(500)
        return docs

    # ============== OPEN SHIFTS ==============
    @router.get("/shifts/open/{property_id}")
    async def list_open_shifts(property_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        query = {"status": "open"}
        if property_id != "all":
            query["property_id"] = property_id
        docs = await db.shift_open.find(query, {"_id": 0}).sort("date", 1).to_list(200)
        return docs

    @router.post("/shifts/open")
    async def create_open_shift(data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        shift = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "date": data.get("date"),
            "start_time": data.get("start_time", "09:00"),
            "end_time": data.get("end_time", "17:00"),
            "role": data.get("role", "receptionist"),
            "notes": data.get("notes", ""),
            "status": "open",
            "claimed_by": None,
            "created_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.shift_open.insert_one(shift)
        shift.pop("_id", None)
        return shift

    @router.post("/shifts/open/{open_id}/claim")
    async def claim_open_shift(open_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper", "maintenance"))):
        staff_id = data.get("staff_id", current_user.get("id", ""))
        staff_name = data.get("staff_name", current_user.get("name", ""))
        result = await db.shift_open.update_one(
            {"id": open_id, "status": "open"},
            {"$set": {"status": "claimed", "claimed_by": staff_id,
                      "claimed_by_name": staff_name,
                      "claimed_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.matched_count == 0:
            raise HTTPException(409, "open shift no longer available")
        return await db.shift_open.find_one({"id": open_id}, {"_id": 0})

    return router
