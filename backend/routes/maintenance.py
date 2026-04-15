"""
Maintenance Management — Advanced module with photos, SLA, costs, comments, recurring tasks
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
import uuid
import os
import logging

logger = logging.getLogger(__name__)
MAINT_UPLOAD_DIR = "/app/backend/uploads/maintenance"
os.makedirs(MAINT_UPLOAD_DIR, exist_ok=True)

# SLA targets in hours
SLA_TARGETS = {
    "critical": 2,
    "high": 8,
    "medium": 24,
    "low": 72,
}

# Auto-assignment rules
CATEGORY_DEPARTMENT = {
    "plumbing": "maintenance",
    "electrical": "maintenance",
    "hvac": "maintenance",
    "furniture": "maintenance",
    "appliance": "maintenance",
    "structural": "maintenance",
    "cleaning": "housekeeping",
    "pest_control": "maintenance",
    "safety": "management",
    "it_network": "management",
    "general": "maintenance",
}


def create_maintenance_router(db, require_roles):
    router = APIRouter()

    # ==================== ISSUES CRUD ====================

    @router.get("/maintenance/issues/{property_id}")
    async def list_issues(property_id: str, status: str = "", priority: str = "",
                          category: str = "", assigned_to: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if status: query["status"] = status
        if priority: query["priority"] = priority
        if category: query["category"] = category
        if assigned_to: query["assigned_to"] = assigned_to
        docs = await db.maintenance_issues.find(query, {"_id": 0}).sort("created_at", -1).to_list(300)
        return docs

    @router.post("/maintenance/issues")
    async def create_issue(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        now = datetime.now(timezone.utc).isoformat()
        priority = data.get("priority", "medium")
        category = data.get("category", "general")

        # Auto-assign department
        dept = CATEGORY_DEPARTMENT.get(category, "maintenance")

        # Calculate SLA deadline
        sla_hours = SLA_TARGETS.get(priority, 24)
        sla_deadline = (datetime.now(timezone.utc) + timedelta(hours=sla_hours)).isoformat()

        issue = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "category": category,
            "priority": priority,
            "status": "open",
            "location": data.get("location", ""),
            "room_number": data.get("room_number", ""),
            "assigned_to": data.get("assigned_to", ""),
            "assigned_department": dept,
            "reported_by": current_user.get("name", current_user.get("email", "Staff")),
            "photos": data.get("photos", []),
            "estimated_cost": 0,
            "actual_cost": 0,
            "cost_notes": "",
            "materials": [],
            "sla_hours": sla_hours,
            "sla_deadline": sla_deadline,
            "sla_breached": False,
            "acknowledged_at": "",
            "started_at": "",
            "resolved_at": "",
            "closed_at": "",
            "resolution_notes": "",
            "comments": [],
            "recurring_id": "",
            "created_at": now,
            "updated_at": now,
        }
        await db.maintenance_issues.insert_one(issue)
        issue.pop("_id", None)
        return issue

    @router.get("/maintenance/issues/detail/{issue_id}")
    async def get_issue(issue_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        doc = await db.maintenance_issues.find_one({"id": issue_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Issue not found")
        return doc

    @router.put("/maintenance/issues/{issue_id}")
    async def update_issue(issue_id: str, updates: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        # Track status transitions
        new_status = updates.get("status")
        if new_status:
            if new_status == "acknowledged":
                updates["acknowledged_at"] = now
            elif new_status == "in_progress":
                updates["started_at"] = now
            elif new_status == "resolved":
                updates["resolved_at"] = now
            elif new_status == "closed":
                updates["closed_at"] = now

        await db.maintenance_issues.update_one({"id": issue_id}, {"$set": updates})
        doc = await db.maintenance_issues.find_one({"id": issue_id}, {"_id": 0})
        return doc

    @router.delete("/maintenance/issues/{issue_id}")
    async def delete_issue(issue_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.maintenance_issues.delete_one({"id": issue_id})
        return {"status": "deleted"}

    # ==================== PHOTO UPLOAD ====================

    @router.post("/maintenance/upload-photo/{issue_id}")
    async def upload_photo(issue_id: str, file: UploadFile = File(...),
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        issue = await db.maintenance_issues.find_one({"id": issue_id}, {"_id": 0})
        if not issue:
            raise HTTPException(404, "Issue not found")

        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
        filename = f"{issue_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(MAINT_UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        photo_url = f"/api/uploads/maintenance/{filename}"
        photos = issue.get("photos", [])
        photos.append({"url": photo_url, "filename": file.filename, "uploaded_by": current_user.get("name", "Staff"), "uploaded_at": datetime.now(timezone.utc).isoformat()})
        await db.maintenance_issues.update_one({"id": issue_id}, {"$set": {"photos": photos}})
        return {"status": "uploaded", "url": photo_url}

    # ==================== COMMENTS ====================

    @router.post("/maintenance/issues/{issue_id}/comment")
    async def add_comment(issue_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        issue = await db.maintenance_issues.find_one({"id": issue_id}, {"_id": 0})
        if not issue:
            raise HTTPException(404, "Issue not found")

        comment = {
            "id": str(uuid.uuid4()),
            "text": data.get("text", ""),
            "author": current_user.get("name", current_user.get("email", "Staff")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        comments = issue.get("comments", [])
        comments.append(comment)
        await db.maintenance_issues.update_one({"id": issue_id}, {"$set": {"comments": comments, "updated_at": datetime.now(timezone.utc).isoformat()}})
        return comment

    # ==================== COST TRACKING ====================

    @router.put("/maintenance/issues/{issue_id}/cost")
    async def update_cost(issue_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        updates = {
            "estimated_cost": data.get("estimated_cost", 0),
            "actual_cost": data.get("actual_cost", 0),
            "cost_notes": data.get("cost_notes", ""),
            "materials": data.get("materials", []),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.maintenance_issues.update_one({"id": issue_id}, {"$set": updates})
        return {"status": "updated"}

    # ==================== STATS & ANALYTICS ====================

    @router.get("/maintenance/stats/{property_id}")
    async def get_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        total = await db.maintenance_issues.count_documents(query)
        open_q = {**query, "status": "open"}
        in_progress_q = {**query, "status": {"$in": ["acknowledged", "in_progress"]}}
        resolved_q = {**query, "status": {"$in": ["resolved", "closed"]}}
        overdue_q = {**query, "sla_breached": True, "status": {"$nin": ["resolved", "closed"]}}

        open_count = await db.maintenance_issues.count_documents(open_q)
        in_progress = await db.maintenance_issues.count_documents(in_progress_q)
        resolved = await db.maintenance_issues.count_documents(resolved_q)
        overdue = await db.maintenance_issues.count_documents(overdue_q)

        # Category breakdown
        pipeline = [{"$match": query}, {"$group": {"_id": "$category", "count": {"$sum": 1}}}]
        cat_breakdown = {}
        async for doc in db.maintenance_issues.aggregate(pipeline):
            cat_breakdown[doc["_id"]] = doc["count"]

        # Priority breakdown
        pipeline2 = [{"$match": query}, {"$group": {"_id": "$priority", "count": {"$sum": 1}}}]
        pri_breakdown = {}
        async for doc in db.maintenance_issues.aggregate(pipeline2):
            pri_breakdown[doc["_id"]] = doc["count"]

        # Total costs
        cost_pipeline = [{"$match": query}, {"$group": {"_id": None, "total_estimated": {"$sum": "$estimated_cost"}, "total_actual": {"$sum": "$actual_cost"}}}]
        cost_data = {"total_estimated": 0, "total_actual": 0}
        async for doc in db.maintenance_issues.aggregate(cost_pipeline):
            cost_data = {"total_estimated": doc.get("total_estimated", 0), "total_actual": doc.get("total_actual", 0)}

        return {
            "total": total, "open": open_count, "in_progress": in_progress,
            "resolved": resolved, "overdue": overdue,
            "by_category": cat_breakdown, "by_priority": pri_breakdown,
            "costs": cost_data,
        }

    # ==================== SLA CHECK ====================

    @router.post("/maintenance/check-sla/{property_id}")
    async def check_sla(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Check and mark SLA breaches"""
        now = datetime.now(timezone.utc).isoformat()
        query = {"status": {"$in": ["open", "acknowledged", "in_progress"]}, "sla_breached": False}
        if property_id != "all":
            query["property_id"] = property_id

        docs = await db.maintenance_issues.find(query, {"_id": 0}).to_list(500)
        breached = 0
        for doc in docs:
            if doc.get("sla_deadline") and doc["sla_deadline"] < now:
                await db.maintenance_issues.update_one({"id": doc["id"]}, {"$set": {"sla_breached": True}})
                breached += 1
        return {"checked": len(docs), "newly_breached": breached}

    # ==================== RECURRING MAINTENANCE ====================

    @router.get("/maintenance/recurring/{property_id}")
    async def list_recurring(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.recurring_maintenance.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/maintenance/recurring")
    async def create_recurring(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        schedule = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "category": data.get("category", "general"),
            "priority": data.get("priority", "medium"),
            "location": data.get("location", ""),
            "assigned_to": data.get("assigned_to", ""),
            "frequency": data.get("frequency", "monthly"),  # daily, weekly, monthly, quarterly, yearly
            "day_of_week": data.get("day_of_week", ""),  # for weekly
            "day_of_month": data.get("day_of_month", 1),  # for monthly
            "is_active": True,
            "last_generated": "",
            "next_due": data.get("next_due", now),
            "created_by": current_user.get("name", "Staff"),
            "created_at": now,
        }
        await db.recurring_maintenance.insert_one(schedule)
        schedule.pop("_id", None)
        return schedule

    @router.put("/maintenance/recurring/{schedule_id}")
    async def update_recurring(schedule_id: str, updates: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.recurring_maintenance.update_one({"id": schedule_id}, {"$set": updates})
        doc = await db.recurring_maintenance.find_one({"id": schedule_id}, {"_id": 0})
        return doc

    @router.delete("/maintenance/recurring/{schedule_id}")
    async def delete_recurring(schedule_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.recurring_maintenance.delete_one({"id": schedule_id})
        return {"status": "deleted"}

    @router.post("/maintenance/recurring/generate/{property_id}")
    async def generate_recurring_tasks(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Generate maintenance issues from recurring schedules that are due"""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        query = {"is_active": True, "next_due": {"$lte": now_str}}
        if property_id != "all":
            query["property_id"] = property_id

        schedules = await db.recurring_maintenance.find(query, {"_id": 0}).to_list(100)
        created = 0
        for sched in schedules:
            # Create issue
            sla_hours = SLA_TARGETS.get(sched.get("priority", "medium"), 24)
            issue = {
                "id": str(uuid.uuid4()),
                "property_id": sched["property_id"],
                "title": f"[Scheduled] {sched['title']}",
                "description": sched.get("description", ""),
                "category": sched.get("category", "general"),
                "priority": sched.get("priority", "medium"),
                "status": "open",
                "location": sched.get("location", ""),
                "room_number": "",
                "assigned_to": sched.get("assigned_to", ""),
                "assigned_department": CATEGORY_DEPARTMENT.get(sched.get("category", "general"), "maintenance"),
                "reported_by": "System (Recurring)",
                "photos": [], "estimated_cost": 0, "actual_cost": 0,
                "cost_notes": "", "materials": [],
                "sla_hours": sla_hours,
                "sla_deadline": (now + timedelta(hours=sla_hours)).isoformat(),
                "sla_breached": False,
                "acknowledged_at": "", "started_at": "", "resolved_at": "", "closed_at": "",
                "resolution_notes": "", "comments": [],
                "recurring_id": sched["id"],
                "created_at": now_str, "updated_at": now_str,
            }
            await db.maintenance_issues.insert_one(issue)
            created += 1

            # Calculate next due
            freq = sched.get("frequency", "monthly")
            if freq == "daily":
                next_due = now + timedelta(days=1)
            elif freq == "weekly":
                next_due = now + timedelta(weeks=1)
            elif freq == "monthly":
                next_due = now + timedelta(days=30)
            elif freq == "quarterly":
                next_due = now + timedelta(days=90)
            else:
                next_due = now + timedelta(days=365)

            await db.recurring_maintenance.update_one(
                {"id": sched["id"]},
                {"$set": {"last_generated": now_str, "next_due": next_due.isoformat()}}
            )

        return {"generated": created, "schedules_checked": len(schedules)}

    # ==================== TEAM MEMBERS ====================

    @router.get("/maintenance/team/{property_id}")
    async def list_team(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.maintenance_team.find(query, {"_id": 0}).sort("name", 1).to_list(100)
        # Attach workload (open issues count)
        for d in docs:
            d["open_issues"] = await db.maintenance_issues.count_documents({
                "assigned_to": d["name"], "status": {"$in": ["open", "acknowledged", "in_progress"]}
            })
            d["total_resolved"] = await db.maintenance_issues.count_documents({
                "assigned_to": d["name"], "status": {"$in": ["resolved", "closed"]}
            })
        return docs

    @router.post("/maintenance/team")
    async def add_team_member(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        member = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "name": data.get("name", ""),
            "role": data.get("role", "technician"),
            "phone": data.get("phone", ""),
            "email": data.get("email", ""),
            "specialities": data.get("specialities", []),
            "is_active": True,
            "type": "internal",
            "created_at": now,
        }
        await db.maintenance_team.insert_one(member)
        member.pop("_id", None)
        return member

    @router.put("/maintenance/team/{member_id}")
    async def update_team_member(member_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.maintenance_team.update_one({"id": member_id}, {"$set": updates})
        doc = await db.maintenance_team.find_one({"id": member_id}, {"_id": 0})
        return doc

    @router.delete("/maintenance/team/{member_id}")
    async def delete_team_member(member_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.maintenance_team.delete_one({"id": member_id})
        return {"status": "deleted"}

    # ==================== EXTERNAL VENDORS ====================

    @router.get("/maintenance/vendors/{property_id}")
    async def list_vendors(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        docs = await db.maintenance_vendors.find(query, {"_id": 0}).sort("company_name", 1).to_list(100)
        # Attach stats
        for d in docs:
            d["open_issues"] = await db.maintenance_issues.count_documents({
                "assigned_to": d["company_name"], "status": {"$in": ["open", "acknowledged", "in_progress"]}
            })
            d["total_resolved"] = await db.maintenance_issues.count_documents({
                "assigned_to": d["company_name"], "status": {"$in": ["resolved", "closed"]}
            })
            # Total cost from issues assigned to this vendor
            cost_pipeline = [
                {"$match": {"assigned_to": d["company_name"]}},
                {"$group": {"_id": None, "total": {"$sum": "$actual_cost"}}}
            ]
            total_cost = 0
            async for doc in db.maintenance_issues.aggregate(cost_pipeline):
                total_cost = doc.get("total", 0)
            d["total_cost"] = total_cost
        return docs

    @router.post("/maintenance/vendors")
    async def add_vendor(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        vendor = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "company_name": data.get("company_name", ""),
            "contact_person": data.get("contact_person", ""),
            "phone": data.get("phone", ""),
            "email": data.get("email", ""),
            "specialities": data.get("specialities", []),
            "hourly_rate": data.get("hourly_rate", 0),
            "currency": data.get("currency", "GBP"),
            "notes": data.get("notes", ""),
            "rating": 0,
            "is_active": True,
            "type": "external",
            "created_at": now,
        }
        await db.maintenance_vendors.insert_one(vendor)
        vendor.pop("_id", None)
        return vendor

    @router.put("/maintenance/vendors/{vendor_id}")
    async def update_vendor(vendor_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.maintenance_vendors.update_one({"id": vendor_id}, {"$set": updates})
        doc = await db.maintenance_vendors.find_one({"id": vendor_id}, {"_id": 0})
        return doc

    @router.delete("/maintenance/vendors/{vendor_id}")
    async def delete_vendor(vendor_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.maintenance_vendors.delete_one({"id": vendor_id})
        return {"status": "deleted"}

    # ==================== ASSIGNEES LIST (combined team + vendors) ====================

    @router.get("/maintenance/assignees/{property_id}")
    async def list_assignees(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Returns combined list of internal team and external vendors for assignment dropdowns"""
        query = {} if property_id == "all" else {"property_id": property_id}
        team = await db.maintenance_team.find({**query, "is_active": True}, {"_id": 0}).to_list(100)
        vendors = await db.maintenance_vendors.find({**query, "is_active": True}, {"_id": 0}).to_list(100)

        assignees = []
        for t in team:
            open_count = await db.maintenance_issues.count_documents({"assigned_to": t["name"], "status": {"$in": ["open", "acknowledged", "in_progress"]}})
            assignees.append({"name": t["name"], "type": "internal", "role": t.get("role", ""), "specialities": t.get("specialities", []), "open_issues": open_count})
        for v in vendors:
            open_count = await db.maintenance_issues.count_documents({"assigned_to": v["company_name"], "status": {"$in": ["open", "acknowledged", "in_progress"]}})
            assignees.append({"name": v["company_name"], "type": "external", "role": "vendor", "specialities": v.get("specialities", []), "hourly_rate": v.get("hourly_rate", 0), "open_issues": open_count})
        return assignees

    return router
