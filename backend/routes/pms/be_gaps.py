"""Booking engine gap-MVP: BE ayarları (doluluk/LOS/flex-cancel/hold), acente kodu, bekleme listesi, canlı FX."""
import uuid
from datetime import datetime, timezone, date as _date
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

DEFAULTS = {"base_occupancy": 2, "extra_adult_per_night": 0.0, "los_tiers": [{"min_nights": 7, "pct": 10}, {"min_nights": 28, "pct": 25}],
            "flex_cancel_pct": 8.0, "flex_cancel_enabled": True, "hold_hours": 24, "hold_enabled": True, "scarcity_threshold": 3,
            "waitlist_enabled": True, "agent_code_enabled": True, "long_stay_enabled": True}


async def get_be_settings(db, pid: str) -> dict:
    doc = await db.be_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULTS, **doc, "property_id": pid}


def los_discount_pct(settings: dict, nights: int) -> float:
    if not settings.get("long_stay_enabled"):
        return 0.0
    best = 0.0
    for t in settings.get("los_tiers") or []:
        try:
            if nights >= int(t.get("min_nights") or 0) and float(t.get("pct") or 0) > best:
                best = float(t["pct"])
        except (TypeError, ValueError):
            continue
    return best


def create_be_gaps_router(db, require_roles):
    router = APIRouter()

    @router.get("/booking/be-settings/{pid}")
    async def be_settings_public(pid: str):
        s = await get_be_settings(db, pid)
        return {k: s[k] for k in DEFAULTS} | {"property_id": pid}

    @router.put("/booking/be-settings/{pid}")
    async def be_settings_put(pid: str, data: Dict, _u: dict = Depends(require_roles("admin", "manager"))):
        cur = await get_be_settings(db, pid)
        upd = {"property_id": pid, "updated_at": datetime.now(timezone.utc).isoformat()}
        for k, v in DEFAULTS.items():
            if k in data:
                val = data[k]
                if isinstance(v, bool):
                    val = bool(val)
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    try:
                        val = float(val) if isinstance(v, float) else int(val)
                    except (TypeError, ValueError):
                        raise HTTPException(422, f"{k} sayı olmalı")
                    if val < 0 or (k.endswith("_pct") and val > 100):
                        raise HTTPException(422, f"{k} aralık dışı")
                elif k == "los_tiers":
                    val = [{"min_nights": int(t.get("min_nights") or 0), "pct": float(t.get("pct") or 0)} for t in (val or []) if isinstance(t, dict)][:6]
                upd[k] = val
        await db.be_settings.update_one({"property_id": pid}, {"$set": {**cur, **upd}}, upsert=True)
        return await get_be_settings(db, pid)

    # ---- acente / şirket kodu ----
    @router.post("/booking/agent-code/validate")
    async def agent_code_validate(data: Dict):
        pid = data.get("property_id") or ""
        code = str(data.get("code") or "").strip().upper()
        if not code:
            raise HTTPException(422, "Kod boş")
        ag = await db.travel_agents.find_one({"property_id": pid, "$or": [{"code": code}, {"agent_code": code}], "is_active": {"$ne": False}}, {"_id": 0})
        if not ag:
            raise HTTPException(404, "Kod bulunamadı veya pasif")
        return {"valid": True, "agent_id": ag.get("id"), "agent_name": ag.get("name") or ag.get("company"), "discount_pct": float(ag.get("negotiated_discount_pct") or 0),
                "type": ag.get("type") or "corporate", "billing": ag.get("billing_mode") or "guest_pays"}

    # ---- bekleme listesi ----
    @router.post("/booking/waitlist")
    async def waitlist_add(data: Dict):
        pid = data.get("property_id") or ""
        email = str(data.get("email") or "").strip().lower()
        if not pid or "@" not in email:
            raise HTTPException(422, "E-posta gerekli")
        try:
            ci = _date.fromisoformat(str(data.get("check_in"))); co = _date.fromisoformat(str(data.get("check_out")))
        except (TypeError, ValueError):
            raise HTTPException(422, "Tarih hatalı")
        if co <= ci:
            raise HTTPException(422, "Çıkış girişten sonra olmalı")
        doc = {"id": str(uuid.uuid4()), "property_id": pid, "email": email, "name": str(data.get("name") or "")[:120], "check_in": ci.isoformat(), "check_out": co.isoformat(),
               "adults": int(data.get("adults") or 2), "room_type_id": str(data.get("room_type_id") or ""), "lang": str(data.get("lang") or "en")[:2],
               "status": "waiting", "created_at": datetime.now(timezone.utc).isoformat()}
        exists = await db.be_waitlist.find_one({"property_id": pid, "email": email, "check_in": doc["check_in"], "check_out": doc["check_out"], "status": "waiting"}, {"_id": 0, "id": 1})
        if exists:
            return {"ok": True, "already": True, "id": exists["id"]}
        await db.be_waitlist.insert_one(dict(doc))
        try:
            await db.lost_demand.insert_one({"id": str(uuid.uuid4()), "property_id": pid, "check_in": doc["check_in"], "check_out": doc["check_out"], "reason": "no_availability",
                                             "source": "be_waitlist", "guests": doc["adults"], "created_at": doc["created_at"]})
        except Exception:
            pass
        return {"ok": True, "id": doc["id"]}

    @router.get("/booking/waitlist/{pid}")
    async def waitlist_list(pid: str, _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.be_waitlist.find({"property_id": pid}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        return {"items": rows, "waiting": sum(1 for r in rows if r["status"] == "waiting"), "notified": sum(1 for r in rows if r["status"] == "notified")}

    # ---- canlı FX (currency_fx modülünden, public) ----
    @router.get("/booking/fx-rates")
    async def fx_public(base: str = "GBP"):
        rows = await db.fx_rates.find({"code": {"$exists": True}}, {"_id": 0, "code": 1, "rate": 1, "rate_to_base": 1, "updated_at": 1, "as_of": 1}).sort("code", 1).to_list(500)
        latest: Dict[str, dict] = {}
        for r in rows:
            latest[r["code"]] = r
        out = {}
        for code, r in latest.items():
            v = r.get("rate_to_base")
            if v and float(v) > 0:
                out[code] = round(1 / float(v), 6)
        return {"base": base, "rates": out, "count": len(out), "source": "currency_fx" if out else "static"}

    # ---- hold ----
    @router.get("/booking/holds/{pid}")
    async def holds_list(pid: str, _u: dict = Depends(require_roles("admin", "manager", "receptionist"))):
        rows = await db.bookings.find({"property_id": pid, "status": "hold"}, {"_id": 0, "booking_ref": 1, "guest_name": 1, "guest_email": 1, "check_in": 1, "check_out": 1, "total_price": 1, "hold_expires_at": 1}).sort("hold_expires_at", 1).to_list(200)
        return {"items": rows}

    return router
