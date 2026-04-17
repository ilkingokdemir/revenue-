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
    {"id": "bed_sheet_single", "name": "Bed Sheet (Single)"},
    {"id": "bed_sheet_double", "name": "Bed Sheet (Double)"},
    {"id": "bed_sheet_king",   "name": "Bed Sheet (King)"},
    {"id": "pillow_case",      "name": "Pillow Case"},
    {"id": "duvet_cover",      "name": "Duvet Cover"},
    {"id": "bath_towel",       "name": "Bath Towel"},
    {"id": "hand_towel",       "name": "Hand Towel"},
    {"id": "face_cloth",       "name": "Face Cloth"},
    {"id": "bath_mat",         "name": "Bath Mat"},
    {"id": "table_cloth",      "name": "Table Cloth"},
    {"id": "napkin",           "name": "Napkin"},
]

DISPATCH_STATUSES = ("pending", "sent", "received", "invoiced", "paid")


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

    # ========================= STOCK =========================
    @router.get("/laundry/stock/{property_id}")
    async def get_stock(property_id: str,
                        current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        query = {"property_id": property_id} if property_id != "all" else {}
        rows = await db.laundry_stock.find(query, {"_id": 0}).to_list(200)
        existing = {r["item_id"] for r in rows}
        for default in DEFAULT_ITEMS:
            if default["id"] not in existing:
                rows.append({
                    "item_id": default["id"], "name": default["name"], "property_id": property_id,
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
    @router.get("/laundry/contracts/{property_id}")
    async def list_contracts(property_id: str,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id} if property_id != "all" else {}
        contracts = await db.laundry_contracts.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return {"contracts": contracts}

    @router.post("/laundry/contracts/{property_id}")
    async def create_contract(property_id: str, data: Dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        vendor = (data.get("vendor") or "").strip()
        if not vendor:
            raise HTTPException(400, "Vendor required")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "vendor": vendor,
            "contact_name": data.get("contact_name", ""),
            "contact_email": data.get("contact_email", ""),
            "contact_phone": data.get("contact_phone", ""),
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
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

    # ========================= CATALOG =========================
    @router.get("/laundry/catalog")
    async def catalog(current_user: dict = Depends(require_roles("admin", "manager", "housekeeper"))):
        return {"items": DEFAULT_ITEMS}

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
        """Record a room's daily linen collection. Can pass items array for multiple lines at once."""
        date = data.get("date", datetime.now(timezone.utc).date().isoformat())
        room_id = data.get("room_id", "")
        room_number = data.get("room_number", "")
        items = data.get("items", [])
        if not items or not isinstance(items, list):
            raise HTTPException(400, "items array required")
        now = datetime.now(timezone.utc).isoformat()
        created = []
        for it in items:
            qty = int(it.get("qty", 0))
            if qty <= 0:
                continue
            doc = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "date": date,
                "room_id": room_id,
                "room_number": room_number,
                "item_id": it.get("item_id", ""),
                "item_name": it.get("item_name", ""),
                "qty": qty,
                "recorded_by": current_user.get("name", ""),
                "created_at": now,
            }
            await db.laundry_daily_usage.insert_one({**doc})
            # Also move stock from clean→dirty
            await _adjust_stock(db, property_id, it.get("item_id", ""), it.get("item_name", ""),
                                clean=-qty, dirty=qty)
            created.append(doc)
        return {"created": created, "count": len(created)}

    @router.delete("/laundry/usage/{property_id}/{usage_id}")
    async def delete_usage(property_id: str, usage_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = await db.laundry_daily_usage.find_one({"id": usage_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        # Reverse the stock adjustment
        qty = int(doc.get("qty", 0))
        await _adjust_stock(db, property_id, doc.get("item_id", ""), doc.get("item_name", ""),
                            clean=qty, dirty=-qty)
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

    return router


async def _adjust_stock(db, property_id: str, item_id: str, name: str, clean: int = 0, dirty: int = 0, in_transit: int = 0):
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
            "damaged": int(base.get("damaged", 0)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
