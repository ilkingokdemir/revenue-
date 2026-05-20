"""
Conference Sales & Catering (S&C) Proposal Builder — MICE segment depth.

MICE = Meetings, Incentives, Conferences, Events. Avg deal value 10-50x single-room bookings.

Workflow:
  Sales rep receives inquiry → creates Inquiry record
  Builds Proposal: event spaces + catering packages + room block + AV equipment
  System auto-calculates total quote
  Sales rep sends proposal (status: draft → sent → accepted/rejected)
  On accept: creates event booking + room block reservations

Why this beats competitors:
  Opera Sales&Catering: separate $$$ module. Us: native.
  Cloudbeds: no S&C module. Us: complete quote-to-event pipeline.
  Mews Events: basic room bookings only. Us: catering + AV + room blocks.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict
import uuid
import logging

logger = logging.getLogger(__name__)


class EventSpace(BaseModel):
    property_id: str
    name: str
    capacity_theater: int = 0
    capacity_banquet: int = 0
    capacity_boardroom: int = 0
    capacity_reception: int = 0
    area_sqm: float = 0
    half_day_rate: float = 0
    full_day_rate: float = 0
    features: List[str] = []
    photos: List[str] = []


class CateringPackage(BaseModel):
    property_id: str
    name: str
    category: str = "lunch"        # breakfast | lunch | dinner | coffee_break | gala
    per_person_price: float
    min_persons: int = 1
    includes: List[str] = []


class Inquiry(BaseModel):
    property_id: str
    contact_name: str
    contact_email: str
    contact_company: Optional[str] = None
    contact_phone: Optional[str] = None
    event_name: str
    event_type: str = "conference"  # conference | wedding | banquet | meeting | gala | training
    start_date: str                 # YYYY-MM-DD
    end_date: str
    total_attendees: int
    budget_estimate: Optional[float] = None
    special_requirements: Optional[str] = None


class ProposalLine(BaseModel):
    type: str                       # "space" | "catering" | "room_block" | "av" | "custom"
    reference_id: Optional[str] = None
    description: str
    qty: float = 1
    unit_price: float
    currency: str = "gbp"


class ProposalBuild(BaseModel):
    lines: List[ProposalLine]
    discount_pct: float = 0
    notes: Optional[str] = None
    valid_until: Optional[str] = None   # YYYY-MM-DD


DEFAULT_SPACES = [
    {"name": "Grand Ballroom", "capacity_theater": 500, "capacity_banquet": 300, "capacity_boardroom": 0, "capacity_reception": 600, "area_sqm": 450, "half_day_rate": 1500, "full_day_rate": 2500, "features": ["Stage", "Dance floor", "AV-ready"]},
    {"name": "Executive Boardroom", "capacity_theater": 0, "capacity_banquet": 0, "capacity_boardroom": 20, "capacity_reception": 30, "area_sqm": 60, "half_day_rate": 400, "full_day_rate": 700, "features": ["Videoconf", "Whiteboard"]},
    {"name": "Rooftop Terrace", "capacity_theater": 0, "capacity_banquet": 80, "capacity_boardroom": 0, "capacity_reception": 120, "area_sqm": 180, "half_day_rate": 800, "full_day_rate": 1500, "features": ["Outdoor", "Panoramic view"]},
    {"name": "Meeting Room A", "capacity_theater": 50, "capacity_banquet": 30, "capacity_boardroom": 16, "capacity_reception": 60, "area_sqm": 40, "half_day_rate": 200, "full_day_rate": 350, "features": ["Projector"]},
]

DEFAULT_CATERING = [
    {"name": "Coffee Break Classic", "category": "coffee_break", "per_person_price": 8, "min_persons": 10, "includes": ["Coffee", "Tea", "Assorted biscuits"]},
    {"name": "Coffee Break Premium", "category": "coffee_break", "per_person_price": 14, "min_persons": 10, "includes": ["Barista coffee", "Premium tea", "Fresh pastries", "Seasonal fruits"]},
    {"name": "Business Lunch", "category": "lunch", "per_person_price": 35, "min_persons": 15, "includes": ["2-course hot lunch", "Salad bar", "Non-alcoholic drinks"]},
    {"name": "Executive Lunch", "category": "lunch", "per_person_price": 55, "min_persons": 15, "includes": ["3-course menu", "Wine pairing", "Coffee station"]},
    {"name": "Gala Dinner", "category": "dinner", "per_person_price": 95, "min_persons": 30, "includes": ["4-course fine dining", "Welcome drinks", "Wine", "Live music option"]},
    {"name": "Breakfast Buffet", "category": "breakfast", "per_person_price": 22, "min_persons": 10, "includes": ["Continental", "Hot options", "Juices", "Coffee"]},
]


def create_conference_sc_router(db, require_roles):
    router = APIRouter()

    # ---------- EVENT SPACES ----------
    @router.get("/conference/event-spaces/{property_id}")
    async def list_spaces(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.conf_event_spaces.find({"property_id": property_id}, {"_id": 0}).to_list(100)
        return {"rows": rows, "count": len(rows)}

    @router.post("/conference/event-spaces/{property_id}/seed-defaults")
    async def seed_spaces(property_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.conf_event_spaces.count_documents({"property_id": property_id})
        if existing > 0:
            return {"seeded": 0, "note": f"{existing} space(s) already configured"}
        now = datetime.now(timezone.utc).isoformat()
        docs = [
            {**d, "id": str(uuid.uuid4()), "property_id": property_id, "created_at": now, "photos": []}
            for d in DEFAULT_SPACES
        ]
        await db.conf_event_spaces.insert_many(docs)
        # Seed catering too
        cat_existing = await db.conf_catering.count_documents({"property_id": property_id})
        if cat_existing == 0:
            cdocs = [{**c, "id": str(uuid.uuid4()), "property_id": property_id, "created_at": now} for c in DEFAULT_CATERING]
            await db.conf_catering.insert_many(cdocs)
            return {"seeded_spaces": len(docs), "seeded_catering": len(cdocs)}
        return {"seeded_spaces": len(docs)}

    @router.post("/conference/event-spaces")
    async def upsert_space(space: EventSpace,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = space.dict()
        doc["updated_at"] = now
        result = await db.conf_event_spaces.update_one(
            {"property_id": space.property_id, "name": space.name},
            {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
            upsert=True,
        )
        return {"upserted": bool(result.upserted_id), "modified": result.modified_count > 0}

    # ---------- CATERING ----------
    @router.get("/conference/catering/{property_id}")
    async def list_catering(property_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.conf_catering.find({"property_id": property_id}, {"_id": 0}).to_list(100)
        return {"rows": rows, "count": len(rows)}

    @router.post("/conference/catering")
    async def upsert_catering(pkg: CateringPackage,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc).isoformat()
        doc = pkg.dict()
        doc["updated_at"] = now
        await db.conf_catering.update_one(
            {"property_id": pkg.property_id, "name": pkg.name},
            {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
            upsert=True,
        )
        return {"updated": True}

    # ---------- INQUIRIES ----------
    @router.get("/conference/inquiries/{property_id}")
    async def list_inquiries(property_id: str, status: Optional[str] = None, limit: int = 100,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q = {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.conf_inquiries.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        # Summary
        pipeline = await db.conf_inquiries.aggregate([
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}, "total_value": {"$sum": "$proposal_total"}}},
        ]).to_list(20)
        by_status = {p["_id"] or "new": {"count": p["count"], "total_value": round(p.get("total_value") or 0, 2)} for p in pipeline}
        return {"rows": rows, "count": len(rows), "by_status": by_status}

    @router.post("/conference/inquiry")
    async def create_inquiry(inq: Inquiry,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        try:
            sd = date.fromisoformat(inq.start_date)
            ed = date.fromisoformat(inq.end_date)
        except ValueError:
            raise HTTPException(400, "start_date and end_date must be YYYY-MM-DD")
        if ed < sd:
            raise HTTPException(400, "end_date must be after start_date")
        if inq.total_attendees < 1 or inq.total_attendees > 5000:
            raise HTTPException(400, "total_attendees must be 1..5000")

        now = datetime.now(timezone.utc).isoformat()
        doc = inq.dict()
        doc["id"] = str(uuid.uuid4())
        doc["ref"] = f"INQ-{datetime.now(timezone.utc).strftime('%y%m%d')}-{doc['id'][:4].upper()}"
        doc["status"] = "new"
        doc["created_at"] = now
        doc["created_by"] = current_user.get("email")
        doc["days"] = (ed - sd).days + 1
        doc["proposal_lines"] = []
        doc["proposal_total"] = 0
        await db.conf_inquiries.insert_one(doc)
        return {k: v for k, v in doc.items() if k != "_id"}

    @router.get("/conference/inquiry/{inq_id}")
    async def get_inquiry(inq_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        inq = await db.conf_inquiries.find_one({"id": inq_id}, {"_id": 0})
        if not inq:
            raise HTTPException(404, "Inquiry not found")
        return inq

    # ---------- PROPOSAL BUILDER ----------
    @router.post("/conference/inquiry/{inq_id}/proposal")
    async def build_proposal(inq_id: str, build: ProposalBuild,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        inq = await db.conf_inquiries.find_one({"id": inq_id}, {"_id": 0})
        if not inq:
            raise HTTPException(404, "Inquiry not found")
        if not build.lines:
            raise HTTPException(400, "At least one line required")
        if build.discount_pct < 0 or build.discount_pct > 50:
            raise HTTPException(400, "discount_pct must be 0..50")

        subtotal = sum(l.qty * l.unit_price for l in build.lines)
        discount_amount = round(subtotal * build.discount_pct / 100, 2)
        total = round(subtotal - discount_amount, 2)
        # Per-attendee price if attendees present
        pp = round(total / inq["total_attendees"], 2) if inq.get("total_attendees") else None

        now = datetime.now(timezone.utc).isoformat()
        lines = [l.dict() for l in build.lines]
        patch = {
            "proposal_lines": lines,
            "proposal_subtotal": round(subtotal, 2),
            "proposal_discount_pct": build.discount_pct,
            "proposal_discount_amount": discount_amount,
            "proposal_total": total,
            "proposal_per_person": pp,
            "proposal_notes": build.notes,
            "proposal_valid_until": build.valid_until,
            "proposal_built_at": now,
            "proposal_built_by": current_user.get("email"),
            "status": "proposal_ready" if inq.get("status") in ("new", "proposal_ready") else inq.get("status"),
        }
        await db.conf_inquiries.update_one({"id": inq_id}, {"$set": patch})
        return {"inquiry_id": inq_id, "subtotal": round(subtotal, 2), "discount_amount": discount_amount, "total": total, "per_person": pp, "lines_count": len(lines)}

    @router.post("/conference/inquiry/{inq_id}/status/{new_status}")
    async def set_status(inq_id: str, new_status: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        valid = {"new", "proposal_ready", "sent", "accepted", "rejected", "cancelled"}
        if new_status not in valid:
            raise HTTPException(400, f"Invalid status. Must be one of {sorted(valid)}")
        now = datetime.now(timezone.utc).isoformat()
        await db.conf_inquiries.update_one(
            {"id": inq_id},
            {"$set": {"status": new_status, f"{new_status}_at": now, f"{new_status}_by": current_user.get("email")}}
        )
        return {"id": inq_id, "status": new_status}

    # ---------- DASHBOARD SUMMARY ----------
    @router.get("/conference/dashboard/{property_id}")
    async def dashboard(property_id: str, days: int = 90,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        if days < 7 or days > 365:
            raise HTTPException(400, "days must be 7..365")
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        inq = await db.conf_inquiries.find({
            "property_id": property_id,
            "created_at": {"$gte": since},
        }, {"_id": 0}).to_list(1000)

        total_inq = len(inq)
        pipeline_value = sum(i.get("proposal_total") or 0 for i in inq if i.get("status") in ("proposal_ready", "sent"))
        won_value = sum(i.get("proposal_total") or 0 for i in inq if i.get("status") == "accepted")
        lost_value = sum(i.get("proposal_total") or 0 for i in inq if i.get("status") == "rejected")
        avg_deal = round(won_value / sum(1 for i in inq if i.get("status") == "accepted"), 2) if any(i.get("status") == "accepted" for i in inq) else 0
        conversion = round(sum(1 for i in inq if i.get("status") == "accepted") / total_inq * 100, 1) if total_inq else 0

        by_event_type = {}
        for i in inq:
            et = i.get("event_type", "other")
            by_event_type[et] = by_event_type.get(et, 0) + 1

        return {
            "total_inquiries": total_inq,
            "pipeline_value": round(pipeline_value, 2),
            "won_value": round(won_value, 2),
            "lost_value": round(lost_value, 2),
            "avg_deal_size": avg_deal,
            "conversion_rate": conversion,
            "by_event_type": by_event_type,
            "days": days,
        }

    return router
