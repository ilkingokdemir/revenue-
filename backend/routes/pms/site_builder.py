"""Web Sitesi Oluşturucu — şablonlu otel sitesi, tek tık yayınlama (Cloudbeds Websites paritesi)."""
import os
import re
from typing import Dict
import uuid
import requests as _requests
from datetime import datetime, timezone

from fastapi import Request, APIRouter, Depends, HTTPException, UploadFile, File, Response

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
    {"id": "coastal", "name": "Sahil", "desc": "Kum tonları, derin turkuaz vurgular"},
    {"id": "urban", "name": "Urban", "desc": "Antrasit zemin, amber vurgu, şehir oteli"},
    {"id": "nature", "name": "Doğa", "desc": "Krem zemin, orman yeşili, dağ/köy evi"},
]

DEFAULT_BLOCKS = [
    {"id": "hero", "enabled": True}, {"id": "availability", "enabled": True}, {"id": "about", "enabled": True},
    {"id": "rooms", "enabled": True}, {"id": "amenities", "enabled": True}, {"id": "gallery", "enabled": True},
    {"id": "reviews", "enabled": True}, {"id": "map", "enabled": True}, {"id": "faq", "enabled": True},
    {"id": "contact", "enabled": True},
]
BLOCK_IDS = {b["id"] for b in DEFAULT_BLOCKS}
SITE_PAGES = ["home", "rooms", "gallery", "location", "faq", "contact", "blog"]



TRANSLATION_KEYS = ("headline", "about", "seo_title", "seo_description", "faqs")


def _approved_translations(content: dict) -> dict:
    """Onay kilidi: yalnızca onaylanan satırlar canlı siteye çıkar; onaysız satır TR kaynağa düşer."""
    out = {}
    for lg, t in (content.get("translations") or {}).items():
        if not isinstance(t, dict):
            continue
        ap = t.get("approved") or {}
        kept = {k: v for k, v in t.items() if k in TRANSLATION_KEYS and v and ap.get(k)}
        if kept:
            out[lg] = kept
    return out

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
                  "seo_title", "seo_description", "seo_keywords", "map_query"):
            if k in content and not isinstance(content[k], str):
                content[k] = str(content[k])
        blocks = [b for b in (content.get("blocks") or []) if isinstance(b, dict) and b.get("id") in BLOCK_IDS]
        seen = {b["id"] for b in blocks}
        blocks += [b for b in DEFAULT_BLOCKS if b["id"] not in seen]
        content["blocks"] = [{"id": b["id"], "enabled": bool(b.get("enabled", True))} for b in blocks]
        content["faqs"] = [{"q": str(f.get("q", ""))[:200], "a": str(f.get("a", ""))[:1000]}
                           for f in (content.get("faqs") or []) if isinstance(f, dict) and f.get("q")][:20]
        content["pages_enabled"] = [p for p in (content.get("pages_enabled") or SITE_PAGES) if p in SITE_PAGES] or ["home"]
        tr_in = content.get("translations") or {}
        content["translations"] = {}
        for lg in ("en", "de", "tr"):
            t_in = tr_in.get(lg)
            if not isinstance(t_in, dict):
                continue
            t_out = {k: str(v)[:2000] for k, v in t_in.items() if k in ("headline", "about", "seo_title", "seo_description") and v}
            if isinstance(t_in.get("faqs"), list):
                t_out["faqs"] = [{"q": str(f.get("q", ""))[:200], "a": str(f.get("a", ""))[:1000]} for f in t_in["faqs"] if isinstance(f, dict) and f.get("q")][:20]
            ap_in = t_in.get("approved") if isinstance(t_in.get("approved"), dict) else {}
            t_out["approved"] = {k: bool(ap_in.get(k)) for k in TRANSLATION_KEYS if t_out.get(k)}
            content["translations"][lg] = t_out
        posts = []
        for po in (content.get("posts") or [])[:50]:
            if not isinstance(po, dict) or not po.get("title"):
                continue
            slug = re.sub(r"[^a-z0-9-]+", "-", str(po.get("slug") or po["title"]).lower()).strip("-")[:80] or str(uuid.uuid4())[:8]
            posts.append({"id": po.get("id") or str(uuid.uuid4()), "slug": slug, "title": str(po["title"])[:160], "excerpt": str(po.get("excerpt") or "")[:300],
                          "body": str(po.get("body") or "")[:8000], "image_url": str(po.get("image_url") or "")[:500], "type": po.get("type") if po.get("type") in ("blog", "campaign") else "blog",
                          "date": str(po.get("date") or datetime.now(timezone.utc).date().isoformat())[:10], "published": bool(po.get("published", True)),
                          "cta_url": str(po.get("cta_url") or "")[:300], "starts_at": str(po.get("starts_at") or "")[:10], "ends_at": str(po.get("ends_at") or "")[:10], "promo_code": re.sub(r"[^A-Z0-9_-]", "", str(po.get("promo_code") or "").upper())[:20],
                          "title_b": str(po.get("title_b") or "")[:160], "ab_auto_n": max(20, min(100000, int(po.get("ab_auto_n") or 200))),
                          "ab_winner": po.get("ab_winner") if po.get("ab_winner") in ("A", "B") else "", "ab_auto_closed": bool(po.get("ab_auto_closed")), "ab_closed_at": str(po.get("ab_closed_at") or "")[:40],
                          "discount_pct": max(0, min(90, int(po.get("discount_pct") or 0)))})
        content["posts"] = posts
        today_iso = datetime.now(timezone.utc).date().isoformat()
        for po in posts:
            if po.get("promo_code") and po.get("discount_pct"):
                in_window = (not po.get("starts_at") or po["starts_at"] <= today_iso) and (not po.get("ends_at") or po["ends_at"] >= today_iso)
                await db.promo_codes.update_one({"code": po["promo_code"]}, {"$set": {"code": po["promo_code"], "property_id": pid, "discount_type": "percentage", "discount_value": po["discount_pct"],
                                                                                  "description": f"Kampanya: {po['title']}", "is_active": bool(po.get("published", True)) and in_window, "source": "campaign_post",
                                                                                  "valid_from": po.get("starts_at") or None, "valid_until": po.get("ends_at") or None},
                                                                         "$setOnInsert": {"id": str(uuid.uuid4()), "used_count": 0, "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        an = content.get("analytics") or {}
        content["analytics"] = {k: re.sub(r"[^A-Za-z0-9_-]", "", str(an.get(k) or ""))[:40] for k in ("ga4_id", "gtm_id", "pixel_id")}
        br = content.get("brand") or {}
        content["brand"] = {k: v for k, v in {"accent": str(br.get("accent") or "")[:7], "radius": str(br.get("radius") or "")[:6]}.items() if v and (k != "accent" or re.match(r"^#[0-9a-fA-F]{6}$", v))}
        upd = {"property_id": pid, "template": tpl, "content": content,
               "mode": data.get("mode") if data.get("mode") in ("simple", "pro") else "simple",
               "engine_template": (data.get("engine_template") or "")[:40],
               "published": bool(data.get("published")),
               "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.hotel_sites.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, "published": upd["published"], "url": f"/site/{pid}"}

    @router.get("/public/site/{pid}")
    async def public_site(pid: str):
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0})
        if not cfg or not cfg.get("published"):
            raise HTTPException(404, "Site yayında değil")
        content = cfg.get("content") or {}
        if not content.get("blocks"):
            content["blocks"] = DEFAULT_BLOCKS
        if not content.get("pages_enabled"):
            content["pages_enabled"] = SITE_PAGES
        _t = datetime.now(timezone.utc).date().isoformat()
        content["posts"] = [p for p in (content.get("posts") or []) if (not p.get("starts_at") or p["starts_at"] <= _t) and (not p.get("ends_at") or p["ends_at"] >= _t)]
        content["translations"] = _approved_translations(content)
        cfg["content"] = content
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1, "city": 1, "country": 1, "address": 1, "currency": 1}) or {}
        rts = await db.room_types.find({"property_id": pid, "is_active": {"$ne": False}},
                                       {"_id": 0, "id": 1, "name": 1, "base_rate": 1, "base_price": 1, "photos": 1,
                                        "description": 1, "max_guests": 1, "bed_type": 1, "size_sqm": 1, "amenities": 1}).to_list(20)
        photos = await db.site_photos.find({"property_id": pid, "is_deleted": False},
                                           {"_id": 0, "id": 1, "kind": 1}).sort("created_at", 1).to_list(30)
        reviews = await db.reviews.find({"property_id": pid, "rating": {"$gte": 4}},
                                        {"_id": 0, "id": 1, "guest_name": 1, "rating": 1, "review_text": 1, "created_at": 1}).sort("created_at", -1).to_list(6)
        agg = await db.reviews.aggregate([{"$match": {"property_id": pid}}, {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "n": {"$sum": 1}}}]).to_list(1)
        return {"site": cfg, "property": prop, "room_types": rts, "reviews": reviews,
                "rating": {"avg": round(agg[0]["avg"], 1), "count": agg[0]["n"]} if agg else None,
                "photos": [{"id": p["id"], "kind": p["kind"], "url": f"/api/site-builder/photo/{p['id']}"} for p in photos]}

    # ---------------- İLETİŞİM FORMU ----------------
    _contact_rl: Dict[str, list] = {}

    @router.post("/public/contact")
    async def public_contact(data: dict, request: Request):
        if (data.get("website") or data.get("hp_field") or "").strip():
            return {"ok": True, "id": "spam-ignored"}
        ip = (request.headers.get("x-forwarded-for") or request.client.host or "").split(",")[0].strip()
        now_ts = datetime.now(timezone.utc).timestamp()
        hits = [t for t in _contact_rl.get(ip, []) if now_ts - t < 3600]
        if len(hits) >= 5:
            raise HTTPException(429, "Çok fazla deneme — lütfen bir saat sonra tekrar deneyin")
        _contact_rl[ip] = hits + [now_ts]
        pid = (data.get("property_id") or "").strip()
        name, email, msg = (data.get("name") or "").strip(), (data.get("email") or "").strip(), (data.get("message") or "").strip()
        if not pid or not name or "@" not in email or len(msg) < 5:
            raise HTTPException(422, "Ad, geçerli e-posta ve mesaj zorunlu")
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), "property_id": pid, "name": name[:80], "email": email[:120],
               "phone": (data.get("phone") or "")[:40], "message": msg[:2000],
               "check_in": (data.get("check_in") or "")[:10], "check_out": (data.get("check_out") or "")[:10],
               "status": "new", "source": "website", "created_at": now}
        await db.site_inquiries.insert_one(dict(doc))
        await db.notifications.insert_one({"id": str(uuid.uuid4()), "property_id": pid, "type": "site_inquiry",
                                           "title": f"Web sitesi mesajı: {name}", "body": msg[:140],
                                           "read": False, "created_at": now})
        return {"ok": True, "id": doc["id"]}

    @router.get("/public/analytics/{pid}")
    async def public_analytics(pid: str):
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0, "content.analytics": 1, "content.brand": 1}) or {}
        return {"analytics": (cfg.get("content") or {}).get("analytics") or {}, "brand": (cfg.get("content") or {}).get("brand") or {}}

    @router.get("/public/sitemap/{pid}.xml")
    async def public_sitemap(pid: str, request: Request):
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0}) or {}
        if not cfg.get("published"):
            raise HTTPException(404)
        base = f"https://{cfg['custom_domain']}" if cfg.get("custom_domain") and cfg.get("domain_verified") else (os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/") + f"/site/{pid}"
        c = cfg.get("content") or {}
        today = datetime.now(timezone.utc).date().isoformat()
        urls = [(base or "/", "1.0")] + [(f"{base}/{p}", "0.8") for p in (c.get("pages_enabled") or SITE_PAGES) if p != "home"]
        for rt in await db.room_types.find({"property_id": pid, "is_active": {"$ne": False}}, {"_id": 0, "id": 1}).to_list(50):
            urls.append((f"{base}/rooms/{rt['id']}", "0.7"))
        for po in c.get("posts") or []:
            if po.get("published", True):
                urls.append((f"{base}/blog/{po['slug']}", "0.6"))
        langs = ["tr"] + [lg for lg in ("en", "de") if _approved_translations(c).get(lg)]
        body = "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod><priority>{pr}</priority>" + "".join(f'<xhtml:link rel="alternate" hreflang="{lg}" href="{u}{("&" if "?" in u else "?")}lang={lg}"/>' for lg in langs) + "</url>" for u, pr in urls)
        return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">{body}</urlset>', media_type="application/xml")

    @router.get("/public/robots/{pid}.txt")
    async def public_robots(pid: str, request: Request):
        base = (os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
        return Response(f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {base}/api/site-builder/public/sitemap/{pid}.xml\n", media_type="text/plain")

    @router.get("/{pid}/inquiries")
    async def list_inquiries(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.site_inquiries.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return {"items": rows, "new_count": sum(1 for r in rows if r.get("status") == "new")}

    @router.put("/{pid}/inquiries/{iid}")
    async def update_inquiry(pid: str, iid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        st = data.get("status")
        if st not in ("new", "replied", "closed"):
            raise HTTPException(422, "status: new|replied|closed")
        await db.site_inquiries.update_one({"id": iid, "property_id": pid}, {"$set": {"status": st, "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"ok": True}

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

    # ---------------- KAMPANYA KISA LİNK + QR ----------------
    CHANNELS = ("email", "whatsapp", "instagram", "facebook", "qr", "sms", "other")

    async def _campaign_by_code(code: str):
        code = re.sub(r"[^A-Z0-9_-]", "", (code or "").upper())[:20]
        if not code:
            return None, None
        site = await db.hotel_sites.find_one({"content.posts.promo_code": code}, {"_id": 0, "property_id": 1, "published": 1, "content.posts": 1})
        if not site:
            return None, None
        po = next((p for p in (site.get("content") or {}).get("posts") or [] if p.get("promo_code") == code), None)
        return site, po

    @router.get("/public/c/{code}")
    async def campaign_short_link(code: str, request: Request, ch: str = "other"):
        """Kısa link: tıklamayı kanal bazında say → kampanya sayfasına (veya booking engine'e) yönlendir."""
        from fastapi.responses import RedirectResponse
        site, po = await _campaign_by_code(code)
        if not site or not po:
            raise HTTPException(404, "Kampanya bulunamadı")
        channel = ch if ch in CHANNELS else "other"
        import random
        variant = request.cookies.get(f"abv_{po['promo_code']}") if po.get("title_b") else ""
        if po.get("title_b") and variant not in ("A", "B"):
            variant = random.choice(["A", "B"])
        await db.campaign_clicks.insert_one({"id": str(uuid.uuid4()), "code": po["promo_code"], "property_id": site["property_id"], "channel": channel, "variant": variant or "",
                                             "referrer": (request.headers.get("referer") or "")[:200], "ua": (request.headers.get("user-agent") or "")[:160],
                                             "created_at": datetime.now(timezone.utc).isoformat()})
        pid = site["property_id"]
        vq = f"&v={variant}" if variant else ""
        if site.get("published") and po.get("slug"):
            target = f"/site/{pid}/blog/{po['slug']}?utm_source={channel}&utm_campaign={po['promo_code']}{vq}"
        else:
            target = f"/book?property={pid}&promo={po['promo_code']}&utm_source={channel}{vq}"
        resp = RedirectResponse(url=target, status_code=302)
        if variant:
            resp.set_cookie(f"abv_{po['promo_code']}", variant, max_age=30 * 86400, samesite="lax")
        return resp

    @router.post("/{pid}/campaign-ab/{code}/apply-winner")
    async def campaign_apply_winner(pid: str, code: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        """Kazanan varyantı uygula: B kazandıysa title=title_b; her durumda test kapanır."""
        winner = data.get("winner") if data.get("winner") in ("A", "B") else "A"
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0, "content.posts": 1})
        posts = (cfg or {}).get("content", {}).get("posts") or []
        hit = False
        for po in posts:
            if po.get("promo_code") == code.upper():
                if winner == "B" and po.get("title_b"):
                    po["title"] = po["title_b"]
                po["title_b"] = ""; po["ab_winner"] = winner; po["ab_closed_at"] = datetime.now(timezone.utc).isoformat(); hit = True
        if not hit:
            raise HTTPException(404, "Kampanya bulunamadı")
        await db.hotel_sites.update_one({"property_id": pid}, {"$set": {"content.posts": posts}})
        return {"ok": True, "winner": winner}

    @router.get("/public/c/{code}/qr.png")
    async def campaign_qr(code: str, request: Request, ch: str = "qr"):
        import io
        import qrcode
        site, po = await _campaign_by_code(code)
        if not site or not po:
            raise HTTPException(404, "Kampanya bulunamadı")
        base = (os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
        url = f"{base}/c/{po['promo_code']}?ch={ch if ch in CHANNELS else 'qr'}"
        img = qrcode.make(url, box_size=8, border=2)
        buf = io.BytesIO(); img.save(buf, format="PNG")
        return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    # ---------------- ZİYARET İSTATİSTİĞİ ----------------
    @router.post("/public/track")
    async def track(data: dict):
        pid = (data.get("property_id") or "").strip()
        event = data.get("event")
        if not pid or event not in ("view", "cta_click"):
            raise HTTPException(422, "property_id ve event (view|cta_click) zorunlu")
        now = datetime.now(timezone.utc)
        ref = (data.get("referrer") or "").lower()
        if not ref:
            source = "direct"
        elif "google." in ref:
            source = "google"
        elif any(s in ref for s in ("facebook.", "instagram.", "twitter.", "x.com", "t.co/", "linkedin.", "tiktok.", "youtube.")):
            source = "social"
        else:
            source = "other"
        await db.site_visits.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "event": event,
            "visitor_id": (data.get("visitor_id") or "")[:64], "source": source,
            "referrer": ref[:200], "page": str(data.get("page") or "")[:120], "variant": data.get("variant") if data.get("variant") in ("A", "B") else "",
            "date": now.date().isoformat(), "created_at": now.isoformat()})
        return {"ok": True}

    @router.get("/{pid}/campaign-stats")
    async def campaign_stats(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Kampanya performansı: kupon kullanımı, gelir, sayfa görüntülenme → rezervasyon dönüşümü."""
        cfg = await db.hotel_sites.find_one({"property_id": pid}, {"_id": 0, "content.posts": 1}) or {}
        posts = [p for p in ((cfg.get("content") or {}).get("posts") or []) if p.get("type") == "campaign" or p.get("promo_code")]
        today = datetime.now(timezone.utc).date().isoformat()
        out = []
        for po in posts:
            code = po.get("promo_code") or ""
            promo = await db.promo_codes.find_one({"code": code}, {"_id": 0, "used_count": 1, "is_active": 1}) if code else None
            agg = await db.bookings.aggregate([{"$match": {"property_id": pid, "promo_code": code, "status": {"$ne": "cancelled"}}},
                                               {"$group": {"_id": None, "n": {"$sum": 1}, "rev": {"$sum": "$total_price"}}}]).to_list(1) if code else []
            n = agg[0]["n"] if agg else 0
            rev = round(float(agg[0]["rev"]), 2) if agg else 0.0
            pct = float(po.get("discount_pct") or 0)
            views = await db.site_visits.count_documents({"property_id": pid, "event": "view", "page": f"blog/{po.get('slug', '')}"}) if po.get("slug") else 0
            clicks_by = {}
            if code:
                async for c in db.campaign_clicks.find({"code": code}, {"_id": 0, "channel": 1}):
                    clicks_by[c.get("channel") or "other"] = clicks_by.get(c.get("channel") or "other", 0) + 1
            ab = None
            if po.get("title_b") or po.get("ab_winner"):
                ab = {}
                for v in ("A", "B"):
                    vc = await db.campaign_clicks.count_documents({"code": code, "variant": v}) if code else 0
                    vv = await db.site_visits.count_documents({"property_id": pid, "event": "view", "page": f"blog/{po.get('slug', '')}", "variant": v}) if po.get("slug") else 0
                    vcta = await db.site_visits.count_documents({"property_id": pid, "event": "cta_click", "variant": v, "page": f"blog/{po.get('slug', '')}"}) if po.get("slug") else 0
                    ab[v] = {"title": po.get("title") if v == "A" else po.get("title_b"), "clicks": vc, "views": vv, "cta": vcta, "cta_rate_pct": round(vcta / vv * 100, 1) if vv else 0.0}
                ab["leader"] = "B" if ab["B"]["cta_rate_pct"] > ab["A"]["cta_rate_pct"] else "A"
                ab["winner"] = po.get("ab_winner") or ""
                ab["active"] = bool(po.get("title_b"))
            in_window = (not po.get("starts_at") or po["starts_at"] <= today) and (not po.get("ends_at") or po["ends_at"] >= today)
            out.append({"id": po.get("id"), "title": po.get("title"), "slug": po.get("slug"), "promo_code": code, "discount_pct": pct,
                        "starts_at": po.get("starts_at") or "", "ends_at": po.get("ends_at") or "",
                        "status": "active" if (po.get("published", True) and in_window and (promo or {}).get("is_active", True)) else ("scheduled" if po.get("starts_at") and po["starts_at"] > today else "ended"),
                        "coupon_uses": int((promo or {}).get("used_count") or 0), "bookings": n, "revenue": rev,
                        "discount_given": round(rev * pct / (100 - pct), 2) if pct and pct < 100 else 0.0,
                        "page_views": views, "conversion_pct": round(min(n / views * 100, 100), 1) if views else 0.0,
                        "clicks": sum(clicks_by.values()), "clicks_by_channel": clicks_by,
                        "short_path": f"/c/{code}" if code else "", "ab": ab})
        return {"campaigns": out, "totals": {"campaigns": len(out), "active": sum(1 for c in out if c["status"] == "active"),
                                             "coupon_uses": sum(c["coupon_uses"] for c in out), "bookings": sum(c["bookings"] for c in out),
                                             "revenue": round(sum(c["revenue"] for c in out), 2), "page_views": sum(c["page_views"] for c in out),
                                             "clicks": sum(c["clicks"] for c in out)}}

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
        sources = {}
        async for v in db.site_visits.find({**q, "event": "view"}, {"_id": 0, "date": 1, "source": 1}):
            daily[v["date"]] = daily.get(v["date"], 0) + 1
            s = v.get("source") or "direct"
            sources[s] = sources.get(s, 0) + 1
        series = sorted(daily.items())[-14:]
        return {"days": days, "views": views, "unique_visitors": uniques, "cta_clicks": clicks,
                "bookings": bookings,
                "click_rate_pct": round(min(clicks / views * 100, 100), 1) if views else 0,
                "conversion_pct": round(min(bookings / views * 100, 100), 1) if views else 0,
                "sources": sources,
                "daily": [{"date": d, "views": c} for d, c in series]}

    return router
