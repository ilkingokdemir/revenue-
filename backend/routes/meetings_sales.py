"""
Meeting & Events Sales (MICE) — Tier-1 banquet/wedding/conference sales pipeline.

Differs from existing /conference-sc (which is operational floor management):
this module is the SALES funnel — RFPs, quotes, conversions, BEO (Banquet Event Order)
sign-off, and conversion analytics that revenue managers need.

Pipeline stages:
  inquiry → site_visit → proposal_sent → negotiating → confirmed → invoiced → completed
  (or → lost at any stage with reason)

Endpoints:
  GET   /api/meetings                          — list (with stage filter)
  POST  /api/meetings                          — create RFP / lead
  GET   /api/meetings/{id}                     — detail with line items
  PATCH /api/meetings/{id}                     — update / move stage / mark lost
  POST  /api/meetings/{id}/items               — add line item (rooms, F&B, AV, space)
  DELETE /api/meetings/{id}/items/{item_id}    — remove line item
  GET   /api/meetings/pipeline                 — pipeline view (Kanban data)
  GET   /api/meetings/analytics                — conversion funnel + revenue
"""
from datetime import datetime, timezone, timedelta
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


STAGES = ["inquiry", "site_visit", "proposal_sent", "negotiating",
          "confirmed", "invoiced", "completed", "lost"]
EVENT_TYPES = ["wedding", "corporate_meeting", "conference", "gala",
               "birthday", "association", "training", "other"]
ITEM_KINDS = ["room_block", "fnb", "av_tech", "meeting_space", "decor", "misc"]


class MeetingIn(BaseModel):
    name: str
    event_type: str = "wedding"
    property_id: str
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    company: str = ""
    event_date: str            # YYYY-MM-DD
    end_date: str = ""
    guests_count: int = 0
    rooms_required: int = 0
    spaces_required: List[str] = []
    budget_estimate: float = 0
    notes: str = ""
    source: str = "direct"     # direct | referral | website | ota | sales-rep


class LineItemIn(BaseModel):
    kind: str = "fnb"
    label: str
    qty: float = 1
    unit_price: float = 0
    notes: str = ""


def create_meetings_router(db, require_roles):
    router = APIRouter(prefix="/meetings")

    @router.get("")
    async def list_meetings(stage: str = "", property_id: str = "",
                            from_date: str = "", to_date: str = "",
                            _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if stage:
            q["stage"] = stage
        if property_id and property_id != "all":
            q["property_id"] = property_id
        if from_date or to_date:
            dq: dict = {}
            if from_date:
                dq["$gte"] = from_date
            if to_date:
                dq["$lte"] = to_date
            q["event_date"] = dq
        rows = await db.meeting_sales.find(q, {"_id": 0}).sort("event_date", 1).to_list(500)
        # Sum totals lazily
        for r in rows:
            items = await db.meeting_sale_items.find({"meeting_id": r["id"]},
                                                      {"_id": 0, "qty": 1, "unit_price": 1}).to_list(100)
            r["total_estimate"] = round(sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items), 2)
            r["items_count"] = len(items)
        return {"meetings": rows, "count": len(rows), "stages": STAGES}

    @router.post("")
    async def create_meeting(body: MeetingIn,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        if body.event_type not in EVENT_TYPES:
            raise HTTPException(400, f"Invalid event_type; use one of {EVENT_TYPES}")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            **body.dict(),
            "stage": "inquiry",
            "stage_history": [{"stage": "inquiry", "at": now, "by": current_user.get("name", "")}],
            "owner_sales_rep": current_user.get("name", ""),
            "created_at": now,
            "lost_reason": None,
        }
        await db.meeting_sales.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/pipeline")
    async def pipeline(property_id: str = "",
                       _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.meeting_sales.find(q, {"_id": 0}).to_list(1000)
        # Group by stage
        by_stage: dict = {s: [] for s in STAGES}
        for r in rows:
            stage = r.get("stage", "inquiry")
            if stage in by_stage:
                items = await db.meeting_sale_items.find({"meeting_id": r["id"]},
                                                          {"_id": 0, "qty": 1, "unit_price": 1}).to_list(100)
                r["total_estimate"] = round(sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items), 2)
                by_stage[stage].append(r)
        # Sort each lane by event_date ascending
        for s in by_stage:
            by_stage[s].sort(key=lambda m: m.get("event_date", ""))
        # Pipeline value (excl lost & completed)
        active_value = sum(r["total_estimate"] for s in STAGES if s not in ("lost", "completed")
                           for r in by_stage[s])
        return {"by_stage": by_stage, "active_value": round(active_value, 2),
                "stages": STAGES}

    @router.get("/analytics")
    async def analytics(property_id: str = "", days: int = 90,
                        _: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: dict = {"created_at": {"$gte": since}}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        rows = await db.meeting_sales.find(q, {"_id": 0}).to_list(2000)
        funnel = {s: 0 for s in STAGES}
        for r in rows:
            funnel[r.get("stage", "inquiry")] = funnel.get(r.get("stage", "inquiry"), 0) + 1
        total = len(rows)
        confirmed_or_better = funnel["confirmed"] + funnel["invoiced"] + funnel["completed"]
        win_rate = round(confirmed_or_better / max(1, total - funnel["lost"]) * 100, 1)
        # Revenue from confirmed+
        won = [r for r in rows if r.get("stage") in ("confirmed", "invoiced", "completed")]
        won_revenue = 0.0
        for r in won:
            items = await db.meeting_sale_items.find({"meeting_id": r["id"]},
                                                      {"_id": 0, "qty": 1, "unit_price": 1}).to_list(100)
            won_revenue += sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items)
        # Lost reasons
        lost = [r for r in rows if r.get("stage") == "lost"]
        lost_reasons: dict = {}
        for lm in lost:
            r = lm.get("lost_reason") or "unspecified"
            lost_reasons[r] = lost_reasons.get(r, 0) + 1
        return {
            "period_days": days,
            "total_inquiries": total,
            "funnel": funnel,
            "win_rate_pct": win_rate,
            "won_count": len(won),
            "won_revenue_estimate": round(won_revenue, 2),
            "avg_deal_size": round(won_revenue / max(1, len(won)), 2),
            "lost_count": len(lost),
            "lost_reasons": lost_reasons,
        }

    @router.get("/{meeting_id}")
    async def get_meeting(meeting_id: str,
                          _: dict = Depends(require_roles("admin", "manager"))):
        m = await db.meeting_sales.find_one({"id": meeting_id}, {"_id": 0})
        if not m:
            raise HTTPException(404, "Meeting not found")
        items = await db.meeting_sale_items.find({"meeting_id": meeting_id}, {"_id": 0}).to_list(200)
        m["items"] = items
        m["total_estimate"] = round(sum(i.get("qty", 0) * i.get("unit_price", 0) for i in items), 2)
        return m

    @router.patch("/{meeting_id}")
    async def patch_meeting(meeting_id: str, body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        m = await db.meeting_sales.find_one({"id": meeting_id}, {"_id": 0})
        if not m:
            raise HTTPException(404, "Meeting not found")
        update: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
        # Stage transition tracked in history
        new_stage = body.get("stage")
        if new_stage and new_stage != m.get("stage"):
            if new_stage not in STAGES:
                raise HTTPException(400, f"Invalid stage; use {STAGES}")
            history = m.get("stage_history", [])
            history.append({"stage": new_stage,
                            "at": datetime.now(timezone.utc).isoformat(),
                            "by": current_user.get("name", "")})
            update["stage"] = new_stage
            update["stage_history"] = history
            if new_stage == "lost":
                update["lost_reason"] = body.get("lost_reason", "unspecified")
        # Free-form fields
        for k in ("name", "contact_name", "contact_email", "contact_phone", "company",
                  "event_date", "end_date", "guests_count", "rooms_required",
                  "budget_estimate", "notes", "owner_sales_rep"):
            if k in body:
                update[k] = body[k]
        await db.meeting_sales.update_one({"id": meeting_id}, {"$set": update})
        return {"updated": True, "fields": list(update.keys())}

    @router.post("/{meeting_id}/items")
    async def add_item(meeting_id: str, body: LineItemIn,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        m = await db.meeting_sales.find_one({"id": meeting_id}, {"_id": 0, "id": 1})
        if not m:
            raise HTTPException(404, "Meeting not found")
        if body.kind not in ITEM_KINDS:
            raise HTTPException(400, f"Invalid kind; use {ITEM_KINDS}")
        doc = {
            "id": str(uuid.uuid4()),
            "meeting_id": meeting_id,
            **body.dict(),
            "subtotal": round(body.qty * body.unit_price, 2),
            "added_by": current_user.get("name", ""),
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.meeting_sale_items.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/{meeting_id}/items/{item_id}")
    async def delete_item(meeting_id: str, item_id: str,
                          _: dict = Depends(require_roles("admin", "manager"))):
        r = await db.meeting_sale_items.delete_one({"id": item_id, "meeting_id": meeting_id})
        return {"deleted": r.deleted_count}

    return router
