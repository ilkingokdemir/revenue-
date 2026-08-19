"""Stripe Terminal — fiziksel/simüle kart cihazı (Mews Terminals paritesi). Test modunda simulated reader."""
import os
import uuid
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_terminal_router(db, require_roles):
    router = APIRouter(prefix="/terminal", tags=["terminal"])
    ROLES = ("admin", "manager", "receptionist")

    async def _location(pid: str) -> str:
        s = await db.terminal_settings.find_one({"property_id": pid}, {"_id": 0})
        if s and s.get("location_id"):
            return s["location_id"]
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "name": 1}) or {}
        loc = stripe.terminal.Location.create(
            display_name=(prop.get("name") or pid)[:40],
            address={"line1": "1 Hotel Street", "city": "London", "country": "GB", "postal_code": "EC1A1AA"})
        await db.terminal_settings.update_one({"property_id": pid},
                                              {"$set": {"location_id": loc.id, "created_at": now_iso()}}, upsert=True)
        return loc.id

    @router.get("/{pid}/readers")
    async def list_readers(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        try:
            loc = await _location(pid)
            readers = stripe.terminal.Reader.list(location=loc, limit=20)
            return {"readers": [{"id": r.id, "label": r.label, "status": r.status,
                                 "device_type": r.device_type} for r in readers.data],
                    "test_mode": os.environ.get("STRIPE_MODE", "test") == "test"}
        except Exception as e:
            raise HTTPException(502, f"Stripe hata: {str(e)[:150]}")

    @router.post("/{pid}/readers/register")
    async def register_reader(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        """Gerçek cihaz için cihaz üstündeki kodu girin; test modunda 'simulated-wpe' simüle cihaz oluşturur."""
        code = (data.get("registration_code") or "simulated-wpe").strip()
        label = (data.get("label") or "Resepsiyon Cihazı").strip()
        try:
            loc = await _location(pid)
            r = stripe.terminal.Reader.create(registration_code=code, label=label, location=loc)
            return {"ok": True, "reader": {"id": r.id, "label": r.label, "status": r.status},
                    "simulated": code == "simulated-wpe"}
        except Exception as e:
            raise HTTPException(400, f"Cihaz kaydedilemedi: {str(e)[:150]}")

    @router.post("/{pid}/charge")
    async def charge(pid: str, data: dict, _u: dict = Depends(require_roles(*ROLES))):
        amount = float(data.get("amount") or 0)
        reader_id = data.get("reader_id")
        if amount <= 0 or not reader_id:
            raise HTTPException(400, "amount ve reader_id zorunlu")
        try:
            pi = stripe.PaymentIntent.create(
                amount=int(round(amount * 100)), currency=data.get("currency", "gbp"),
                payment_method_types=["card_present"], capture_method="automatic",
                description=f"Terminal ödeme — {data.get('booking_id') or pid}")
            stripe.terminal.Reader.process_payment_intent(reader_id, payment_intent=pi.id)
            simulated = reader_id.startswith("tmr_") and os.environ.get("STRIPE_MODE", "test") == "test"
            if simulated:
                try:
                    stripe.terminal.Reader.TestHelpers.present_payment_method(reader_id)
                except Exception:
                    pass
            pi = stripe.PaymentIntent.retrieve(pi.id)
            doc = {"id": str(uuid.uuid4()), "property_id": pid, "booking_id": data.get("booking_id") or "",
                   "reader_id": reader_id, "payment_intent": pi.id, "amount": amount,
                   "currency": data.get("currency", "gbp"), "status": pi.status,
                   "created_by": _u.get("name", ""), "created_at": now_iso()}
            await db.terminal_payments.insert_one({**doc})
            doc.pop("_id", None)
            # Folyoya otomatik işle — resepsiyon çift kayıt yapmasın
            folio_posted = False
            bid = (data.get("booking_id") or "").strip()
            if bid and pi.status == "succeeded":
                booking = await db.bookings.find_one({"id": bid}, {"_id": 0, "currency": 1, "total_price": 1})
                if booking:
                    await db.folio_items.insert_one({
                        "id": str(uuid.uuid4()), "booking_id": bid, "type": "payment",
                        "category": "card", "payment_method": "card", "channel": "",
                        "description": f"Terminal ödemesi · {reader_id[-6:]}",
                        "quantity": 1, "unit_price": amount, "amount": amount,
                        "currency": booking.get("currency", "GBP"), "reference": pi.id,
                        "sub_folio_id": None, "created_at": now_iso(),
                        "created_by": _u.get("name", "terminal")})
                    items = await db.folio_items.find({"booking_id": bid}, {"_id": 0, "type": 1, "amount": 1}).to_list(500)
                    charges = sum(float(i.get("amount", 0)) for i in items if i.get("type") == "charge")
                    pays = sum(float(i.get("amount", 0)) for i in items if i.get("type") == "payment")
                    gross = charges if charges > 0 else float(booking.get("total_price") or 0)
                    status = "paid" if gross - pays <= 0 else ("partial" if pays > 0 else "pending")
                    await db.bookings.update_one({"id": bid}, {"$set": {"payment_status": status}})
                    folio_posted = True
            return {"ok": True, "payment": doc, "folio_posted": folio_posted}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Ödeme başlatılamadı: {str(e)[:180]}")

    @router.get("/{pid}/payments")
    async def payments(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.terminal_payments.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(30)
        return {"payments": rows}

    return router
