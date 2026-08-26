"""
Vitrin Doğrulaması (Own Storefront Verification) — RevenueIQ gap P0.
Otelin KENDİ Booking vitrinini misafir gözüyle tarar: panele yazılan fiyat +
aktif indirim katmanları (discount_layers) → beklenen misafir fiyatı; gözlenen
fiyatla kuruşuna kıyaslanır. Sapma varsa hangi katmandan geldiği raporlanır.
Mod: mock (canlı scraper anahtarı gelene dek) — inject-drift ile sapma simüle edilir.
Collections: storefront_config, storefront_scans, storefront_mock_observations
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta, date as ddate
from typing import Dict
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

DEFAULT_CFG = {"enabled": True, "mode": "mock", "tolerance_pct": 1.0, "horizon_days": 14}


def _now():
    return datetime.now(timezone.utc)


async def _get_cfg(db, pid: str) -> Dict:
    doc = await db.storefront_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULT_CFG, **{k: doc[k] for k in DEFAULT_CFG if k in doc}}


async def _written_rate(db, pid: str, day: str) -> float:
    ov = await db.rate_overrides.find_one(
        {"property_id": pid, "room_type_id": "", "date": day}, {"_id": 0})
    if ov and ov.get("custom_rate"):
        return float(ov["custom_rate"])
    ov2 = await db.rate_overrides.find_one(
        {"property_id": pid, "date": day, "custom_rate": {"$gt": 0}}, {"_id": 0})
    if ov2:
        return float(ov2["custom_rate"])
    rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0, "base_price": 1},
                                      sort=[("base_price", 1)])
    return float((rt or {}).get("base_price", 0))


async def _active_layers(db, pid: str):
    return await db.discount_layers.find(
        {"property_id": pid, "active": True}, {"_id": 0}).sort("order", 1).to_list(20)


def _guest_price(written: float, layers, mode: str = "multiplicative") -> float:
    p = written
    if mode == "additive":
        total = sum(float(l.get("pct", 0)) for l in layers)
        return round(written * (1 - min(total, 95) / 100), 2)
    for l in layers:
        p *= (1 - float(l.get("pct", 0)) / 100)
    return round(p, 2)


async def scan_property(db, pid: str) -> Dict:
    cfg = await _get_cfg(db, pid)
    if not cfg["enabled"]:
        return {"property_id": pid, "skipped": "disabled"}
    now = _now()
    today = now.date()
    layers = await _active_layers(db, pid)
    stack_cfg = await db.discount_stack_config.find_one({"property_id": pid}, {"_id": 0}) or {}
    stack_mode = stack_cfg.get("mode", "multiplicative")
    rows, flagged = [], 0
    for i in range(int(cfg["horizon_days"])):
        day = (today + timedelta(days=i)).isoformat()
        written = await _written_rate(db, pid, day)
        if written <= 0:
            continue
        expected = _guest_price(written, layers, stack_mode)
        inj = await db.storefront_mock_observations.find_one(
            {"property_id": pid, "date": day}, {"_id": 0})
        observed = float(inj["observed_rate"]) if inj else expected
        dev_pct = round((observed - expected) / expected * 100, 2) if expected > 0 else 0.0
        status = "ok" if abs(dev_pct) <= float(cfg["tolerance_pct"]) else "drift"
        if status == "drift":
            flagged += 1
        rows.append({"date": day, "written": round(written, 2), "expected_guest": expected,
                     "observed": round(observed, 2), "deviation_pct": dev_pct, "status": status,
                     "injected": bool(inj),
                     "layers": [{"name": l["name"], "pct": l["pct"]} for l in layers]})
    scan = {"id": str(uuid.uuid4()), "property_id": pid, "scanned_at": now.isoformat(),
            "mode": cfg["mode"], "tolerance_pct": cfg["tolerance_pct"],
            "rows": rows, "flagged": flagged, "total": len(rows)}
    await db.storefront_scans.insert_one(dict(scan))
    if flagged > 0:
        worst = max((r for r in rows if r["status"] == "drift"), key=lambda r: abs(r["deviation_pct"]))
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "category": "storefront_verify",
            "priority": "high", "target_user": "", "target_role": "manager",
            "title": f"🛍️ Vitrin sapması: {flagged} gün — en kötü {worst['date']} (%{worst['deviation_pct']})",
            "message": (f"Panele yazılan {worst['written']} → beklenen misafir fiyatı {worst['expected_guest']}, "
                        f"vitrinde görünen {worst['observed']}. Vitrin Doğrulaması panelinden inceleyin."),
            "read": False, "created_at": now.isoformat()})
    scan.pop("_id", None)
    return scan


async def storefront_verify_loop(db, interval_seconds: int = 21600):
    await asyncio.sleep(150)
    while True:
        try:
            for pid in await db.properties.distinct("id"):
                r = await scan_property(db, pid)
                if r.get("flagged"):
                    logger.info("Storefront drift %s: %s gün", pid, r["flagged"])
        except Exception as ex:
            logger.warning("Storefront verify loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_storefront_verify_router(db, require_roles):
    router = APIRouter(prefix="/storefront-verify", tags=["storefront-verify"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}/report")
    async def report(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _get_cfg(db, pid)
        scan = await db.storefront_scans.find_one(
            {"property_id": pid}, {"_id": 0}, sort=[("scanned_at", -1)])
        history = await db.storefront_scans.find(
            {"property_id": pid}, {"_id": 0, "rows": 0}).sort("scanned_at", -1).to_list(20)
        return {"config": cfg, "latest": scan, "history": history}

    @router.post("/{pid}/scan")
    async def manual_scan(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await scan_property(db, pid)

    @router.put("/{pid}/config")
    async def put_config(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {}
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        if data.get("tolerance_pct") is not None:
            upd["tolerance_pct"] = max(0.1, min(float(data["tolerance_pct"]), 10.0))
        if data.get("horizon_days") is not None:
            upd["horizon_days"] = max(3, min(int(data["horizon_days"]), 30))
        if data.get("mode") in ("mock", "live"):
            upd["mode"] = data["mode"]
        if upd:
            await db.storefront_config.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, "config": await _get_cfg(db, pid)}

    @router.post("/{pid}/inject-drift")
    async def inject_drift(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        """Test/simülasyon: belirli bir gün için vitrinde 'görünen' fiyatı sabitle."""
        day = data.get("date")
        rate = data.get("observed_rate")
        if not day or rate is None:
            raise HTTPException(422, "date ve observed_rate zorunlu")
        await db.storefront_mock_observations.update_one(
            {"property_id": pid, "date": day},
            {"$set": {"observed_rate": float(rate), "injected_at": _now().isoformat()}}, upsert=True)
        return {"ok": True, "date": day, "observed_rate": float(rate)}

    @router.delete("/{pid}/drift")
    async def clear_drift(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        r = await db.storefront_mock_observations.delete_many({"property_id": pid})
        return {"ok": True, "cleared": r.deleted_count}

    return router
