"""
Deposit Automation (Iter 158) — closes the loop between:
  - `deposit_policies` (evaluates what deposit is owed)
  - `card_vault` (tokenized Stripe PaymentMethod)
  - `folio_items` (payment ledger)

Workflow:
  1. Guest books → SetupIntent is confirmed via booking engine/reception → card
     saved to `card_vault_methods`.
  2. Periodically (or on-demand), this module scans unpaid/partially paid
     bookings, evaluates each one against active deposit_policies, and triggers
     an off-session Stripe charge via the saved PaymentMethod.
  3. Captured deposit is written to `folio_items` so `balance_due` drops.
  4. Failures are logged in `deposit_capture_log` for retry/escalation.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import os
import uuid
import logging
import httpx

logger = logging.getLogger(__name__)
STRIPE_API = "https://api.stripe.com/v1"


def _lead_days(check_in_str: str) -> int:
    try:
        ci = datetime.strptime(check_in_str, "%Y-%m-%d").date()
        return (ci - datetime.now(timezone.utc).date()).days
    except (ValueError, TypeError):
        return 0


def _match_policy(policy: Dict, channel: str, lead_days: int, rate_plan_id: str) -> bool:
    """Mirror of the logic in deposit_policies.py so we can evaluate locally."""
    trig = policy.get("trigger") or {}
    chans = trig.get("channels") or []
    if chans and "any" not in chans and channel and channel not in chans:
        return False
    ld = trig.get("lead_days_lte")
    if ld is not None and lead_days > int(ld):
        return False
    rps = trig.get("rate_plan_ids") or []
    if rps and rate_plan_id and rate_plan_id not in rps:
        return False
    return True


async def _stripe_post(path: str, data: dict, api_key: str):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{STRIPE_API}{path}", data=data, auth=(api_key, ""))
        return r.status_code, r.json() if r.text else {}


def create_deposit_automation_router(db, require_roles):
    router = APIRouter()

    @router.get("/deposit-automation/pending/{property_id}")
    async def pending(property_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Dry-run: list bookings that WOULD be captured if automation ran now.
        Each item shows matched policy, required deposit, already paid, and
        whether a vaulted card is available.
        """
        now = datetime.now(timezone.utc).date()
        today_str = now.strftime("%Y-%m-%d")

        pq = {} if property_id == "all" else {"property_id": property_id}
        # Active policies
        policies = await db.deposit_policies.find({**pq, "active": True}, {"_id": 0}).sort("priority", 1).to_list(200)
        if not policies:
            return {"pending": [], "total_owed": 0, "policies_active": 0, "as_of": today_str}

        # Future bookings (not yet departed, not cancelled)
        bookings = await db.bookings.find({
            **pq, "check_out": {"$gte": today_str},
            "status": {"$nin": ["cancelled", "no_show"]},
        }, {"_id": 0}).to_list(10000)

        pending_list = []
        total_owed = 0.0
        for b in bookings:
            # Payments already recorded
            paid_rows = await db.folio_items.find(
                {"booking_id": b["id"], "type": "payment"}, {"_id": 0, "amount": 1}
            ).to_list(50)
            paid = sum(float(p.get("amount", 0)) for p in paid_rows)

            # Match against policies
            matched = None
            for p in policies:
                if _match_policy(p, b.get("source", ""), _lead_days(b.get("check_in", "")), b.get("rate_plan_id", "")):
                    matched = p
                    break
            if not matched:
                continue

            total_price = float(b.get("total_price") or 0)
            if matched.get("amount_type") == "flat":
                deposit = float(matched.get("amount_value", 0))
            else:
                deposit = round(total_price * float(matched.get("amount_value", 0)) / 100, 2)

            to_capture = round(max(0.0, deposit - paid), 2)
            if to_capture <= 0:
                continue

            # Is there a saved card?
            card = None
            em = (b.get("guest_email") or "").strip().lower()
            if em:
                card = await db.card_vault_methods.find_one(
                    {"email": em}, {"_id": 0},
                    sort=[("created_at", -1)],
                )

            pending_list.append({
                "booking_id": b["id"],
                "booking_ref": b.get("booking_ref", ""),
                "guest_name": b.get("guest_name", ""),
                "guest_email": em,
                "check_in": b.get("check_in", ""),
                "total_price": round(total_price, 2),
                "already_paid": round(paid, 2),
                "deposit_required": round(deposit, 2),
                "to_capture": to_capture,
                "policy": {"id": matched["id"], "name": matched.get("name", "")},
                "card_on_file": bool(card),
                "card_brand": (card or {}).get("brand", ""),
                "card_last4": (card or {}).get("last4", ""),
                "payment_method_id": (card or {}).get("payment_method_id", ""),
            })
            total_owed += to_capture

        pending_list.sort(key=lambda r: r["check_in"])
        return {
            "pending": pending_list,
            "total_owed": round(total_owed, 2),
            "count": len(pending_list),
            "with_card": sum(1 for r in pending_list if r["card_on_file"]),
            "without_card": sum(1 for r in pending_list if not r["card_on_file"]),
            "policies_active": len(policies),
            "as_of": today_str,
        }

    @router.post("/deposit-automation/run/{property_id}")
    async def run(property_id: str, data: Dict,
                  current_user: dict = Depends(require_roles("admin", "manager"))):
        """Execute pending captures. Body:
          {dry_run: bool = false, only_booking_ids: [str] = [], max_charges: int = 50}
        Returns a per-booking result ledger. Only bookings with `card_on_file=true`
        are attempted — those without a saved card are skipped (logged as `no_card`).
        """
        stripe_key = os.environ.get("STRIPE_API_KEY")
        if not stripe_key:
            raise HTTPException(status_code=503, detail="Stripe not configured")

        dry_run = bool(data.get("dry_run", False))
        only_ids = set(data.get("only_booking_ids") or [])
        max_charges = int(data.get("max_charges", 50))

        # Reuse the pending-evaluation logic
        # (local call without auth re-check since we're already authorized)
        # ---- inline copy of pending() query ----
        now = datetime.now(timezone.utc).date()
        today_str = now.strftime("%Y-%m-%d")
        pq = {} if property_id == "all" else {"property_id": property_id}
        policies = await db.deposit_policies.find({**pq, "active": True}, {"_id": 0}).sort("priority", 1).to_list(200)
        if not policies:
            return {"ran": 0, "charged": 0, "failed": 0, "skipped": 0, "results": [], "dry_run": dry_run}

        bookings = await db.bookings.find({
            **pq, "check_out": {"$gte": today_str},
            "status": {"$nin": ["cancelled", "no_show"]},
        }, {"_id": 0}).to_list(10000)

        charged = 0
        failed = 0
        skipped = 0
        total_amount = 0.0
        results = []

        for b in bookings:
            if only_ids and b["id"] not in only_ids:
                continue
            if charged + failed >= max_charges:
                break

            paid_rows = await db.folio_items.find(
                {"booking_id": b["id"], "type": "payment"}, {"_id": 0, "amount": 1}
            ).to_list(50)
            paid = sum(float(p.get("amount", 0)) for p in paid_rows)

            matched = None
            for p in policies:
                if _match_policy(p, b.get("source", ""), _lead_days(b.get("check_in", "")), b.get("rate_plan_id", "")):
                    matched = p
                    break
            if not matched:
                continue

            total_price = float(b.get("total_price") or 0)
            if matched.get("amount_type") == "flat":
                deposit = float(matched.get("amount_value", 0))
            else:
                deposit = round(total_price * float(matched.get("amount_value", 0)) / 100, 2)
            to_capture = round(max(0.0, deposit - paid), 2)
            if to_capture <= 0:
                continue

            em = (b.get("guest_email") or "").strip().lower()
            card = None
            if em:
                card = await db.card_vault_methods.find_one(
                    {"email": em}, {"_id": 0}, sort=[("created_at", -1)],
                )

            if not card:
                skipped += 1
                results.append({"booking_id": b["id"], "guest_name": b.get("guest_name", ""),
                                "status": "no_card", "to_capture": to_capture, "reason": "No card on file"})
                await db.deposit_capture_log.insert_one({
                    "id": str(uuid.uuid4()),
                    "booking_id": b["id"], "amount": to_capture,
                    "status": "skipped_no_card",
                    "at": datetime.now(timezone.utc).isoformat(),
                    "by": current_user.get("name", ""),
                    "property_id": property_id,
                })
                continue

            if dry_run:
                results.append({"booking_id": b["id"], "guest_name": b.get("guest_name", ""),
                                "status": "would_charge", "to_capture": to_capture,
                                "card": f"{card.get('brand', '').upper()} •••• {card.get('last4', '')}"})
                continue

            # Execute off-session charge
            status_code, pi = await _stripe_post("/payment_intents", {
                "amount": int(round(to_capture * 100)),
                "currency": "gbp",
                "customer": card["stripe_customer_id"],
                "payment_method": card["payment_method_id"],
                "off_session": "true",
                "confirm": "true",
                "description": f"Auto-deposit · {matched.get('name', 'policy')} · booking {b.get('booking_ref', '')}",
                "metadata[booking_id]": b["id"],
                "metadata[policy_id]": matched["id"],
                "metadata[automated]": "true",
            }, stripe_key)

            log_id = str(uuid.uuid4())
            if status_code >= 400:
                failed += 1
                err = (pi.get("error") or {}).get("message", "Stripe error")
                results.append({"booking_id": b["id"], "guest_name": b.get("guest_name", ""),
                                "status": "failed", "to_capture": to_capture, "error": err})
                await db.deposit_capture_log.insert_one({
                    "id": log_id, "booking_id": b["id"], "amount": to_capture,
                    "status": "failed", "error": err,
                    "at": datetime.now(timezone.utc).isoformat(),
                    "by": current_user.get("name", ""),
                    "property_id": property_id,
                })
                continue

            # Success → write folio entry
            now_iso = datetime.now(timezone.utc).isoformat()
            folio_entry = {
                "id": str(uuid.uuid4()),
                "booking_id": b["id"],
                "type": "payment",
                "category": "card",
                "payment_method": "card",
                "description": f"Auto-deposit · {matched.get('name', 'policy')} · {card.get('brand', '').title()} •••• {card.get('last4', '')}",
                "quantity": 1,
                "unit_price": to_capture,
                "amount": to_capture,
                "currency": "GBP",
                "reference": pi.get("id", ""),
                "created_at": now_iso,
                "created_by": f"auto:{current_user.get('name', '')}",
                "vault_payment_method_id": card["payment_method_id"],
                "auto_deposit": True,
            }
            await db.folio_items.insert_one(folio_entry)

            charged += 1
            total_amount += to_capture
            results.append({"booking_id": b["id"], "guest_name": b.get("guest_name", ""),
                            "status": "charged", "amount": to_capture,
                            "payment_intent_id": pi.get("id", ""),
                            "card": f"{card.get('brand', '').upper()} •••• {card.get('last4', '')}"})
            await db.deposit_capture_log.insert_one({
                "id": log_id, "booking_id": b["id"], "amount": to_capture,
                "status": "charged", "payment_intent_id": pi.get("id", ""),
                "policy_id": matched["id"],
                "at": now_iso, "by": current_user.get("name", ""),
                "property_id": property_id,
            })

        return {
            "ran": charged + failed + skipped,
            "charged": charged,
            "failed": failed,
            "skipped": skipped,
            "total_amount": round(total_amount, 2),
            "dry_run": dry_run,
            "results": results,
        }

    @router.get("/deposit-automation/log/{property_id}")
    async def capture_log(property_id: str, limit: int = 100,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {} if property_id == "all" else {"property_id": property_id}
        rows = await db.deposit_capture_log.find(q, {"_id": 0}).sort("at", -1).to_list(int(limit))
        return rows

    return router
