"""
Çift Minimum Fiyat Koruması (Dual Min-Rate Floors).
Oda tipi bazında iki taban fiyat: standart minimum + yakın tarih minimumu.
Girişe near_term_window_days (vars. 7) gün kala standart taban devre dışı kalır,
yakın tarih tabanı devreye girer. AI pricing ve Strateji Robotu fiyat yazarken
bu tabanların altına inemez.
Collection: min_rate_floors {property_id, room_type_id|"all", standard_min_rate,
  near_term_min_rate, near_term_window_days, enabled}
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


async def get_effective_min_rate(db, pid: str, date_str: str,
                                 room_type_id: Optional[str] = None) -> Dict:
    """Tek tarih için geçerli taban. {"floor": float|None, "mode": ...}"""
    rules = await db.min_rate_floors.find(
        {"property_id": pid, "enabled": True}, {"_id": 0}).to_list(50)
    rule = _pick_rule(rules, room_type_id)
    if not rule:
        return {"floor": None, "mode": None}
    try:
        days_out = (ddate.fromisoformat(date_str[:10]) - ddate.today()).days
    except Exception:
        return {"floor": None, "mode": None}
    return _floor_for(rule, days_out)


async def effective_min_rate_map(db, pid: str, dates: list,
                                 room_type_id: Optional[str] = None) -> Dict[str, Dict]:
    """Çok tarih için taban haritası — tek DB sorgusuyla."""
    rules = await db.min_rate_floors.find(
        {"property_id": pid, "enabled": True}, {"_id": 0}).to_list(50)
    rule = _pick_rule(rules, room_type_id)
    if not rule:
        return {}
    today = ddate.today()
    out = {}
    for d in dates:
        try:
            days_out = (ddate.fromisoformat(d[:10]) - today).days
        except Exception:
            continue
        out[d] = _floor_for(rule, days_out)
    return out


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
        window = int(payload.get("near_term_window_days", 7) or 7)
        if window < 1 or window > 60:
            raise HTTPException(400, "Pencere 1-60 gün arasında olmalı")
        if std is not None and float(std) <= 0:
            raise HTTPException(400, "Standart minimum fiyat 0'dan büyük olmalı")
        if near is not None and float(near) <= 0:
            raise HTTPException(400, "Yakın tarih minimum fiyatı 0'dan büyük olmalı")
        if std and near and float(near) > float(std):
            raise HTTPException(400, "Yakın tarih minimumu standart minimumdan büyük olamaz")
        doc = {
            "property_id": pid, "room_type_id": room_type_id,
            "standard_min_rate": round(float(std), 2) if std else None,
            "near_term_min_rate": round(float(near), 2) if near else None,
            "near_term_window_days": window,
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
        """Önümüzdeki N gün hangi taban aktif — geçiş gününü gösterir."""
        days = max(1, min(days, 30))
        dates = [(ddate.today() + timedelta(days=i)).isoformat() for i in range(days)]
        fmap = await effective_min_rate_map(db, pid, dates, room_type_id if room_type_id != "all" else None)
        return {"days": [{"date": d, **(fmap.get(d) or {"floor": None, "mode": None})} for d in dates]}

    return router
