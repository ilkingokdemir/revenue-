"""Booking engine gap-MVP: BE ayarları (doluluk/LOS/flex-cancel/hold), acente kodu, bekleme listesi, canlı FX."""
import asyncio
import uuid
from datetime import datetime, timezone, date as _date
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

DEFAULTS = {"base_occupancy": 2, "extra_adult_per_night": 0.0, "los_tiers": [{"min_nights": 7, "pct": 10}, {"min_nights": 28, "pct": 25}],
            "flex_cancel_pct": 8.0, "flex_cancel_enabled": True, "hold_hours": 24, "hold_enabled": True, "scarcity_threshold": 3,
            "waitlist_enabled": True, "agent_code_enabled": True, "long_stay_enabled": True,
            "day_use_enabled": False, "day_use_pct": 50.0, "day_use_start": "10:00", "day_use_end": "17:00", "wishlist_enabled": True,
            "price_display_mode": "auto_by_market", "total_price_transparency": True, "tax_exclusive_markets": ["US", "CA", "en-US"]}


async def get_be_settings(db, pid: str) -> dict:
    doc = await db.be_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULTS, **doc, "property_id": pid}


def los_discount_pct(settings: dict, nights: int) -> float:
    if not settings.get("long_stay_enabled"):
        return 0.0
    best = 0.0
    for t in settings.get("los_tiers") or []:
        try:
            if nights >= int(t.get("min_nights") or 0) and float(t.get("pct") or 0) > best:
                best = float(t["pct"])
        except (TypeError, ValueError):
            continue
    return best


def create_be_gaps_router(db, require_roles):
    router = APIRouter()

    @router.get("/booking/be-settings/{pid}")
    async def be_settings_public(pid: str):
        s = await get_be_settings(db, pid)
        return {k: s[k] for k in DEFAULTS} | {"property_id": pid}

    @router.put("/booking/be-settings/{pid}")
    async def be_settings_put(pid: str, data: Dict, _u: dict = Depends(require_roles("admin", "manager"))):
        cur = await get_be_settings(db, pid)
        upd = {"property_id": pid, "updated_at": datetime.now(timezone.utc).isoformat()}
        for k, v in DEFAULTS.items():
            if k in data:
                val = data[k]
                if isinstance(v, bool):
                    val = bool(val)
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    try:
                        val = float(val) if isinstance(v, float) else int(val)
                    except (TypeError, ValueError):
                        raise HTTPException(422, f"{k} sayı olmalı")
                    if val < 0 or (k.endswith("_pct") and val > 100):
                        raise HTTPException(422, f"{k} aralık dışı")
                elif isinstance(v, str):
                    val = str(val or "")[:40]
                    if k == "price_display_mode" and val not in ("auto_by_market", "tax_inclusive", "tax_exclusive"):
                        raise HTTPException(422, "price_display_mode: auto_by_market | tax_inclusive | tax_exclusive")
                elif k == "tax_exclusive_markets":
                    val = [str(x).strip()[:8] for x in (val or []) if str(x).strip()][:30]
                elif k == "los_tiers":
                    val = [{"min_nights": int(t.get("min_nights") or 0), "pct": float(t.get("pct") or 0)} for t in (val or []) if isinstance(t, dict)][:6]
                upd[k] = val
        await db.be_settings.update_one({"property_id": pid}, {"$set": {**cur, **upd}}, upsert=True)
        return await get_be_settings(db, pid)

    # ---- acente / şirket kodu ----
    @router.post("/booking/agent-code/validate")
    async def agent_code_validate(data: Dict):
        pid = data.get("property_id") or ""
        code = str(data.get("code") or "").strip().upper()
        if not code:
            raise HTTPException(422, "Kod boş")
        ag = await db.travel_agents.find_one({"property_id": pid, "$or": [{"code": code}, {"agent_code": code}], "is_active": {"$ne": False}}, {"_id": 0})
        if not ag:
            raise HTTPException(404, "Kod bulunamadı veya pasif")
        return {"valid": True, "agent_id": ag.get("id"), "agent_name": ag.get("name") or ag.get("company"), "discount_pct": float(ag.get("negotiated_discount_pct") or 0),
                "type": ag.get("type") or "corporate", "billing": ag.get("billing_mode") or "guest_pays"}

    # ---- bekleme listesi ----
    @router.post("/booking/waitlist")
    async def waitlist_add(data: Dict):
        pid = data.get("property_id") or ""
        email = str(data.get("email") or "").strip().lower()
        if not pid or "@" not in email:
            raise HTTPException(422, "E-posta gerekli")
        try:
            ci = _date.fromisoformat(str(data.get("check_in"))); co = _date.fromisoformat(str(data.get("check_out")))
        except (TypeError, ValueError):
            raise HTTPException(422, "Tarih hatalı")
        if co <= ci:
            raise HTTPException(422, "Çıkış girişten sonra olmalı")
        doc = {"id": str(uuid.uuid4()), "property_id": pid, "email": email, "name": str(data.get("name") or "")[:120], "check_in": ci.isoformat(), "check_out": co.isoformat(),
               "adults": int(data.get("adults") or 2), "room_type_id": str(data.get("room_type_id") or ""), "lang": str(data.get("lang") or "en")[:2],
               "status": "waiting", "created_at": datetime.now(timezone.utc).isoformat()}
        exists = await db.be_waitlist.find_one({"property_id": pid, "email": email, "check_in": doc["check_in"], "check_out": doc["check_out"], "status": "waiting"}, {"_id": 0, "id": 1})
        if exists:
            return {"ok": True, "already": True, "id": exists["id"]}
        await db.be_waitlist.insert_one(dict(doc))
        try:
            await db.lost_demand.insert_one({"id": str(uuid.uuid4()), "property_id": pid, "check_in": doc["check_in"], "check_out": doc["check_out"], "reason": "no_availability",
                                             "source": "be_waitlist", "guests": doc["adults"], "created_at": doc["created_at"]})
        except Exception:
            pass
        return {"ok": True, "id": doc["id"]}

    @router.get("/booking/waitlist/{pid}")
    async def waitlist_list(pid: str, _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.be_waitlist.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        return {"items": rows, "waiting": sum(1 for r in rows if r["status"] == "waiting"), "notified": sum(1 for r in rows if r["status"] == "notified")}

    # ---- canlı FX (currency_fx modülünden, public) ----
    @router.get("/booking/fx-rates")
    async def fx_public(base: str = "GBP"):
        rows = await db.fx_rates.find({"code": {"$exists": True}}, {"_id": 0, "code": 1, "rate": 1, "rate_to_base": 1, "updated_at": 1, "as_of": 1}).sort("code", 1).to_list(500)
        latest: Dict[str, dict] = {}
        for r in rows:
            latest[r["code"]] = r
        out = {}
        for code, r in latest.items():
            v = r.get("rate_to_base")
            if v and float(v) > 0:
                out[code] = round(1 / float(v), 6)
        return {"base": base, "rates": out, "count": len(out), "source": "currency_fx" if out else "static"}

    async def _geocode(pr: dict):
        """Şehir/adres → koordinat (Nominatim, sonuç properties.geo'ya önbelleklenir)."""
        q = ", ".join(x for x in [pr.get("address"), pr.get("city"), pr.get("country")] if x)
        if not q:
            return None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=6, headers={"User-Agent": "MyHotelBox/1.0"}) as c:
                r = await c.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "json", "limit": 1})
                hit = (r.json() or [None])[0]
            if hit:
                geo = {"lat": float(hit["lat"]), "lng": float(hit["lon"])}
                await db.properties.update_one({"id": pr["id"]}, {"$set": {"geo": geo}})
                return geo
        except Exception:
            return None
        return None

    @router.put("/booking/property-geo/{pid}")
    async def set_geo(pid: str, data: Dict, _u: dict = Depends(require_roles("admin", "manager"))):
        try:
            geo = {"lat": float(data["lat"]), "lng": float(data["lng"])}
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "lat/lng gerekli")
        await db.properties.update_one({"id": pid}, {"$set": {"geo": geo}})
        return {"ok": True, "geo": geo}

    # ---- en iyi fiyat garantisi ----
    @router.post("/booking/brg-claim")
    async def brg_claim(data: Dict):
        email = str(data.get("email") or "").strip().lower()
        try:
            price = float(data.get("competitor_price"))
        except (TypeError, ValueError):
            raise HTTPException(422, "Rakip fiyat sayı olmalı")
        if "@" not in email or not data.get("property_id") or not str(data.get("competitor_url") or "").startswith("http"):
            raise HTTPException(422, "E-posta, tesis ve rakip bağlantısı gerekli")
        doc = {"id": str(uuid.uuid4()), "property_id": data["property_id"], "booking_ref": str(data.get("booking_ref") or "")[:30], "email": email,
               "competitor_url": str(data["competitor_url"])[:400], "competitor_price": price, "our_price": float(data.get("our_price") or 0), "currency": str(data.get("currency") or "GBP")[:3].upper(),
               "check_in": str(data.get("check_in") or "")[:10], "check_out": str(data.get("check_out") or "")[:10], "note": str(data.get("note") or "")[:500],
               "status": "pending", "created_at": datetime.now(timezone.utc).isoformat()}
        await db.brg_claims.insert_one(dict(doc))
        doc.pop("_id", None)
        return {"ok": True, "id": doc["id"], "status": "pending", "sla_hours": 24}

    @router.get("/booking/brg-claims/{pid}")
    async def brg_list(pid: str, _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.brg_claims.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        return {"items": rows, "pending": sum(1 for r in rows if r["status"] == "pending")}

    @router.put("/booking/brg-claims/{claim_id}")
    async def brg_decide(claim_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        status = data.get("status") if data.get("status") in ("approved", "rejected") else None
        if not status:
            raise HTTPException(422, "status approved|rejected")
        c = await db.brg_claims.find_one({"id": claim_id}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Talep yok")
        upd = {"status": status, "decided_at": datetime.now(timezone.utc).isoformat(), "decided_by": current_user.get("email"), "decision_note": str(data.get("note") or "")[:300]}
        if status == "approved":
            upd["matched_price"] = float(data.get("matched_price") or c["competitor_price"])
            upd["bonus_pct"] = float(data.get("bonus_pct") or 0)
            if c.get("booking_ref"):
                await db.bookings.update_one({"booking_ref": c["booking_ref"]}, {"$set": {"brg_matched_price": upd["matched_price"], "brg_claim_id": claim_id}})
        await db.brg_claims.update_one({"id": claim_id}, {"$set": upd})
        from routes.platform_ext.mailer import send_email
        msg = f"Fiyat eşleme talebiniz <b>{'onaylandı' if status == 'approved' else 'reddedildi'}</b>." + (f" Yeni fiyat: {upd['matched_price']} {c['currency']}." if status == "approved" else "") + (f"<br>{upd['decision_note']}" if upd["decision_note"] else "")
        upd["email_status"] = await send_email(db, c["email"], "En İyi Fiyat Garantisi — talep sonucu / Best Rate Guarantee result", f"<div style='font-family:system-ui'>{msg}</div>", kind="brg", meta={"claim_id": claim_id})
        return {"id": claim_id, **upd}

    # ---- day-use müsaitliği (gece stoğundan ayrı) ----
    @router.get("/booking/day-use-availability/{pid}")
    async def day_use_availability(pid: str, date: str):
        try:
            _date.fromisoformat(date)
        except ValueError:
            raise HTTPException(422, "date YYYY-MM-DD")
        cfg = await get_be_settings(db, pid)
        rooms = await db.room_types.find({"property_id": pid, "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "total_rooms": 1, "base_price": 1}).to_list(50)
        out = []
        for r in rooms:
            total = int(r.get("total_rooms") or 1)
            du = await db.bookings.count_documents({"room_type_id": r["id"], "day_use": True, "check_in": date, "status": {"$nin": ["cancelled", "no_show"]}})
            # gece misafiri sabah çıkar, akşam girer → gündüz slotu odayı bloke etmez; sadece day-use kotası sayılır
            out.append({"room_type_id": r["id"], "name": r.get("name"), "total": total, "day_use_booked": du, "day_use_left": max(0, total - du),
                        "price": round(float(r.get("base_price") or 0) * float(cfg.get("day_use_pct") or 50) / 100, 2), "hours": f"{cfg.get('day_use_start')}-{cfg.get('day_use_end')}"})
        return {"date": date, "enabled": bool(cfg.get("day_use_enabled")), "rooms": out}

    def _km(a_lat, a_lng, b_lat, b_lng) -> float:
        from math import asin, cos, radians, sin, sqrt
        dlat, dlng = radians(b_lat - a_lat), radians(b_lng - a_lng)
        h = sin(dlat / 2) ** 2 + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(dlng / 2) ** 2
        return round(2 * 6371 * asin(sqrt(h)), 1)

    _nomi_lock = asyncio.Lock()
    _nomi_last = {"t": 0.0}

    async def _nominatim(params: dict):
        """Nominatim kullanım politikası: en fazla 1 istek/sn → global kilit + aralık."""
        import httpx
        import time as _t
        async with _nomi_lock:
            wait = 1.1 - (_t.monotonic() - _nomi_last["t"])
            if wait > 0:
                await asyncio.sleep(wait)
            _nomi_last["t"] = _t.monotonic()
            async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "MyHotelBox/1.0 (hotel chain search)"}) as c:
                r = await c.get("https://nominatim.openstreetmap.org/search", params={"format": "json", **params})
            if r.status_code != 200:
                raise RuntimeError(f"nominatim {r.status_code}")
            return r.json() or []

    async def _photon(path: str, params: dict):
        """Photon (komoot) — anahtar gerektirmez, OSM etiketiyle en yakın POI; Nominatim 429 yedeği."""
        import httpx
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": "MyHotelBox/1.0"}) as c:
            r = await c.get(f"https://photon.komoot.io/{path}", params=params)
        if r.status_code != 200:
            raise RuntimeError(f"photon {r.status_code}")
        return (r.json() or {}).get("features") or []

    async def _city_centre(city: str, country: str):
        key = f"centre:{(city or '').lower()}|{(country or '').lower()}"
        hit = await db.geo_cache.find_one({"key": key}, {"_id": 0})
        if hit and hit.get("geo"):
            return hit.get("geo")
        if not city:
            return None
        geo = None
        try:
            feats = await _photon("api", {"q": ", ".join(x for x in [city, country] if x), "limit": 1, "osm_tag": ["place:city", "place:town"]})
            if feats:
                lng, lat = feats[0]["geometry"]["coordinates"]
                geo = {"lat": float(lat), "lng": float(lng)}
        except Exception:
            try:
                res = await _nominatim({"q": ", ".join(x for x in [city, country] if x), "limit": 1})
                if res:
                    geo = {"lat": float(res[0]["lat"]), "lng": float(res[0]["lon"])}
            except Exception:
                return None
        if geo:
            await db.geo_cache.update_one({"key": key}, {"$set": {"key": key, "geo": geo, "at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return geo

    async def _nearest(geo: dict, osm_tag: str, radius_km: int, prefer=None):
        feats = await _photon("reverse", {"lat": geo["lat"], "lon": geo["lng"], "limit": 12, "radius": radius_km, "osm_tag": osm_tag})
        cands = []
        for f in feats:
            name = (f.get("properties") or {}).get("name")
            if not name:
                continue
            lng, lat = f["geometry"]["coordinates"]
            cands.append({"name": str(name)[:60], "km": _km(geo["lat"], geo["lng"], float(lat), float(lng))})
        if prefer:
            major = [c for c in cands if prefer(c["name"])]
            cands = major or cands
        return min(cands, key=lambda c: c["km"]) if cands else None

    def _is_airport(name: str) -> bool:
        n = name.lower()
        return any(k in n for k in ("airport", "flughafen", "aéroport", "aeroporto", "aeropuerto", "havaliman")) and not any(x in n for x in ("raf ", "airfield", "gliding", "militär", "military", "militar"))

    async def _geo_meta(pr: dict):
        """Şehir merkezine mesafe/yürüme + en yakın istasyon + havalimanı (Photon reverse, tesise önbelleklenir)."""
        geo = pr.get("geo")
        if not geo:
            return None
        sig = f"v7:{geo['lat']:.4f},{geo['lng']:.4f}"
        meta = pr.get("geo_meta")
        if meta and meta.get("sig") == sig:
            return meta
        if meta and meta.get("retry_after") and meta["retry_after"] > datetime.now(timezone.utc).isoformat():
            return meta
        meta = {"sig": sig, "centre_km": None, "station": None, "airport": None}
        complete = True
        centre = await _city_centre(pr.get("city"), pr.get("country"))
        if centre:
            meta["centre_km"] = _km(geo["lat"], geo["lng"], centre["lat"], centre["lng"])
            meta["centre_walk_min"] = int(round(meta["centre_km"] / 5 * 60))
        else:
            complete = False
        try:
            meta["station"] = await _nearest(geo, "railway:station", 3)
            if meta["station"]:
                meta["station"]["walk_min"] = int(round(meta["station"]["km"] / 5 * 60))
        except Exception:
            complete = False
        try:
            meta["airport"] = await _nearest(geo, "aeroway:aerodrome", 80, prefer=_is_airport)
        except Exception:
            complete = False
        # eksik arama (ör. sağlayıcı 429) → sig kaydedilmez; 1 saat sonra yeniden denenir
        from datetime import timedelta as _td
        save = {**meta, "sig": sig if complete else None}
        if not complete:
            save["retry_after"] = (datetime.now(timezone.utc) + _td(hours=1)).isoformat()
        await db.properties.update_one({"id": pr["id"]}, {"$set": {"geo_meta": save}})
        return meta

    # ---- zincir arama ----
    @router.get("/booking/chain-search")
    async def chain_search(check_in: str, check_out: str, adults: int = 2):
        try:
            ci = _date.fromisoformat(check_in); co = _date.fromisoformat(check_out)
        except ValueError:
            raise HTTPException(422, "Tarih hatalı")
        nights = max(1, (co - ci).days)
        props = await db.properties.find({"is_active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "city": 1, "country": 1, "address": 1, "image_url": 1, "hero_image": 1, "star_rating": 1, "currency": 1, "geo": 1, "geo_meta": 1, "latitude": 1, "longitude": 1}).to_list(50)
        out = []
        for pr in props:
            if pr.get("latitude") and pr.get("longitude"):
                pr["geo"] = {"lat": float(pr["latitude"]), "lng": float(pr["longitude"])}
            elif not pr.get("geo"):
                pr["geo"] = await _geocode(pr)
            meta = await _geo_meta(pr)
            rooms = await db.room_types.find({"property_id": pr["id"], "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "base_price": 1, "max_occupancy": 1, "total_rooms": 1, "image_url": 1}).to_list(50)
            best = None; avail_total = 0
            for r in rooms:
                if int(r.get("max_occupancy") or 2) < adults:
                    continue
                booked = await db.bookings.count_documents({"room_type_id": r["id"], "status": {"$nin": ["cancelled", "no_show"]}, "check_in": {"$lt": check_out}, "check_out": {"$gt": check_in}})
                left = int(r.get("total_rooms") or 1) - booked
                if left <= 0:
                    continue
                avail_total += left
                price = float(r.get("base_price") or 0)
                if price <= 0:
                    continue
                if best is None or price < best["price"]:
                    best = {"room_type_id": r["id"], "room_name": r.get("name"), "price": price, "rooms_left": left, "image_url": r.get("image_url")}
            out.append({"property_id": pr["id"], "name": pr.get("name"), "city": pr.get("city"), "country": pr.get("country"), "image_url": pr.get("hero_image") or pr.get("image_url"), "geo": pr.get("geo"),
                        "centre_km": (meta or {}).get("centre_km"), "centre_walk_min": (meta or {}).get("centre_walk_min"), "station": (meta or {}).get("station"), "airport": (meta or {}).get("airport"),
                        "star_rating": pr.get("star_rating"), "currency": pr.get("currency") or "GBP", "available": avail_total > 0, "rooms_available": avail_total, "best": best,
                        "nights": nights, "total_from": round(best["price"] * nights, 2) if best else None, "book_url": f"/book?property={pr['id']}&check_in={check_in}&check_out={check_out}&adults={adults}"})
        out.sort(key=lambda x: (not x["available"], x["total_from"] or 1e12))
        return {"check_in": check_in, "check_out": check_out, "adults": adults, "nights": nights, "properties": out}

    # ---- wishlist ----
    @router.post("/booking/wishlist")
    async def wishlist_create(data: Dict):
        items = [i for i in (data.get("items") or []) if isinstance(i, dict) and i.get("property_id") and i.get("room_type_id")][:20]
        if not items:
            raise HTTPException(422, "Liste boş")
        code = uuid.uuid4().hex[:8].upper()
        for it in items:
            r = await db.room_types.find_one({"id": it["room_type_id"]}, {"_id": 0, "base_price": 1})
            it["price_at_save"] = float((r or {}).get("base_price") or 0)
        await db.be_wishlists.insert_one({"id": str(uuid.uuid4()), "code": code, "items": items, "owner_email": str(data.get("owner_email") or "").strip().lower()[:120], "alerts_sent": 0, "check_in": str(data.get("check_in") or ""), "check_out": str(data.get("check_out") or ""),
                                          "adults": int(data.get("adults") or 2), "owner_name": str(data.get("owner_name") or "")[:80], "views": 0, "created_at": datetime.now(timezone.utc).isoformat()})
        return {"code": code, "share_path": f"/wishlist/{code}"}

    @router.get("/booking/wishlist/{code}")
    async def wishlist_get(code: str):
        w = await db.be_wishlists.find_one({"code": code.upper()}, {"_id": 0})
        if not w:
            raise HTTPException(404, "Liste bulunamadı")
        await db.be_wishlists.update_one({"code": code.upper()}, {"$inc": {"views": 1}})
        rooms = []
        for it in w["items"]:
            r = await db.room_types.find_one({"id": it["room_type_id"]}, {"_id": 0, "id": 1, "name": 1, "base_price": 1, "image_url": 1, "property_id": 1, "max_occupancy": 1})
            pr = await db.properties.find_one({"id": it["property_id"]}, {"_id": 0, "name": 1, "city": 1, "currency": 1})
            if r:
                rooms.append({**r, "property_name": (pr or {}).get("name"), "city": (pr or {}).get("city"), "currency": (pr or {}).get("currency") or "GBP",
                              "book_url": f"/book?property={it['property_id']}&check_in={w.get('check_in', '')}&check_out={w.get('check_out', '')}&adults={w.get('adults', 2)}&room={r['id']}"})
        return {**w, "rooms": rooms}

    # ---- hold ----
    @router.get("/booking/holds/{pid}")
    async def holds_list(pid: str, _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.bookings.find({"property_id": pid, "status": "hold"}, {"_id": 0, "booking_ref": 1, "guest_name": 1, "guest_email": 1, "check_in": 1, "check_out": 1, "total_price": 1, "hold_expires_at": 1}).sort("hold_expires_at", 1).to_list(200)
        return {"items": rows}

    return router
