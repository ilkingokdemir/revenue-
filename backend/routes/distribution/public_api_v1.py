"""Public API v1 — partner erişimi: müsaitlik oku, rezervasyon push/iptal. X-API-Key (hbx_) + scope + dakikalık limit."""
import asyncio
import secrets
import time
import uuid
from datetime import date as _date, datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from models import Booking

SCOPES = ("read:availability", "read:bookings", "write:bookings", "read:guests")
DEFAULT_SCOPES = ["read:availability", "read:bookings", "write:bookings"]
_BUCKETS: Dict[str, list] = {}
now_iso = lambda: datetime.now(timezone.utc).isoformat()


def _throttle(key_id: str, limit: int) -> tuple:
    minute = int(time.time() // 60)
    b = _BUCKETS.get(key_id)
    if not b or b[0] != minute:
        b = [minute, 0]
        _BUCKETS[key_id] = b
    b[1] += 1
    return b[1] <= limit, max(0, limit - b[1]), (minute + 1) * 60


async def api_key_auth(db, request: Request, response: Optional[Response] = None, scope: str = "") -> dict:
    key = request.headers.get("X-API-Key", "")
    doc = await db.public_api_keys.find_one({"key": key, "active": {"$ne": False}}, {"_id": 0}) if key else None
    if not doc:
        raise HTTPException(401, "Geçersiz API anahtarı — X-API-Key header gerekli")
    if doc.get("expires_at") and doc["expires_at"] < now_iso():
        raise HTTPException(401, "API anahtarının süresi dolmuş")
    scopes = doc.get("scopes") or DEFAULT_SCOPES
    if scope and scope not in scopes:
        raise HTTPException(403, f"Anahtarda '{scope}' yetkisi yok")
    limit = int(doc.get("rate_per_min") or 120)
    ok, remaining, reset = _throttle(doc["id"], limit)
    if response is not None:
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
    if not ok:
        raise HTTPException(429, "Dakikalık istek limiti aşıldı", headers={"Retry-After": str(max(1, reset - int(time.time()))), "X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"})
    await db.public_api_keys.update_one({"key": key}, {"$inc": {"calls": 1}, "$set": {"last_used": now_iso()}})
    await db.public_api_calls.insert_one({"id": str(uuid.uuid4()), "key_id": doc["id"], "property_id": doc["property_id"], "path": request.url.path, "method": request.method, "at": now_iso()})
    return doc


def _parse_dates(check_in: str, check_out: str):
    try:
        ci = _date.fromisoformat(check_in); co = _date.fromisoformat(check_out)
    except (TypeError, ValueError):
        raise HTTPException(422, "check_in/check_out YYYY-MM-DD olmalı")
    if co <= ci:
        raise HTTPException(422, "check_out check_in'den sonra olmalı")
    return ci, co, (co - ci).days


async def _availability(db, pid: str, check_in: str, check_out: str, adults: int):
    _, _, nights = _parse_dates(check_in, check_out)
    rooms = await db.room_types.find({"property_id": pid, "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "base_price": 1, "max_occupancy": 1, "total_rooms": 1}).to_list(100)
    out = []
    for r in rooms:
        booked = await db.bookings.count_documents({"room_type_id": r["id"], "status": {"$nin": ["cancelled", "no_show"]}, "check_in": {"$lt": check_out}, "check_out": {"$gt": check_in}})
        left = max(0, int(r.get("total_rooms") or 1) - booked)
        price = float(r.get("base_price") or 0)
        out.append({"room_type_id": r["id"], "name": r.get("name"), "max_occupancy": int(r.get("max_occupancy") or 2), "rooms_left": left,
                    "available": left > 0 and int(r.get("max_occupancy") or 2) >= adults, "nightly_rate": price, "stay_total": round(price * nights, 2)})
    return nights, out


def _public_booking(b: dict) -> dict:
    keys = ("id", "booking_ref", "property_id", "room_type_id", "room_name", "guest_name", "guest_email", "guest_phone", "check_in", "check_out", "nights", "adults", "children", "rooms",
            "total_price", "currency", "status", "payment_status", "special_requests", "source", "external_ref", "created_at", "cancelled_at")
    return {k: b.get(k) for k in keys if k in b}


DOCS = {
    "version": "v1", "auth": "Header: X-API-Key: hbx_... (Süper Admin → Public API Anahtarları)",
    "rate_limit": "Anahtar başına varsayılan 120 istek/dk. Yanıt başlıkları: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset; aşımda 429 + Retry-After.",
    "scopes": list(SCOPES),
    "idempotency": "POST /public/v1/bookings için opsiyonel Idempotency-Key başlığı: aynı anahtarla tekrar gönderim aynı rezervasyonu döndürür (201 yerine 200).",
    "webhooks": "booking.created / booking.cancelled olayları webhook aboneliklerine POST edilir (X-Webhook-Secret).",
    "endpoints": [
        {"method": "GET", "path": "/api/public/v1/availability", "scope": "read:availability", "query": "check_in, check_out, adults=2", "desc": "Oda tipi bazlı kalan oda ve fiyat"},
        {"method": "GET", "path": "/api/public/v1/rate-plans", "scope": "read:availability", "desc": "Fiyat planları (esnek / iade edilmez / kahvaltılı)"},
        {"method": "GET", "path": "/api/public/v1/rates?days=14", "scope": "read:availability", "desc": "Günlük fiyat blokları"},
        {"method": "GET", "path": "/api/public/v1/bookings?limit=50", "scope": "read:bookings", "desc": "Rezervasyon listesi"},
        {"method": "GET", "path": "/api/public/v1/bookings/{ref}", "scope": "read:bookings", "desc": "Tek rezervasyon (booking_ref veya id)"},
        {"method": "POST", "path": "/api/public/v1/bookings", "scope": "write:bookings", "body": {"room_type_id": "…", "guest_name": "…", "guest_email": "…", "check_in": "YYYY-MM-DD", "check_out": "YYYY-MM-DD", "adults": 2, "rooms": 1, "total_price": "opsiyonel", "external_ref": "PMS/OTA referansı", "rate_plan_id": "opsiyonel", "special_requests": ""}, "desc": "Rezervasyon push (müsaitlik kontrolü, 409 doluysa)"},
        {"method": "POST", "path": "/api/public/v1/bookings/{ref}/cancel", "scope": "write:bookings", "body": {"reason": "opsiyonel"}, "desc": "Rezervasyon iptali"},
        {"method": "GET", "path": "/api/public/v1/guests?limit=50", "scope": "read:guests", "desc": "Misafir listesi"},
    ],
}


def create_public_api_v1_router(db, require_roles):
    router = APIRouter(tags=["public-api-v1"])

    def curl(base: str):
        return [
            {"title": "Müsaitlik", "cmd": f"curl '{base}/api/public/v1/availability?check_in=2026-07-10&check_out=2026-07-12&adults=2' -H 'X-API-Key: hbx_…'"},
            {"title": "Rezervasyon push", "cmd": f"curl -X POST '{base}/api/public/v1/bookings' -H 'X-API-Key: hbx_…' -H 'Idempotency-Key: ota-12345' -H 'Content-Type: application/json' -d '{{\"room_type_id\":\"RT_ID\",\"guest_name\":\"Ada Lovelace\",\"guest_email\":\"ada@example.com\",\"check_in\":\"2026-07-10\",\"check_out\":\"2026-07-12\",\"adults\":2,\"external_ref\":\"OTA-778\"}}'"},
            {"title": "Rezervasyon sorgula", "cmd": f"curl '{base}/api/public/v1/bookings/MHB-XXXX' -H 'X-API-Key: hbx_…'"},
            {"title": "İptal", "cmd": f"curl -X POST '{base}/api/public/v1/bookings/MHB-XXXX/cancel' -H 'X-API-Key: hbx_…' -H 'Content-Type: application/json' -d '{{\"reason\":\"guest request\"}}'"},
        ]

    @router.get("/public/v1/docs")
    async def docs(request: Request):
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        base = f"{request.headers.get('x-forwarded-proto') or 'https'}://{host}"
        return {**DOCS, "curl_examples": curl(base), "openapi_url": f"{base}/api/openapi.json"}

    @router.put("/public-keys/{pid}/{key_id}")
    async def update_key(pid: str, key_id: str, data: dict, _u: dict = Depends(require_roles("admin"))):
        upd = {}
        if "active" in data:
            upd["active"] = bool(data["active"])
        if "scopes" in data:
            upd["scopes"] = [s for s in (data.get("scopes") or []) if s in SCOPES] or DEFAULT_SCOPES
        if "rate_per_min" in data:
            upd["rate_per_min"] = max(10, min(5000, int(data["rate_per_min"] or 120)))
        if "name" in data:
            upd["name"] = str(data["name"])[:60]
        r = await db.public_api_keys.update_one({"id": key_id, "property_id": pid}, {"$set": upd})
        if not r.matched_count:
            raise HTTPException(404, "Anahtar yok")
        return {"ok": True, **upd}

    @router.get("/public-keys/{pid}/usage")
    async def key_usage(pid: str, days: int = 7, _u: dict = Depends(require_roles("admin"))):
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.public_api_calls.find({"property_id": pid, "at": {"$gte": since}}, {"_id": 0, "key_id": 1, "path": 1}).to_list(50000)
        by_key: Dict[str, int] = {}; by_path: Dict[str, int] = {}
        for r in rows:
            by_key[r["key_id"]] = by_key.get(r["key_id"], 0) + 1
            by_path[r["path"]] = by_path.get(r["path"], 0) + 1
        return {"days": days, "calls": len(rows), "by_key": by_key, "by_path": by_path}

    @router.get("/public/v1/availability")
    async def pub_availability(request: Request, response: Response, check_in: str, check_out: str, adults: int = 2):
        k = await api_key_auth(db, request, response, "read:availability")
        nights, rooms = await _availability(db, k["property_id"], check_in, check_out, adults)
        pr = await db.properties.find_one({"id": k["property_id"]}, {"_id": 0, "currency": 1, "name": 1})
        return {"property_id": k["property_id"], "property_name": (pr or {}).get("name"), "currency": (pr or {}).get("currency") or "GBP", "check_in": check_in, "check_out": check_out, "nights": nights, "adults": adults, "rooms": rooms}

    @router.get("/public/v1/rate-plans")
    async def pub_rate_plans(request: Request, response: Response):
        k = await api_key_auth(db, request, response, "read:availability")
        rows = await db.be_rate_plans.find({"property_id": k["property_id"], "is_active": {"$ne": False}}, {"_id": 0}).to_list(50)
        return {"property_id": k["property_id"], "rate_plans": rows}

    @router.get("/public/v1/bookings/{ref}")
    async def pub_booking_get(ref: str, request: Request, response: Response):
        k = await api_key_auth(db, request, response, "read:bookings")
        b = await db.bookings.find_one({"property_id": k["property_id"], "$or": [{"booking_ref": ref}, {"id": ref}, {"external_ref": ref}]}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        return _public_booking(b)

    @router.post("/public/v1/bookings/{ref}/cancel")
    async def pub_booking_cancel(ref: str, request: Request, response: Response, data: Optional[dict] = None):
        k = await api_key_auth(db, request, response, "write:bookings")
        b = await db.bookings.find_one({"property_id": k["property_id"], "$or": [{"booking_ref": ref}, {"id": ref}, {"external_ref": ref}]}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        if b.get("status") == "cancelled":
            return _public_booking(b)
        upd = {"status": "cancelled", "cancelled_at": now_iso(), "cancel_reason": str((data or {}).get("reason") or "")[:200], "cancelled_by": f"public_api:{k.get('name', '')}"}
        await db.bookings.update_one({"id": b["id"]}, {"$set": upd})
        from routes.platform_ext.p0_pack import emit_webhook
        asyncio.create_task(emit_webhook(db, k["property_id"], "booking.cancelled", _public_booking({**b, **upd})))
        return _public_booking({**b, **upd})

    return router


async def create_booking_from_api(db, k: dict, data: dict, idem_key: str = "") -> tuple:
    """Public API rezervasyon push: doğrulama + müsaitlik + idempotency + MOCK onay e-postası. (doc, created) döner."""
    pid = k["property_id"]
    if idem_key:
        prev = await db.public_api_idempotency.find_one({"key_id": k["id"], "idem_key": idem_key}, {"_id": 0, "booking_id": 1})
        if prev:
            b = await db.bookings.find_one({"id": prev["booking_id"]}, {"_id": 0})
            if b:
                return _public_booking(b), False
    name = str(data.get("guest_name") or "").strip()
    email = str(data.get("guest_email") or "").strip().lower()
    if not name or "@" not in email:
        raise HTTPException(422, "guest_name ve geçerli guest_email zorunlu")
    check_in, check_out = str(data.get("check_in") or ""), str(data.get("check_out") or "")
    _, _, nights = _parse_dates(check_in, check_out)
    adults = max(1, int(data.get("adults") or 2)); qty = max(1, int(data.get("rooms") or 1))
    rt = await db.room_types.find_one({"id": str(data.get("room_type_id") or ""), "property_id": pid}, {"_id": 0})
    if not rt:
        raise HTTPException(422, "room_type_id bu tesise ait değil — GET /public/v1/availability ile geçerli id alın")
    booked = await db.bookings.count_documents({"room_type_id": rt["id"], "status": {"$nin": ["cancelled", "no_show"]}, "check_in": {"$lt": check_out}, "check_out": {"$gt": check_in}})
    left = int(rt.get("total_rooms") or 1) - booked
    if left < qty:
        raise HTTPException(409, f"Müsait oda yok: {max(0, left)} kaldı, {qty} istendi")
    pr = await db.properties.find_one({"id": pid}, {"_id": 0, "currency": 1})
    price = float(data.get("total_price")) if data.get("total_price") not in (None, "") else round(float(rt.get("base_price") or 0) * nights * qty, 2)
    b = Booking(property_id=pid, room_type_id=rt["id"], guest_name=name[:100], guest_email=email, guest_phone=str(data.get("guest_phone") or "")[:30], check_in=check_in, check_out=check_out,
                adults=adults, children=int(data.get("children") or 0), rooms=qty, total_price=price, currency=str((pr or {}).get("currency") or "GBP"),
                special_requests=str(data.get("special_requests") or "")[:500], status="confirmed", payment_status=str(data.get("payment_status") or "pending"))
    doc = b.model_dump()
    doc.update({"source": "public_api", "api_key_id": k["id"], "api_key_name": k.get("name", ""), "nights": nights, "room_name": rt.get("name", ""),
                "external_ref": str(data.get("external_ref") or "")[:60], "rate_plan_id": str(data.get("rate_plan_id") or "")})
    await db.bookings.insert_one(dict(doc))
    if idem_key:
        await db.public_api_idempotency.insert_one({"key_id": k["id"], "idem_key": idem_key, "booking_id": doc["id"], "at": now_iso()})
    try:
        from routes.pms.guest_email_i18n import send_guest_confirmation
        asyncio.create_task(send_guest_confirmation(db, dict(doc)))
    except Exception:
        pass
    try:
        from routes.automation_rules import fire_event
        asyncio.create_task(fire_event(db, "booking_created", {"property_id": pid, "booking_ref": doc["booking_ref"], "guest_name": name, "guest_email": email, "room_number": rt.get("name", ""), "tags": [], "nights": nights, "total_price": price, "source": "public_api"}))
    except Exception:
        pass
    return _public_booking(doc), True
