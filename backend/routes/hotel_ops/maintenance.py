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

# Status flow: open → acknowledged → in_progress → resolved → verified → closed
# "verified" is a manager quality-check step between resolved and closed
VALID_STATUSES = ["open", "acknowledged", "in_progress", "resolved", "verified", "closed"]

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
                          category: str = "", assigned_to: str = "", department: str = "",
                          asset_id: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        if status: query["status"] = status
        if priority: query["priority"] = priority
        if category: query["category"] = category
        if assigned_to: query["assigned_to"] = assigned_to
        if department: query["assigned_department"] = department
        if asset_id: query["asset_id"] = asset_id
        docs = await db.maintenance_issues.find(query, {"_id": 0}).sort("created_at", -1).to_list(300)
        # Compute duration_hours for resolved issues (started_at → resolved_at)
        for d in docs:
            if d.get("resolved_at") and d.get("started_at"):
                try:
                    delta = datetime.fromisoformat(d["resolved_at"]) - datetime.fromisoformat(d["started_at"])
                    d["duration_hours"] = round(delta.total_seconds() / 3600, 2)
                except Exception:
                    d["duration_hours"] = None
            elif d.get("resolved_at") and d.get("created_at"):
                try:
                    delta = datetime.fromisoformat(d["resolved_at"]) - datetime.fromisoformat(d["created_at"])
                    d["duration_hours"] = round(delta.total_seconds() / 3600, 2)
                except Exception:
                    d["duration_hours"] = None
        return docs

    @router.post("/maintenance/issues")
    async def create_issue(data: Dict, current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper"))):
        now = datetime.now(timezone.utc).isoformat()
        priority = data.get("priority", "medium")
        category = data.get("category", "general")

        # Auto-assign department (explicit override wins)
        dept = data.get("assigned_department") or CATEGORY_DEPARTMENT.get(category, "maintenance")

        # Calculate SLA deadline
        sla_hours = SLA_TARGETS.get(priority, 24)
        sla_deadline = (datetime.now(timezone.utc) + timedelta(hours=sla_hours)).isoformat()

        reporter_dept = current_user.get("department", "") or ""
        issue = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id", ""),
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "category": category,
            "priority": priority,
            "priority_override": int(data.get("priority_override") or 0),
            "status": "open",
            "location": data.get("location", ""),
            "room_number": data.get("room_number", ""),
            "room_id": data.get("room_id", ""),
            "asset_id": data.get("asset_id", ""),
            "asset_name": data.get("asset_name", ""),
            "assigned_to": data.get("assigned_to", ""),
            "assigned_department": dept,
            "reported_by": current_user.get("name", current_user.get("email", "Staff")),
            "reported_by_email": current_user.get("email", ""),
            "reported_by_department": reporter_dept,
            "photos_before": data.get("photos_before", []),
            "photos_after": [],
            "estimated_cost": 0,
            "actual_cost": 0,
            "cost_notes": "",
            "materials": [],
            "sla_hours": sla_hours,
            "sla_deadline": sla_deadline,
            "sla_breached": False,
            "acknowledged_at": "",
            "acknowledged_by": "",
            "started_at": "",
            "started_by": "",
            "resolved_at": "",
            "resolved_by": "",
            "verified_at": "",
            "verified_by": "",
            "verification_notes": "",
            "closed_at": "",
            "closed_by": "",
            "resolution_notes": "",
            "comments": [],
            "timeline": [
                {"action": "created", "by": current_user.get("name", current_user.get("email", "Staff")),
                 "at": now, "detail": f"Issue reported: {data.get('title', '')}",
                 "department": reporter_dept}
            ],
            "recurring_id": "",
            "room_blocked": False,
            "created_at": now,
            "updated_at": now,
        }
        await db.maintenance_issues.insert_one(issue)
        issue.pop("_id", None)

        # Auto-block room if critical issue targets a specific room
        if priority == "critical" and issue.get("room_id"):
            try:
                await db.rooms.update_one(
                    {"id": issue["room_id"]},
                    {"$set": {"status": "out_of_order",
                              "ooo_reason": f"Maintenance #{issue['id'][:8]} · {issue['title']}",
                              "ooo_issue_id": issue["id"],
                              "ooo_since": now}}
                )
                await db.maintenance_issues.update_one({"id": issue["id"]}, {"$set": {"room_blocked": True}})
                issue["room_blocked"] = True
            except Exception as ex:
                logger.warning(f"Room auto-block failed: {ex}")
        return issue

    @router.get("/maintenance/issues/detail/{issue_id}")
    async def get_issue(issue_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper"))):
        doc = await db.maintenance_issues.find_one({"id": issue_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Issue not found")
        # duration
        if doc.get("resolved_at") and doc.get("started_at"):
            try:
                delta = datetime.fromisoformat(doc["resolved_at"]) - datetime.fromisoformat(doc["started_at"])
                doc["duration_hours"] = round(delta.total_seconds() / 3600, 2)
            except Exception:
                pass
        return doc

    @router.get("/maintenance/issues/by-asset/{asset_id}")
    async def list_issues_by_asset(asset_id: str,
                                   current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper"))):
        """Return full issue history for an asset — powers MTBF/MTTR analytics."""
        docs = await db.maintenance_issues.find({"asset_id": asset_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
        durations = []
        resolved_count = 0
        for d in docs:
            if d.get("resolved_at") and d.get("started_at"):
                try:
                    delta = datetime.fromisoformat(d["resolved_at"]) - datetime.fromisoformat(d["started_at"])
                    hrs = round(delta.total_seconds() / 3600, 2)
                    d["duration_hours"] = hrs
                    durations.append(hrs)
                    resolved_count += 1
                except Exception:
                    pass
        mttr = round(sum(durations) / len(durations), 2) if durations else None
        # MTBF: avg days between consecutive issue created_at
        sorted_dates = sorted([d["created_at"] for d in docs if d.get("created_at")])
        gaps = []
        for i in range(1, len(sorted_dates)):
            try:
                g = (datetime.fromisoformat(sorted_dates[i]) - datetime.fromisoformat(sorted_dates[i - 1])).total_seconds() / 86400
                gaps.append(g)
            except Exception:
                pass
        mtbf_days = round(sum(gaps) / len(gaps), 1) if gaps else None
        return {"issues": docs, "count": len(docs), "resolved_count": resolved_count,
                "mttr_hours": mttr, "mtbf_days": mtbf_days}

    @router.put("/maintenance/issues/{issue_id}")
    async def update_issue(issue_id: str, updates: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now
        user_name = current_user.get("name", current_user.get("email", "Staff"))

        # Build timeline entry for status changes
        new_status = updates.get("status")
        timeline_entry = None
        if new_status:
            if new_status == "acknowledged":
                updates["acknowledged_at"] = now
                updates["acknowledged_by"] = user_name
                timeline_entry = {"action": "acknowledged", "by": user_name, "at": now, "detail": "Issue acknowledged"}
            elif new_status == "in_progress":
                updates["started_at"] = now
                updates["started_by"] = user_name
                timeline_entry = {"action": "started", "by": user_name, "at": now, "detail": "Work started"}
            elif new_status == "resolved":
                updates["resolved_at"] = now
                updates["resolved_by"] = user_name
                timeline_entry = {"action": "resolved", "by": user_name, "at": now, "detail": updates.get("resolution_notes", "Issue resolved")}
            elif new_status == "verified":
                updates["verified_at"] = now
                updates["verified_by"] = user_name
                timeline_entry = {"action": "verified", "by": user_name, "at": now, "detail": updates.get("verification_notes", "Work quality verified")}
            elif new_status == "closed":
                updates["closed_at"] = now
                updates["closed_by"] = user_name
                timeline_entry = {"action": "closed", "by": user_name, "at": now, "detail": "Issue closed"}

        # Track assignment changes
        new_assigned = updates.get("assigned_to")
        if new_assigned is not None:
            issue_before = await db.maintenance_issues.find_one({"id": issue_id}, {"_id": 0})
            old_assigned = (issue_before or {}).get("assigned_to", "")
            if new_assigned != old_assigned:
                timeline_entry = {"action": "assigned", "by": user_name, "at": now, "detail": f"Assigned to {new_assigned}" if new_assigned else "Unassigned"}

        # Append timeline
        if timeline_entry:
            issue_doc = await db.maintenance_issues.find_one({"id": issue_id}, {"_id": 0})
            timeline = (issue_doc or {}).get("timeline", [])
            timeline.append(timeline_entry)
            updates["timeline"] = timeline

        await db.maintenance_issues.update_one({"id": issue_id}, {"$set": updates})
        doc = await db.maintenance_issues.find_one({"id": issue_id}, {"_id": 0})
        if doc is None:
            raise HTTPException(status_code=404, detail="Arıza kaydı bulunamadı")

        # Auto-unblock room when issue is resolved or closed
        if new_status in ("resolved", "verified", "closed") and doc and doc.get("room_blocked") and doc.get("room_id"):
            try:
                await db.rooms.update_one(
                    {"id": doc["room_id"], "ooo_issue_id": issue_id},
                    {"$set": {"status": "dirty", "ooo_reason": "", "ooo_issue_id": "", "ooo_since": ""}}
                )
                await db.maintenance_issues.update_one({"id": issue_id}, {"$set": {"room_blocked": False}})
                doc["room_blocked"] = False
            except Exception as ex:
                logger.warning(f"Room auto-unblock failed: {ex}")

        # Compute duration if resolved
        if doc.get("resolved_at") and doc.get("started_at"):
            try:
                delta = datetime.fromisoformat(doc["resolved_at"]) - datetime.fromisoformat(doc["started_at"])
                doc["duration_hours"] = round(delta.total_seconds() / 3600, 2)
            except Exception:
                pass
        return doc

    @router.delete("/maintenance/issues/{issue_id}")
    async def delete_issue(issue_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.maintenance_issues.delete_one({"id": issue_id})
        return {"status": "deleted"}

    # ==================== PHOTO UPLOAD ====================

    @router.post("/maintenance/upload-photo/{issue_id}")
    async def upload_photo(issue_id: str, file: UploadFile = File(...), photo_type: str = Form("before"),
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper"))):
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
        photo_entry = {"url": photo_url, "filename": file.filename, "uploaded_by": current_user.get("name", "Staff"), "uploaded_at": datetime.now(timezone.utc).isoformat(), "type": photo_type}

        # Add to before or after list
        field = "photos_before" if photo_type == "before" else "photos_after"
        photos = issue.get(field, [])
        photos.append(photo_entry)

        # Also add timeline entry
        timeline = issue.get("timeline", [])
        timeline.append({"action": "photo_uploaded", "by": current_user.get("name", "Staff"), "at": datetime.now(timezone.utc).isoformat(), "detail": f"{photo_type.capitalize()} photo uploaded: {file.filename}"})

        await db.maintenance_issues.update_one({"id": issue_id}, {"$set": {field: photos, "timeline": timeline}})
        return {"status": "uploaded", "url": photo_url, "type": photo_type}

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
        timeline = issue.get("timeline", [])
        timeline.append({"action": "comment", "by": comment["author"], "at": comment["created_at"], "detail": data.get("text", "")[:100]})
        await db.maintenance_issues.update_one({"id": issue_id}, {"$set": {"comments": comments, "timeline": timeline, "updated_at": datetime.now(timezone.utc).isoformat()}})
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
    async def get_stats(property_id: str, current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "housekeeper"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        total = await db.maintenance_issues.count_documents(query)
        open_q = {**query, "status": "open"}
        in_progress_q = {**query, "status": {"$in": ["acknowledged", "in_progress"]}}
        resolved_q = {**query, "status": {"$in": ["resolved", "verified", "closed"]}}
        overdue_q = {**query, "sla_breached": True, "status": {"$nin": ["resolved", "verified", "closed"]}}

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

        # Department breakdown + Workload by assignee
        dept_pipeline = [{"$match": query}, {"$group": {"_id": "$assigned_department", "count": {"$sum": 1}}}]
        dept_breakdown = {}
        async for doc in db.maintenance_issues.aggregate(dept_pipeline):
            dept_breakdown[doc["_id"] or "unassigned"] = doc["count"]

        workload_pipeline = [
            {"$match": {**query, "status": {"$nin": ["resolved", "verified", "closed"]}}},
            {"$group": {"_id": "$assigned_to", "open": {"$sum": 1}}},
            {"$sort": {"open": -1}}, {"$limit": 15},
        ]
        workload = []
        async for doc in db.maintenance_issues.aggregate(workload_pipeline):
            workload.append({"assignee": doc["_id"] or "Unassigned", "open": doc["open"]})

        # MTTR — avg across all resolved issues
        resolved_docs = await db.maintenance_issues.find(
            {**query, "resolved_at": {"$ne": ""}, "started_at": {"$ne": ""}},
            {"_id": 0, "resolved_at": 1, "started_at": 1}
        ).to_list(1000)
        durations = []
        for d in resolved_docs:
            try:
                hrs = (datetime.fromisoformat(d["resolved_at"]) - datetime.fromisoformat(d["started_at"])).total_seconds() / 3600
                if hrs >= 0:
                    durations.append(hrs)
            except Exception:
                pass
        mttr = round(sum(durations) / len(durations), 2) if durations else None

        # Total costs
        cost_pipeline = [{"$match": query}, {"$group": {"_id": None, "total_estimated": {"$sum": "$estimated_cost"}, "total_actual": {"$sum": "$actual_cost"}}}]
        cost_data = {"total_estimated": 0, "total_actual": 0}
        async for doc in db.maintenance_issues.aggregate(cost_pipeline):
            cost_data = {"total_estimated": doc.get("total_estimated", 0), "total_actual": doc.get("total_actual", 0)}

        return {
            "total": total, "open": open_count, "in_progress": in_progress,
            "resolved": resolved, "overdue": overdue,
            "by_category": cat_breakdown, "by_priority": pri_breakdown,
            "by_department": dept_breakdown, "workload": workload,
            "mttr_hours": mttr,
            "costs": cost_data,
        }

    @router.get("/maintenance/dashboard/{property_id}")
    async def get_dashboard(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Enhanced dashboard with trends, SLA compliance, team workload"""
        query = {} if property_id == "all" else {"property_id": property_id}

        # Monthly trends (last 6 months)
        now = datetime.now(timezone.utc)
        monthly = []
        for i in range(5, -1, -1):
            month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1)
            m_query = {**query, "created_at": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}}
            created = await db.maintenance_issues.count_documents(m_query)
            r_query = {**query, "resolved_at": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}}
            resolved = await db.maintenance_issues.count_documents(r_query)
            monthly.append({"month": month_start.strftime("%b %Y"), "created": created, "resolved": resolved})

        # SLA compliance
        total_with_sla = await db.maintenance_issues.count_documents({**query, "sla_deadline": {"$exists": True, "$ne": ""}})
        breached = await db.maintenance_issues.count_documents({**query, "sla_breached": True})
        sla_rate = round(((total_with_sla - breached) / max(total_with_sla, 1)) * 100, 1)

        # Avg resolution time (hours)
        pipeline_res = [
            {"$match": {**query, "resolved_at": {"$ne": ""}, "created_at": {"$ne": ""}}},
            {"$limit": 100}
        ]
        resolved_issues = []
        async for doc in db.maintenance_issues.aggregate(pipeline_res):
            resolved_issues.append(doc)
        avg_hours = 0
        if resolved_issues:
            total_ms = sum((datetime.fromisoformat(d["resolved_at"].replace("Z", "+00:00")) - datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))).total_seconds() for d in resolved_issues if d.get("resolved_at") and d.get("created_at"))
            avg_hours = round(total_ms / len(resolved_issues) / 3600, 1)

        # Team workload
        team_pipeline = [
            {"$match": {**query, "assigned_to": {"$ne": ""}, "status": {"$in": ["open", "acknowledged", "in_progress"]}}},
            {"$group": {"_id": "$assigned_to", "count": {"$sum": 1}}}
        ]
        team_load = {}
        async for doc in db.maintenance_issues.aggregate(team_pipeline):
            team_load[doc["_id"]] = doc["count"]

        # Top locations
        loc_pipeline = [
            {"$match": query},
            {"$group": {"_id": {"$ifNull": ["$location", "$room_number"]}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, {"$limit": 10}
        ]
        top_locations = []
        async for doc in db.maintenance_issues.aggregate(loc_pipeline):
            if doc["_id"]:
                top_locations.append({"location": doc["_id"], "count": doc["count"]})

        return {
            "monthly_trends": monthly,
            "sla_compliance_rate": sla_rate,
            "sla_total": total_with_sla,
            "sla_breached": breached,
            "avg_resolution_hours": avg_hours,
            "team_workload": team_load,
            "top_locations": top_locations,
        }

    # ==================== GUEST QR MAINTENANCE REPORT (PUBLIC) ====================

    @router.get("/maintenance/guest-report-info/{property_id}/{room_id}")
    async def guest_report_info(property_id: str, room_id: str):
        """Public: Get property info for guest maintenance report form"""
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0})
        ts = await db.template_settings.find_one({"property_id": property_id}, {"_id": 0}) or {}
        hotel_name = ts.get("hotel_name") or (prop or {}).get("name", "Hotel")
        return {"hotel_name": hotel_name, "room": room_id, "property_id": property_id}

    @router.post("/maintenance/guest-report/{property_id}/{room_id}")
    async def guest_report_issue(property_id: str, room_id: str, data: Dict):
        """Public: Guest submits maintenance issue via QR code"""
        now = datetime.now(timezone.utc).isoformat()
        category = data.get("category", "general")
        dept = CATEGORY_DEPARTMENT.get(category, "maintenance")
        sla_hours = SLA_TARGETS.get("high", 8)

        issue = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "title": data.get("title", f"Guest report - Room {room_id}"),
            "description": data.get("description", ""),
            "category": category,
            "priority": "high",
            "status": "open",
            "location": f"Room {room_id}",
            "room_number": room_id,
            "assigned_to": "",
            "assigned_department": dept,
            "reported_by": data.get("guest_name", "Guest"),
            "reported_by_email": data.get("guest_email", ""),
            "photos_before": [],
            "photos_after": [],
            "estimated_cost": 0, "actual_cost": 0, "cost_notes": "", "materials": [],
            "sla_hours": sla_hours,
            "sla_deadline": (datetime.now(timezone.utc) + timedelta(hours=sla_hours)).isoformat(),
            "sla_breached": False,
            "acknowledged_at": "", "acknowledged_by": "",
            "started_at": "", "started_by": "",
            "resolved_at": "", "resolved_by": "",
            "closed_at": "", "closed_by": "",
            "resolution_notes": "", "comments": [],
            "timeline": [{"action": "created", "by": data.get("guest_name", "Guest"), "at": now, "detail": f"Guest reported from Room {room_id}: {data.get('title', '')}"}],
            "recurring_id": "", "source": "guest_qr",
            "created_at": now, "updated_at": now,
        }
        await db.maintenance_issues.insert_one(issue)
        return {"status": "submitted", "id": issue["id"]}

    @router.post("/maintenance/guest-upload-photo/{issue_id}")
    async def guest_upload_photo(issue_id: str, file: UploadFile = File(...)):
        """Public: Guest uploads photo for their reported issue"""
        issue = await db.maintenance_issues.find_one({"id": issue_id, "source": "guest_qr"}, {"_id": 0})
        if not issue:
            raise HTTPException(404, "Issue not found")
        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
        filename = f"{issue_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(MAINT_UPLOAD_DIR, filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        photo_url = f"/api/uploads/maintenance/{filename}"
        photos = issue.get("photos_before", [])
        photos.append({"url": photo_url, "filename": file.filename, "uploaded_by": "Guest", "uploaded_at": datetime.now(timezone.utc).isoformat(), "type": "before"})
        await db.maintenance_issues.update_one({"id": issue_id}, {"$set": {"photos_before": photos}})
        return {"status": "uploaded", "url": photo_url}

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
