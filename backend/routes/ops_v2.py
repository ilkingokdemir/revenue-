"""
Operations Ops v2 — Maintenance work-order workflow + Linen PAR tracking + HK Inspection checklist.

Maintenance v2: corrective work orders with state machine:
  reported → assigned → in_progress → completed → verified
  Photo evidence at each stage, SLA target, technician stopwatch.

Linen PAR: par-level stock tracking per outlet. Clean → In-Use → Dirty → Washing → Clean cycle.
Auto-flags below-par when clean stock drops below threshold.

Inspection: HK supervisor post-cleaning checklist with room pass/fail + photo proof.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from pydantic import BaseModel
import uuid
import logging

logger = logging.getLogger(__name__)


# ========== MODELS ==========

class WorkOrder(BaseModel):
    id: Optional[str] = None
    property_id: str
    title: str
    description: Optional[str] = ""
    location: Optional[str] = None
    room_id: Optional[str] = None
    priority: str = "normal"     # low | normal | high | critical
    category: str = "general"    # plumbing | electrical | hvac | general | it | safety
    status: str = "reported"
    reported_by: Optional[str] = None
    assigned_to: Optional[str] = None
    photos_before: List[str] = []
    photos_after: List[str] = []


class WorkOrderAction(BaseModel):
    action: str                  # assign | start | pause | resume | complete | verify | reopen
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    photos: Optional[List[str]] = None


class LinenItem(BaseModel):
    property_id: str
    item_type: str               # bed_sheet | towel_bath | towel_face | pillowcase | duvet | tablecloth
    par_level: int               # target on-hand clean
    reorder_threshold: int
    unit_cost: float = 0


class LinenCycle(BaseModel):
    property_id: str
    item_type: str
    movement: str                # checkout_to_dirty | dirty_to_washing | washing_to_clean | lost_or_damaged
    qty: int


class Inspection(BaseModel):
    property_id: str
    room_id: str
    hk_attendant: Optional[str] = None
    supervisor: Optional[str] = None
    checks: List[Dict]           # [{name, pass:bool, notes, photo_b64}]
    overall_pass: bool
    notes: Optional[str] = None


DEFAULT_INSPECTION_CHECKS = [
    "Bed made and linen fresh",
    "Bathroom cleaned and stocked",
    "Trash bins empty",
    "Floor vacuumed/mopped",
    "Minibar restocked",
    "TV remote + batteries working",
    "All lights working",
    "A/C / heater functional",
    "Welcome amenity in place",
    "Windows clean / curtains drawn",
]


def create_ops_v2_router(db, require_roles):
    router = APIRouter()

    # ========== MAINTENANCE WORK ORDERS ==========

    @router.get("/ops-v2/workorders/{property_id}")
    async def list_workorders(property_id: str, status: Optional[str] = None,
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance"))):
        q = {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.maintenance_workorders.find(q, {"_id": 0}).sort("reported_at", -1).to_list(500)
        # Counters
        all_rows = rows if not status else await db.maintenance_workorders.find(
            {"property_id": property_id}, {"_id": 0, "status": 1, "priority": 1}
        ).to_list(2000)
        counters = {"reported": 0, "assigned": 0, "in_progress": 0, "completed": 0, "verified": 0}
        critical_open = 0
        for r in all_rows:
            s = r.get("status", "reported")
            if s in counters:
                counters[s] += 1
            if r.get("priority") == "critical" and s not in ("completed", "verified"):
                critical_open += 1
        return {"rows": rows, "counters": counters, "critical_open": critical_open}

    @router.post("/ops-v2/workorders")
    async def create_workorder(wo: WorkOrder,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeping", "maintenance"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = wo.dict()
        doc["id"] = str(uuid.uuid4())
        doc["status"] = "reported"
        doc["reported_at"] = now
        doc["reported_by"] = current_user.get("email")
        doc["events"] = [{"action": "reported", "at": now, "by": current_user.get("email")}]
        await db.maintenance_workorders.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    @router.post("/ops-v2/workorders/{wo_id}/action")
    async def workorder_action(wo_id: str, act: WorkOrderAction,
                               current_user: dict = Depends(require_roles("admin", "manager", "maintenance", "housekeeping"))):
        wo = await db.maintenance_workorders.find_one({"id": wo_id}, {"_id": 0})
        if not wo:
            raise HTTPException(404, "Work order not found")

        valid = {"assign", "start", "pause", "resume", "complete", "verify", "reopen"}
        if act.action not in valid:
            raise HTTPException(400, f"Invalid action. Must be {valid}")

        now = datetime.now(timezone.utc).isoformat()
        new_status_map = {
            "assign": "assigned", "start": "in_progress", "pause": "paused",
            "resume": "in_progress", "complete": "completed",
            "verify": "verified", "reopen": "reported",
        }
        new_status = new_status_map[act.action]
        patch = {"status": new_status, f"{act.action}d_at": now, f"{act.action}d_by": current_user.get("email")}
        if act.assigned_to and act.action == "assign":
            patch["assigned_to"] = act.assigned_to
        if act.photos:
            if act.action in ("start",):
                patch["photos_before"] = list(wo.get("photos_before", [])) + list(act.photos)
            elif act.action in ("complete", "verify"):
                patch["photos_after"] = list(wo.get("photos_after", [])) + list(act.photos)

        await db.maintenance_workorders.update_one(
            {"id": wo_id},
            {"$set": patch,
             "$push": {"events": {"action": act.action, "at": now, "by": current_user.get("email"), "notes": act.notes}}}
        )
        return {"id": wo_id, "status": new_status, "at": now}

    # ========== LINEN PAR TRACKING ==========

    @router.get("/ops-v2/linen/{property_id}")
    async def linen_overview(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        items = await db.linen_items.find({"property_id": property_id}, {"_id": 0}).to_list(100)
        counts_rows = await db.linen_stock.find({"property_id": property_id}, {"_id": 0}).to_list(500)
        # Index counts by item_type
        by_type = {}
        for c in counts_rows:
            by_type.setdefault(c["item_type"], {"clean": 0, "dirty": 0, "washing": 0, "in_use": 0, "lost": 0})
            by_type[c["item_type"]][c.get("state", "clean")] = c.get("qty", 0)

        # Merge with par levels
        rows = []
        low_par = []
        for it in items:
            states = by_type.get(it["item_type"], {"clean": 0, "dirty": 0, "washing": 0, "in_use": 0, "lost": 0})
            total = sum(states.values())
            below = states.get("clean", 0) < (it.get("reorder_threshold") or it.get("par_level") * 0.3)
            r = {
                **it,
                "states": states,
                "total": total,
                "clean": states.get("clean", 0),
                "dirty": states.get("dirty", 0),
                "washing": states.get("washing", 0),
                "in_use": states.get("in_use", 0),
                "lost": states.get("lost", 0),
                "below_par": below,
            }
            rows.append(r)
            if below:
                low_par.append(r)
        return {"items": rows, "low_par_count": len(low_par), "low_par": low_par}

    @router.post("/ops-v2/linen/item")
    async def upsert_linen_item(item: LinenItem,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = item.dict()
        doc["updated_at"] = now
        await db.linen_items.update_one(
            {"property_id": item.property_id, "item_type": item.item_type},
            {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
            upsert=True,
        )
        return {"updated": True}

    @router.post("/ops-v2/linen/cycle")
    async def cycle_linen(cycle: LinenCycle,
                          current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        now = datetime.now(timezone.utc).isoformat()
        transitions = {
            "checkout_to_dirty":  ("in_use", "dirty"),
            "dirty_to_washing":   ("dirty", "washing"),
            "washing_to_clean":   ("washing", "clean"),
            "clean_to_in_use":    ("clean", "in_use"),
            "lost_or_damaged":    ("dirty", "lost"),
        }
        if cycle.movement not in transitions:
            raise HTTPException(400, f"Invalid movement. Valid: {list(transitions.keys())}")
        from_state, to_state = transitions[cycle.movement]

        # Decrement from
        await db.linen_stock.update_one(
            {"property_id": cycle.property_id, "item_type": cycle.item_type, "state": from_state},
            {"$inc": {"qty": -cycle.qty}, "$set": {"updated_at": now}, "$setOnInsert": {"id": str(uuid.uuid4())}},
            upsert=True,
        )
        # Increment to
        await db.linen_stock.update_one(
            {"property_id": cycle.property_id, "item_type": cycle.item_type, "state": to_state},
            {"$inc": {"qty": cycle.qty}, "$set": {"updated_at": now}, "$setOnInsert": {"id": str(uuid.uuid4())}},
            upsert=True,
        )
        # Log
        await db.linen_cycles.insert_one({
            "id": str(uuid.uuid4()),
            "property_id": cycle.property_id,
            "item_type": cycle.item_type,
            "movement": cycle.movement,
            "qty": cycle.qty,
            "from_state": from_state,
            "to_state": to_state,
            "at": now,
            "by": current_user.get("email"),
        })
        return {"movement": cycle.movement, "qty": cycle.qty, "from": from_state, "to": to_state}

    @router.post("/ops-v2/linen/{property_id}/seed-defaults")
    async def seed_linen(property_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.linen_items.count_documents({"property_id": property_id})
        if existing > 0:
            return {"seeded": 0, "note": f"{existing} item(s) already configured"}
        now = datetime.now(timezone.utc).isoformat()
        defaults = [
            {"id": str(uuid.uuid4()), "property_id": property_id, "item_type": "bed_sheet",
             "par_level": 100, "reorder_threshold": 40, "unit_cost": 12, "created_at": now},
            {"id": str(uuid.uuid4()), "property_id": property_id, "item_type": "towel_bath",
             "par_level": 120, "reorder_threshold": 50, "unit_cost": 9, "created_at": now},
            {"id": str(uuid.uuid4()), "property_id": property_id, "item_type": "towel_face",
             "par_level": 150, "reorder_threshold": 60, "unit_cost": 4, "created_at": now},
            {"id": str(uuid.uuid4()), "property_id": property_id, "item_type": "pillowcase",
             "par_level": 200, "reorder_threshold": 80, "unit_cost": 3, "created_at": now},
            {"id": str(uuid.uuid4()), "property_id": property_id, "item_type": "duvet",
             "par_level": 60,  "reorder_threshold": 20, "unit_cost": 40, "created_at": now},
        ]
        await db.linen_items.insert_many(defaults)
        # Seed starting stock — put par at clean
        stock_docs = [{
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "item_type": d["item_type"],
            "state": "clean",
            "qty": d["par_level"],
            "updated_at": now,
        } for d in defaults]
        await db.linen_stock.insert_many(stock_docs)
        return {"seeded": len(defaults)}

    # ========== HK INSPECTION ==========

    @router.get("/ops-v2/inspection/template")
    async def inspection_template(current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        return {"default_checks": DEFAULT_INSPECTION_CHECKS}

    @router.post("/ops-v2/inspection")
    async def submit_inspection(insp: Inspection,
                                current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = insp.dict()
        doc["id"] = str(uuid.uuid4())
        doc["inspected_at"] = now
        doc["inspected_by"] = current_user.get("email")
        failed = sum(1 for c in insp.checks if not c.get("pass", True))
        doc["failed_count"] = failed
        doc["passed_count"] = len(insp.checks) - failed
        await db.inspections.insert_one(doc)

        # Auto-create work orders for failed items with photos
        wos_created = []
        for c in insp.checks:
            if not c.get("pass", True):
                wo_doc = {
                    "id": str(uuid.uuid4()),
                    "property_id": insp.property_id,
                    "title": f"Inspection fail: {c.get('name','check')}",
                    "description": c.get("notes", ""),
                    "room_id": insp.room_id,
                    "priority": "high",
                    "category": "housekeeping",
                    "status": "reported",
                    "reported_at": now,
                    "reported_by": current_user.get("email"),
                    "photos_before": [c["photo_b64"]] if c.get("photo_b64") else [],
                    "events": [{"action": "reported", "at": now, "by": current_user.get("email"), "notes": "Auto from inspection"}],
                    "from_inspection": doc["id"],
                }
                await db.maintenance_workorders.insert_one(wo_doc)
                wos_created.append(wo_doc["id"])

        return {
            "id": doc["id"],
            "passed_count": doc["passed_count"],
            "failed_count": failed,
            "overall_pass": insp.overall_pass,
            "workorders_created": wos_created,
        }

    @router.get("/ops-v2/inspections/{property_id}")
    async def list_inspections(property_id: str, limit: int = 50,
                               current_user: dict = Depends(require_roles("admin", "manager", "housekeeping"))):
        rows = await db.inspections.find({"property_id": property_id}, {"_id": 0}).sort("inspected_at", -1).limit(limit).to_list(limit)
        total = len(rows)
        failed = sum(1 for r in rows if not r.get("overall_pass"))
        return {"rows": rows, "total": total, "failed": failed, "pass_rate": round((total - failed) / total * 100, 1) if total else 0}

    return router
