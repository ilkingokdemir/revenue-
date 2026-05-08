"""
GDPR Compliance — Data Portability (Art. 20) + Right to Erasure (Art. 17)
-------------------------------------------------------------------------
For any guest identified by email, aggregate all personally-identifiable data
held across collections and optionally anonymise it.

Endpoints (/api/gdpr/*):
- GET  /search?q=                      → find guests by email/name (admin only)
- POST /export                         → full JSON export of a guest's data
- POST /erasure                        → pseudonymise personal fields (immutable audit trail kept)
- GET  /log                            → history of past export/erasure actions
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
import uuid
import re

from auth import require_perm


class GdprActionIn(BaseModel):
    email: str
    reason: Optional[str] = ""


# Collections that may hold PII keyed by guest_email (and other PII fields)
PII_COLLECTIONS = [
    "bookings", "guest_profiles", "reviews", "messaging_threads", "unified_messages",
    "guest_payments", "loyalty_members", "folio_charges", "surveys_responses",
    "legal_consents", "registration_cards", "city_ledger_invoices", "lost_found",
]

ANON_VALUE = "[REDACTED]"


def _normalise(email: str) -> str:
    return (email or "").strip().lower()


def create_gdpr_router(db):
    router = APIRouter(prefix="/gdpr")

    @router.get("/search")
    async def search(
        q: str = "",
        current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any")),
    ):
        if not q or len(q) < 2:
            return []
        rx = re.compile(re.escape(q), re.IGNORECASE)
        # Pull unique identities from bookings + guest_profiles
        seen = {}
        bcur = db.bookings.find(
            {"$or": [{"guest_email": {"$regex": rx}}, {"guest_name": {"$regex": rx}}]},
            {"_id": 0, "guest_name": 1, "guest_email": 1, "guest_phone": 1}
        ).limit(50)
        async for b in bcur:
            email = _normalise(b.get("guest_email", ""))
            if email and email not in seen:
                seen[email] = {
                    "email": email,
                    "name": b.get("guest_name", ""),
                    "phone": b.get("guest_phone", ""),
                    "source": "bookings",
                }
        pcur = db.guest_profiles.find(
            {"$or": [{"email": {"$regex": rx}}, {"name": {"$regex": rx}}]},
            {"_id": 0, "name": 1, "email": 1, "phone": 1}
        ).limit(50)
        async for p in pcur:
            email = _normalise(p.get("email", ""))
            if email and email not in seen:
                seen[email] = {
                    "email": email,
                    "name": p.get("name", ""),
                    "phone": p.get("phone", ""),
                    "source": "guest_profiles",
                }
        return list(seen.values())

    @router.post("/export")
    async def export_data(
        data: GdprActionIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """Art. 20 — Data Portability. Returns a full JSON bundle across every
        collection that mentions the guest's email."""
        email = _normalise(data.email)
        if not email:
            raise HTTPException(400, "Email required")
        bundle = {"guest_email": email, "generated_at": datetime.now(timezone.utc).isoformat(),
                  "collections": {}}
        for coll in PII_COLLECTIONS:
            try:
                # Probe several common email field names
                q = {"$or": [
                    {"guest_email": email}, {"email": email}, {"to": email},
                    {"from_addr": email}, {"to_addr": email},
                ]}
                rows = await db[coll].find(q, {"_id": 0}).to_list(5000)
                if rows:
                    bundle["collections"][coll] = rows
            except Exception:
                continue

        # Audit entry
        await db.gdpr_log.insert_one({
            "id": str(uuid.uuid4()),
            "action": "export",
            "email": email,
            "reason": data.reason or "",
            "rows_exported": sum(len(v) for v in bundle["collections"].values()),
            "performed_by": current_user.get("email", ""),
            "performed_at": datetime.now(timezone.utc).isoformat(),
        })
        return bundle

    @router.post("/erasure")
    async def erase(
        data: GdprActionIn,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        """Art. 17 — Right to Erasure. Pseudonymises all personal fields we know of
        while keeping primary keys & financial totals intact (for legal retention)."""
        email = _normalise(data.email)
        if not email:
            raise HTTPException(400, "Email required")

        ops = {
            "bookings": [
                ({"guest_email": email},
                 {"guest_email": ANON_VALUE, "guest_name": ANON_VALUE,
                  "guest_phone": ANON_VALUE, "special_requests": ANON_VALUE}),
            ],
            "guest_profiles": [
                ({"email": email},
                 {"email": ANON_VALUE, "name": ANON_VALUE, "phone": ANON_VALUE,
                  "notes": ANON_VALUE, "passport": ANON_VALUE, "address": ANON_VALUE}),
            ],
            "reviews": [
                ({"guest_email": email},
                 {"guest_email": ANON_VALUE, "guest_name": ANON_VALUE}),
            ],
            "messaging_threads": [
                ({"guest_email": email},
                 {"guest_email": ANON_VALUE, "guest_name": ANON_VALUE}),
            ],
            "unified_messages": [
                ({"$or": [{"from_addr": email}, {"to_addr": email}]},
                 {"from_addr": ANON_VALUE, "to_addr": ANON_VALUE,
                  "guest_name": ANON_VALUE, "body": ANON_VALUE}),
            ],
            "loyalty_members": [
                ({"email": email},
                 {"email": ANON_VALUE, "name": ANON_VALUE, "phone": ANON_VALUE}),
            ],
            "legal_consents": [
                ({"email": email},
                 {"email": ANON_VALUE, "signature": ANON_VALUE, "ip": ANON_VALUE}),
            ],
            "registration_cards": [
                ({"guest_email": email},
                 {"guest_email": ANON_VALUE, "guest_name": ANON_VALUE,
                  "passport": ANON_VALUE, "address": ANON_VALUE,
                  "emergency_contact": ANON_VALUE, "signature_base64": ANON_VALUE}),
            ],
            "surveys_responses": [
                ({"email": email}, {"email": ANON_VALUE, "name": ANON_VALUE}),
            ],
            "lost_found": [
                ({"guest_email": email},
                 {"guest_email": ANON_VALUE, "guest_name": ANON_VALUE}),
            ],
        }

        affected = {}
        for coll, pairs in ops.items():
            total = 0
            for query, update in pairs:
                try:
                    r = await db[coll].update_many(query, {"$set": update})
                    total += r.modified_count
                except Exception:
                    continue
            if total:
                affected[coll] = total

        await db.gdpr_log.insert_one({
            "id": str(uuid.uuid4()),
            "action": "erasure",
            "email": email,
            "reason": data.reason or "",
            "affected": affected,
            "performed_by": current_user.get("email", ""),
            "performed_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, "email": email, "affected": affected,
                "note": "Personal fields redacted; primary keys and financial totals retained for legal compliance"}

    @router.get("/log")
    async def audit_log(
        limit: int = 100,
        current_user: dict = Depends(require_perm("edit_bookings")),
    ):
        rows = await db.gdpr_log.find({}, {"_id": 0}).sort("performed_at", -1).to_list(int(limit))
        return rows

    return router
