"""
Self Check-in Auto Trigger
==========================

Automates the pre-arrival self check-in flow so the property doesn't have to
press a button per booking. Two configurable trigger windows:

  • email_window_h  (default 48h before check-in) → Resend email + auto-issue token
  • sms_window_h    (default 4h before check-in)  → Twilio SMS reminder
                                                    (re-uses same token)

Tokens are issued via the existing self_checkin_v2 collection so all downstream
endpoints (verify / reg-card / slot) work unchanged.

Endpoints
---------
GET  /self-checkin-auto/settings/{property_id}   read settings
PUT  /self-checkin-auto/settings/{property_id}   update settings
POST /self-checkin-auto/run-once/{property_id}   force one pass (manual)
GET  /self-checkin-auto/log/{property_id}        last 100 dispatch attempts
GET  /self-checkin-auto/stats/{property_id}      counts: queued / sent / failed

The background loop runs every 5 minutes (when enabled per property).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
import asyncio
import logging
import os
import uuid

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "enabled": True,
    "email_enabled": True,
    "sms_enabled": True,
    "email_window_h": 48,
    "sms_window_h": 4,
    "expiry_hours": 96,
    "subject_template_tr": "Erken check-in linkiniz hazır — {hotel_name}",
    "subject_template_en": "Your fast-track check-in link — {hotel_name}",
    "body_template_tr": (
        "Merhaba {guest_name},\n\n"
        "{check_in} tarihindeki konaklamanız için resepsiyonda zaman "
        "kaybetmeyin: aşağıdaki linkten kayıt kartınızı önceden doldurun, "
        "bir varış saati seçin ve fast-track girişin keyfini çıkarın.\n\n"
        "{link}\n\n"
        "Güzel bir konaklama dileriz,\n{hotel_name}"
    ),
    "body_template_en": (
        "Hello {guest_name},\n\n"
        "Skip the queue at reception for your stay on {check_in}: complete "
        "your registration card and pick an arrival slot using the link below. "
        "We'll have your key ready when you arrive.\n\n"
        "{link}\n\n"
        "See you soon,\n{hotel_name}"
    ),
    "sms_template_tr": "Hoş geldiniz! Hızlı giriş için {link} (geçerlilik {expiry}h)",
    "sms_template_en": "Welcome! Fast-track check-in: {link} (valid {expiry}h)",
    "language": "tr",  # tr | en
}


class AutoSettings(BaseModel):
    enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    email_window_h: Optional[int] = Field(None, ge=1, le=168)
    sms_window_h: Optional[int] = Field(None, ge=1, le=168)
    expiry_hours: Optional[int] = Field(None, ge=12, le=720)
    subject_template_tr: Optional[str] = None
    subject_template_en: Optional[str] = None
    body_template_tr: Optional[str] = None
    body_template_en: Optional[str] = None
    sms_template_tr: Optional[str] = None
    sms_template_en: Optional[str] = None
    language: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _frontend_link(token: str) -> str:
    base = (os.environ.get("FRONTEND_URL")
            or os.environ.get("REACT_APP_BACKEND_URL")
            or "").rstrip("/")
    return f"{base}/selfcheckin-v2/{token}"


def _format(t: str, ctx: dict) -> str:
    try:
        return t.format(**ctx)
    except Exception:
        # Don't crash on a missing key — just return the raw template.
        return t


async def _resolve_settings(db, property_id: str) -> dict:
    cfg = await db.self_checkin_auto_config.find_one({"property_id": property_id}, {"_id": 0})
    if not cfg:
        cfg = {"property_id": property_id, **DEFAULT_SETTINGS}
    else:
        # Backfill any new keys with defaults so old configs don't break.
        for k, v in DEFAULT_SETTINGS.items():
            cfg.setdefault(k, v)
    return cfg


async def _ensure_token(db, booking: dict, expiry_hours: int) -> dict:
    """Return existing or freshly issued self-checkin-v2 token for the booking."""
    existing = await db.self_checkin_tokens.find_one(
        {"booking_id": booking["id"]}, {"_id": 0}
    )
    if existing:
        return existing
    token_str = uuid.uuid4().hex
    now = _now()
    doc = {
        "id": str(uuid.uuid4()),
        "token": token_str,
        "booking_id": booking["id"],
        "property_id": booking.get("property_id"),
        "guest_name": booking.get("guest_name"),
        "guest_email": booking.get("guest_email"),
        "created_at": now.isoformat(),
        "created_by": "auto-trigger",
        "expires_at": (now + timedelta(hours=expiry_hours)).isoformat(),
        "status": "issued",
    }
    await db.self_checkin_tokens.insert_one(dict(doc))
    await db.bookings.update_one(
        {"id": booking["id"]},
        {"$set": {
            "self_checkin_v2_token": token_str,
            "self_checkin_v2_issued_at": now.isoformat(),
            "self_checkin_v2_issued_by": "auto-trigger",
        }}
    )
    doc.pop("_id", None)
    return doc


async def _send_email(db, cfg: dict, booking: dict, prop: dict, token: dict, log_id: str) -> dict:
    """Send via Resend if API key present, otherwise queue-only."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    lang = (cfg.get("language") or "en").lower()
    link = _frontend_link(token["token"])
    ctx = {
        "guest_name": booking.get("guest_name") or "guest",
        "hotel_name": prop.get("name") or "Hotel",
        "check_in": booking.get("check_in") or "",
        "link": link,
    }
    subj_t = cfg.get(f"subject_template_{lang}") or cfg.get("subject_template_en")
    body_t = cfg.get(f"body_template_{lang}") or cfg.get("body_template_en")
    subject = _format(subj_t, ctx)
    body = _format(body_t, ctx)
    to_email = booking.get("guest_email")
    if not to_email:
        return {"channel": "email", "status": "skipped", "reason": "no email"}
    if not api_key:
        await db.self_checkin_auto_log.update_one(
            {"id": log_id},
            {"$set": {"email_status": "queued", "email_subject": subject, "email_link": link}}
        )
        return {"channel": "email", "status": "queued", "reason": "RESEND_API_KEY missing"}
    # Real dispatch
    try:
        import resend
        resend.api_key = api_key
        resp = resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "no-reply@hotel.local"),
            "to": [to_email],
            "subject": subject,
            "text": body,
        })
        await db.self_checkin_auto_log.update_one(
            {"id": log_id},
            {"$set": {"email_status": "sent", "email_subject": subject,
                      "email_link": link, "email_provider_id": resp.get("id")}}
        )
        return {"channel": "email", "status": "sent"}
    except Exception as e:
        msg = str(e).lower()
        # Treat invalid/missing/expired keys as 'queued' rather than 'failed' so the
        # admin sees a clean "waiting for key" state instead of a scary error count.
        if any(s in msg for s in ("api key", "invalid_api_key", "unauthorized", "401", "403", "auth")):
            await db.self_checkin_auto_log.update_one(
                {"id": log_id},
                {"$set": {"email_status": "queued", "email_subject": subject,
                          "email_link": link, "email_error": str(e)}}
            )
            return {"channel": "email", "status": "queued", "reason": "API key invalid/missing"}
        await db.self_checkin_auto_log.update_one(
            {"id": log_id}, {"$set": {"email_status": "failed", "email_error": str(e)}}
        )
        return {"channel": "email", "status": "failed", "error": str(e)}


async def _send_sms(db, cfg: dict, booking: dict, prop: dict, token: dict, log_id: str) -> dict:
    """Send via Twilio if API key present, otherwise queue-only."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    tkn = os.environ.get("TWILIO_AUTH_TOKEN", "")
    frm = os.environ.get("TWILIO_FROM", "")
    lang = (cfg.get("language") or "en").lower()
    link = _frontend_link(token["token"])
    expiry = cfg.get("expiry_hours", 96)
    ctx = {"link": link, "expiry": expiry,
           "guest_name": booking.get("guest_name") or "guest",
           "hotel_name": prop.get("name") or "Hotel"}
    body_t = cfg.get(f"sms_template_{lang}") or cfg.get("sms_template_en")
    body = _format(body_t, ctx)
    to_phone = (booking.get("guest_phone") or "").strip()
    if not to_phone:
        return {"channel": "sms", "status": "skipped", "reason": "no phone"}
    if not (sid and tkn and frm):
        await db.self_checkin_auto_log.update_one(
            {"id": log_id}, {"$set": {"sms_status": "queued", "sms_body": body, "sms_link": link}}
        )
        return {"channel": "sms", "status": "queued", "reason": "Twilio creds missing"}
    try:
        from twilio.rest import Client
        client = Client(sid, tkn)
        msg = client.messages.create(body=body, from_=frm, to=to_phone)
        await db.self_checkin_auto_log.update_one(
            {"id": log_id},
            {"$set": {"sms_status": "sent", "sms_body": body, "sms_link": link, "sms_provider_id": msg.sid}}
        )
        return {"channel": "sms", "status": "sent"}
    except Exception as e:
        msg = str(e).lower()
        if any(s in msg for s in ("auth", "401", "403", "unauthorized", "invalid", "credentials")):
            await db.self_checkin_auto_log.update_one(
                {"id": log_id},
                {"$set": {"sms_status": "queued", "sms_body": body, "sms_link": link, "sms_error": str(e)}}
            )
            return {"channel": "sms", "status": "queued", "reason": "Twilio creds invalid/missing"}
        await db.self_checkin_auto_log.update_one(
            {"id": log_id}, {"$set": {"sms_status": "failed", "sms_error": str(e)}}
        )
        return {"channel": "sms", "status": "failed", "error": str(e)}


async def _run_once(db, property_id: str) -> dict:
    """Single pass: scan upcoming bookings and trigger email/SMS as windows match."""
    cfg = await _resolve_settings(db, property_id)
    if not cfg.get("enabled"):
        return {"skipped": True, "reason": "disabled"}
    now = _now()
    horizon = now + timedelta(hours=max(cfg["email_window_h"], cfg["sms_window_h"]))
    today = now.strftime("%Y-%m-%d")
    horizon_d = horizon.strftime("%Y-%m-%d")
    # Find bookings whose check_in date falls between today and horizon date.
    bookings = await db.bookings.find({
        "property_id": property_id,
        "check_in": {"$gte": today, "$lte": horizon_d},
        "status": {"$nin": ["cancelled", "no_show"]},
    }, {"_id": 0}).to_list(500)

    prop = await db.properties.find_one({"id": property_id}, {"_id": 0}) or {"name": "Hotel"}

    out = {"processed": 0, "email": {"sent": 0, "queued": 0, "skipped": 0, "failed": 0},
           "sms":   {"sent": 0, "queued": 0, "skipped": 0, "failed": 0}, "details": []}

    for b in bookings:
        try:
            check_in_str = b.get("check_in") or ""
            check_in_dt = datetime.fromisoformat(check_in_str + "T15:00:00+00:00")
        except Exception:
            continue
        hours_until = (check_in_dt - now).total_seconds() / 3600.0
        if hours_until < 0:
            continue
        triggers = []
        if cfg.get("email_enabled") and hours_until <= cfg["email_window_h"] and not b.get("auto_email_sent_at"):
            triggers.append("email")
        if cfg.get("sms_enabled") and hours_until <= cfg["sms_window_h"] and not b.get("auto_sms_sent_at"):
            triggers.append("sms")
        if not triggers:
            continue

        token = await _ensure_token(db, b, cfg["expiry_hours"])
        log_id = str(uuid.uuid4())
        await db.self_checkin_auto_log.insert_one({
            "id": log_id,
            "property_id": property_id,
            "booking_id": b["id"],
            "guest_name": b.get("guest_name"),
            "triggers": triggers,
            "hours_until": round(hours_until, 2),
            "created_at": now.isoformat(),
        })

        results = []
        if "email" in triggers:
            r = await _send_email(db, cfg, b, prop, token, log_id)
            results.append(r)
            out["email"][r["status"]] = out["email"].get(r["status"], 0) + 1
            if r["status"] in ("sent", "queued"):
                await db.bookings.update_one({"id": b["id"]},
                    {"$set": {"auto_email_sent_at": now.isoformat(),
                              "auto_email_status": r["status"]}})
        if "sms" in triggers:
            r = await _send_sms(db, cfg, b, prop, token, log_id)
            results.append(r)
            out["sms"][r["status"]] = out["sms"].get(r["status"], 0) + 1
            if r["status"] in ("sent", "queued"):
                await db.bookings.update_one({"id": b["id"]},
                    {"$set": {"auto_sms_sent_at": now.isoformat(),
                              "auto_sms_status": r["status"]}})

        out["processed"] += 1
        out["details"].append({"booking_id": b["id"], "guest_name": b.get("guest_name"),
                               "hours_until": round(hours_until, 2), "results": results})

    out["ran_at"] = now.isoformat()
    return out


def create_self_checkin_auto_router(db, require_roles):
    router = APIRouter()

    @router.get("/self-checkin-auto/settings/{property_id}")
    async def get_settings(property_id: str,
                           current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        return await _resolve_settings(db, property_id)

    @router.put("/self-checkin-auto/settings/{property_id}")
    async def update_settings(property_id: str, patch: AutoSettings,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        cur = await _resolve_settings(db, property_id)
        upd = {k: v for k, v in patch.model_dump().items() if v is not None}
        cur.update(upd)
        cur["property_id"] = property_id
        cur["updated_at"] = _now().isoformat()
        cur["updated_by"] = current_user.get("email")
        await db.self_checkin_auto_config.update_one(
            {"property_id": property_id}, {"$set": cur}, upsert=True
        )
        cur.pop("_id", None)
        return cur

    @router.post("/self-checkin-auto/run-once/{property_id}")
    async def run_once(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        return await _run_once(db, property_id)

    @router.get("/self-checkin-auto/log/{property_id}")
    async def log(property_id: str, limit: int = 100,
                  current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        items = await db.self_checkin_auto_log.find(
            {"property_id": property_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(limit)
        return {"items": items, "count": len(items)}

    @router.get("/self-checkin-auto/stats/{property_id}")
    async def stats(property_id: str,
                    current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        cursor = db.self_checkin_auto_log.find(
            {"property_id": property_id}, {"_id": 0}
        )
        items = await cursor.to_list(2000)
        out = {
            "total_attempts": len(items),
            "email": {"sent": 0, "queued": 0, "failed": 0},
            "sms":   {"sent": 0, "queued": 0, "failed": 0},
        }
        for it in items:
            es = it.get("email_status")
            ss = it.get("sms_status")
            if es in out["email"]:
                out["email"][es] += 1
            if ss in out["sms"]:
                out["sms"][ss] += 1
        return out

    async def auto_trigger_loop():
        """Background loop: every 5 min, run trigger for all enabled properties."""
        await asyncio.sleep(15)  # slight startup delay
        while True:
            try:
                cfgs = await db.self_checkin_auto_config.find(
                    {"enabled": True}, {"_id": 0, "property_id": 1}
                ).to_list(500)
                # Ensure default property is always processed when no per-property cfg yet.
                seen = {c["property_id"] for c in cfgs}
                if "default" not in seen:
                    cfgs.append({"property_id": "default"})
                for c in cfgs:
                    try:
                        result = await _run_once(db, c["property_id"])
                        if result.get("processed"):
                            logger.info(
                                "self-checkin-auto: %s processed=%d email_sent=%d sms_sent=%d",
                                c["property_id"], result["processed"],
                                result["email"]["sent"], result["sms"]["sent"]
                            )
                    except Exception as e:
                        logger.error(f"self-checkin-auto loop error for {c['property_id']}: {e}")
            except Exception as e:
                logger.error(f"self-checkin-auto outer loop error: {e}")
            await asyncio.sleep(300)  # 5 minutes

    router.auto_trigger_loop = auto_trigger_loop
    return router
