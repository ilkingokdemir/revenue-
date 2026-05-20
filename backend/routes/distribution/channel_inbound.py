"""
Channel Inbound (Iter 160) — Reservations arrive from OTAs via:
  1. Manual paste-based entry (reception receives OTA email, pastes details)
  2. iCal URL polling (Airbnb, VRBO, Homeaway publish iCal feeds)

Webhook receivers for Booking.com/Expedia live APIs require partner credentials
and are NOT included in this MVP — when credentials are provided, plug into
the same `inbound_reservations` pipeline.

Inbound reservations are staged first (status='pending_review') and a staff
member confirms them, creating a real `bookings` row. This prevents auto-
duplication when polling iCal feeds multiple times.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import uuid
import re
import logging
import httpx

logger = logging.getLogger(__name__)


def _parse_ical(text: str):
    """Parse a minimal iCalendar feed. Returns list of {uid, summary, start, end, description}."""
    events = []
    lines = text.replace("\r\n", "\n").split("\n")
    # Unfold lines (iCal folds lines starting with space)
    unfolded = []
    for line in lines:
        if line.startswith(" ") or line.startswith("\t"):
            if unfolded:
                unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    current = None
    for line in unfolded:
        line = line.strip()
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            if current:
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, _, val = line.partition(":")
            key = key.split(";")[0].upper()
            if key == "UID":
                current["uid"] = val.strip()
            elif key == "SUMMARY":
                current["summary"] = val.strip()
            elif key == "DTSTART":
                current["start"] = val.strip()[:8]  # YYYYMMDD
            elif key == "DTEND":
                current["end"] = val.strip()[:8]
            elif key == "DESCRIPTION":
                current["description"] = val.strip().replace("\\n", "\n")
    return events


def _to_iso_date(yyyymmdd: str) -> str:
    if len(yyyymmdd) == 8 and yyyymmdd.isdigit():
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"
    return yyyymmdd


def create_channel_inbound_router(db, require_roles):
    router = APIRouter()

    # --- iCal sources ---
    @router.get("/channel-inbound/ical/sources/{property_id}")
    async def list_ical_sources(property_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.ical_sources.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        return rows

    @router.post("/channel-inbound/ical/sources")
    async def add_ical_source(data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        src = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "channel": (data.get("channel") or "Airbnb").strip(),
            "url": (data.get("url") or "").strip(),
            "room_type_id": data.get("room_type_id") or "",
            "label": (data.get("label") or "").strip(),
            "enabled": bool(data.get("enabled", True)),
            "last_pull_at": None,
            "last_pull_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not src["url"].startswith(("http://", "https://")):
            raise HTTPException(400, "Valid iCal URL required")
        await db.ical_sources.insert_one(src)
        src.pop("_id", None)
        return src

    @router.delete("/channel-inbound/ical/sources/{source_id}")
    async def delete_ical_source(source_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.ical_sources.delete_one({"id": source_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    @router.post("/channel-inbound/ical/fetch/{source_id}")
    async def fetch_ical(source_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """Fetch + parse an iCal feed. Dedupe by UID. Create `inbound_reservations` rows."""
        src = await db.ical_sources.find_one({"id": source_id}, {"_id": 0})
        if not src:
            raise HTTPException(404, "Source not found")
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.get(src["url"])
                r.raise_for_status()
                text = r.text
        except Exception as e:
            raise HTTPException(502, f"Could not fetch: {e}")

        events = _parse_ical(text)
        new_count = 0
        now = datetime.now(timezone.utc).isoformat()
        for ev in events:
            uid = ev.get("uid") or f"{src['id']}-{ev.get('start')}-{ev.get('end')}"
            existing = await db.inbound_reservations.find_one({"uid": uid}, {"_id": 0, "id": 1})
            if existing:
                continue
            row = {
                "id": str(uuid.uuid4()),
                "uid": uid,
                "property_id": src["property_id"],
                "channel": src["channel"],
                "source_type": "ical",
                "source_id": src["id"],
                "room_type_id": src.get("room_type_id", ""),
                "guest_name": (ev.get("summary") or "iCal reservation").strip(),
                "check_in": _to_iso_date(ev.get("start", "")),
                "check_out": _to_iso_date(ev.get("end", "")),
                "description": ev.get("description", ""),
                "status": "pending_review",
                "booking_id": None,
                "created_at": now,
            }
            await db.inbound_reservations.insert_one(row)
            new_count += 1

        await db.ical_sources.update_one(
            {"id": source_id},
            {"$set": {"last_pull_at": now, "last_pull_count": len(events),
                      "last_new_count": new_count}}
        )
        return {"fetched": len(events), "new_staged": new_count, "source": src["channel"]}

    # --- Manual entry ---
    @router.post("/channel-inbound/manual")
    async def manual_entry(data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        required = ["property_id", "channel", "channel_booking_ref",
                    "guest_name", "check_in", "check_out", "total_price"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            raise HTTPException(400, f"Missing: {', '.join(missing)}")
        row = {
            "id": str(uuid.uuid4()),
            "uid": f"manual:{data['channel']}:{data['channel_booking_ref']}",
            "property_id": data["property_id"],
            "channel": data["channel"],
            "source_type": "manual",
            "channel_booking_ref": data["channel_booking_ref"],
            "guest_name": data["guest_name"],
            "guest_email": (data.get("guest_email") or "").strip().lower(),
            "check_in": data["check_in"],
            "check_out": data["check_out"],
            "total_price": float(data["total_price"]),
            "currency": data.get("currency", "GBP"),
            "room_type_id": data.get("room_type_id", ""),
            "nights": data.get("nights"),
            "notes": data.get("notes", ""),
            "status": "pending_review",
            "booking_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.inbound_reservations.insert_one(row)
        row.pop("_id", None)
        return row

    # --- List + Confirm ---
    @router.get("/channel-inbound/{property_id}")
    async def list_inbound(property_id: str, status: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.inbound_reservations.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        pending = sum(1 for r in rows if r.get("status") == "pending_review")
        confirmed = sum(1 for r in rows if r.get("status") == "confirmed")
        return {"rows": rows, "pending_count": pending, "confirmed_count": confirmed, "total": len(rows)}

    @router.post("/channel-inbound/{inbound_id}/confirm")
    async def confirm(inbound_id: str, data: Dict = None,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Promote an inbound reservation to a real `bookings` row."""
        row = await db.inbound_reservations.find_one({"id": inbound_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "Not found")
        if row.get("status") != "pending_review":
            raise HTTPException(409, f"Already {row.get('status')}")

        # Build a booking
        check_in = row.get("check_in", "")
        check_out = row.get("check_out", "")
        try:
            ci = datetime.strptime(check_in, "%Y-%m-%d").date()
            co = datetime.strptime(check_out, "%Y-%m-%d").date()
            nights = max(1, (co - ci).days)
        except ValueError:
            nights = 1

        total = float(row.get("total_price") or 0)
        booking = {
            "id": str(uuid.uuid4()),
            "booking_ref": re.sub(r"[^A-Z0-9]", "", (row.get("channel_booking_ref") or row.get("id")[:8]).upper())[:12],
            "property_id": row["property_id"],
            "guest_name": row.get("guest_name", "Guest"),
            "guest_email": row.get("guest_email", ""),
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "adults": 1, "children": 0,
            "total_price": total,
            "rate_per_night": round(total / nights, 2) if nights else total,
            "status": "confirmed",
            "payment_status": "pending",
            "source": row.get("channel", ""),
            "source_code": (row.get("channel") or "").lower().replace(".", "_").replace(" ", "_"),
            "room_type_id": row.get("room_type_id", ""),
            "currency": row.get("currency", "GBP"),
            "channel_reference": row.get("channel_booking_ref") or row.get("uid"),
            "inbound_reservation_id": row["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.bookings.insert_one(booking)
        booking.pop("_id", None)

        await db.inbound_reservations.update_one(
            {"id": inbound_id},
            {"$set": {"status": "confirmed", "booking_id": booking["id"],
                      "confirmed_at": datetime.now(timezone.utc).isoformat(),
                      "confirmed_by": current_user.get("name", "")}}
        )
        return {"status": "confirmed", "booking": booking}

    @router.post("/channel-inbound/{inbound_id}/reject")
    async def reject(inbound_id: str, data: Dict,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.inbound_reservations.update_one(
            {"id": inbound_id},
            {"$set": {"status": "rejected",
                      "reject_reason": (data.get("reason") or "").strip(),
                      "rejected_at": datetime.now(timezone.utc).isoformat(),
                      "rejected_by": current_user.get("name", "")}}
        )
        return {"status": "rejected"}

    return router
