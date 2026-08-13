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
    {"name": "Deniz manzarası", "price": 15.0, "icon": "waves", "description": "Deniz cepheli oda garantisi",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/d218cf083e5a28710c6a523f82bfd32e4f5cf2dc578ba1ce926ee009d841cf54.jpeg"},
    {"name": "Yüksek kat", "price": 8.0, "icon": "building", "description": "5. kat ve üzeri",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/5d6ffb3194a7aa43856ff4dfb26c308b97019f0e8f4d8361247c0fa06ce54bec.jpeg"},
    {"name": "Balkonlu oda", "price": 12.0, "icon": "sun", "description": "Özel balkon",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/67975259827081d4b366a05ac5f5701654d708dc6e2e9c98d0fe4685d4d74177.jpeg"},
    {"name": "Sessiz oda", "price": 6.0, "icon": "moon", "description": "Asansör ve sokaktan uzak",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/bd39a8fb258af81f5951e530f211750980c644fec74676f464116a18cba16cf6.jpeg"},
    {"name": "Erken check-in garantisi", "price": 10.0, "icon": "clock", "description": "12:00'de odanız hazır",
     "image_url": "https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/dfb0dd03dc13301730d1d8688cd7c184129e16d66daa0259896b0eee46d39667.jpeg"},
]


def create_abs_router(db, require_roles):
    router = APIRouter(prefix="/abs", tags=["abs-selling"])

    @router.get("/public/{property_id}")
    async def public_attrs(property_id: str):
        rows = await db.abs_attributes.find(
            {"property_id": property_id, "active": {"$ne": False}},
            {"_id": 0, "id": 1, "name": 1, "price": 1, "icon": 1, "description": 1, "image_url": 1}
        ).sort("sort", 1).to_list(20)
        # Akıllı sıralama: son 90 günde en çok satan özellik üstte (dönüşüm bazlı)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        counts: Dict[str, int] = {}
        async for b in db.bookings.find(
                {"property_id": property_id, "abs_total": {"$gt": 0},
                 "created_at": {"$gte": cutoff}, "status": {"$ne": "cancelled"}},
                {"_id": 0, "abs_attributes.id": 1}):
            for a in (b.get("abs_attributes") or []):
                if a.get("id"):
                    counts[a["id"]] = counts.get(a["id"], 0) + 1
        rows.sort(key=lambda r: (-counts.get(r["id"], 0), r.get("name", "")))
        for r in rows:
            if counts.get(r["id"], 0) >= 3:
                r["popular"] = True
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
               "image_url": (body.get("image_url") or "").strip(),
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
