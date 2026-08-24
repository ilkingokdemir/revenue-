"""P0 Paketi: Stripe Ödemeleri, Public API v1 + Giden Webhooks, Süper Admin, Veri Göçü."""
import os
import csv
import io
import uuid
import secrets
from datetime import datetime, timezone

import httpx
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
now_iso = lambda: datetime.now(timezone.utc).isoformat()


async def emit_webhook(db, pid: str, event: str, data: dict):
    """Giden webhook: abone URL'lere event POST'lar (tek deneme, teslimat loglanır)."""
    subs = await db.webhook_subscriptions.find(
        {"property_id": {"$in": [pid, "*"]}, "active": {"$ne": False},
         "$or": [{"events": event}, {"events": "*"}]}, {"_id": 0}).to_list(20)
    if not subs:
        return 0
    payload = {"id": str(uuid.uuid4()), "event": event, "property_id": pid,
               "created_at": now_iso(), "data": data}
    sent = 0
    async with httpx.AsyncClient(timeout=8) as client:
        for s in subs:
            try:
                r = await client.post(s["url"], json=payload,
                                      headers={"X-Webhook-Secret": s.get("secret", "")})
                ok = r.status_code < 300
            except Exception:
                ok = False
            sent += 1 if ok else 0
            await db.webhook_deliveries.insert_one({
                "id": str(uuid.uuid4()), "subscription_id": s.get("id"), "event": event,
                "url": s["url"], "ok": ok, "property_id": pid, "at": now_iso()})
    return sent


def create_p0_router(db, require_roles):
    router = APIRouter(tags=["p0"])
    ROLES = ("admin", "manager")

    # ================= 1) STRIPE ÖDEMELERİ =================
    @router.post("/payments/checkout")
    async def create_checkout(data: dict, request: Request,
                              _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Pay-by-link / tahsilat: booking için dinamik tutarlı Stripe Checkout üretir."""
        amount = float(data.get("amount") or 0)
        if amount <= 0 or amount > 100000:
            raise HTTPException(400, "Geçersiz tutar")
        currency = (data.get("currency") or "gbp").lower()
        pid = data.get("property_id") or "default"
        booking_id = data.get("booking_id") or ""
        desc = (data.get("description") or f"Konaklama ödemesi {booking_id}")[:120]
        origin = data.get("origin_url") or str(request.base_url).rstrip("/")
        session = stripe.checkout.Session.create(
            line_items=[{"price_data": {"currency": currency, "unit_amount": int(round(amount * 100)),
                                        "product_data": {"name": desc}}, "quantity": 1}],
            mode="payment",
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/payment/cancel",
            metadata={"property_id": pid, "booking_id": booking_id, "kind": data.get("kind", "payment")})
        await db.payment_transactions.insert_one({
            "id": str(uuid.uuid4()), "session_id": session.id, "property_id": pid,
            "booking_id": booking_id, "amount": amount, "currency": currency,
            "description": desc, "kind": data.get("kind", "payment"),
            "status": "initiated", "payment_status": "pending",
            "created_by": str(_u.get("email") or ""), "created_at": now_iso(), "updated_at": now_iso()})
        return {"checkout_url": session.url, "session_id": session.id,
                "note": "Bu linki misafire gönderin (pay-by-link) veya yönlendirin."}

    @router.post("/payments/email-link")
    async def email_payment_link(data: dict,
                                 _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Ödeme linkini misafire e-postayla gönder (Resend anahtarı gelene kadar MOCK)."""
        to = (data.get("to") or "").strip()
        link = (data.get("link") or "").strip()
        if not to or not link:
            raise HTTPException(400, "to ve link zorunlu")
        await db.email_outbox.insert_one({
            "id": str(uuid.uuid4()), "to": to, "link": link,
            "booking_id": data.get("booking_id") or "", "amount": data.get("amount"),
            "subject": "Konaklama ödeme linkiniz", "kind": "payment_link",
            "status": "mocked", "created_by": str(_u.get("email") or ""), "created_at": now_iso()})
        return {"ok": True, "mocked": True, "to": to,
                "note": "Resend API anahtarı eklenince gerçek gönderim aktif olacak."}

    @router.get("/payments/tx-log/{pid}")
    async def list_transactions(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.payment_transactions.find({"property_id": pid}, {"_id": 0}).sort(
            "created_at", -1).to_list(50)
        return {"transactions": rows}

    @router.post("/stripe/webhook")
    async def stripe_webhook(request: Request):
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
        except Exception:
            raise HTTPException(400, "Invalid signature")
        obj, t = event["data"]["object"], event["type"]
        if t == "checkout.session.completed":
            await db.payment_transactions.update_one(
                {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                          "stripe_payment_intent_id": obj.get("payment_intent"), "updated_at": now_iso()}})
        elif t == "charge.refunded":
            await db.payment_transactions.update_one(
                {"stripe_payment_intent_id": obj.get("payment_intent")},
                {"$set": {"status": "refunded", "payment_status": "refunded", "updated_at": now_iso()}})
        return {"status": "ok"}

    # ================= 2) PUBLIC API v1 (dış sistemler bize bağlanır) =================
    async def api_key_auth(request: Request) -> dict:
        key = request.headers.get("X-API-Key", "")
        doc = await db.public_api_keys.find_one({"key": key, "active": {"$ne": False}}, {"_id": 0})
        if not doc:
            raise HTTPException(401, "Geçersiz API anahtarı — X-API-Key header gerekli")
        await db.public_api_keys.update_one({"key": key}, {"$inc": {"calls": 1},
                                                           "$set": {"last_used": now_iso()}})
        return doc

    @router.post("/public-keys/{pid}")
    async def create_api_key(pid: str, data: dict = None, _u: dict = Depends(require_roles("admin"))):
        doc = {"id": str(uuid.uuid4()), "key": f"hbx_{secrets.token_urlsafe(24)}",
               "property_id": pid, "name": (data or {}).get("name", "default"),
               "active": True, "calls": 0, "created_at": now_iso()}
        await db.public_api_keys.insert_one({**doc})
        return doc

    @router.get("/public-keys/{pid}")
    async def list_api_keys(pid: str, _u: dict = Depends(require_roles("admin"))):
        rows = await db.public_api_keys.find({"property_id": pid}, {"_id": 0}).to_list(20)
        for r in rows:
            r["key"] = r["key"][:12] + "•••"
        return {"keys": rows}

    @router.get("/public/v1/bookings")
    async def pub_bookings(request: Request, limit: int = 50):
        k = await api_key_auth(request)
        rows = await db.bookings.find({"property_id": k["property_id"]}, {"_id": 0}).sort(
            "created_at", -1).to_list(min(limit, 200))
        return {"bookings": rows}

    @router.get("/public/v1/rates")
    async def pub_rates(request: Request, days: int = 14):
        k = await api_key_auth(request)
        from routes.distribution.cloudbeds_adapter import _build_rate_blocks
        cfg = await db.cloudbeds_config.find_one({"property_id": k["property_id"]}, {"_id": 0}) or {}
        blocks = await _build_rate_blocks(db, k["property_id"], min(days, 30), cfg)
        return {"rates": blocks}

    @router.get("/public/v1/guests")
    async def pub_guests(request: Request, limit: int = 50):
        k = await api_key_auth(request)
        rows = await db.guests.find({"property_id": k["property_id"]},
                                    {"_id": 0}).to_list(min(limit, 200))
        return {"guests": rows}

    @router.post("/public/v1/bookings")
    async def pub_create_booking(request: Request, data: dict):
        k = await api_key_auth(request)
        doc = {"id": str(uuid.uuid4()), "property_id": k["property_id"],
               "guest_name": str(data.get("guest_name", ""))[:100],
               "check_in": data.get("check_in"), "check_out": data.get("check_out"),
               "room_type_id": data.get("room_type_id", ""), "status": "confirmed",
               "total_price": float(data.get("total_price") or 0),
               "source": "public_api", "created_at": now_iso()}
        if not (doc["guest_name"] and doc["check_in"] and doc["check_out"]):
            raise HTTPException(422, "guest_name, check_in, check_out zorunlu")
        await db.bookings.insert_one({**doc})
        await emit_webhook(db, k["property_id"], "booking.created", doc)
        return doc

    # -------- Giden webhook abonelikleri --------
    @router.get("/webhook-subs/{pid}")
    async def list_subs(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.webhook_subscriptions.find({"property_id": pid}, {"_id": 0}).to_list(20)
        deliveries = await db.webhook_deliveries.find({"property_id": pid}, {"_id": 0}).sort(
            "at", -1).to_list(10)
        return {"subscriptions": rows, "recent_deliveries": deliveries,
                "events": ["booking.created", "payment.completed", "rate.updated", "*"]}

    @router.post("/webhook-subs/{pid}")
    async def add_sub(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        doc = {"id": str(uuid.uuid4()), "property_id": pid, "url": str(data.get("url", ""))[:300],
               "events": data.get("events") or ["*"], "secret": secrets.token_urlsafe(16),
               "active": True, "created_at": now_iso()}
        if not doc["url"].startswith("http"):
            raise HTTPException(422, "Geçerli URL gerekli")
        await db.webhook_subscriptions.insert_one({**doc})
        return doc

    # ================= 3) SÜPER ADMİN KONSOLU =================
    PLAN_MODULES = {"basic": "Ön büro + rezervasyon + takvim (çekirdek ~30 modül)",
                    "rms": "Sadece Gelir Yönetimi — fiyatlama, forecast, compset, raporlar",
                    "cm": "Sadece Channel Manager — kanallar, eşleme, booking engine",
                    "pro": "Basic + gelir yönetimi + kanallar + raporlar (~150 modül)",
                    "full": "Tüm 280+ modül + Public API + süper admin"}

    @router.get("/super-admin/tenants")
    async def tenants(_u: dict = Depends(require_roles("admin"))):
        props = await db.properties.find({}, {"_id": 0, "id": 1, "name": 1, "plan": 1,
                                              "is_active": 1, "suspended": 1,
                                              "provisioned_at": 1}).to_list(100)
        out = []
        for p in props:
            pid = p["id"]
            out.append({**p,
                        "bookings": await db.bookings.count_documents({"property_id": pid}),
                        "room_types": await db.room_types.count_documents({"property_id": pid}),
                        "payments": await db.payment_transactions.count_documents({"property_id": pid}),
                        "api_keys": await db.public_api_keys.count_documents({"property_id": pid})})
        return {"tenants": out, "total": len(out), "plans": PLAN_MODULES}

    @router.post("/super-admin/tenants/{pid}/suspend")
    async def suspend(pid: str, data: dict, _u: dict = Depends(require_roles("admin"))):
        sus = bool(data.get("suspended", True))
        await db.properties.update_one({"id": pid}, {"$set": {"suspended": sus,
                                                              "suspended_at": now_iso() if sus else None}})
        return {"ok": True, "property_id": pid, "suspended": sus}

    # ================= 3b) SAĞLIK SKORU + PLAN + ONBOARDING =================
    async def _health_steps(pid: str) -> list:
        rts = await db.room_types.find({"property_id": pid}, {"_id": 0, "base_rate": 1, "base_price": 1}).to_list(20)
        has_rates = any(float(r.get("base_rate") or r.get("base_price") or 0) > 0 for r in rts) or \
            await db.rate_overrides.count_documents({"property_id": pid}) > 0
        cb = await db.cloudbeds_config.find_one({"property_id": pid}, {"_id": 0, "api_key": 1, "rate_map": 1}) or {}
        return [
            {"key": "rooms", "label": "Oda tipleri tanımlı", "done": len(rts) > 0, "link": "settings"},
            {"key": "rates", "label": "Fiyatlar girilmiş", "done": bool(has_rates), "link": "revenue"},
            {"key": "channel", "label": "Kanal bağlantısı (Cloudbeds/PMS eşleme)",
             "done": bool(cb.get("api_key") or cb.get("rate_map")), "link": "cloudbeds-live"},
            {"key": "payment", "label": "İlk ödeme linki üretilmiş",
             "done": await db.payment_transactions.count_documents({"property_id": pid}) > 0,
             "link": "super-admin"},
            {"key": "api", "label": "Public API anahtarı oluşturulmuş",
             "done": await db.public_api_keys.count_documents({"property_id": pid}) > 0,
             "link": "super-admin"},
        ]

    @router.get("/onboarding/{pid}")
    async def onboarding(pid: str, _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        steps = await _health_steps(pid)
        done = sum(1 for s in steps if s["done"])
        return {"property_id": pid, "steps": steps, "done": done, "total": len(steps),
                "score": int(done / len(steps) * 100)}

    PLAN_PRICES = {"basic": 49, "rms": 99, "cm": 99, "pro": 149, "full": 199}  # £/ay liste fiyatı

    @router.get("/super-admin/health-scores")
    async def health_scores(_u: dict = Depends(require_roles("admin"))):
        props = await db.properties.find({"is_active": {"$ne": False}},
                                         {"_id": 0, "id": 1, "name": 1, "plan": 1, "suspended": 1,
                                          "promo_code": 1, "promo_pct": 1, "promo_until": 1}).to_list(100)
        out = []
        for p in props:
            steps = await _health_steps(p["id"])
            done = sum(1 for s in steps if s["done"])
            list_price = PLAN_PRICES.get(p.get("plan") or "full", 199)
            promo_active = (p.get("promo_code") == "WINBACK20"
                            and (p.get("promo_until") or "") > now_iso())
            billed = round(list_price * (1 - (p.get("promo_pct") or 0) / 100), 2) if promo_active else list_price
            out.append({**{k: v for k, v in p.items() if k not in ("promo_code",)},
                        "score": int(done / len(steps) * 100),
                        "missing": [s["label"] for s in steps if not s["done"]],
                        "list_price": list_price, "billed_price": billed,
                        "promo_active": promo_active,
                        "promo_pct": p.get("promo_pct") if promo_active else None,
                        "promo_until": p.get("promo_until") if promo_active else None})
        out.sort(key=lambda x: x["score"])
        mrr = round(sum(t["billed_price"] for t in out if not t.get("suspended")), 2)
        # Son 6 ay MRR trendi (tesisin katılım tarihine göre geriye dönük kurgu) + bugünün anlık değeri
        from datetime import datetime as _dt, timezone as _tz
        raw = await db.properties.find({"is_active": {"$ne": False}},
                                       {"_id": 0, "plan": 1, "suspended": 1, "provisioned_at": 1,
                                        "created_at": 1, "trial_started_at": 1,
                                        "promo_pct": 1, "promo_code": 1, "promo_until": 1,
                                        "promo_claimed_at": 1}).to_list(100)
        now_dt = _dt.now(_tz.utc)
        months = []
        y, m = now_dt.year, now_dt.month
        for i in range(5, -1, -1):
            mm = m - i
            yy = y + (mm - 1) // 12
            mm = (mm - 1) % 12 + 1
            month_end = f"{yy:04d}-{mm:02d}-31"
            total = 0.0
            for p in raw:
                if p.get("suspended"):
                    continue
                joined = p.get("provisioned_at") or p.get("trial_started_at") or p.get("created_at") or ""
                if joined and joined[:10] > month_end:
                    continue
                price = PLAN_PRICES.get(p.get("plan") or "full", 199)
                if (p.get("promo_code") == "WINBACK20" and (p.get("promo_claimed_at") or "")[:7] <= f"{yy:04d}-{mm:02d}"
                        and (p.get("promo_until") or "") > f"{yy:04d}-{mm:02d}-01"):
                    price = round(price * (1 - (p.get("promo_pct") or 0) / 100), 2)
                total += price
            months.append({"month": f"{yy:04d}-{mm:02d}", "mrr": round(total, 2)})
        return {"tenants": out, "plans": PLAN_MODULES, "plan_prices": PLAN_PRICES, "mrr": mrr,
                "mrr_target": ((await db.platform_settings.find_one({"id": "billing"}, {"_id": 0, "mrr_target": 1})) or {}).get("mrr_target"),
                "mrr_trend": months}

    @router.post("/super-admin/tenants/{pid}/plan")
    async def set_plan(pid: str, data: dict, _u: dict = Depends(require_roles("admin"))):
        plan = str(data.get("plan", "full"))
        if plan not in PLAN_MODULES:
            raise HTTPException(422, "plan: basic|rms|cm|pro|full")
        prev = await db.properties.find_one({"id": pid}, {"_id": 0, "plan": 1})
        await db.properties.update_one({"id": pid}, {"$set": {
            "plan": plan, "modules_enabled": "all" if plan == "full" else plan,
            "plan_changed_at": now_iso()}})
        if prev and prev.get("plan") != plan:
            await db.plan_changes.insert_one({
                "property_id": pid, "from_plan": prev.get("plan") or "full", "to_plan": plan,
                "changed_by": _u.get("email", ""), "changed_at": now_iso(), "source": "super-admin"})
        return {"ok": True, "property_id": pid, "plan": plan, "scope": PLAN_MODULES[plan]}

    @router.get("/super-admin/plan-history")
    async def plan_history(property_id: str = "", _u: dict = Depends(require_roles("admin"))):
        q = {"property_id": property_id} if property_id else {}
        items = await db.plan_changes.find(q, {"_id": 0}).sort("changed_at", -1).to_list(50)
        return {"items": items}

    @router.post("/super-admin/mrr-target")
    async def set_mrr_target(data: dict, _u: dict = Depends(require_roles("admin"))):
        try:
            target = float(data.get("target"))
        except (TypeError, ValueError):
            raise HTTPException(422, "target: sayı olmalı")
        await db.platform_settings.update_one({"id": "billing"}, {"$set": {
            "id": "billing", "mrr_target": target, "updated_at": now_iso()}}, upsert=True)
        return {"ok": True, "mrr_target": target}

    # ================= 4) VERİ GÖÇÜ (CSV IMPORT) =================
    @router.get("/migration/template/{kind}")
    async def template(kind: str, _u: dict = Depends(require_roles(*ROLES))):
        cols = {"bookings": "guest_name,check_in,check_out,room_type_name,total_price,status",
                "guests": "name,email,phone,country,notes",
                "room_types": "name,base_rate,total_rooms,max_guests"}
        if kind not in cols:
            raise HTTPException(404, "kind: bookings|guests|room_types")
        return {"kind": kind, "csv_header": cols[kind]}

    @router.post("/migration/import/{pid}/{kind}")
    async def import_csv(pid: str, kind: str, file: UploadFile = File(...),
                         _u: dict = Depends(require_roles(*ROLES))):
        """CSV import: bookings/guests/room_types — eski PMS'ten veri göçü."""
        if kind not in ("bookings", "guests", "room_types"):
            raise HTTPException(404, "kind: bookings|guests|room_types")
        text = (await file.read()).decode("utf-8-sig", errors="ignore")
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows:
            raise HTTPException(422, "CSV boş veya başlık satırı eksik")
        imported, errors = 0, []
        rt_by_name = {r["name"].lower(): r["id"] for r in
                      await db.room_types.find({"property_id": pid}, {"_id": 0, "id": 1, "name": 1}).to_list(50)}
        for i, r in enumerate(rows[:2000]):
            try:
                if kind == "room_types":
                    await db.room_types.insert_one({
                        "id": str(uuid.uuid4()), "property_id": pid, "name": r["name"].strip(),
                        "base_rate": float(r.get("base_rate") or 100),
                        "total_rooms": int(r.get("total_rooms") or 1),
                        "max_guests": int(r.get("max_guests") or 2),
                        "is_active": True, "source": "migration", "created_at": now_iso()})
                elif kind == "guests":
                    await db.guests.insert_one({
                        "id": str(uuid.uuid4()), "property_id": pid, "name": r["name"].strip(),
                        "email": r.get("email", ""), "phone": r.get("phone", ""),
                        "country": r.get("country", ""), "notes": r.get("notes", ""),
                        "source": "migration", "created_at": now_iso()})
                else:
                    ci, co = r["check_in"].strip(), r["check_out"].strip()
                    datetime.fromisoformat(ci); datetime.fromisoformat(co)
                    if co <= ci:
                        raise ValueError("check_out check_in'den sonra olmalı")
                    await db.bookings.insert_one({
                        "id": str(uuid.uuid4()), "property_id": pid,
                        "guest_name": r["guest_name"].strip(),
                        "check_in": ci, "check_out": co,
                        "room_type_id": rt_by_name.get((r.get("room_type_name") or "").lower(), ""),
                        "total_price": float(r.get("total_price") or 0),
                        "status": r.get("status", "confirmed") or "confirmed",
                        "source": "migration", "created_at": now_iso()})
                imported += 1
            except Exception as e:
                errors.append({"row": i + 2, "error": str(e)[:80]})
        await db.migration_log.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "kind": kind, "file": file.filename,
            "imported": imported, "errors": len(errors), "by": str(_u.get("email") or ""),
            "at": now_iso()})
        return {"ok": True, "kind": kind, "imported": imported, "errors": errors[:10],
                "total_rows": len(rows)}

    return router
