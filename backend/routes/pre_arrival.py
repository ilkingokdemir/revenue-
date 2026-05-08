"""
Pre-arrival Drip Email Sequence (P1)
------------------------------------
Property-level template for staged comms before guest checks in:

  T-7 days  — "Get ready for your stay" (welcome + map + parking)
  T-3 days  — Upsell window (early check-in, late checkout, airport transfer)
  T-1 day   — Final reminder (door-code, weather, dining recs)
  T+0       — On-arrival comms (Wi-Fi, room location, breakfast)

A scheduler sweeps `bookings` daily and queues `pre_arrival_dispatches` rows
that the existing email/SMS pipeline drains. Templates are property-level with
language fallback and merge tags ({guest_name}, {checkin_date}, {hotel_name}).

Endpoints
---------
POST /pre-arrival/templates                Upsert template for a property
GET  /pre-arrival/{property_id}/templates  List templates
DELETE /pre-arrival/templates/{id}         Remove template
POST /pre-arrival/sweep                    Cron — schedule due dispatches
GET  /pre-arrival/{property_id}/dispatches Recent / pending dispatches
POST /pre-arrival/dispatches/{id}/preview  Render merged subject + body
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional
import uuid


VALID_STAGES = {"t_minus_7", "t_minus_3", "t_minus_1", "t_zero"}
STAGE_OFFSET_DAYS = {"t_minus_7": 7, "t_minus_3": 3, "t_minus_1": 1, "t_zero": 0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _merge(text: str, ctx: Dict) -> str:
    out = text or ""
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", str(v if v is not None else ""))
    return out


def create_pre_arrival_router(db, require_roles):
    router = APIRouter()

    @router.post("/pre-arrival/templates")
    async def upsert(data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        stage = (data.get("stage") or "").strip()
        lang = (data.get("language") or "en").strip().lower()
        if not property_id or stage not in VALID_STAGES:
            raise HTTPException(400, f"property_id and stage in {VALID_STAGES} required")
        subject = (data.get("subject") or "").strip()
        body = (data.get("body") or "").strip()
        if not subject or not body:
            raise HTTPException(400, "subject + body required")
        key = {"property_id": property_id, "stage": stage, "language": lang}
        existing = await db.pre_arrival_templates.find_one(key, {"_id": 0})
        record = {
            **key,
            "subject": subject,
            "body": body,
            "channel": (data.get("channel") or "email"),  # email | sms | whatsapp
            "active": bool(data.get("active", True)),
            "updated_at": _now(),
            "updated_by": current_user.get("name", "Staff"),
        }
        if existing:
            record["id"] = existing["id"]
            await db.pre_arrival_templates.update_one(key, {"$set": record})
        else:
            record["id"] = str(uuid.uuid4())
            record["created_at"] = _now()
            await db.pre_arrival_templates.insert_one(dict(record))
        return {"ok": True, "template": record}

    @router.get("/pre-arrival/{property_id}/templates")
    async def list_templates(property_id: str,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.pre_arrival_templates.find({"property_id": property_id}, {"_id": 0}).sort("stage", 1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.delete("/pre-arrival/templates/{template_id}")
    async def delete_tpl(template_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.pre_arrival_templates.delete_one({"id": template_id})
        return {"ok": True}

    @router.post("/pre-arrival/sweep")
    async def sweep(data: Optional[Dict] = None,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data or {}).get("property_id", "")
        q: Dict = {"status": {"$in": ["confirmed", "checked_in"]}}
        if property_id:
            q["property_id"] = property_id
        bookings = await db.bookings.find(q, {"_id": 0}).to_list(20000)
        today = _today()
        scheduled = 0
        for b in bookings:
            ci = (b.get("check_in") or "")[:10]
            if not ci:
                continue
            try:
                ci_d = date.fromisoformat(ci)
            except ValueError:
                continue
            days_to_ci = (ci_d - today).days
            for stage, offset in STAGE_OFFSET_DAYS.items():
                if days_to_ci != offset:
                    continue
                # Look up template (lang fallback en)
                lang = (b.get("language") or "en").lower()
                tpl = await db.pre_arrival_templates.find_one(
                    {"property_id": b.get("property_id", ""), "stage": stage, "language": lang, "active": True}, {"_id": 0}
                ) or await db.pre_arrival_templates.find_one(
                    {"property_id": b.get("property_id", ""), "stage": stage, "language": "en", "active": True}, {"_id": 0}
                )
                if not tpl:
                    continue
                # Already queued?
                existing = await db.pre_arrival_dispatches.find_one(
                    {"booking_id": b["id"], "stage": stage}, {"_id": 0}
                )
                if existing:
                    continue
                await db.pre_arrival_dispatches.insert_one({
                    "id": str(uuid.uuid4()),
                    "property_id": b.get("property_id", ""),
                    "booking_id": b["id"],
                    "stage": stage,
                    "channel": tpl.get("channel", "email"),
                    "language": tpl.get("language", "en"),
                    "to_email": b.get("guest_email", ""),
                    "to_phone": b.get("guest_phone", ""),
                    "template_id": tpl["id"],
                    "subject_preview": tpl["subject"][:80],
                    "scheduled_for": _now(),
                    "status": "pending",  # pending | sent | failed | skipped
                })
                scheduled += 1
        return {"ok": True, "scanned": len(bookings), "scheduled": scheduled, "today": today.isoformat()}

    @router.get("/pre-arrival/{property_id}/dispatches")
    async def list_dispatches(property_id: str, days: int = 14, status: str = "",
                                current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "scheduled_for": {"$gte": since}}
        if status:
            q["status"] = status
        rows = await db.pre_arrival_dispatches.find(q, {"_id": 0}).sort("scheduled_for", -1).to_list(500)
        by_stage = {s: 0 for s in VALID_STAGES}
        sent = 0
        pending = 0
        for r in rows:
            by_stage[r.get("stage", "")] = by_stage.get(r.get("stage", ""), 0) + 1
            if r.get("status") == "sent": sent += 1
            if r.get("status") == "pending": pending += 1
        return {"items": rows, "count": len(rows), "by_stage": by_stage, "sent": sent, "pending": pending}

    @router.post("/pre-arrival/dispatches/{dispatch_id}/preview")
    async def preview(dispatch_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        d = await db.pre_arrival_dispatches.find_one({"id": dispatch_id}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Dispatch not found")
        tpl = await db.pre_arrival_templates.find_one({"id": d["template_id"]}, {"_id": 0})
        if not tpl:
            raise HTTPException(404, "Template missing — cannot render")
        booking = await db.bookings.find_one({"id": d["booking_id"]}, {"_id": 0}) or {}
        prop = await db.properties.find_one({"id": d["property_id"]}, {"_id": 0}) or {}
        ctx = {
            "guest_name": booking.get("guest_name", ""),
            "first_name": (booking.get("guest_name") or "").split(" ")[0],
            "checkin_date": (booking.get("check_in") or "")[:10],
            "checkout_date": (booking.get("check_out") or "")[:10],
            "nights": booking.get("nights", 0),
            "hotel_name": prop.get("name", ""),
            "hotel_phone": prop.get("phone", ""),
            "hotel_address": prop.get("address", ""),
            "room_type": booking.get("room_type", ""),
            "booking_ref": (booking.get("id") or "")[:8],
        }
        return {
            "ok": True,
            "subject": _merge(tpl["subject"], ctx),
            "body": _merge(tpl["body"], ctx),
            "to_email": d.get("to_email", ""),
            "channel": d.get("channel", "email"),
            "stage": d.get("stage", ""),
            "context": ctx,
        }

    return router
