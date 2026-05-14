"""
TÜRSAB Agency Portal — Self-Service Travel Agency Distribution.

TR market parity with Elektra Soft's TÜRSAB extranet (12,000+ travel agencies).
Provides travel agencies (acentalar) direct access to:
  - Contracted rates per property
  - Real-time availability quote
  - Direct booking creation against their contract
  - Commission/booking history

Auth model mirrors owner_self_service.py:
  - Agency record stores `password_hash` (bcrypt of PIN)
  - JWT with `type='agency_access'`, `sub=<agency_id>`
  - Token segregated from staff & owner tokens.

Endpoints
---------
Public:
  POST /api/agency-auth/login                 — email + PIN
  GET  /api/agency-auth/me                    — current agency profile
  GET  /api/agency-auth/dashboard             — YTD bookings + commission
  GET  /api/agency-auth/contracts             — list of contracted properties+rates
  POST /api/agency-auth/quote                 — { property_id, room_type_id, check_in, check_out, guests }
  POST /api/agency-auth/book                  — create booking against contract
  GET  /api/agency-auth/bookings              — list agency's bookings
  POST /api/agency-auth/logout

Admin (require_roles admin):
  POST /api/agencies                          — create agency
  GET  /api/agencies                          — list agencies
  GET  /api/agencies/{id}                     — detail
  PATCH /api/agencies/{id}                    — update
  POST /api/agencies/{id}/set-credentials     — generate or set PIN
  POST /api/agency-contracts                  — create per-property contract rate
  GET  /api/agency-contracts?agency_id=&property_id=
  PATCH /api/agency-contracts/{id}
  DELETE /api/agency-contracts/{id}
"""
from datetime import datetime, timezone, timedelta
import os
import secrets
import uuid
import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request

JWT_ALGORITHM = "HS256"


def _jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def _hash(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


def _create_agency_token(agency_id: str) -> str:
    payload = {
        "sub": agency_id,
        "type": "agency_access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _days_between(ci: str, co: str) -> int:
    try:
        a = datetime.strptime(ci[:10], "%Y-%m-%d")
        b = datetime.strptime(co[:10], "%Y-%m-%d")
        return max(1, (b - a).days)
    except Exception:
        return 1


def _date_in_range(d: str, frm: str, to: str) -> bool:
    if frm and d < frm:
        return False
    if to and d > to:
        return False
    return True


def create_agency_portal_router(db, require_roles):
    router = APIRouter()

    async def get_current_agency(request: Request) -> dict:
        token = request.cookies.get("agency_access_token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            raise HTTPException(401, "Not authenticated")
        try:
            payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "agency_access":
                raise HTTPException(401, "Invalid token type")
            ag = await db.travel_agencies.find_one({"id": payload["sub"]}, {"_id": 0})
            if not ag:
                raise HTTPException(401, "Agency not found")
            if not ag.get("login_enabled", True):
                raise HTTPException(403, "Agency login disabled")
            return ag
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid token")

    # =========== Public agency auth ===========
    @router.post("/agency-auth/login")
    async def login(body: dict):
        email = (body.get("email") or "").strip().lower()
        pin = body.get("pin") or body.get("password") or ""
        if not email or not pin:
            raise HTTPException(400, "email and pin required")
        ag = await db.travel_agencies.find_one({"email": email}, {"_id": 0})
        if not ag or not ag.get("password_hash"):
            raise HTTPException(401, "Invalid credentials")
        if not _verify(pin, ag["password_hash"]):
            raise HTTPException(401, "Invalid credentials")
        if not ag.get("login_enabled", True):
            raise HTTPException(403, "Login disabled — contact management")
        token = _create_agency_token(ag["id"])
        await db.travel_agencies.update_one(
            {"id": ag["id"]},
            {"$set": {"last_login_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "agency": {
                "id": ag["id"], "name": ag.get("name"),
                "email": ag.get("email"),
                "tursab_no": ag.get("tursab_no"),
                "default_commission_percent": ag.get("default_commission_percent", 10),
            },
        }

    @router.get("/agency-auth/me")
    async def me(ag: dict = Depends(get_current_agency)):
        return {
            "id": ag["id"], "name": ag.get("name"),
            "email": ag.get("email"),
            "tursab_no": ag.get("tursab_no"),
            "company": ag.get("company"),
            "phone": ag.get("phone"),
            "contact_person": ag.get("contact_person"),
            "default_commission_percent": ag.get("default_commission_percent", 10),
            "payment_terms": ag.get("payment_terms", "Net 30"),
            "last_login_at": ag.get("last_login_at"),
        }

    @router.post("/agency-auth/logout")
    async def logout(_: dict = Depends(get_current_agency)):
        return {"ok": True}

    @router.get("/agency-auth/dashboard")
    async def dashboard(year: str = "", ag: dict = Depends(get_current_agency)):
        if not year:
            year = datetime.now(timezone.utc).strftime("%Y")
        bookings = await db.bookings.find(
            {"agency_id": ag["id"],
             "status": {"$nin": ["cancelled"]},
             "check_in": {"$regex": f"^{year}"}},
            {"_id": 0},
        ).to_list(2000)
        months = [{"month": f"{year}-{m:02d}", "revenue": 0.0,
                   "nights": 0, "bookings": 0, "commission": 0.0}
                  for m in range(1, 13)]
        commission_default = float(ag.get("default_commission_percent", 10)) / 100.0
        for b in bookings:
            ci = (b.get("check_in") or "")[:7]
            if not ci.startswith(year):
                continue
            try:
                idx = int(ci[5:7]) - 1
            except (ValueError, TypeError):
                continue
            if 0 <= idx < 12:
                rev = float(b.get("total_price") or 0)
                comm = rev * float(b.get("commission_percent",
                                          commission_default * 100)) / 100.0
                months[idx]["revenue"] += rev
                months[idx]["nights"] += int(b.get("nights") or 1)
                months[idx]["bookings"] += 1
                months[idx]["commission"] += comm
        for m in months:
            m["revenue"] = round(m["revenue"], 2)
            m["commission"] = round(m["commission"], 2)
        total = {
            "revenue": round(sum(m["revenue"] for m in months), 2),
            "commission": round(sum(m["commission"] for m in months), 2),
            "nights": sum(m["nights"] for m in months),
            "bookings_count": sum(m["bookings"] for m in months),
        }
        return {"agency_id": ag["id"], "year": year,
                "months": months, "total": total}

    @router.get("/agency-auth/contracts")
    async def list_my_contracts(ag: dict = Depends(get_current_agency)):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        contracts = await db.agency_contracts.find(
            {"agency_id": ag["id"], "is_active": True}, {"_id": 0}
        ).to_list(500)
        # Enrich with property name + room_type label
        prop_ids = list({c["property_id"] for c in contracts if c.get("property_id")})
        rt_ids = list({c["room_type_id"] for c in contracts if c.get("room_type_id")})
        props = await db.properties.find(
            {"id": {"$in": prop_ids}}, {"_id": 0, "id": 1, "name": 1}
        ).to_list(200) if prop_ids else []
        rts = await db.room_types.find(
            {"id": {"$in": rt_ids}}, {"_id": 0, "id": 1, "name": 1}
        ).to_list(200) if rt_ids else []
        prop_map = {p["id"]: p["name"] for p in props}
        rt_map = {r["id"]: r["name"] for r in rts}
        for c in contracts:
            c["property_name"] = prop_map.get(c.get("property_id"), c.get("property_id"))
            c["room_type_name"] = rt_map.get(c.get("room_type_id"), "Tüm odalar")
            c["valid_now"] = _date_in_range(today, c.get("valid_from", ""), c.get("valid_to", ""))
        return {"items": contracts, "count": len(contracts)}

    @router.post("/agency-auth/quote")
    async def quote(body: dict, ag: dict = Depends(get_current_agency)):
        prop_id = body.get("property_id")
        rt_id = body.get("room_type_id")
        ci = body.get("check_in") or ""
        co = body.get("check_out") or ""
        guests = int(body.get("guests") or 2)
        if not all([prop_id, rt_id, ci, co]):
            raise HTTPException(400, "property_id, room_type_id, check_in, check_out required")
        contract = await db.agency_contracts.find_one(
            {"agency_id": ag["id"], "property_id": prop_id,
             "room_type_id": rt_id, "is_active": True}, {"_id": 0}
        )
        if not contract:
            # fall back to property-wide contract
            contract = await db.agency_contracts.find_one(
                {"agency_id": ag["id"], "property_id": prop_id,
                 "room_type_id": None, "is_active": True}, {"_id": 0}
            )
        if not contract:
            raise HTTPException(404, "Bu mülk/oda için aktif acenta kontratı yok")
        # Validate stay rules
        nights = _days_between(ci, co)
        if contract.get("min_stay") and nights < int(contract["min_stay"]):
            raise HTTPException(400, f"Minimum konaklama {contract['min_stay']} gece")
        if contract.get("max_stay") and nights > int(contract["max_stay"]):
            raise HTTPException(400, f"Maksimum konaklama {contract['max_stay']} gece")
        if not _date_in_range(ci[:10], contract.get("valid_from", ""), contract.get("valid_to", "")):
            raise HTTPException(400, "Tarih kontrat geçerlilik aralığı dışında")
        # Blackout dates
        for bd in (contract.get("blackout_dates") or []):
            if ci[:10] <= bd <= co[:10]:
                raise HTTPException(400, f"Blackout date: {bd}")
        # Compute price (handle stay-pay promotion e.g. stay_pay 7/6 → pay 6 nights)
        contract_rate = float(contract.get("contract_rate", 0))
        promo = contract.get("promotion") or {}
        pay_nights = nights
        promo_label = ""
        if promo.get("type") == "stay_pay":
            stay_n = int(promo.get("stay", 0))
            pay_n = int(promo.get("pay", 0))
            if stay_n > 0 and pay_n > 0 and nights >= stay_n:
                multiples = nights // stay_n
                remainder = nights % stay_n
                pay_nights = multiples * pay_n + remainder
                promo_label = f"{stay_n} yat {pay_n} öde"
        elif promo.get("type") == "early_bird":
            days_ahead = (datetime.strptime(ci[:10], "%Y-%m-%d") -
                          datetime.now(timezone.utc).replace(tzinfo=None)).days
            min_ahead = int(promo.get("days_ahead", 30))
            disc = float(promo.get("discount_percent", 10))
            if days_ahead >= min_ahead:
                contract_rate = round(contract_rate * (1 - disc / 100), 2)
                promo_label = f"Erken Rezervasyon -%{disc}"
        gross = round(contract_rate * pay_nights, 2)
        commission_pct = float(contract.get("commission_percent",
                                            ag.get("default_commission_percent", 10)))
        commission = round(gross * commission_pct / 100, 2)
        return {
            "property_id": prop_id, "room_type_id": rt_id,
            "check_in": ci, "check_out": co,
            "nights": nights, "pay_nights": pay_nights,
            "contract_rate_per_night": contract_rate,
            "total_gross": gross,
            "commission_percent": commission_pct,
            "commission_amount": commission,
            "net_payable_to_hotel": round(gross - commission, 2),
            "currency": contract.get("currency", "TRY"),
            "promotion": promo_label or None,
            "guests": guests,
            "contract_id": contract.get("id"),
        }

    @router.post("/agency-auth/book")
    async def create_booking(body: dict, ag: dict = Depends(get_current_agency)):
        guest_name = (body.get("guest_name") or "").strip()
        guest_email = (body.get("guest_email") or "").strip().lower()
        if not guest_name:
            raise HTTPException(400, "guest_name required")
        # Re-quote to validate & price
        q = await quote(body, ag)
        booking_id = str(uuid.uuid4())
        # Resolve a room from room_type if not given
        room_id = body.get("room_id")
        if not room_id:
            room = await db.rooms.find_one(
                {"property_id": q["property_id"], "room_type_id": q["room_type_id"]},
                {"_id": 0, "id": 1, "room_number": 1},
            )
            room_id = (room or {}).get("id")
        booking = {
            "id": booking_id,
            "booking_ref": f"AG{booking_id[:6].upper()}",
            "property_id": q["property_id"],
            "room_id": room_id,
            "room_type_id": q["room_type_id"],
            "guest_name": guest_name,
            "guest_email": guest_email,
            "guest_phone": body.get("guest_phone", ""),
            "check_in": q["check_in"],
            "check_out": q["check_out"],
            "nights": q["nights"],
            "guests": q["guests"],
            "total_price": q["total_gross"],
            "currency": q["currency"],
            "status": "confirmed",
            "source": "agency",
            "agency_id": ag["id"],
            "agency_name": ag.get("name"),
            "tursab_no": ag.get("tursab_no"),
            "commission_percent": q["commission_percent"],
            "commission_amount": q["commission_amount"],
            "contract_id": q.get("contract_id"),
            "notes": body.get("notes", ""),
            "created_by": f"agency:{ag['id']}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.bookings.insert_one(booking)
        booking.pop("_id", None)
        return booking

    @router.get("/agency-auth/bookings")
    async def list_my_bookings(ag: dict = Depends(get_current_agency),
                               status: str = "", limit: int = 100):
        q: dict = {"agency_id": ag["id"]}
        if status:
            q["status"] = status
        items = await db.bookings.find(q, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(min(limit, 500))
        return {"items": items, "count": len(items)}

    # =========== Admin: agency CRUD ===========
    @router.post("/agencies")
    async def create_agency(body: dict,
                            current_user: dict = Depends(require_roles("admin"))):
        name = (body.get("name") or "").strip()
        email = (body.get("email") or "").strip().lower()
        if not name or not email:
            raise HTTPException(400, "name and email required")
        existing = await db.travel_agencies.find_one({"email": email}, {"_id": 0, "id": 1})
        if existing:
            raise HTTPException(409, "Agency with this email exists")
        ag = {
            "id": str(uuid.uuid4()),
            "name": name,
            "email": email,
            "tursab_no": body.get("tursab_no", ""),
            "company": body.get("company", name),
            "phone": body.get("phone", ""),
            "contact_person": body.get("contact_person", ""),
            "address": body.get("address", ""),
            "city": body.get("city", ""),
            "country": body.get("country", "TR"),
            "default_commission_percent": float(body.get("default_commission_percent", 10)),
            "payment_terms": body.get("payment_terms", "Net 30"),
            "login_enabled": True,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.travel_agencies.insert_one(ag)
        ag.pop("_id", None)
        ag.pop("password_hash", None)
        return ag

    @router.get("/agencies")
    async def list_agencies(_: dict = Depends(require_roles("admin", "manager"))):
        items = await db.travel_agencies.find(
            {}, {"_id": 0, "password_hash": 0}
        ).sort("name", 1).to_list(1000)
        return {"items": items, "count": len(items)}

    @router.get("/agencies/{agency_id}")
    async def get_agency(agency_id: str,
                         _: dict = Depends(require_roles("admin", "manager"))):
        ag = await db.travel_agencies.find_one(
            {"id": agency_id}, {"_id": 0, "password_hash": 0}
        )
        if not ag:
            raise HTTPException(404, "Agency not found")
        return ag

    @router.patch("/agencies/{agency_id}")
    async def patch_agency(agency_id: str, body: dict,
                           _: dict = Depends(require_roles("admin"))):
        allowed = {"name", "tursab_no", "company", "phone", "contact_person",
                   "address", "city", "country", "default_commission_percent",
                   "payment_terms", "login_enabled", "is_active"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.travel_agencies.update_one({"id": agency_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "Agency not found")
        return {"ok": True, "modified": r.modified_count}

    @router.post("/agencies/{agency_id}/set-credentials")
    async def set_credentials(agency_id: str, body: dict,
                              current_user: dict = Depends(require_roles("admin"))):
        ag = await db.travel_agencies.find_one({"id": agency_id}, {"_id": 0, "id": 1})
        if not ag:
            raise HTTPException(404, "Agency not found")
        pin = body.get("pin") or ""
        generate = body.get("generate", not pin)
        if generate:
            pin = "".join(secrets.choice("0123456789") for _ in range(6))
        if not pin or len(pin) < 4:
            raise HTTPException(400, "PIN must be at least 4 chars")
        update = {
            "password_hash": _hash(pin),
            "login_enabled": body.get("login_enabled", True),
            "credentials_set_at": datetime.now(timezone.utc).isoformat(),
            "credentials_set_by": current_user.get("name", ""),
        }
        await db.travel_agencies.update_one({"id": agency_id}, {"$set": update})
        return {
            "ok": True,
            "pin_generated": generate,
            "pin": pin if generate else None,
            "note": "Share this PIN with the agency over a secure channel. It will not be shown again.",
        }

    # =========== Admin: contract CRUD ===========
    @router.post("/agency-contracts")
    async def create_contract(body: dict,
                              current_user: dict = Depends(require_roles("admin", "manager"))):
        required = ["agency_id", "property_id", "contract_rate"]
        for f in required:
            if f not in body:
                raise HTTPException(400, f"{f} required")
        ag = await db.travel_agencies.find_one({"id": body["agency_id"]}, {"_id": 0, "id": 1})
        if not ag:
            raise HTTPException(404, "Agency not found")
        c = {
            "id": str(uuid.uuid4()),
            "agency_id": body["agency_id"],
            "property_id": body["property_id"],
            "room_type_id": body.get("room_type_id"),  # None = property-wide
            "contract_rate": float(body["contract_rate"]),
            "currency": body.get("currency", "TRY"),
            "commission_percent": float(body.get("commission_percent", 10)),
            "min_stay": int(body.get("min_stay", 1)),
            "max_stay": int(body.get("max_stay", 30)),
            "valid_from": body.get("valid_from", ""),
            "valid_to": body.get("valid_to", ""),
            "blackout_dates": body.get("blackout_dates", []),
            "promotion": body.get("promotion"),  # {"type":"stay_pay","stay":7,"pay":6} OR {"type":"early_bird","days_ahead":30,"discount_percent":10}
            "notes": body.get("notes", ""),
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("name", ""),
        }
        await db.agency_contracts.insert_one(c)
        c.pop("_id", None)
        return c

    @router.get("/agency-contracts")
    async def list_contracts(agency_id: str = "", property_id: str = "",
                             _: dict = Depends(require_roles("admin", "manager"))):
        q: dict = {}
        if agency_id:
            q["agency_id"] = agency_id
        if property_id:
            q["property_id"] = property_id
        items = await db.agency_contracts.find(q, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(1000)
        return {"items": items, "count": len(items)}

    @router.patch("/agency-contracts/{contract_id}")
    async def patch_contract(contract_id: str, body: dict,
                             _: dict = Depends(require_roles("admin", "manager"))):
        allowed = {"contract_rate", "currency", "commission_percent", "min_stay",
                   "max_stay", "valid_from", "valid_to", "blackout_dates",
                   "promotion", "notes", "is_active", "room_type_id"}
        update = {k: v for k, v in body.items() if k in allowed}
        if not update:
            raise HTTPException(400, "Nothing to update")
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.agency_contracts.update_one({"id": contract_id}, {"$set": update})
        if not r.matched_count:
            raise HTTPException(404, "Contract not found")
        return {"ok": True, "modified": r.modified_count}

    @router.delete("/agency-contracts/{contract_id}")
    async def delete_contract(contract_id: str,
                              _: dict = Depends(require_roles("admin"))):
        r = await db.agency_contracts.delete_one({"id": contract_id})
        if not r.deleted_count:
            raise HTTPException(404, "Contract not found")
        return {"ok": True, "deleted": r.deleted_count}

    return router
