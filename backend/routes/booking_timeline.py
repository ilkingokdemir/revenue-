"""
Booking Timeline — Gantt-style calendar API.
Returns rooms grouped by type with bookings for a date range.
Also seeds individual rooms if the rooms collection is empty for a property.
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import random
import asyncio
import resend
import logging

logger = logging.getLogger(__name__)

GUEST_FIRST = ["James", "Emma", "Oliver", "Sophia", "William", "Isabella", "Liam", "Mia", "Noah", "Charlotte",
               "Lucas", "Amelia", "Henry", "Harper", "Alexander", "Evelyn", "Benjamin", "Abigail", "Daniel", "Emily",
               "Valentina", "Marco", "Yuki", "Sven", "Priya", "Ahmed", "Fatima", "Chen", "Lars", "Rosa"]
GUEST_LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee",
              "Müller", "Tanaka", "Petrov", "Rossi", "Kim", "Singh", "Okafor", "Björk", "Santos", "Wang"]
SOURCES = ["Booking.com", "Expedia", "Direct", "Airbnb", "Hotels.com", "Agoda", "Phone", "Walk-in", "Website", "Affiliate"]
SOURCE_CODES = {"Booking.com": "BO", "Expedia": "EX", "Direct": "DI", "Airbnb": "AB", "Hotels.com": "HO",
                "Agoda": "AG", "Phone": "PH", "Walk-in": "WI", "Website": "WB", "Affiliate": "AF"}


def create_booking_timeline_router(db, require_roles):
    router = APIRouter()

    async def _ensure_rooms(pid):
        """Auto-generate individual rooms for a property if none exist."""
        existing = await db.rooms.count_documents({"property_id": pid})
        if existing > 0:
            return

        room_types = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
        if not room_types:
            return

        rooms_to_insert = []
        for rt in room_types:
            rt_id = rt.get("id", "")
            rt_name = rt.get("name", "Room")
            count = random.randint(2, 5)
            for i in range(1, count + 1):
                short = rt_name.split()[0] if rt_name else "Room"
                room = {
                    "id": f"{rt_id}-r{i}",
                    "property_id": pid,
                    "room_type_id": rt_id,
                    "name": f"{short} {i:02d}",
                    "floor": random.choice([1, 2, 3]),
                    "status": "available",
                    "housekeeping": random.choice(["clean", "clean", "clean", "dirty", "inspected"]),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                rooms_to_insert.append(room)

        if rooms_to_insert:
            await db.rooms.insert_many(rooms_to_insert)
            logger.info(f"Seeded {len(rooms_to_insert)} rooms for property {pid}")

    async def _ensure_bookings(pid, window_start=None, window_end=None):
        """Seed sample bookings if too few active bookings with rooms assigned.
        If window_start/window_end given, also seed bookings overlapping that window."""
        # First, assign rooms to existing bookings that lack room_id
        unassigned = await db.bookings.find(
            {"property_id": pid, "status": {"$nin": ["cancelled"]},
             "$or": [{"room_id": {"$exists": False}}, {"room_id": ""}]},
            {"_id": 0}
        ).to_list(500)

        if unassigned:
            rooms = await db.rooms.find({"property_id": pid}, {"_id": 0}).to_list(200)
            rooms_by_type = {}
            for r in rooms:
                rooms_by_type.setdefault(r.get("room_type_id", ""), []).append(r)

            for b in unassigned:
                rtid = b.get("room_type_id", "")
                available_rooms = rooms_by_type.get(rtid, [])
                if not available_rooms:
                    all_rooms = [r for rl in rooms_by_type.values() for r in rl]
                    if all_rooms:
                        chosen = random.choice(all_rooms)
                    else:
                        continue
                else:
                    chosen = random.choice(available_rooms)

                source = random.choice(SOURCES)
                nights = 1
                ci = b.get("check_in", "")
                co = b.get("check_out", "")
                if ci and co:
                    try:
                        ci_dt = datetime.strptime(ci[:10], "%Y-%m-%d")
                        co_dt = datetime.strptime(co[:10], "%Y-%m-%d")
                        nights = max(1, (co_dt - ci_dt).days)
                    except ValueError:
                        pass

                rate = float(b.get("total_price", 0) or 0)
                rpn = round(rate / max(nights, 1), 2) if rate else round(random.uniform(60, 150), 2)

                await db.bookings.update_one({"id": b["id"]}, {"$set": {
                    "room_id": chosen.get("id", ""),
                    "nights": nights,
                    "source": b.get("source") or source,
                    "source_code": SOURCE_CODES.get(b.get("source") or source, "OT"),
                    "rate_per_night": rpn,
                }})

        # Then check if we need additional seeded bookings
        active = await db.bookings.count_documents({
            "property_id": pid, "status": {"$nin": ["cancelled"]},
            "room_id": {"$exists": True, "$ne": ""}
        })

        # Decide which window to seed: the requested one (if empty) or the default "now" window
        seed_start = None
        seed_end = None
        now = datetime.now(timezone.utc)
        if window_start and window_end:
            # Check if requested window has any bookings
            window_count = await db.bookings.count_documents({
                "property_id": pid,
                "status": {"$nin": ["cancelled"]},
                "room_id": {"$exists": True, "$ne": ""},
                "check_in": {"$lt": window_end.strftime("%Y-%m-%d")},
                "check_out": {"$gte": window_start.strftime("%Y-%m-%d")},
            })
            if window_count < 3:
                # Expand window by 2 days on each side for natural feel
                seed_start = window_start - timedelta(days=2)
                seed_end = window_end + timedelta(days=2)
        # Default initial seed if global data is sparse
        if seed_start is None and active < 5:
            seed_start = now - timedelta(days=3)
            seed_end = now + timedelta(days=21)

        if seed_start is None:
            return

        rooms = await db.rooms.find({"property_id": pid}, {"_id": 0}).to_list(100)
        if not rooms:
            return

        room_types = await db.room_types.find({"property_id": pid}, {"_id": 0}).to_list(20)
        rate_map = {}
        for rt in room_types:
            rate_map[rt.get("id", "")] = float(rt.get("base_rate") or random.randint(60, 150))

        bookings = []

        for room in rooms:
            rid = room.get("id", "")
            rtid = room.get("room_type_id", "")
            base = rate_map.get(rtid, 90)

            cursor_date = seed_start
            attempts = 0
            while cursor_date < seed_end and attempts < 8:
                attempts += 1
                if random.random() < 0.25:
                    cursor_date += timedelta(days=random.randint(1, 3))
                    continue

                nights = random.choices([1, 2, 3, 4, 5, 7], weights=[30, 30, 20, 10, 5, 5])[0]
                ci = cursor_date.strftime("%Y-%m-%d")
                co = (cursor_date + timedelta(days=nights)).strftime("%Y-%m-%d")
                rate = round(base * random.uniform(0.85, 1.3), 2)
                total = round(rate * nights, 2)
                adults = random.choice([1, 1, 2, 2, 2, 3])

                is_past = cursor_date < now
                if is_past:
                    status = random.choices(
                        ["checked_out", "checked_in", "no_show"],
                        weights=[60, 20, 10]
                    )[0]
                else:
                    status = random.choices(
                        ["confirmed", "confirmed", "pending"],
                        weights=[60, 20, 20]
                    )[0]

                source = random.choice(SOURCES)
                fname = random.choice(GUEST_FIRST)
                lname = random.choice(GUEST_LAST)

                created_days_before = random.randint(2, 30)
                created = (cursor_date - timedelta(days=created_days_before)).isoformat()

                booking = {
                    "id": str(uuid.uuid4()),
                    "property_id": pid,
                    "room_type_id": rtid,
                    "room_id": rid,
                    "guest_name": f"{fname} {lname}",
                    "guest_email": f"{fname.lower()}.{lname.lower()}@example.com",
                    "guest_phone": f"+44 7{random.randint(100,999)} {random.randint(100,999)} {random.randint(1000,9999)}",
                    "check_in": ci,
                    "check_out": co,
                    "nights": nights,
                    "adults": adults,
                    "children": random.choice([0, 0, 0, 1]),
                    "rooms": 1,
                    "rate_per_night": rate,
                    "total_price": total,
                    "currency": "GBP",
                    "status": status,
                    "payment_status": "paid" if status in ["checked_out", "checked_in"] else random.choice(["paid", "pending"]),
                    "source": source,
                    "source_code": SOURCE_CODES.get(source, "OT"),
                    "notes": "",
                    "created_at": created,
                }
                bookings.append(booking)
                cursor_date += timedelta(days=nights + random.choice([0, 0, 1]))

        if bookings:
            await db.bookings.insert_many(bookings)
            logger.info(f"Seeded {len(bookings)} bookings for property {pid}")

    @router.get("/bookings/timeline/{property_id}")
    async def get_booking_timeline(property_id: str, start: str = "", days: int = 14,
                                   current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Gantt-style timeline: rooms grouped by type with booking bars. Freely navigable — seeds data for any visible window."""
        now = datetime.now(timezone.utc)
        if start:
            try:
                start_date = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                start_date = now
        else:
            start_date = now - timedelta(days=1)

        end_date = start_date + timedelta(days=days)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Get properties
        if property_id == "all":
            props = await db.properties.find({}, {"_id": 0}).to_list(50)
            # Find a property with actual room types
            chosen_pid = None
            for p in props:
                pid_check = p.get("id", "")
                rt_count = await db.room_types.count_documents({"property_id": pid_check})
                if rt_count > 0:
                    chosen_pid = pid_check
                    break
            property_id = chosen_pid or (props[0].get("id", "default") if props else "default")
        else:
            pass

        # Ensure rooms + bookings exist
        await _ensure_rooms(property_id)
        await _ensure_bookings(property_id, window_start=start_date, window_end=end_date)

        # Load room types
        room_types = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(20)

        # Load rooms
        rooms = await db.rooms.find({"property_id": property_id}, {"_id": 0}).to_list(200)

        # Load bookings in range
        bookings = await db.bookings.find({
            "property_id": property_id,
            "status": {"$nin": ["cancelled"]},
            "check_in": {"$lt": end_str},
            "check_out": {"$gt": start_str},
        }, {"_id": 0}).to_list(1000)

        # Enrich with live folio balance so the pill reflects actual payments made
        if bookings:
            booking_ids = [b["id"] for b in bookings if b.get("id")]
            paid_map = {}
            charged_map = {}
            if booking_ids:
                pipeline = [
                    {"$match": {"booking_id": {"$in": booking_ids}}},
                    {"$group": {
                        "_id": {"b": "$booking_id", "t": "$type"},
                        "sum": {"$sum": {"$toDouble": {"$ifNull": ["$amount", 0]}}},
                    }},
                ]
                # Primary collection for folio entries is `folio_items`.
                # Some legacy code writes into `folio_charges`; include both for safety.
                for coll_name in ("folio_items", "folio_charges"):
                    async for row in db[coll_name].aggregate(pipeline):
                        key = row["_id"]
                        bid = key.get("b")
                        if not bid:
                            continue
                        t = (key.get("t") or "").lower()
                        if t == "payment":
                            paid_map[bid] = paid_map.get(bid, 0) + float(row["sum"])
                        else:
                            charged_map[bid] = charged_map.get(bid, 0) + float(row["sum"])
            for b in bookings:
                bid = b.get("id")
                paid = round(paid_map.get(bid, 0), 2)
                charged = round(charged_map.get(bid, 0), 2)
                gross = charged if charged > 0 else round(float(b.get("total_price") or 0), 2)
                b["folio_paid"] = paid
                b["folio_charged"] = charged
                b["balance_due"] = max(0.0, round(gross - paid, 2))

        # Group rooms by type
        rooms_by_type = {}
        for r in rooms:
            rtid = r.get("room_type_id", "")
            rooms_by_type.setdefault(rtid, []).append(r)

        # Index bookings by room_id
        bookings_by_room = {}
        bookings_by_type = {}
        for b in bookings:
            rid = b.get("room_id", "")
            rtid = b.get("room_type_id", "")
            if rid:
                bookings_by_room.setdefault(rid, []).append(b)
            bookings_by_type.setdefault(rtid, []).append(b)

        # Build date columns
        date_cols = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            date_cols.append({
                "date": ds,
                "day": d.day,
                "dow": d.strftime("%a"),
                "month": d.strftime("%b"),
                "is_today": ds == now.strftime("%Y-%m-%d"),
                "is_weekend": d.weekday() >= 5,
            })

        # Build room type groups
        total_rooms_count = len(rooms)
        groups = []
        for rt in room_types:
            rtid = rt.get("id", "")
            type_rooms = rooms_by_type.get(rtid, [])
            type_bookings = bookings_by_type.get(rtid, [])

            rate = float(rt.get("base_rate") or 0)
            if not rate:
                if type_bookings:
                    rate = sum(b.get("rate_per_night", 0) for b in type_bookings) / len(type_bookings)
                else:
                    rate = 90

            room_entries = []
            for room in type_rooms:
                room_bks = bookings_by_room.get(room.get("id", ""), [])
                bk_bars = []
                for b in room_bks:
                    bk_bars.append({
                        "id": b.get("id", ""),
                        "guest_name": b.get("guest_name", ""),
                        "check_in": b.get("check_in", ""),
                        "check_out": b.get("check_out", ""),
                        "nights": b.get("nights", 1),
                        "status": b.get("status", "confirmed"),
                        "source": b.get("source", ""),
                        "source_code": b.get("source_code", ""),
                        "total_price": b.get("total_price", 0),
                        "rate_per_night": b.get("rate_per_night", 0),
                        "adults": b.get("adults", 1),
                        "children": b.get("children", 0),
                        "payment_status": b.get("payment_status", "pending"),
                    })
                room_entries.append({
                    "id": room.get("id", ""),
                    "name": room.get("name", ""),
                    "floor": room.get("floor", 1),
                    "status": room.get("status", "available"),
                    "housekeeping": room.get("housekeeping", "clean"),
                    "bookings": bk_bars,
                })

            groups.append({
                "room_type_id": rtid,
                "room_type_name": rt.get("name", ""),
                "rate": round(rate, 2),
                "total_rooms": len(type_rooms),
                "rooms": room_entries,
            })

        # Daily occupancy
        daily_occ = []
        for col in date_cols:
            ds = col["date"]
            booked = sum(1 for b in bookings if b.get("check_in", "") <= ds < b.get("check_out", ""))
            occ_pct = round((booked / max(total_rooms_count, 1)) * 100) if total_rooms_count else 0
            daily_occ.append({
                "date": ds,
                "booked": booked,
                "available": max(0, total_rooms_count - booked),
                "occupancy_pct": occ_pct,
            })

        return {
            "property_id": property_id,
            "start": start_str,
            "end": end_str,
            "days": days,
            "date_columns": date_cols,
            "daily_occupancy": daily_occ,
            "groups": groups,
            "total_rooms": total_rooms_count,
            "total_bookings": len(bookings),
        }

    @router.get("/bookings/timeline/{property_id}/detail/{booking_id}")
    async def get_booking_detail(property_id: str, booking_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Full booking detail for slide-over panel."""
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            return {"error": "Booking not found"}

        room = await db.rooms.find_one({"id": booking.get("room_id", "")}, {"_id": 0})
        room_type = await db.room_types.find_one({"id": booking.get("room_type_id", "")}, {"_id": 0})

        return {
            **booking,
            "room_name": room.get("name", "") if room else "",
            "room_floor": room.get("floor", "") if room else "",
            "room_type_name": room_type.get("name", "") if room_type else "",
        }

    @router.put("/bookings/timeline/{property_id}/status/{booking_id}")
    async def update_booking_status(property_id: str, booking_id: str, data: Dict,
                                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Quick status change from timeline. Also triggers:
        - Housekeeping auto-dispatch (OOS 'Deep Clean' block) on checkout
        - Auto-email folio to guest on checkout (opt-out via booking.auto_email_folio_on_checkout=False)
        """
        new_status = data.get("status", "")
        if new_status not in ["pending", "confirmed", "checked_in", "checked_out", "no_show", "cancelled"]:
            return {"error": "Invalid status"}

        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("name", ""),
        }})

        if new_status == "checked_out":
            updated = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
            if updated:
                # 1. Housekeeping auto-dispatch — block the room with "Deep Clean" OOS
                if updated.get("room_id"):
                    co_date = updated.get("check_out") or datetime.now(timezone.utc).date().isoformat()
                    try:
                        end_date = (datetime.strptime(co_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    except Exception:
                        end_date = co_date
                    await db.oos_blocks.insert_one({
                        "id": str(uuid.uuid4()),
                        "room_id": updated["room_id"],
                        "property_id": updated.get("property_id", property_id or ""),
                        "start": co_date,
                        "end": end_date,
                        "reason": "Deep Clean",
                        "auto": True,
                        "booking_id": booking_id,
                        "created_by": "system:housekeeping-autodispatch",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    await db.rooms.update_one({"id": updated["room_id"]}, {"$set": {"housekeeping": "dirty"}})

                # 2. (Auto-email folio on checkout intentionally disabled per user preference —
                #     reception can still email manually via the "Email" button on the Actions tab.)

        return {"status": new_status, "booking_id": booking_id}

    @router.put("/bookings/timeline/{property_id}/reassign/{booking_id}")
    async def reassign_room(property_id: str, booking_id: str, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Drag-and-drop room reassignment."""
        new_room_id = data.get("room_id", "")
        if not new_room_id:
            return {"error": "room_id required"}

        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            return {"error": "Booking not found"}

        new_room = await db.rooms.find_one({"id": new_room_id}, {"_id": 0})
        if not new_room:
            return {"error": "Room not found"}

        old_room_id = booking.get("room_id", "")
        new_room_type_id = new_room.get("room_type_id", "")

        # Check for conflicts — is the new room already booked for these dates?
        ci = booking.get("check_in", "")
        co = booking.get("check_out", "")
        conflict = await db.bookings.find_one({
            "room_id": new_room_id,
            "id": {"$ne": booking_id},
            "status": {"$nin": ["cancelled"]},
            "check_in": {"$lt": co},
            "check_out": {"$gt": ci},
        })
        if conflict:
            return {"error": "Room conflict", "conflict_guest": conflict.get("guest_name", ""), "conflict_dates": f"{conflict.get('check_in')} - {conflict.get('check_out')}"}

        await db.bookings.update_one({"id": booking_id}, {"$set": {
            "room_id": new_room_id,
            "room_type_id": new_room_type_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("name", ""),
        }})

        return {
            "booking_id": booking_id,
            "old_room_id": old_room_id,
            "new_room_id": new_room_id,
            "new_room_name": new_room.get("name", ""),
            "status": "reassigned",
        }

    @router.post("/bookings/timeline/{property_id}/bulk-action")
    async def bulk_action(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        """Bulk check-in, check-out, or other status changes."""
        booking_ids = data.get("booking_ids", [])
        action = data.get("action", "")
        if not booking_ids or not action:
            return {"error": "booking_ids and action required"}
        if action not in ["checked_in", "checked_out", "confirmed", "cancelled", "no_show"]:
            return {"error": "Invalid action"}

        now_iso = datetime.now(timezone.utc).isoformat()
        updated = 0
        errors = []

        for bid in booking_ids:
            booking = await db.bookings.find_one({"id": bid}, {"_id": 0})
            if not booking:
                errors.append({"id": bid, "error": "not found"})
                continue

            current_status = booking.get("status", "")
            # Validate transitions
            valid = False
            if action == "checked_in" and current_status in ["confirmed", "pending"]:
                valid = True
            elif action == "checked_out" and current_status == "checked_in":
                valid = True
            elif action == "confirmed" and current_status == "pending":
                valid = True
            elif action == "cancelled" and current_status not in ["cancelled", "checked_out"]:
                valid = True
            elif action == "no_show" and current_status in ["confirmed", "pending"]:
                valid = True

            if valid:
                await db.bookings.update_one({"id": bid}, {"$set": {
                    "status": action,
                    "updated_at": now_iso,
                    "updated_by": current_user.get("name", ""),
                }})
                updated += 1

                # Bulk checkout — also fire the housekeeping + auto-email hooks
                if action == "checked_out":
                    updated_bk = await db.bookings.find_one({"id": bid}, {"_id": 0})
                    if updated_bk and updated_bk.get("room_id"):
                        co_date = updated_bk.get("check_out") or datetime.now(timezone.utc).date().isoformat()
                        try:
                            end_date = (datetime.strptime(co_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                        except Exception:
                            end_date = co_date
                        await db.oos_blocks.insert_one({
                            "id": str(uuid.uuid4()),
                            "room_id": updated_bk["room_id"],
                            "property_id": updated_bk.get("property_id", property_id or ""),
                            "start": co_date, "end": end_date,
                            "reason": "Deep Clean", "auto": True, "booking_id": bid,
                            "created_by": "system:housekeeping-autodispatch",
                            "created_at": now_iso,
                        })
                        await db.rooms.update_one({"id": updated_bk["room_id"]}, {"$set": {"housekeeping": "dirty"}})
            else:
                errors.append({"id": bid, "error": f"Cannot {action} from {current_status}"})

        return {
            "action": action,
            "updated": updated,
            "errors": errors,
            "total_requested": len(booking_ids),
        }

    @router.get("/bookings/timeline/{property_id}/todays-actions")
    async def todays_actions(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Get today's arrivals, departures, and in-house guests for bulk actions."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        query_base = {"status": {"$nin": ["cancelled"]}}
        if property_id != "all":
            query_base["property_id"] = property_id

        arrivals = await db.bookings.find(
            {**query_base, "check_in": today, "status": {"$in": ["confirmed", "pending"]}},
            {"_id": 0}
        ).to_list(200)

        departures = await db.bookings.find(
            {**query_base, "check_out": today, "status": "checked_in"},
            {"_id": 0}
        ).to_list(200)

        in_house = await db.bookings.find(
            {**query_base, "check_in": {"$lte": today}, "check_out": {"$gt": today}, "status": "checked_in"},
            {"_id": 0}
        ).to_list(200)

        return {
            "date": today,
            "arrivals": [{"id": b["id"], "guest_name": b.get("guest_name", ""), "room_id": b.get("room_id", ""), "check_in": b.get("check_in", ""), "check_out": b.get("check_out", ""), "status": b.get("status", "")} for b in arrivals],
            "departures": [{"id": b["id"], "guest_name": b.get("guest_name", ""), "room_id": b.get("room_id", ""), "check_in": b.get("check_in", ""), "check_out": b.get("check_out", ""), "status": b.get("status", "")} for b in departures],
            "in_house": [{"id": b["id"], "guest_name": b.get("guest_name", ""), "room_id": b.get("room_id", ""), "check_in": b.get("check_in", ""), "check_out": b.get("check_out", ""), "status": b.get("status", "")} for b in in_house],
            "counts": {
                "arrivals": len(arrivals),
                "departures": len(departures),
                "in_house": len(in_house),
            }
        }

    return router
