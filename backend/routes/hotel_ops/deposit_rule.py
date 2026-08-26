"""
Depozito Kuralı — yüksek no-show riskli rezervasyonlardan otomatik ön ödeme (depozito)
istenir: Stripe checkout linki üretilir ve misafire e-postalanır (e-posta MOCK olabilir).
Config: deposit_rules {enabled, min_score, deposit_pct, origin_url}
Collections: deposit_rules, deposit_requests
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone, timedelta
from typing import Dict
import os
import uuid
import asyncio
import logging

import stripe

from routes.hotel_ops.noshow_risk import score_arrivals
from routes.platform_ext.mailer import send_email

logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"

DEFAULT_CFG = {"enabled": False, "min_score": 50, "deposit_pct": 30.0, "origin_url": ""}


def _now():
    return datetime.now(timezone.utc)


async def _get_cfg(db, pid: str) -> Dict:
    doc = await db.deposit_rules.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**DEFAULT_CFG, **{k: doc[k] for k in DEFAULT_CFG if k in doc}}


async def run_deposit_check(db, pid: str, origin_url: str = "") -> Dict:
    cfg = await _get_cfg(db, pid)
    if not cfg["enabled"]:
        return {"skipped": "disabled", "created": []}
    origin = (origin_url or cfg.get("origin_url") or "").rstrip("/")
    if not origin:
        return {"skipped": "no_origin", "created": [],
                "detail": "origin_url gerekli (panelden çalıştırınca otomatik dolar)"}
    tomorrow = (_now().date() + timedelta(days=1)).isoformat()
    risks = await score_arrivals(db, pid, tomorrow)
    created, skips = [], []
    for r in risks:
        if r["score"] < int(cfg["min_score"]):
            continue
        if (r.get("payment_status") or "pending") not in ("pending", "unpaid", ""):
            skips.append({"booking_id": r["booking_id"], "reason": "already_paid"})
            continue
        existing = await db.deposit_requests.find_one(
            {"booking_id": r["booking_id"], "status": {"$in": ["requested", "paid"]}})
        if existing:
            skips.append({"booking_id": r["booking_id"], "reason": "already_requested"})
            continue
        booking = await db.bookings.find_one({"id": r["booking_id"]}, {"_id": 0})
        total = float(booking.get("total_price", 0) or 0)
        amount = round(max(total * float(cfg["deposit_pct"]) / 100, 1.0), 2)
        currency = (booking.get("currency") or "GBP").lower()
        try:
            session = stripe.checkout.Session.create(
                line_items=[{"price_data": {
                    "currency": currency, "unit_amount": int(round(amount * 100)),
                    "product_data": {"name": (f"Depozito (no-show güvencesi) — {booking.get('guest_name','')} "
                                              f"({booking.get('check_in')} → {booking.get('check_out')})")},
                }, "quantity": 1}],
                mode="payment",
                success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{origin}/payment/cancel",
                metadata={"booking_id": r["booking_id"], "kind": "noshow_deposit"})
        except Exception as ex:
            skips.append({"booking_id": r["booking_id"], "reason": f"stripe_error: {str(ex)[:80]}"})
            continue
        req = {"id": str(uuid.uuid4()), "property_id": pid, "booking_id": r["booking_id"],
               "booking_ref": r.get("booking_ref"), "guest_name": r.get("guest_name"),
               "guest_email": booking.get("guest_email", ""), "risk_score": r["score"],
               "amount": amount, "currency": currency.upper(), "deposit_pct": cfg["deposit_pct"],
               "checkout_url": session.url, "session_id": session.id,
               "status": "requested", "created_at": _now().isoformat()}
        await db.deposit_requests.insert_one(dict(req))
        email_status = "no_email"
        if (booking.get("guest_email") or "").strip():
            email_status = await send_email(
                db, booking["guest_email"],
                f"Rezervasyon güvencesi: depozito ödemesi — {booking.get('booking_ref','')}",
                (f"<div style='font-family:sans-serif;max-width:520px'>"
                 f"<h3>Sayın {booking.get('guest_name','Misafirimiz')},</h3>"
                 f"<p>{booking.get('check_in')} girişli rezervasyonunuzu güvenceye almak için "
                 f"<b>{currency.upper()} {amount}</b> depozito ödemenizi rica ederiz.</p>"
                 f"<p><a href='{session.url}' style='background:#1c1917;color:#fff;padding:10px 18px;"
                 f"border-radius:999px;text-decoration:none'>Depozitoyu Öde</a></p>"
                 f"<p style='color:#888;font-size:12px'>Ödeme, konaklama toplamınızdan düşülür.</p></div>"),
                kind="noshow_deposit", meta={"booking_id": r["booking_id"]})
        req.pop("_id", None)
        req["email_status"] = email_status
        created.append(req)
    if created:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "property_id": pid, "category": "deposit_rule",
            "priority": "medium", "target_user": "", "target_role": "manager",
            "title": f"💳 {len(created)} riskli rezervasyondan depozito istendi",
            "message": "Yüksek no-show riskli misafirlere Stripe depozito linki gönderildi. Detay: No-Show Riski paneli.",
            "read": False, "created_at": _now().isoformat()})
    return {"created": created, "skips": skips, "scanned": len(risks)}


async def deposit_rule_loop(db, interval_seconds: int = 21600):
    await asyncio.sleep(390)
    while True:
        try:
            for pid in await db.properties.distinct("id"):
                r = await run_deposit_check(db, pid)
                if r.get("created"):
                    logger.info("Deposit rule %s: %s istek", pid, len(r["created"]))
        except Exception as ex:
            logger.warning("Deposit rule loop error: %s", ex)
        await asyncio.sleep(interval_seconds)


def create_deposit_rule_router(db, require_roles):
    router = APIRouter(prefix="/deposit-rule", tags=["deposit-rule"])
    ROLES = ("admin", "manager")

    @router.get("/{pid}")
    async def status(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        cfg = await _get_cfg(db, pid)
        reqs = await db.deposit_requests.find(
            {"property_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"config": cfg, "requests": reqs,
                "summary": {"requested": sum(1 for r in reqs if r["status"] == "requested"),
                            "paid": sum(1 for r in reqs if r["status"] == "paid")}}

    @router.put("/{pid}/config")
    async def put_config(pid: str, data: Dict, _u: dict = Depends(require_roles(*ROLES))):
        upd = {}
        if "enabled" in data:
            upd["enabled"] = bool(data["enabled"])
        if data.get("min_score") is not None:
            upd["min_score"] = max(30, min(int(data["min_score"]), 90))
        if data.get("deposit_pct") is not None:
            upd["deposit_pct"] = max(10.0, min(float(data["deposit_pct"]), 100.0))
        if data.get("origin_url"):
            upd["origin_url"] = data["origin_url"].rstrip("/")
        if upd:
            await db.deposit_rules.update_one({"property_id": pid}, {"$set": upd}, upsert=True)
        return {"ok": True, "config": await _get_cfg(db, pid)}

    @router.post("/{pid}/run")
    async def run_now(pid: str, data: Dict = None, request: Request = None,
                      _u: dict = Depends(require_roles(*ROLES))):
        data = data or {}
        origin = data.get("origin_url", "")
        if origin:
            await db.deposit_rules.update_one(
                {"property_id": pid}, {"$set": {"origin_url": origin.rstrip("/")}}, upsert=True)
        return await run_deposit_check(db, pid, origin)

    return router
