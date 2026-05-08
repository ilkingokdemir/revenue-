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
        """Automatically match bank transactions to payments, income, and expenses"""
        query = {"property_id": property_id, "matched": False}
        if account_id:
            query["account_id"] = account_id

        unmatched = await db.bank_transactions.find(query, {"_id": 0}).to_list(500)
        matched_count = 0

        for tx in unmatched:
            best_match = None
            best_confidence = 0
            match_type = None

            # Try matching against payments
            pay_query = {"property_id": property_id}
            if tx["amount"] > 0:
                pay_query["payment_type"] = "received"
                pay_query["amount"] = tx["amount"]
            else:
                pay_query["payment_type"] = "made"
                pay_query["amount"] = abs(tx["amount"])

            if tx.get("date"):
                pay_query["date"] = tx["date"]

            payment = await db.payments.find_one(pay_query, {"_id": 0})
            if payment:
                best_match = payment["id"]
                best_confidence = 95
                match_type = "payment"
                # Check reference match for higher confidence
                if tx.get("reference") and payment.get("reference") and tx["reference"].lower() in payment["reference"].lower():
                    best_confidence = 99

            # Try matching against income entries
            if not best_match and tx["amount"] > 0:
                inc_query = {"property_id": property_id, "amount": tx["amount"]}
                if tx.get("date"):
                    inc_query["date"] = tx["date"]
                income = await db.income_entries.find_one(inc_query, {"_id": 0})
                if income:
                    best_match = income["id"]
                    best_confidence = 85
                    match_type = "income"

            # Try matching against expense entries
            if not best_match and tx["amount"] < 0:
                exp_query = {"property_id": property_id, "amount": abs(tx["amount"])}
                if tx.get("date"):
                    exp_query["date"] = tx["date"]
                expense = await db.expense_entries.find_one(exp_query, {"_id": 0})
                if expense:
                    best_match = expense["id"]
                    best_confidence = 85
                    match_type = "expense"

            # Try matching against invoices
            if not best_match:
                inv_amount = abs(tx["amount"])
                inv_query = {"property_id": property_id, "total": inv_amount}
                invoice = await db.invoices.find_one(inv_query, {"_id": 0})
                if invoice:
                    best_match = invoice["id"]
                    best_confidence = 75
                    match_type = "invoice"

            if best_match and best_confidence >= 75:
                await db.bank_transactions.update_one({"id": tx["id"]}, {"$set": {
                    "matched": True,
                    "matched_to": best_match,
                    "matched_type": match_type,
                    "match_confidence": best_confidence,
                }})
                matched_count += 1

        remaining = await db.bank_transactions.count_documents(
            {"property_id": property_id, "matched": False, **({"account_id": account_id} if account_id else {})}
        )
        return {"matched": matched_count, "remaining_unmatched": remaining}

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
