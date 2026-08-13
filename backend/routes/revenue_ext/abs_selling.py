"""
Attribute-Based Selling (ABS) — oda özelliklerini (manzara, kat, balkon...)
ayrı fiyatlanabilir ürün olarak satar. Booking widget'ta misafir seçer,
gecelik ek ücret rezervasyon toplamına eklenir.

Endpoints (/api/abs/*):
- GET    /public/{property_id}        → aktif özellikler (auth yok, widget kullanır)
- GET    /{property_id}               → admin liste + 90 günlük gelir istatistiği
- POST   /{property_id}               → özellik ekle/güncelle
- DELETE /{property_id}/{attr_id}     → pasifleştir
- POST   /{property_id}/seed          → başlangıç seti
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

STARTER = [
    {"name": "Deniz manzarası", "price": 15.0, "icon": "waves", "description": "Deniz cepheli oda garantisi"},
    {"name": "Yüksek kat", "price": 8.0, "icon": "building", "description": "5. kat ve üzeri"},
    {"name": "Balkonlu oda", "price": 12.0, "icon": "sun", "description": "Özel balkon"},
    {"name": "Sessiz oda", "price": 6.0, "icon": "moon", "description": "Asansör ve sokaktan uzak"},
    {"name": "Erken check-in garantisi", "price": 10.0, "icon": "clock", "description": "12:00'de odanız hazır"},
]


def create_abs_router(db, require_roles):
    router = APIRouter(prefix="/abs", tags=["abs-selling"])

    @router.get("/public/{property_id}")
    async def public_attrs(property_id: str):
        rows = await db.abs_attributes.find(
            {"property_id": property_id, "active": {"$ne": False}},
            {"_id": 0, "id": 1, "name": 1, "price": 1, "icon": 1, "description": 1}
        ).sort("sort", 1).to_list(20)
        return {"attributes": rows}

    @router.get("/{property_id}")
    async def admin_list(property_id: str,
                         _: dict = Depends(require_roles("admin", "manager"))):
        attrs = await db.abs_attributes.find(
            {"property_id": property_id}, {"_id": 0}).sort("sort", 1).to_list(50)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        bookings = await db.bookings.find(
            {"property_id": property_id, "abs_total": {"$gt": 0},
             "created_at": {"$gte": cutoff}, "status": {"$ne": "cancelled"}},
            {"_id": 0, "abs_total": 1, "abs_attributes": 1}).to_list(2000)
        total_rev = round(sum(float(b.get("abs_total", 0) or 0) for b in bookings), 2)
        counts: Dict[str, int] = {}
        for b in bookings:
            for a in (b.get("abs_attributes") or []):
                counts[a.get("name", "?")] = counts.get(a.get("name", "?"), 0) + 1
        top = max(counts, key=counts.get) if counts else None
        return {"attributes": attrs,
                "stats": {"revenue_90d": total_rev, "bookings_with_abs": len(bookings),
                          "top_attribute": top, "attribute_counts": counts}}

    @router.post("/{property_id}")
    async def upsert(property_id: str, body: Dict,
                     _: dict = Depends(require_roles("admin", "manager"))):
        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "name gerekli")
        try:
            price = round(max(0.0, float(body.get("price", 0) or 0)), 2)
        except (TypeError, ValueError):
            raise HTTPException(400, "price sayısal olmalı")
        aid = body.get("id") or str(uuid.uuid4())
        doc = {"id": aid, "property_id": property_id, "name": name, "price": price,
               "icon": body.get("icon", "star"), "description": body.get("description", ""),
               "active": bool(body.get("active", True)), "sort": int(body.get("sort", 99) or 99),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.abs_attributes.update_one({"id": aid}, {"$set": doc}, upsert=True)
        return {"ok": True, "attribute": doc}

    @router.delete("/{property_id}/{attr_id}")
    async def deactivate(property_id: str, attr_id: str,
                         _: dict = Depends(require_roles("admin", "manager"))):
        await db.abs_attributes.update_one(
            {"id": attr_id, "property_id": property_id}, {"$set": {"active": False}})
        return {"ok": True}

    @router.post("/{property_id}/seed")
    async def seed(property_id: str,
                   _: dict = Depends(require_roles("admin", "manager"))):
        existing = await db.abs_attributes.count_documents({"property_id": property_id})
        if existing > 0:
            raise HTTPException(400, f"Zaten {existing} özellik tanımlı")
        now = datetime.now(timezone.utc).isoformat()
        docs = [{"id": str(uuid.uuid4()), "property_id": property_id, "active": True,
                 "sort": i, "updated_at": now, **s} for i, s in enumerate(STARTER)]
        await db.abs_attributes.insert_many([dict(d) for d in docs])
        for d in docs:
            d.pop("_id", None)
        return {"ok": True, "seeded": len(docs), "attributes": docs}

    return router
