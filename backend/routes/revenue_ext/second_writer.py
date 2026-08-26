"""
İkinci-Yazıcı Tespiti (Second-Writer Detection) — RevenueIQ gap P0.
Her fiyat yazımımız aktör imzalı olarak channel_price_ledger'a kaydedilir.
Kanal tarafındaki fiyat (mock: mock_channel_rates) bizim son yazdığımızla kıyaslanır;
başka bir aktör yazmışsa veya fiyat sapıyorsa saatler içinde alarm üretilir.
Collections: channel_price_ledger, mock_channel_rates, second_writer_alerts
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

OUR_ACTOR = "hotelbox-rms"
CHANNELS = ["booking", "expedia", "airbnb"]


def _now():
    return datetime.now(timezone.utc)


async def _current_rate(db, pid: str, day: str) -> float:
    ov = await db.rate_overrides.find_one(
        {"property_id": pid, "date": day, "custom_rate": {"$gt": 0}}, {"_id": 0})
    if ov:
        return float(ov["custom_rate"])
    rt = await db.room_types.find_one({"property_id": pid}, {"_id": 0, "base_price": 1},
                                      sort=[("base_price", 1)])
    return float((rt or {}).get("base_price", 0))


async def push_rates(db, pid: str, horizon_days: int = 7, actor: str = OUR_ACTOR) -> Dict:
    """Fiyatları kanallara yaz (mock) + aktör imzalı ledger kaydı."""
    now = _now()
    today = now.date()
    written = 0
    for i in range(horizon_days):
        day = (today + timedelta(days=i)).isoformat()
        rate = await _current_rate(db, pid, day)
        if rate <= 0:
            continue
        for ch in CHANNELS:
            await db.channel_price_ledger.update_one(
                {"property_id": pid, "date": day, "channel": ch},
                {"$set": {"rate": round(rate, 2), "actor": actor,
                          "written_at": now.isoformat()}}, upsert=True)
            await db.mock_channel_rates.update_one(
                {"property_id": pid, "date": day, "channel": ch},
                {"$set": {"rate": round(rate, 2), "actor": actor,
                          "written_at": now.isoformat()}}, upsert=True)
            written += 1
    return {"ok": True, "cells_written": written, "channels": CHANNELS, "actor": actor}


async def scan_property(db, pid: str) -> Dict:
    now = _now()
    today = now.date().isoformat()
    alerts = []
    async for ch_row in db.mock_channel_rates.find(
            {"property_id": pid, "date": {"$gte": today}}, {"_id": 0}):
        ours = await db.channel_price_ledger.find_one(
            {"property_id": pid, "date": ch_row["date"], "channel": ch_row["channel"]}, {"_id": 0})
        if not ours:
            continue
        foreign_actor = ch_row.get("actor") != OUR_ACTOR
        rate_mismatch = abs(float(ch_row.get("rate", 0)) - float(ours.get("rate", 0))) > 0.01
        if not (foreign_actor or rate_mismatch):
            continue
        existing = await db.second_writer_alerts.find_one(
            {"property_id": pid, "date": ch_row["date"], "channel": ch_row["channel"],
             "status": "open"}, {"_id": 0})
        if existing:
            continue
        alert = {"id": str(uuid.uuid4()), "property_id": pid,
                 "date": ch_row["date"], "channel": ch_row["channel"],
                 "channel_rate": float(ch_row.get("rate", 0)),
                 "expected_rate": float(ours.get("rate", 0)),
                 "channel_actor": ch_row.get("actor", "unknown"),
                 "our_written_at": ours.get("written_at"),
                 "detected_at": now.isoformat(), "status": "open"}
        await db.second_writer_alerts.insert_one(dict(alert))
        alert.pop("_id", None)
        alerts.append(alert)
    if alerts:
        a = alerts[0]
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "category": "second_writer",
            "priority": "high", "target_user": "", "target_role": "manager",
            "title": f"🚨 İkinci yazıcı tespit edildi: {len(alerts)} hücre",
            "message": (f"{a['channel']} kanalında {a['date']} için bizim yazdığımız {a['expected_rate']} yerine "
                        f"{a['channel_rate']} görünüyor (aktör: {a['channel_actor']}). "
                        "Eski bir araç veya elle müdahale fiyat yazıyor olabilir."),
            "read": False, "created_at": now.isoformat()})
    return {"property_id": pid, "new_alerts": len(alerts), "alerts": alerts}


async def second_writer_loop(db, interval_seconds: int = 3600):
    await asyncio.sleep(180)
    while True:
        try:
            for pid in await db.properties.distinct("id"):
                r = await scan_property(db, pid)
                if r["new_alerts"]:
                    logger.info("Second writer %s: %s alarm", pid, r["new_alerts"])
        except Exception as ex:
            logger.warning("Second writer loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_second_writer_router(db, require_roles):
    router = APIRouter(prefix="/second-writer", tags=["second-writer"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        q = {} if pid == "all" else {"property_id": pid}
        alerts = await db.second_writer_alerts.find(q, {"_id": 0}).sort("detected_at", -1).to_list(100)
        ledger_count = await db.channel_price_ledger.count_documents(q)
        last_push = await db.channel_price_ledger.find_one(q, {"_id": 0}, sort=[("written_at", -1)])
        return {"alerts": alerts, "channels": CHANNELS, "our_actor": OUR_ACTOR,
                "summary": {"open": sum(1 for a in alerts if a["status"] == "open"),
                            "acked": sum(1 for a in alerts if a["status"] == "acked"),
                            "ledger_cells": ledger_count,
                            "last_push_at": (last_push or {}).get("written_at")}}

    @router.post("/{pid}/push")
    async def push(pid: str, horizon_days: int = 7, u: dict = Depends(require_roles(*ROLES))):
        return await push_rates(db, pid, max(1, min(horizon_days, 30)))

    @router.post("/{pid}/scan")
    async def scan(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        return await scan_property(db, pid)

    @router.post("/{pid}/simulate-foreign-write")
    async def simulate_foreign(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        """Test/tatbikat: kanala yabancı bir aktörün fiyat yazdığını simüle eder."""
        day = data.get("date")
        rate = data.get("rate")
        ch = data.get("channel", "booking")
        if not day or rate is None:
            raise HTTPException(422, "date ve rate zorunlu")
        if ch not in CHANNELS:
            raise HTTPException(422, f"channel şunlardan biri olmalı: {CHANNELS}")
        await db.mock_channel_rates.update_one(
            {"property_id": pid, "date": day, "channel": ch},
            {"$set": {"rate": float(rate), "actor": data.get("actor", "legacy-tool"),
                      "written_at": _now().isoformat()}}, upsert=True)
        return {"ok": True, "date": day, "channel": ch, "rate": float(rate)}

    @router.post("/{pid}/alerts/{alert_id}/ack")
    async def ack(pid: str, alert_id: str, u: dict = Depends(require_roles(*ROLES))):
        r = await db.second_writer_alerts.update_one(
            {"id": alert_id, "property_id": pid},
            {"$set": {"status": "acked", "acked_at": _now().isoformat(),
                      "acked_by": u.get("name") or u.get("email", "")}})
        if r.matched_count == 0:
            raise HTTPException(404, "Alarm bulunamadı")
        return {"ok": True}

    @router.post("/{pid}/repush")
    async def repush(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        """Yabancı yazımların üzerine bizim fiyatları geri yazar (drift onarımı)."""
        res = await push_rates(db, pid, 7)
        await db.second_writer_alerts.update_many(
            {"property_id": pid, "status": "open"},
            {"$set": {"status": "repushed", "resolved_at": _now().isoformat()}})
        return {"ok": True, **res}

    return router
