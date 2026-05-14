"""
Public Event Listings & ROX Personalization — Tripleseat parity.

Two extensions in one module:

(A) ROX Hyper-Personalization metadata for `meeting_sale_items`:
    Adds endpoint to attach experience_type (sommelier/playlist/show/
    interactive_dining/eatertainment) + personalization_meta JSON to
    existing meeting line items.

(B) Public Event Listings (Social SEO):
    Hotels can publish confirmed/upcoming public events. These get a
    pretty public URL `/events/{slug}` (frontend) and structured data
    so they appear in Google. Backend supplies the metadata.

Endpoints
---------
ROX:
  POST  /api/mice-rox/personalize/{item_id}
        Body: {experience_type, personalization_meta?, notes?}
  GET   /api/mice-rox/catalog
        Returns curated experience catalog (Tripleseat-style)

Public events:
  POST  /api/public-events                       (admin/manager)
        Body: {meeting_id?, property_id, title, slug?, date, start_time, end_time,
               description, hero_image, capacity, ticket_url, price_from, tags[]}
  GET   /api/public-events                        (public, no auth)
        Query: property_id, upcoming_only=true
  GET   /api/public-events/{slug}                 (public, no auth)
  PATCH /api/public-events/{event_id}             (admin/manager)
  POST  /api/public-events/{event_id}/publish     (admin/manager)
  POST  /api/public-events/{event_id}/unpublish   (admin/manager)
  DELETE /api/public-events/{event_id}            (admin)
"""
from datetime import datetime, timezone
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    t = text.lower()
    repl = {"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}
    for k, v in repl.items():
        t = t.replace(k, v)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t or "event"


EXPERIENCE_CATALOG = [
    {"id": "sommelier",         "label": "Sommelier Eşliği",      "icon": "🍷",
     "default_price": 1500, "currency": "TRY",
     "description": "Sertifikalı sommelier eşliğinde özel şarap eşleştirmesi."},
    {"id": "playlist_curated",  "label": "Özel Hazırlanmış Çalma Listesi", "icon": "🎵",
     "default_price": 0, "currency": "TRY",
     "description": "Müzik küratörümüzün etkinlik temanıza özel hazırladığı çalma listesi."},
    {"id": "live_show",         "label": "Canlı Sahne Şovu",      "icon": "🎭",
     "default_price": 8000, "currency": "TRY",
     "description": "Canlı müzik, dans veya DJ performansı."},
    {"id": "interactive_dining","label": "İnteraktif Yemek Deneyimi", "icon": "🔥",
     "default_price": 2500, "currency": "TRY",
     "description": "Açık mutfak, omakase tezgâhı veya canlı pişirme istasyonu."},
    {"id": "eatertainment",     "label": "Eatertainment",          "icon": "✨",
     "default_price": 5000, "currency": "TRY",
     "description": "Yemek + tema gece + interaktif performans paketi."},
    {"id": "calligrapher",      "label": "Canlı Hat Sanatı",       "icon": "🖋️",
     "default_price": 1200, "currency": "TRY",
     "description": "Hat sanatçısı misafir adlarını oturum kartlarına yazıyor."},
    {"id": "florist_live",      "label": "Canlı Çiçek Atölyesi",   "icon": "💐",
     "default_price": 1800, "currency": "TRY",
     "description": "Misafirlere mini buket hazırlatan canlı çiçekçi istasyonu."},
    {"id": "barista_lab",       "label": "Barista Lab",            "icon": "☕",
     "default_price": 1500, "currency": "TRY",
     "description": "Specialty kahve istasyonu — V60, espresso art."},
]


def create_public_events_router(db, require_roles):
    router = APIRouter()

    # ============ ROX experience catalog ============
    @router.get("/mice-rox/catalog")
    async def catalog(_: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return {"items": EXPERIENCE_CATALOG}

    @router.post("/mice-rox/personalize/{item_id}")
    async def personalize(item_id: str, body: dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        exp_type = body.get("experience_type")
        if exp_type and exp_type not in {e["id"] for e in EXPERIENCE_CATALOG}:
            raise HTTPException(400, f"Unknown experience_type '{exp_type}'")
        update = {
            "experience_type": exp_type,
            "personalization_meta": body.get("personalization_meta", {}),
            "personalization_notes": body.get("notes", ""),
            "personalized_at": _now_iso(),
            "personalized_by": current_user.get("name", ""),
        }
        r = await db.meeting_sale_items.update_one({"id": item_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "Meeting item not found")
        return {"ok": True, **update}

    # ============ Public event listings ============
    @router.post("/public-events")
    async def create_event(body: dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        title = (body.get("title") or "").strip()
        prop = body.get("property_id")
        date = body.get("date")
        if not all([title, prop, date]):
            raise HTTPException(400, "title, property_id, date required")
        slug = (body.get("slug") or _slugify(f"{title}-{date}")).lower()
        existing = await db.public_events.find_one({"slug": slug}, {"_id": 0, "id": 1})
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": prop,
            "meeting_id": body.get("meeting_id"),
            "title": title,
            "slug": slug,
            "date": date,
            "start_time": body.get("start_time", "19:00"),
            "end_time": body.get("end_time", "23:00"),
            "description": body.get("description", ""),
            "hero_image": body.get("hero_image", ""),
            "capacity": int(body.get("capacity", 50)),
            "ticket_url": body.get("ticket_url", ""),
            "price_from": float(body.get("price_from", 0)),
            "currency": body.get("currency", "TRY"),
            "tags": body.get("tags", []),
            "experience_types": body.get("experience_types", []),
            "status": "draft",
            "is_public": False,
            "created_at": _now_iso(),
            "created_by": current_user.get("name", ""),
        }
        await db.public_events.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/public-events")
    async def list_events(property_id: str = "", upcoming_only: bool = False,
                          include_drafts: bool = False):
        q: dict = {}
        if property_id:
            q["property_id"] = property_id
        if not include_drafts:
            q["is_public"] = True
            q["status"] = "published"
        if upcoming_only:
            q["date"] = {"$gte": _now_iso()[:10]}
        items = await db.public_events.find(q, {"_id": 0}).sort(
            "date", 1
        ).to_list(500)
        # Enrich with property name
        prop_ids = list({i["property_id"] for i in items if i.get("property_id")})
        props = await db.properties.find(
            {"id": {"$in": prop_ids}}, {"_id": 0, "id": 1, "name": 1, "city": 1}
        ).to_list(200) if prop_ids else []
        pm = {p["id"]: p for p in props}
        for i in items:
            p = pm.get(i.get("property_id"), {})
            i["property_name"] = p.get("name", "")
            i["property_city"] = p.get("city", "")
        return {"items": items, "count": len(items)}

    @router.get("/public-events/{slug}")
    async def get_event(slug: str):
        ev = await db.public_events.find_one({"slug": slug}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        if not ev.get("is_public") or ev.get("status") != "published":
            raise HTTPException(404, "Event not published")
        # Enrich
        p = await db.properties.find_one(
            {"id": ev.get("property_id")}, {"_id": 0, "name": 1, "city": 1, "address": 1}
        )
        ev["property_name"] = (p or {}).get("name", "")
        ev["property_city"] = (p or {}).get("city", "")
        ev["property_address"] = (p or {}).get("address", "")
        # Structured data for SEO (JSON-LD)
        ev["structured_data"] = {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": ev["title"],
            "startDate": f"{ev['date']}T{ev.get('start_time','19:00')}:00",
            "endDate": f"{ev['date']}T{ev.get('end_time','23:00')}:00",
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {
                "@type": "Place",
                "name": ev["property_name"],
                "address": ev.get("property_address", ev["property_city"]),
            },
            "image": ev.get("hero_image", ""),
            "description": ev.get("description", ""),
            "offers": {
                "@type": "Offer",
                "url": ev.get("ticket_url", ""),
                "price": ev.get("price_from", 0),
                "priceCurrency": ev.get("currency", "TRY"),
                "availability": "https://schema.org/InStock",
            } if ev.get("price_from") else None,
        }
        return ev

    @router.patch("/public-events/{event_id}")
    async def patch_event(event_id: str, body: dict,
                          _: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"title", "description", "hero_image", "capacity", "ticket_url",
                   "price_from", "currency", "tags", "experience_types",
                   "date", "start_time", "end_time"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        update["updated_at"] = _now_iso()
        r = await db.public_events.update_one({"id": event_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "Event not found")
        return {"ok": True}

    @router.post("/public-events/{event_id}/publish")
    async def publish(event_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.public_events.update_one(
            {"id": event_id},
            {"$set": {"is_public": True, "status": "published",
                      "published_at": _now_iso(),
                      "published_by": current_user.get("name", "")}}
        )
        if not r.matched_count:
            raise HTTPException(404, "Event not found")
        return {"ok": True}

    @router.post("/public-events/{event_id}/unpublish")
    async def unpublish(event_id: str,
                        _: dict = Depends(require_roles("admin", "manager"))):
        r = await db.public_events.update_one(
            {"id": event_id},
            {"$set": {"is_public": False, "status": "draft"}}
        )
        if not r.matched_count:
            raise HTTPException(404, "Event not found")
        return {"ok": True}

    @router.delete("/public-events/{event_id}")
    async def delete_event(event_id: str,
                           _: dict = Depends(require_roles("admin"))):
        r = await db.public_events.delete_one({"id": event_id})
        if not r.deleted_count:
            raise HTTPException(404, "Event not found")
        return {"ok": True}

    return router
