"""
PCI Card-on-File Vault (Iter 157) — tokenized 1-click charging via Stripe.

Flow:
  1. POST /card-vault/setup-intent  →  creates/reuses a Stripe Customer for the
     guest and generates a SetupIntent. Returns client_secret for frontend
     Stripe Elements to confirm (collects card details off our servers — we
     never see raw PAN; PCI SAQ-A scope).
  2. POST /card-vault/save-method  →  after frontend confirms, backend records
     the saved payment_method reference in our DB (no card details stored).
  3. GET  /card-vault/guest/{email}  →  list saved cards for a guest.
  4. POST /card-vault/charge  →  off-session charge using a saved method ID.
  5. DELETE /card-vault/methods/{id}  →  detach from Stripe + delete our record.

All API keys come from STRIPE_API_KEY env var (already in backend/.env).
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict
import os
import uuid
import logging
import httpx

logger = logging.getLogger(__name__)

STRIPE_API = "https://api.stripe.com/v1"


async def _stripe_post(path: str, data: dict, api_key: str):
    """Stripe wants form-encoded POST bodies."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{STRIPE_API}{path}", data=data,
                         auth=(api_key, ""),
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
        if r.status_code >= 400:
            logger.warning(f"Stripe error on {path}: {r.status_code} {r.text[:200]}")
            raise HTTPException(status_code=400, detail=r.json().get("error", {}).get("message", "Stripe error"))
        return r.json()


async def _stripe_get(path: str, api_key: str):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{STRIPE_API}{path}", auth=(api_key, ""))
        if r.status_code >= 400:
            raise HTTPException(status_code=400, detail=r.json().get("error", {}).get("message", "Stripe error"))
        return r.json()


async def _stripe_delete(path: str, api_key: str):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.delete(f"{STRIPE_API}{path}", auth=(api_key, ""))
        return r.json() if r.text else {}


def create_card_vault_router(db, require_roles):
    router = APIRouter()

    def _key():
        k = os.environ.get("STRIPE_API_KEY")
        if not k:
            raise HTTPException(status_code=503, detail="Stripe not configured")
        return k

    async def _ensure_customer(email: str, name: str = "") -> str:
        """Get or create a Stripe customer for this email. Cached in our DB."""
        existing = await db.card_vault_customers.find_one({"email": email}, {"_id": 0})
        if existing and existing.get("stripe_customer_id"):
            return existing["stripe_customer_id"]

        data = {"email": email}
        if name:
            data["name"] = name
        cust = await _stripe_post("/customers", data, _key())
        cust_id = cust["id"]
        await db.card_vault_customers.update_one(
            {"email": email},
            {"$set": {
                "email": email, "stripe_customer_id": cust_id, "name": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        return cust_id

    @router.post("/card-vault/setup-intent")
    async def setup_intent(data: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Body: {email, name?, booking_id?}. Returns client_secret for Stripe.js Payment Element."""
        email = (data.get("email") or "").strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="email required")
        cust_id = await _ensure_customer(email, data.get("name", ""))
        si = await _stripe_post("/setup_intents", {
            "customer": cust_id,
            "payment_method_types[]": "card",
            "usage": "off_session",
            "metadata[booking_id]": data.get("booking_id", ""),
            "metadata[issued_by]": current_user.get("name", ""),
        }, _key())
        return {
            "client_secret": si["client_secret"],
            "setup_intent_id": si["id"],
            "customer_id": cust_id,
            "publishable_key_hint": "pk_test_... (set STRIPE_PUBLISHABLE_KEY for frontend)",
        }

    @router.post("/card-vault/save-method")
    async def save_method(data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """After Stripe.js confirms setup, call this to record the saved PM.
        Body: {email, payment_method_id, booking_id?}
        """
        email = (data.get("email") or "").strip().lower()
        pm_id = (data.get("payment_method_id") or "").strip()
        if not email or not pm_id:
            raise HTTPException(status_code=400, detail="email + payment_method_id required")
        pm = await _stripe_get(f"/payment_methods/{pm_id}", _key())
        card = pm.get("card", {})
        record = {
            "id": str(uuid.uuid4()),
            "email": email,
            "stripe_customer_id": pm.get("customer"),
            "payment_method_id": pm_id,
            "brand": card.get("brand", ""),
            "last4": card.get("last4", ""),
            "exp_month": card.get("exp_month"),
            "exp_year": card.get("exp_year"),
            "booking_id": data.get("booking_id", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.card_vault_methods.insert_one(record)
        record.pop("_id", None)
        return record

    @router.get("/card-vault/guest/{email}")
    async def list_for_guest(email: str,
                             current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.card_vault_methods.find({"email": email.lower()}, {"_id": 0})\
            .sort("created_at", -1).to_list(20)
        return rows

    @router.post("/card-vault/charge")
    async def charge(data: Dict,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        """Off-session charge using a saved PaymentMethod. Body:
        {payment_method_id, amount_gbp, booking_id?, description?}
        On success, writes a folio_items payment entry so the booking balance reduces.
        """
        pm_id = (data.get("payment_method_id") or "").strip()
        amt = float(data.get("amount_gbp") or 0)
        if amt <= 0 or not pm_id:
            raise HTTPException(status_code=400, detail="payment_method_id + amount_gbp required")

        pm_row = await db.card_vault_methods.find_one({"payment_method_id": pm_id}, {"_id": 0})
        if not pm_row:
            raise HTTPException(status_code=404, detail="Payment method not on file")

        pi = await _stripe_post("/payment_intents", {
            "amount": int(round(amt * 100)),
            "currency": "gbp",
            "customer": pm_row["stripe_customer_id"],
            "payment_method": pm_id,
            "off_session": "true",
            "confirm": "true",
            "description": data.get("description", "Card-on-file charge"),
            "metadata[booking_id]": data.get("booking_id", ""),
            "metadata[charged_by]": current_user.get("name", ""),
        }, _key())

        # Write folio payment line so booking balance updates in real time
        booking_id = data.get("booking_id")
        folio_entry = None
        if booking_id:
            folio_entry = {
                "id": str(uuid.uuid4()),
                "booking_id": booking_id,
                "type": "payment",
                "category": "card",
                "payment_method": "card",
                "description": data.get("description") or f"Card-on-file · {pm_row.get('brand', '').title()} •••• {pm_row.get('last4', '')}",
                "quantity": 1,
                "unit_price": amt,
                "amount": amt,
                "currency": "GBP",
                "reference": pi.get("id", ""),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user.get("name", ""),
                "vault_payment_method_id": pm_id,
            }
            await db.folio_items.insert_one(folio_entry)
            folio_entry.pop("_id", None)

        return {
            "status": pi.get("status"),
            "payment_intent_id": pi.get("id"),
            "amount_charged_gbp": amt,
            "folio_entry": folio_entry,
        }

    @router.delete("/card-vault/methods/{record_id}")
    async def delete_method(record_id: str,
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        row = await db.card_vault_methods.find_one({"id": record_id}, {"_id": 0})
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        try:
            await _stripe_post(f"/payment_methods/{row['payment_method_id']}/detach", {}, _key())
        except HTTPException:
            pass  # already detached upstream — proceed to local delete
        await db.card_vault_methods.delete_one({"id": record_id})
        return {"status": "deleted"}

    @router.get("/card-vault/config")
    async def config(current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Expose the publishable key (if set) so the frontend can init Stripe.js."""
        return {
            "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY", ""),
            "mode": "test" if (os.environ.get("STRIPE_API_KEY", "").startswith("sk_test") or os.environ.get("STRIPE_API_KEY", "") == "sk_test_emergent") else "live",
        }

    return router
