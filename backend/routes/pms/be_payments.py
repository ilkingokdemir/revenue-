"""Sayfa içi ödeme (Stripe Payment Element) + AI site çevirisi."""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException


def create_be_payments_router(db, require_roles):
    router = APIRouter()
    secret = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY", "")
    publishable = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

    @router.get("/payments/config")
    async def payments_config():
        return {"publishable_key": publishable, "inline_enabled": bool(secret and publishable)}

    @router.post("/payments/intent")
    async def create_intent(data: Dict):
        """Public: booking için PaymentIntent (kart, Apple Pay, Google Pay otomatik)."""
        if not secret:
            raise HTTPException(503, "Stripe yapılandırılmamış")
        booking = await db.bookings.find_one({"id": data.get("booking_id")}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Rezervasyon yok")
        total = float(booking.get("cart_total") or booking.get("total_price") or 0)
        amount = total
        is_deposit = False
        if data.get("amount_mode") == "deposit":
            from routes.pms.be_payment_plans import compute_deposit
            dep = float(booking.get("deposit_due") or 0) or await compute_deposit(db, booking)
            if 0 < dep < total:
                amount, is_deposit = round(dep, 2), True
                await db.bookings.update_one({"id": booking["id"]}, {"$set": {"deposit_due": amount, "balance_due": round(total - amount, 2), "payment_plan": "deposit"}})
        if amount <= 0:
            raise HTTPException(400, "Tutar geçersiz")
        import stripe
        stripe.api_key = secret
        cur = (booking.get("currency") or "gbp").lower()
        extra = {}
        if is_deposit:  # kalan bakiye için kartı sakla (off-session tahsilat)
            cust = stripe.Customer.create(email=booking.get("guest_email") or None, name=booking.get("guest_name") or None, metadata={"booking_ref": booking.get("booking_ref", "")})
            extra = {"customer": cust.id, "setup_future_usage": "off_session"}
            await db.bookings.update_one({"id": booking["id"]}, {"$set": {"stripe_customer_id": cust.id}})
        if booking.get("stripe_pi_id"):
            try:
                pi = stripe.PaymentIntent.retrieve(booking["stripe_pi_id"])
                if pi.status in ("requires_payment_method", "requires_confirmation", "requires_action"):
                    return {"client_secret": pi.client_secret, "amount": amount, "currency": cur, "publishable_key": publishable}
            except Exception:
                pass
        pi = stripe.PaymentIntent.create(amount=int(round(amount * 100)), currency=cur, automatic_payment_methods={"enabled": True},
                                         receipt_email=booking.get("guest_email") or None, **extra,
                                         metadata={"type": "booking", "booking_id": booking["id"], "booking_ref": booking.get("booking_ref", ""), "property_id": booking.get("property_id", ""), "amount_mode": "deposit" if is_deposit else "full"})
        await db.bookings.update_one({"id": booking["id"]}, {"$set": {"stripe_pi_id": pi.id}})
        await db.payment_transactions.insert_one({"id": str(uuid.uuid4()), "session_id": pi.id, "type": "booking", "reference_id": booking["id"], "reference_number": booking.get("booking_ref"),
                                                  "property_id": booking.get("property_id"), "amount": amount, "currency": cur, "guest_name": booking.get("guest_name"), "guest_email": booking.get("guest_email"),
                                                  "payment_method": "stripe_element", "payment_status": "initiated", "created_at": datetime.now(timezone.utc).isoformat()})
        return {"client_secret": pi.client_secret, "amount": amount, "currency": cur, "publishable_key": publishable}

    @router.post("/payments/intent/confirm")
    async def confirm_intent(data: Dict):
        """Public: client confirm sonrası sunucu tarafı doğrulama → booking paid."""
        if not secret:
            raise HTTPException(503, "Stripe yapılandırılmamış")
        import stripe
        stripe.api_key = secret
        booking = await db.bookings.find_one({"id": data.get("booking_id")}, {"_id": 0})
        if not booking or not booking.get("stripe_pi_id"):
            raise HTTPException(404, "Rezervasyon/ödeme yok")
        pi = stripe.PaymentIntent.retrieve(booking["stripe_pi_id"])
        if pi.status != "succeeded":
            return {"paid": False, "status": pi.status}
        now = datetime.now(timezone.utc).isoformat()
        paid = pi.amount_received / 100.0
        total = float(booking.get("cart_total") or booking.get("total_price") or 0)
        if (pi.metadata or {}).get("amount_mode") == "deposit" and paid < total - 0.5:
            from routes.pms.be_payment_plans import schedule_balance
            upd = await schedule_balance(db, booking, paid, getattr(pi, "payment_method", None), getattr(pi, "customer", None) or booking.get("stripe_customer_id"))
            upd.update({"payment_method": "stripe", "paid_at": now, "paid_amount": paid})
            await db.bookings.update_one({"id": booking["id"]}, {"$set": {"payment_method": "stripe", "paid_at": now, "paid_amount": paid}})
        else:
            upd = {"payment_status": "paid", "payment_method": "stripe", "paid_at": now, "paid_amount": paid}
            await db.bookings.update_one({"id": booking["id"]}, {"$set": upd})
            if booking.get("cart_master") and booking.get("cart_ref"):
                await db.bookings.update_many({"cart_ref": booking["cart_ref"]}, {"$set": {"payment_status": "paid", "payment_method": "stripe", "paid_at": now}})
        await db.payment_transactions.update_one({"session_id": pi.id}, {"$set": {"payment_status": "paid", "paid_at": now}})
        try:
            from routes.pms.guest_email_i18n import send_guest_confirmation
            await send_guest_confirmation(db, {**booking, **upd})
        except Exception:
            pass
        return {"paid": True, "status": "succeeded", "booking_ref": booking.get("booking_ref"), "payment_status": upd.get("payment_status"), "balance_due": upd.get("balance_due", 0), "balance_due_date": upd.get("balance_due_date")}

    # ---------------- UPSELL ÖDEMESİ (onay ekranı) ----------------
    async def _upsell_booking(data: Dict):
        b = await db.bookings.find_one({"booking_ref": (data.get("booking_ref") or "").strip(), "guest_email": (data.get("guest_email") or "").strip()}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        unpaid = [u for u in (b.get("post_upsells") or []) if not u.get("paid")]
        return b, unpaid, round(sum(float(u.get("price") or 0) for u in unpaid), 2)

    @router.post("/payments/upsell-intent")
    async def upsell_intent(data: Dict):
        """Public: onay ekranında eklenen ekstralar için PaymentIntent."""
        if not secret:
            raise HTTPException(503, "Stripe yapılandırılmamış")
        b, unpaid, amount = await _upsell_booking(data)
        if amount <= 0:
            raise HTTPException(400, "Ödenecek ekstra yok")
        import stripe
        stripe.api_key = secret
        cur = (b.get("currency") or "gbp").lower()
        if b.get("upsell_pi_id"):
            try:
                old = stripe.PaymentIntent.retrieve(b["upsell_pi_id"])
                if old.status in ("requires_payment_method", "requires_confirmation", "requires_action") and old.amount == int(round(amount * 100)):
                    return {"client_secret": old.client_secret, "amount": amount, "currency": cur, "publishable_key": publishable, "items": [u.get("name") for u in unpaid]}
            except Exception:
                pass
        pi = stripe.PaymentIntent.create(amount=int(round(amount * 100)), currency=cur, automatic_payment_methods={"enabled": True},
                                         receipt_email=b.get("guest_email") or None,
                                         metadata={"type": "upsell", "booking_id": b["id"], "booking_ref": b.get("booking_ref", ""), "property_id": b.get("property_id", ""),
                                                   "items": ",".join(u.get("name", "")[:30] for u in unpaid)[:400]})
        await db.bookings.update_one({"id": b["id"]}, {"$set": {"upsell_pi_id": pi.id}})
        return {"client_secret": pi.client_secret, "amount": amount, "currency": cur, "publishable_key": publishable, "items": [u.get("name") for u in unpaid]}

    @router.post("/payments/upsell-intent/confirm")
    async def upsell_confirm(data: Dict):
        if not secret:
            raise HTTPException(503, "Stripe yapılandırılmamış")
        b, unpaid, amount = await _upsell_booking(data)
        pi_id = str(data.get("payment_intent_id") or "").split("_secret")[0] or b.get("upsell_pi_id")
        if not pi_id:
            raise HTTPException(404, "Ödeme başlatılmamış")
        import stripe
        stripe.api_key = secret
        pi = stripe.PaymentIntent.retrieve(pi_id)
        meta = pi.metadata.to_dict() if hasattr(pi.metadata, "to_dict") else dict(pi.metadata or {})
        if meta.get("type") != "upsell" or meta.get("booking_id") != b["id"]:
            raise HTTPException(400, "Ödeme bu rezervasyona ait değil")
        if pi.status != "succeeded":
            return {"paid": False, "status": pi.status}
        if not unpaid:
            return {"paid": True, "already": True, "amount": pi.amount_received / 100.0}
        now = datetime.now(timezone.utc).isoformat()
        paid_amt = pi.amount_received / 100.0
        items = [{**u, "paid": True, "paid_at": now, "payment_method": "stripe"} if not u.get("paid") else u for u in (b.get("post_upsells") or [])]
        await db.bookings.update_one({"id": b["id"]}, {"$set": {"post_upsells": items, "balance_due": max(0.0, round(float(b.get("balance_due") or 0) - paid_amt, 2)),
                                                                "post_upsell_paid_total": round(float(b.get("post_upsell_paid_total") or 0) + paid_amt, 2)},
                                                       "$unset": {"upsell_pi_id": ""}})
        await db.payment_transactions.insert_one({"id": str(uuid.uuid4()), "session_id": pi.id, "type": "upsell", "reference_id": b["id"], "reference_number": b.get("booking_ref"),
                                                  "property_id": b.get("property_id"), "amount": paid_amt, "currency": (b.get("currency") or "gbp").lower(), "guest_name": b.get("guest_name"),
                                                  "guest_email": b.get("guest_email"), "payment_method": "stripe_element", "payment_status": "paid", "paid_at": now, "created_at": now})
        return {"paid": True, "amount": paid_amt, "items": [u.get("name") for u in unpaid]}

    # ---------------- AI ÇEVİRİ ----------------
    @router.post("/site-builder/{pid}/translate")
    async def ai_translate(pid: str, data: Dict, _u: dict = Depends(require_roles("admin", "manager"))):
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            raise HTTPException(503, "LLM anahtarı yok")
        target = data.get("lang") if data.get("lang") in ("en", "de", "tr") else "en"
        src = {k: (data.get(k) or "")[:2000] for k in ("headline", "about", "seo_title", "seo_description")}
        faqs = [{"q": str(f.get("q", ""))[:200], "a": str(f.get("a", ""))[:800]} for f in (data.get("faqs") or [])[:12] if f.get("q")]
        if not any(src.values()) and not faqs:
            raise HTTPException(422, "Çevrilecek içerik yok")
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        lang_name = {"en": "English", "de": "German", "tr": "Turkish"}[target]
        chat = LlmChat(api_key=key, session_id=f"site-tr-{uuid.uuid4()}",
                       system_message=f"You are a professional hotel marketing translator. Translate the JSON values into natural, persuasive {lang_name} suitable for a hotel website. Keep the JSON structure and keys identical, keep brand/place names, do not add keys. Respond ONLY with valid JSON.").with_model("openai", "gpt-5.2")
        payload = {**src, "faqs": faqs}
        resp = await chat.send_message(UserMessage(text=json.dumps(payload, ensure_ascii=False)))
        txt = str(resp).strip()
        if txt.startswith("```"):
            txt = txt.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        try:
            out = json.loads(txt)
        except Exception:
            raise HTTPException(502, "Çeviri ayrıştırılamadı — tekrar deneyin")
        result = {k: str(out.get(k) or "")[:2000] for k in src if out.get(k)}
        result_faqs = [{"q": str(f.get("q", ""))[:200], "a": str(f.get("a", ""))[:1000]} for f in (out.get("faqs") or []) if isinstance(f, dict) and f.get("q")]
        return {"lang": target, "translation": result, "faqs": result_faqs}

    return router
