"""
Group Rooming List CSV Import
-----------------------------
Bulk-creates child bookings for a group from a CSV / spreadsheet upload.

Expected CSV columns (case-insensitive, in any order):
  guest_name (required)
  email
  phone
  room_type    (matched against room_types.name)
  arrival      (YYYY-MM-DD; falls back to group's check_in)
  departure    (YYYY-MM-DD; falls back to group's check_out)
  rate_override (numeric; optional)
  notes

Endpoints:
  POST /api/group-rooming/preview     — body: group_id, csv_text  (returns parsed rows + warnings)
  POST /api/group-rooming/commit      — body: group_id, rows[]    (creates bookings, attaches to group)
  GET  /api/group-rooming/{group_id}  — list group child bookings
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, List
import csv
import io
import uuid


REQUIRED = {"guest_name"}
OPTIONAL = {"email", "phone", "room_type", "arrival", "departure", "rate_override", "notes"}


def _parse_csv(csv_text: str) -> tuple[List[Dict], List[str]]:
    warnings: List[str] = []
    if not csv_text or not csv_text.strip():
        return [], ["empty CSV"]
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        return [], ["no header row"]
    headers = [h.strip().lower() for h in reader.fieldnames]
    if "guest_name" not in headers:
        return [], ["missing required column: guest_name"]
    rows: List[Dict] = []
    for i, raw in enumerate(reader, start=2):
        clean = { (k or "").strip().lower(): (v or "").strip() for k, v in raw.items() }
        if not clean.get("guest_name"):
            warnings.append(f"row {i}: missing guest_name — skipped")
            continue
        rows.append({
            "row": i,
            "guest_name":   clean.get("guest_name"),
            "email":        clean.get("email", ""),
            "phone":        clean.get("phone", ""),
            "room_type":    clean.get("room_type", ""),
            "arrival":      clean.get("arrival", ""),
            "departure":    clean.get("departure", ""),
            "rate_override": clean.get("rate_override", ""),
            "notes":        clean.get("notes", ""),
        })
    return rows, warnings


def create_group_rooming_router(db, require_roles):
    router = APIRouter()

    @router.post("/group-rooming/preview")
    async def preview(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        group_id = data.get("group_id", "")
        if not group_id:
            raise HTTPException(400, "group_id required")
        group = await db.groups.find_one({"id": group_id}, {"_id": 0})
        if not group:
            raise HTTPException(404, "Group not found")
        csv_text = data.get("csv_text", "")
        rows, warnings = _parse_csv(csv_text)

        # Map room types
        property_id = group.get("property_id", "")
        rt_docs = await db.room_types.find({"property_id": property_id}, {"_id": 0}).to_list(50)
        rt_by_name = {r.get("name", "").lower(): r for r in rt_docs}

        for r in rows:
            r["check_in"]  = r.get("arrival")  or group.get("check_in", "")
            r["check_out"] = r.get("departure") or group.get("check_out", "")
            rtname = r.get("room_type", "").lower()
            rt = rt_by_name.get(rtname)
            if rt:
                r["room_type_id"]   = rt.get("id")
                r["room_type_name"] = rt.get("name")
                r["base_rate"] = float(rt.get("base_price") or rt.get("price_per_night") or 0)
            else:
                r["room_type_id"]   = ""
                r["room_type_name"] = r.get("room_type", "")
                r["base_rate"] = 0.0
                warnings.append(f"row {r['row']}: room_type '{r.get('room_type','')}' not found at this property")
            try:
                r["rate"] = float(r.get("rate_override") or r["base_rate"])
            except Exception:
                r["rate"] = r["base_rate"]
        return {"group_id": group_id, "rows": rows, "warnings": warnings, "row_count": len(rows)}

    @router.post("/group-rooming/commit")
    async def commit(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        group_id = data.get("group_id", "")
        rows = data.get("rows") or []
        if not group_id or not rows:
            raise HTTPException(400, "group_id and rows required")
        group = await db.groups.find_one({"id": group_id}, {"_id": 0})
        if not group:
            raise HTTPException(404, "Group not found")
        property_id = group.get("property_id", "")

        created: List[Dict] = []
        for r in rows:
            check_in = r.get("check_in") or group.get("check_in", "")
            check_out = r.get("check_out") or group.get("check_out", "")
            try:
                d_in = datetime.fromisoformat(check_in).date()
                d_out = datetime.fromisoformat(check_out).date()
                nights = max(1, (d_out - d_in).days)
            except Exception:
                nights = 1
            rate = float(r.get("rate") or 0)
            total = round(rate * nights, 2)
            booking_id = str(uuid.uuid4())
            booking_ref = f"GRP-{group_id[:6].upper()}-{booking_id[:6].upper()}"
            doc = {
                "id": booking_id,
                "property_id": property_id,
                "booking_ref": booking_ref,
                "channel": "group",
                "source": "group",
                "group_id": group_id,
                "group_name": group.get("client_name") or group.get("name", ""),
                "guest_name": r.get("guest_name", ""),
                "guest_email": r.get("email", ""),
                "guest_phone": r.get("phone", ""),
                "room_type_id": r.get("room_type_id", ""),
                "room_type_name": r.get("room_type_name", ""),
                "check_in": check_in, "check_out": check_out, "nights": nights,
                "guests": int(r.get("guests") or 1),
                "rate_per_night": rate,
                "subtotal": total, "total_price": total,
                "currency": group.get("currency", "GBP"),
                "status": "confirmed",
                "internal_notes": r.get("notes", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user.get("name", "Staff"),
            }
            await db.bookings.insert_one(dict(doc))
            doc.pop("_id", None)
            created.append({"id": doc["id"], "booking_ref": booking_ref, "guest_name": doc["guest_name"]})

        # Stamp group with total bookings count
        await db.groups.update_one({"id": group_id}, {
            "$inc": {"rooms_booked": len(created)},
            "$set": {"last_rooming_import_at": datetime.now(timezone.utc).isoformat()},
        })
        return {"ok": True, "group_id": group_id, "created": len(created), "items": created}

    @router.get("/group-rooming/{group_id}")
    async def list_group_bookings(group_id: str,
                                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.bookings.find(
            {"group_id": group_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        return {"group_id": group_id, "count": len(rows), "items": rows}

    return router
