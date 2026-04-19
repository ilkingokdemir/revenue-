"""
Group Bookings / Master Folio
-----------------------------
Link multiple individual bookings into one group (weddings, conferences, tours).
Supports three billing modes:
  - master_pays_all       → organiser pays room + extras for every room
  - master_pays_room_only → organiser pays rooms; guests pay extras
  - each_room_self_pays   → bookkeeping only; each room settles its own folio

Collections:
- groups: {id, property_id, name, organiser_name, organiser_email, organiser_phone,
           organisation, booking_ids[], billing_mode, rooming_list[], notes, created_at, ...}

Endpoints (/api/groups/*):
- GET/POST/PUT/DELETE /groups[/{id}]
- POST /groups/{id}/attach                 → add booking_ids
- POST /groups/{id}/detach                 → remove booking_ids
- GET  /groups/{id}/master-folio           → consolidated folio view
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from auth import require_perm


BILLING_MODES = ("master_pays_all", "master_pays_room_only", "each_room_self_pays")


class GroupIn(BaseModel):
    property_id: str = "default"
    name: str
    organiser_name: Optional[str] = ""
    organiser_email: Optional[str] = ""
    organiser_phone: Optional[str] = ""
    organisation: Optional[str] = ""
    billing_mode: str = "master_pays_room_only"
    booking_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = ""


class AttachIn(BaseModel):
    booking_ids: List[str]


def create_groups_router(db):
    router = APIRouter(prefix="/groups")

    async def _enrich(group: dict) -> dict:
        """Load bookings + compute totals for a group doc."""
        bookings = []
        totals = {"rooms": 0, "gross": 0.0, "paid": 0.0, "balance": 0.0, "currency": "GBP"}
        if group.get("booking_ids"):
            cursor = db.bookings.find(
                {"id": {"$in": group["booking_ids"]}},
                {"_id": 0, "id": 1, "guest_name": 1, "guest_email": 1, "check_in": 1,
                 "check_out": 1, "total_price": 1, "status": 1, "currency": 1,
                 "room_type_id": 1, "payment_status": 1},
            )
            async for b in cursor:
                rt = await db.room_types.find_one({"id": b.get("room_type_id", "")},
                                                  {"_id": 0, "name": 1})
                b["room_type_name"] = rt.get("name") if rt else "—"
                # Tally paid from folio_charges where relevant
                charges = await db.folio_charges.find(
                    {"booking_id": b["id"]}, {"_id": 0, "amount": 1, "type": 1}
                ).to_list(500)
                paid = round(sum(float(c.get("amount", 0)) for c in charges
                                 if c.get("type") == "payment"), 2)
                b["folio_paid"] = paid
                gross = float(b.get("total_price", 0))
                b["balance"] = round(gross - paid, 2)
                bookings.append(b)
                totals["rooms"] += 1
                totals["gross"] += gross
                totals["paid"] += paid
                totals["balance"] += b["balance"]
                if b.get("currency"):
                    totals["currency"] = b["currency"]
        totals = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in totals.items()}
        group["bookings"] = bookings
        group["totals"] = totals
        return group

    @router.get("/")
    async def list_groups(
        property_id: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        q = {} if not property_id or property_id == "all" else {"property_id": property_id}
        rows = await db.groups.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        for g in rows:
            await _enrich(g)
        return rows

    @router.get("/{group_id}")
    async def get_group(
        group_id: str,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        g = await db.groups.find_one({"id": group_id}, {"_id": 0})
        if not g:
            raise HTTPException(404, "Group not found")
        return await _enrich(g)

    @router.post("/")
    async def create_group(
        data: GroupIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        if data.billing_mode not in BILLING_MODES:
            raise HTTPException(400, f"billing_mode must be one of {BILLING_MODES}")
        doc = data.model_dump()
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = datetime.now(timezone.utc).isoformat()
        doc["created_by"] = current_user.get("email", "")
        await db.groups.insert_one(dict(doc))
        # Back-link on bookings
        if doc["booking_ids"]:
            await db.bookings.update_many(
                {"id": {"$in": doc["booking_ids"]}},
                {"$set": {"group_id": doc["id"]}},
            )
        doc.pop("_id", None)
        return await _enrich(doc)

    @router.put("/{group_id}")
    async def update_group(
        group_id: str, data: GroupIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        update = data.model_dump(exclude_unset=True)
        if "billing_mode" in update and update["billing_mode"] not in BILLING_MODES:
            raise HTTPException(400, f"billing_mode must be one of {BILLING_MODES}")
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.groups.update_one({"id": group_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Group not found")
        return {"ok": True}

    @router.delete("/{group_id}")
    async def delete_group(
        group_id: str,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        g = await db.groups.find_one({"id": group_id}, {"_id": 0})
        if g and g.get("booking_ids"):
            await db.bookings.update_many(
                {"id": {"$in": g["booking_ids"]}}, {"$unset": {"group_id": ""}}
            )
        r = await db.groups.delete_one({"id": group_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Group not found")
        return {"deleted": True}

    @router.post("/{group_id}/attach")
    async def attach_bookings(
        group_id: str, body: AttachIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        g = await db.groups.find_one({"id": group_id}, {"_id": 0})
        if not g:
            raise HTTPException(404, "Group not found")
        ids = list(set((g.get("booking_ids") or []) + body.booking_ids))
        await db.groups.update_one({"id": group_id}, {"$set": {"booking_ids": ids}})
        await db.bookings.update_many(
            {"id": {"$in": body.booking_ids}}, {"$set": {"group_id": group_id}}
        )
        return {"ok": True, "booking_ids": ids}

    @router.post("/{group_id}/detach")
    async def detach_bookings(
        group_id: str, body: AttachIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        g = await db.groups.find_one({"id": group_id}, {"_id": 0})
        if not g:
            raise HTTPException(404, "Group not found")
        ids = [i for i in (g.get("booking_ids") or []) if i not in body.booking_ids]
        await db.groups.update_one({"id": group_id}, {"$set": {"booking_ids": ids}})
        await db.bookings.update_many(
            {"id": {"$in": body.booking_ids}}, {"$unset": {"group_id": ""}}
        )
        return {"ok": True, "booking_ids": ids}

    @router.get("/{group_id}/master-folio")
    async def master_folio(
        group_id: str,
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        g = await db.groups.find_one({"id": group_id}, {"_id": 0})
        if not g:
            raise HTTPException(404, "Group not found")
        g = await _enrich(g)
        # Aggregate folio charges across all bookings
        lines = []
        for b in g.get("bookings", []):
            charges = await db.folio_charges.find(
                {"booking_id": b["id"]}, {"_id": 0}
            ).sort("timestamp", 1).to_list(1000)
            for c in charges:
                c["guest_name"] = b.get("guest_name", "")
                c["booking_id"] = b["id"]
                lines.append(c)
        # Split visibility by billing mode
        mode = g.get("billing_mode", "master_pays_room_only")
        master_lines = []
        room_owner_lines = []
        for ln in lines:
            ctype = ln.get("type", "")
            if mode == "master_pays_all":
                master_lines.append(ln)
            elif mode == "master_pays_room_only":
                (master_lines if ctype in ("room", "payment") else room_owner_lines).append(ln)
            else:  # each_room_self_pays
                room_owner_lines.append(ln)
        return {
            "group": {k: v for k, v in g.items() if k != "bookings"},
            "bookings": g.get("bookings", []),
            "totals": g.get("totals", {}),
            "billing_mode": mode,
            "master_charges": master_lines,
            "room_owner_charges": room_owner_lines,
        }

    return router
