"""
OTA Virtual Card (VCC) Automation — Mews parity.
Detects OTA prepaid bookings, tracks their virtual cards and auto-charges
them on activation date (check-in). Mock charge processor (Stripe test).
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date, timedelta
from typing import Dict
import uuid
import random
import logging

logger = logging.getLogger(__name__)

OTA_CHANNELS = ("booking_com", "expedia", "agoda", "trip_com", "hotelbeds")


def _now():
    return datetime.now(timezone.utc).isoformat()


async def scan_ota_bookings(db, property_id: str = "all") -> Dict:
    """Create VCC records for OTA bookings not yet tracked (idempotent)."""
    pq: Dict = {} if property_id == "all" else {"property_id": property_id}
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    q = {**pq,
         "status": {"$nin": ["cancelled", "no_show"]},
         "check_in": {"$gte": cutoff},
         "$or": [{"channel": {"$in": list(OTA_CHANNELS)}},
                 {"source": {"$regex": "^ota:"}}]}
    created = 0
    async for b in db.bookings.find(q, {"_id": 0}):
        amount = float(b.get("total_price") or 0)
        if amount <= 0:
            continue
        exists = await db.vcc_cards.find_one({"booking_id": b["id"]}, {"_id": 0, "id": 1})
        if exists:
            continue
        ci = b.get("check_in", "")
        co = b.get("check_out", ci)
        await db.vcc_cards.insert_one({
            "id": str(uuid.uuid4()), "property_id": b.get("property_id"),
            "booking_id": b["id"], "guest_name": b.get("guest_name"),
            "channel": b.get("channel") or (b.get("source", "").replace("ota:", "")),
            "last4": f"{random.randint(0, 9999):04d}",
            "amount": round(amount, 2), "currency": b.get("currency", "GBP"),
            "activation_date": ci, "expiry_date": co,
            "status": "pending", "attempts": 0,
            "created_at": _now()})
        created += 1
    return {"ok": True, "created": created}


async def charge_due_vccs(db, force_id: str = "") -> Dict:
    """Charge VCCs whose activation date has arrived. Mock processor."""
    today = date.today().isoformat()
    q: Dict = {"status": {"$in": ["pending", "failed"]}}
    if force_id:
        q["id"] = force_id
    else:
        q["activation_date"] = {"$lte": today}
    charged = failed = expired = 0
    async for c in db.vcc_cards.find(q, {"_id": 0}):
        if not force_id and c.get("expiry_date", "9999") < (date.today() - timedelta(days=14)).isoformat():
            await db.vcc_cards.update_one({"id": c["id"]}, {"$set": {
                "status": "expired", "updated_at": _now()}})
            expired += 1
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "type": "error",
                "title": "VCC Süresi Doldu — Tahsilat Kaçtı!",
                "message": f"{c['guest_name']} ({c['channel']}) sanal kartı tahsil edilemeden süresi doldu: {c['currency']} {c['amount']}",
                "category": "vcc", "target_user": "", "target_role": "manager",
                "link_to": "vcc-automation", "priority": "high",
                "read": False, "created_by": "VCC Autopilot", "created_at": _now()})
            continue
        success = random.random() < 0.9 or bool(force_id)
        if success:
            await db.vcc_cards.update_one({"id": c["id"]}, {"$set": {
                "status": "charged", "charged_at": _now(),
                "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
                "updated_at": _now()}, "$inc": {"attempts": 1}})
            charged += 1
        else:
            await db.vcc_cards.update_one({"id": c["id"]}, {"$set": {
                "status": "failed", "last_error": "Card declined (mock)",
                "updated_at": _now()}, "$inc": {"attempts": 1}})
            failed += 1
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "type": "warning",
                "title": "VCC Tahsilatı Başarısız",
                "message": f"{c['guest_name']} ({c['channel']}) sanal kart tahsilatı reddedildi: {c['currency']} {c['amount']} — tekrar denenecek.",
                "category": "vcc", "target_user": "", "target_role": "manager",
                "link_to": "vcc-automation", "priority": "high",
                "read": False, "created_by": "VCC Autopilot", "created_at": _now()})
    return {"ok": True, "charged": charged, "failed": failed, "expired": expired}


async def vcc_job(db) -> Dict:
    scan = await scan_ota_bookings(db)
    run = await charge_due_vccs(db)
    return {**run, "scanned_new": scan["created"]}


def create_vcc_router(db, require_roles):
    router = APIRouter()

    @router.get("/vcc/{property_id}")
    async def list_vcc(property_id: str, limit: int = 100,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        pq: Dict = {} if property_id == "all" else {"property_id": property_id}
        cards = await db.vcc_cards.find(pq, {"_id": 0}).sort("activation_date", 1).to_list(int(limit))
        today = date.today().isoformat()
        cutoff30 = (date.today() - timedelta(days=30)).isoformat()
        pending = [c for c in cards if c["status"] == "pending"]
        due_today = [c for c in pending if c["activation_date"] <= today]
        charged30 = await db.vcc_cards.find(
            {**pq, "status": "charged", "charged_at": {"$gte": cutoff30}},
            {"_id": 0, "amount": 1}).to_list(2000)
        return {"cards": cards,
                "summary": {
                    "pending_count": len(pending),
                    "pending_amount": round(sum(c["amount"] for c in pending), 2),
                    "due_today_count": len(due_today),
                    "due_today_amount": round(sum(c["amount"] for c in due_today), 2),
                    "failed_count": sum(1 for c in cards if c["status"] == "failed"),
                    "charged_30d_amount": round(sum(c["amount"] for c in charged30), 2),
                }}

    @router.post("/vcc/scan")
    async def scan_now(data: Dict = None,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        return await scan_ota_bookings(db, (data or {}).get("property_id", "all"))

    @router.post("/vcc/run")
    async def run_now(current_user: dict = Depends(require_roles("admin", "manager"))):
        return await charge_due_vccs(db)

    @router.post("/vcc/{vcc_id}/charge")
    async def charge_one(vcc_id: str,
                         current_user: dict = Depends(require_roles("admin", "manager"))):
        card = await db.vcc_cards.find_one({"id": vcc_id}, {"_id": 0, "status": 1})
        if not card:
            raise HTTPException(404, "VCC bulunamadı")
        if card["status"] == "charged":
            raise HTTPException(409, "Zaten tahsil edildi")
        return await charge_due_vccs(db, force_id=vcc_id)

    router.run_vcc_job_internal = vcc_job
    return router
