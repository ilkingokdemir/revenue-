"""
Digital Tipping — Guest-to-staff tipping via Stripe Checkout.

Flow:
1. Guest scans QR in lobby/room → lands on /tip/{property_id} or /tip/{property_id}/{staff_id}.
2. Frontend calls POST /api/tipping/session (public) → gets Stripe Checkout URL.
3. Guest pays on Stripe → redirected to /tip/success.
4. Frontend polls GET /api/tipping/status/{session_id} until paid.
5. Webhook confirms + writes to db.tips collection.
6. Admin sees leaderboard at /api/tipping/leaderboard/{property_id}.

Stripe Tips vs competitors:
- Opera/Cloudbeds: requires external tipping vendor (Grazzy/eTip ~$2/stay+fees).
- Us: native, 0 integration cost, zero vendor lock-in.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
import uuid
import os
import logging

from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

logger = logging.getLogger(__name__)


ALLOWED_ROLES = {"receptionist", "housekeeping", "concierge", "bellhop", "restaurant", "bar", "spa", "other"}


class TipSessionReq(BaseModel):
    property_id: str
    amount: float                     # in currency units (e.g. 5.00 GBP)
    currency: str = "gbp"
    staff_id: Optional[str] = None    # if tipping a specific staff member
    staff_role: Optional[str] = "other"
    guest_name: Optional[str] = None
    message: Optional[str] = None
    origin_url: str                   # front-end origin, e.g. https://hotel.com — used to build success/cancel


def create_tipping_router(db, require_roles, stripe_api_key: str):
    router = APIRouter()

    # ---------------- PUBLIC: create session ----------------
    @router.post("/tipping/session")
    async def create_session(req: TipSessionReq, request: Request):
        # Validate
        if req.amount < 0.5:
            raise HTTPException(400, "Minimum tip amount is 0.50")
        if req.amount > 500:
            raise HTTPException(400, "Maximum tip amount is 500")
        if req.staff_role and req.staff_role not in ALLOWED_ROLES:
            raise HTTPException(400, f"Invalid staff_role. Allowed: {sorted(ALLOWED_ROLES)}")
        currency = (req.currency or "gbp").lower()
        if currency not in ("gbp", "eur", "usd", "try"):
            raise HTTPException(400, "Unsupported currency")

        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        sc = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)

        # If staff_id provided, validate
        staff_name = None
        if req.staff_id:
            staff = await db.users.find_one({"id": req.staff_id}, {"_id": 0, "email": 1, "full_name": 1, "role": 1})
            if not staff:
                raise HTTPException(404, "Staff not found")
            staff_name = staff.get("full_name") or staff.get("email")

        origin = req.origin_url.rstrip("/")
        success_url = f"{origin}/tip/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{origin}/tip/cancel"

        ckreq = CheckoutSessionRequest(
            amount=float(req.amount),
            currency=currency,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "tip",
                "property_id": req.property_id,
                "staff_id": req.staff_id or "",
                "staff_role": req.staff_role or "other",
                "guest_name": req.guest_name or "",
                "message": (req.message or "")[:200],
            },
        )
        session = await sc.create_checkout_session(ckreq)

        # Record pending tip
        tip = {
            "id": str(uuid.uuid4()),
            "session_id": session.session_id,
            "property_id": req.property_id,
            "staff_id": req.staff_id,
            "staff_name": staff_name,
            "staff_role": req.staff_role,
            "amount": float(req.amount),
            "currency": currency,
            "status": "pending",
            "guest_name": req.guest_name,
            "message": req.message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.tips.insert_one(tip)
        return {
            "session_id": session.session_id,
            "checkout_url": session.url,
            "tip_id": tip["id"],
        }

    # ---------------- PUBLIC: poll status ----------------
    @router.get("/tipping/status/{session_id}")
    async def status(session_id: str, request: Request):
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        sc = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
        try:
            s = await sc.get_checkout_status(session_id)
        except Exception as e:
            logger.warning(f"Stripe status poll failed: {e}")
            s = None

        tip = await db.tips.find_one({"session_id": session_id}, {"_id": 0})
        if not tip:
            raise HTTPException(404, "Tip session not found")

        # Sync status from Stripe
        if s and s.payment_status == "paid" and tip.get("status") != "paid":
            await db.tips.update_one(
                {"session_id": session_id},
                {"$set": {"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}}
            )
            tip["status"] = "paid"

        return {
            "session_id": session_id,
            "status": tip["status"],
            "amount": tip["amount"],
            "currency": tip["currency"],
            "staff_name": tip.get("staff_name"),
            "stripe_status": s.payment_status if s else None,
        }

    # ---------------- PUBLIC: landing info (property/staff cards) ----------------
    @router.get("/tipping/landing/{property_id}")
    async def landing(property_id: str, staff_id: Optional[str] = None):
        """Info needed to render public tip page. No auth."""
        prop = await db.properties.find_one({"id": property_id}, {"_id": 0, "name": 1, "city": 1, "country": 1}) or {}
        # Also consult brand_portal/public-branding if available
        branding = await db.brand_portal_branding.find_one({"property_id": property_id}, {"_id": 0, "logo_url": 1, "primary_color": 1, "secondary_color": 1}) or {}
        staff = None
        if staff_id:
            u = await db.users.find_one({"id": staff_id}, {"_id": 0, "email": 1, "full_name": 1, "role": 1, "avatar_url": 1})
            if u:
                staff = {"id": staff_id, "name": u.get("full_name") or u.get("email"), "role": u.get("role"), "avatar_url": u.get("avatar_url")}
        # Suggested amounts
        return {
            "property": {"id": property_id, "name": prop.get("name") or "Hotel", "city": prop.get("city"), "country": prop.get("country")},
            "branding": branding,
            "staff": staff,
            "suggested_amounts": [2, 5, 10, 20, 50],
            "currency": "gbp",
        }

    # ---------------- ADMIN: leaderboard ----------------
    @router.get("/tipping/leaderboard/{property_id}")
    async def leaderboard(property_id: str, days: int = 30,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        if days < 1 or days > 365:
            raise HTTPException(400, "days must be 1..365")
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        tips = await db.tips.find({
            "property_id": property_id,
            "status": "paid",
            "created_at": {"$gte": since},
        }, {"_id": 0}).to_list(2000)

        total_amount = sum(t["amount"] for t in tips)
        total_count = len(tips)
        by_staff = {}
        by_role = {}
        for t in tips:
            sid = t.get("staff_id") or "unassigned"
            sname = t.get("staff_name") or ("Takım geneli" if sid == "unassigned" else sid[:8])
            by_staff.setdefault(sid, {"staff_id": sid, "staff_name": sname, "total": 0, "count": 0, "currency": t["currency"]})
            by_staff[sid]["total"] += t["amount"]
            by_staff[sid]["count"] += 1
            role = t.get("staff_role") or "other"
            by_role.setdefault(role, {"role": role, "total": 0, "count": 0})
            by_role[role]["total"] += t["amount"]
            by_role[role]["count"] += 1

        leaderboard_rows = sorted(by_staff.values(), key=lambda x: x["total"], reverse=True)
        for r in leaderboard_rows:
            r["total"] = round(r["total"], 2)
        role_rows = sorted(by_role.values(), key=lambda x: x["total"], reverse=True)
        for r in role_rows:
            r["total"] = round(r["total"], 2)

        # Recent messages (anonymized if no guest_name)
        messages = [
            {
                "at": t.get("paid_at") or t.get("created_at"),
                "amount": t["amount"],
                "currency": t["currency"],
                "guest_name": t.get("guest_name") or "Anonymous",
                "message": t.get("message") or "",
                "staff_name": t.get("staff_name"),
                "staff_role": t.get("staff_role"),
            }
            for t in tips if t.get("message")
        ][-20:]
        messages.reverse()

        return {
            "property_id": property_id,
            "days": days,
            "total_amount": round(total_amount, 2),
            "total_count": total_count,
            "avg_tip": round(total_amount / total_count, 2) if total_count else 0,
            "leaderboard": leaderboard_rows,
            "by_role": role_rows,
            "recent_messages": messages,
        }

    # ---------------- ADMIN: list (filter + paging) ----------------
    @router.get("/tipping/list/{property_id}")
    async def list_tips(property_id: str, status: Optional[str] = None, limit: int = 100,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        q = {"property_id": property_id}
        if status:
            q["status"] = status
        rows = await db.tips.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        return {"rows": rows, "count": len(rows)}

    return router
