"""
Gift Cards / Vouchers (P1)
Hotel-branded prepaid vouchers. Typical revenue use cases:
- Christmas/holiday gift purchases (spike in Q4)
- Apology / compensation issuance
- Referral programme rewards
Each card has: code, initial_amount, balance, expires_at, status (active/redeemed/expired/cancelled)
Redemption creates a folio payment line with method='gift_card'. Outstanding balance is a liability.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import secrets
import string
import logging

logger = logging.getLogger(__name__)


def _gen_code(prefix: str = "MHB") -> str:
    """Readable code like MHB-XJ4F-R9K2-8N7P."""
    alphabet = string.ascii_uppercase + string.digits
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "").replace("L", "")
    return f"{prefix}-{''.join(secrets.choice(alphabet) for _ in range(4))}-{''.join(secrets.choice(alphabet) for _ in range(4))}-{''.join(secrets.choice(alphabet) for _ in range(4))}"


def create_gift_cards_router(db, require_roles):
    router = APIRouter()

    @router.get("/gift-cards")
    async def list_cards(property_id: str = "", status: str = "",
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {}
        if property_id:
            q["property_id"] = property_id
        if status:
            q["status"] = status
        rows = await db.gift_cards.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return rows

    @router.get("/gift-cards/summary/{property_id}")
    async def summary(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Totals for the Gift Card panel header: sold, outstanding, redeemed."""
        pq = {} if property_id == "all" else {"property_id": property_id}
        cards = await db.gift_cards.find(pq, {"_id": 0}).to_list(5000)
        total_sold = sum(float(c.get("initial_amount", 0)) for c in cards)
        total_outstanding = sum(float(c.get("balance", 0)) for c in cards if c.get("status") == "active")
        total_redeemed = total_sold - total_outstanding - sum(
            float(c.get("initial_amount", 0)) for c in cards if c.get("status") in ("expired", "cancelled")
        )
        counts = {
            "active": sum(1 for c in cards if c.get("status") == "active"),
            "redeemed": sum(1 for c in cards if c.get("status") == "redeemed"),
            "expired": sum(1 for c in cards if c.get("status") == "expired"),
            "cancelled": sum(1 for c in cards if c.get("status") == "cancelled"),
        }
        return {
            "total_sold": round(total_sold, 2),
            "total_outstanding": round(total_outstanding, 2),
            "total_redeemed": round(max(0.0, total_redeemed), 2),
            "counts": counts,
            "count": len(cards),
        }

    @router.post("/gift-cards")
    async def issue_card(data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        """Issue a new gift card. Body: {property_id, amount, recipient_name, recipient_email, message, expires_days}"""
        amount = float(data.get("amount") or 0)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")
        prop_id = data.get("property_id") or ""
        expires_days = int(data.get("expires_days") or 365)
        now = datetime.now(timezone.utc)
        card = {
            "id": str(uuid.uuid4()),
            "code": _gen_code(),
            "property_id": prop_id,
            "initial_amount": round(amount, 2),
            "balance": round(amount, 2),
            "currency": data.get("currency", "GBP"),
            "recipient_name": (data.get("recipient_name") or "").strip(),
            "recipient_email": (data.get("recipient_email") or "").strip(),
            "purchaser_name": (data.get("purchaser_name") or "").strip(),
            "message": (data.get("message") or "").strip(),
            "status": "active",
            "expires_at": (now + timedelta(days=expires_days)).isoformat(),
            "created_at": now.isoformat(),
            "created_by": current_user.get("name", ""),
            "redemption_log": [],
        }
        await db.gift_cards.insert_one(card)
        card.pop("_id", None)
        return card

    @router.post("/gift-cards/{card_id}/redeem")
    async def redeem(card_id: str, data: Dict,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Redeem part/all of a card against a booking's folio.
        Body: {booking_id, amount, note}
        Creates a folio payment line with method='gift_card' and deducts from card balance.
        """
        card = await db.gift_cards.find_one({"id": card_id}, {"_id": 0})
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        if card.get("status") != "active":
            raise HTTPException(status_code=409, detail=f"Card is {card.get('status')}")
        amount = float(data.get("amount") or 0)
        if amount <= 0 or amount > float(card.get("balance", 0)):
            raise HTTPException(status_code=400, detail=f"Invalid amount (balance {card.get('balance')})")

        booking_id = data.get("booking_id")
        if not booking_id:
            raise HTTPException(status_code=400, detail="booking_id required")
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        # Create folio payment line
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "booking_id": booking_id,
            "type": "payment",
            "category": "gift_card",
            "payment_method": "gift_card",
            "description": f"Gift card {card.get('code')}",
            "quantity": 1,
            "unit_price": amount,
            "amount": amount,
            "currency": card.get("currency", "GBP"),
            "reference": card.get("code"),
            "created_at": now,
            "created_by": current_user.get("name", ""),
        }
        await db.folio_items.insert_one(item)

        new_balance = round(float(card.get("balance", 0)) - amount, 2)
        new_status = "redeemed" if new_balance <= 0.009 else "active"
        log_entry = {
            "at": now, "by": current_user.get("name", ""),
            "amount": amount, "booking_id": booking_id,
            "note": (data.get("note") or "").strip(),
        }
        await db.gift_cards.update_one(
            {"id": card_id},
            {"$set": {"balance": new_balance, "status": new_status},
             "$push": {"redemption_log": log_entry}}
        )
        return {"status": "ok", "redeemed": amount, "new_balance": new_balance, "card_status": new_status}

    @router.post("/gift-cards/{card_id}/cancel")
    async def cancel_card(card_id: str, data: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.gift_cards.update_one({"id": card_id},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat(),
                      "cancel_reason": (data.get("reason") or "").strip(),
                      "cancelled_by": current_user.get("name", "")}})
        return {"status": "cancelled"}

    @router.get("/gift-cards/lookup/{code}")
    async def lookup(code: str,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        """Look up a card by its code (for the reception check-lookup flow)."""
        card = await db.gift_cards.find_one({"code": code.upper().strip()}, {"_id": 0})
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
        return card

    return router
