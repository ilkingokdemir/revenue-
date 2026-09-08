"""Booking Engine dönüşüm paketi: fiyat takvimi, oran planları, çoklu oda sepeti, esnek tarih önerisi."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta, date as _date
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import Booking

DEFAULT_PLANS = [
    {"code": "flexible", "name": "Flexible Rate", "name_tr": "Esnek Fiyat", "name_de": "Flexibler Tarif",
     "adjustment_type": "pct", "adjustment_value": 0, "cancellation_type": "free", "free_cancel_hours": 48,
     "includes": [], "deposit_pct": 0, "sort_order": 1, "is_default": True, "badge": ""},
    {"code": "non_refundable", "name": "Non-refundable", "name_tr": "İade Edilmez", "name_de": "Nicht erstattbar",
     "adjustment_type": "pct", "adjustment_value": -10, "cancellation_type": "non_refundable", "free_cancel_hours": 0,
     "includes": [], "deposit_pct": 100, "sort_order": 2, "is_default": False, "badge": "save"},
    {"code": "breakfast", "name": "Breakfast Included", "name_tr": "Kahvaltı Dahil", "name_de": "Frühstück inklusive",
     "adjustment_type": "fixed_per_night", "adjustment_value": 15, "cancellation_type": "free", "free_cancel_hours": 48,
     "includes": ["breakfast"], "deposit_pct": 0, "sort_order": 3, "is_default": False, "badge": "popular"},
]


class CartItem(BaseModel):
    room_type_id: str
    rate_plan_id: str = ""
    qty: int = 1
    extra_beds: int = 0
    children_ages: List[int] = Field(default_factory=list)


class MultiReserve(BaseModel):
    property_id: str
    guest_name: str
    guest_email: str
    guest_phone: str = ""
    check_in: str
    check_out: str
    adults: int = 2
    children: int = 0
    special_requests: str = ""
    damage_waiver: bool = False
    promo_code: str = ""
    gift_card_code: str = ""
    source: str = ""
    loyalty_email: str = ""
    agent_code: str = ""
    flex_cancel: bool = False
    payment_method: str = ""
    day_use: bool = False
    items: List[CartItem] = Field(default_factory=list)


SOURCES = {"booking_engine", "google_hotel_ads", "embed", "website", "metasearch", "exit_intent"}


def plan_night_price(base: float, plan: Optional[dict]) -> float:
    if not plan:
        return float(base)
    v = float(plan.get("adjustment_value") or 0)
    if plan.get("adjustment_type") == "fixed_per_night":
        return round(float(base) + v, 2)
    return round(float(base) * (1 + v / 100.0), 2)


def create_be_conversion_router(db, require_roles):
    router = APIRouter()
    ROLES = ("admin", "manager")

    async def _plans(pid: str, seed: bool = True) -> List[dict]:
        rows = await db.be_rate_plans.find({"property_id": pid}, {"_id": 0}).sort("sort_order", 1).to_list(30)
        if not rows and seed:
            now = datetime.now(timezone.utc).isoformat()
            rows = [{**p, "id": str(uuid.uuid4()), "property_id": pid, "is_active": True, "created_at": now} for p in DEFAULT_PLANS]
            await db.be_rate_plans.insert_many([dict(r) for r in rows])
            rows = [{k: v for k, v in r.items() if k != "_id"} for r in rows]
        return rows

    async def _overrides(pid: str, start: str, end: str) -> Dict[tuple, float]:
        out = {}
        async for ov in db.rate_overrides.find(
                {"property_id": pid, "date": {"$gte": start, "$lte": end}, "custom_rate": {"$gt": 0}},
                {"_id": 0, "date": 1, "room_type_id": 1, "custom_rate": 1}):
            out[(ov.get("room_type_id") or "", ov["date"])] = float(ov["custom_rate"])
        return out

    def _rate(ovs: dict, rt_id: str, d: str, base: float) -> float:
        return ovs.get((rt_id, d)) or ovs.get(("", d)) or float(base or 0)

    async def _booked_per_day(pid: str, room_ids: List[str], start: str, end: str) -> Dict[tuple, int]:
        """(room_type_id, date) → dolu oda sayısı."""
        out: Dict[tuple, int] = {}
        async for b in db.bookings.find(
                {"property_id": pid, "room_type_id": {"$in": room_ids}, "status": {"$nin": ["cancelled"]},
                 "check_in": {"$lt": end}, "check_out": {"$gt": start}},
                {"_id": 0, "room_type_id": 1, "check_in": 1, "check_out": 1, "rooms": 1}):
            try:
                ci = _date.fromisoformat(b["check_in"][:10]); co = _date.fromisoformat(b["check_out"][:10])
            except Exception:
                continue
            d = max(ci, _date.fromisoformat(start))
            stop = min(co, _date.fromisoformat(end) + timedelta(days=1))
            while d < stop:
                k = (b["room_type_id"], d.isoformat())
                out[k] = out.get(k, 0) + int(b.get("rooms") or 1)
                d += timedelta(days=1)
        return out

    # ---------------- FİYAT TAKVİMİ ----------------
    @router.get("/booking/price-calendar/{pid}")
    async def price_calendar(pid: str, month: str = "", adults: int = 2):
        """Public: ay bazında gün gün en düşük fiyat + müsaitlik (Mews/Cloudbeds paritesi)."""
        try:
            y, m = (int(x) for x in (month or datetime.now(timezone.utc).strftime("%Y-%m")).split("-"))
            first = _date(y, m, 1)
        except Exception:
            raise HTTPException(422, "month=YYYY-MM")
        last = (_date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1))
        rooms = await db.room_types.find({"property_id": pid, "is_active": True}, {"_id": 0, "id": 1, "base_price": 1, "total_rooms": 1, "max_guests": 1}).to_list(50)
        if not rooms:
            return {"month": f"{y:04d}-{m:02d}", "days": [], "currency": "GBP"}
        ids = [r["id"] for r in rooms]
        ovs, booked = await asyncio.gather(_overrides(pid, first.isoformat(), last.isoformat()),
                                           _booked_per_day(pid, ids, first.isoformat(), last.isoformat()))
        prop = await db.properties.find_one({"id": pid}, {"_id": 0, "currency": 1}) or {}
        today = datetime.now(timezone.utc).date()
        days, prices = [], []
        d = first
        while d <= last:
            iso = d.isoformat()
            best, avail_total = None, 0
            for r in rooms:
                if adults and int(r.get("max_guests") or 99) < adults:
                    continue
                left = max(0, int(r.get("total_rooms") or 1) - booked.get((r["id"], iso), 0))
                avail_total += left
                if left > 0:
                    p = _rate(ovs, r["id"], iso, r.get("base_price", 0))
                    best = p if best is None or p < best else best
            past = d < today
            days.append({"date": iso, "min_price": None if past else best, "available": 0 if past else avail_total,
                         "sold_out": (not past) and avail_total == 0, "past": past, "weekend": d.weekday() >= 4})
            if best is not None and not past:
                prices.append(best)
            d += timedelta(days=1)
        floor_p = min(prices) if prices else None
        has_variance = bool(prices) and max(prices) > floor_p
        for x in days:
            x["is_cheapest"] = has_variance and x["min_price"] == floor_p
        return {"month": f"{y:04d}-{m:02d}", "days": days, "currency": prop.get("currency", "GBP"),
                "min_price": floor_p, "max_price": max(prices) if prices else None}

    # ---------------- ORAN PLANLARI ----------------
    @router.get("/booking/rate-plans/{pid}")
    async def public_rate_plans(pid: str):
        rows = await _plans(pid)
        return [r for r in rows if r.get("is_active", True)]

    @router.get("/be-rate-plans/{pid}")
    async def admin_rate_plans(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await _plans(pid)

    @router.post("/be-rate-plans/{pid}")
    async def create_plan(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        if not (data.get("name") or "").strip():
            raise HTTPException(422, "name zorunlu")
        doc = {"id": str(uuid.uuid4()), "property_id": pid, "code": (data.get("code") or "custom")[:30],
               "name": data["name"][:60], "name_tr": (data.get("name_tr") or data["name"])[:60], "name_de": (data.get("name_de") or data["name"])[:60],
               "adjustment_type": data.get("adjustment_type") if data.get("adjustment_type") in ("pct", "fixed_per_night") else "pct",
               "adjustment_value": float(data.get("adjustment_value") or 0),
               "cancellation_type": data.get("cancellation_type") if data.get("cancellation_type") in ("free", "non_refundable") else "free",
               "free_cancel_hours": int(data.get("free_cancel_hours") or 0),
               "includes": [str(x) for x in (data.get("includes") or [])][:10],
               "deposit_pct": max(0, min(100, int(data.get("deposit_pct") or 0))),
               "sort_order": int(data.get("sort_order") or 99), "is_default": bool(data.get("is_default")),
               "badge": (data.get("badge") or "")[:20], "is_active": True,
               "created_at": datetime.now(timezone.utc).isoformat()}
        await db.be_rate_plans.insert_one(dict(doc))
        return doc

    @router.put("/be-rate-plans/{pid}/{plan_id}")
    async def update_plan(pid: str, plan_id: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        allowed = {"name", "name_tr", "name_de", "adjustment_type", "adjustment_value", "cancellation_type",
                   "free_cancel_hours", "includes", "deposit_pct", "sort_order", "is_default", "is_active", "badge"}
        upd = {k: v for k, v in data.items() if k in allowed}
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = await db.be_rate_plans.update_one({"id": plan_id, "property_id": pid}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(404, "Plan yok")
        return await db.be_rate_plans.find_one({"id": plan_id}, {"_id": 0})

    @router.delete("/be-rate-plans/{pid}/{plan_id}")
    async def delete_plan(pid: str, plan_id: str, _u: dict = Depends(require_roles(*ROLES))):
        await db.be_rate_plans.delete_one({"id": plan_id, "property_id": pid})
        return {"ok": True}

    # ---------------- ÜYE FİYATI / VERGİ AYARLARI ----------------
    @router.post("/booking/member-rate")
    async def member_rate(data: Dict):
        email = (data.get("email") or "").lower().strip()
        if "@" not in email:
            raise HTTPException(422, "email")
        mem = await db.loyalty_members.find_one({"email": email}, {"_id": 0, "tier": 1, "name": 1}) or await db.guest_profiles.find_one({"email": email, "loyalty_tier": {"$exists": True}}, {"_id": 0, "loyalty_tier": 1, "name": 1})
        if not mem:
            return {"member": False, "discount_pct": 0}
        tier = (mem.get("tier") or mem.get("loyalty_tier") or "bronze").lower()
        return {"member": True, "tier": tier, "discount_pct": {"bronze": 5, "silver": 8, "gold": 10, "platinum": 15}.get(tier, 5), "name": mem.get("name", "")}

    @router.get("/booking/pricing-settings/{pid}")
    async def pricing_settings_get(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        p = await db.properties.find_one({"id": pid}, {"_id": 0, "vat_rate": 1, "city_tax_per_night": 1, "child_policy": 1, "extra_bed_price": 1}) or {}
        return {"vat_rate": p.get("vat_rate") or 0, "city_tax_per_night": p.get("city_tax_per_night") or 0, "extra_bed_price": p.get("extra_bed_price") or 0,
                "child_policy": p.get("child_policy") or {"free_under_age": 3, "child_price_per_night": 0, "max_child_age": 12}}

    @router.put("/booking/pricing-settings/{pid}")
    async def pricing_settings_put(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        cp = data.get("child_policy") or {}
        upd = {"vat_rate": max(0.0, min(50.0, float(data.get("vat_rate") or 0))), "city_tax_per_night": max(0.0, float(data.get("city_tax_per_night") or 0)),
               "extra_bed_price": max(0.0, float(data.get("extra_bed_price") or 0)),
               "child_policy": {"free_under_age": int(cp.get("free_under_age") or 0), "child_price_per_night": max(0.0, float(cp.get("child_price_per_night") or 0)), "max_child_age": int(cp.get("max_child_age") or 12)}}
        await db.properties.update_one({"id": pid}, {"$set": upd})
        return {"ok": True, **upd}

    # ---------------- ÖDEME SONRASI UPSELL ----------------
    @router.post("/booking/{booking_ref}/add-upsell")
    async def add_upsell(booking_ref: str, data: Dict):
        """Public: onay ekranında tek dokunuşla ek hizmet (kahvaltı, geç çıkış…) ekle; ödendiyse bakiye olarak kaydedilir."""
        b = await db.bookings.find_one({"booking_ref": booking_ref, "guest_email": (data.get("guest_email") or "").strip()}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Rezervasyon bulunamadı")
        item = await db.upsell_items.find_one({"id": data.get("upsell_id"), "property_id": b["property_id"]}, {"_id": 0})
        if not item:
            raise HTTPException(404, "Ek hizmet yok")
        if any(u.get("id") == item["id"] for u in (b.get("post_upsells") or [])):
            return {"ok": True, "already": True, "balance_due": b.get("balance_due", 0), "upsell_unpaid_total": round(sum(float(u.get("price") or 0) for u in (b.get("post_upsells") or []) if not u.get("paid")), 2)}
        nights = int(b.get("nights") or 1)
        price = float(item.get("price") or 0) * (nights if item.get("price_type") == "per_night" else 1)
        new_total = round(float(b.get("cart_total") or b.get("total_price") or 0) + price, 2)
        bal = round(float(b.get("balance_due") or 0) + price, 2) if b.get("payment_status") == "paid" else 0
        upd = {"total_price": round(float(b.get("total_price") or 0) + price, 2), "post_upsell_total": round(float(b.get("post_upsell_total") or 0) + price, 2)}
        if b.get("cart_total") is not None:
            upd["cart_total"] = new_total
        if b.get("payment_status") == "paid":
            upd["balance_due"] = bal
        await db.bookings.update_one({"id": b["id"]}, {"$set": upd, "$push": {"post_upsells": {"id": item["id"], "name": item.get("name"), "price": price, "added_at": datetime.now(timezone.utc).isoformat(), "source": "post_payment", "paid": False}}})
        unpaid_total = round(sum(float(u.get("price") or 0) for u in (b.get("post_upsells") or []) if not u.get("paid")) + price, 2)
        return {"ok": True, "added": {"id": item["id"], "name": item.get("name"), "price": price}, "new_total": new_total, "balance_due": bal, "upsell_unpaid_total": unpaid_total}

    # ---------------- ESNEK TARİH ----------------
    @router.get("/booking/flex-dates/{pid}")
    async def flex_dates(pid: str, check_in: str, check_out: str, adults: int = 2, room_type_id: str = "", span: int = 3):
        """Public: ±span gün kaydırılmış alternatifler ve tasarruf oranı."""
        try:
            ci = _date.fromisoformat(check_in); co = _date.fromisoformat(check_out)
        except Exception:
            raise HTTPException(422, "check_in/check_out YYYY-MM-DD")
        nights = max(1, (co - ci).days)
        span = max(1, min(7, span))
        q = {"property_id": pid, "is_active": True}
        if room_type_id:
            q["id"] = room_type_id
        rooms = await db.room_types.find(q, {"_id": 0, "id": 1, "base_price": 1, "total_rooms": 1, "max_guests": 1, "name": 1}).to_list(50)
        if not rooms:
            return {"nights": nights, "current": None, "alternatives": []}
        start = ci - timedelta(days=span); end = co + timedelta(days=span)
        ids = [r["id"] for r in rooms]
        ovs, booked = await asyncio.gather(_overrides(pid, start.isoformat(), end.isoformat()),
                                           _booked_per_day(pid, ids, start.isoformat(), end.isoformat()))
        today = datetime.now(timezone.utc).date()

        def total_for(s: _date):
            best = None
            for r in rooms:
                if adults and int(r.get("max_guests") or 99) < adults:
                    continue
                tot, ok = 0.0, True
                for n in range(nights):
                    d = (s + timedelta(days=n)).isoformat()
                    if int(r.get("total_rooms") or 1) - booked.get((r["id"], d), 0) <= 0:
                        ok = False; break
                    tot += _rate(ovs, r["id"], d, r.get("base_price", 0))
                if ok and (best is None or tot < best["total"]):
                    best = {"total": round(tot, 2), "room_type_id": r["id"], "room_name": r.get("name", "")}
            return best

        current = total_for(ci)
        alts = []
        for off in range(-span, span + 1):
            if off == 0:
                continue
            s = ci + timedelta(days=off)
            if s < today:
                continue
            b = total_for(s)
            if not b:
                continue
            saving = round(current["total"] - b["total"], 2) if current else 0
            alts.append({"offset": off, "check_in": s.isoformat(), "check_out": (s + timedelta(days=nights)).isoformat(),
                         **b, "saving": saving,
                         "saving_pct": round(saving / current["total"] * 100, 1) if current and current["total"] else 0})
        alts.sort(key=lambda a: a["total"])
        return {"nights": nights, "current": current, "alternatives": alts[:6],
                "best": alts[0] if alts and (not current or alts[0]["total"] < current["total"]) else None}

    # ---------------- ÇOKLU ODA SEPETİ ----------------
    @router.post("/booking/reserve-multi")
    async def reserve_multi(data: MultiReserve):
        """Public: tek işlemde birden fazla oda tipi / oran planı. Her satır ayrı booking, ortak cart_ref."""
        if not data.items:
            raise HTTPException(422, "Sepet boş")
        try:
            ci = _date.fromisoformat(data.check_in); co = _date.fromisoformat(data.check_out)
        except Exception:
            raise HTTPException(422, "Geçersiz tarih")
        nights = max(1, (co - ci).days)
        from routes.pms.widget_pricing import check_los_restrictions
        los = await check_los_restrictions(db, data.property_id, data.check_in, data.check_out)
        if los:
            raise HTTPException(400, los.get("message_tr") or los.get("message") or "Bu tarihler için minimum konaklama kuralı geçerli")
        plans = {p["id"]: p for p in await _plans(data.property_id)}
        ovs = await _overrides(data.property_id, data.check_in, data.check_out)
        prop = await db.properties.find_one({"id": data.property_id}, {"_id": 0, "currency": 1, "name": 1, "vat_rate": 1, "city_tax_per_night": 1, "child_policy": 1, "extra_bed_price": 1}) or {}
        currency = prop.get("currency") or "GBP"
        child_policy = prop.get("child_policy") or {}
        member_pct = 0.0
        if data.loyalty_email:
            mem = await db.loyalty_members.find_one({"email": data.loyalty_email.lower().strip()}, {"_id": 0, "tier": 1}) or await db.guest_profiles.find_one({"email": data.loyalty_email.lower().strip(), "loyalty_tier": {"$exists": True}}, {"_id": 0, "loyalty_tier": 1})
            if mem:
                tier = (mem.get("tier") or mem.get("loyalty_tier") or "").lower()
                member_pct = {"bronze": 5, "silver": 8, "gold": 10, "platinum": 15}.get(tier, 5)
        dw_cfg = None
        if data.damage_waiver:
            dw_cfg = await db.damage_protection_config.find_one({"property_id": data.property_id, "enabled": True}, {"_id": 0})

        # Müsaitlik + fiyat
        lines = []
        for it in data.items:
            room = await db.room_types.find_one({"id": it.room_type_id, "is_active": True}, {"_id": 0})
            if not room:
                raise HTTPException(404, f"Oda tipi bulunamadı: {it.room_type_id}")
            cnt = await db.bookings.count_documents({"room_type_id": it.room_type_id, "status": {"$nin": ["cancelled"]},
                                                     "check_in": {"$lt": data.check_out}, "check_out": {"$gt": data.check_in}})
            want = sum(x.qty for x in data.items if x.room_type_id == it.room_type_id)
            if int(room.get("total_rooms") or 1) - cnt < want:
                raise HTTPException(400, f"{room.get('name', 'Oda')} için yeterli müsaitlik yok")
            plan = plans.get(it.rate_plan_id) or next((p for p in plans.values() if p.get("is_default")), None)
            nightly = sum(plan_night_price(_rate(ovs, room["id"], (ci + timedelta(days=n)).isoformat(), room.get("base_price", 0)), plan)
                          for n in range(nights))
            if member_pct:
                nightly = round(nightly * (1 - member_pct / 100.0), 2)
            extra_bed_total = round(float(room.get("extra_bed_price") or prop.get("extra_bed_price") or 0) * nights * max(0, it.extra_beds), 2)
            child_total = 0.0
            for age in it.children_ages:
                free_under = int(child_policy.get("free_under_age") or 0)
                if age < free_under:
                    continue
                child_total += float(child_policy.get("child_price_per_night") or 0) * nights
            line_total = round(nightly * max(1, it.qty) + extra_bed_total + child_total, 2)
            if dw_cfg:
                line_total += round(float(dw_cfg.get("fee_per_night", 0) or 0) * nights * it.qty, 2)
            lines.append({"room": room, "plan": plan, "qty": max(1, it.qty), "total": line_total, "extra_beds": it.extra_beds, "children_ages": it.children_ages, "extra_bed_total": extra_bed_total, "child_total": child_total})

        subtotal = round(sum(l["total"] for l in lines), 2)
        from routes.pms.be_gaps import get_be_settings, los_discount_pct
        be_cfg = await get_be_settings(db, data.property_id)
        extra_adults = max(0, int(data.adults or 0) - int(be_cfg.get("base_occupancy") or 2) * sum(l["qty"] for l in lines))
        extra_adult_total = round(extra_adults * float(be_cfg.get("extra_adult_per_night") or 0) * nights, 2)
        los_pct = los_discount_pct(be_cfg, nights)
        los_discount = round(subtotal * los_pct / 100, 2)
        agent_discount = 0.0; agent_info = None
        if data.agent_code and be_cfg.get("agent_code_enabled", True):
            ag = await db.travel_agents.find_one({"property_id": data.property_id, "$or": [{"code": data.agent_code.strip().upper()}, {"agent_code": data.agent_code.strip().upper()}], "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1, "negotiated_discount_pct": 1})
            if ag:
                agent_discount = round(subtotal * float(ag.get("negotiated_discount_pct") or 0) / 100, 2)
                agent_info = {"agent_id": ag.get("id"), "agent_name": ag.get("name"), "agent_code": data.agent_code.strip().upper()}
        flex_fee = round(subtotal * float(be_cfg.get("flex_cancel_pct") or 0) / 100, 2) if (data.flex_cancel and be_cfg.get("flex_cancel_enabled", True)) else 0.0
        day_use_discount = 0.0
        if data.day_use and be_cfg.get("day_use_enabled"):
            day_use_discount = round(subtotal * (100 - float(be_cfg.get("day_use_pct") or 50)) / 100, 2)
            subtotal = round(subtotal - day_use_discount, 2)
        subtotal = round(subtotal + extra_adult_total - los_discount - agent_discount + flex_fee, 2)
        vat_rate = float(prop.get("vat_rate") or 0)
        city_tax = round(float(prop.get("city_tax_per_night") or 0) * nights * sum(l["qty"] for l in lines), 2)
        vat_included = round(subtotal - subtotal / (1 + vat_rate / 100.0), 2) if vat_rate else 0.0
        discount = 0.0
        promo_code = (data.promo_code or "").upper().strip()
        if promo_code:
            promo = await db.promo_codes.find_one({"code": promo_code, "is_active": True}, {"_id": 0})
            if promo and (not promo.get("property_id") or promo["property_id"] == data.property_id):
                discount = float(promo["discount_value"]) if promo.get("discount_type") == "fixed" else round(subtotal * float(promo["discount_value"]) / 100, 2)
                discount = min(discount, subtotal)
                await db.promo_codes.update_one({"code": promo_code}, {"$inc": {"used_count": 1}})
        cart_total = round(subtotal - discount + city_tax, 2)
        gift_applied, gift_code = 0.0, (data.gift_card_code or "").upper().strip()
        if gift_code and cart_total > 0:
            card = await db.gift_cards.find_one({"code": gift_code, "status": "active"}, {"_id": 0, "id": 1, "balance": 1, "property_id": 1, "expires_at": 1})
            if card and (not card.get("property_id") or card["property_id"] == data.property_id) and (not card.get("expires_at") or card["expires_at"] > datetime.now(timezone.utc).isoformat()):
                gift_applied = round(min(float(card["balance"]), cart_total), 2)
                new_bal = round(float(card["balance"]) - gift_applied, 2)
                await db.gift_cards.update_one({"id": card["id"]}, {"$set": {"balance": new_bal, "status": "redeemed" if new_bal <= 0.009 else "active"},
                                                                     "$push": {"redemption_log": {"at": datetime.now(timezone.utc).isoformat(), "by": "booking_engine", "amount": gift_applied, "note": "online checkout"}}})
        cart_total = round(cart_total - gift_applied, 2)
        source = data.source if data.source in SOURCES else "booking_engine"
        cart_ref = f"CART-{uuid.uuid4().hex[:8].upper()}"

        created = []
        for i, l in enumerate(lines):
            share = round((discount + gift_applied) * (l["total"] / subtotal), 2) if subtotal and (discount or gift_applied) else 0.0
            b = Booking(property_id=data.property_id, room_type_id=l["room"]["id"], guest_name=data.guest_name,
                        guest_email=data.guest_email, guest_phone=data.guest_phone, check_in=data.check_in,
                        check_out=data.check_out, adults=data.adults, children=data.children, rooms=l["qty"],
                        total_price=round(l["total"] - share, 2), currency=currency,
                        special_requests=data.special_requests, status="confirmed", payment_status="pending")
            doc = b.model_dump()
            if data.payment_method == "hold" and be_cfg.get("hold_enabled", True):
                from datetime import timedelta as _td
                doc.update({"status": "hold", "hold_expires_at": (datetime.now(timezone.utc) + _td(hours=int(be_cfg.get("hold_hours") or 24))).isoformat(), "payment_method": "hold"})
            if data.day_use and be_cfg.get("day_use_enabled"):
                doc.update({"day_use": True, "day_use_hours": f"{be_cfg.get('day_use_start')}-{be_cfg.get('day_use_end')}", "day_use_discount": day_use_discount, "check_out": doc["check_in"], "nights": 0})
            if i == 0:
                doc.update({"extra_adults": extra_adults, "extra_adult_total": extra_adult_total, "los_discount_pct": los_pct, "los_discount": los_discount,
                            "agent_discount": agent_discount, "flex_cancel": bool(flex_fee), "flex_cancel_fee": flex_fee, **(agent_info or {})})
                if flex_fee:
                    doc["cancellation_type"] = "free"; doc["cancellation_policy"] = "flex_cancel_addon"
            doc.update({"cart_ref": cart_ref, "cart_index": i, "source": source, "nights": nights,
                        "rate_plan_id": (l["plan"] or {}).get("id", ""), "rate_plan_code": (l["plan"] or {}).get("code", ""),
                        "rate_plan_name": (l["plan"] or {}).get("name", ""),
                        "cancellation_type": (l["plan"] or {}).get("cancellation_type", "free"),
                        "room_name": l["room"].get("name", ""), "extra_beds": l["extra_beds"], "children_ages": l["children_ages"],
                        "member_discount_pct": member_pct})
            if promo_code and discount:
                doc["promo_code"] = promo_code
            if dw_cfg:
                doc["damage_waiver"] = True
            await db.bookings.insert_one(dict(doc))
            created.append(doc)

        items = [{"booking_ref": c["booking_ref"], "room_name": c["room_name"], "rate_plan_name": c["rate_plan_name"],
                  "qty": c["rooms"], "total": c["total_price"]} for c in created]
        master = created[0]
        await db.bookings.update_one({"id": master["id"]}, {"$set": {
            "cart_master": True, "cart_total": cart_total, "cart_items": items, "cart_discount": discount,
            "gift_card_code": gift_code if gift_applied else "", "gift_card_applied": gift_applied,
            "tax_breakdown": {"vat_rate": vat_rate, "vat_included": vat_included, "city_tax": city_tax}, "member_discount_pct": member_pct,
            "cart_refs": [c["booking_ref"] for c in created]}})
        master.update({"cart_master": True, "cart_total": cart_total, "cart_items": items, "cart_discount": discount, "gift_card_applied": gift_applied})

        try:
            from routes.pms.guest_email_i18n import send_guest_confirmation
            asyncio.create_task(send_guest_confirmation(db, {**master, "total_price": cart_total}))
        except Exception:
            pass
        try:
            from routes.automation_rules import fire_event
            asyncio.create_task(fire_event(db, "booking_created", {
                "property_id": data.property_id, "booking_ref": master["booking_ref"], "guest_name": data.guest_name,
                "guest_email": data.guest_email, "room_number": items[0]["room_name"], "tags": [], "nights": nights,
                "total_price": cart_total, "source": source}))
        except Exception:
            pass
        return {**master, "total_price": cart_total, "subtotal": subtotal, "discount": discount, "nights": nights, "gift_card_applied": gift_applied,
                "tax_breakdown": {"vat_rate": vat_rate, "vat_included": vat_included, "city_tax": city_tax}, "member_discount_pct": member_pct,
                "manage_url": f"/guest-portal-v2?ref={master['booking_ref']}&email={data.guest_email}"}

    return router
