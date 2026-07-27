"""
İki Yönlü Sahip Fiyat Panosu (Owner Rates Board).
Otel sahibi kendi portalında (owner JWT) ve admin kendi panelinde AYNI veriyi görür:
tarih bazlı Live PMS Rate (brüt), Current Sell Rate (indirimler sonrası müşteri fiyatı),
doluluk, taban/tavan. Her iki taraf da fiyatı manuel değiştirebilir ve indirim/promosyon
katmanlarını ekleyip çıkarabilir — değişiklikler anında iki yönde görünür (rate_overrides
ve discount_layers ortak).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, date as ddate, timedelta
from typing import Dict
import jwt
import uuid
import logging

from routes.platform_ext.owner_self_service import _jwt_secret, JWT_ALGORITHM
from routes.revenue_ext.min_rate_floors import effective_bounds_map, clamp_to_bounds
from routes.revenue_ext.discount_stack import compute_stack, _active_layers, _get_mode, _combined_factor
from routes.revenue_ext.revenue_strategist import _occ_map

logger = logging.getLogger(__name__)


async def build_board(db, pid: str, days: int = 14) -> Dict:
    days = max(1, min(days, 60))
    today = ddate.today()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(days)]

    total_rooms = 0
    base_rate = 100.0
    async for rt in db.room_types.find({"property_id": pid}, {"_id": 0, "total_rooms": 1, "base_rate": 1}):
        total_rooms += int(rt.get("total_rooms", 0) or 0)
        if rt.get("base_rate"):
            base_rate = float(rt["base_rate"])
    total_rooms = max(total_rooms, 1)

    occ = await _occ_map(db, pid, today, today + timedelta(days=days))
    ov_docs = await db.rate_overrides.find(
        {"property_id": pid, "date": {"$gte": dates[0], "$lte": dates[-1]}},
        {"_id": 0, "date": 1, "custom_rate": 1, "source": 1, "set_at": 1}).sort(
        "set_at", 1).to_list(500)
    ov_map = {o["date"]: o for o in ov_docs}  # set_at artan sıralı → en güncel kazanır
    bounds_map = await effective_bounds_map(db, pid, dates)

    layers = await _active_layers(db, pid)
    mode = await _get_mode(db, pid)
    factor = _combined_factor([float(l["pct"]) for l in layers], mode)
    total_disc = round((1 - factor) * 100, 2)

    rows = []
    for d in dates:
        ov = ov_map.get(d)
        gross = float(ov["custom_rate"]) if ov and ov.get("custom_rate") else base_rate
        sold = occ.get(d, {}).get("rooms_sold", 0)
        b = bounds_map.get(d, {})
        rows.append({
            "date": d,
            "live_pms_rate": round(gross, 2),
            "current_sell_rate": round(gross * factor, 2),
            "source": (ov or {}).get("source", "base"),
            "occ_pct": round(sold / total_rooms * 100, 1),
            "rooms_sold": sold, "available": total_rooms - sold,
            "min_rate": b.get("floor"), "min_mode": b.get("mode"),
            "max_rate": b.get("ceiling"), "is_event_day": bool(b.get("is_event_day")),
        })
    return {"days": rows, "total_discount_pct": total_disc, "stack_mode": mode,
            "active_layers": layers, "total_rooms": total_rooms}


async def set_manual_rate(db, pid: str, payload: Dict, set_by: str, source: str) -> Dict:
    date_str = (payload.get("date") or "")[:10]
    rate = float(payload.get("rate", 0) or 0)
    rate_mode = payload.get("mode", "gross")
    if rate <= 0:
        raise HTTPException(400, "Fiyat 0'dan büyük olmalı")
    try:
        ddate.fromisoformat(date_str)
    except Exception:
        raise HTTPException(400, "Geçersiz tarih")
    if rate_mode == "net":
        calc = await compute_stack(db, pid, target_net=rate)
        gross = calc["gross_pms_override"]
    else:
        gross = rate
    bounds = (await effective_bounds_map(db, pid, [date_str])).get(date_str, {})
    res = clamp_to_bounds(gross, bounds)
    await db.rate_overrides.update_one(
        {"property_id": pid, "date": date_str},
        {"$set": {"property_id": pid, "date": date_str, "custom_rate": round(res["rate"], 2),
                  "source": source, "set_by": set_by,
                  "set_at": datetime.now(timezone.utc).isoformat(),
                  "context": {"manual": True, "input_mode": rate_mode, "input_value": rate}}},
        upsert=True)
    layers = await _active_layers(db, pid)
    mode = await _get_mode(db, pid)
    factor = _combined_factor([float(l["pct"]) for l in layers], mode)
    return {"ok": True, "date": date_str, "live_pms_rate": round(res["rate"], 2),
            "current_sell_rate": round(res["rate"] * factor, 2),
            "guard_clamped": res["clamped"], "guard_reason": res["reason"]}


def create_owner_rates_router(db, require_roles):
    router = APIRouter(prefix="/owner-rates")

    async def get_current_owner(request: Request) -> dict:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(401, "Owner token gerekli")
        try:
            payload = jwt.decode(auth[7:], _jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "owner_access":
                raise HTTPException(401, "Geçersiz token kapsamı")
            owner = await db.unit_owners.find_one({"id": payload["sub"]}, {"_id": 0})
            if not owner:
                raise HTTPException(401, "Sahip bulunamadı")
            return owner
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Oturum süresi doldu")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Geçersiz token")

    def _owner_pid(owner: dict) -> str:
        return owner.get("property_id") or "default"

    # ── Sahip (owner portal) tarafı — /{pid} rotalarından ÖNCE tanımlanmalı ──
    @router.get("/portal/board")
    async def owner_board(days: int = 14, owner: dict = Depends(get_current_owner)):
        return await build_board(db, _owner_pid(owner), days)

    @router.post("/portal/manual-rate")
    async def owner_manual_rate(payload: Dict, owner: dict = Depends(get_current_owner)):
        return await set_manual_rate(db, _owner_pid(owner), payload,
                                     owner.get("email", ""), "owner-manual")

    # ── Admin/staff tarafı ──
    @router.get("/{pid}/board")
    async def staff_board(pid: str, days: int = 14,
                          current_user: dict = Depends(require_roles("admin", "manager"))):
        return await build_board(db, pid, days)

    @router.post("/{pid}/manual-rate")
    async def staff_manual_rate(pid: str, payload: Dict,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        return await set_manual_rate(db, pid, payload, current_user.get("email", ""), "admin-manual")

    @router.get("/portal/layers")
    async def owner_layers(owner: dict = Depends(get_current_owner)):
        pid = _owner_pid(owner)
        layers = await db.discount_layers.find({"property_id": pid}, {"_id": 0}).sort("order", 1).to_list(50)
        return {"layers": layers, "stack_mode": await _get_mode(db, pid)}

    @router.post("/portal/layers")
    async def owner_add_layer(payload: Dict, owner: dict = Depends(get_current_owner)):
        pid = _owner_pid(owner)
        name = (payload.get("name") or "").strip()[:60]
        pct = float(payload.get("pct", 0) or 0)
        if not name or pct <= 0 or pct >= 90:
            raise HTTPException(400, "Geçerli ad ve %0-90 arası yüzde girin")
        count = await db.discount_layers.count_documents({"property_id": pid})
        doc = {"id": str(uuid.uuid4())[:8], "property_id": pid, "name": name,
               "pct": round(pct, 2), "active": True, "order": count,
               "created_at": datetime.now(timezone.utc).isoformat(),
               "created_by_owner": owner.get("email", "")}
        await db.discount_layers.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/portal/layers/{lid}")
    async def owner_toggle_layer(lid: str, payload: Dict, owner: dict = Depends(get_current_owner)):
        upd = {}
        if "active" in payload:
            upd["active"] = bool(payload["active"])
        if "pct" in payload:
            pct = float(payload["pct"] or 0)
            if pct <= 0 or pct >= 90:
                raise HTTPException(400, "Yüzde 0-90 arası olmalı")
            upd["pct"] = round(pct, 2)
        res = await db.discount_layers.update_one(
            {"property_id": _owner_pid(owner), "id": lid}, {"$set": upd})
        if res.matched_count == 0:
            raise HTTPException(404, "İndirim bulunamadı")
        return {"ok": True}

    @router.delete("/portal/layers/{lid}")
    async def owner_delete_layer(lid: str, owner: dict = Depends(get_current_owner)):
        res = await db.discount_layers.delete_one({"property_id": _owner_pid(owner), "id": lid})
        if res.deleted_count == 0:
            raise HTTPException(404, "İndirim bulunamadı")
        return {"ok": True}

    return router
