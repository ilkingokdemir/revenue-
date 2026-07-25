"""
Bank Reconciliation Routes
Import bank statements, match against recorded transactions, flag discrepancies
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from collections import defaultdict
import uuid
import logging

logger = logging.getLogger(__name__)


def create_bank_reconciliation_router(db, require_roles):
    router = APIRouter()

    # ==================== BANK ACCOUNTS ====================

    @router.get("/accounting/bank-accounts/{property_id}")
    async def list_bank_accounts(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.bank_accounts.find({"property_id": property_id}, {"_id": 0}).to_list(20)
        if not docs:
            default = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "name": "Main Business Account",
                "bank_name": "Barclays",
                "account_number": "****1234",
                "sort_code": "20-00-00",
                "currency": "GBP",
                "opening_balance": 0,
                "current_balance": 0,
                "last_reconciled": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.bank_accounts.insert_one(default)
            default.pop("_id", None)
            return [default]
        return docs

    @router.post("/accounting/bank-accounts")
    async def create_bank_account(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        account = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "name": data.get("name", ""),
            "bank_name": data.get("bank_name", ""),
            "account_number": data.get("account_number", ""),
            "sort_code": data.get("sort_code", ""),
            "currency": data.get("currency", "GBP"),
            "opening_balance": data.get("opening_balance", 0),
            "current_balance": data.get("opening_balance", 0),
            "last_reconciled": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.bank_accounts.insert_one(account)
        account.pop("_id", None)
        return account

    @router.put("/accounting/bank-accounts/{account_id}")
    async def update_bank_account(account_id: str, updates: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.bank_accounts.update_one({"id": account_id}, {"$set": updates})
        doc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
        return doc

    # ==================== BANK TRANSACTIONS (STATEMENT IMPORT) ====================

    @router.post("/accounting/bank-transactions/import")
    async def import_bank_transactions(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        """Import bank statement transactions (CSV-parsed or manual entry)"""
        property_id = data.get("property_id")
        account_id = data.get("account_id")
        transactions = data.get("transactions", [])

        imported = 0
        duplicates = 0
        for tx in transactions:
            # Check for duplicate by date + amount + reference
            existing = await db.bank_transactions.find_one({
                "account_id": account_id,
                "date": tx.get("date"),
                "amount": tx.get("amount"),
                "reference": tx.get("reference", ""),
            })
            if existing:
                duplicates += 1
                continue

            doc = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "account_id": account_id,
                "date": tx.get("date", ""),
                "description": tx.get("description", ""),
                "reference": tx.get("reference", ""),
                "amount": tx.get("amount", 0),
                "type": "credit" if tx.get("amount", 0) > 0 else "debit",
                "balance": tx.get("balance"),
                "matched": False,
                "matched_to": None,
                "matched_type": None,
                "match_confidence": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.bank_transactions.insert_one(doc)
            imported += 1

        return {"imported": imported, "duplicates": duplicates, "total": len(transactions)}

    @router.get("/accounting/bank-transactions/{property_id}")
    async def list_bank_transactions(property_id: str, account_id: str = "", month: str = "",
                                      matched: str = "",
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if account_id:
            query["account_id"] = account_id
        if month:
            query["date"] = {"$regex": f"^{month}"}
        if matched == "true":
            query["matched"] = True
        elif matched == "false":
            query["matched"] = False
        docs = await db.bank_transactions.find(query, {"_id": 0}).sort("date", -1).to_list(500)
        return docs

    # ==================== AUTO-MATCHING ====================

    @router.post("/accounting/bank-reconciliation/auto-match/{property_id}")
    async def auto_match_transactions(property_id: str, account_id: str = "",
                                       current_user: dict = Depends(require_roles("admin", "manager"))):
        """Mews-level auto-matching: ±3 day window, name/reference token scoring,
        Stripe fee tolerance, city-ledger invoice closing, low-confidence suggestions."""
        from datetime import date as _date, timedelta as _td

        def _tokens(s: str):
            return {w for w in (s or "").lower().replace(",", " ").replace("-", " ").split() if len(w) > 2}

        def _date_window(d: str, days: int = 3):
            try:
                base = _date.fromisoformat(d)
            except (ValueError, TypeError):
                return None
            return {"$gte": (base - _td(days=days)).isoformat(),
                    "$lte": (base + _td(days=days)).isoformat()}

        def _score(base: int, tx, cand_ref: str, cand_name: str, cand_date: str):
            score = base
            ttok = _tokens(tx.get("description", "") + " " + (tx.get("reference") or ""))
            if cand_ref and cand_ref.lower() in (tx.get("reference") or "").lower() + (tx.get("description") or "").lower():
                score += 15
            if _tokens(cand_name) & ttok:
                score += 10
            if cand_date and cand_date == tx.get("date"):
                score += 5
            return min(score, 99)

        query = {"property_id": property_id, "matched": False}
        if account_id:
            query["account_id"] = account_id

        unmatched = await db.bank_transactions.find(query, {"_id": 0}).to_list(500)
        matched_count = suggested_count = invoices_closed = 0

        for tx in unmatched:
            amount = abs(tx["amount"])
            window = _date_window(tx.get("date", ""))
            candidates = []  # (confidence, matched_to, match_type, extra)

            # 1) Recorded payments (exact amount, ±3 days)
            pay_query = {"property_id": property_id, "amount": amount,
                         "payment_type": "received" if tx["amount"] > 0 else "made"}
            if window:
                pay_query["date"] = window
            async for p in db.payments.find(pay_query, {"_id": 0}).limit(5):
                candidates.append((_score(80, tx, p.get("reference", ""),
                                          p.get("counterparty", ""), p.get("date", "")),
                                   p["id"], "payment", None))

            # 2) Stripe payouts (paid transactions, fee tolerance up to 4%)
            if tx["amount"] > 0:
                async for pt in db.payment_transactions.find(
                        {"payment_status": "paid",
                         "amount": {"$gte": amount, "$lte": round(amount / 0.96, 2)}},
                        {"_id": 0}).limit(5):
                    candidates.append((_score(70, tx, pt.get("session_id", ""),
                                              pt.get("guest_name", ""), "")
                                       + (10 if abs(pt["amount"] - amount) < 0.01 else 0),
                                       pt["id"], "stripe_payment", None))

            # 3) City-ledger invoices (open balance == amount, or invoice_number in text)
            if tx["amount"] > 0:
                async for inv in db.city_ledger_invoices.find(
                        {"status": {"$nin": ["paid", "void", "cancelled"]}},
                        {"_id": 0}).limit(50):
                    balance = round(float(inv.get("amount", 0)) - float(inv.get("paid_amount", 0)), 2)
                    num = (inv.get("invoice_number") or "").lower()
                    text = ((tx.get("reference") or "") + " " + (tx.get("description") or "")).lower()
                    if abs(balance - amount) < 0.01:
                        comp = await db.city_ledger_companies.find_one(
                            {"id": inv.get("company_id")}, {"_id": 0, "name": 1})
                        candidates.append((_score(78, tx, num, (comp or {}).get("name", ""),
                                                  inv.get("due_date", "")),
                                           inv["id"], "city_ledger_invoice", balance))
                    elif num and num in text:
                        candidates.append((90, inv["id"], "city_ledger_invoice", min(balance, amount)))

            # 4) Income / expense entries (exact amount, ±3 days)
            coll, base = (db.income_entries, 72) if tx["amount"] > 0 else (db.expense_entries, 72)
            iq = {"property_id": property_id, "amount": amount}
            if window:
                iq["date"] = window
            async for e in coll.find(iq, {"_id": 0}).limit(5):
                candidates.append((_score(base, tx, e.get("reference", ""),
                                          e.get("description", "") or e.get("vendor", ""),
                                          e.get("date", "")), e["id"],
                                   "income" if tx["amount"] > 0 else "expense", None))

            # 5) Legacy invoices
            async for inv in db.invoices.find(
                    {"property_id": property_id, "total": amount}, {"_id": 0}).limit(3):
                candidates.append((70, inv["id"], "invoice", None))

            if not candidates:
                continue
            candidates.sort(key=lambda c: -c[0])
            confidence, matched_to, match_type, extra = candidates[0]

            if confidence >= 75:
                await db.bank_transactions.update_one({"id": tx["id"]}, {"$set": {
                    "matched": True, "matched_to": matched_to,
                    "matched_type": match_type, "match_confidence": confidence,
                    "suggested_match": None}})
                matched_count += 1
                # Payment-to-bill: close the city-ledger invoice automatically
                if match_type == "city_ledger_invoice":
                    inv = await db.city_ledger_invoices.find_one({"id": matched_to}, {"_id": 0})
                    if inv:
                        new_paid = round(float(inv.get("paid_amount", 0)) + float(extra or amount), 2)
                        fully = new_paid >= float(inv.get("amount", 0)) - 0.01
                        await db.city_ledger_invoices.update_one({"id": matched_to}, {"$set": {
                            "paid_amount": new_paid,
                            "status": "paid" if fully else inv.get("status", "open"),
                            "paid_at": datetime.now(timezone.utc).isoformat() if fully else inv.get("paid_at"),
                            "paid_via": "bank_auto_match"}})
                        if fully:
                            invoices_closed += 1
            elif confidence >= 50:
                label = {"payment": "Kayıtlı ödeme", "stripe_payment": "Stripe tahsilatı",
                         "city_ledger_invoice": "City-ledger faturası", "income": "Gelir kaydı",
                         "expense": "Gider kaydı", "invoice": "Fatura"}.get(match_type, match_type)
                await db.bank_transactions.update_one({"id": tx["id"]}, {"$set": {
                    "suggested_match": {"matched_to": matched_to, "matched_type": match_type,
                                        "confidence": confidence, "label": label}}})
                suggested_count += 1

        remaining = await db.bank_transactions.count_documents(
            {"property_id": property_id, "matched": False, **({"account_id": account_id} if account_id else {})}
        )
        return {"matched": matched_count, "suggested": suggested_count,
                "invoices_closed": invoices_closed, "remaining_unmatched": remaining}

    @router.post("/accounting/bank-reconciliation/suggestion/{tx_id}/confirm")
    async def confirm_suggestion(tx_id: str,
                                 current_user: dict = Depends(require_roles("admin", "manager"))):
        tx = await db.bank_transactions.find_one({"id": tx_id}, {"_id": 0})
        if not tx or not tx.get("suggested_match"):
            raise HTTPException(404, "Öneri bulunamadı")
        sm = tx["suggested_match"]
        await db.bank_transactions.update_one({"id": tx_id}, {"$set": {
            "matched": True, "matched_to": sm["matched_to"],
            "matched_type": sm["matched_type"],
            "match_confidence": sm["confidence"],
            "confirmed_by": current_user.get("name", ""),
            "suggested_match": None}})
        if sm["matched_type"] == "city_ledger_invoice":
            inv = await db.city_ledger_invoices.find_one({"id": sm["matched_to"]}, {"_id": 0})
            if inv:
                new_paid = round(float(inv.get("paid_amount", 0)) + abs(tx["amount"]), 2)
                fully = new_paid >= float(inv.get("amount", 0)) - 0.01
                await db.city_ledger_invoices.update_one({"id": sm["matched_to"]}, {"$set": {
                    "paid_amount": new_paid,
                    "status": "paid" if fully else inv.get("status", "open"),
                    "paid_via": "bank_match_confirmed"}})
        return {"ok": True}

    @router.post("/accounting/bank-reconciliation/suggestion/{tx_id}/reject")
    async def reject_suggestion(tx_id: str,
                                current_user: dict = Depends(require_roles("admin", "manager"))):
        r = await db.bank_transactions.update_one(
            {"id": tx_id}, {"$set": {"suggested_match": None}})
        if r.matched_count == 0:
            raise HTTPException(404, "İşlem bulunamadı")
        return {"ok": True}

    # ==================== MANUAL MATCHING ====================

    @router.post("/accounting/bank-reconciliation/manual-match")
    async def manual_match(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        tx_id = data.get("transaction_id")
        matched_to = data.get("matched_to")
        match_type = data.get("match_type", "manual")

        await db.bank_transactions.update_one({"id": tx_id}, {"$set": {
            "matched": True,
            "matched_to": matched_to,
            "matched_type": match_type,
            "match_confidence": 100,
        }})
        return {"status": "matched"}

    @router.post("/accounting/bank-reconciliation/unmatch/{tx_id}")
    async def unmatch_transaction(tx_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.bank_transactions.update_one({"id": tx_id}, {"$set": {
            "matched": False, "matched_to": None, "matched_type": None, "match_confidence": None,
        }})
        return {"status": "unmatched"}

    # ==================== RECONCILIATION SUMMARY ====================

    @router.get("/accounting/bank-reconciliation/summary/{property_id}")
    async def reconciliation_summary(property_id: str, account_id: str = "", month: str = "",
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        if not month:
            month = datetime.now(timezone.utc).strftime("%Y-%m")

        base_query = {"property_id": property_id}
        if account_id:
            base_query["account_id"] = account_id

        month_query = {**base_query, "date": {"$regex": f"^{month}"}}

        total_txns = await db.bank_transactions.count_documents(month_query)
        matched_txns = await db.bank_transactions.count_documents({**month_query, "matched": True})
        unmatched_txns = total_txns - matched_txns

        # Totals
        credit_total = 0
        debit_total = 0
        async for doc in db.bank_transactions.aggregate([
            {"$match": month_query},
            {"$group": {
                "_id": "$type",
                "total": {"$sum": {"$abs": "$amount"}}
            }}
        ]):
            if doc["_id"] == "credit":
                credit_total = round(doc["total"], 2)
            else:
                debit_total = round(doc["total"], 2)

        # System totals (income + payments received vs expenses + payments made)
        sys_income = 0
        async for doc in db.income_entries.aggregate([
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{month}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            sys_income = round(doc["total"], 2)

        sys_expense = 0
        async for doc in db.expense_entries.aggregate([
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{month}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            sys_expense = round(doc["total"], 2)

        bank_net = round(credit_total - debit_total, 2)
        system_net = round(sys_income - sys_expense, 2)
        discrepancy = round(bank_net - system_net, 2)

        match_rate = round((matched_txns / total_txns * 100) if total_txns else 0, 1)

        return {
            "month": month,
            "total_transactions": total_txns,
            "matched": matched_txns,
            "unmatched": unmatched_txns,
            "match_rate": match_rate,
            "bank_credits": credit_total,
            "bank_debits": debit_total,
            "bank_net": bank_net,
            "system_income": sys_income,
            "system_expenses": sys_expense,
            "system_net": system_net,
            "discrepancy": discrepancy,
            "reconciled": abs(discrepancy) < 0.02 and unmatched_txns == 0,
        }

    # ==================== ADD MANUAL TRANSACTION ====================

    @router.post("/accounting/bank-transactions/manual")
    async def add_manual_transaction(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        doc = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "account_id": data.get("account_id", ""),
            "date": data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "description": data.get("description", ""),
            "reference": data.get("reference", ""),
            "amount": data.get("amount", 0),
            "type": "credit" if data.get("amount", 0) > 0 else "debit",
            "balance": data.get("balance"),
            "matched": False,
            "matched_to": None,
            "matched_type": None,
            "match_confidence": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.bank_transactions.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.delete("/accounting/bank-transactions/{tx_id}")
    async def delete_transaction(tx_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        await db.bank_transactions.delete_one({"id": tx_id})
        return {"status": "deleted"}

    return router
