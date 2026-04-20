"""
Laundry Management — Dispatches, Deliveries, Stock tracking, Contracts.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

DEFAULT_ITEMS = [
    # User's real product catalog (ref screenshot — Hotel Ops Laundry Items)
    # slug/name mirror the competitor view so housekeepers & managers see familiar labels.
    # {id(slug), name, washing_cost, purchase_cost, maintenance_cost, per_cleaning_qty, sort_order}
    {"id": "bath-mat",                 "name": "Bath Mat",                 "washing_cost": 0.50, "purchase_cost": 6.00,  "maintenance_cost": 0.05, "per_cleaning_qty": 1, "sort_order": 10},
    {"id": "bath-towel",               "name": "Bath Towel",               "washing_cost": 0.50, "purchase_cost": 8.00,  "maintenance_cost": 0.10, "per_cleaning_qty": 2, "sort_order": 20},
    {"id": "double-sheet",             "name": "Double Sheet",             "washing_cost": 1.00, "purchase_cost": 18.00, "maintenance_cost": 0.15, "per_cleaning_qty": 1, "sort_order": 30},
    {"id": "double-sheet-duvet-cover", "name": "Double Sheet Duvet Cover", "washing_cost": 1.50, "purchase_cost": 28.00, "maintenance_cost": 0.20, "per_cleaning_qty": 1, "sort_order": 40},
    {"id": "hand-towel",               "name": "Hand Towel",               "washing_cost": 0.30, "purchase_cost": 4.00,  "maintenance_cost": 0.05, "per_cleaning_qty": 2, "sort_order": 50},
    {"id": "pillow-cases",             "name": "Pillow Cases",             "washing_cost": 0.30, "purchase_cost": 4.00,  "maintenance_cost": 0.05, "per_cleaning_qty": 2, "sort_order": 60},
    {"id": "single-sheet",             "name": "Single Sheet",             "washing_cost": 0.80, "purchase_cost": 12.00, "maintenance_cost": 0.10, "per_cleaning_qty": 1, "sort_order": 70},
    {"id": "single-sheet-duvet-cover", "name": "Single Sheet Duvet Cover", "washing_cost": 1.20, "purchase_cost": 22.00, "maintenance_cost": 0.18, "per_cleaning_qty": 1, "sort_order": 80},
]

DISPATCH_STATUSES = ("pending", "sent", "received", "invoiced", "paid")


async def _seed_items_if_empty(db, property_id: str):
    """Seed default items on first request for a property (idempotent).
    Uses `laundry_item_defs` collection (distinct from `laundry_items` which tracks
    guest-laundry batches in routes/operations.py).
    """
    existing = await db.laundry_item_defs.count_documents({"property_id": property_id})
    if existing:
        return
    now = datetime.now(timezone.utc).isoformat()
    to_insert = []
    for d in DEFAULT_ITEMS:
        to_insert.append({
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "slug": d["id"],
            "name": d["name"],
            "washing_cost": float(d["washing_cost"]),
            "purchase_cost": float(d["purchase_cost"]),
            "maintenance_cost": float(d["maintenance_cost"]),
            "per_cleaning_qty": int(d["per_cleaning_qty"]),
            "sort_order": int(d["sort_order"]),
            "active": True,
            "created_at": now,
        })
    if to_insert:
        await db.laundry_item_defs.insert_many(to_insert)


async def _get_items(db, property_id: str, active_only: bool = True):
    """Return DB-backed item definitions for a property, seeding on first call."""
    await _seed_items_if_empty(db, property_id)
    q = {"property_id": property_id}
    if active_only:
        q["active"] = True
    items = await db.laundry_item_defs.find(q, {"_id": 0}).sort("sort_order", 1).to_list(500)
    return items


def create_laundry_router(db, require_roles):
    router = APIRouter()

    # ========================= DISPATCHES =========================
    @router.get("/laundry/dispatches/{property_id}")
    async def list_dispatches(property_id: str, status: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        query = {}
        if property_id != "all":
            query["property_id"] = property_id
        if status in DISPATCH_STATUSES:
            query["status"] = status
        items = await db.laundry_dispatches.find(query, {"_id": 0}).sort("sent_date", -1).to_list(200)

        kpis = {"pending": 0, "sent": 0, "received": 0, "total_items": 0, "total_cost": 0.0}
        all_q = {} if property_id == "all" else {"property_id": property_id}
        all_items = await db.laundry_dispatches.find(all_q, {"_id": 0}).to_list(1000)
        for d in all_items:
            if d.get("status") in kpis:
                kpis[d["status"]] += 1
            kpis["total_items"] += sum(i.get("qty_sent", 0) for i in d.get("items", []))
            kpis["total_cost"] += float(d.get("total_cost", 0) or 0)
        kpis["total_cost"] = round(kpis["total_cost"], 2)

        return {"dispatches": items, "kpis": kpis}

    @router.post("/laundry/dispatches/{property_id}")
    async def create_dispatch(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        vendor = (data.get("vendor") or "").strip()
        items = data.get("items", [])  # [{item_id, name, qty_sent, rate}]
        if not vendor or not items:
            raise HTTPException(400, "Vendor and items required")

        total_cost = 0.0
        normalized = []
        for i in items:
            qty = int(i.get("qty_sent", 0))
            rate = float(i.get("rate", 0))
            normalized.append({
                "item_id": i.get("item_id", ""),
                "name": i.get("name", ""),
                "qty_sent": qty,
                "qty_received": 0,
                "rate": rate,
                "line_total": round(qty * rate, 2),
            })
            total_cost += qty * rate

        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "vendor": vendor,
            "items": normalized,
            "sent_date": data.get("sent_date", now[:10]),
            "expected_return": data.get("expected_return", ""),
            "status": "sent",
            "total_cost": round(total_cost, 2),
            "notes": (data.get("notes") or "").strip(),
            "created_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.laundry_dispatches.insert_one({**doc})
        # Update stock — move from clean→in_transit
        for it in normalized:
            await _adjust_stock(db, property_id, it["item_id"], it["name"], clean=-it["qty_sent"], in_transit=it["qty_sent"])
        return doc

    @router.post("/laundry/dispatches/{property_id}/{dispatch_id}/receive")
    async def receive_dispatch(property_id: str, dispatch_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        doc = await db.laundry_dispatches.find_one({"id": dispatch_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Dispatch not found")
        received_map = {r["item_id"]: int(r.get("qty_received", 0)) for r in data.get("items", [])}
        for it in doc["items"]:
            rec = received_map.get(it["item_id"], it["qty_sent"])
            delta_in_transit = -it["qty_sent"]  # release all in-transit
            delta_clean = rec
            await _adjust_stock(db, property_id, it["item_id"], it["name"], clean=delta_clean, in_transit=delta_in_transit)
            it["qty_received"] = rec
        await db.laundry_dispatches.update_one({"id": dispatch_id}, {"$set": {
            "items": doc["items"], "status": "received",
            "received_date": datetime.now(timezone.utc).isoformat()[:10],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
        return {"ok": True}

    # ========================= DELIVERIES (RICH — MyHotelBox parity) =========================
    @router.get("/laundry/deliveries/{property_id}")
    async def list_deliveries(property_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """Return delivery history with gross/deduction/net payable + coverage %."""
        rows = await db.laundry_deliveries.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("delivery_date", -1).to_list(500)
        # Enrich with dispatch invoice numbers for UI
        dispatch_ids = list({r.get("dispatch_id") for r in rows if r.get("dispatch_id")})
        dispatches = {}
        if dispatch_ids:
            dlist = await db.laundry_dispatches.find(
                {"id": {"$in": dispatch_ids}},
                {"_id": 0, "id": 1, "dispatch_date": 1, "vendor": 1, "items": 1}
            ).to_list(len(dispatch_ids))
            for d in dlist:
                dispatches[d["id"]] = d
        for r in rows:
            disp = dispatches.get(r.get("dispatch_id") or "")
            r["dispatch_summary"] = {
                "dispatch_date": disp.get("dispatch_date") if disp else None,
                "vendor": disp.get("vendor") if disp else None,
            } if disp else None
        return {"rows": rows, "count": len(rows)}

    @router.post("/laundry/deliveries/{property_id}")
    async def create_delivery(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """Create a rich delivery record with per-item discrepancy tracking.

        Body: {
          dispatch_id (optional), delivery_date, invoice_number, notes,
          items: [{item_id, name, qty_received, qty_shortage, qty_damage,
                   qty_rejected, reason, unit_cost}]
        }
        Gross = sum(qty_received * unit_cost)
        Deduction = sum((shortage + damage + rejected) * unit_cost)
        Net Payable = Gross - Deduction
        Coverage = qty_received / dispatched_qty (if dispatch_id linked)
        """
        if not data.get("delivery_date"):
            raise HTTPException(400, "delivery_date required")
        items = data.get("items") or []
        if not items:
            raise HTTPException(400, "At least one item required")

        gross = 0.0
        deduction = 0.0
        total_received = 0
        for it in items:
            cost = float(it.get("unit_cost") or 0)
            rec = int(it.get("qty_received") or 0)
            sh  = int(it.get("qty_shortage") or 0)
            dm  = int(it.get("qty_damage") or 0)
            rj  = int(it.get("qty_rejected") or 0)
            gross     += rec * cost
            deduction += (sh + dm + rj) * cost
            total_received += rec

        # Coverage based on linked dispatch
        coverage = None
        dispatch_id = data.get("dispatch_id")
        if dispatch_id:
            disp = await db.laundry_dispatches.find_one({"id": dispatch_id}, {"_id": 0})
            if disp:
                total_sent = sum(int(i.get("qty_sent") or 0) for i in disp.get("items") or [])
                if total_sent:
                    coverage = round(total_received / total_sent * 100, 1)

        now = datetime.now(timezone.utc).isoformat()
        status = "complete" if (coverage is None or coverage >= 100) and deduction == 0 \
                 else "short" if coverage and coverage < 100 \
                 else "with_deductions"
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "dispatch_id": dispatch_id,
            "delivery_date": data["delivery_date"],
            "invoice_number": data.get("invoice_number", ""),
            "notes": data.get("notes", ""),
            "items": items,
            "gross_amount": round(gross, 2),
            "deduction_amount": round(deduction, 2),
            "net_payable": round(gross - deduction, 2),
            "coverage_pct": coverage,
            "status": status,
            "created_at": now,
            "created_by": current_user.get("email", ""),
        }
        await db.laundry_deliveries.insert_one(doc)
        doc.pop("_id", None)

        # Update stock: received -> clean, shortage/damage/rejected -> damaged counter
        for it in items:
            await _adjust_stock(db, property_id, it.get("item_id", ""), it.get("name", ""),
                                clean=int(it.get("qty_received") or 0),
                                damaged=int(it.get("qty_damage") or 0))
        # If linked dispatch, mark it received
        if dispatch_id:
            await db.laundry_dispatches.update_one(
                {"id": dispatch_id},
                {"$set": {"status": "received",
                          "received_date": data["delivery_date"],
                          "linked_delivery_id": doc["id"]}}
            )
        return doc

    @router.delete("/laundry/deliveries/{delivery_id}")
    async def delete_delivery(delivery_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.laundry_deliveries.delete_one({"id": delivery_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    # ========================= STOCK =========================
    @router.get("/laundry/stock/{property_id}")
    async def get_stock(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        query = {"property_id": property_id} if property_id != "all" else {}
        rows = await db.laundry_stock.find(query, {"_id": 0}).to_list(200)
        existing = {r["item_id"] for r in rows}
        # Seed defaults from DB-backed items if no stock row exists yet
        if property_id != "all":
            items = await _get_items(db, property_id, active_only=True)
            for it in items:
                slug = it.get("slug") or it["id"]
                if slug not in existing:
                    rows.append({
                        "item_id": slug, "name": it["name"], "property_id": property_id,
                        "on_hand_clean": 0, "dirty": 0, "in_transit": 0, "damaged": 0,
                    })
        for r in rows:
            r["total"] = int(r.get("on_hand_clean", 0)) + int(r.get("dirty", 0)) + int(r.get("in_transit", 0))
        return {"stock": sorted(rows, key=lambda x: x.get("name", ""))}

    @router.put("/laundry/stock/{property_id}/{item_id}")
    async def update_stock(property_id: str, item_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        allowed = {"on_hand_clean", "dirty", "in_transit", "damaged", "name", "par_level"}
        updates = {k: v for k, v in data.items() if k in allowed}
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Build $setOnInsert without fields already in $set to avoid MongoDB conflict
        set_on_insert = {"property_id": property_id, "item_id": item_id}
        if "name" not in updates:
            set_on_insert["name"] = data.get("name", item_id)
        await db.laundry_stock.update_one(
            {"property_id": property_id, "item_id": item_id},
            {"$set": updates, "$setOnInsert": set_on_insert},
            upsert=True,
        )
        doc = await db.laundry_stock.find_one({"property_id": property_id, "item_id": item_id}, {"_id": 0})
        return doc

    # ========================= CONTRACTS =========================
    # ========================= PROVIDERS (settings entity) =========================
    @router.get("/laundry/providers/{property_id}")
    async def list_providers(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {} if property_id == "all" else {"property_id": property_id}
        providers = await db.laundry_providers.find(query, {"_id": 0}).sort("name", 1).to_list(200)
        # Enrich each with items_count + active_contracts_count
        for p in providers:
            p["items_count"] = await db.laundry_contract_items.count_documents({"provider_id": p["id"]})
            p["active_contracts"] = await db.laundry_contracts.count_documents({
                "provider_id": p["id"], "active": True,
            })
        return {"providers": providers}

    @router.post("/laundry/providers/{property_id}")
    async def create_provider(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "name required")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "name": name,
            "contact_name": data.get("contact_name", ""),
            "contact_email": data.get("contact_email", ""),
            "contact_phone": data.get("contact_phone", ""),
            "address": data.get("address", ""),
            "notes": data.get("notes", ""),
            "status": "active",
            "created_at": now,
            "created_by": current_user.get("email", ""),
        }
        await db.laundry_providers.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/laundry/providers/{provider_id}")
    async def update_provider(provider_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"name", "contact_name", "contact_email", "contact_phone",
                   "address", "notes", "status"}
        patch = {k: v for k, v in data.items() if k in allowed}
        if not patch:
            raise HTTPException(400, "No valid fields")
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        res = await db.laundry_providers.update_one({"id": provider_id}, {"$set": patch})
        if not res.matched_count:
            raise HTTPException(404, "Provider not found")
        return {"status": "updated", "patch": patch}

    @router.delete("/laundry/providers/{provider_id}")
    async def delete_provider(provider_id: str,
                              current_user: dict = Depends(require_roles("admin"))):
        active = await db.laundry_contracts.count_documents({"provider_id": provider_id, "active": True})
        if active > 0:
            raise HTTPException(400, f"Provider has {active} active contract(s) — deactivate them first")
        res = await db.laundry_providers.delete_one({"id": provider_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    @router.get("/laundry/contracts/{property_id}")
    async def list_contracts(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id} if property_id != "all" else {}
        contracts = await db.laundry_contracts.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        # Enrich with provider name
        provider_ids = list({c.get("provider_id") for c in contracts if c.get("provider_id")})
        if provider_ids:
            providers = await db.laundry_providers.find(
                {"id": {"$in": provider_ids}}, {"_id": 0, "id": 1, "name": 1}
            ).to_list(len(provider_ids))
            pmap = {p["id"]: p["name"] for p in providers}
            for c in contracts:
                c["provider_name"] = pmap.get(c.get("provider_id") or "", c.get("vendor", ""))
        return {"contracts": contracts}

    @router.post("/laundry/contracts/{property_id}")
    async def create_contract(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        """Supports 3 pricing models (Mews/Eviivo/Cloudbeds parity):
           • per_piece  — rates[] charged per item
           • flat_rate  — flat_amount per billing period
           • hybrid     — quota (pieces included) + overage_rate (£ per piece over)
        """
        provider_id = data.get("provider_id") or ""
        vendor = (data.get("vendor") or "").strip()
        if not provider_id and not vendor:
            raise HTTPException(400, "provider_id or vendor required")
        pricing_model = data.get("pricing_model", "per_piece")
        if pricing_model not in ("per_piece", "flat_rate", "hybrid"):
            raise HTTPException(400, "pricing_model must be per_piece|flat_rate|hybrid")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "provider_id": provider_id,
            "vendor": vendor,
            "contact_name": data.get("contact_name", ""),
            "contact_email": data.get("contact_email", ""),
            "contact_phone": data.get("contact_phone", ""),
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
            "currency": data.get("currency", "GBP"),
            "pricing_model": pricing_model,
            "flat_amount": float(data.get("flat_amount") or 0),
            "quota": int(data.get("quota") or 0),
            "overage_rate": float(data.get("overage_rate") or 0),
            "billing_period": data.get("billing_period", "monthly"),
            "dispatch_days": data.get("dispatch_days") or [],
            "return_days": data.get("return_days") or [],
            "pickup_schedule": data.get("pickup_schedule", ""),
            "terms": (data.get("terms") or "").strip(),
            "rates": data.get("rates", []),  # [{item_id, name, rate}]
            "active": data.get("active", True),
            "created_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.laundry_contracts.insert_one({**doc})
        return doc

    @router.delete("/laundry/contracts/{property_id}/{contract_id}")
    async def delete_contract(property_id: str, contract_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.laundry_contracts.delete_one({"id": contract_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Contract not found")
        return {"deleted": True}

    # ========================= CATALOG (DB-backed items) =========================
    @router.get("/laundry/catalog")
    async def catalog(property_id: str = "aldgate-flats",
                      current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """Legacy catalog endpoint — returns {items: [{id,name}]} used by contract-builder UI.
        Now backed by `laundry_items` collection. `id` = stable slug (for cross-references).
        """
        items = await _get_items(db, property_id, active_only=True)
        return {"items": [{"id": it.get("slug") or it["id"], "name": it["name"]} for it in items]}

    # ========================= LAUNDRY ITEMS (full CRUD) =========================
    @router.get("/laundry/items/{property_id}")
    async def list_items(property_id: str, active_only: bool = False,
                         current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """List all laundry item definitions with usage stats (30d)."""
        items = await _get_items(db, property_id, active_only=active_only)
        # Enrich with 30d usage stats
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
        pipeline = [
            {"$match": {"property_id": property_id, "date": {"$gte": cutoff}}},
            {"$group": {"_id": "$item_id", "total_used": {"$sum": "$qty"},
                        "last_used": {"$max": "$date"}}},
        ]
        agg = await db.laundry_daily_usage.aggregate(pipeline).to_list(200)
        stats_map = {a["_id"]: a for a in agg}
        for it in items:
            slug = it.get("slug") or it["id"]
            s = stats_map.get(slug, {})
            it["usage_30d"] = int(s.get("total_used") or 0)
            it["last_used"] = s.get("last_used") or None
            # Total cost-of-ownership per piece (purchase amortized over useful life is app-specific;
            # we surface the three costs raw)
            it["total_cost"] = round(float(it.get("washing_cost") or 0) +
                                     float(it.get("purchase_cost") or 0) +
                                     float(it.get("maintenance_cost") or 0), 2)
        return {"items": items, "count": len(items)}

    @router.post("/laundry/items/{property_id}")
    async def create_item(property_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "name required")
        # Unique name per property
        dup = await db.laundry_item_defs.find_one({"property_id": property_id, "name": name})
        if dup:
            raise HTTPException(400, f"Item '{name}' already exists")
        await _seed_items_if_empty(db, property_id)
        now = datetime.now(timezone.utc).isoformat()
        slug = (data.get("slug") or name.lower().replace(" ", "_").replace("(", "").replace(")", ""))[:60]
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "slug": slug,
            "name": name,
            "washing_cost": float(data.get("washing_cost") or 0),
            "purchase_cost": float(data.get("purchase_cost") or 0),
            "maintenance_cost": float(data.get("maintenance_cost") or 0),
            "per_cleaning_qty": int(data.get("per_cleaning_qty") or 0),
            "sort_order": int(data.get("sort_order") or 999),
            "active": bool(data.get("active", True)),
            "created_at": now,
            "created_by": current_user.get("email", ""),
        }
        await db.laundry_item_defs.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/laundry/items/{item_id}")
    async def update_item(item_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"name", "washing_cost", "purchase_cost", "maintenance_cost",
                   "per_cleaning_qty", "sort_order", "active", "slug"}
        patch = {}
        for k, v in data.items():
            if k not in allowed:
                continue
            if k in ("washing_cost", "purchase_cost", "maintenance_cost"):
                patch[k] = float(v or 0)
            elif k in ("per_cleaning_qty", "sort_order"):
                patch[k] = int(v or 0)
            elif k == "active":
                patch[k] = bool(v)
            else:
                patch[k] = v
        if not patch:
            raise HTTPException(400, "No valid fields to update")
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        res = await db.laundry_item_defs.update_one({"id": item_id}, {"$set": patch})
        if not res.matched_count:
            raise HTTPException(404, "Item not found")
        updated = await db.laundry_item_defs.find_one({"id": item_id}, {"_id": 0})
        return updated

    @router.delete("/laundry/items/{item_id}")
    async def delete_item(item_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.laundry_item_defs.delete_one({"id": item_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    # ========================= ORDER FORECAST =========================
    @router.get("/laundry/forecast/{property_id}")
    async def order_forecast(property_id: str,
                             delivery_date: str = "",
                             horizon_days: int = 7,
                             in_house_cleaning_every: int = 2,
                             current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """Smart order forecast.

        Looks at bookings in [delivery_date, delivery_date + horizon_days) window and counts
        'cleaning events' per day:
          - Every arrival (new check-in) = 1 cleaning event (fresh linen for the room)
          - Every in-house stay where (day_index since check-in) % in_house_cleaning_every == 0
            and day_index > 0 = 1 cleaning event (mid-stay linen change)
        Each cleaning event consumes `per_cleaning_qty` of every active linen item.

        Returns per-item {needed, on_hand_clean, shortfall=order_qty} plus daily breakdown.
        """
        from datetime import date as _date
        today = _date.today()
        if not delivery_date:
            delivery_date = today.isoformat()
        try:
            start = datetime.fromisoformat(delivery_date).date()
        except Exception:
            raise HTTPException(400, "delivery_date must be YYYY-MM-DD")
        horizon_days = max(1, min(int(horizon_days or 7), 30))
        in_house_every = max(1, int(in_house_cleaning_every or 2))
        end = start + timedelta(days=horizon_days)
        # Pre-delivery window: from today up to (not including) delivery_date
        pre_start = min(today, start)
        pre_days = max(0, (start - pre_start).days)

        # Pull bookings overlapping the full window (pre + horizon)
        prop_q = {} if property_id == "all" else {"property_id": property_id}
        bookings = await db.bookings.find({
            **prop_q,
            "status": {"$in": ["confirmed", "pending", "checked_in"]},
            "check_in": {"$lt": end.isoformat()},
            "check_out": {"$gt": pre_start.isoformat()},
        }, {"_id": 0, "id": 1, "check_in": 1, "check_out": 1, "room_id": 1,
            "guest_name": 1, "status": 1}).to_list(2000)

        def _count_events_on_day(day):
            arrivals = 0
            in_house = 0
            for b in bookings:
                ci = b.get("check_in")
                co = b.get("check_out")
                if not ci or not co:
                    continue
                try:
                    ci_d = datetime.fromisoformat(ci).date()
                    co_d = datetime.fromisoformat(co).date()
                except Exception:
                    continue
                if ci_d == day:
                    arrivals += 1
                    continue
                if ci_d < day < co_d:
                    day_index = (day - ci_d).days
                    if day_index % in_house_every == 0:
                        in_house += 1
            return arrivals, in_house

        # Pre-delivery events (today → delivery_date-1): consumed from current stock
        pre_events = 0
        for d_offset in range(pre_days):
            day = pre_start + timedelta(days=d_offset)
            a, h = _count_events_on_day(day)
            pre_events += a + h

        # Horizon events (delivery_date → delivery_date + horizon-1): to be covered by new order
        daily = []
        total_events = 0
        for d_offset in range(horizon_days):
            day = start + timedelta(days=d_offset)
            arrivals, in_house_cleanings = _count_events_on_day(day)
            events = arrivals + in_house_cleanings
            total_events += events
            daily.append({
                "date": day.isoformat(),
                "arrivals": arrivals,
                "in_house_cleanings": in_house_cleanings,
                "events": events,
            })

        # Per-item needs
        items = await _get_items(db, property_id, active_only=True)
        # Current clean stock
        stock_rows = await db.laundry_stock.find(
            {"property_id": property_id}, {"_id": 0}
        ).to_list(500)
        stock_map = {s.get("item_id"): int(s.get("on_hand_clean") or 0) for s in stock_rows}

        per_item = []
        total_order_qty = 0
        total_order_cost = 0.0
        for it in items:
            per_clean = int(it.get("per_cleaning_qty") or 0)
            if per_clean <= 0:
                # Skip items that don't participate in a cleaning event (e.g. napkins)
                continue
            needed = per_clean * total_events
            used_before_delivery = per_clean * pre_events
            slug = it.get("slug") or it["id"]
            on_hand = stock_map.get(slug, 0)
            # Stock actually available on delivery day after today's consumption
            remaining_at_delivery = max(0, on_hand - used_before_delivery)
            shortfall = max(0, needed - remaining_at_delivery)
            washing_cost = float(it.get("washing_cost") or 0)
            per_item.append({
                "item_id": slug,
                "name": it["name"],
                "per_cleaning_qty": per_clean,
                "cleaning_events": total_events,
                "needed": needed,
                "on_hand_clean": on_hand,                      # stock NOW
                "used_before_delivery": used_before_delivery,  # consumed before delivery day
                "remaining_at_delivery": remaining_at_delivery,# available on delivery day
                "shortfall": shortfall,                        # true order requirement
                "washing_cost": round(washing_cost, 2),
                "estimated_order_cost": round(shortfall * washing_cost, 2),
            })
            total_order_qty += shortfall
            total_order_cost += shortfall * washing_cost

        per_item.sort(key=lambda x: -x["shortfall"])

        return {
            "delivery_date": start.isoformat(),
            "horizon_days": horizon_days,
            "in_house_cleaning_every": in_house_every,
            "pre_delivery_days": pre_days,
            "pre_delivery_events": pre_events,
            "bookings_in_window": len(bookings),
            "total_cleaning_events": total_events,
            "daily": daily,
            "items": per_item,
            "summary": {
                "total_order_qty": total_order_qty,
                "estimated_order_cost": round(total_order_cost, 2),
                "items_needing_order": sum(1 for i in per_item if i["shortfall"] > 0),
            },
        }

    @router.post("/laundry/forecast/{property_id}/create-dispatch")
    async def create_dispatch_from_forecast(property_id: str, data: Dict,
                                            current_user: dict = Depends(require_roles("admin", "manager"))):
        """Create a dispatch using forecast-computed shortfalls.
        Body: {vendor, delivery_date, horizon_days, in_house_cleaning_every,
               expected_return, notes, items?: [{item_id,name,qty_sent,rate}]}
        If `items` not provided, the forecast is recomputed server-side and used.
        """
        vendor = (data.get("vendor") or "").strip()
        if not vendor:
            raise HTTPException(400, "vendor required")
        items_in = data.get("items")
        if not items_in:
            # Recompute
            delivery_date = data.get("delivery_date", "")
            horizon_days = int(data.get("horizon_days") or 7)
            in_house_every = int(data.get("in_house_cleaning_every") or 2)
            fc = await order_forecast(property_id=property_id,
                                      delivery_date=delivery_date,
                                      horizon_days=horizon_days,
                                      in_house_cleaning_every=in_house_every,
                                      current_user=current_user)
            items_in = []
            items_map = {it.get("slug") or it["id"]: it for it in await _get_items(db, property_id, True)}
            for row in fc["items"]:
                if row["shortfall"] <= 0:
                    continue
                src = items_map.get(row["item_id"], {})
                items_in.append({
                    "item_id": row["item_id"],
                    "name": row["name"],
                    "qty_sent": row["shortfall"],
                    "rate": float(src.get("washing_cost") or 0),
                })
        if not items_in:
            raise HTTPException(400, "No shortfall — nothing to order")

        # Reuse the dispatch creation logic inline
        total_cost = 0.0
        normalized = []
        for i in items_in:
            qty = int(i.get("qty_sent", 0))
            rate = float(i.get("rate", 0))
            if qty <= 0:
                continue
            normalized.append({
                "item_id": i.get("item_id", ""),
                "name": i.get("name", ""),
                "qty_sent": qty,
                "qty_received": 0,
                "rate": rate,
                "line_total": round(qty * rate, 2),
            })
            total_cost += qty * rate
        if not normalized:
            raise HTTPException(400, "No items with qty > 0")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "vendor": vendor,
            "items": normalized,
            "sent_date": data.get("delivery_date") or now[:10],
            "expected_return": data.get("expected_return", ""),
            "status": "sent",
            "total_cost": round(total_cost, 2),
            "notes": data.get("notes") or "Auto-generated from Order Forecast",
            "from_forecast": True,
            "forecast_meta": {
                "horizon_days": int(data.get("horizon_days") or 7),
                "in_house_cleaning_every": int(data.get("in_house_cleaning_every") or 2),
            },
            "created_at": now,
            "created_by": current_user.get("email", ""),
        }
        await db.laundry_dispatches.insert_one({**doc})
        # Move stock clean→in_transit
        for it in normalized:
            await _adjust_stock(db, property_id, it["item_id"], it["name"],
                                clean=-it["qty_sent"], in_transit=it["qty_sent"])
        doc.pop("_id", None)
        return doc

    # ========================= DAILY USAGE =========================
    @router.get("/laundry/usage/{property_id}")
    async def list_usage(property_id: str, date: str = "", start: str = "", end: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """Per-room daily linen collection records."""
        query = {}
        if property_id != "all":
            query["property_id"] = property_id
        if date:
            query["date"] = date
        elif start and end:
            query["date"] = {"$gte": start, "$lte": end}
        rows = await db.laundry_daily_usage.find(query, {"_id": 0}).sort("date", -1).to_list(500)
        # Group by room + date for convenient display
        return {"records": rows, "count": len(rows)}

    @router.post("/laundry/usage/{property_id}")
    async def create_usage(property_id: str, data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """Record a housekeeper's per-room cleaning activity.

        Each line item now carries TWO quantities:
          - `clean_used` — fresh linen brought INTO the room (deducts from clean stock)
          - `dirty_collected` — soiled linen taken OUT of the room (adds to dirty stock)
        For backward compatibility, if only `qty` is provided, both are set to `qty`.
        """
        date = data.get("date", datetime.now(timezone.utc).date().isoformat())
        room_id = data.get("room_id", "")
        room_number = data.get("room_number", "")
        items = data.get("items", [])
        notes = (data.get("notes") or "").strip()
        if not items or not isinstance(items, list):
            raise HTTPException(400, "items array required")
        now = datetime.now(timezone.utc).isoformat()
        created = []
        for it in items:
            # Read fields, fall back to legacy `qty`
            legacy_qty = int(it.get("qty") or 0)
            clean_used = int(it.get("clean_used") if it.get("clean_used") is not None else legacy_qty)
            dirty_collected = int(it.get("dirty_collected") if it.get("dirty_collected") is not None else legacy_qty)
            factory_unusable = int(it.get("factory_unusable") or 0)   # came back unusable from laundry
            guest_damaged = int(it.get("guest_damaged") or 0)         # damaged by guest in room
            if clean_used <= 0 and dirty_collected <= 0 and factory_unusable <= 0 and guest_damaged <= 0:
                continue
            qty = dirty_collected if dirty_collected > 0 else clean_used
            doc = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "date": date,
                "room_id": room_id,
                "room_number": room_number,
                "item_id": it.get("item_id", ""),
                "item_name": it.get("item_name", ""),
                "qty": qty,                        # legacy summary field
                "clean_used": clean_used,
                "dirty_collected": dirty_collected,
                "factory_unusable": factory_unusable,
                "guest_damaged": guest_damaged,
                "notes": notes,
                "recorded_by": current_user.get("name", "") or current_user.get("email", ""),
                "created_at": now,
            }
            await db.laundry_daily_usage.insert_one({**doc})
            # Stock side-effects:
            #   clean_used    → clean stock decreases (linen brought into room)
            #   dirty_collected → dirty stock increases (soiled linen taken from room)
            #   factory_unusable → damaged increases (items came back unusable from laundry)
            #   guest_damaged → damaged increases (written off — guest ruined it)
            await _adjust_stock(
                db, property_id,
                it.get("item_id", ""), it.get("item_name", ""),
                clean=-clean_used,
                dirty=dirty_collected,
                damaged=factory_unusable + guest_damaged,
            )
            created.append(doc)
        return {"created": created, "count": len(created)}

    @router.delete("/laundry/usage/{property_id}/{usage_id}")
    async def delete_usage(property_id: str, usage_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.laundry_daily_usage.find_one({"id": usage_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        # Reverse every stock side-effect
        legacy_qty = int(doc.get("qty", 0))
        clean_used = int(doc.get("clean_used") if doc.get("clean_used") is not None else legacy_qty)
        dirty_collected = int(doc.get("dirty_collected") if doc.get("dirty_collected") is not None else legacy_qty)
        factory_unusable = int(doc.get("factory_unusable") or 0)
        guest_damaged = int(doc.get("guest_damaged") or 0)
        await _adjust_stock(
            db, property_id,
            doc.get("item_id", ""), doc.get("item_name", ""),
            clean=clean_used,
            dirty=-dirty_collected,
            damaged=-(factory_unusable + guest_damaged),
        )
        await db.laundry_daily_usage.delete_one({"id": usage_id})
        return {"deleted": True}

    # ========================= REPORTS =========================
    @router.get("/laundry/reports/{property_id}/{report_type}")
    async def reports(property_id: str, report_type: str, start: str = "", end: str = "",
                      current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """report_type: daily-usage | count | order | dispatch | monthly-audit | group-update"""
        from datetime import date as _date
        today = _date.today().isoformat()
        if not end:
            end = today
        if not start:
            start = (datetime.fromisoformat(end) - timedelta(days=30)).date().isoformat()
        prop_filter = {} if property_id == "all" else {"property_id": property_id}

        if report_type == "daily-usage":
            rows = await db.laundry_daily_usage.find(
                {"date": {"$gte": start, "$lte": end}, **prop_filter}, {"_id": 0}
            ).sort("date", -1).to_list(2000)
            by_room = {}
            by_date = {}
            for r in rows:
                rn = r.get("room_number") or r.get("room_id", "Unknown")
                by_room[rn] = by_room.get(rn, 0) + int(r.get("qty", 0))
                by_date[r.get("date", "")] = by_date.get(r.get("date", ""), 0) + int(r.get("qty", 0))
            return {"rows": rows, "by_room": by_room, "by_date": by_date, "total_items": sum(int(r.get("qty", 0)) for r in rows), "start": start, "end": end}

        if report_type == "count":
            usage = await db.laundry_daily_usage.find(
                {"date": {"$gte": start, "$lte": end}, **prop_filter}, {"_id": 0}
            ).to_list(5000)
            by_item = {}
            for u in usage:
                k = u.get("item_name") or u.get("item_id", "Unknown")
                by_item.setdefault(k, {"name": k, "total": 0, "days": set(), "rooms": set()})
                by_item[k]["total"] += int(u.get("qty", 0))
                by_item[k]["days"].add(u.get("date", ""))
                by_item[k]["rooms"].add(u.get("room_number") or u.get("room_id", ""))
            out = []
            for v in by_item.values():
                days = len(v["days"]) or 1
                daily_avg = v["total"] / days
                out.append({
                    "item": v["name"],
                    "total": v["total"],
                    "days_active": len(v["days"]),
                    "rooms_active": len(v["rooms"]),
                    "daily_avg": round(daily_avg, 1),
                    "anomaly": v["total"] > (daily_avg * days * 1.5) or (days < 3 and v["total"] > 20),
                })
            out.sort(key=lambda x: -x["total"])
            return {"items": out, "start": start, "end": end}

        if report_type == "order":
            disp = await db.laundry_dispatches.find(
                {"sent_date": {"$gte": start, "$lte": end}, **prop_filter}, {"_id": 0}
            ).to_list(500)
            by_item = {}
            for d in disp:
                for it in d.get("items", []):
                    k = it.get("name") or it.get("item_id", "Unknown")
                    by_item.setdefault(k, {"name": k, "sent": 0, "received": 0, "variance": 0})
                    by_item[k]["sent"] += int(it.get("qty_sent", 0))
                    by_item[k]["received"] += int(it.get("qty_received", 0))
            for v in by_item.values():
                v["variance"] = v["sent"] - v["received"]
            out = sorted(by_item.values(), key=lambda x: -x["sent"])
            return {"items": out, "dispatches": len(disp), "start": start, "end": end}

        if report_type == "dispatch":
            disp = await db.laundry_dispatches.find(
                {"sent_date": {"$gte": start, "$lte": end}, **prop_filter}, {"_id": 0}
            ).sort("sent_date", -1).to_list(500)
            return {
                "dispatches": disp,
                "total_cost": round(sum(float(d.get("total_cost", 0) or 0) for d in disp), 2),
                "total_items": sum(int(i.get("qty_sent", 0)) for d in disp for i in d.get("items", [])),
                "start": start, "end": end,
            }

        if report_type == "monthly-audit":
            # End-of-month reconciliation: stock snapshot + discrepancies
            stock = await db.laundry_stock.find(prop_filter, {"_id": 0}).to_list(200)
            usage_total = await db.laundry_daily_usage.find(
                {"date": {"$gte": start, "$lte": end}, **prop_filter}, {"_id": 0}
            ).to_list(5000)
            usage_by_item = {}
            for u in usage_total:
                k = u.get("item_id", "")
                usage_by_item[k] = usage_by_item.get(k, 0) + int(u.get("qty", 0))
            dispatches = await db.laundry_dispatches.find(
                {"sent_date": {"$gte": start, "$lte": end}, **prop_filter}, {"_id": 0}
            ).to_list(500)
            dispatched_by_item = {}
            for d in dispatches:
                for it in d.get("items", []):
                    k = it.get("item_id", "")
                    dispatched_by_item[k] = dispatched_by_item.get(k, 0) + int(it.get("qty_sent", 0))
            audit = []
            for s in stock:
                iid = s.get("item_id", "")
                audit.append({
                    "item": s.get("name", iid),
                    "clean": int(s.get("on_hand_clean", 0)),
                    "dirty": int(s.get("dirty", 0)),
                    "in_transit": int(s.get("in_transit", 0)),
                    "damaged": int(s.get("damaged", 0)),
                    "used_in_period": usage_by_item.get(iid, 0),
                    "dispatched_in_period": dispatched_by_item.get(iid, 0),
                    "total_inventory": int(s.get("on_hand_clean", 0)) + int(s.get("dirty", 0)) + int(s.get("in_transit", 0)),
                })
            return {"audit": audit, "start": start, "end": end}

        if report_type == "group-update":
            # Rolling cycle ledger: each event that affected stock
            usage = await db.laundry_daily_usage.find(
                {"date": {"$gte": start, "$lte": end}, **prop_filter}, {"_id": 0}
            ).to_list(2000)
            disp = await db.laundry_dispatches.find(
                {"sent_date": {"$gte": start, "$lte": end}, **prop_filter}, {"_id": 0}
            ).to_list(500)
            events = []
            for u in usage:
                events.append({"date": u.get("date", ""), "type": "usage", "item": u.get("item_name", ""), "qty": int(u.get("qty", 0)), "delta_clean": -int(u.get("qty", 0)), "delta_dirty": int(u.get("qty", 0)), "ref": u.get("room_number", "")})
            for d in disp:
                total_sent = sum(int(i.get("qty_sent", 0)) for i in d.get("items", []))
                total_recv = sum(int(i.get("qty_received", 0)) for i in d.get("items", []))
                events.append({"date": d.get("sent_date", ""), "type": "dispatch_sent", "item": d.get("vendor", ""), "qty": total_sent, "delta_clean": 0, "delta_dirty": -total_sent, "ref": d.get("vendor", "")})
                if d.get("status") == "received":
                    events.append({"date": d.get("received_date", d.get("sent_date", "")), "type": "dispatch_received", "item": d.get("vendor", ""), "qty": total_recv, "delta_clean": total_recv, "delta_dirty": 0, "ref": d.get("vendor", "")})
            events.sort(key=lambda x: x["date"], reverse=True)
            return {"events": events, "count": len(events), "start": start, "end": end}

        raise HTTPException(400, f"Unknown report_type: {report_type}")

    # ========================= STOCK TRANSACTIONS (maintenance/disposal/write-off) =========================
    @router.get("/laundry/stock-transactions/{property_id}")
    async def list_stock_txns(property_id: str, tx_type: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        q: Dict = {"property_id": property_id}
        if tx_type:
            q["tx_type"] = tx_type
        rows = await db.laundry_stock_transactions.find(
            q, {"_id": 0}
        ).sort("transaction_date", -1).to_list(500)
        # Stats by type
        pipeline = [
            {"$match": {"property_id": property_id}},
            {"$group": {
                "_id": "$tx_type",
                "count": {"$sum": 1},
                "total_qty": {"$sum": "$quantity"},
                "total_cost": {"$sum": "$total_cost"},
            }},
        ]
        agg = await db.laundry_stock_transactions.aggregate(pipeline).to_list(20)
        stats = {a["_id"]: {"count": a["count"], "qty": a["total_qty"],
                            "cost": round(a["total_cost"], 2)} for a in agg}
        return {"rows": rows, "stats": stats}

    @router.post("/laundry/stock-transactions/{property_id}")
    async def create_stock_txn(property_id: str, data: Dict,
                               current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        """Body: {item_id, name, tx_type, quantity, unit_cost, transaction_date,
                  reason?, notes?}
        tx_type: maintenance | disposal | write_off | found | stock_in | stock_out
        """
        for f in ("item_id", "tx_type", "quantity", "transaction_date"):
            if data.get(f) in (None, ""):
                raise HTTPException(400, f"{f} required")
        tx_type = data["tx_type"]
        if tx_type not in ("maintenance", "disposal", "write_off", "found",
                           "stock_in", "stock_out"):
            raise HTTPException(400, "invalid tx_type")
        qty = int(data["quantity"])
        if qty < 1:
            raise HTTPException(400, "quantity must be >= 1")
        cost = float(data.get("unit_cost") or 0)
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "item_id": data["item_id"],
            "name": data.get("name", ""),
            "tx_type": tx_type,
            "quantity": qty,
            "unit_cost": cost,
            "total_cost": round(qty * cost, 2),
            "transaction_date": data["transaction_date"],
            "reason": data.get("reason", tx_type),
            "notes": data.get("notes", ""),
            "created_at": now,
            "created_by": current_user.get("email", ""),
        }
        await db.laundry_stock_transactions.insert_one(doc)
        doc.pop("_id", None)

        # Adjust stock based on tx_type:
        # maintenance/disposal/write_off → reduce clean stock (move to damaged bucket for audit)
        # found / stock_in → add clean stock
        # stock_out → reduce clean stock
        if tx_type in ("maintenance", "disposal", "write_off"):
            await _adjust_stock(db, property_id, data["item_id"], data.get("name", ""),
                                clean=-qty, damaged=qty if tx_type == "disposal" else 0)
        elif tx_type in ("found", "stock_in"):
            await _adjust_stock(db, property_id, data["item_id"], data.get("name", ""),
                                clean=qty)
        elif tx_type == "stock_out":
            await _adjust_stock(db, property_id, data["item_id"], data.get("name", ""),
                                clean=-qty)
        return doc

    @router.delete("/laundry/stock-transactions/{txn_id}")
    async def delete_stock_txn(txn_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.laundry_stock_transactions.delete_one({"id": txn_id})
        return {"status": "deleted" if res.deleted_count else "not_found"}

    return router


async def _adjust_stock(db, property_id: str, item_id: str, name: str, clean: int = 0, dirty: int = 0, in_transit: int = 0, damaged: int = 0):
    current = await db.laundry_stock.find_one({"property_id": property_id, "item_id": item_id}, {"_id": 0})
    base = current or {"on_hand_clean": 0, "dirty": 0, "in_transit": 0, "damaged": 0}
    await db.laundry_stock.update_one(
        {"property_id": property_id, "item_id": item_id},
        {"$set": {
            "property_id": property_id,
            "item_id": item_id,
            "name": name or base.get("name", item_id),
            "on_hand_clean": max(0, int(base.get("on_hand_clean", 0)) + clean),
            "dirty": max(0, int(base.get("dirty", 0)) + dirty),
            "in_transit": max(0, int(base.get("in_transit", 0)) + in_transit),
            "damaged": max(0, int(base.get("damaged", 0)) + damaged),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
