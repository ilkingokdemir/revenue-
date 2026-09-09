"""Ödeme planı: depozito → kalan bakiye varıştan X gün önce kayıtlı karttan otomatik tahsilat + hatırlatma; grup 'ödemeyi bölüş' linkleri."""
import asyncio
import logging
import os
import secrets
import uuid
from datetime import date as _date, datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
now_iso = lambda: datetime.now(timezone.utc).isoformat()
PLAN_DEFAULTS = {"balance_auto_charge_enabled": True, "balance_charge_days_before": 7, "balance_reminder_days_before": 10, "split_pay_enabled": True}


def _stripe():
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    return stripe


async def plan_settings(db, pid: str) -> dict:
    doc = await db.be_settings.find_one({"property_id": pid}, {"_id": 0}) or {}
    return {**PLAN_DEFAULTS, **{k: doc[k] for k in PLAN_DEFAULTS if k in doc}}


async def compute_deposit(db, booking: dict) -> float:
    """Sepetteki plan deposit_pct'lerine göre depozito (0 → depozito yok)."""
    q = {"cart_ref": booking["cart_ref"]} if booking.get("cart_ref") else {"id": booking["id"]}
    rows = await db.bookings.find(q, {"_id": 0, "rate_plan_id": 1, "total_price": 1}).to_list(50)
    plans = {p["id"]: p for p in await db.be_rate_plans.find({"id": {"$in": [r.get("rate_plan_id") for r in rows if r.get("rate_plan_id")]}}, {"_id": 0, "id": 1, "deposit_pct": 1}).to_list(50)}
    dep = sum(float(r.get("total_price") or 0) * float(plans.get(r.get("rate_plan_id"), {}).get("deposit_pct") or 0) / 100.0 for r in rows)
    return round(dep, 2)


async def schedule_balance(db, booking: dict, paid_amount: float, pm_id: Optional[str], customer_id: Optional[str]):
    """Depozito ödendi → bakiye planı yaz (kart kayıtlıysa otomatik tahsilat tarihi)."""
    total = float(booking.get("cart_total") or booking.get("total_price") or 0)
    balance = round(total - paid_amount, 2)
    st = await plan_settings(db, booking["property_id"])
    ci = _date.fromisoformat(booking["check_in"][:10])
    due = max(_date.today(), ci - timedelta(days=int(st["balance_charge_days_before"])))
    upd = {"payment_status": "deposit_paid", "deposit_paid": paid_amount, "balance_due": balance, "balance_due_date": due.isoformat(),
           "balance_status": "scheduled" if (pm_id and st["balance_auto_charge_enabled"]) else "manual",
           "stripe_customer_id": customer_id, "stripe_pm_id": pm_id,
           "payment_schedule": [{"label": "deposit", "amount": paid_amount, "status": "paid", "at": now_iso()},
                                {"label": "balance", "amount": balance, "status": "scheduled" if pm_id else "manual", "due_date": due.isoformat()}]}
    await db.bookings.update_one({"id": booking["id"]}, {"$set": upd})
    if booking.get("cart_ref"):
        await db.bookings.update_many({"cart_ref": booking["cart_ref"], "id": {"$ne": booking["id"]}}, {"$set": {"payment_status": "deposit_paid"}})
    return upd


async def schedule_installments(db, booking: dict, paid_amount: float, pm_id: Optional[str], customer_id: Optional[str], count: int = 3):
    """Taksit: ilk taksit ödendi → kalan taksitler aylık (son taksit en geç check_in − charge_days)."""
    total = float(booking.get("cart_total") or booking.get("total_price") or 0)
    st = await plan_settings(db, booking["property_id"])
    ci = _date.fromisoformat(booking["check_in"][:10])
    last_day = max(_date.today(), ci - timedelta(days=int(st["balance_charge_days_before"])))
    remaining = count - 1
    per = round((total - paid_amount) / remaining, 2) if remaining else 0
    sched = [{"label": "installment_1", "amount": paid_amount, "status": "paid", "at": now_iso()}]
    for i in range(1, count):
        due = min(last_day, _date.today() + timedelta(days=30 * i))
        amt = round(total - paid_amount - per * (remaining - 1), 2) if i == count - 1 else per
        sched.append({"label": f"installment_{i + 1}", "amount": amt, "status": "scheduled" if pm_id else "manual", "due_date": due.isoformat()})
    upd = {"payment_status": "deposit_paid", "payment_plan": "installments", "installments_count": count, "deposit_paid": paid_amount, "balance_due": round(total - paid_amount, 2),
           "balance_due_date": sched[1]["due_date"] if len(sched) > 1 else None, "balance_status": "scheduled" if (pm_id and st["balance_auto_charge_enabled"]) else "manual",
           "stripe_customer_id": customer_id, "stripe_pm_id": pm_id, "payment_schedule": sched}
    await db.bookings.update_one({"id": booking["id"]}, {"$set": upd})
    if booking.get("cart_ref"):
        await db.bookings.update_many({"cart_ref": booking["cart_ref"], "id": {"$ne": booking["id"]}}, {"$set": {"payment_status": "deposit_paid"}})
    return upd


def _pay_link(pid: str, ref: str, email: str) -> str:
    base = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("FRONTEND_URL") or ""
    return f"{base}/pay-balance/{ref}?email={email}"


async def _email(db, to: str, subject: str, html: str, kind: str, meta: dict):
    from routes.platform_ext.mailer import send_email
    return await send_email(db, to, subject, html, kind=kind, meta=meta)


async def charge_balance(db, b: dict, trigger: str = "auto", entry_idx: Optional[int] = None) -> dict:
    """Kayıtlı karttan off-session bakiye (veya tek taksit) tahsilatı."""
    sched = b.get("payment_schedule") or []
    entry = sched[entry_idx] if entry_idx is not None and entry_idx < len(sched) else None
    amount = float(entry["amount"]) if entry else float(b.get("balance_due") or 0)
    if amount <= 0:
        return {"ok": False, "reason": "no_balance"}
    if not (b.get("stripe_customer_id") and b.get("stripe_pm_id")):
        return {"ok": False, "reason": "no_card_on_file"}
    stripe = _stripe()
    if not stripe.api_key:
        return {"ok": False, "reason": "stripe_not_configured"}
    try:
        pi = stripe.PaymentIntent.create(amount=int(round(amount * 100)), currency=(b.get("currency") or "GBP").lower(), customer=b["stripe_customer_id"], payment_method=b["stripe_pm_id"],
                                         off_session=True, confirm=True, description=f"Balance {b['booking_ref']}", metadata={"booking_ref": b["booking_ref"], "kind": "balance"})
        ok = pi.status == "succeeded"
        err = "" if ok else pi.status
    except Exception as e:  # kart reddi / 3DS gerekli
        ok, err, pi = False, str(getattr(e, "user_message", None) or e)[:200], None
    now = now_iso()
    if ok:
        new_balance = round(float(b.get("balance_due") or 0) - amount, 2)
        if entry is not None:
            sched[entry_idx] = {**entry, "status": "paid", "at": now, "pi_id": pi.id}
        nxt = next((e for e in sched if e.get("status") == "scheduled"), None)
        full = new_balance <= 0.5
        upd = {"balance_due": max(0.0, new_balance), "paid_amount": round(float(b.get("paid_amount") or b.get("deposit_paid") or 0) + amount, 2), "payment_schedule": sched or b.get("payment_schedule") or [],
               "payment_status": "paid" if full else "partial", "balance_status": "paid" if full else "scheduled", "balance_due_date": None if full else (nxt or {}).get("due_date"), "balance_pi_id": pi.id}
        if full:
            upd["balance_paid_at"] = now
        await db.bookings.update_one({"id": b["id"]}, {"$set": upd, "$push": {"payment_events": {"kind": "installment_charged" if entry else "balance_charged", "amount": amount, "trigger": trigger, "at": now}}})
        if full:
            await db.bookings.update_many({"cart_ref": b.get("cart_ref") or "__none__"}, {"$set": {"payment_status": "paid"}})
        cur = b.get("currency", "GBP")
        tail = "Rezervasyonunuz tamamen ödenmiştir." if full else f"Kalan: {cur} {max(0.0, new_balance):.2f}"
        await _email(db, b["guest_email"], f"{'Taksit' if entry else 'Kalan bakiye'} tahsil edildi — {b['booking_ref']}", f"<p>{b.get('guest_name', '')}, {cur} {amount:.2f} kayıtlı kartınızdan tahsil edildi. {tail}</p>", "balance_charged", {"booking_ref": b["booking_ref"]})
    else:
        await db.bookings.update_one({"id": b["id"]}, {"$set": {"balance_status": "failed", "balance_last_error": err, "balance_failed_at": now},
                                                       "$push": {"payment_events": {"kind": "balance_failed", "amount": amount, "error": err, "trigger": trigger, "at": now}}})
        link = _pay_link(b["property_id"], b["booking_ref"], b["guest_email"])
        await _email(db, b["guest_email"], f"Ödeme alınamadı — {b['booking_ref']}", f"<p>Kalan bakiye ({b.get('currency', 'GBP')} {amount:.2f}) kartınızdan tahsil edilemedi ({err}). Lütfen <a href='{link}'>buradan</a> ödeyin.</p>", "balance_failed", {"booking_ref": b["booking_ref"]})
        await db.notifications.insert_one({"id": str(uuid.uuid4()), "property_id": b["property_id"], "type": "balance_failed", "title": f"Bakiye tahsilatı başarısız: {b['booking_ref']}", "body": f"{b.get('guest_name')} · {b.get('currency', 'GBP')} {amount:.2f} · {err}", "read": False, "created_at": now})
    return {"ok": ok, "error": err, "amount": amount}


async def run_payment_schedules(db, pid: Optional[str] = None) -> dict:
    today = _date.today().isoformat()
    q = {"status": {"$nin": ["cancelled", "no_show"]}, "balance_due": {"$gt": 0}, "payment_status": {"$in": ["deposit_paid", "partial"]}}
    if pid:
        q["property_id"] = pid
    charged = failed = reminded = 0
    async for b in db.bookings.find(q, {"_id": 0}):
        st = await plan_settings(db, b["property_id"])
        ci = _date.fromisoformat(b["check_in"][:10])
        rem_day = (ci - timedelta(days=int(st["balance_reminder_days_before"]))).isoformat()
        if not b.get("balance_reminder_sent_at") and today >= rem_day and ci.isoformat() > today:
            link = _pay_link(b["property_id"], b["booking_ref"], b["guest_email"])
            auto = b.get("balance_status") == "scheduled"
            await _email(db, b["guest_email"], f"Kalan bakiye hatırlatması — {b['booking_ref']}",
                         f"<p>{b.get('guest_name', '')}, {b.get('currency', 'GBP')} {float(b['balance_due']):.2f} kalan bakiyeniz {b.get('balance_due_date')} tarihinde " + ("kayıtlı kartınızdan otomatik tahsil edilecek." if auto else f"ödenmelidir. <a href='{link}'>Şimdi öde</a>") + "</p>", "balance_reminder", {"booking_ref": b["booking_ref"]})
            await db.bookings.update_one({"id": b["id"]}, {"$set": {"balance_reminder_sent_at": now_iso()}})
            reminded += 1
        if b.get("balance_status") == "scheduled" and st["balance_auto_charge_enabled"]:
            if b.get("payment_plan") == "installments":
                for idx, e in enumerate(b.get("payment_schedule") or []):
                    if e.get("status") == "scheduled" and (e.get("due_date") or "9999") <= today:
                        r = await charge_balance(db, b, "auto", entry_idx=idx)
                        charged += 1 if r["ok"] else 0; failed += 0 if r["ok"] else 1
                        break
            elif (b.get("balance_due_date") or "9999") <= today:
                r = await charge_balance(db, b, "auto")
                charged += 1 if r["ok"] else 0; failed += 0 if r["ok"] else 1
    return {"charged": charged, "failed": failed, "reminded": reminded}


async def balance_charge_loop(db, interval_seconds: int = 21600):
    await asyncio.sleep(120)
    while True:
        try:
            r = await run_payment_schedules(db)
            if any(r.values()):
                logger.info(f"balance_charge_loop: {r}")
        except Exception as e:
            logger.warning(f"balance_charge_loop error: {e}")
        await asyncio.sleep(interval_seconds)


def create_payment_plans_router(db, require_roles):
    router = APIRouter(tags=["payment-plans"])
    ROLES = ("admin", "manager", "revenue_manager", "front_desk")

    async def _booking(ref: str, email: str):
        b = await db.bookings.find_one({"$or": [{"booking_ref": ref}, {"id": ref}]}, {"_id": 0})
        if not b or (b.get("guest_email") or "").lower() != (email or "").lower():
            raise HTTPException(404, "Rezervasyon bulunamadı")
        return b

    @router.get("/booking/payment-schedule/{ref}")
    async def get_schedule(ref: str, email: str):
        b = await _booking(ref, email)
        return {"booking_ref": b["booking_ref"], "id": b["id"], "property_id": b["property_id"], "currency": b.get("currency", "GBP"), "total": b.get("cart_total") or b.get("total_price"),
                "payment_status": b.get("payment_status"), "deposit_paid": b.get("deposit_paid", 0), "balance_due": b.get("balance_due", 0), "balance_due_date": b.get("balance_due_date"),
                "balance_status": b.get("balance_status"), "card_on_file": bool(b.get("stripe_pm_id")), "schedule": b.get("payment_schedule") or [], "events": b.get("payment_events") or [],
                "split": [{k: s.get(k) for k in ("email", "amount", "status", "paid_at")} for s in await db.split_payments.find({"booking_id": b["id"]}, {"_id": 0}).to_list(20)]}

    @router.post("/booking/payment-schedule/{ref}/pay-now")
    async def pay_now(ref: str, data: dict):
        """Misafir bakiyeyi kendisi öder → PaymentIntent (Payment Element için client_secret)."""
        b = await _booking(ref, str(data.get("email") or ""))
        amount = float(b.get("balance_due") or 0)
        if amount <= 0:
            raise HTTPException(400, "Ödenecek bakiye yok")
        stripe = _stripe()
        if not stripe.api_key:
            raise HTTPException(503, "Stripe yapılandırılmamış")
        pi = stripe.PaymentIntent.create(amount=int(round(amount * 100)), currency=(b.get("currency") or "GBP").lower(), automatic_payment_methods={"enabled": True},
                                         metadata={"booking_ref": b["booking_ref"], "kind": "balance"}, receipt_email=b["guest_email"])
        await db.bookings.update_one({"id": b["id"]}, {"$set": {"balance_pi_id": pi.id}})
        return {"client_secret": pi.client_secret, "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY", ""), "amount": amount, "currency": b.get("currency", "GBP")}

    @router.post("/booking/payment-schedule/{ref}/confirm")
    async def confirm_pay_now(ref: str, data: dict):
        b = await _booking(ref, str(data.get("email") or ""))
        stripe = _stripe()
        if not b.get("balance_pi_id"):
            raise HTTPException(404, "Ödeme yok")
        pi = stripe.PaymentIntent.retrieve(b["balance_pi_id"])
        if pi.status != "succeeded":
            return {"paid": False, "status": pi.status}
        now = now_iso()
        await db.bookings.update_one({"id": b["id"]}, {"$set": {"payment_status": "paid", "balance_due": 0, "balance_status": "paid", "balance_paid_at": now, "paid_amount": round(float(b.get("deposit_paid") or 0) + pi.amount_received / 100.0, 2)},
                                                       "$push": {"payment_events": {"kind": "balance_paid_by_guest", "amount": pi.amount_received / 100.0, "at": now}}})
        await db.bookings.update_many({"cart_ref": b.get("cart_ref") or "__none__"}, {"$set": {"payment_status": "paid"}})
        return {"paid": True}

    @router.get("/booking/payment-schedules/{pid}")
    async def list_schedules(pid: str, _u: dict = Depends(require_roles(*ROLES))):
        rows = await db.bookings.find({"property_id": pid, "balance_due": {"$gt": 0}, "status": {"$nin": ["cancelled", "no_show"]}},
                                      {"_id": 0, "id": 1, "booking_ref": 1, "guest_name": 1, "guest_email": 1, "check_in": 1, "currency": 1, "cart_total": 1, "total_price": 1, "deposit_paid": 1, "balance_due": 1, "balance_due_date": 1, "balance_status": 1, "balance_last_error": 1, "stripe_pm_id": 1, "balance_reminder_sent_at": 1}).sort("check_in", 1).to_list(200)
        for r in rows:
            r["card_on_file"] = bool(r.pop("stripe_pm_id", None))
        return {"settings": await plan_settings(db, pid), "items": rows, "counts": {"scheduled": sum(1 for r in rows if r.get("balance_status") == "scheduled"), "failed": sum(1 for r in rows if r.get("balance_status") == "failed"), "manual": sum(1 for r in rows if r.get("balance_status") in (None, "manual"))}}

    @router.put("/booking/payment-schedules/{pid}/settings")
    async def save_settings(pid: str, data: dict, _u: dict = Depends(require_roles("admin", "manager"))):
        upd = {"balance_auto_charge_enabled": bool(data.get("balance_auto_charge_enabled", True)), "balance_charge_days_before": max(0, min(60, int(data.get("balance_charge_days_before") or 7))),
               "balance_reminder_days_before": max(0, min(90, int(data.get("balance_reminder_days_before") or 10))), "split_pay_enabled": bool(data.get("split_pay_enabled", True))}
        await db.be_settings.update_one({"property_id": pid}, {"$set": upd, "$setOnInsert": {"property_id": pid}}, upsert=True)
        return upd

    @router.post("/booking/payment-schedules/{pid}/run")
    async def run_now(pid: str, _u: dict = Depends(require_roles("admin", "manager"))):
        return await run_payment_schedules(db, pid)

    @router.post("/booking/payment-schedules/{pid}/{booking_id}/charge")
    async def charge_now(pid: str, booking_id: str, _u: dict = Depends(require_roles("admin", "manager"))):
        b = await db.bookings.find_one({"id": booking_id, "property_id": pid}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Rezervasyon yok")
        return await charge_balance(db, b, f"manual:{_u.get('email')}")

    # ---------------- Ödemeyi bölüş ----------------
    @router.post("/booking/{ref}/split")
    async def create_split(ref: str, data: dict):
        b = await _booking(ref, str(data.get("email") or ""))
        st = await plan_settings(db, b["property_id"])
        if not st["split_pay_enabled"]:
            raise HTTPException(403, "Bölüşme kapalı")
        emails = [str(e).strip().lower() for e in (data.get("emails") or []) if "@" in str(e)]
        if not (1 <= len(emails) <= 10):
            raise HTTPException(422, "1-10 e-posta")
        amount = float(b.get("balance_due") if b.get("balance_due") else (b.get("cart_total") or b.get("total_price") or 0))
        if b.get("payment_status") == "paid" or amount <= 0:
            raise HTTPException(400, "Bölüşülecek ödenmemiş tutar yok")
        existing = await db.split_payments.count_documents({"booking_id": b["id"], "status": {"$ne": "cancelled"}})
        if existing:
            raise HTTPException(409, "Bu rezervasyon için bölüşme zaten oluşturuldu")
        parts = len(emails) + (1 if data.get("include_me", True) else 0)
        share = round(amount / parts, 2)
        base = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("FRONTEND_URL") or ""
        docs = []
        allp = ([b["guest_email"].lower()] if data.get("include_me", True) else []) + emails
        for i, e in enumerate(allp):
            amt = round(amount - share * (parts - 1), 2) if i == parts - 1 else share
            d = {"id": str(uuid.uuid4()), "token": secrets.token_urlsafe(16), "booking_id": b["id"], "booking_ref": b["booking_ref"], "property_id": b["property_id"], "email": e, "amount": amt, "currency": b.get("currency", "GBP"), "status": "pending", "created_at": now_iso()}
            docs.append(d)
            await _email(db, e, f"{b.get('guest_name', '')} sizinle rezervasyon ödemesini bölüştü — {b['booking_ref']}", f"<p>Payınız: <b>{d['currency']} {amt:.2f}</b>. <a href='{base}/pay-share/{d['token']}'>Ödemek için tıklayın</a></p>", "split_invite", {"booking_ref": b["booking_ref"]})
        if docs:
            await db.split_payments.insert_many([dict(x) for x in docs])
        await db.bookings.update_one({"id": b["id"]}, {"$set": {"split_pay": {"parts": parts, "share": share, "created_at": now_iso()}}})
        return {"ok": True, "parts": parts, "share": share, "links": [{"email": d["email"], "amount": d["amount"], "url": f"{base}/pay-share/{d['token']}", "token": d["token"]} for d in docs]}

    @router.get("/booking/split/{token}")
    async def split_get(token: str):
        s = await db.split_payments.find_one({"token": token}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Link geçersiz")
        b = await db.bookings.find_one({"id": s["booking_id"]}, {"_id": 0, "guest_name": 1, "check_in": 1, "check_out": 1, "room_name": 1, "property_id": 1}) or {}
        prop = await db.properties.find_one({"id": s["property_id"]}, {"_id": 0, "name": 1}) or {}
        others = await db.split_payments.find({"booking_id": s["booking_id"]}, {"_id": 0, "email": 1, "amount": 1, "status": 1}).to_list(20)
        return {**s, "host_name": b.get("guest_name"), "check_in": b.get("check_in"), "check_out": b.get("check_out"), "room_name": b.get("room_name"), "property_name": prop.get("name"), "parts": others}

    @router.post("/booking/split/{token}/intent")
    async def split_intent(token: str):
        s = await db.split_payments.find_one({"token": token}, {"_id": 0})
        if not s or s["status"] == "paid":
            raise HTTPException(400, "Bu pay zaten ödendi veya link geçersiz")
        stripe = _stripe()
        if not stripe.api_key:
            raise HTTPException(503, "Stripe yapılandırılmamış")
        pi = stripe.PaymentIntent.create(amount=int(round(float(s["amount"]) * 100)), currency=s["currency"].lower(), automatic_payment_methods={"enabled": True}, receipt_email=s["email"], metadata={"booking_ref": s["booking_ref"], "kind": "split", "split_id": s["id"]})
        await db.split_payments.update_one({"id": s["id"]}, {"$set": {"pi_id": pi.id}})
        return {"client_secret": pi.client_secret, "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY", ""), "amount": s["amount"], "currency": s["currency"]}

    @router.post("/booking/split/{token}/confirm")
    async def split_confirm(token: str, data: Optional[dict] = None):
        s = await db.split_payments.find_one({"token": token}, {"_id": 0})
        if not s or not s.get("pi_id"):
            raise HTTPException(404, "Ödeme yok")
        stripe = _stripe()
        pi = stripe.PaymentIntent.retrieve(s["pi_id"])
        if pi.status != "succeeded" and not (data or {}).get("_test_force"):
            return {"paid": False, "status": pi.status}
        return await _mark_split_paid(s)

    async def _mark_split_paid(s: dict):
        now = now_iso()
        await db.split_payments.update_one({"id": s["id"]}, {"$set": {"status": "paid", "paid_at": now}})
        remaining = await db.split_payments.count_documents({"booking_id": s["booking_id"], "status": {"$ne": "paid"}})
        b = await db.bookings.find_one({"id": s["booking_id"]}, {"_id": 0})
        paid_sum = sum(float(x["amount"]) for x in await db.split_payments.find({"booking_id": s["booking_id"], "status": "paid"}, {"_id": 0, "amount": 1}).to_list(20))
        total = float(b.get("cart_total") or b.get("total_price") or 0)
        upd = {"paid_amount": round(float(b.get("deposit_paid") or 0) + paid_sum, 2), "balance_due": max(0.0, round(total - float(b.get("deposit_paid") or 0) - paid_sum, 2))}
        upd["payment_status"] = "paid" if remaining == 0 or upd["balance_due"] <= 0.5 else "partial"
        if upd["payment_status"] == "paid":
            upd["balance_status"] = "paid"
        await db.bookings.update_one({"id": s["booking_id"]}, {"$set": upd, "$push": {"payment_events": {"kind": "split_paid", "email": s["email"], "amount": s["amount"], "at": now}}})
        return {"paid": True, "remaining_parts": remaining, "booking_payment_status": upd["payment_status"]}

    @router.post("/booking/split/{token}/mark-paid-test")
    async def split_mark_test(token: str, _u: dict = Depends(require_roles("admin"))):
        """Test/MOCK: Stripe olmadan payı ödenmiş işaretle (admin)."""
        s = await db.split_payments.find_one({"token": token}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Link geçersiz")
        return await _mark_split_paid(s)

    return router
