"""
Pay-by-Link — Stripe hosted checkout ile rezervasyon bakiyesi tahsilatı.
Resepsiyon tek tıkla ödeme linki üretir; misafir linkten öder; sistem folioyu günceller.

Endpoints:
- POST /api/pay-links/create {booking_id, amount?, origin_url} (staff)
- GET  /api/pay-links/{booking_id} (staff) — geçmiş linkler
- GET  /api/pay-links/status/{session_id} (public, poll)
- POST /api/stripe/webhook
"""
import os
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import resend
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import require_perm

logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


class PayLinkIn(BaseModel):
    booking_id: str
    amount: Optional[float] = None
    origin_url: str


class SendLinkIn(BaseModel):
    booking_id: str
    checkout_url: str
    amount: float
    currency: str = "GBP"
    language: str = "en"


class BulkSendIn(BaseModel):
    property_id: str = ""
    language: str = "en"


_EMAIL_I18N = {
    "en": {"dear": "Dear", "body": "Please use the secure link below to complete your payment of",
           "btn": "Pay Securely", "note": "Payment is processed securely by Stripe.",
           "reminder": "This is a friendly reminder — your payment is still pending.",
           "subject": "Payment request", "rem_subject": "Payment reminder"},
    "tr": {"dear": "Sayın", "body": "Aşağıdaki güvenli bağlantıyı kullanarak ödemenizi tamamlayabilirsiniz:",
           "btn": "Güvenli Öde", "note": "Ödemeniz Stripe altyapısıyla güvenle işlenir.",
           "reminder": "Nazik bir hatırlatma — ödemeniz henüz tamamlanmadı.",
           "subject": "Ödeme talebi", "rem_subject": "Ödeme hatırlatması"},
    "de": {"dear": "Sehr geehrte/r", "body": "Bitte nutzen Sie den sicheren Link unten, um Ihre Zahlung abzuschließen:",
           "btn": "Sicher bezahlen", "note": "Die Zahlung wird sicher über Stripe abgewickelt.",
           "reminder": "Eine freundliche Erinnerung — Ihre Zahlung steht noch aus.",
           "subject": "Zahlungsanforderung", "rem_subject": "Zahlungserinnerung"},
}


class TipApplyIn(BaseModel):
    property_id: str = "all"
    tip: str


def _link_email_html(booking: dict, hotel: str, checkout_url: str, amount: float,
                     currency: str, reminder: bool = False, lang: str = "en") -> str:
    t = _EMAIL_I18N.get(lang, _EMAIL_I18N["en"])
    sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(currency.upper(), currency.upper() + " ")
    note = f"<p style='color:#b45309'>{t['reminder']}</p>" if reminder else ""
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px">
      <h2 style="color:#1c1917">{hotel}</h2>
      <p>{t['dear']} {booking.get('guest_name', '')},</p>
      {note}
      <p>{t['body']} <b>{sym}{amount:.2f}</b>
         ({booking.get('check_in')} → {booking.get('check_out')}).</p>
      <p style="margin:28px 0;text-align:center">
        <a href="{checkout_url}" style="background:#4f46e5;color:#fff;padding:12px 28px;
           border-radius:8px;text-decoration:none;font-weight:bold">{t['btn']}</a>
      </p>
      <p style="color:#78716c;font-size:12px">{t['note']}</p>
    </div>"""


async def _deliver_email(to: str, subject: str, html: str) -> bool:
    """Returns True if actually sent, False if mocked/failed."""
    import resend
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key or api_key == "re_123456789":
        return False
    resend.api_key = api_key
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
            "to": [to], "subject": subject, "html": html})
        return True
    except Exception as e:
        logger.warning(f"pay-link email failed: {e}")
        return False


async def run_pay_link_reminders(db, property_id: str = "") -> dict:
    """24 saatten eski, ödenmemiş pay-by-link'ler için yeni Stripe linki üretip hatırlatma e-postası gönderir."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()
    q = {"kind": "pay_by_link", "payment_status": "pending",
         "created_at": {"$lt": cutoff}, "reminder_sent": {"$ne": True}}
    if property_id and property_id != "all":
        q["property_id"] = property_id
    txs = await db.payment_transactions.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
    base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
    sent = skipped = 0
    seen_bookings = set()
    for tx in txs:
        bid = tx.get("booking_id")
        if not bid or bid in seen_bookings:
            skipped += 1
            continue
        seen_bookings.add(bid)
        booking = await db.bookings.find_one({"id": bid}, {"_id": 0})
        if not booking or booking.get("payment_status") == "paid" or not booking.get("guest_email"):
            await db.payment_transactions.update_one(
                {"session_id": tx["session_id"]},
                {"$set": {"reminder_sent": True, "reminder_skipped": True}})
            skipped += 1
            continue
        amount = float(tx.get("amount") or 0)
        currency = (tx.get("currency") or "gbp").lower()
        try:
            session = stripe.checkout.Session.create(
                line_items=[{"price_data": {
                    "currency": currency,
                    "unit_amount": int(round(amount * 100)),
                    "product_data": {"name": f"Konaklama ödemesi — {booking.get('guest_name', '')} ({booking.get('check_in')} → {booking.get('check_out')})"},
                }, "quantity": 1}],
                mode="payment",
                success_url=f"{base}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{base}/payment/cancel",
                metadata={"booking_id": bid, "kind": "pay_by_link", "reminder": "true"})
        except stripe.error.StripeError as e:
            logger.warning(f"reminder session create failed: {e}")
            skipped += 1
            continue
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.payment_transactions.insert_one({
            "session_id": session.id, "booking_id": bid,
            "property_id": booking.get("property_id"), "kind": "pay_by_link",
            "amount": amount, "currency": currency,
            "status": "initiated", "payment_status": "pending",
            "reminder_of": tx["session_id"],
            "created_by": "auto_reminder",
            "created_at": now_iso, "updated_at": now_iso})
        await db.payment_transactions.update_one(
            {"session_id": tx["session_id"]},
            {"$set": {"reminder_sent": True, "reminder_at": now_iso,
                      "superseded_by": session.id}})
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0, "name": 1})
        hotel = (prop or {}).get("name", "Hotel")
        html = _link_email_html(booking, hotel, session.url, amount, currency.upper(), reminder=True)
        delivered = await _deliver_email(booking["guest_email"],
                                         f"{hotel} — Payment reminder", html)
        await db.payment_transactions.update_one(
            {"session_id": session.id},
            {"$set": {"emailed_to": booking["guest_email"], "emailed_at": now_iso,
                      "email_mocked": not delivered}})
        sent += 1
    return {"ok": True, "reminders_sent": sent, "skipped": skipped}


async def _mark_paid(db, session_id: str, extra: dict):
    res = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid",
                  "updated_at": datetime.now(timezone.utc).isoformat(), **extra}})
    if res.modified_count:
        tx = await db.payment_transactions.find_one({"session_id": session_id})
        if tx and tx.get("booking_id"):
            booking = await db.bookings.find_one(
                {"id": tx["booking_id"]}, {"_id": 0, "guest_name": 1, "booking_ref": 1, "total_price": 1})
            paid_txs = await db.payment_transactions.find(
                {"booking_id": tx["booking_id"], "kind": "pay_by_link", "payment_status": "paid"},
                {"_id": 0, "amount": 1}).to_list(50)
            paid_total = sum(float(t.get("amount") or 0) for t in paid_txs)
            total_price = float((booking or {}).get("total_price") or 0)
            new_status = "paid" if paid_total >= total_price * 0.99 else "partial"
            await db.bookings.update_one({"id": tx["booking_id"]},
                                         {"$set": {"payment_status": new_status}})
            await db.folio_items.insert_one({
                "id": str(uuid.uuid4()), "booking_id": tx["booking_id"],
                "property_id": tx.get("property_id"),
                "type": "payment", "category": "card",
                "description": f"Stripe Pay-by-Link tahsilatı ({(booking or {}).get('booking_ref', '')})",
                "quantity": 1, "unit_price": float(tx.get("amount") or 0),
                "amount": float(tx.get("amount") or 0),
                "currency": (tx.get("currency") or "gbp").upper(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "Stripe Pay-by-Link"})


def create_pay_by_link_router(db):
    router = APIRouter()

    @router.post("/pay-links/create")
    async def create_link(body: PayLinkIn,
                          current_user: dict = Depends(require_perm("edit_bookings"))):
        booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        amount = float(body.amount if body.amount else booking.get("total_price") or 0)
        if amount <= 0:
            raise HTTPException(400, "Tutar 0'dan büyük olmalı")
        currency = (booking.get("currency") or "GBP").lower()
        origin = body.origin_url.rstrip("/")
        kwargs = dict(
            line_items=[{"price_data": {
                "currency": currency,
                "unit_amount": int(round(amount * 100)),
                "product_data": {"name": f"Konaklama ödemesi — {booking.get('guest_name', '')} ({booking.get('check_in')} → {booking.get('check_out')})"},
            }, "quantity": 1}],
            mode="payment",
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/payment/cancel",
            metadata={"booking_id": body.booking_id, "kind": "pay_by_link"},
        )
        try:
            session = stripe.checkout.Session.create(
                **kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
        except stripe.error.InvalidRequestError:
            session = stripe.checkout.Session.create(**kwargs)
        await db.payment_transactions.insert_one({
            "session_id": session.id, "booking_id": body.booking_id,
            "property_id": booking.get("property_id"), "kind": "pay_by_link",
            "amount": amount, "currency": currency,
            "status": "initiated", "payment_status": "pending",
            "created_by": current_user.get("email", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"checkout_url": session.url, "session_id": session.id, "amount": amount, "currency": currency}

    @router.post("/pay-links/send")
    async def send_link_email(body: SendLinkIn,
                              current_user: dict = Depends(require_perm("edit_bookings"))):
        booking = await db.bookings.find_one({"id": body.booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        email = booking.get("guest_email")
        if not email:
            raise HTTPException(400, "Rezervasyonda misafir e-postası yok")
        prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0, "name": 1})
        hotel = (prop or {}).get("name", "Hotel")
        sym = {"GBP": "£", "USD": "$", "EUR": "€", "TRY": "₺"}.get(body.currency.upper(), body.currency.upper() + " ")
        lang = body.language if body.language in _EMAIL_I18N else "en"
        html = _link_email_html(booking, hotel, body.checkout_url, body.amount, body.currency, lang=lang)
        delivered = await _deliver_email(email, f"{hotel} — {_EMAIL_I18N[lang]['subject']} {sym}{body.amount:.2f}", html)
        mocked = not delivered
        last_tx = await db.payment_transactions.find_one(
            {"booking_id": body.booking_id, "kind": "pay_by_link"},
            sort=[("created_at", -1)])
        if last_tx:
            await db.payment_transactions.update_one(
                {"session_id": last_tx["session_id"]},
                {"$set": {"emailed_to": email, "emailed_at": datetime.now(timezone.utc).isoformat(),
                          "email_mocked": mocked}})
        return {"status": "mocked" if mocked else "sent", "to": email}

    @router.get("/pay-links/insights")
    async def links_insights(property_id: str = "", refresh: int = 0,
                             current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        key = property_id or "all"
        now = datetime.now(timezone.utc)

        async def _attach_applied(doc: dict) -> dict:
            logs = await db.pay_link_tip_log.find(
                {"property_id": key}, {"_id": 0}).sort("applied_at", -1).to_list(20)
            conv_now = float((doc.get("stats") or {}).get("conversion_pct") or 0)
            for l in logs:
                if l.get("applied_at", "") < (now - timedelta(days=7)).isoformat():
                    l["impact_pts"] = round(conv_now - float(l.get("baseline_conversion") or 0), 1)
                else:
                    l["impact_pts"] = None
            doc["applied"] = logs
            return doc

        cached = await db.pay_link_insights.find_one({"property_id": key}, {"_id": 0})
        if cached and not refresh and cached.get("created_at", "") > (now - timedelta(hours=24)).isoformat():
            return await _attach_applied(cached)
        q = {"kind": "pay_by_link"}
        if key != "all":
            q["property_id"] = key
        txs = await db.payment_transactions.find(
            q, {"_id": 0, "payment_status": 1, "amount": 1, "created_at": 1,
                "updated_at": 1, "emailed_to": 1, "superseded_by": 1}).to_list(2000)
        active = [t for t in txs if not t.get("superseded_by")]
        paid = [t for t in txs if t.get("payment_status") == "paid"]
        hour_hist = {}
        for t in txs:
            try:
                h = int(t["created_at"][11:13])
                hour_hist.setdefault(h, {"sent": 0, "paid": 0})
                hour_hist[h]["sent"] += 1
                if t.get("payment_status") == "paid":
                    hour_hist[h]["paid"] += 1
            except (ValueError, KeyError, IndexError):
                pass
        conv = round(len(paid) * 100 / len(active), 1) if active else 0
        emailed = sum(1 for t in txs if t.get("emailed_to"))
        context = (f"Toplam link: {len(txs)}, aktif: {len(active)}, ödenen: {len(paid)}, "
                   f"dönüşüm: %{conv}, e-postalanan: {emailed}. "
                   f"Saat bazlı gönderim/ödeme: {hour_hist}")
        tips = []
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import json as _json
            chat = LlmChat(
                api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
                session_id=f"paylink-tips-{uuid.uuid4().hex[:8]}",
                system_message=("Sen bir otel ödeme dönüşüm uzmanısın. Stripe ödeme linki istatistiklerine "
                                "bakıp resepsiyon ekibine 3 kısa, somut, uygulanabilir Türkçe öneri ver. "
                                'SADECE JSON dizi döndür: ["öneri 1","öneri 2","öneri 3"]')
            ).with_model("openai", "gpt-5.2")
            raw = await chat.send_message(UserMessage(text=context))
            start, end = raw.find("["), raw.rfind("]")
            if start >= 0 and end > start:
                tips = [str(t) for t in _json.loads(raw[start:end + 1])][:3]
        except Exception as e:
            logger.warning(f"pay-link insights LLM failed: {e}")
        if not tips:
            tips = ["Linkleri rezervasyondan hemen sonra gönderin — ilk 1 saatte ödeme olasılığı en yüksektir.",
                    "Ödenmeyen linkler için e-postaya ek WhatsApp ile de paylaşın.",
                    "Yüksek tutarlarda %30 depozito seçeneği sunmak dönüşümü artırır."]
        doc = {"property_id": key, "tips": tips,
               "stats": {"total": len(txs), "paid": len(paid), "conversion_pct": conv},
               "created_at": now.isoformat()}
        await db.pay_link_insights.update_one({"property_id": key}, {"$set": doc}, upsert=True)
        return await _attach_applied(doc)

    @router.post("/pay-links/bulk-send")
    async def bulk_send(body: BulkSendIn,
                        current_user: dict = Depends(require_perm("edit_bookings"))):
        q = {"status": "confirmed", "payment_status": {"$in": ["pending", "partial"]},
             "guest_email": {"$nin": [None, ""]}, "total_price": {"$gt": 0}}
        if body.property_id and body.property_id != "all":
            q["property_id"] = body.property_id
        bookings = await db.bookings.find(q, {"_id": 0}).sort("check_in", 1).to_list(20)
        base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
        lang = body.language if body.language in _EMAIL_I18N else "en"
        sent = skipped = 0
        results = []
        for booking in bookings:
            has_pending = await db.payment_transactions.find_one(
                {"booking_id": booking["id"], "kind": "pay_by_link",
                 "payment_status": "pending", "superseded_by": {"$exists": False}}, {"_id": 1})
            if has_pending:
                skipped += 1
                continue
            amount = float(booking.get("total_price") or 0)
            currency = (booking.get("currency") or "gbp").lower()
            try:
                session = stripe.checkout.Session.create(
                    line_items=[{"price_data": {
                        "currency": currency,
                        "unit_amount": int(round(amount * 100)),
                        "product_data": {"name": f"Konaklama ödemesi — {booking.get('guest_name', '')} ({booking.get('check_in')} → {booking.get('check_out')})"},
                    }, "quantity": 1}],
                    mode="payment",
                    success_url=f"{base}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{base}/payment/cancel",
                    metadata={"booking_id": booking["id"], "kind": "pay_by_link", "bulk": "true"})
            except stripe.error.StripeError as e:
                logger.warning(f"bulk session failed: {e}")
                skipped += 1
                continue
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.payment_transactions.insert_one({
                "session_id": session.id, "booking_id": booking["id"],
                "property_id": booking.get("property_id"), "kind": "pay_by_link",
                "amount": amount, "currency": currency,
                "status": "initiated", "payment_status": "pending",
                "created_by": f"bulk:{current_user.get('email', '')}",
                "created_at": now_iso, "updated_at": now_iso})
            prop = await db.properties.find_one({"id": booking.get("property_id", "")}, {"_id": 0, "name": 1})
            hotel = (prop or {}).get("name", "Hotel")
            html = _link_email_html(booking, hotel, session.url, amount, currency.upper(), lang=lang)
            delivered = await _deliver_email(
                booking["guest_email"], f"{hotel} — {_EMAIL_I18N[lang]['subject']}", html)
            await db.payment_transactions.update_one(
                {"session_id": session.id},
                {"$set": {"emailed_to": booking["guest_email"], "emailed_at": now_iso,
                          "email_mocked": not delivered}})
            sent += 1
            results.append({"booking_ref": booking.get("booking_ref"),
                            "guest": booking.get("guest_name"), "amount": amount})
        return {"ok": True, "sent": sent, "skipped": skipped, "results": results}

    @router.post("/pay-links/insights/apply")
    async def apply_tip(body: TipApplyIn,
                        current_user: dict = Depends(require_perm("edit_bookings"))):
        key = body.property_id or "all"
        q = {"kind": "pay_by_link"}
        if key != "all":
            q["property_id"] = key
        txs = await db.payment_transactions.find(
            q, {"_id": 0, "payment_status": 1, "superseded_by": 1}).to_list(2000)
        active = [t for t in txs if not t.get("superseded_by")]
        paid = [t for t in active if t.get("payment_status") == "paid"]
        baseline = round(len(paid) * 100 / len(active), 1) if active else 0
        log = {"id": str(uuid.uuid4()), "property_id": key, "tip": body.tip[:500],
               "baseline_conversion": baseline,
               "applied_at": datetime.now(timezone.utc).isoformat(),
               "applied_by": current_user.get("email", "")}
        await db.pay_link_tip_log.insert_one({**log})
        return log

    @router.get("/pay-links/stats")
    async def links_stats(property_id: str = "",
                          current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        q = {"kind": "pay_by_link"}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        txs = await db.payment_transactions.find(
            q, {"_id": 0, "payment_status": 1, "amount": 1, "created_at": 1, "updated_at": 1,
                "superseded_by": 1}).to_list(2000)
        active = [t for t in txs if not t.get("superseded_by")]
        paid = [t for t in txs if t.get("payment_status") == "paid"]
        pending = [t for t in active if t.get("payment_status") == "pending"]
        hours = []
        for t in paid:
            try:
                c = datetime.fromisoformat(t["created_at"])
                u = datetime.fromisoformat(t["updated_at"])
                h = (u - c).total_seconds() / 3600
                if 0 <= h < 24 * 30:
                    hours.append(h)
            except (ValueError, KeyError, TypeError):
                pass
        return {
            "total_links": len(txs),
            "paid_links": len(paid),
            "pending_links": len(pending),
            "conversion_pct": round(len(paid) * 100 / len(active), 1) if active else 0,
            "total_collected": round(sum(float(t.get("amount") or 0) for t in paid), 2),
            "avg_hours_to_pay": round(sum(hours) / len(hours), 1) if hours else None,
        }

    @router.get("/pay-links/history")
    async def links_history(property_id: str = "", limit: int = 50,
                            current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        q = {"kind": "pay_by_link"}
        if property_id and property_id != "all":
            q["property_id"] = property_id
        txs = await db.payment_transactions.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(int(limit), 200))
        bids = list({t["booking_id"] for t in txs if t.get("booking_id")})
        bmap = {b["id"]: b async for b in db.bookings.find(
            {"id": {"$in": bids}}, {"_id": 0, "id": 1, "guest_name": 1, "booking_ref": 1})}
        for t in txs:
            bk = bmap.get(t.get("booking_id"), {})
            t["guest_name"] = bk.get("guest_name", "")
            t["booking_ref"] = bk.get("booking_ref", "")
        return txs

    @router.get("/pay-links/{booking_id}")
    async def list_links(booking_id: str,
                         current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        return await db.payment_transactions.find(
            {"booking_id": booking_id, "kind": "pay_by_link"}, {"_id": 0}
        ).sort("created_at", -1).to_list(20)

    @router.get("/pay-links/status/{session_id}")
    async def payment_status(session_id: str):
        rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not rec:
            raise HTTPException(404, "Transaction not found")
        if rec.get("payment_status") != "paid":
            try:
                s = stripe.checkout.Session.retrieve(session_id)
                if s.payment_status == "paid" or s.status == "complete":
                    await _mark_paid(db, session_id, {"stripe_payment_intent_id": s.payment_intent})
                    rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            except stripe.error.StripeError:
                pass
        return {"session_id": rec["session_id"], "status": rec["status"],
                "payment_status": rec["payment_status"]}

    @router.post("/stripe/webhook")
    async def stripe_webhook(request: Request):
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except Exception:
            raise HTTPException(400, "Invalid signature")
        obj, t = event["data"]["object"], event["type"]
        if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            await _mark_paid(db, obj["id"], {"stripe_payment_intent_id": obj.get("payment_intent")})
        elif t in ("checkout.session.async_payment_failed", "checkout.session.expired"):
            await db.payment_transactions.update_one(
                {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                {"$set": {"status": "failed" if "failed" in t else "expired",
                          "payment_status": "failed" if "failed" in t else "expired",
                          "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"status": "ok"}

    return router
