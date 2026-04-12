"""
Advanced Hotel Accounting Routes
AR/AP Aging, Night Audit, Cash Flow, Payments, Journal Entries,
Balance Sheet, Forecasting, Recurring Invoices, Audit Trail
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from collections import defaultdict
import uuid
import logging

from routes.helpers import log_sync

logger = logging.getLogger(__name__)


def create_accounting_advanced_router(db, require_roles):
    router = APIRouter()

    # Helper: log audit trail
    async def audit_log(user, action, entity_type, entity_id, details="", before=None, after=None):
        entry = {
            "id": str(uuid.uuid4()),
            "user_id": user.get("id", ""),
            "user_name": user.get("name", "Admin"),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
            "before": before,
            "after": after,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await db.accounting_audit_trail.insert_one(entry)
        entry.pop("_id", None)
        return entry

    # ==================== 1. ACCOUNTS RECEIVABLE AGING ====================

    @router.get("/accounting/ar-aging/{property_id}")
    async def ar_aging_report(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        invoices = await db.invoices.find(
            {"property_id": property_id, "invoice_type": "receivable", "status": {"$ne": "paid"}},
            {"_id": 0}
        ).to_list(500)

        buckets = {"current": [], "30": [], "60": [], "90": [], "120_plus": []}
        totals = {"current": 0, "30": 0, "60": 0, "90": 0, "120_plus": 0}

        for inv in invoices:
            due = inv.get("due_date", today)
            try:
                due_dt = datetime.strptime(due, "%Y-%m-%d")
                today_dt = datetime.strptime(today, "%Y-%m-%d")
                days_overdue = (today_dt - due_dt).days
            except Exception:
                days_overdue = 0

            inv["days_overdue"] = max(days_overdue, 0)
            balance = inv.get("total", 0) - inv.get("amount_paid", 0)
            inv["balance_due"] = round(balance, 2)

            if days_overdue <= 0:
                buckets["current"].append(inv)
                totals["current"] += balance
            elif days_overdue <= 30:
                buckets["30"].append(inv)
                totals["30"] += balance
            elif days_overdue <= 60:
                buckets["60"].append(inv)
                totals["60"] += balance
            elif days_overdue <= 90:
                buckets["90"].append(inv)
                totals["90"] += balance
            else:
                buckets["120_plus"].append(inv)
                totals["120_plus"] += balance

        total_outstanding = sum(totals.values())
        return {
            "as_of": today,
            "total_outstanding": round(total_outstanding, 2),
            "totals": {k: round(v, 2) for k, v in totals.items()},
            "counts": {k: len(v) for k, v in buckets.items()},
            "buckets": {k: v for k, v in buckets.items()},
        }

    # ==================== 2. ACCOUNTS PAYABLE AGING ====================

    @router.get("/accounting/ap-aging/{property_id}")
    async def ap_aging_report(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        invoices = await db.invoices.find(
            {"property_id": property_id, "invoice_type": "payable", "status": {"$ne": "paid"}},
            {"_id": 0}
        ).to_list(500)

        buckets = {"current": [], "30": [], "60": [], "90": [], "120_plus": []}
        totals = {"current": 0, "30": 0, "60": 0, "90": 0, "120_plus": 0}

        for inv in invoices:
            due = inv.get("due_date", today)
            try:
                due_dt = datetime.strptime(due, "%Y-%m-%d")
                today_dt = datetime.strptime(today, "%Y-%m-%d")
                days_overdue = (today_dt - due_dt).days
            except Exception:
                days_overdue = 0

            inv["days_overdue"] = max(days_overdue, 0)
            balance = inv.get("total", 0) - inv.get("amount_paid", 0)
            inv["balance_due"] = round(balance, 2)

            if days_overdue <= 0:
                buckets["current"].append(inv)
                totals["current"] += balance
            elif days_overdue <= 30:
                buckets["30"].append(inv)
                totals["30"] += balance
            elif days_overdue <= 60:
                buckets["60"].append(inv)
                totals["60"] += balance
            elif days_overdue <= 90:
                buckets["90"].append(inv)
                totals["90"] += balance
            else:
                buckets["120_plus"].append(inv)
                totals["120_plus"] += balance

        total_outstanding = sum(totals.values())
        return {
            "as_of": today,
            "total_outstanding": round(total_outstanding, 2),
            "totals": {k: round(v, 2) for k, v in totals.items()},
            "counts": {k: len(v) for k, v in buckets.items()},
            "buckets": {k: v for k, v in buckets.items()},
        }

    # ==================== 3. DAILY REVENUE REPORT (NIGHT AUDIT) ====================

    @router.get("/accounting/night-audit/{property_id}")
    async def daily_revenue_report(property_id: str, date: str = "", current_user: dict = Depends(require_roles("admin", "manager"))):
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Room revenue from bookings for this date
        room_rev = 0
        room_count = 0
        bookings = await db.bookings.find(
            {"property_id": property_id, "status": {"$ne": "cancelled"},
             "check_in": {"$lte": date}, "check_out": {"$gt": date}},
            {"_id": 0}
        ).to_list(500)
        for b in bookings:
            try:
                ci = datetime.strptime(b["check_in"], "%Y-%m-%d")
                co = datetime.strptime(b["check_out"], "%Y-%m-%d")
                nights = max((co - ci).days, 1)
                daily_rate = b.get("total_price", 0) / nights
                room_rev += daily_rate
                room_count += 1
            except Exception:
                pass

        # Manual income for this date
        income_entries = await db.income_entries.find(
            {"property_id": property_id, "date": date}, {"_id": 0}
        ).to_list(200)
        income_by_cat = defaultdict(float)
        for e in income_entries:
            income_by_cat[e.get("category", "other")] += e.get("amount", 0)

        # Invoices created today
        inv_count = await db.invoices.count_documents(
            {"property_id": property_id, "created_at": {"$regex": f"^{date}"}}
        )

        # Payments received today
        payments_today = await db.payments.find(
            {"property_id": property_id, "date": date}, {"_id": 0}
        ).to_list(200)
        total_payments = sum(p.get("amount", 0) for p in payments_today)

        # Expenses today
        expenses_today = await db.expense_entries.find(
            {"property_id": property_id, "date": date}, {"_id": 0}
        ).to_list(200)
        total_expenses = sum(e.get("amount", 0) for e in expenses_today)

        total_revenue = room_rev + sum(income_by_cat.values())
        net = total_revenue - total_expenses

        return {
            "date": date,
            "rooms_occupied": room_count,
            "room_revenue": round(room_rev, 2),
            "other_income": {k: round(v, 2) for k, v in income_by_cat.items()},
            "total_revenue": round(total_revenue, 2),
            "total_expenses": round(total_expenses, 2),
            "net_revenue": round(net, 2),
            "payments_received": round(total_payments, 2),
            "invoices_created": inv_count,
            "expense_entries": len(expenses_today),
        }

    @router.get("/accounting/night-audit-week/{property_id}")
    async def weekly_night_audit(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        results = []
        for i in range(7):
            date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            report = await daily_revenue_report(property_id, date, current_user)
            results.append(report)
        results.reverse()
        return results

    # ==================== 4. CASH FLOW STATEMENT ====================

    @router.get("/accounting/cash-flow/{property_id}")
    async def cash_flow_statement(property_id: str, period: str = "", current_user: dict = Depends(require_roles("admin", "manager"))):
        if not period:
            period = datetime.now(timezone.utc).strftime("%Y-%m")

        # Operating: Income - Expenses
        inc_total = 0
        async for doc in db.income_entries.aggregate([
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{period}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            inc_total = round(doc["total"], 2)

        # Add booking revenue
        async for doc in db.bookings.aggregate([
            {"$match": {"property_id": property_id, "status": {"$ne": "cancelled"}, "created_at": {"$regex": f"^{period}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
        ]):
            inc_total += round(doc["total"], 2)

        exp_total = 0
        async for doc in db.expense_entries.aggregate([
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{period}"}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            exp_total = round(doc["total"], 2)

        # Payments received (AR collections)
        ar_collected = 0
        async for doc in db.payments.aggregate([
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{period}"}, "payment_type": "received"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            ar_collected = round(doc["total"], 2)

        # Payments made (AP payments)
        ap_paid = 0
        async for doc in db.payments.aggregate([
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{period}"}, "payment_type": "made"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            ap_paid = round(doc["total"], 2)

        operating = round(inc_total - exp_total + ar_collected - ap_paid, 2)

        # Investing: Capital expenditures (tagged expenses)
        capex = 0
        async for doc in db.expense_entries.aggregate([
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{period}"}, "category": {"$in": ["maintenance", "depreciation", "technology"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            capex = round(doc["total"], 2)

        investing = round(-capex, 2)

        # Financing: rent/lease payments
        financing = 0
        async for doc in db.expense_entries.aggregate([
            {"$match": {"property_id": property_id, "date": {"$regex": f"^{period}"}, "category": {"$in": ["rent_lease", "insurance"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            financing = round(-doc["total"], 2)

        net_cash_flow = round(operating + investing + financing, 2)

        return {
            "period": period,
            "operating": {
                "revenue": inc_total, "expenses": exp_total,
                "ar_collected": ar_collected, "ap_paid": ap_paid,
                "net": operating,
            },
            "investing": {"capex": capex, "net": investing},
            "financing": {"net": financing},
            "net_cash_flow": net_cash_flow,
        }

    # ==================== 5. PAYMENT TRACKING ====================

    @router.get("/accounting/payments/{property_id}")
    async def list_payments(property_id: str, invoice_id: str = "", month: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if invoice_id:
            query["invoice_id"] = invoice_id
        if month:
            query["date"] = {"$regex": f"^{month}"}
        docs = await db.payments.find(query, {"_id": 0}).sort("date", -1).to_list(500)
        return docs

    @router.post("/accounting/payments")
    async def record_payment(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        payment = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "invoice_id": data.get("invoice_id", ""),
            "invoice_number": data.get("invoice_number", ""),
            "counterparty": data.get("counterparty", ""),
            "amount": data.get("amount", 0),
            "method": data.get("method", "bank_transfer"),
            "payment_type": data.get("payment_type", "received"),
            "reference": data.get("reference", ""),
            "notes": data.get("notes", ""),
            "date": data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "recorded_by": current_user.get("name", "Admin"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payments.insert_one(payment)
        payment.pop("_id", None)

        # Update invoice amount_paid if linked
        if payment["invoice_id"]:
            inv = await db.invoices.find_one({"id": payment["invoice_id"]}, {"_id": 0})
            if inv:
                new_paid = (inv.get("amount_paid", 0) or 0) + payment["amount"]
                status = "paid" if new_paid >= inv.get("total", 0) else "partially_paid"
                await db.invoices.update_one({"id": payment["invoice_id"]}, {
                    "$set": {"amount_paid": round(new_paid, 2), "status": status}
                })
                if status == "paid":
                    await db.invoices.update_one({"id": payment["invoice_id"]}, {
                        "$set": {"paid_date": payment["date"]}
                    })

        await audit_log(current_user, "payment_recorded", "payment", payment["id"],
                        f"£{payment['amount']} via {payment['method']} - {payment['counterparty']}")
        return payment

    # ==================== 6. JOURNAL ENTRIES (GENERAL LEDGER) ====================

    @router.get("/accounting/journal-entries/{property_id}")
    async def list_journal_entries(property_id: str, month: str = "",
                                   current_user: dict = Depends(require_roles("admin", "manager"))):
        query = {"property_id": property_id}
        if month:
            query["date"] = {"$regex": f"^{month}"}
        docs = await db.journal_entries.find(query, {"_id": 0}).sort("date", -1).to_list(500)
        return docs

    @router.post("/accounting/journal-entries")
    async def create_journal_entry(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        lines = data.get("lines", [])
        total_debit = sum(line.get("debit", 0) for line in lines)
        total_credit = sum(line.get("credit", 0) for line in lines)

        if abs(total_debit - total_credit) > 0.01:
            raise HTTPException(400, f"Debits (£{total_debit}) must equal Credits (£{total_credit})")

        count = await db.journal_entries.count_documents({"property_id": data.get("property_id", "")})
        entry = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "entry_number": f"JE-{count + 1:05d}",
            "date": data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "description": data.get("description", ""),
            "lines": lines,
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "status": "posted",
            "created_by": current_user.get("name", "Admin"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.journal_entries.insert_one(entry)
        entry.pop("_id", None)

        await audit_log(current_user, "journal_entry_created", "journal_entry", entry["id"],
                        f"{entry['entry_number']}: £{total_debit}")
        return entry

    @router.delete("/accounting/journal-entries/{entry_id}")
    async def void_journal_entry(entry_id: str, current_user: dict = Depends(require_roles("admin"))):
        await db.journal_entries.update_one({"id": entry_id}, {"$set": {"status": "voided"}})
        await audit_log(current_user, "journal_entry_voided", "journal_entry", entry_id)
        return {"status": "voided"}

    # ==================== 7. BALANCE SHEET ====================

    @router.get("/accounting/balance-sheet/{property_id}")
    async def balance_sheet(property_id: str, as_of: str = "",
                            current_user: dict = Depends(require_roles("admin", "manager"))):
        if not as_of:
            as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Assets = Cash + AR outstanding
        # Cash approximation: total income - total expenses + payments received - payments made
        total_income = 0
        async for doc in db.income_entries.aggregate([
            {"$match": {"property_id": property_id, "date": {"$lte": as_of}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            total_income = doc["total"]

        # Add booking revenue
        async for doc in db.bookings.aggregate([
            {"$match": {"property_id": property_id, "status": {"$ne": "cancelled"}, "created_at": {"$lte": as_of + "T23:59:59"}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
        ]):
            total_income += doc["total"]

        total_expenses = 0
        async for doc in db.expense_entries.aggregate([
            {"$match": {"property_id": property_id, "date": {"$lte": as_of}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]):
            total_expenses = doc["total"]

        # AR: unpaid receivable invoices
        ar_total = 0
        async for doc in db.invoices.aggregate([
            {"$match": {"property_id": property_id, "invoice_type": "receivable", "status": {"$ne": "paid"}}},
            {"$group": {"_id": None, "total": {"$sum": "$total"}}}
        ]):
            ar_total = doc["total"]
        ar_paid = 0
        async for doc in db.invoices.aggregate([
            {"$match": {"property_id": property_id, "invoice_type": "receivable", "status": {"$ne": "paid"}}},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount_paid", 0]}}}}
        ]):
            ar_paid = doc["total"]
        accounts_receivable = round(ar_total - ar_paid, 2)

        # AP: unpaid payable invoices
        ap_total = 0
        async for doc in db.invoices.aggregate([
            {"$match": {"property_id": property_id, "invoice_type": "payable", "status": {"$ne": "paid"}}},
            {"$group": {"_id": None, "total": {"$sum": "$total"}}}
        ]):
            ap_total = doc["total"]
        ap_paid_amount = 0
        async for doc in db.invoices.aggregate([
            {"$match": {"property_id": property_id, "invoice_type": "payable", "status": {"$ne": "paid"}}},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount_paid", 0]}}}}
        ]):
            ap_paid_amount = doc["total"]
        accounts_payable = round(ap_total - ap_paid_amount, 2)

        # VAT liability
        vat_liability = 0
        async for doc in db.invoices.aggregate([
            {"$match": {"property_id": property_id, "invoice_type": "receivable"}},
            {"$group": {"_id": None, "total": {"$sum": "$vat_amount"}}}
        ]):
            vat_liability = round(doc["total"], 2)

        cash = round(total_income - total_expenses, 2)
        total_assets = round(cash + accounts_receivable, 2)
        total_liabilities = round(accounts_payable + vat_liability, 2)
        equity = round(total_assets - total_liabilities, 2)

        return {
            "as_of": as_of,
            "assets": {
                "cash_and_equivalents": cash,
                "accounts_receivable": accounts_receivable,
                "total_assets": total_assets,
            },
            "liabilities": {
                "accounts_payable": accounts_payable,
                "vat_liability": vat_liability,
                "total_liabilities": total_liabilities,
            },
            "equity": {
                "retained_earnings": equity,
                "total_equity": equity,
            },
            "balanced": abs(total_assets - (total_liabilities + equity)) < 0.02,
        }

    # ==================== 8. REVENUE FORECASTING ====================

    @router.get("/accounting/forecast/{property_id}")
    async def revenue_forecast(property_id: str, months: int = 3,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        now = datetime.now(timezone.utc)
        forecasts = []

        # Historical monthly averages (last 6 months)
        hist_income = []
        for i in range(1, 7):
            dt = now.replace(day=1) - timedelta(days=30 * i)
            m = dt.strftime("%Y-%m")
            total = 0
            async for doc in db.income_entries.aggregate([
                {"$match": {"property_id": property_id, "date": {"$regex": f"^{m}"}}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]):
                total = doc["total"]
            async for doc in db.bookings.aggregate([
                {"$match": {"property_id": property_id, "status": {"$ne": "cancelled"}, "created_at": {"$regex": f"^{m}"}}},
                {"$group": {"_id": None, "total": {"$sum": "$total_price"}}}
            ]):
                total += doc["total"]
            hist_income.append(total)

        avg_historical = round(sum(hist_income) / len(hist_income), 2) if hist_income else 0
        trend = 0
        if len(hist_income) >= 2 and hist_income[0] > 0:
            trend = round((hist_income[0] - hist_income[-1]) / max(len(hist_income) - 1, 1), 2)

        for i in range(months):
            future_dt = now.replace(day=1) + timedelta(days=30 * (i + 1))
            future_month = future_dt.strftime("%Y-%m")

            # Confirmed booking revenue for future month
            confirmed_rev = 0
            confirmed_count = 0
            future_bookings = await db.bookings.find(
                {"property_id": property_id, "status": {"$ne": "cancelled"},
                 "check_in": {"$regex": f"^{future_month}"}},
                {"_id": 0}
            ).to_list(500)
            for b in future_bookings:
                confirmed_rev += b.get("total_price", 0)
                confirmed_count += 1

            # Forecast = max(confirmed bookings, historical average + trend)
            projected = round(max(confirmed_rev, avg_historical + trend * (i + 1)), 2)

            forecasts.append({
                "month": future_month,
                "confirmed_bookings": confirmed_count,
                "confirmed_revenue": round(confirmed_rev, 2),
                "historical_avg": avg_historical,
                "trend_adjustment": round(trend * (i + 1), 2),
                "projected_revenue": projected,
                "confidence": "high" if confirmed_rev > avg_historical * 0.7 else ("medium" if confirmed_rev > avg_historical * 0.3 else "low"),
            })

        return {
            "historical_avg_monthly": avg_historical,
            "monthly_trend": trend,
            "forecasts": forecasts,
        }

    # ==================== 9. RECURRING INVOICES ====================

    @router.get("/accounting/recurring-invoices/{property_id}")
    async def list_recurring_invoices(property_id: str,
                                      current_user: dict = Depends(require_roles("admin", "manager"))):
        docs = await db.recurring_invoices.find({"property_id": property_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return docs

    @router.post("/accounting/recurring-invoices")
    async def create_recurring_invoice(data: Dict, current_user: dict = Depends(require_roles("admin", "manager"))):
        rec = {
            "id": str(uuid.uuid4()),
            "property_id": data.get("property_id"),
            "invoice_type": data.get("invoice_type", "receivable"),
            "counterparty": data.get("counterparty", ""),
            "items": data.get("items", []),
            "frequency": data.get("frequency", "monthly"),
            "start_date": data.get("start_date", ""),
            "end_date": data.get("end_date", ""),
            "next_date": data.get("start_date", ""),
            "enabled": True,
            "times_generated": 0,
            "last_generated": None,
            "created_by": current_user.get("name", "Admin"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.recurring_invoices.insert_one(rec)
        rec.pop("_id", None)
        await audit_log(current_user, "recurring_invoice_created", "recurring_invoice", rec["id"],
                        f"{rec['counterparty']} - {rec['frequency']}")
        return rec

    @router.put("/accounting/recurring-invoices/{rec_id}")
    async def update_recurring_invoice(rec_id: str, updates: Dict,
                                        current_user: dict = Depends(require_roles("admin", "manager"))):
        updates.pop("_id", None)
        updates.pop("id", None)
        await db.recurring_invoices.update_one({"id": rec_id}, {"$set": updates})
        doc = await db.recurring_invoices.find_one({"id": rec_id}, {"_id": 0})
        return doc

    @router.delete("/accounting/recurring-invoices/{rec_id}")
    async def delete_recurring_invoice(rec_id: str, current_user: dict = Depends(require_roles("admin"))):
        await db.recurring_invoices.delete_one({"id": rec_id})
        return {"status": "deleted"}

    @router.post("/accounting/recurring-invoices/generate/{property_id}")
    async def generate_recurring_invoices(property_id: str, current_user: dict = Depends(require_roles("admin", "manager"))):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        recs = await db.recurring_invoices.find(
            {"property_id": property_id, "enabled": True, "next_date": {"$lte": today}},
            {"_id": 0}
        ).to_list(100)

        generated = 0
        for rec in recs:
            if rec.get("end_date") and rec["end_date"] < today:
                await db.recurring_invoices.update_one({"id": rec["id"]}, {"$set": {"enabled": False}})
                continue

            # Calculate invoice totals
            items = rec.get("items", [])
            subtotal = 0
            vat_total = 0
            for item in items:
                qty = item.get("quantity", 1)
                price = item.get("unit_price", 0)
                vat_rate = item.get("vat_rate", 20)
                line_total = round(qty * price, 2)
                line_vat = round(line_total * vat_rate / 100, 2)
                item["total"] = line_total
                item["vat"] = line_vat
                subtotal += line_total
                vat_total += line_vat

            count = await db.invoices.count_documents({"property_id": property_id})
            inv = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "invoice_number": f"INV-{count + 1:05d}",
                "invoice_type": rec.get("invoice_type", "receivable"),
                "counterparty": rec.get("counterparty", ""),
                "items": items,
                "subtotal": round(subtotal, 2),
                "vat_amount": round(vat_total, 2),
                "total": round(subtotal + vat_total, 2),
                "status": "pending",
                "amount_paid": 0,
                "due_date": (datetime.strptime(rec["next_date"], "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d"),
                "recurring_id": rec["id"],
                "created_by": "System (Recurring)",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.invoices.insert_one(inv)

            # Calculate next date
            freq = rec.get("frequency", "monthly")
            next_dt = datetime.strptime(rec["next_date"], "%Y-%m-%d")
            if freq == "weekly":
                next_dt += timedelta(days=7)
            elif freq == "monthly":
                next_dt = next_dt.replace(month=next_dt.month % 12 + 1) if next_dt.month < 12 else next_dt.replace(year=next_dt.year + 1, month=1)
            elif freq == "quarterly":
                for _ in range(3):
                    next_dt = next_dt.replace(month=next_dt.month % 12 + 1) if next_dt.month < 12 else next_dt.replace(year=next_dt.year + 1, month=1)

            await db.recurring_invoices.update_one({"id": rec["id"]}, {"$set": {
                "next_date": next_dt.strftime("%Y-%m-%d"),
                "last_generated": today,
                "times_generated": rec.get("times_generated", 0) + 1,
            }})
            generated += 1

        return {"generated": generated}

    # ==================== 10. AUDIT TRAIL ====================

    @router.get("/accounting/audit-trail/{property_id}")
    async def list_audit_trail(property_id: str, limit: int = 50,
                               current_user: dict = Depends(require_roles("admin", "manager"))):
        # Fetch from both property-specific and general entries
        docs = await db.accounting_audit_trail.find(
            {}, {"_id": 0}
        ).sort("timestamp", -1).to_list(limit)
        return docs

    return router
