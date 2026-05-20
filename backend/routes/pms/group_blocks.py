"""
Group Blocks (Iter 165) — Group reservation / block module parity with
Mews / Eviivo / Cloudbeds / SiteMinder.

A group block pre-reserves N rooms of specific types for a date range
(weddings, corporate stays, sports teams, tour groups) with:
  • cutoff_date after which unsold block rooms release back to inventory
  • status (tentative | definite | cancelled)
  • contact (lead / booker)
  • allocations list [{room_type_id, quantity, rate}]

Materialize endpoint converts allocations into actual bookings in one click.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date as date_cls
from typing import Dict, List, Optional
import uuid


def create_group_blocks_router(db, require_roles):
    router = APIRouter()

    # ──────────────────────────────────────────────────────────────
    # LIST
    # ──────────────────────────────────────────────────────────────
    @router.get("/group-blocks/{property_id}")
    async def list_blocks(property_id: str, status: str = "",
                          search: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {"property_id": property_id}
        if status:
            q["status"] = status
        if search:
            q["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"code": {"$regex": search, "$options": "i"}},
                {"contact_name": {"$regex": search, "$options": "i"}},
            ]
        rows = await db.group_blocks.find(q, {"_id": 0}) \
            .sort("from_date", -1).to_list(500)
        # Enrich each block with room_type names
        if rows:
            room_types = await db.room_types.find(
                {}, {"_id": 0, "id": 1, "name": 1}
            ).to_list(500)
            rt_map = {r["id"]: r["name"] for r in room_types}
            for b in rows:
                total = 0
                for a in b.get("allocations") or []:
                    a["room_type_name"] = rt_map.get(a.get("room_type_id"), "—")
                    total += int(a.get("quantity") or 0)
                b["rooms_blocked"] = total
        # Stats for header chips
        stats_pipeline = [
            {"$match": {"property_id": property_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        agg = await db.group_blocks.aggregate(stats_pipeline).to_list(10)
        stats = {a["_id"]: a["count"] for a in agg}
        return {"rows": rows, "count": len(rows), "stats": stats}

    @router.get("/group-blocks/{property_id}/{block_id}")
    async def get_block(property_id: str, block_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        row = await db.group_blocks.find_one({"id": block_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "Block not found")
        return row

    # ──────────────────────────────────────────────────────────────
    # CREATE
    # ──────────────────────────────────────────────────────────────
    @router.post("/group-blocks/{property_id}")
    async def create_block(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        required = ["name", "from_date", "to_date"]
        for f in required:
            if not data.get(f):
                raise HTTPException(400, f"{f} required")
        try:
            d_from = date_cls.fromisoformat(data["from_date"])
            d_to = date_cls.fromisoformat(data["to_date"])
        except ValueError:
            raise HTTPException(400, "dates must be YYYY-MM-DD")
        if d_to <= d_from:
            raise HTTPException(400, "to_date must be after from_date")

        allocations = data.get("allocations") or []
        if allocations:
            for a in allocations:
                if not a.get("room_type_id") or int(a.get("quantity") or 0) < 1:
                    raise HTTPException(400, "each allocation needs room_type_id and quantity >= 1")

        now = datetime.now(timezone.utc).isoformat()
        code = (data.get("code") or "").upper() or f"GRP-{uuid.uuid4().hex[:6].upper()}"
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "name": data["name"],
            "code": code,
            "from_date": data["from_date"],
            "to_date": data["to_date"],
            "cutoff_date": data.get("cutoff_date", ""),
            "nights": (d_to - d_from).days,
            "status": data.get("status", "tentative"),
            "allocations": [{
                "room_type_id": a["room_type_id"],
                "quantity": int(a["quantity"]),
                "rate": float(a.get("rate") or 0),
            } for a in allocations],
            "contact_name": data.get("contact_name", ""),
            "contact_email": data.get("contact_email", ""),
            "contact_phone": data.get("contact_phone", ""),
            "company": data.get("company", ""),
            "notes": data.get("notes", ""),
            "version": 1,
            "created_at": now,
            "created_by": current_user.get("email", ""),
            "updated_at": now,
        }
        await db.group_blocks.insert_one(doc)
        doc.pop("_id", None)
        return doc

    # ──────────────────────────────────────────────────────────────
    # UPDATE
    # ──────────────────────────────────────────────────────────────
    @router.put("/group-blocks/{block_id}")
    async def update_block(block_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"name", "code", "from_date", "to_date", "cutoff_date",
                   "status", "allocations", "contact_name", "contact_email",
                   "contact_phone", "company", "notes"}
        patch = {k: v for k, v in data.items() if k in allowed}
        if not patch:
            raise HTTPException(400, "No valid fields")
        if "status" in patch and patch["status"] not in ("tentative", "definite", "cancelled"):
            raise HTTPException(400, "status must be tentative|definite|cancelled")
        if "allocations" in patch:
            for a in patch["allocations"]:
                if not a.get("room_type_id") or int(a.get("quantity") or 0) < 1:
                    raise HTTPException(400, "each allocation needs room_type_id and quantity >= 1")
            patch["allocations"] = [{
                "room_type_id": a["room_type_id"],
                "quantity": int(a["quantity"]),
                "rate": float(a.get("rate") or 0),
            } for a in patch["allocations"]]
        # Recompute nights if dates updated
        if "from_date" in patch or "to_date" in patch:
            existing = await db.group_blocks.find_one({"id": block_id}, {"_id": 0})
            if not existing:
                raise HTTPException(404, "Block not found")
            try:
                d_from = date_cls.fromisoformat(patch.get("from_date", existing["from_date"]))
                d_to = date_cls.fromisoformat(patch.get("to_date", existing["to_date"]))
            except ValueError:
                raise HTTPException(400, "dates must be YYYY-MM-DD")
            if d_to <= d_from:
                raise HTTPException(400, "to_date must be after from_date")
            patch["nights"] = (d_to - d_from).days
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        patch["updated_by"] = current_user.get("email", "")
        res = await db.group_blocks.update_one(
            {"id": block_id},
            {"$set": patch, "$inc": {"version": 1}}
        )
        if not res.matched_count:
            raise HTTPException(404, "Block not found")
        return {"status": "updated", "patch": {k: patch[k] for k in patch if k not in ("updated_at",)}}

    # ──────────────────────────────────────────────────────────────
    # CANCEL / DELETE
    # ──────────────────────────────────────────────────────────────
    @router.delete("/group-blocks/{block_id}")
    async def cancel_block(block_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        # Soft-cancel by default (keeps audit trail)
        res = await db.group_blocks.update_one(
            {"id": block_id},
            {"$set": {"status": "cancelled",
                      "cancelled_at": datetime.now(timezone.utc).isoformat(),
                      "cancelled_by": current_user.get("email", "")},
             "$inc": {"version": 1}}
        )
        if not res.matched_count:
            raise HTTPException(404, "Block not found")
        return {"status": "cancelled"}

    @router.delete("/group-blocks/{block_id}/hard")
    async def hard_delete_block(block_id: str,
                                current_user: dict = Depends(require_roles("admin"))):
        res = await db.group_blocks.delete_one({"id": block_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    # ──────────────────────────────────────────────────────────────
    # MATERIALIZE — convert block allocations into actual bookings
    # ──────────────────────────────────────────────────────────────
    @router.post("/group-blocks/{block_id}/materialize")
    async def materialize(block_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        block = await db.group_blocks.find_one({"id": block_id}, {"_id": 0})
        if not block:
            raise HTTPException(404, "Block not found")
        if block.get("status") == "cancelled":
            raise HTTPException(400, "Cannot materialize a cancelled block")

        created: List[Dict] = []
        now = datetime.now(timezone.utc).isoformat()
        for alloc in block.get("allocations") or []:
            qty = int(alloc.get("quantity") or 0)
            for i in range(qty):
                booking = {
                    "id": str(uuid.uuid4()),
                    "property_id": block["property_id"],
                    "guest_name": f"{block['name']} #{i + 1}",
                    "guest_email": block.get("contact_email", ""),
                    "room_type_id": alloc["room_type_id"],
                    "check_in": block["from_date"],
                    "check_out": block["to_date"],
                    "nights": block.get("nights") or 1,
                    "total_amount": float(alloc.get("rate") or 0) * (block.get("nights") or 1),
                    "channel": "direct_group",
                    "status": "confirmed" if block.get("status") == "definite" else "pending",
                    "group_block_id": block_id,
                    "group_block_code": block.get("code"),
                    "created_at": now,
                    "created_by": current_user.get("email", ""),
                }
                await db.bookings.insert_one(booking)
                booking.pop("_id", None)
                created.append(booking)
        # Mark block as materialized
        await db.group_blocks.update_one(
            {"id": block_id},
            {"$set": {"materialized": True, "materialized_at": now,
                      "materialized_count": len(created)},
             "$inc": {"version": 1}}
        )
        return {"status": "ok", "bookings_created": len(created)}

    return router
