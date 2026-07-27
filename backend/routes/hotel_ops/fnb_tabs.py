"""
F&B Tab Transfer — Cross-outlet guest tab management.

Workflow:
  1. Guest opens tab at Pool Bar (lunch drinks).
  2. Moves to Restaurant for dinner — staff transfers tab.
  3. Items added at restaurant.
  4. End of evening: tab charged to guest's room folio (via guest_id linkage)
     OR settled with cash/card.

Why beat competitors:
  Cloudbeds POS: tabs are per-outlet, no transfer.
  Mews: separate POS module, manual reconciliation.
  Opera Symphony: requires F&B Genie module ($$$$).
  Us: native cross-outlet transfers + room folio link in 1 endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


VALID_OUTLETS = {"bar", "pool_bar", "restaurant", "rooftop", "spa", "poolside", "lounge", "in_room"}
VALID_PAYMENTS = {"cash", "card", "room_folio", "complimentary", "voucher"}


class OpenTabReq(BaseModel):
    property_id: str
    outlet: str
    guest_name: Optional[str] = None
    booking_id: Optional[str] = None    # for room-folio billing
    table_number: Optional[str] = None
    server_id: Optional[str] = None
    party_size: int = 1


class AddItemReq(BaseModel):
    name: str
    qty: float = 1
    unit_price: float
    category: Optional[str] = None      # food | beverage | dessert | other
    pos_item_id: Optional[str] = None
    note: Optional[str] = None


class TransferReq(BaseModel):
    new_outlet: str
    new_table_number: Optional[str] = None
    new_server_id: Optional[str] = None


class CloseReq(BaseModel):
    payment_method: str
    tip_amount: float = 0
    discount_pct: float = 0
    apply_loyalty: bool = False


async def _loyalty_fnb_discount(db, booking_id: str) -> Optional[dict]:
    """Booking → guest tier → tier benefits içindeki F&B indirim yüzdesi."""
    import re
    bk = await db.bookings.find_one({"id": booking_id},
                                    {"_id": 0, "guest_email": 1, "guest_name": 1})
    if not bk or not bk.get("guest_email"):
        return None
    prof = await db.guest_profiles.find_one({"email": bk["guest_email"]}, {"_id": 0, "id": 1})
    if not prof:
        return None
    gt = await db.loyalty_guest_tiers.find_one({"guest_id": prof["id"]},
                                               {"_id": 0, "tier_key": 1, "property_id": 1})
    if not gt:
        return None
    cfg = await db.loyalty_tier_configs.find_one({"property_id": gt.get("property_id")},
                                                 {"_id": 0, "tiers": 1}) or {}
    tier = next((t for t in cfg.get("tiers", []) if t.get("tier_key") == gt["tier_key"]), None)
    if not tier:
        return None
    pct = 0
    for b in tier.get("benefits", []):
        m = re.search(r"(\d+)\s*%\s*F&B", b, re.I)
        if m:
            pct = max(pct, int(m.group(1)))
    return {"tier_key": gt["tier_key"], "tier_name": tier.get("name"),
            "discount_pct": pct, "guest_name": bk.get("guest_name")}


def create_fnb_tabs_router(db, require_roles):
    router = APIRouter()

    @router.post("/fnb/tabs")
    async def open_tab(req: OpenTabReq,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        if req.outlet not in VALID_OUTLETS:
            raise HTTPException(400, f"outlet must be one of {sorted(VALID_OUTLETS)}")
        if req.party_size < 1 or req.party_size > 50:
            raise HTTPException(400, "party_size must be 1..50")

        if req.booking_id:
            bk = await db.bookings.find_one({"id": req.booking_id}, {"_id": 0, "guest_name": 1})
            if not bk:
                raise HTTPException(404, "Booking not found")

        now = datetime.now(timezone.utc).isoformat()
        tab_id = str(uuid.uuid4())
        ref = f"TAB-{datetime.now(timezone.utc).strftime('%y%m%d-%H%M%S')}-{tab_id[:4].upper()}"
        doc = {
            "id": tab_id,
            "ref": ref,
            "property_id": req.property_id,
            "outlet": req.outlet,
            "guest_name": req.guest_name,
            "booking_id": req.booking_id,
            "table_number": req.table_number,
            "server_id": req.server_id or current_user.get("email"),
            "party_size": req.party_size,
            "status": "open",
            "items": [],
            "subtotal": 0,
            "tip_amount": 0,
            "discount_pct": 0,
            "discount_amount": 0,
            "total": 0,
            "transfer_history": [{"at": now, "outlet": req.outlet, "by": current_user.get("email")}],
            "opened_at": now,
            "opened_by": current_user.get("email"),
        }
        await db.fnb_tabs.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/fnb/tabs/{property_id}")
    async def list_tabs(property_id: str, status: Optional[str] = "open", outlet: Optional[str] = None,
                        limit: int = 100,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        q = {"property_id": property_id}
        if status:
            q["status"] = status
        if outlet:
            q["outlet"] = outlet
        rows = await db.fnb_tabs.find(q, {"_id": 0}).sort("opened_at", -1).limit(limit).to_list(limit)
        # Counts
        agg = await db.fnb_tabs.aggregate([
            {"$match": {"property_id": property_id, "status": "open"}},
            {"$group": {"_id": "$outlet", "count": {"$sum": 1}, "total_value": {"$sum": "$total"}}},
        ]).to_list(50)
        by_outlet = {a["_id"]: {"count": a["count"], "total_value": round(a.get("total_value") or 0, 2)} for a in agg}
        return {"rows": rows, "count": len(rows), "by_outlet": by_outlet}

    @router.get("/fnb/tabs/detail/{tab_id}")
    async def tab_detail(tab_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        tab = await db.fnb_tabs.find_one({"id": tab_id}, {"_id": 0})
        if not tab:
            raise HTTPException(404, "Tab not found")
        return tab

    @router.post("/fnb/tabs/{tab_id}/items")
    async def add_item(tab_id: str, item: AddItemReq,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        tab = await db.fnb_tabs.find_one({"id": tab_id}, {"_id": 0})
        if not tab:
            raise HTTPException(404, "Tab not found")
        if tab["status"] != "open":
            raise HTTPException(400, f"Cannot add to {tab['status']} tab")
        if item.qty <= 0:
            raise HTTPException(400, "qty must be > 0")
        if item.unit_price < 0:
            raise HTTPException(400, "unit_price must be >= 0")

        line_total = round(item.qty * item.unit_price, 2)
        new_item = {
            "id": str(uuid.uuid4()),
            "name": item.name,
            "qty": item.qty,
            "unit_price": item.unit_price,
            "line_total": line_total,
            "category": item.category or "other",
            "pos_item_id": item.pos_item_id,
            "note": item.note,
            "outlet": tab["outlet"],
            "added_at": datetime.now(timezone.utc).isoformat(),
            "added_by": current_user.get("email"),
        }
        items = tab.get("items", []) + [new_item]
        subtotal = round(sum(it["line_total"] for it in items), 2)
        total = round(subtotal - tab.get("discount_amount", 0) + tab.get("tip_amount", 0), 2)
        await db.fnb_tabs.update_one(
            {"id": tab_id},
            {"$set": {"items": items, "subtotal": subtotal, "total": total, "updated_at": new_item["added_at"]}}
        )
        return {"item": new_item, "subtotal": subtotal, "total": total, "items_count": len(items)}

    @router.delete("/fnb/tabs/{tab_id}/items/{item_id}")
    async def remove_item(tab_id: str, item_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager", "fnb"))):
        tab = await db.fnb_tabs.find_one({"id": tab_id}, {"_id": 0})
        if not tab:
            raise HTTPException(404, "Tab not found")
        if tab["status"] != "open":
            raise HTTPException(400, f"Cannot remove from {tab['status']} tab")
        items = [it for it in tab.get("items", []) if it.get("id") != item_id]
        if len(items) == len(tab.get("items", [])):
            raise HTTPException(404, "Item not found")
        subtotal = round(sum(it["line_total"] for it in items), 2)
        total = round(subtotal - tab.get("discount_amount", 0) + tab.get("tip_amount", 0), 2)
        await db.fnb_tabs.update_one(
            {"id": tab_id},
            {"$set": {"items": items, "subtotal": subtotal, "total": total}}
        )
        return {"removed": True, "subtotal": subtotal, "total": total}

    @router.post("/fnb/tabs/{tab_id}/transfer")
    async def transfer_tab(tab_id: str, req: TransferReq,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        if req.new_outlet not in VALID_OUTLETS:
            raise HTTPException(400, f"new_outlet must be one of {sorted(VALID_OUTLETS)}")
        tab = await db.fnb_tabs.find_one({"id": tab_id}, {"_id": 0})
        if not tab:
            raise HTTPException(404, "Tab not found")
        if tab["status"] != "open":
            raise HTTPException(400, f"Cannot transfer {tab['status']} tab")
        if tab["outlet"] == req.new_outlet:
            raise HTTPException(400, "Already at this outlet")

        now = datetime.now(timezone.utc).isoformat()
        history = tab.get("transfer_history", []) + [{
            "at": now,
            "from_outlet": tab["outlet"],
            "outlet": req.new_outlet,
            "by": current_user.get("email"),
        }]
        patch = {
            "outlet": req.new_outlet,
            "table_number": req.new_table_number,
            "server_id": req.new_server_id or current_user.get("email"),
            "transfer_history": history,
            "updated_at": now,
        }
        await db.fnb_tabs.update_one({"id": tab_id}, {"$set": patch})
        # Audit log
        await db.fnb_transfers.insert_one({
            "id": str(uuid.uuid4()),
            "tab_id": tab_id,
            "tab_ref": tab["ref"],
            "from_outlet": tab["outlet"],
            "to_outlet": req.new_outlet,
            "items_count": len(tab.get("items", [])),
            "tab_total_at_transfer": tab.get("total", 0),
            "transferred_at": now,
            "transferred_by": current_user.get("email"),
            "property_id": tab["property_id"],
        })
        return {"transferred": True, "from": tab["outlet"], "to": req.new_outlet, "history_len": len(history)}

    @router.get("/fnb/tabs/{tab_id}/loyalty-discount")
    async def loyalty_discount(tab_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        tab = await db.fnb_tabs.find_one({"id": tab_id}, {"_id": 0, "booking_id": 1})
        if not tab:
            raise HTTPException(404, "Tab not found")
        if not tab.get("booking_id"):
            return {"eligible": False, "reason": "no_booking"}
        info = await _loyalty_fnb_discount(db, tab["booking_id"])
        if not info:
            return {"eligible": False, "reason": "no_tier"}
        return {"eligible": True, **info}

    @router.post("/fnb/tabs/{tab_id}/close")
    async def close_tab(tab_id: str, req: CloseReq,
                        current_user: dict = Depends(require_roles("admin", "manager", "receptionist", "fnb"))):
        if req.payment_method not in VALID_PAYMENTS:
            raise HTTPException(400, f"payment_method must be one of {sorted(VALID_PAYMENTS)}")
        if req.discount_pct < 0 or req.discount_pct > 50:
            raise HTTPException(400, "discount_pct must be 0..50")
        if req.tip_amount < 0:
            raise HTTPException(400, "tip_amount must be >= 0")

        tab = await db.fnb_tabs.find_one({"id": tab_id}, {"_id": 0})
        if not tab:
            raise HTTPException(404, "Tab not found")
        if tab["status"] != "open":
            raise HTTPException(400, f"Tab already {tab['status']}")

        if req.payment_method == "room_folio" and not tab.get("booking_id"):
            raise HTTPException(400, "Cannot charge to room folio: no booking linked")

        loyalty = None
        if req.apply_loyalty and tab.get("booking_id"):
            loyalty = await _loyalty_fnb_discount(db, tab["booking_id"])
        effective_pct = req.discount_pct
        if loyalty and loyalty.get("discount_pct", 0) > effective_pct:
            effective_pct = loyalty["discount_pct"]

        subtotal = tab.get("subtotal", 0)
        discount_amount = round(subtotal * effective_pct / 100, 2)
        total = round(subtotal - discount_amount + req.tip_amount, 2)

        now = datetime.now(timezone.utc).isoformat()
        patch = {
            "status": "closed",
            "discount_pct": effective_pct,
            "loyalty_tier": loyalty.get("tier_key") if loyalty else None,
            "loyalty_tier_name": loyalty.get("tier_name") if loyalty else None,
            "loyalty_discount_pct": loyalty.get("discount_pct") if loyalty else 0,
            "discount_amount": discount_amount,
            "tip_amount": req.tip_amount,
            "total": total,
            "payment_method": req.payment_method,
            "closed_at": now,
            "closed_by": current_user.get("email"),
        }
        await db.fnb_tabs.update_one({"id": tab_id}, {"$set": patch})

        # Charge to guest folio
        if req.payment_method == "room_folio":
            charge_doc = {
                "id": str(uuid.uuid4()),
                "booking_id": tab["booking_id"],
                "type": "fnb_tab",
                "ref": tab["ref"],
                "outlet": tab["outlet"],
                "amount": total,
                "currency": "GBP",
                "description": f"F&B Tab {tab['ref']} ({tab['outlet']}, {len(tab.get('items', []))} items)",
                "created_at": now,
                "created_by": current_user.get("email"),
            }
            await db.guest_folio_charges.insert_one(charge_doc)

        return {"closed": True, "total": total, "payment_method": req.payment_method,
                "charged_to_folio": req.payment_method == "room_folio",
                "loyalty_applied": bool(loyalty and loyalty.get("discount_pct", 0) > 0),
                "loyalty_tier": loyalty.get("tier_name") if loyalty else None,
                "effective_discount_pct": effective_pct}

    @router.get("/fnb/tabs/transfers/{property_id}")
    async def list_transfers(property_id: str, limit: int = 100,
                             current_user: dict = Depends(require_roles("admin", "manager", "fnb"))):
        rows = await db.fnb_transfers.find({"property_id": property_id}, {"_id": 0}).sort("transferred_at", -1).limit(limit).to_list(limit)
        return {"rows": rows, "count": len(rows)}

    @router.get("/fnb/tabs/dashboard/{property_id}")
    async def dashboard(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        # Today's stats
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        open_tabs = await db.fnb_tabs.count_documents({"property_id": property_id, "status": "open"})
        closed_today = await db.fnb_tabs.find({
            "property_id": property_id,
            "status": "closed",
            "closed_at": {"$gte": today_start},
        }, {"_id": 0, "total": 1, "outlet": 1, "payment_method": 1, "tip_amount": 1}).to_list(2000)

        revenue_today = sum(t.get("total") or 0 for t in closed_today)
        tips_today = sum(t.get("tip_amount") or 0 for t in closed_today)
        by_outlet = {}
        by_payment = {}
        for t in closed_today:
            o = t.get("outlet")
            by_outlet[o] = by_outlet.get(o, 0) + (t.get("total") or 0)
            p = t.get("payment_method")
            by_payment[p] = by_payment.get(p, 0) + (t.get("total") or 0)
        # Today's transfers
        transfers_today = await db.fnb_transfers.count_documents({
            "property_id": property_id,
            "transferred_at": {"$gte": today_start},
        })
        return {
            "open_tabs": open_tabs,
            "closed_today": len(closed_today),
            "revenue_today": round(revenue_today, 2),
            "tips_today": round(tips_today, 2),
            "transfers_today": transfers_today,
            "by_outlet_today": {k: round(v, 2) for k, v in by_outlet.items()},
            "by_payment_today": {k: round(v, 2) for k, v in by_payment.items()},
        }

    return router
