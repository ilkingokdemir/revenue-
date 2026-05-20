"""
Multi-language Email Template Engine (P1)
-----------------------------------------
Central catalog of message templates indexed by (template_key, language).
Other modules (booking_confirmation, pre_arrival_drip, post_stay_thanks, etc)
can resolve a template via `/templates/render` and get the merged subject + body.

Endpoints
---------
POST /msg-templates                          Upsert a template
GET  /msg-templates/{property_id}            List for a property (filter by key/language)
DELETE /msg-templates/{template_id}          Remove
POST /msg-templates/render                   Resolve key + language (with fallback) + merge ctx
GET  /msg-templates/keys                     Catalog of known template keys
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, Optional
import uuid


KNOWN_KEYS = [
    {"key": "booking_confirmation",  "channel": "email", "description": "Sent immediately after a booking is confirmed."},
    {"key": "pre_arrival_t7",        "channel": "email", "description": "7 days before check-in."},
    {"key": "pre_arrival_t3",        "channel": "email", "description": "3 days before check-in (upsell)."},
    {"key": "pre_arrival_t1",        "channel": "email", "description": "1 day before check-in (final reminder)."},
    {"key": "on_arrival",            "channel": "email", "description": "Guest checks in."},
    {"key": "mid_stay_survey",       "channel": "email", "description": "Day-2 pulse survey invite."},
    {"key": "checkout_thanks",       "channel": "email", "description": "Post-checkout thank you + review request."},
    {"key": "rebook_followup",       "channel": "email", "description": "30 days after stay — quick rebook CTA."},
    {"key": "birthday_offer",        "channel": "email", "description": "Birthday voucher delivery."},
    {"key": "service_recovery_voucher", "channel": "email", "description": "Apology + voucher."},
    {"key": "loyalty_tier_upgrade",  "channel": "email", "description": "Tier promotion notice."},
    {"key": "cancellation_confirm",  "channel": "email", "description": "Booking cancelled."},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge(text: str, ctx: Dict) -> str:
    out = text or ""
    for k, v in (ctx or {}).items():
        out = out.replace("{" + k + "}", str(v if v is not None else ""))
    return out


def create_msg_templates_router(db, require_roles):
    router = APIRouter()

    @router.get("/msg-templates/keys")
    async def keys():
        return {"items": KNOWN_KEYS, "count": len(KNOWN_KEYS)}

    @router.post("/msg-templates")
    async def upsert(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        key = (data.get("key") or "").strip().lower()
        lang = (data.get("language") or "en").lower()
        subject = (data.get("subject") or "").strip()
        body = (data.get("body") or "").strip()
        if not property_id or not key or not subject or not body:
            raise HTTPException(400, "property_id, key, subject, body required")
        record = {
            "property_id": property_id,
            "key": key,
            "language": lang,
            "subject": subject,
            "body": body,
            "channel": data.get("channel", "email"),
            "active": bool(data.get("active", True)),
            "updated_at": _now(),
            "updated_by": current_user.get("name", "Staff"),
        }
        existing = await db.msg_templates.find_one({"property_id": property_id, "key": key, "language": lang}, {"_id": 0})
        if existing:
            record["id"] = existing["id"]
            await db.msg_templates.update_one({"id": existing["id"]}, {"$set": record})
        else:
            record["id"] = str(uuid.uuid4())
            record["created_at"] = _now()
            await db.msg_templates.insert_one(dict(record))
        return {"ok": True, "template": record}

    @router.get("/msg-templates/{property_id}")
    async def list_tpls(property_id: str, key: str = "", language: str = "",
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        q: Dict = {"property_id": property_id}
        if key:      q["key"] = key
        if language: q["language"] = language
        rows = await db.msg_templates.find(q, {"_id": 0}).sort([("key", 1), ("language", 1)]).to_list(500)
        # Coverage matrix: per-key list of available languages
        coverage: Dict[str, list] = {}
        for r in rows:
            coverage.setdefault(r["key"], []).append(r["language"])
        return {"items": rows, "count": len(rows), "coverage": coverage}

    @router.delete("/msg-templates/{template_id}")
    async def remove(template_id: str,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.msg_templates.delete_one({"id": template_id})
        return {"ok": True}

    @router.post("/msg-templates/render")
    async def render(data: Dict):
        property_id = (data.get("property_id") or "").strip()
        key = (data.get("key") or "").strip().lower()
        lang = (data.get("language") or "en").lower()
        ctx = data.get("context") or {}
        if not property_id or not key:
            raise HTTPException(400, "property_id, key required")
        # Try requested language → English fallback → any active
        tpl = await db.msg_templates.find_one(
            {"property_id": property_id, "key": key, "language": lang, "active": True}, {"_id": 0}
        ) or await db.msg_templates.find_one(
            {"property_id": property_id, "key": key, "language": "en", "active": True}, {"_id": 0}
        ) or await db.msg_templates.find_one(
            {"property_id": property_id, "key": key, "active": True}, {"_id": 0}
        )
        if not tpl:
            raise HTTPException(404, f"No template for key '{key}'")
        return {
            "key": key,
            "language_used": tpl["language"],
            "language_requested": lang,
            "channel": tpl.get("channel", "email"),
            "subject": _merge(tpl["subject"], ctx),
            "body": _merge(tpl["body"], ctx),
        }

    return router
