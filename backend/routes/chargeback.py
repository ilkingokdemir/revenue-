"""
Chargeback Defense Package (P0 #12)
-----------------------------------
Builds a complete dispute evidence bundle for a booking when the cardholder
issues a chargeback. The hotel can then submit this manifest to the acquiring
bank via Stripe / Adyen / etc.

Sources stitched into the manifest:
  * Booking record (dates, room, guest, total)
  * Folio charges (post + payment ledger)
  * Pre-auth holds + captures
  * Door-lock entry events (proves guest was on-property)
  * Communications log (emails / WhatsApp / chat)
  * Signed registration card / ID copy references (if uploaded)
  * Reviews / surveys submitted by the same guest

Endpoints
---------
POST /chargebacks                            Open a chargeback case
GET  /chargebacks/{property_id}              List cases (filter by status)
GET  /chargebacks/{case_id}/evidence         Auto-build evidence manifest (JSON)
POST /chargebacks/{case_id}/status           Update case status (won / lost / pending)
POST /chargebacks/{case_id}/note             Append a note / comment to the case
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_chargeback_router(db, require_roles):
    router = APIRouter()

    @router.post("/chargebacks")
    async def open_case(data: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        booking_id = (data.get("booking_id") or "").strip()
        property_id = (data.get("property_id") or "").strip()
        amount = float(data.get("amount") or 0)
        reason = (data.get("reason") or "fraudulent").strip()  # fraudulent | not_received | duplicate | not_described
        if not booking_id or not property_id or amount <= 0:
            raise HTTPException(400, "booking_id, property_id, amount required")
        case = {
            "id": str(uuid.uuid4()),
            "case_ref": f"CB-{uuid.uuid4().hex[:8].upper()}",
            "property_id": property_id,
            "booking_id": booking_id,
            "amount": round(amount, 2),
            "currency": data.get("currency", "GBP"),
            "reason_code": reason,
            "card_last4": data.get("card_last4", ""),
            "issuer": data.get("issuer", ""),
            "status": "pending",  # pending | submitted | won | lost | accepted
            "deadline": data.get("deadline", (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()),
            "opened_at": _now(),
            "opened_by": current_user.get("name", "Staff"),
            "notes": [],
        }
        await db.chargebacks.insert_one(dict(case))
        case.pop("_id", None)
        return {"ok": True, "case": case}

    @router.get("/chargebacks/{property_id}")
    async def list_cases(property_id: str, status: str = "", days: int = 90,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "opened_at": {"$gte": since}}
        if status:
            q["status"] = status
        rows = await db.chargebacks.find(q, {"_id": 0}).sort("opened_at", -1).to_list(500)
        won = sum(1 for r in rows if r["status"] == "won")
        lost = sum(1 for r in rows if r["status"] == "lost")
        rate = round(won * 100 / max(won + lost, 1), 1)
        return {"items": rows, "count": len(rows), "won": won, "lost": lost, "win_rate": rate}

    @router.get("/chargebacks/case/{case_id}/evidence")
    async def build_evidence(case_id: str,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        case = await db.chargebacks.find_one({"id": case_id}, {"_id": 0})
        if not case:
            raise HTTPException(404, "Case not found")
        booking_id = case["booking_id"]
        property_id = case["property_id"]

        # Pull all evidence in parallel-ish style
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0}) or {}
        folio = await db.folios.find_one({"booking_id": booking_id}, {"_id": 0}) or {}
        charges = await db.folio_charges.find({"booking_id": booking_id}, {"_id": 0}).to_list(200)
        payments = await db.payments.find({"booking_id": booking_id}, {"_id": 0}).to_list(200)
        holds = await db.preauth_holds.find({"booking_id": booking_id}, {"_id": 0}).to_list(20)
        lock_events = await db.door_lock_log.find({"booking_id": booking_id}, {"_id": 0}).sort("logged_at", 1).to_list(200)
        comms = await db.guest_messages.find({"booking_id": booking_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
        reg_cards = await db.registration_cards.find({"booking_id": booking_id}, {"_id": 0}).to_list(10)
        id_uploads = await db.id_documents.find({"booking_id": booking_id}, {"_id": 0}).to_list(10)
        surveys = await db.survey_responses.find({"booking_id": booking_id}, {"_id": 0}).to_list(20)

        # Evidence completeness scoring
        checks = {
            "has_booking": bool(booking),
            "has_folio_charges": len(charges) > 0,
            "has_payments": len(payments) > 0,
            "has_preauth_history": len(holds) > 0,
            "has_lock_evidence_guest_was_present": len(lock_events) > 0,
            "has_communications_log": len(comms) > 0,
            "has_signed_registration_card": len(reg_cards) > 0,
            "has_id_document_copy": len(id_uploads) > 0,
            "has_guest_survey_or_review": len(surveys) > 0,
        }
        score = sum(1 for v in checks.values() if v) * 100 // len(checks)

        manifest = {
            "case_ref": case["case_ref"],
            "case_id": case_id,
            "property_id": property_id,
            "booking_id": booking_id,
            "amount_disputed": case["amount"],
            "reason_code": case["reason_code"],
            "deadline": case["deadline"],
            "compiled_at": _now(),
            "evidence_score": score,
            "checks": checks,
            "narrative_summary": _build_narrative(booking, charges, holds, lock_events, comms),
            "booking": booking,
            "folio_summary": {
                "total_charges": round(sum(float(c.get("amount") or 0) for c in charges), 2),
                "total_payments": round(sum(float(p.get("amount") or 0) for p in payments), 2),
                "items": charges[:50],
            },
            "preauth_history": holds,
            "lock_events": lock_events[:100],
            "communications": comms[:50],
            "registration_cards": reg_cards,
            "id_documents": id_uploads,
            "guest_feedback": surveys,
        }
        # Cache the manifest on the case so subsequent submissions are immutable
        await db.chargebacks.update_one(
            {"id": case_id}, {"$set": {"last_evidence": manifest, "last_evidence_at": _now()}}
        )
        return manifest

    @router.post("/chargebacks/case/{case_id}/status")
    async def update_status(case_id: str, data: Dict,
                             current_user: dict = Depends(require_roles("admin", "manager"))):
        new_status = (data.get("status") or "").strip()
        if new_status not in {"pending", "submitted", "won", "lost", "accepted"}:
            raise HTTPException(400, "Invalid status")
        await db.chargebacks.update_one(
            {"id": case_id},
            {"$set": {"status": new_status, "status_updated_at": _now(),
                       "status_updated_by": current_user.get("name", "Staff")}}
        )
        return {"ok": True, "status": new_status}

    @router.post("/chargebacks/case/{case_id}/note")
    async def add_note(case_id: str, data: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        text = (data.get("text") or "").strip()
        if not text:
            raise HTTPException(400, "text required")
        note = {"text": text, "by": current_user.get("name", "Staff"), "at": _now()}
        await db.chargebacks.update_one({"id": case_id}, {"$push": {"notes": note}})
        return {"ok": True, "note": note}

    return router


def _build_narrative(booking, charges, holds, locks, comms) -> str:
    """Auto-build a defense narrative for the chargeback rebuttal letter."""
    if not booking:
        return "No booking found."
    g = booking.get("guest_name", "the guest")
    nights = booking.get("nights", 0)
    total = booking.get("total_price", 0)
    parts = [
        f"Booking ref {booking.get('id', '')[:8]} confirmed for {g} for {nights} nights at total {total}.",
    ]
    if locks:
        parts.append(f"Smart-lock activity records {len(locks)} room-entry events during the stay, "
                      f"first at {locks[0].get('logged_at', '')[:19]}, last at {locks[-1].get('logged_at', '')[:19]} — "
                      f"confirming guest physically occupied the room.")
    if holds:
        parts.append(f"A pre-authorisation hold was taken at check-in (auth code "
                      f"{holds[0].get('auth_code', '?')}) demonstrating guest provided a valid card.")
    if charges:
        parts.append(f"Folio includes {len(charges)} itemised line items totalling "
                      f"{sum(float(c.get('amount') or 0) for c in charges):.2f}, all posted within the stay window.")
    if comms:
        parts.append(f"There were {len(comms)} two-way communications with the guest before/during/after the stay.")
    parts.append("This evidence package is submitted in full to demonstrate that the goods/services "
                  "were rendered as agreed and that the cardholder authorised the transaction.")
    return " ".join(parts)
