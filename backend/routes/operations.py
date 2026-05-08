"""
Operations Hub — Reception Dashboard, Routine Templates, Shift Handover, Laundry, Compliance
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import os
import logging

logger = logging.getLogger(__name__)
COMPLIANCE_UPLOAD_DIR = "/app/backend/uploads/compliance"
os.makedirs(COMPLIANCE_UPLOAD_DIR, exist_ok=True)


def create_operations_router(db, require_roles):
    router = APIRouter()

    # ==================== 1. RECEPTION DASHBOARD ====================

    @router.get("/operations/reception/{property_id}")
    async def reception_dashboard(property_id: str, from_date: str = "", to_date: str = "",
                                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        now = datetime.now(timezone.utc)
        if not from_date:
            from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = now.strftime("%Y-%m-%d")

        date_q = {**query, "created_at": {"$gte": from_date, "$lte": to_date + "T23:59:59"}}

        bookings = await db.bookings.find(date_q, {"_id": 0}).sort("created_at", -1).to_list(100)
        checkins = await db.bookings.find({**query, "status": "checked_in", "check_in": {"$gte": from_date, "$lte": to_date}}, {"_id": 0}).to_list(100)
        checkouts = await db.bookings.find({**query, "status": {"$in": ["checked_out", "completed"]}, "check_out": {"$gte": from_date, "$lte": to_date}}, {"_id": 0}).to_list(100)
        cancellations = await db.bookings.find({**query, "status": "cancelled", "created_at": {"$gte": from_date}}, {"_id": 0}).to_list(100)
        routines_run = await db.routine_history.count_documents({**query, "created_at": {"$gte": from_date}})

        return {
            "from_date": from_date, "to_date": to_date,
            "stats": {
                "bookings_created": len(bookings), "check_ins": len(checkins),
                "check_outs": len(checkouts), "cancellations": len(cancellations),
                "routine_runs": routines_run,
            },
            "bookings": [{"guest": b.get("guest_name", ""), "branch": b.get("property_id", ""), "created_by": b.get("created_by", "System"), "created_at": b.get("created_at", "")} for b in bookings[:20]],
            "checkins": [{"guest": b.get("guest_name", ""), "branch": b.get("property_id", ""), "checked_in_by": b.get("checked_in_by", "—"), "checked_in_at": b.get("check_in", "")} for b in checkins[:20]],
            "checkouts": [{"guest": b.get("guest_name", ""), "branch": b.get("property_id", ""), "checked_out_by": b.get("checked_out_by", "—"), "checked_out_at": b.get("check_out", "")} for b in checkouts[:20]],
        }

    # ==================== 2. ROUTINE TEMPLATES ====================

    @router.get("/operations/routine-templates/{property_id}")
    async def list_templates(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"$or": [{"property_id": property_id}, {"property_id": "any"}]}
        docs = await db.routine_templates.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
        return docs

    @router.post("/operations/routine-templates")
    async def create_template(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        template = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", "any"),
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "steps": data.get("steps", []),
            "role": data.get("role", "receptionist"),
            "shift": data.get("shift", "default"),
            "is_active": data.get("is_active", True),
            "version": "1.0",
            "created_by": current_user.get("name", "Staff"),
            "created_at": now, "updated_at": now,
        }
        await db.routine_templates.insert_one(template)
        template.pop("_id", None)
        return template

    @router.put("/operations/routine-templates/{template_id}")
    async def update_template(template_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None); updates.pop("id", None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.routine_templates.update_one({"id": template_id}, {"$set": updates})
        return await db.routine_templates.find_one({"id": template_id}, {"_id": 0})

    @router.delete("/operations/routine-templates/{template_id}")
    async def delete_template(template_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.routine_templates.delete_one({"id": template_id})
        return {"status": "deleted"}

    @router.post("/operations/routine-templates/{template_id}/start")
    async def start_routine(template_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Start a routine run from a template"""
        template = await db.routine_templates.find_one({"id": template_id}, {"_id": 0})
        if not template:
            raise HTTPException(404, "Template not found")
        now = datetime.now(timezone.utc).isoformat()
        run = {
            "id": str(uuid.uuid4()),
            "template_id": template_id, "template_name": template.get("name", ""),
            "property_id": template.get("property_id", ""),
            "shift": template.get("shift", "default"),
            "user": current_user.get("name", "Staff"),
            "status": "in_progress",
            "tasks": [{"step": s, "completed": False, "completed_at": "", "notes": ""} for s in template.get("steps", [])],
            "total_tasks": len(template.get("steps", [])),
            "completed_tasks": 0,
            "started_at": now, "completed_at": "", "created_at": now,
        }
        await db.routine_history.insert_one(run)
        run.pop("_id", None)
        return run

    # ==================== 2b. ROUTINE HISTORY ====================

    @router.get("/operations/routine-history/{property_id}")
    async def list_history(property_id: str, shift: str = "", status: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if shift: query["shift"] = shift
        if status: query["status"] = status
        docs = await db.routine_history.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.put("/operations/routine-history/{run_id}/task/{task_index}")
    async def complete_task(run_id: str, task_index: int, data: Dict,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Mark a task as complete in a routine run"""
        run = await db.routine_history.find_one({"id": run_id}, {"_id": 0})
        if not run:
            raise HTTPException(404, "Run not found")
        tasks = run.get("tasks", [])
        if task_index < 0 or task_index >= len(tasks):
            raise HTTPException(400, "Invalid task index")

        tasks[task_index]["completed"] = data.get("completed", True)
        tasks[task_index]["completed_at"] = datetime.now(timezone.utc).isoformat()
        tasks[task_index]["notes"] = data.get("notes", "")

        completed = sum(1 for t in tasks if t["completed"])
        status = "completed" if completed == len(tasks) else "in_progress"
        updates = {"tasks": tasks, "completed_tasks": completed, "status": status}
        if status == "completed":
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()

        await db.routine_history.update_one({"id": run_id}, {"$set": updates})
        return await db.routine_history.find_one({"id": run_id}, {"_id": 0})

    @router.get("/operations/routine-history/stats/{property_id}")
    async def routine_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        total = await db.routine_history.count_documents(query)
        completed = await db.routine_history.count_documents({**query, "status": "completed"})
        in_progress = await db.routine_history.count_documents({**query, "status": "in_progress"})
        return {"total": total, "completed": completed, "incomplete": in_progress, "completion_rate": round((completed / max(total, 1)) * 100, 1)}

    # ==================== 3. SHIFT HANDOVER (PASS OVER DUTIES) ====================

    @router.get("/operations/handover/{property_id}")
    async def list_handover(property_id: str, note_type: str = "", priority: str = "", status: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if note_type: query["note_type"] = note_type
        if priority: query["priority"] = priority
        if status: query["status"] = status
        docs = await db.shift_handover.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/operations/handover")
    async def create_handover(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        now = datetime.now(timezone.utc).isoformat()
        note = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "note_type": data.get("note_type", "general"),
            "priority": data.get("priority", "normal"),
            "status": "pending",
            "content": data.get("content", ""),
            "owner": data.get("owner", ""),
            "role_target": data.get("role_target", ""),
            "due_date": data.get("due_date", ""),
            "author": current_user.get("name", current_user.get("email", "Staff")),
            "resolved_by": "", "resolved_at": "",
            "created_at": now,
        }
        await db.shift_handover.insert_one(note)
        note.pop("_id", None)
        return note

    @router.put("/operations/handover/{note_id}")
    async def update_handover(note_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        updates.pop("_id", None); updates.pop("id", None)
        if updates.get("status") == "resolved":
            updates["resolved_by"] = current_user.get("name", "Staff")
            updates["resolved_at"] = datetime.now(timezone.utc).isoformat()
        await db.shift_handover.update_one({"id": note_id}, {"$set": updates})
        return await db.shift_handover.find_one({"id": note_id}, {"_id": 0})

    @router.delete("/operations/handover/{note_id}")
    async def delete_handover(note_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.shift_handover.delete_one({"id": note_id})
        return {"status": "deleted"}

    # ==================== 4. LAUNDRY TRACKING ====================

    @router.get("/operations/laundry/{property_id}")
    async def list_laundry(property_id: str, status: str = "",
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if status: query["status"] = status
        docs = await db.laundry_items.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    @router.post("/operations/laundry")
    async def create_laundry(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "room_number": data.get("room_number", ""),
            "guest_name": data.get("guest_name", ""),
            "items": data.get("items", []),
            "total_pieces": data.get("total_pieces", 0),
            "status": "sent",
            "sent_by": current_user.get("name", "Staff"),
            "sent_at": now,
            "returned_at": "", "returned_by": "",
            "notes": data.get("notes", ""),
            "lost_items": [],
            "created_at": now,
        }
        await db.laundry_items.insert_one(item)
        item.pop("_id", None)
        return item

    @router.put("/operations/laundry/{item_id}")
    async def update_laundry(item_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        updates.pop("_id", None); updates.pop("id", None)
        now = datetime.now(timezone.utc).isoformat()
        if updates.get("status") == "returned":
            updates["returned_at"] = now
            updates["returned_by"] = current_user.get("name", "Staff")
        await db.laundry_items.update_one({"id": item_id}, {"$set": updates})
        return await db.laundry_items.find_one({"id": item_id}, {"_id": 0})

    @router.get("/operations/laundry/stats/{property_id}")
    async def laundry_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        total = await db.laundry_items.count_documents(query)
        sent = await db.laundry_items.count_documents({**query, "status": "sent"})
        in_progress = await db.laundry_items.count_documents({**query, "status": "in_progress"})
        returned = await db.laundry_items.count_documents({**query, "status": "returned"})
        pieces_pipeline = [{"$match": query}, {"$group": {"_id": None, "total": {"$sum": "$total_pieces"}}}]
        total_pieces = 0
        async for d in db.laundry_items.aggregate(pieces_pipeline):
            total_pieces = d.get("total", 0)
        return {"total": total, "sent": sent, "in_progress": in_progress, "returned": returned, "total_pieces": total_pieces}

    # ==================== 5. COMPLIANCE CHECKS ====================

    @router.get("/operations/compliance/{property_id}")
    async def list_compliance(property_id: str, check_type: str = "", status: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if check_type: query["check_type"] = check_type
        if status: query["status"] = status
        docs = await db.compliance_checks.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/operations/compliance")
    async def create_compliance(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        check = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "check_type": data.get("check_type", "safety"),
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "checklist": [{"item": i, "passed": None, "notes": ""} for i in data.get("checklist_items", [])],
            "status": "scheduled",
            "scheduled_date": data.get("scheduled_date", ""),
            "frequency": data.get("frequency", "monthly"),
            "inspector": data.get("inspector", ""),
            "result": "",
            "evidence_photos": [],
            "completed_at": "", "completed_by": "",
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.compliance_checks.insert_one(check)
        check.pop("_id", None)
        return check

    @router.put("/operations/compliance/{check_id}")
    async def update_compliance(check_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None); updates.pop("id", None)
        now = datetime.now(timezone.utc).isoformat()
        if updates.get("status") == "completed":
            updates["completed_at"] = now
            updates["completed_by"] = current_user.get("name", "Staff")
            checklist = updates.get("checklist", [])
            if checklist:
                failed = any(c.get("passed") == False for c in checklist)
                updates["result"] = "fail" if failed else "pass"
        await db.compliance_checks.update_one({"id": check_id}, {"$set": updates})
        return await db.compliance_checks.find_one({"id": check_id}, {"_id": 0})

    @router.post("/operations/compliance/upload-evidence/{check_id}")
    async def upload_evidence(check_id: str, file: UploadFile = File(...),
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        check = await db.compliance_checks.find_one({"id": check_id}, {"_id": 0})
        if not check:
            raise HTTPException(404, "Check not found")
        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
        filename = f"{check_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(COMPLIANCE_UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        photo_url = f"/api/uploads/compliance/{filename}"
        photos = check.get("evidence_photos", [])
        photos.append({"url": photo_url, "filename": file.filename, "uploaded_by": current_user.get("name", "Staff"), "uploaded_at": datetime.now(timezone.utc).isoformat()})
        await db.compliance_checks.update_one({"id": check_id}, {"$set": {"evidence_photos": photos}})
        return {"status": "uploaded", "url": photo_url}

    @router.delete("/operations/compliance/{check_id}")
    async def delete_compliance(check_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.compliance_checks.delete_one({"id": check_id})
        return {"status": "deleted"}

    return router
