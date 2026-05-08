"""
Bug Tracker & System Feedback
- Any authenticated user can file a bug / feedback / feature request
- Admins/managers can triage: status, priority, assign, comment, resolve
- Kanban-style board support via status grouping
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid


STATUSES = ["new", "triaged", "in_progress", "resolved", "closed", "wont_fix"]
PRIORITIES = ["low", "medium", "high", "critical"]
TYPES = ["bug", "feedback", "feature_request", "question"]


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field("", max_length=5000)
    type: str = "bug"
    priority: str = "medium"
    area: Optional[str] = None           # "bookings", "payroll", "integrations", …
    property_id: Optional[str] = None
    url_context: Optional[str] = None    # page where the issue occurred
    screenshot_url: Optional[str] = None


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    type: Optional[str] = None
    area: Optional[str] = None
    assigned_to_id: Optional[str] = None
    resolution_note: Optional[str] = None


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=3000)


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_bug_tracker_router(db, require_roles, get_current_user):
    router = APIRouter()

    # ----------- CREATE -----------
    @router.post("/bug-tracker")
    async def create_ticket(body: TicketCreate, current_user: dict = Depends(get_current_user)):
        if body.type not in TYPES:
            raise HTTPException(400, "Invalid type")
        if body.priority not in PRIORITIES:
            raise HTTPException(400, "Invalid priority")

        ticket = {
            "id": str(uuid.uuid4()),
            "title": body.title.strip(),
            "description": body.description or "",
            "type": body.type,
            "priority": body.priority,
            "status": "new",
            "area": body.area,
            "property_id": body.property_id,
            "url_context": body.url_context,
            "screenshot_url": body.screenshot_url,
            "created_by_id": current_user.get("id"),
            "created_by_name": current_user.get("name"),
            "created_by_role": current_user.get("role"),
            "created_by_email": current_user.get("email"),
            "assigned_to_id": None,
            "assigned_to_name": None,
            "resolution_note": None,
            "resolved_at": None,
            "resolved_by_id": None,
            "resolved_by_name": None,
            "comments": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.bug_tickets.insert_one(ticket)
        ticket.pop("_id", None)
        return ticket

    # ----------- LIST -----------
    @router.get("/bug-tracker")
    async def list_tickets(status: str = "", priority: str = "",
                           type: str = "", q: str = "",
                           mine: bool = False,
                           assigned_to_me: bool = False,
                           current_user: dict = Depends(get_current_user)):
        role = current_user.get("role")
        query: dict = {}
        # Non-admins only see their own tickets (unless they're assigned one)
        if role not in ("admin", "manager"):
            query["$or"] = [
                {"created_by_id": current_user.get("id")},
                {"assigned_to_id": current_user.get("id")},
            ]
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        if type:
            query["type"] = type
        if mine:
            query["created_by_id"] = current_user.get("id")
        if assigned_to_me:
            query["assigned_to_id"] = current_user.get("id")

        tickets = await db.bug_tickets.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

        if q:
            ql = q.lower()
            tickets = [t for t in tickets if ql in (t.get("title") or "").lower()
                       or ql in (t.get("description") or "").lower()]

        # Stats
        totals_query = {} if role in ("admin", "manager") else query
        all_tickets = await db.bug_tickets.find(totals_query, {"_id": 0, "status": 1, "priority": 1, "type": 1}).to_list(2000)
        stats = {
            "total": len(all_tickets),
            "new": sum(1 for t in all_tickets if t.get("status") == "new"),
            "in_progress": sum(1 for t in all_tickets if t.get("status") == "in_progress"),
            "resolved": sum(1 for t in all_tickets if t.get("status") == "resolved"),
            "critical": sum(1 for t in all_tickets if t.get("priority") == "critical"),
            "by_status": {s: sum(1 for t in all_tickets if t.get("status") == s) for s in STATUSES},
        }
        return {"tickets": tickets, "stats": stats}

    # ----------- GET ONE -----------
    @router.get("/bug-tracker/{ticket_id}")
    async def get_ticket(ticket_id: str, current_user: dict = Depends(get_current_user)):
        t = await db.bug_tickets.find_one({"id": ticket_id}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Ticket not found")
        role = current_user.get("role")
        if role not in ("admin", "manager") and t.get("created_by_id") != current_user.get("id") and t.get("assigned_to_id") != current_user.get("id"):
            raise HTTPException(403, "Not allowed")
        return t

    # ----------- UPDATE (triage) -----------
    @router.put("/bug-tracker/{ticket_id}")
    async def update_ticket(ticket_id: str, body: TicketUpdate,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        t = await db.bug_tickets.find_one({"id": ticket_id})
        if not t:
            raise HTTPException(404, "Ticket not found")

        updates: dict = {"updated_at": _now()}
        if body.status is not None:
            if body.status not in STATUSES:
                raise HTTPException(400, "Invalid status")
            updates["status"] = body.status
            if body.status == "resolved" and not t.get("resolved_at"):
                updates["resolved_at"] = _now()
                updates["resolved_by_id"] = current_user.get("id")
                updates["resolved_by_name"] = current_user.get("name")
        if body.priority is not None:
            if body.priority not in PRIORITIES:
                raise HTTPException(400, "Invalid priority")
            updates["priority"] = body.priority
        if body.type is not None:
            if body.type not in TYPES:
                raise HTTPException(400, "Invalid type")
            updates["type"] = body.type
        if body.area is not None:
            updates["area"] = body.area
        if body.resolution_note is not None:
            updates["resolution_note"] = body.resolution_note
        if body.assigned_to_id is not None:
            if body.assigned_to_id:
                assignee = await db.users.find_one({"id": body.assigned_to_id}, {"_id": 0, "name": 1})
                if not assignee:
                    raise HTTPException(400, "Assignee not found")
                updates["assigned_to_id"] = body.assigned_to_id
                updates["assigned_to_name"] = assignee.get("name")
            else:
                updates["assigned_to_id"] = None
                updates["assigned_to_name"] = None

        await db.bug_tickets.update_one({"id": ticket_id}, {"$set": updates})
        return await db.bug_tickets.find_one({"id": ticket_id}, {"_id": 0})

    # ----------- COMMENT -----------
    @router.post("/bug-tracker/{ticket_id}/comments")
    async def add_comment(ticket_id: str, body: CommentCreate,
                          current_user: dict = Depends(get_current_user)):
        t = await db.bug_tickets.find_one({"id": ticket_id}, {"_id": 0, "created_by_id": 1, "assigned_to_id": 1})
        if not t:
            raise HTTPException(404, "Ticket not found")
        role = current_user.get("role")
        if role not in ("admin", "manager") and t.get("created_by_id") != current_user.get("id") and t.get("assigned_to_id") != current_user.get("id"):
            raise HTTPException(403, "Not allowed")
        comment = {
            "id": str(uuid.uuid4()),
            "body": body.body.strip(),
            "author_id": current_user.get("id"),
            "author_name": current_user.get("name"),
            "author_role": current_user.get("role"),
            "created_at": _now(),
        }
        await db.bug_tickets.update_one(
            {"id": ticket_id},
            {"$push": {"comments": comment}, "$set": {"updated_at": _now()}}
        )
        return comment

    # ----------- DELETE (admin only) -----------
    @router.delete("/bug-tracker/{ticket_id}")
    async def delete_ticket(ticket_id: str, current_user: dict = Depends(require_roles("admin"))):
        r = await db.bug_tickets.delete_one({"id": ticket_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Ticket not found")
        return {"ok": True}

    # ----------- ASSIGNABLE USERS -----------
    @router.get("/bug-tracker-meta/assignees")
    async def assignees(current_user: dict = Depends(require_roles("admin", "manager"))):
        users = await db.users.find(
            {"role": {"$in": ["admin", "manager"]}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}
        ).sort("name", 1).to_list(100)
        return users

    return router
