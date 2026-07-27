"""
İndirim Katmanları & Net Fiyat Hesaplayıcı (Discount Stacking).
OTA'da uygulanan indirimler (phone %10, last minute %10, Genius %10 vb.) üst üste
biner. Kullanıcı müşterinin göreceği SON satış fiyatını girer (örn. £79); sistem
geriye doğru hesaplayıp PMS Override brüt fiyatını (örn. £96) bulur ve rate_overrides'a
yazar. OTA'da "was £96 → £79" görünür.
Yığınlama: multiplicative (her indirim kalan fiyata uygulanır, OTA standardı) veya
additive (yüzdeler toplanır).
Collections: discount_layers, discount_stack_config
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date as ddate, timedelta
from typing import Dict
import uuid
import logging

logger = logging.getLogger(__name__)

STACK_MODES = ("multiplicative", "additive")


def _iso():
    return datetime.now(timezone.utc).isoformat()


def _combined_factor(pcts: list, mode: str) -> float:
    """Net = Brüt * factor. multiplicative: Π(1-p); additive: 1-Σp."""
    if mode == "additive":
        return max(1.0 - sum(pcts) / 100.0, 0.01)
    f = 1.0
    for p in pcts:
        f *= (1.0 - p / 100.0)
    return max(f, 0.01)


def _breakdown(gross: float, layers: list, mode: str) -> list:
    steps = []
    running = gross
    for l in layers:
        p = float(l["pct"])
        cut = round((gross if mode == "additive" else running) * p / 100.0, 2)
        running = round(running - cut, 2)
        steps.append({"name": l["name"], "pct": p, "discount_amount": cut, "price_after": running})
    return steps


async def _active_layers(db, pid: str) -> list:
    return await db.discount_layers.find(
        {"property_id": pid, "active": True}, {"_id": 0}).sort("order", 1).to_list(20)


async def _get_mode(db, pid: str) -> str:
    doc = await db.discount_stack_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    return doc.get("stack_mode", "multiplicative")


async def compute_stack(db, pid: str, target_net: float = None, gross: float = None) -> Dict:
    layers = await _active_layers(db, pid)
    mode = await _get_mode(db, pid)
    pcts = [float(l["pct"]) for l in layers]
    factor = _combined_factor(pcts, mode)
    if target_net is not None:
        gross = round(target_net / factor, 2)
        net = round(gross * factor, 2)
    else:
        net = round(gross * factor, 2)
    return {
        "gross_pms_override": gross, "net_customer_price": net,
        "total_discount_pct": round((1 - factor) * 100, 2), "stack_mode": mode,
        "layers": layers, "breakdown": _breakdown(gross, layers, mode),
        "ota_display": {"was": gross, "now": net},
    }


def create_discount_stack_router(db, require_roles):
    router = APIRouter(prefix="/discount-stack")

    @router.get("/{pid}")
    async def get_all(pid: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        layers = await db.discount_layers.find({"property_id": pid}, {"_id": 0}).sort("order", 1).to_list(50)
        return {"layers": layers, "stack_mode": await _get_mode(db, pid)}

    @router.put("/{pid}/config")
    async def set_config(pid: str, payload: Dict,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        mode = payload.get("stack_mode")
        if mode not in STACK_MODES:
            raise HTTPException(400, f"stack_mode {STACK_MODES} olmalı")
        await db.discount_stack_config.update_one(
            {"property_id": pid}, {"$set": {"property_id": pid, "stack_mode": mode,
                                            "updated_at": _iso()}}, upsert=True)
        return {"stack_mode": mode}

    @router.post("/{pid}/layers")
    async def add_layer(pid: str, payload: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        name = (payload.get("name") or "").strip()[:60]
        pct = float(payload.get("pct", 0) or 0)
        if not name:
            raise HTTPException(400, "İndirim adı gerekli")
        if pct <= 0 or pct >= 90:
            raise HTTPException(400, "İndirim yüzdesi 0-90 arasında olmalı")
        count = await db.discount_layers.count_documents({"property_id": pid})
        doc = {"id": str(uuid.uuid4())[:8], "property_id": pid, "name": name,
               "pct": round(pct, 2), "active": bool(payload.get("active", True)),
               "order": count, "created_at": _iso()}
        await db.discount_layers.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.put("/{pid}/layers/{lid}")
    async def update_layer(pid: str, lid: str, payload: Dict,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        upd = {}
        if "name" in payload:
            upd["name"] = (payload["name"] or "").strip()[:60]
        if "pct" in payload:
            pct = float(payload["pct"] or 0)
            if pct <= 0 or pct >= 90:
                raise HTTPException(400, "İndirim yüzdesi 0-90 arasında olmalı")
            upd["pct"] = round(pct, 2)
        if "active" in payload:
            upd["active"] = bool(payload["active"])
        res = await db.discount_layers.update_one(
            {"property_id": pid, "id": lid}, {"$set": upd})
        if res.matched_count == 0:
            raise HTTPException(404, "İndirim bulunamadı")
        return {"ok": True}

    @router.delete("/{pid}/layers/{lid}")
    async def delete_layer(pid: str, lid: str,
                           current_user: dict = Depends(require_roles("admin", "manager"))):
        res = await db.discount_layers.delete_one({"property_id": pid, "id": lid})
        if res.deleted_count == 0:
            raise HTTPException(404, "İndirim bulunamadı")
        return {"ok": True}

    @router.post("/{pid}/calculate")
    async def calculate(pid: str, payload: Dict,
                        current_user: dict = Depends(require_roles("admin", "manager"))):
        """{target_net: 79} → brüt hesapla; {gross: 96} → net hesapla."""
        target_net = payload.get("target_net")
        gross = payload.get("gross")
        if target_net is None and gross is None:
            raise HTTPException(400, "target_net veya gross gerekli")
        if target_net is not None and float(target_net) <= 0:
            raise HTTPException(400, "Hedef fiyat 0'dan büyük olmalı")
        return await compute_stack(db, pid,
                                   float(target_net) if target_net is not None else None,
                                   float(gross) if gross is not None else None)

    @router.post("/{pid}/apply")
    async def apply(pid: str, payload: Dict,
                    current_user: dict = Depends(require_roles("admin", "manager"))):
        """Hedef net fiyattan brüt hesaplar, tarih aralığına PMS Override yazar.
        Fiyat koruma (min/max) sınırları BRÜT fiyata uygulanır."""
        from routes.revenue_ext.min_rate_floors import effective_bounds_map, clamp_to_bounds
        target_net = float(payload.get("target_net", 0) or 0)
        if target_net <= 0:
            raise HTTPException(400, "target_net gerekli")
        try:
            d = ddate.fromisoformat(payload["date_start"])
            d_end = ddate.fromisoformat(payload.get("date_end") or payload["date_start"])
        except Exception:
            raise HTTPException(400, "Geçersiz tarih aralığı")
        calc = await compute_stack(db, pid, target_net=target_net)
        gross = calc["gross_pms_override"]
        dates = []
        while d <= d_end and len(dates) < 120:
            dates.append(d.isoformat())
            d += timedelta(days=1)
        bounds_map = await effective_bounds_map(db, pid, dates)
        now = _iso()
        clamped = 0
        for ds in dates:
            res = clamp_to_bounds(gross, bounds_map.get(ds, {}))
            if res["clamped"]:
                clamped += 1
            await db.rate_overrides.update_one(
                {"property_id": pid, "date": ds},
                {"$set": {"property_id": pid, "date": ds, "custom_rate": round(res["rate"], 2),
                          "source": "discount-calculator", "set_by": current_user.get("email", ""),
                          "set_at": now,
                          "context": {"target_net": target_net, "gross": gross,
                                      "total_discount_pct": calc["total_discount_pct"]}}},
                upsert=True)
        return {"ok": True, "dates_updated": len(dates), "gross_pms_override": gross,
                "net_customer_price": calc["net_customer_price"],
                "ota_display": calc["ota_display"], "guard_clamped": clamped,
                "breakdown": calc["breakdown"]}

    return router
