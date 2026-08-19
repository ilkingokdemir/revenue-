"""Web Sitesi Oluşturucu — şablonlu otel sitesi, tek tık yayınlama (Cloudbeds Websites paritesi)."""
import os
import uuid
import requests as _requests
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "myhotelbox"
_storage_key = None


def _init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    r = _requests.post(f"{STORAGE_URL}/init",
                       json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _put_object(path: str, data: bytes, content_type: str) -> dict:
    key = _init_storage()
    r = _requests.put(f"{STORAGE_URL}/objects/{path}",
                      headers={"X-Storage-Key": key, "Content-Type": content_type},
                      data=data, timeout=120)
    if r.status_code == 404:
        key = _init_storage(force=True)
        r = _requests.put(f"{STORAGE_URL}/objects/{path}",
                          headers={"X-Storage-Key": key, "Content-Type": content_type},
                          data=data, timeout=120)
    r.raise_for_status()
    return r.json()


def _get_object(path: str):
    key = _init_storage()
    r = _requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if r.status_code == 404:
        key = _init_storage(force=True)
        r = _requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


TEMPLATES = [
    {"id": "classic", "name": "Klasik", "desc": "Sıcak tonlar, geleneksel otel havası"},
    {"id": "modern", "name": "Modern", "desc": "Koyu zemin, keskin tipografi"},
    {"id": "boutique", "name": "Butik", "desc": "Zarif, minimal, yüksek beyaz alan"},
]


def create_site_builder_router(db, require_roles):
    router = APIRouter(prefix="/site-builder", tags=["site-builder"])
    ROLES = ("admin", "manager")

    @router.get("/templates")
    async def templates(_u: dict = Depends(require_roles(*ROLES))):
        return {"templates": TEMPLATES}

    @router.post("/{pid}/photos")
    async def upload_photo(pid: str, kind: str = "gallery", file: UploadFile = File(...),
                           _u: dict = Depends(require_roles(*ROLES))):
        """Kapak (kind=cover) veya galeri (kind=gallery) fotoğrafı yükle — Emergent Object Storage."""
        if kind not in ("cover", "gallery"):
            raise HTTPException(422, "kind: cover|gallery")
        ext = (file.filename or "img").rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            raise HTTPException(400, "Sadece jpg/png/webp/gif")
        data = await file.read()
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(400, "Maksimum 8MB")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "gif": "image/gif"}[ext]
        photo_id = str(uuid.uuid4())
        path = f"{APP_NAME}/sites/{pid}/{photo_id}.{ext}"
        try:
            result = _put_object(path, data, mime)
        except Exception as e:
            raise HTTPException(502, f"Depolama hatası: {str(e)[:120]}")
        doc = {"id": photo_id, "property_id": pid, "kind": kind,
               "storage_path": result["path"], "content_type": mime,
               "original_filename": file.filename, "size": result.get("size", len(data)),
               "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat()}
        await db.site_photos.insert_one({**doc})
        if kind == "cover":
            await db.site_photos.update_many(
                {"property_id": pid, "kind": "cover", "id": {"$ne": photo_id}},
                {"$set": {"is_deleted": True}})
        return {"ok": True, "photo": {"id": photo_id, "kind": kind,
                                      "url": f"/api/site-builder/photo/{photo_id}"}}

    @router.get("/photo/{photo_id}")
    async def get_photo(photo_id: str):
        """Public fotoğraf servis — site sayfası ve panel img src için."""
        rec = await db.site_photos.find_one({"id": photo_id, "is_deleted": False}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Fotoğraf yok")
        try:
            data, ct = _get_object(rec["storage_path"])
        except Exception:
            raise HTTPException(502, "Depolamadan okunamadı")
        return Response(content=data, media_type=rec.get("content_type", ct),
                        headers={"Cache-Control": "public, max-age=3600"})

    @router.delete("/{pid}/photos/{photo_id}")
    async def delete_photo(pid: str, photo_id: str, _u: dict = Depends(require_roles(*ROLES))):
        r = await db.site_photos.update_one({"id": photo_id, "property_id": pid},
                                            {"$set": {"is_deleted": True}})
        if r.matched_count == 0:
            raise HTTPException(404, "Fotoğraf yok")
        return {"ok": True}

    async def _photos(pid: str):
        rows = await db.site_photos.find({"property_id": pid, "is_deleted": False},
                                         {"_id": 0, "id": 1, "kind": 1}).sort("created_at", 1).to_list(30)
        return [{"id": p["id"], "kind": p["kind"], "url": f"/api/site-builder/photo/{p['id']}"} for p in rows]

    @router.get("/{pid}")
    async def get_site(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0}) or {"property_id": pid, "template": "classic", "published": False, "content": {}}
        return {"site": cfg, "templates": TEMPLATES, "photos": await _photos(pid)}

    @router.post("/{pid}")
    async def save_site(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        tpl = data.get("template", "classic")
        if tpl not in {t["id"] for t in TEMPLATES}:
            raise HTTPException(422, "Geçersiz şablon")
        content = data.get("content") or {}
        if isinstance(content.get("amenities"), list):
            content["amenities"] = ", ".join(str(x) for x in content["amenities"])
        for k in ("headline", "about", "amenities", "phone", "email", "address",
                  "seo_title", "seo_description", "seo_keywords"):
            if k in content and not isinstance(content[k], str):
                content[k] = str(content[k])
        upd = {"property_id": pid, "template": tpl, "content": content,
               "published": bool(data.get("published")),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.hotel_sites.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, "published": upd["published"], "url": f"/site/{pid}"}

    @router.get("/public/site/{pid}")
    async def public_site(pid: str):
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0})
        if not cfg or not cfg.get("published"):
            raise HTTPException(404, "Site yayında değil")
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1, "city": 1, "country": 1}) or {}
        rts = await db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1, "base_rate": 1, "base_price": 1}).to_list(20)
        photos = await db.site_photos.find({"property_id": pid, "is_deleted": False},
                                           {"_id": 0, "id": 1, "kind": 1}).sort("created_at", 1).to_list(30)
        return {"site": cfg, "property": prop, "room_types": rts,
                "photos": [{"id": p["id"], "kind": p["kind"], "url": f"/api/site-builder/photo/{p['id']}"} for p in photos]}

    # ---------------- ÖZEL ALAN ADI ----------------
    @router.post("/{pid}/domain")
    async def set_domain(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        import re as _re
        domain = (data.get("domain") or "").lower().strip().replace("https://", "").replace("http://", "").rstrip("/")
        expected = (data.get("expected_target") or "").lower().strip()
        if not _re.match(r"^([a-z0-9-]+\.)+[a-z]{2,}$", domain):
            raise HTTPException(400, "Geçerli bir alan adı girin (örn. otelim.com)")
        taken = await db.hotel_sites.find_one({"custom_domain": domain, "property_id": {"$ne": pid}}, {"_id": 1})
        if taken:
            raise HTTPException(409, "Bu alan adı başka bir tesise bağlı")
        await db.hotel_sites.update_one({"property_id": pid}, {"$set": {
            "custom_domain": domain, "domain_status": "pending", "domain_target": expected,
            "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True, "domain": domain, "status": "pending",
                "dns_instruction": f"DNS sağlayıcınızda CNAME kaydı ekleyin: {domain} → {expected or 'uygulama adresiniz'}"}

    @router.post("/{pid}/domain/verify")
    async def verify_domain(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0, "custom_domain": 1, "domain_target": 1})
        if not cfg or not cfg.get("custom_domain"):
            raise HTTPException(400, "Önce alan adı kaydedin")
        domain, target = cfg["custom_domain"], (cfg.get("domain_target") or "").lower()
        found, status = [], "pending"
        try:
            for rtype in ("CNAME", "A"):
                r = _requests.get(f"https://dns.google/resolve?name={domain}&type={rtype}", timeout=10)
                for ans in (r.json().get("Answer") or []):
                    found.append(ans.get("data", "").rstrip(".").lower())
        except Exception as e:
            raise HTTPException(502, f"DNS sorgusu başarısız: {str(e)[:100]}")
        if target and any(target in f for f in found):
            status = "verified"
        await db.hotel_sites.update_one({"property_id": pid}, {"$set": {
            "domain_status": status, "domain_checked_at": datetime.now(timezone.utc).isoformat(),
            "domain_dns_found": found[:5]}})
        return {"ok": True, "status": status, "dns_found": found[:5],
                "note": "Doğrulandı! Alan adınız siteye yönleniyor." if status == "verified"
                else f"CNAME henüz görünmüyor. DNS'e {domain} → {target} CNAME kaydı ekleyin (yayılım 1-24 saat sürebilir)."}

    @router.delete("/{pid}/domain")
    async def remove_domain(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.hotel_sites.update_one({"property_id": pid}, {"$unset": {
            "custom_domain": "", "domain_status": "", "domain_target": "", "domain_dns_found": ""}})
        return {"ok": True}

    @router.get("/public/resolve-domain")
    async def resolve_domain(host: str):
        host = (host or "").lower().strip()
        cfg = await db.hotel_sites.find_one(
            {"custom_domain": host, "domain_status": "verified", "published": True},
            {"_id": 0, "property_id": 1})
        if not cfg:
            raise HTTPException(404, "Alan adı eşleşmedi")
        return {"property_id": cfg["property_id"]}

    # ---------------- ZİYARET İSTATİSTİĞİ ----------------
    @router.post("/public/track")
    async def track(data: dict):
        pid = (data.get("property_id") or "").strip()
        event = data.get("event")
        if not pid or event not in ("view", "cta_click"):
            raise HTTPException(422, "property_id ve event (view|cta_click) zorunlu")
        now = datetime.now(timezone.utc)
        await db.site_visits.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "event": event,
            "visitor_id": (data.get("visitor_id") or "")[:64],
            "date": now.date().isoformat(), "created_at": now.isoformat()})
        return {"ok": True}

    @router.get("/{pid}/stats")
    async def site_stats(pid: str, days: int = 30, _u: dict = Depends(require_roles(*ROLES))):
        from datetime import timedelta
        since_dt = datetime.now(timezone.utc) - timedelta(days=max(1, min(90, days)))
        since = since_dt.isoformat()
        q = {"property_id": pid, "created_at": {"$gte": since}}
        views = await db.site_visits.count_documents({**q, "event": "view"})
        clicks = await db.site_visits.count_documents({**q, "event": "cta_click"})
        uniques = len(await db.site_visits.distinct("visitor_id", {**q, "event": "view", "visitor_id": {"$ne": ""}}))
        bookings = await db.bookings.count_documents(
            {"property_id": pid, "source": "website_widget", "created_at": {"$gte": since}})
        daily = {}
        async for v in db.site_visits.find({**q, "event": "view"}, {"_id": 0, "date": 1}):
            daily[v["date"]] = daily.get(v["date"], 0) + 1
        series = sorted(daily.items())[-14:]
        return {"days": days, "views": views, "unique_visitors": uniques, "cta_clicks": clicks,
                "bookings": bookings,
                "click_rate_pct": round(min(clicks / views * 100, 100), 1) if views else 0,
                "conversion_pct": round(min(bookings / views * 100, 100), 1) if views else 0,
                "daily": [{"date": d, "views": c} for d, c in series]}

    return router
