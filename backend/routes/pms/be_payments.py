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
        amount = float(booking.get("cart_total") or booking.get("total_price") or 0)
        if data.get("amount_mode") == "deposit" and booking.get("deposit_due"):
            amount = float(booking["deposit_due"])
        if amount <= 0:
            raise HTTPException(400, "Tutar geçersiz")
        import stripe
        stripe.api_key = secret
        cur = (booking.get("currency") or "gbp").lower()
        if booking.get("stripe_pi_id"):
            try:
                pi = stripe.PaymentIntent.retrieve(booking["stripe_pi_id"])
                if pi.status in ("requires_payment_method", "requires_confirmation", "requires_action"):
                    return {"client_secret": pi.client_secret, "amount": amount, "currency": cur, "publishable_key": publishable}
            except Exception:
                pass
        pi = stripe.PaymentIntent.create(amount=int(round(amount * 100)), currency=cur, automatic_payment_methods={"enabled": True},
                                         receipt_email=booking.get("guest_email") or None,
                                         metadata={"type": "booking", "booking_id": booking["id"], "booking_ref": booking.get("booking_ref", ""), "property_id": booking.get("property_id", "")})
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
        upd = {"payment_status": "paid", "payment_method": "stripe", "paid_at": now, "paid_amount": pi.amount_received / 100.0}
        await db.bookings.update_one({"id": booking["id"]}, {"$set": upd})
        if booking.get("cart_master") and booking.get("cart_ref"):
            await db.bookings.update_many({"cart_ref": booking["cart_ref"]}, {"$set": {"payment_status": "paid", "payment_method": "stripe", "paid_at": now}})
        await db.payment_transactions.update_one({"session_id": pi.id}, {"$set": {"payment_status": "paid", "paid_at": now}})
        try:
            from routes.pms.guest_email_i18n import send_guest_confirmation
            await send_guest_confirmation(db, {**booking, **upd})
        except Exception:
            pass
        return {"paid": True, "status": "succeeded", "booking_ref": booking.get("booking_ref")}

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
