"""
Guest Self-Modify / Cancel Portal v2 — Public, token-based booking self-service.

Flow:
  Admin/auto: generate magic link token for a booking → emailed/SMS'd to guest.
  Guest: visits /portal/{token}, sees booking, can:
    - Modify dates (if allowed by policy)
    - Change guest count
    - Add preferences (early check-in, late check-out requests)
    - Cancel booking (if within cancel window)

Cancel policy:
  Flexible: full refund if > 48h before check_in
  Moderate:  full refund if > 5d, 50% if 2-5d, 0% if < 2d
  Strict:    50% if > 7d, else 0

Modification log kept in db.booking_modifications for audit.

Why this beats competitors:
  Cloudbeds/Mews: guests must contact reception to modify. Us: self-service portal.
  Opera: heavy integration required. Us: public link, zero install.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
import uuid
import logging

logger = logging.getLogger(__name__)


class TokenIssueReq(BaseModel):
    expiry_hours: int = 72
    policy: str = "flexible"   # flexible | moderate | strict


class ModifyReq(BaseModel):
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    adults: Optional[int] = None
    children: Optional[int] = None
    special_requests: Optional[str] = None


class CancelReq(BaseModel):
    reason: Optional[str] = None


POLICY_LABELS = {
    "flexible": "Esnek — varıştan 48 saat öncesine kadar tam iade",
    "moderate": "Orta — varıştan 5+ gün önce tam iade, 2-5 gün %50, <2 gün iade yok",
    "strict":   "Sıkı — varıştan 7+ gün önce %50 iade, aksi halde iade yok",
}


def _refund_percent(policy: str, days_to_arrival: int) -> int:
    if policy == "flexible":
        return 100 if days_to_arrival >= 2 else 0
    if policy == "moderate":
        if days_to_arrival >= 5: return 100
        if days_to_arrival >= 2: return 50
        return 0
    if policy == "strict":
        return 50 if days_to_arrival >= 7 else 0
    return 0


def create_guest_portal_v2_router(db, require_roles):
    router = APIRouter()

    # ---------------- ADMIN: issue token ----------------
    @router.post("/guest-portal-v2/token/{booking_id}")
    async def issue_token(booking_id: str, req: TokenIssueReq,
                          current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        if req.policy not in POLICY_LABELS:
            raise HTTPException(400, f"policy must be one of {list(POLICY_LABELS.keys())}")
        if req.expiry_hours < 1 or req.expiry_hours > 720:
            raise HTTPException(400, "expiry_hours must be 1..720")

        bk = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not bk:
            raise HTTPException(404, "Booking not found")

        token = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(hours=req.expiry_hours)
        doc = {
            "id": str(uuid.uuid4()),
            "token": token,
            "booking_id": booking_id,
            "booking_ref": bk.get("booking_ref"),
            "property_id": bk.get("property_id"),
            "policy": req.policy,
            "status": "issued",
            "issued_at": now.isoformat(),
            "expires_at": expiry.isoformat(),
            "issued_by": current_user.get("email"),
        }
        await db.guest_portal_v2_tokens.insert_one(doc)
        await db.bookings.update_one({"id": booking_id}, {"$set": {"guest_portal_v2_token": token}})
        return {
            "token": token,
            "expires_at": expiry.isoformat(),
            "link_path": f"/portal/{token}",
        }

    # ---------------- PUBLIC: verify token ----------------
    @router.get("/guest-portal-v2/verify/{token}")
    async def verify(token: str):
        tok = await db.guest_portal_v2_tokens.find_one({"token": token}, {"_id": 0})
        if not tok:
            raise HTTPException(404, "Geçersiz bağlantı")
        if datetime.now(timezone.utc) > datetime.fromisoformat(tok["expires_at"].replace("Z", "+00:00")):
            raise HTTPException(410, "Bağlantı süresi dolmuş")
        if tok.get("status") == "cancelled":
            raise HTTPException(410, "Bu rezervasyon iptal edildi")

        bk = await db.bookings.find_one({"id": tok["booking_id"]}, {"_id": 0})
        if not bk:
            raise HTTPException(404, "Booking not found")

        prop = await db.properties.find_one({"id": bk.get("property_id")}, {"_id": 0, "name": 1, "city": 1}) or {}
        branding = await db.brand_portal_branding.find_one({"property_id": bk.get("property_id")}, {"_id": 0, "logo_url": 1, "primary_color": 1}) or {}

        today = date.today()
        try:
            ci = date.fromisoformat((bk.get("check_in") or "")[:10])
            days_to_arrival = (ci - today).days
        except Exception:
            days_to_arrival = 0

        policy = tok.get("policy", "flexible")
        refund_pct = _refund_percent(policy, days_to_arrival)

        # Modifications history (public-safe)
        mods = await db.booking_modifications.find(
            {"booking_id": tok["booking_id"]}, {"_id": 0, "at": 1, "change": 1, "type": 1}
        ).sort("at", -1).limit(20).to_list(20)

        can_modify = bk.get("status") not in ("cancelled", "checked_out", "no_show") and days_to_arrival >= 1
        can_cancel = bk.get("status") not in ("cancelled", "checked_in", "checked_out", "no_show")

        return {
            "token": token,
            "status": tok["status"],
            "expires_at": tok["expires_at"],
            "policy": policy,
            "policy_label": POLICY_LABELS[policy],
            "days_to_arrival": days_to_arrival,
            "refund_percent_if_cancel": refund_pct,
            "can_modify": can_modify,
            "can_cancel": can_cancel,
            "booking": {
                "booking_ref": bk.get("booking_ref"),
                "guest_name": bk.get("guest_name"),
                "guest_email": bk.get("guest_email"),
                "check_in": bk.get("check_in"),
                "check_out": bk.get("check_out"),
                "adults": bk.get("adults") or bk.get("guests") or 1,
                "children": bk.get("children") or 0,
                "nights": bk.get("nights"),
                "total_price": bk.get("total_price"),
                "currency": bk.get("currency", "GBP"),
                "status": bk.get("status"),
                "room_type": bk.get("room_type"),
                "special_requests": bk.get("special_requests"),
            },
            "property": {"id": bk.get("property_id"), "name": prop.get("name") or "Hotel", "city": prop.get("city")},
            "branding": branding,
            "modifications": mods,
        }

    # ---------------- PUBLIC: modify booking ----------------
    @router.post("/guest-portal-v2/modify/{token}")
    async def modify(token: str, req: ModifyReq):
        tok = await db.guest_portal_v2_tokens.find_one({"token": token}, {"_id": 0})
        if not tok:
            raise HTTPException(404, "Invalid link")
        if datetime.now(timezone.utc) > datetime.fromisoformat(tok["expires_at"].replace("Z", "+00:00")):
            raise HTTPException(410, "Link expired")
        if tok.get("status") in ("cancelled",):
            raise HTTPException(400, "Booking cancelled, cannot modify")

        bk = await db.bookings.find_one({"id": tok["booking_id"]}, {"_id": 0})
        if not bk:
            raise HTTPException(404, "Booking not found")
        if bk.get("status") in ("cancelled", "checked_out", "no_show"):
            raise HTTPException(400, "Booking status does not allow modification")

        today = date.today()
        try:
            ci = date.fromisoformat((bk.get("check_in") or "")[:10])
        except ValueError:
            ci = None
        if ci and (ci - today).days < 1:
            raise HTTPException(400, "Modifications only allowed before arrival day")

        changes = {}
        if req.check_in and req.check_in != bk.get("check_in"):
            try:
                new_ci = date.fromisoformat(req.check_in)
                if new_ci < today:
                    raise HTTPException(400, "New check-in cannot be in the past")
            except ValueError:
                raise HTTPException(400, "check_in must be YYYY-MM-DD")
            changes["check_in"] = req.check_in
        if req.check_out and req.check_out != bk.get("check_out"):
            try:
                date.fromisoformat(req.check_out)
            except ValueError:
                raise HTTPException(400, "check_out must be YYYY-MM-DD")
            changes["check_out"] = req.check_out
        if req.adults is not None and req.adults != bk.get("adults"):
            if req.adults < 1 or req.adults > 10:
                raise HTTPException(400, "adults must be 1..10")
            changes["adults"] = req.adults
        if req.children is not None and req.children != bk.get("children"):
            if req.children < 0 or req.children > 10:
                raise HTTPException(400, "children must be 0..10")
            changes["children"] = req.children
        if req.special_requests is not None and req.special_requests != bk.get("special_requests"):
            changes["special_requests"] = req.special_requests[:500]

        if "check_in" in changes or "check_out" in changes:
            new_ci = changes.get("check_in") or bk.get("check_in")
            new_co = changes.get("check_out") or bk.get("check_out")
            nights = (date.fromisoformat(new_co) - date.fromisoformat(new_ci)).days
            if nights < 1:
                raise HTTPException(400, "check_out must be after check_in")
            changes["nights"] = nights

        if not changes:
            return {"updated": False, "note": "No changes"}

        now = datetime.now(timezone.utc).isoformat()
        changes["last_guest_modified_at"] = now
        await db.bookings.update_one({"id": tok["booking_id"]}, {"$set": changes})

        mod_doc = {
            "id": str(uuid.uuid4()),
            "booking_id": tok["booking_id"],
            "type": "guest_modify",
            "change": {k: v for k, v in changes.items() if k != "last_guest_modified_at"},
            "at": now,
            "source": "guest_portal_v2",
            "token": token,
        }
        await db.booking_modifications.insert_one(mod_doc)
        await db.guest_portal_v2_tokens.update_one(
            {"token": token},
            {"$set": {"last_action_at": now, "status": "modified"}}
        )
        return {"updated": True, "changes": mod_doc["change"]}

    # ---------------- PUBLIC: cancel booking ----------------
    @router.post("/guest-portal-v2/cancel/{token}")
    async def cancel(token: str, req: CancelReq):
        tok = await db.guest_portal_v2_tokens.find_one({"token": token}, {"_id": 0})
        if not tok:
            raise HTTPException(404, "Invalid link")
        if datetime.now(timezone.utc) > datetime.fromisoformat(tok["expires_at"].replace("Z", "+00:00")):
            raise HTTPException(410, "Link expired")
        if tok.get("status") == "cancelled":
            raise HTTPException(400, "Already cancelled")

        bk = await db.bookings.find_one({"id": tok["booking_id"]}, {"_id": 0})
        if not bk:
            raise HTTPException(404, "Booking not found")
        if bk.get("status") in ("cancelled", "checked_in", "checked_out", "no_show"):
            raise HTTPException(400, f"Cannot cancel booking with status {bk.get('status')}")

        today = date.today()
        try:
            ci = date.fromisoformat((bk.get("check_in") or "")[:10])
            days_to_arrival = (ci - today).days
        except Exception:
            days_to_arrival = 0
        policy = tok.get("policy", "flexible")
        refund_pct = _refund_percent(policy, days_to_arrival)
        total = float(bk.get("total_price") or 0)
        refund_amount = round(total * refund_pct / 100, 2)

        now = datetime.now(timezone.utc).isoformat()
        await db.bookings.update_one(
            {"id": tok["booking_id"]},
            {"$set": {
                "status": "cancelled",
                "cancelled_at": now,
                "cancellation_reason": (req.reason or "Guest self-cancel")[:500],
                "cancellation_refund_amount": refund_amount,
                "cancellation_refund_percent": refund_pct,
                "cancellation_source": "guest_portal_v2",
            }}
        )
        await db.guest_portal_v2_tokens.update_one(
            {"token": token},
            {"$set": {"status": "cancelled", "last_action_at": now}}
        )
        await db.booking_modifications.insert_one({
            "id": str(uuid.uuid4()),
            "booking_id": tok["booking_id"],
            "type": "guest_cancel",
            "change": {
                "status": "cancelled",
                "refund_percent": refund_pct,
                "refund_amount": refund_amount,
                "reason": req.reason,
            },
            "at": now,
            "source": "guest_portal_v2",
            "token": token,
        })
        return {
            "cancelled": True,
            "refund_percent": refund_pct,
            "refund_amount": refund_amount,
            "currency": bk.get("currency", "GBP"),
        }

    # ---------------- ADMIN: pipeline ----------------
    @router.get("/guest-portal-v2/pipeline/{property_id}")
    async def pipeline(property_id: str, days_ahead: int = 14,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        if days_ahead < 1 or days_ahead > 90:
            raise HTTPException(400, "days_ahead must be 1..90")
        today = date.today()
        horizon = (today + timedelta(days=days_ahead)).isoformat()
        bks = await db.bookings.find({
            "property_id": property_id,
            "check_in": {"$gte": today.isoformat(), "$lte": horizon},
        }, {"_id": 0}).to_list(500)

        rows = []
        counts = {"total": 0, "token_issued": 0, "modified": 0, "cancelled": 0}
        for b in bks:
            counts["total"] += 1
            tok = await db.guest_portal_v2_tokens.find_one({"booking_id": b["id"]}, {"_id": 0})
            issued = bool(tok)
            if issued:
                counts["token_issued"] += 1
                if tok.get("status") == "modified":
                    counts["modified"] += 1
                if tok.get("status") == "cancelled":
                    counts["cancelled"] += 1
            rows.append({
                "booking_id": b["id"],
                "booking_ref": b.get("booking_ref"),
                "guest_name": b.get("guest_name"),
                "check_in": b.get("check_in"),
                "check_out": b.get("check_out"),
                "status": b.get("status"),
                "token_issued": issued,
                "token_status": tok.get("status") if tok else None,
                "last_action_at": tok.get("last_action_at") if tok else None,
            })
        rows.sort(key=lambda x: x["check_in"])
        return {
            "property_id": property_id,
            "days_ahead": days_ahead,
            "rows": rows,
            "counts": counts,
        }

    return router
