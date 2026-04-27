"""
Guest Birthday Auto-Discount (P1)
---------------------------------
Sweeps `guest_profiles` for upcoming birthdays in the next N days, generates
a single-use discount voucher (uses `service_recovery_vouchers` collection
with source='birthday'), and queues a `pre_arrival_dispatches`-style row in
`birthday_dispatches` for the email pipeline to pick up.

Endpoints
---------
POST /birthday/config                     Save discount % + lookahead days + voucher_validity_days
GET  /birthday/{property_id}/config
POST /birthday/sweep                      Cron — find upcoming birthdays, issue vouchers
GET  /birthday/{property_id}/upcoming     Show next N days of birthdays
GET  /birthday/{property_id}/dispatches   Queued comms (last 60d)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
import secrets
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _new_code() -> str:
    return f"BDAY-{secrets.token_hex(4).upper()}"


def _parse_dob(dob: str) -> Optional[date]:
    if not dob: return None
    try:
        return date.fromisoformat(dob[:10])
    except ValueError:
        return None


def _next_bday(dob: date, ref: date) -> date:
    try:
        nxt = dob.replace(year=ref.year)
    except ValueError:
        # Feb 29 born on a non-leap year — bump to Feb 28
        nxt = dob.replace(year=ref.year, day=28)
    if nxt < ref:
        try:
            nxt = nxt.replace(year=ref.year + 1)
        except ValueError:
            nxt = nxt.replace(year=ref.year + 1, day=28)
    return nxt


def create_birthday_router(db, require_roles):
    router = APIRouter()

    @router.post("/birthday/config")
    async def upsert(data: Dict,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data.get("property_id") or "").strip()
        if not property_id:
            raise HTTPException(400, "property_id required")
        record = {
            "property_id": property_id,
            "enabled": bool(data.get("enabled", True)),
            "lookahead_days": int(data.get("lookahead_days") or 30),
            "discount_pct": float(data.get("discount_pct") or 15.0),
            "max_amount_off": float(data.get("max_amount_off") or 100.0),
            "voucher_validity_days": int(data.get("voucher_validity_days") or 90),
            "channel": data.get("channel", "email"),
            "updated_at": _now(),
            "updated_by": current_user.get("name", "Staff"),
        }
        await db.birthday_config.update_one({"property_id": property_id}, {"$set": record}, upsert=True)
        return {"ok": True, "config": record}

    @router.get("/birthday/{property_id}/config")
    async def get_cfg(property_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        return await db.birthday_config.find_one({"property_id": property_id}, {"_id": 0}) or {
            "property_id": property_id, "enabled": True, "lookahead_days": 30,
            "discount_pct": 15.0, "max_amount_off": 100.0, "voucher_validity_days": 90, "channel": "email",
        }

    @router.post("/birthday/sweep")
    async def sweep(data: Optional[Dict] = None,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        body = data or {}
        property_id = body.get("property_id", "")
        cfg = await db.birthday_config.find_one({"property_id": property_id}, {"_id": 0}) if property_id else None
        if cfg and not cfg.get("enabled", True):
            return {"ok": True, "skipped": "disabled"}
        cfg = cfg or {"discount_pct": 15.0, "max_amount_off": 100.0, "voucher_validity_days": 90,
                       "lookahead_days": 30, "channel": "email"}

        q: Dict = {"date_of_birth": {"$exists": True, "$ne": ""}}
        if property_id:
            q["property_id"] = property_id
        profiles = await db.guest_profiles.find(q, {"_id": 0}).to_list(20000)
        today = _today()
        cutoff = today + timedelta(days=int(cfg["lookahead_days"]))
        issued = 0
        skipped = 0
        for p in profiles:
            dob = _parse_dob(p.get("date_of_birth", ""))
            if not dob:
                continue
            nxt = _next_bday(dob, today)
            if not (today <= nxt <= cutoff):
                continue
            # Already dispatched this birthday-year?
            dup = await db.birthday_dispatches.find_one({
                "property_id": p.get("property_id", property_id),
                "guest_email": p.get("guest_email", "").lower(),
                "birthday_year": nxt.year,
            }, {"_id": 0})
            if dup:
                skipped += 1
                continue
            code = _new_code()
            voucher = {
                "id": str(uuid.uuid4()),
                "code": code,
                "property_id": p.get("property_id", property_id),
                "guest_email": (p.get("guest_email") or "").lower(),
                "guest_name": p.get("guest_name", ""),
                "source_ticket_id": "",
                "source": "birthday",
                "source_score": 0,
                "percent_off": float(cfg["discount_pct"]),
                "max_amount_off": float(cfg["max_amount_off"]),
                "currency": "GBP",
                "valid_from": _now(),
                "valid_until": (datetime.combine(nxt, datetime.min.time()) + timedelta(days=int(cfg["voucher_validity_days"]))).replace(tzinfo=timezone.utc).isoformat(),
                "redeemed": False, "redeemed_at": "", "redeemed_booking_id": "",
                "issued_at": _now(), "issued_by": "birthday-sweep",
            }
            await db.service_recovery_vouchers.insert_one(dict(voucher))
            await db.birthday_dispatches.insert_one({
                "id": str(uuid.uuid4()),
                "property_id": p.get("property_id", property_id),
                "guest_email": (p.get("guest_email") or "").lower(),
                "guest_name": p.get("guest_name", ""),
                "birthday_year": nxt.year,
                "birthday_date": nxt.isoformat(),
                "voucher_code": code,
                "channel": cfg.get("channel", "email"),
                "scheduled_for": _now(),
                "status": "pending",
            })
            issued += 1
        return {"ok": True, "scanned": len(profiles), "issued": issued, "skipped_duplicates": skipped,
                 "today": today.isoformat()}

    @router.get("/birthday/{property_id}/upcoming")
    async def upcoming(property_id: str, days: int = 30,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        rows = await db.guest_profiles.find(
            {"property_id": property_id, "date_of_birth": {"$exists": True, "$ne": ""}}, {"_id": 0}
        ).to_list(20000)
        today = _today()
        cutoff = today + timedelta(days=days)
        out = []
        for p in rows:
            dob = _parse_dob(p.get("date_of_birth", ""))
            if not dob:
                continue
            nxt = _next_bday(dob, today)
            if today <= nxt <= cutoff:
                out.append({
                    "guest_name": p.get("guest_name", ""),
                    "guest_email": p.get("guest_email", ""),
                    "next_birthday": nxt.isoformat(),
                    "days_until": (nxt - today).days,
                    "loyalty_tier": p.get("loyalty_tier", "bronze"),
                    "lifetime_stays": p.get("lifetime_stays", 0),
                })
        out.sort(key=lambda x: x["days_until"])
        return {"items": out, "count": len(out)}

    @router.get("/birthday/{property_id}/dispatches")
    async def dispatches(property_id: str, days: int = 60,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await db.birthday_dispatches.find(
            {"property_id": property_id, "scheduled_for": {"$gte": since}}, {"_id": 0}
        ).sort("scheduled_for", -1).to_list(500)
        return {"items": rows, "count": len(rows)}

    return router
