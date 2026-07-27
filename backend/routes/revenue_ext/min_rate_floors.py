"""
Çift Minimum + Çift Maksimum Fiyat Koruması (Dual Rate Guards).
Oda tipi bazında:
- standart minimum + yakın tarih minimumu (girişe N gün kala geçiş)
- standart maksimum + etkinlik günü maksimumu (event robotu talep skoru >= eşik
  olan günlerde yüksek tavan devreye girer)
AI pricing ve Strateji Robotu bu sınırların dışına fiyat yazamaz.
Collection: min_rate_floors {property_id, room_type_id|"all", standard_min_rate,
  near_term_min_rate, near_term_window_days, standard_max_rate, event_max_rate,
  event_score_threshold, enabled}
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date as ddate, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def _pick_rule(rules: list, room_type_id: Optional[str]):
    if room_type_id:
        for r in rules:
            if r.get("room_type_id") == room_type_id:
                return r
    for r in rules:
        if r.get("room_type_id") == "all":
            return r
    return None


def _floor_for(rule: Dict, days_out: int) -> Dict:
    window = int(rule.get("near_term_window_days", 7) or 7)
    near = rule.get("near_term_min_rate")
    std = rule.get("standard_min_rate")
    if days_out <= window and near:
        return {"floor": float(near), "mode": "near_term", "window_days": window}
    if std:
        return {"floor": float(std), "mode": "standard", "window_days": window}
    return {"floor": None, "mode": None, "window_days": window}


def _ceiling_for(rule: Dict, is_event_day: bool) -> Dict:
    ev_max = rule.get("event_max_rate")
    std_max = rule.get("standard_max_rate")
    if is_event_day and ev_max:
        return {"ceiling": float(ev_max), "ceiling_mode": "event"}
    if std_max:
        return {"ceiling": float(std_max), "ceiling_mode": "standard"}
    return {"ceiling": None, "ceiling_mode": None}


async def _event_days(db, pid: str, date_min: str, date_max: str, threshold: int) -> set:
    """Talep skoru eşiği aşan etkinlik günleri (event robotundan)."""
    days = set()
    async for e in db.market_events.find(
            {"property_id": {"$in": [pid, "all"]},
             "date": {"$gte": date_min, "$lte": date_max},
             "hotel_demand_score": {"$gte": threshold}},
            {"_id": 0, "date": 1, "end_date": 1}):
        try:
            s = ddate.fromisoformat(e["date"][:10])
            en = ddate.fromisoformat((e.get("end_date") or e["date"])[:10])
        except Exception:
            continue
        d = s
        while d <= en:
            days.add(d.isoformat())
            d += timedelta(days=1)
    return days


async def effective_bounds_map(db, pid: str, dates: list,
                               room_type_id: Optional[str] = None) -> Dict[str, Dict]:
    """Çok tarih için taban+tavan haritası. {date: {floor, mode, ceiling, ceiling_mode, is_event_day}}"""
    rules = await db.min_rate_floors.find(
        {"property_id": pid, "enabled": True}, {"_id": 0}).to_list(50)
    rule = _pick_rule(rules, room_type_id)
    if not rule:
        return {}
    valid = sorted(d[:10] for d in dates if d)
    if not valid:
        return {}
    threshold = int(rule.get("event_score_threshold", 40) or 40)
    ev_days = set()
    if rule.get("event_max_rate"):
        ev_days = await _event_days(db, pid, valid[0], valid[-1], threshold)
    today = ddate.today()
    out = {}
    for d in dates:
        try:
            days_out = (ddate.fromisoformat(d[:10]) - today).days
        except Exception:
            continue
        is_ev = d[:10] in ev_days
        out[d] = {**_floor_for(rule, days_out), **_ceiling_for(rule, is_ev),
                  "is_event_day": is_ev}
    return out


async def get_effective_bounds(db, pid: str, date_str: str,
                               room_type_id: Optional[str] = None) -> Dict:
    m = await effective_bounds_map(db, pid, [date_str], room_type_id)
    return m.get(date_str, {"floor": None, "mode": None, "ceiling": None,
                            "ceiling_mode": None, "is_event_day": False})


# Geriye dönük uyumluluk (eski çağrılar)
async def get_effective_min_rate(db, pid: str, date_str: str,
                                 room_type_id: Optional[str] = None) -> Dict:
    return await get_effective_bounds(db, pid, date_str, room_type_id)


async def effective_min_rate_map(db, pid: str, dates: list,
                                 room_type_id: Optional[str] = None) -> Dict[str, Dict]:
    return await effective_bounds_map(db, pid, dates, room_type_id)


def clamp_to_bounds(rate: float, bounds: Dict) -> Dict:
    """Fiyatı taban/tavan sınırına kırpar. {rate, clamped, reason}"""
    if bounds.get("floor") and rate < bounds["floor"]:
        label = "yakın tarih min." if bounds.get("mode") == "near_term" else "standart min."
        return {"rate": bounds["floor"], "clamped": True, "reason": label}
    if bounds.get("ceiling") and rate > bounds["ceiling"]:
        label = "etkinlik maks." if bounds.get("ceiling_mode") == "event" else "standart maks."
        return {"rate": bounds["ceiling"], "clamped": True, "reason": label}
    return {"rate": rate, "clamped": False, "reason": None}


def create_min_rate_floors_router(db, require_roles):
    router = APIRouter(prefix="/min-rates")

    @router.get("/{pid}")
    async def list_rules(pid: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        rules = await db.min_rate_floors.find({"property_id": pid}, {"_id": 0}).to_list(50)
        room_types = await db.room_types.find(
            {"property_id": pid}, {"_id": 0, "id": 1, "name": 1, "base_rate": 1}).to_list(50)
        return {"rules": rules, "room_types": room_types}

    @router.put("/{pid}/{room_type_id}")
    async def upsert_rule(pid: str, room_type_id: str, payload: Dict,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        std = payload.get("standard_min_rate")
        near = payload.get("near_term_min_rate")
        std_max = payload.get("standard_max_rate")
        ev_max = payload.get("event_max_rate")
        window = int(payload.get("near_term_window_days", 7) or 7)
        threshold = int(payload.get("event_score_threshold", 40) or 40)
        if window < 1 or window > 60:
            raise HTTPException(400, "Pencere 1-60 gün arasında olmalı")
        if threshold < 1 or threshold > 100:
            raise HTTPException(400, "Etkinlik skoru eşiği 1-100 arasında olmalı")
        for label, v in [("Standart minimum", std), ("Yakın tarih minimumu", near),
                         ("Standart maksimum", std_max), ("Etkinlik maksimumu", ev_max)]:
            if v is not None and float(v) <= 0:
                raise HTTPException(400, f"{label} 0'dan büyük olmalı")
        if std and near and float(near) > float(std):
            raise HTTPException(400, "Yakın tarih minimumu standart minimumdan büyük olamaz")
        if std_max and ev_max and float(ev_max) < float(std_max):
            raise HTTPException(400, "Etkinlik maksimumu standart maksimumdan küçük olamaz")
        if std and std_max and float(std_max) < float(std):
            raise HTTPException(400, "Maksimum, minimumdan küçük olamaz")
        doc = {
            "property_id": pid, "room_type_id": room_type_id,
            "standard_min_rate": round(float(std), 2) if std else None,
            "near_term_min_rate": round(float(near), 2) if near else None,
            "near_term_window_days": window,
            "standard_max_rate": round(float(std_max), 2) if std_max else None,
            "event_max_rate": round(float(ev_max), 2) if ev_max else None,
            "event_score_threshold": threshold,
            "enabled": bool(payload.get("enabled", True)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.get("email", ""),
        }
        await db.min_rate_floors.update_one(
            {"property_id": pid, "room_type_id": room_type_id}, {"$set": doc}, upsert=True)
        return doc

    @router.delete("/{pid}/{room_type_id}")
    async def delete_rule(pid: str, room_type_id: str,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.min_rate_floors.delete_one({"property_id": pid, "room_type_id": room_type_id})
        if res.deleted_count == 0:
            raise HTTPException(404, "Kural bulunamadı")
        return {"ok": True}

    @router.get("/{pid}/preview/{room_type_id}")
    async def preview(pid: str, room_type_id: str, days: int = 14,
                      current_user: dict = Depends(require_roles("admin", "manager"))):
        """Önümüzdeki N gün hangi taban/tavan aktif — geçiş ve etkinlik günleri görünür."""
        days = max(1, min(days, 30))
        dates = [(ddate.today() + timedelta(days=i)).isoformat() for i in range(days)]
        fmap = await effective_bounds_map(db, pid, dates, room_type_id if room_type_id != "all" else None)
        return {"days": [{"date": d, **(fmap.get(d) or {"floor": None, "mode": None,
                                                        "ceiling": None, "ceiling_mode": None,
                                                        "is_event_day": False})} for d in dates]}

    return router
