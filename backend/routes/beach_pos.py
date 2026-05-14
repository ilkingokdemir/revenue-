"""
Beach POS — TR sahil oteli (Antalya/Bodrum) niş modülü.

Elektra Soft'un Beach POS modülüne paralel: sunbed/şezlong numaralarına
göre içecek/yemek siparişi alma, plaja servis.

Endpoints
---------
  GET  /api/beach-pos/sunbeds/{property_id}        — list with current status
  POST /api/beach-pos/sunbeds/{property_id}        — register new sunbed
  PATCH /api/beach-pos/sunbeds/{sunbed_id}         — update label/zone/active
  POST /api/beach-pos/sunbeds/bulk-seed/{property_id} — seed N sunbeds in a row/zone
  DELETE /api/beach-pos/sunbeds/{sunbed_id}

  POST /api/beach-pos/orders                       — { sunbed_number, items[], guest_room? }
  GET  /api/beach-pos/orders/{property_id}?date=  — list orders for a date
  POST /api/beach-pos/orders/{order_id}/deliver
  POST /api/beach-pos/orders/{order_id}/cancel

  GET  /api/beach-pos/menu/{property_id}           — beach menu (food + drinks)
  POST /api/beach-pos/menu/{property_id}           — add menu item
"""
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_MENU = [
    {"category": "Soğuk İçecek", "name": "Su (50cl)", "price": 25, "sku": "BV-WATER"},
    {"category": "Soğuk İçecek", "name": "Coca-Cola", "price": 80, "sku": "BV-COKE"},
    {"category": "Soğuk İçecek", "name": "Fanta", "price": 80, "sku": "BV-FANTA"},
    {"category": "Soğuk İçecek", "name": "Taze Sıkılmış Portakal Suyu", "price": 120, "sku": "BV-OJ"},
    {"category": "Bira", "name": "Efes Pilsen", "price": 150, "sku": "BR-EFES"},
    {"category": "Bira", "name": "Tuborg", "price": 150, "sku": "BR-TUBORG"},
    {"category": "Yiyecek", "name": "Tost (Karışık)", "price": 180, "sku": "FD-TOAST"},
    {"category": "Yiyecek", "name": "Patates Kızartması", "price": 140, "sku": "FD-FRIES"},
    {"category": "Yiyecek", "name": "Karpuz Tabağı", "price": 100, "sku": "FD-WATERMELON"},
    {"category": "Dondurma", "name": "Dondurma (Tek Top)", "price": 70, "sku": "IC-ONE"},
]


def create_beach_pos_router(db, require_roles):
    router = APIRouter()

    # ============ Sunbeds ============
    @router.get("/beach-pos/sunbeds/{property_id}")
    async def list_sunbeds(property_id: str,
                           _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.beach_sunbeds.find(
            {"property_id": property_id, "is_active": True}, {"_id": 0}
        ).sort("sunbed_number", 1).to_list(500)
        # Append today's order count per sunbed
        today = _now_iso()[:10]
        orders = await db.beach_orders.find(
            {"property_id": property_id, "date": today,
             "status": {"$in": ["new", "in_progress", "delivered"]}},
            {"_id": 0, "sunbed_number": 1, "status": 1, "total": 1}
        ).to_list(1000)
        from collections import defaultdict
        agg = defaultdict(lambda: {"orders": 0, "spend": 0.0})
        for o in orders:
            agg[o["sunbed_number"]]["orders"] += 1
            agg[o["sunbed_number"]]["spend"] += float(o.get("total") or 0)
        for s in items:
            a = agg.get(s["sunbed_number"], {"orders": 0, "spend": 0.0})
            s["today_orders"] = a["orders"]
            s["today_spend"] = round(a["spend"], 2)
        return {"items": items, "count": len(items)}

    @router.post("/beach-pos/sunbeds/{property_id}")
    async def create_sunbed(property_id: str, body: dict,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        num = body.get("sunbed_number")
        if not num:
            raise HTTPException(400, "sunbed_number required")
        existing = await db.beach_sunbeds.find_one(
            {"property_id": property_id, "sunbed_number": str(num)}, {"_id": 0, "id": 1}
        )
        if existing:
            raise HTTPException(409, "Sunbed with this number exists")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "sunbed_number": str(num),
            "zone": body.get("zone", "main"),
            "label": body.get("label", f"Sunbed {num}"),
            "is_active": True,
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.beach_sunbeds.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.post("/beach-pos/sunbeds/bulk-seed/{property_id}")
    async def bulk_seed(property_id: str, body: dict,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        zone = body.get("zone", "main")
        prefix = body.get("prefix", "")
        start = int(body.get("start", 1))
        end = int(body.get("end", 20))
        if end - start > 200:
            raise HTTPException(400, "Max 200 sunbeds per seed")
        created = 0
        for i in range(start, end + 1):
            num = f"{prefix}{i}"
            ex = await db.beach_sunbeds.find_one(
                {"property_id": property_id, "sunbed_number": num}, {"_id": 0, "id": 1}
            )
            if ex:
                continue
            await db.beach_sunbeds.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "sunbed_number": num,
                "zone": zone,
                "label": f"Sunbed {num}",
                "is_active": True,
                "created_at": _now_iso(),
                "created_by": current_user.get("name", ""),
            })
            created += 1
        return {"ok": True, "created": created, "zone": zone}

    @router.patch("/beach-pos/sunbeds/{sunbed_id}")
    async def patch_sunbed(sunbed_id: str, body: dict,
                           _: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"zone", "label", "is_active"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        r = await db.beach_sunbeds.update_one({"id": sunbed_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "Not found")
        return {"ok": True}

    @router.delete("/beach-pos/sunbeds/{sunbed_id}")
    async def delete_sunbed(sunbed_id: str,
                            _: dict = Depends(require_roles("admin"))):
        r = await db.beach_sunbeds.delete_one({"id": sunbed_id})
        if not r.deleted_count:
            raise HTTPException(404, "Not found")
        return {"ok": True}

    # ============ Menu ============
    @router.get("/beach-pos/menu/{property_id}")
    async def get_menu(property_id: str,
                       _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.beach_menu.find(
            {"property_id": property_id, "is_active": True}, {"_id": 0}
        ).sort("category", 1).to_list(500)
        # Auto-seed default menu on first read
        if not items:
            seeded = []
            for d in DEFAULT_MENU:
                doc = {"id": str(uuid.uuid4()), "property_id": property_id,
                       **d, "is_active": True, "seeded": True,
                       "created_at": _now_iso()}
                seeded.append(doc)
            if seeded:
                await db.beach_menu.insert_many(seeded)
                items = [{**s} for s in seeded]
                for s in items:
                    s.pop("_id", None)
        return {"items": items, "count": len(items)}

    @router.post("/beach-pos/menu/{property_id}")
    async def add_menu(property_id: str, body: dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        name = (body.get("name") or "").strip()
        price = body.get("price")
        if not name or price is None:
            raise HTTPException(400, "name and price required")
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "category": body.get("category", "Yiyecek"),
            "name": name,
            "price": float(price),
            "sku": body.get("sku", ""),
            "is_active": True,
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.beach_menu.insert_one(doc)
        doc.pop("_id", None)
        return doc

    # ============ Orders ============
    @router.post("/beach-pos/orders")
    async def create_order(body: dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        prop = body.get("property_id")
        sunbed = body.get("sunbed_number")
        items = body.get("items") or []
        if not prop or not sunbed or not items:
            raise HTTPException(400, "property_id, sunbed_number, items required")
        # Validate sunbed exists
        sb = await db.beach_sunbeds.find_one(
            {"property_id": prop, "sunbed_number": str(sunbed), "is_active": True},
            {"_id": 0, "id": 1, "zone": 1, "label": 1},
        )
        if not sb:
            raise HTTPException(404, "Sunbed not registered")
        total = round(sum(float(i.get("price", 0)) * int(i.get("qty", 1)) for i in items), 2)
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": prop,
            "sunbed_number": str(sunbed),
            "sunbed_zone": sb.get("zone"),
            "items": items,
            "total": total,
            "currency": body.get("currency", "TRY"),
            "guest_room": body.get("guest_room"),
            "guest_booking_id": body.get("guest_booking_id"),
            "notes": body.get("notes", ""),
            "status": "new",
            "date": _now_iso()[:10],
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.beach_orders.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/beach-pos/orders/{property_id}")
    async def list_orders(property_id: str, date: str = "", status: str = "",
                          _: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        q: dict = {"property_id": property_id}
        if date:
            q["date"] = date
        else:
            q["date"] = _now_iso()[:10]
        if status:
            q["status"] = status
        items = await db.beach_orders.find(q, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(500)
        # Compute daily totals
        from collections import defaultdict
        zone_totals = defaultdict(float)
        for o in items:
            if o.get("status") != "cancelled":
                zone_totals[o.get("sunbed_zone", "main")] += float(o.get("total") or 0)
        return {"items": items, "count": len(items),
                "date": q["date"],
                "zone_totals": {z: round(v, 2) for z, v in zone_totals.items()},
                "grand_total": round(sum(zone_totals.values()), 2)}

    @router.post("/beach-pos/orders/{order_id}/deliver")
    async def deliver(order_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        r = await db.beach_orders.update_one(
            {"id": order_id, "status": {"$ne": "cancelled"}},
            {"$set": {"status": "delivered",
                      "delivered_at": _now_iso(),
                      "delivered_by": current_user.get("name", "")}}
        )
        if not r.matched_count:
            raise HTTPException(404, "Order not found or cancelled")
        return {"ok": True}

    @router.post("/beach-pos/orders/{order_id}/cancel")
    async def cancel(order_id: str, body: dict = None,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        body = body or {}
        r = await db.beach_orders.update_one(
            {"id": order_id},
            {"$set": {"status": "cancelled",
                      "cancelled_at": _now_iso(),
                      "cancelled_by": current_user.get("name", ""),
                      "cancel_reason": body.get("reason", "")}}
        )
        if not r.matched_count:
            raise HTTPException(404, "Order not found")
        return {"ok": True}

    return router
