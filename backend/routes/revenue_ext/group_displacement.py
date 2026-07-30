"""
Group Displacement Analyzer — Duetto BlockBuster / Lybra paritesi.
Bir grup teklifi (tarih aralığı, oda sayısı, teklif fiyatı) için transient talebi
ne kadar yerinden edeceğini hesaplar ve kabul / pazarlık / red önerisi üretir.

Model (gece bazında):
- capacity = room_types.total_rooms toplamı
- booked   = o gece kesişen iptal-dışı rezervasyon odaları
- expected_pickup = geçmiş 8 aynı haftagünü ortalama doluluğa göre beklenen ek transient
- available_for_group = capacity - booked - expected_pickup
- displaced = max(0, istenen_oda - max(0, available_for_group))
- displacement_cost = displaced × transient ADR (o gecenin gerçek ADR'i, yoksa baz fiyat ort.)

Endpoints (/api/group-displacement/*):
- POST /analyze  → tam analiz + öneri (kaydeder)
- GET  /history/{property_id} → son analizler
"""
import uuid
from datetime import datetime, timedelta, timezone, date as ddate
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_perm


class AnalyzeIn(BaseModel):
    property_id: str
    check_in: str          # YYYY-MM-DD
    check_out: str
    rooms_requested: int
    offered_rate: float    # gecelik oda fiyatı
    group_name: Optional[str] = ""


def _d(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


async def _capacity(db, pid: str) -> int:
    total = 0
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1}):
        total += int(rt.get("total_rooms", 0) or 0)
    return max(total, 1)


async def _bookings(db, pid: str, start: ddate, end: ddate):
    return await db.bookings.find(
        {"property_id": pid, "status": {"$ne": "cancelled"},
         "check_in": {"$lt": (end + timedelta(days=1)).isoformat()},
         "check_out": {"$gt": (start - timedelta(days=60)).isoformat()}},
        {"_id": 0, "check_in": 1, "check_out": 1, "rooms": 1, "total_price": 1}
    ).to_list(20000)


def _rooms_on(bookings, night: ddate) -> int:
    n = 0
    iso = night.isoformat()
    for b in bookings:
        if (b.get("check_in") or "9999") <= iso < (b.get("check_out") or "0000"):
            n += int(b.get("rooms", 1) or 1)
    return n


def _adr_on(bookings, night: ddate, fallback: float) -> float:
    iso = night.isoformat()
    rates = []
    for b in bookings:
        ci, co = b.get("check_in"), b.get("check_out")
        if not ci or not co or not (ci <= iso < co):
            continue
        try:
            nights = max((_d(co) - _d(ci)).days, 1)
            rooms = int(b.get("rooms", 1) or 1)
            rates.append(float(b.get("total_price", 0) or 0) / nights / rooms)
        except (ValueError, ZeroDivisionError):
            continue
    rates = [r for r in rates if r > 0]
    return round(sum(rates) / len(rates), 2) if rates else fallback


async def compute_displacement(db, pid: str, start: ddate, end: ddate, rooms_requested: int, offered_rate: float):
    """Modül seviyesi: AI Auto-Quote gibi diğer modüller de kullanır."""
    capacity = await _capacity(db, pid)
    bookings = await _bookings(db, pid, start, end)
    base_prices = [float(rt.get("base_price", 0) or 0)
                   async for rt in db.room_types.find({"property_id": pid},
                                                      {"_id": 0, "base_price": 1})]
    base_prices = [p for p in base_prices if p > 0]
    fallback_adr = round(sum(base_prices) / len(base_prices), 2) if base_prices else 100.0

    nights = []
    total_displaced, total_disp_cost, total_group_rev = 0, 0.0, 0.0
    night = start
    while night < end:
        booked = _rooms_on(bookings, night)
        hist_occs = []
        for k in range(1, 9):
            past = night - timedelta(weeks=k)
            if past >= ddate.today():
                continue
            hist_occs.append(min(_rooms_on(bookings, past) / capacity, 1.0))
        hist_occ = sum(hist_occs) / len(hist_occs) if hist_occs else 0.5
        expected_final = max(booked, int(round(hist_occ * capacity)))
        expected_pickup = max(0, expected_final - booked)
        available = capacity - booked - expected_pickup
        displaced = max(0, rooms_requested - max(0, available))
        adr = _adr_on(bookings, night, fallback_adr)
        disp_cost = round(displaced * adr, 2)
        group_rev = round(rooms_requested * offered_rate, 2)
        nights.append({
            "date": night.isoformat(), "capacity": capacity, "booked": booked,
            "expected_pickup": expected_pickup, "available_for_group": max(0, available),
            "displaced_rooms": displaced, "transient_adr": adr,
            "displacement_cost": disp_cost, "group_revenue": group_rev,
            "net_value": round(group_rev - disp_cost, 2),
        })
        total_displaced += displaced
        total_disp_cost += disp_cost
        total_group_rev += group_rev
        night += timedelta(days=1)

    n_nights = len(nights)
    net_total = round(total_group_rev - total_disp_cost, 2)
    breakeven_rate = round(total_disp_cost / (rooms_requested * n_nights), 2) if n_nights else 0
    suggested_rate = round(max(breakeven_rate * 1.1, offered_rate), 2)

    if total_displaced == 0:
        recommendation, reason = "accept", "Hiç transient talep yerinden edilmiyor — grup net katkı sağlıyor."
    elif net_total > 0 and total_disp_cost / max(total_group_rev, 1) < 0.35:
        recommendation, reason = "accept", "Displacement maliyeti grup gelirinin %35'inin altında — kabul edilebilir."
    elif net_total > 0:
        recommendation, reason = "negotiate", f"Net pozitif ama displacement yüksek. Önerilen min fiyat: {suggested_rate}."
    else:
        recommendation, reason = "reject", f"Grup geliri displacement maliyetini karşılamıyor. En az {suggested_rate} istenmeli."

    return {
        "nights": n_nights, "fallback_adr": fallback_adr,
        "total_group_revenue": round(total_group_rev, 2),
        "total_displaced_rooms": total_displaced,
        "total_displacement_cost": round(total_disp_cost, 2),
        "net_value": net_total, "breakeven_rate": breakeven_rate,
        "suggested_min_rate": suggested_rate,
        "recommendation": recommendation, "reason": reason,
        "per_night": nights,
    }


def create_group_displacement_router(db):
    router = APIRouter(prefix="/group-displacement")

    @router.post("/analyze")
    async def analyze(body: AnalyzeIn,
                      current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        try:
            start, end = _d(body.check_in), _d(body.check_out)
        except ValueError:
            raise HTTPException(400, "Dates must be YYYY-MM-DD")
        if end <= start:
            raise HTTPException(400, "check_out must be after check_in")
        if (end - start).days > 30:
            raise HTTPException(400, "Max 30 nights")
        if body.rooms_requested < 1:
            raise HTTPException(400, "rooms_requested must be >= 1")

        computed = await compute_displacement(db, body.property_id, start, end, body.rooms_requested, body.offered_rate)
        result = {
            "id": str(uuid.uuid4()), "property_id": body.property_id,
            "group_name": body.group_name or "", "check_in": body.check_in,
            "check_out": body.check_out,
            "rooms_requested": body.rooms_requested, "offered_rate": body.offered_rate,
            **computed,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("email", ""),
        }
        await db.group_displacement_analyses.insert_one(dict(result))
        result.pop("_id", None)
        return result

    @router.get("/verdicts/{property_id}")
    async def verdicts(property_id: str,
                       current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        """Bekleyen grup talepleri için hızlı displacement kararları (liste rozetleri)."""
        requests = await db.group_bookings.find(
            {"property_id": property_id, "status": {"$in": ["pending", "quoted", None]}},
            {"_id": 0, "id": 1, "check_in": 1, "check_out": 1, "total_rooms": 1, "quoted_price": 1}
        ).to_list(100)
        out = {}
        for r in requests:
            try:
                start, end = _d(r["check_in"]), _d(r["check_out"])
                n_nights = (end - start).days
                rooms = int(r.get("total_rooms", 1) or 1)
                if n_nights < 1 or n_nights > 30 or rooms < 1:
                    continue
                quoted = float(r.get("quoted_price", 0) or 0)
                if quoted > 0:
                    rate, estimated = round(quoted / (rooms * n_nights), 2), False
                else:
                    rate, estimated = None, True
                computed = await compute_displacement(db, property_id, start, end, rooms, rate if rate else 0)
                if estimated:
                    rate = round(computed["fallback_adr"] * 0.8, 2)
                    computed = await compute_displacement(db, property_id, start, end, rooms, rate)
                out[r["id"]] = {
                    "recommendation": computed["recommendation"],
                    "net_value": computed["net_value"],
                    "displaced_rooms": computed["total_displaced_rooms"],
                    "suggested_min_rate": computed["suggested_min_rate"],
                    "assumed_rate": rate, "rate_estimated": estimated,
                    "reason": computed["reason"],
                }
            except (ValueError, KeyError, TypeError):
                continue
        return out

    @router.get("/history/{property_id}")
    async def history(property_id: str, limit: int = 10,
                      current_user: dict = Depends(require_perm("view_bookings", "edit_bookings", mode="any"))):
        return await db.group_displacement_analyses.find(
            {"property_id": property_id}, {"_id": 0, "per_night": 0}
        ).sort("created_at", -1).to_list(min(limit, 50))

    return router
