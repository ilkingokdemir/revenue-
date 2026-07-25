"""
Invoice Reminder Automation — Mews parity.
Overdue city-ledger invoices get escalating reminder emails with a pay link.
L1: 1-7 days overdue, L2: 8-21, L3: 22+ (manager alert). Mock email fallback.
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, date
from typing import Dict
import uuid
import os
import logging

try:
    import resend
except Exception:
    resend = None

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _level(days_overdue: int) -> int:
    if days_overdue >= 22:
        return 3
    if days_overdue >= 8:
        return 2
    return 1


LEVEL_TONE = {
    1: ("Nazik hatırlatma", "aşağıdaki faturanın vadesi geçmiştir. Uygun olduğunuzda ödemenizi rica ederiz."),
    2: ("İkinci hatırlatma", "faturanın vadesi üzerinden bir süre geçti. En kısa sürede ödemenizi önemle rica ederiz."),
    3: ("Son hatırlatma", "fatura ciddi şekilde gecikmiştir. Ödeme yapılmazsa hesabınız askıya alınabilir."),
}


async def _send_reminder_email(to_email: str, company: str, inv: Dict, level: int, pay_url: str) -> str:
    if not to_email:
        return "no_email"
    title, tone = LEVEL_TONE[level]
    balance = round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)
    subject = f"{title}: Fatura {inv.get('invoice_number')} — £{balance}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#292524;">
      <h2 style="color:{'#b45309' if level < 3 else '#b91c1c'};">{title}</h2>
      <p>Sayın {company} yetkilisi, {tone}</p>
      <div style="background:#f5f5f4;border-radius:12px;padding:16px 20px;margin:16px 0;">
        <p style="margin:0;"><b>Fatura:</b> {inv.get('invoice_number')}</p>
        <p style="margin:4px 0 0;"><b>Vade:</b> {inv.get('due_date')}</p>
        <p style="margin:4px 0 0;font-size:18px;"><b>Kalan bakiye: £{balance}</b></p>
      </div>
      <a href="{pay_url}" style="background:#059669;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;display:inline-block;font-weight:bold;">Şimdi Öde</a>
      <p style="font-size:12px;color:#78716c;margin-top:16px;">Ödemeyi yaptıysanız bu e-postayı dikkate almayın.</p>
    </div>"""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not resend or not api_key or api_key.startswith("re_1234"):
        logger.info(f"[MOCK EMAIL] Invoice reminder L{level} to {to_email}: {inv.get('invoice_number')}")
        return "mock"
    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": os.environ.get("RESEND_FROM", "MyHotelBox <onboarding@resend.dev>"),
            "to": [to_email], "subject": subject, "html": html})
        return "sent"
    except Exception as e:
        logger.warning(f"Invoice reminder email failed: {e}")
        return "failed"


async def run_invoice_reminders(db, base_url: str = "") -> Dict:
    today = date.today()
    sent = skipped = 0
    async for inv in db.city_ledger_invoices.find(
            {"status": {"$nin": ["paid", "void", "cancelled"]}}, {"_id": 0}):
        due = inv.get("due_date") or ""
        if not due or due >= today.isoformat():
            continue
        days_overdue = (today - date.fromisoformat(due)).days
        level = _level(days_overdue)
        already = await db.invoice_reminders.find_one(
            {"invoice_id": inv["id"], "level": level}, {"_id": 0, "id": 1})
        if already:
            skipped += 1
            continue
        company = await db.city_ledger_companies.find_one(
            {"id": inv.get("company_id")}, {"_id": 0, "name": 1, "email": 1})
        pay_url = f"{base_url or 'https://pay.myhotelbox.app'}/pay-invoice/{inv['id']}"
        status = await _send_reminder_email(
            (company or {}).get("email", ""), (company or {}).get("name", "Müşteri"),
            inv, level, pay_url)
        balance = round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)
        await db.invoice_reminders.insert_one({
            "id": str(uuid.uuid4()), "invoice_id": inv["id"],
            "invoice_number": inv.get("invoice_number"),
            "company_id": inv.get("company_id"),
            "company_name": (company or {}).get("name", ""),
            "level": level, "days_overdue": days_overdue,
            "balance": balance, "email_status": status,
            "pay_url": pay_url, "created_at": _now()})
        sent += 1
        if level == 3:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()), "type": "error",
                "title": "Ciddi Gecikmiş Fatura!",
                "message": f"{(company or {}).get('name', '')} — {inv.get('invoice_number')} faturası {days_overdue} gündür gecikmiş (£{balance}). Son hatırlatma gönderildi.",
                "category": "finance", "target_user": "", "target_role": "manager",
                "link_to": "city-ledger", "priority": "high",
                "read": False, "created_by": "Invoice Reminder Bot", "created_at": _now()})
    return {"ok": True, "reminders_sent": sent, "skipped_already_sent": skipped}


def create_invoice_reminders_router(db, require_roles):
    router = APIRouter()

    @router.get("/invoice-reminders")
    async def status(limit: int = 50,
                     current_user: dict = Depends(require_roles("admin", "manager"))):
        today = date.today().isoformat()
        overdue = []
        async for inv in db.city_ledger_invoices.find(
                {"status": {"$nin": ["paid", "void", "cancelled"]},
                 "due_date": {"$lt": today, "$ne": None}}, {"_id": 0}):
            days = (date.today() - date.fromisoformat(inv["due_date"])).days
            comp = await db.city_ledger_companies.find_one(
                {"id": inv.get("company_id")}, {"_id": 0, "name": 1, "email": 1})
            overdue.append({**inv, "days_overdue": days, "level": _level(days),
                            "company_name": (comp or {}).get("name", ""),
                            "company_email": (comp or {}).get("email", ""),
                            "balance": round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)})
        overdue.sort(key=lambda x: -x["days_overdue"])
        log = await db.invoice_reminders.find({}, {"_id": 0}) \
            .sort("created_at", -1).to_list(int(limit))
        return {"overdue_invoices": overdue,
                "summary": {"overdue_count": len(overdue),
                            "overdue_balance": round(sum(o["balance"] for o in overdue), 2),
                            "reminders_sent_total": await db.invoice_reminders.count_documents({})},
                "reminder_log": log}

    @router.post("/invoice-reminders/run")
    async def run_now(current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_invoice_reminders(db)

    @router.post("/invoice-reminders/{invoice_id}/send")
    async def send_one(invoice_id: str,
                       current_user: dict = Depends(require_roles("admin", "manager"))):
        inv = await db.city_ledger_invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Fatura bulunamadı")
        if inv.get("status") in ("paid", "void", "cancelled"):
            raise HTTPException(409, "Fatura zaten kapalı")
        due = inv.get("due_date") or date.today().isoformat()
        days = max((date.today() - date.fromisoformat(due)).days, 0)
        level = _level(days) if days > 0 else 1
        comp = await db.city_ledger_companies.find_one(
            {"id": inv.get("company_id")}, {"_id": 0, "name": 1, "email": 1})
        pay_url = f"https://pay.myhotelbox.app/pay-invoice/{inv['id']}"
        status = await _send_reminder_email(
            (comp or {}).get("email", ""), (comp or {}).get("name", "Müşteri"), inv, level, pay_url)
        balance = round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)
        await db.invoice_reminders.insert_one({
            "id": str(uuid.uuid4()), "invoice_id": inv["id"],
            "invoice_number": inv.get("invoice_number"),
            "company_id": inv.get("company_id"),
            "company_name": (comp or {}).get("name", ""),
            "level": level, "days_overdue": days, "balance": balance,
            "email_status": status, "pay_url": pay_url,
            "manual": True, "sent_by": current_user.get("name", ""),
            "created_at": _now()})
        return {"ok": True, "email_status": status, "level": level}

    router.run_invoice_reminders_internal = run_invoice_reminders
    return router
