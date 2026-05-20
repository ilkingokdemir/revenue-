"""
Cleaning Checklists per Room Type
---------------------------------
Per-property + per-room-type checklists with photo evidence. Housekeepers
tick off each item; supervisors run an inspection pass. A completion record
is written so quality-of-clean is auditable per cleaner per shift.

Endpoints:
  GET  /api/cleaning-checklists/{property_id}/templates      — list templates
  POST /api/cleaning-checklists/{property_id}/templates       — create / update
  DELETE .../templates/{template_id}                          — remove
  POST /api/cleaning-checklists/run                            — start a run for a room
  POST /api/cleaning-checklists/run/{run_id}/tick              — tick an item
  POST /api/cleaning-checklists/run/{run_id}/complete          — finalize
  GET  /api/cleaning-checklists/{property_id}/runs             — recent runs
  GET  /api/cleaning-checklists/{property_id}/stats            — KPIs
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


# Industry-standard 18-point checklist used as default template.
DEFAULT_ITEMS = [
    {"key": "trash_emptied",      "label": "All bins emptied & relined",         "section": "removal"},
    {"key": "linen_changed",      "label": "Bed linen fully changed",            "section": "bedroom"},
    {"key": "bed_made",           "label": "Bed made hospital-corner style",     "section": "bedroom"},
    {"key": "towels_replaced",    "label": "All towels replaced + folded",       "section": "bathroom"},
    {"key": "amenities_replenished","label": "Amenities/toiletries restocked",   "section": "bathroom"},
    {"key": "minibar_checked",    "label": "Minibar restocked & logged",         "section": "minibar"},
    {"key": "surfaces_dusted",    "label": "All surfaces dusted",                "section": "cleaning"},
    {"key": "floors_vacuumed",    "label": "Carpet vacuumed / floors mopped",    "section": "cleaning"},
    {"key": "bathroom_disinfected","label": "Toilet/sink/shower disinfected",    "section": "bathroom"},
    {"key": "mirror_polished",    "label": "Mirrors streak-free",                "section": "bathroom"},
    {"key": "windows_wiped",      "label": "Windows + sills wiped",              "section": "cleaning"},
    {"key": "ac_set",             "label": "AC reset to 21°C",                   "section": "controls"},
    {"key": "tv_remote_disinfected","label": "TV remote disinfected",            "section": "controls"},
    {"key": "lightbulbs_check",   "label": "All bulbs working",                  "section": "checks"},
    {"key": "plumbing_check",     "label": "Plumbing check (no drips)",          "section": "checks"},
    {"key": "stationery",         "label": "Stationery / hotel folder restocked","section": "details"},
    {"key": "scent",              "label": "Room aired & lightly scented",       "section": "details"},
    {"key": "final_walkthrough",  "label": "Final walkthrough — guest-ready",    "section": "checks"},
]


def create_cleaning_checklists_router(db, require_roles):
    router = APIRouter()

    async def _ensure_default(property_id: str, room_type_id: str = "") -> dict:
        existing = await db.cleaning_checklist_templates.find_one(
            {"property_id": property_id, "room_type_id": room_type_id, "active": True},
            {"_id": 0},
        )
        if existing:
            return existing
        tpl = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "room_type_id": room_type_id,
            "name": "Standard 18-point" + (f" ({room_type_id})" if room_type_id else ""),
            "items": DEFAULT_ITEMS,
            "active": True,
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.cleaning_checklist_templates.insert_one(dict(tpl))
        tpl.pop("_id", None)
        return tpl

    @router.get("/cleaning-checklists/{property_id}/templates")
    async def list_templates(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping"))):
        await _ensure_default(property_id, "")
        rows = await db.cleaning_checklist_templates.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", 1).to_list(50)
        return {"items": rows, "default_items": DEFAULT_ITEMS}

    @router.post("/cleaning-checklists/{property_id}/templates")
    async def upsert_template(property_id: str, data: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        tpl_id = data.get("id") or str(uuid.uuid4())
        items = data.get("items") or DEFAULT_ITEMS
        # Sanitize items (must have key+label)
        clean_items = [
            {"key": (i.get("key") or "").strip(),
             "label": (i.get("label") or "").strip(),
             "section": i.get("section", "general")}
            for i in items if i.get("label")
        ]
        update = {
            "id": tpl_id,
            "property_id": property_id,
            "room_type_id": data.get("room_type_id", ""),
            "name": data.get("name", "Custom checklist"),
            "items": clean_items,
            "active": bool(data.get("active", True)),
            "version": int(data.get("version", 1)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.cleaning_checklist_templates.update_one(
            {"id": tpl_id}, {"$set": update, "$setOnInsert": {"created_at": update["updated_at"]}},
            upsert=True,
        )
        doc = await db.cleaning_checklist_templates.find_one({"id": tpl_id}, {"_id": 0})
        return {"ok": True, "template": doc}

    @router.delete("/cleaning-checklists/{property_id}/templates/{template_id}")
    async def delete_template(property_id: str, template_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.cleaning_checklist_templates.delete_one({"id": template_id, "property_id": property_id})
        return {"ok": True}

    @router.post("/cleaning-checklists/run")
    async def start_run(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping"))):
        property_id = data.get("property_id", "")
        room_id = data.get("room_id", "")
        if not property_id or not room_id:
            raise HTTPException(400, "property_id and room_id required")
        room = await db.room_statuses.find_one({"id": room_id}, {"_id": 0})
        if not room:
            raise HTTPException(404, "Room not found")

        room_type_id = room.get("room_type_id", "")
        # Use room-type-specific template if exists, else property default.
        tpl = await db.cleaning_checklist_templates.find_one(
            {"property_id": property_id, "room_type_id": room_type_id, "active": True}, {"_id": 0}
        ) or await _ensure_default(property_id, "")

        run = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "room_id": room_id,
            "room_number": room.get("room_number", ""),
            "room_type_id": room_type_id,
            "template_id": tpl["id"],
            "template_name": tpl["name"],
            "items": [
                {"key": i["key"], "label": i["label"], "section": i.get("section", "general"),
                 "checked": False, "checked_at": "", "photo_url": "", "note": ""}
                for i in tpl["items"]
            ],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "started_by": current_user.get("name", "Staff"),
            "completed_at": "",
            "duration_min": 0,
            "score_pct": 0,
            "supervisor_passed": False,
            "supervisor_notes": "",
        }
        await db.cleaning_runs.insert_one(dict(run))
        run.pop("_id", None)
        return run

    @router.post("/cleaning-checklists/run/{run_id}/tick")
    async def tick(run_id: str, data: Dict,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping"))):
        key = (data.get("key") or "").strip()
        if not key:
            raise HTTPException(400, "key required")
        run = await db.cleaning_runs.find_one({"id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        items = run.get("items", [])
        found = False
        for it in items:
            if it["key"] == key:
                it["checked"] = bool(data.get("checked", True))
                it["checked_at"] = datetime.now(timezone.utc).isoformat() if it["checked"] else ""
                it["photo_url"] = data.get("photo_url", it.get("photo_url", ""))
                it["note"] = data.get("note", it.get("note", ""))
                found = True
                break
        if not found:
            raise HTTPException(400, f"unknown key {key}")
        await db.cleaning_runs.update_one({"id": run_id}, {"$set": {"items": items}})
        return {"ok": True, "key": key}

    @router.post("/cleaning-checklists/run/{run_id}/complete")
    async def complete(run_id: str, data: Optional[Dict] = None,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping"))):
        run = await db.cleaning_runs.find_one({"id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        items = run.get("items", [])
        if not items:
            raise HTTPException(400, "no items")
        ticked = sum(1 for i in items if i.get("checked"))
        score = round(ticked / len(items) * 100, 1)
        try:
            started = datetime.fromisoformat(run["started_at"])
            duration_min = round((datetime.now(timezone.utc) - started).total_seconds() / 60, 1)
        except Exception:
            duration_min = 0

        update = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by": current_user.get("name", "Staff"),
            "score_pct": score,
            "duration_min": duration_min,
            "supervisor_passed": bool((data or {}).get("supervisor_passed")),
            "supervisor_notes": (data or {}).get("supervisor_notes", ""),
        }
        await db.cleaning_runs.update_one({"id": run_id}, {"$set": update})

        # If full score, auto-flip room to clean.
        if score >= 100:
            await db.room_statuses.update_one(
                {"id": run["room_id"]},
                {"$set": {"status": "clean",
                          "last_cleaned_at": update["completed_at"],
                          "last_cleaned_by": update["completed_by"]}}
            )
        return {"ok": True, "score_pct": score, "duration_min": duration_min, "auto_flipped_to_clean": score >= 100}

    @router.get("/cleaning-checklists/{property_id}/runs")
    async def list_runs(property_id: str, days: int = 7,
                          current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.cleaning_runs.find(
            {"property_id": property_id, "started_at": {"$gte": since}},
            {"_id": 0},
        ).sort("started_at", -1).to_list(200)
        return rows

    @router.get("/cleaning-checklists/{property_id}/stats")
    async def stats(property_id: str, days: int = 30,
                     current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.cleaning_runs.find(
            {"property_id": property_id, "started_at": {"$gte": since}},
            {"_id": 0, "items": 0},
        ).to_list(2000)
        total = len(rows)
        if total == 0:
            return {"total": 0, "completed": 0, "avg_score_pct": 0, "avg_duration_min": 0,
                    "supervisor_pass_rate": 0, "by_cleaner": []}
        completed = [r for r in rows if r.get("completed_at")]
        avg_score = round(sum(r.get("score_pct", 0) for r in completed) / max(1, len(completed)), 1)
        avg_dur = round(sum(r.get("duration_min", 0) for r in completed) / max(1, len(completed)), 1)
        passed = sum(1 for r in completed if r.get("supervisor_passed"))
        # Group by cleaner
        by_cleaner: Dict[str, dict] = {}
        for r in completed:
            who = r.get("completed_by", r.get("started_by", "—"))
            d = by_cleaner.setdefault(who, {"name": who, "runs": 0, "avg_score": 0, "_sum": 0})
            d["runs"] += 1; d["_sum"] += r.get("score_pct", 0)
        cleaners = []
        for d in by_cleaner.values():
            d["avg_score"] = round(d["_sum"] / max(1, d["runs"]), 1)
            d.pop("_sum")
            cleaners.append(d)
        cleaners.sort(key=lambda x: x["runs"], reverse=True)
        return {
            "total": total,
            "completed": len(completed),
            "avg_score_pct": avg_score,
            "avg_duration_min": avg_dur,
            "supervisor_pass_rate": round(passed / max(1, len(completed)) * 100, 1),
            "by_cleaner": cleaners[:20],
        }

    return router
