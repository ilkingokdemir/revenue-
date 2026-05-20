"""
Service Recovery Auto-Voucher (P1)
----------------------------------
Listens to low-score mid-stay survey responses (and any manually opened
service_recovery_tickets) and instantly generates a single-use voucher code
that the guest can redeem on their *next* booking.

Voucher schema:
  code, percent_off, max_amount_off, valid_from, valid_until, redeemed,
  source_ticket_id, guest_email, property_id

Endpoints
---------
POST /service-recovery/voucher              Manual issue
POST /service-recovery/sweep                Cron — auto-issue for open tickets without voucher
GET  /service-recovery/{property_id}/vouchers
POST /service-recovery/voucher/{code}/redeem  Mark voucher as used (server-side)
GET  /service-recovery/voucher/{code}        Public lookup (booking widget)
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import secrets
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_code() -> str:
    return f"SR-{secrets.token_hex(4).upper()}"


def _amount_for_score(score: int) -> Dict[str, float]:
    if score <= 1: return {"percent_off": 25.0, "max_amount_off": 200.0}
    if score == 2: return {"percent_off": 20.0, "max_amount_off": 150.0}
    return {"percent_off": 15.0, "max_amount_off": 100.0}


def create_service_recovery_voucher_router(db, require_roles):
    router = APIRouter()

    @router.post("/service-recovery/voucher")
    async def issue(data: Dict,
                     current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        property_id = (data.get("property_id") or "").strip()
        guest_email = (data.get("guest_email") or "").strip().lower()
        ticket_id = (data.get("ticket_id") or "").strip()
        if not property_id:
            raise HTTPException(400, "property_id required")
        score = int(data.get("score") or 3)
        amts = _amount_for_score(score)
        v = {
            "id": str(uuid.uuid4()),
            "code": _new_code(),
            "property_id": property_id,
            "guest_email": guest_email,
            "guest_name": data.get("guest_name", ""),
            "source_ticket_id": ticket_id,
            "source_score": score,
            "percent_off": float(data.get("percent_off") or amts["percent_off"]),
            "max_amount_off": float(data.get("max_amount_off") or amts["max_amount_off"]),
            "currency": data.get("currency", "GBP"),
            "valid_from": _now(),
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=int(data.get("valid_days") or 180))).isoformat(),
            "redeemed": False,
            "redeemed_at": "",
            "redeemed_booking_id": "",
            "issued_at": _now(),
            "issued_by": current_user.get("name", "Staff"),
        }
        await db.service_recovery_vouchers.insert_one(dict(v))
        if ticket_id:
            await db.service_recovery_tickets.update_one(
                {"id": ticket_id},
                {"$set": {"voucher_code": v["code"], "voucher_issued_at": _now()}},
            )
        v.pop("_id", None)
        return {"ok": True, "voucher": v}

    @router.post("/service-recovery/sweep")
    async def sweep(data: Optional[Dict] = None,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        property_id = (data or {}).get("property_id", "")
        q: Dict = {"status": "open", "voucher_code": {"$exists": False}}
        if property_id:
            q["property_id"] = property_id
        tickets = await db.service_recovery_tickets.find(q, {"_id": 0}).to_list(2000)
        issued = 0
        for t in tickets:
            score = int(t.get("score") or 3)
            amts = _amount_for_score(score)
            v = {
                "id": str(uuid.uuid4()),
                "code": _new_code(),
                "property_id": t.get("property_id", ""),
                "guest_email": (t.get("guest_email") or "").lower(),
                "guest_name": t.get("guest_name", ""),
                "source_ticket_id": t["id"],
                "source_score": score,
                "percent_off": amts["percent_off"],
                "max_amount_off": amts["max_amount_off"],
                "currency": "GBP",
                "valid_from": _now(),
                "valid_until": (datetime.now(timezone.utc) + timedelta(days=180)).isoformat(),
                "redeemed": False,
                "issued_at": _now(),
                "issued_by": "auto-sweep",
            }
            await db.service_recovery_vouchers.insert_one(dict(v))
            await db.service_recovery_tickets.update_one(
                {"id": t["id"]},
                {"$set": {"voucher_code": v["code"], "voucher_issued_at": _now()}},
            )
            issued += 1
        return {"ok": True, "scanned": len(tickets), "issued": issued}

    @router.get("/service-recovery/{property_id}/vouchers")
    async def list_vouchers(property_id: str, days: int = 180, redeemed: str = "",
                              current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q: Dict = {"property_id": property_id, "issued_at": {"$gte": since}}
        if redeemed == "yes": q["redeemed"] = True
        if redeemed == "no": q["redeemed"] = False
        rows = await db.service_recovery_vouchers.find(q, {"_id": 0}).sort("issued_at", -1).to_list(500)
        used = sum(1 for r in rows if r.get("redeemed"))
        return {"items": rows, "count": len(rows), "redeemed_count": used,
                 "redeem_rate": round(used * 100 / max(len(rows), 1), 1)}

    @router.post("/service-recovery/voucher/{code}/redeem")
    async def redeem(code: str, data: Dict,
                       current_user: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        v = await db.service_recovery_vouchers.find_one({"code": code}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Voucher code not found")
        if v.get("redeemed"):
            raise HTTPException(400, "Voucher already redeemed")
        if v.get("valid_until") and v["valid_until"] < _now():
            raise HTTPException(400, "Voucher expired")
        await db.service_recovery_vouchers.update_one(
            {"code": code},
            {"$set": {"redeemed": True, "redeemed_at": _now(),
                       "redeemed_booking_id": data.get("booking_id", ""),
                       "redeemed_by": current_user.get("name", "Staff")}},
        )
        return {"ok": True, "voucher_code": code, "percent_off": v["percent_off"], "max_amount_off": v["max_amount_off"]}

    @router.get("/service-recovery/voucher/{code}")
    async def lookup(code: str):
        """Public — booking widget validates user-entered code."""
        v = await db.service_recovery_vouchers.find_one({"code": code}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Code not found")
        valid = (not v.get("redeemed")) and (v.get("valid_until", "") >= _now())
        return {"code": code, "valid": valid, "redeemed": v.get("redeemed", False),
                 "percent_off": v.get("percent_off"), "max_amount_off": v.get("max_amount_off"),
                 "valid_until": v.get("valid_until")}

    return router
