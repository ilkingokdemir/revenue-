"""
AR Mutabakat Agent'ı (Mews Accounts Receivable paritesi) — gelen banka
ödemelerini açık city-ledger faturalarıyla akıllı eşleştirir:
  - referansta fatura no (CL-YYYY-NNN, birden çok olabilir → toplu)
  - tam tutar eşleşmesi (şirket bazlı veya global tekil)
  - alt-küme toplamı (bir ödeme birden çok faturayı kapatır)
  - kısmi ödeme (tek açık faturaya kısmi uygulanır)
  - fazla ödeme (bakiye kapanır, kalan → ar_credits alacak kaydı)
Collections: ar_incoming_payments, ar_match_log, ar_credits
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from typing import Dict, List, Optional
from itertools import combinations
import uuid
import re
import logging

logger = logging.getLogger(__name__)

_INV_RE = re.compile(r"CL-\d{4}-\d{3,}", re.IGNORECASE)
_TOL = 0.011


def _now():
    return datetime.now(timezone.utc).isoformat()


def _bal(inv: Dict) -> float:
    return round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)


async def _apply_to_invoice(db, inv: Dict, amount: float, payment_id: str) -> Dict:
    """Apply `amount` to invoice; returns {applied, invoice_id, new_status}."""
    bal = _bal(inv)
    applied = round(min(amount, bal), 2)
    new_paid = round(float(inv.get("paid_amount", 0)) + applied, 2)
    new_status = "paid" if new_paid >= float(inv.get("amount", 0)) - _TOL else "partial"
    upd = {"paid_amount": new_paid, "status": new_status}
    if new_status == "paid":
        upd["paid_at"] = _now()
    await db.city_ledger_invoices.update_one({"id": inv["id"]}, {"$set": upd, "$push": {
        "payments": {"amount": applied, "at": _now(), "source": "ar_agent", "payment_id": payment_id}}})
    return {"applied": applied, "invoice_id": inv["id"], "invoice_number": inv.get("invoice_number"), "new_status": new_status}


async def _resolve_company(db, payer: str) -> Optional[Dict]:
    if not payer:
        return None
    rows = await db.city_ledger_companies.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    p = payer.lower().strip()
    for r in rows:
        n = (r.get("name") or "").lower().strip()
        if n and (n in p or p in n):
            return r
    return None


def _subset_match(invoices: List[Dict], amount: float) -> Optional[List[Dict]]:
    """Find subset of invoices whose balances sum to `amount` (max 6 invoices)."""
    open_invs = [i for i in invoices if _bal(i) > _TOL]
    if len(open_invs) > 12:
        open_invs = sorted(open_invs, key=_bal, reverse=True)[:12]
    for k in range(2, min(len(open_invs), 6) + 1):
        for combo in combinations(open_invs, k):
            if abs(sum(_bal(i) for i in combo) - amount) < _TOL:
                return list(combo)
    return None


async def _match_one(db, pmt: Dict) -> Dict:
    amount = round(float(pmt.get("amount", 0)), 2)
    ref = pmt.get("reference", "") or ""
    result = {"payment_id": pmt["id"], "matched_by": None, "applications": [], "credit": 0.0, "needs_review": None}

    # 1) Invoice number(s) in reference → direct/batch
    inv_nos = list(dict.fromkeys(m.upper() for m in _INV_RE.findall(ref)))
    if inv_nos:
        invs = await db.city_ledger_invoices.find(
            {"invoice_number": {"$in": inv_nos}, "status": {"$ne": "paid"}}, {"_id": 0}).to_list(20)
        if invs:
            remaining = amount
            for inv in sorted(invs, key=lambda i: i.get("due_date", "")):
                if remaining < _TOL:
                    break
                app = await _apply_to_invoice(db, inv, remaining, pmt["id"])
                result["applications"].append(app)
                remaining = round(remaining - app["applied"], 2)
            result["matched_by"] = "reference" if len(invs) == 1 else "reference_batch"
            if remaining > _TOL:
                result["credit"] = remaining
            return result

    # 2) Company resolution
    company = await _resolve_company(db, pmt.get("payer_name", ""))
    scope = {"status": {"$ne": "paid"}}
    if company:
        scope["company_id"] = company["id"]
    open_invs = await db.city_ledger_invoices.find(scope, {"_id": 0}).to_list(300)
    open_invs = [i for i in open_invs if _bal(i) > _TOL]

    # 3) Exact amount == single invoice balance
    exact = [i for i in open_invs if abs(_bal(i) - amount) < _TOL]
    if len(exact) == 1 or (len(exact) > 1 and company):
        app = await _apply_to_invoice(db, exact[0], amount, pmt["id"])
        result["applications"].append(app)
        result["matched_by"] = "exact_amount"
        return result

    if company:
        # 4) Batch subset-sum within company
        subset = _subset_match(open_invs, amount)
        if subset:
            for inv in subset:
                result["applications"].append(await _apply_to_invoice(db, inv, _bal(inv), pmt["id"]))
            result["matched_by"] = "subset_batch"
            return result
        # 5) Partial / overpayment when company has exactly 1 open invoice
        if len(open_invs) == 1:
            inv = open_invs[0]
            bal = _bal(inv)
            app = await _apply_to_invoice(db, inv, amount, pmt["id"])
            result["applications"].append(app)
            if amount < bal - _TOL:
                result["matched_by"] = "partial"
            else:
                result["matched_by"] = "overpayment" if amount > bal + _TOL else "exact_amount"
                if amount > bal + _TOL:
                    result["credit"] = round(amount - bal, 2)
            return result

    result["needs_review"] = ("Şirket çözümlenemedi" if not company else "Tutar hiçbir fatura/kombinasyonla eşleşmedi")
    return result


async def _record_credit(db, pmt: Dict, amount: float):
    company = await _resolve_company(db, pmt.get("payer_name", ""))
    await db.ar_credits.insert_one({
        "id": str(uuid.uuid4()), "company_id": (company or {}).get("id", ""),
        "company_name": (company or {}).get("name", pmt.get("payer_name", "")),
        "amount": amount, "currency": pmt.get("currency", "GBP"),
        "source_payment_id": pmt["id"], "status": "open", "created_at": _now(),
    })


async def run_match_internal(db) -> Dict:
    pending = await db.ar_incoming_payments.find({"status": "unapplied"}, {"_id": 0}).to_list(200)
    matched, review, credits = 0, 0, 0.0
    for pmt in pending:
        try:
            res = await _match_one(db, pmt)
        except Exception as e:
            logger.exception("AR match failed for %s: %s", pmt["id"], e)
            continue
        log = {"id": str(uuid.uuid4()), **res, "amount": pmt.get("amount"),
               "payer_name": pmt.get("payer_name"), "reference": pmt.get("reference"), "created_at": _now()}
        await db.ar_match_log.insert_one(log)
        if res["applications"]:
            matched += 1
            new_status = "applied" if res["credit"] < _TOL else "applied_with_credit"
            await db.ar_incoming_payments.update_one({"id": pmt["id"]}, {"$set": {
                "status": new_status, "matched_by": res["matched_by"],
                "applied_invoices": [a["invoice_number"] for a in res["applications"]], "matched_at": _now()}})
            if res["credit"] > _TOL:
                await _record_credit(db, pmt, res["credit"])
                credits += res["credit"]
        else:
            review += 1
            await db.ar_incoming_payments.update_one({"id": pmt["id"]}, {"$set": {
                "status": "needs_review", "review_reason": res["needs_review"]}})
    return {"scanned": len(pending), "matched": matched, "needs_review": review, "credits_created": round(credits, 2)}


def create_ar_recon_router(db, require_roles):
    router = APIRouter(prefix="/ar-agent")
    router.run_match_internal = lambda: run_match_internal(db)

    @router.post("/payments")
    async def record_payment(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        amount = float(data.get("amount") or 0)
        if amount <= 0:
            raise HTTPException(400, "amount > 0 olmalı")
        doc = {
            "id": str(uuid.uuid4()),
            "payer_name": (data.get("payer_name") or "").strip(),
            "amount": round(amount, 2),
            "currency": data.get("currency", "GBP"),
            "reference": (data.get("reference") or "").strip(),
            "received_at": data.get("received_at") or _now(),
            "status": "unapplied", "created_at": _now(),
            "created_by": current_user.get("email", ""),
        }
        await db.ar_incoming_payments.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/overview")
    async def overview(current_user: dict = Depends(require_roles("admin", "manager"))):
        payments = await db.ar_incoming_payments.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
        credits = await db.ar_credits.find({"status": "open"}, {"_id": 0}).sort("created_at", -1).to_list(50)
        log = await db.ar_match_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(30)
        open_invs = await db.city_ledger_invoices.find({"status": {"$ne": "paid"}}, {"_id": 0, "amount": 1, "paid_amount": 1}).to_list(1000)
        return {
            "payments": payments,
            "unapplied_count": sum(1 for p in payments if p.get("status") == "unapplied"),
            "needs_review_count": sum(1 for p in payments if p.get("status") == "needs_review"),
            "open_invoice_count": len(open_invs),
            "open_balance": round(sum(float(i.get("amount", 0)) - float(i.get("paid_amount", 0)) for i in open_invs), 2),
            "credits": credits,
            "credits_total": round(sum(float(c.get("amount", 0)) for c in credits), 2),
            "match_log": log,
        }

    @router.post("/match-run")
    async def match_run(current_user: dict = Depends(require_roles("admin", "manager"))):
        return await run_match_internal(db)

    @router.post("/payments/{payment_id}/apply")
    async def manual_apply(payment_id: str, data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        pmt = await db.ar_incoming_payments.find_one({"id": payment_id}, {"_id": 0})
        if not pmt:
            raise HTTPException(404, "Ödeme bulunamadı")
        if pmt.get("status") not in ("unapplied", "needs_review"):
            raise HTTPException(400, "Bu ödeme zaten uygulanmış")
        inv = await db.city_ledger_invoices.find_one({"id": data.get("invoice_id")}, {"_id": 0})
        if not inv or inv.get("status") == "paid":
            raise HTTPException(404, "Açık fatura bulunamadı")
        amount = round(float(pmt.get("amount", 0)), 2)
        app = await _apply_to_invoice(db, inv, amount, payment_id)
        credit = round(amount - app["applied"], 2)
        if credit > _TOL:
            await _record_credit(db, pmt, credit)
        await db.ar_incoming_payments.update_one({"id": payment_id}, {"$set": {
            "status": "applied" if credit < _TOL else "applied_with_credit",
            "matched_by": "manual", "applied_invoices": [app["invoice_number"]], "matched_at": _now()}})
        await db.ar_match_log.insert_one({
            "id": str(uuid.uuid4()), "payment_id": payment_id, "matched_by": "manual",
            "applications": [app], "credit": credit, "amount": amount,
            "payer_name": pmt.get("payer_name"), "reference": pmt.get("reference"),
            "created_at": _now(), "by": current_user.get("email", "")})
        return {"ok": True, "application": app, "credit": credit}

    return router
