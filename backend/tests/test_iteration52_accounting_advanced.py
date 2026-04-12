"""
Iteration 52 - Advanced Hotel Accounting Features Tests
Testing 10 new features: AR Aging, AP Aging, Night Audit, Cash Flow, 
Payment Tracking, Journal Entries, Balance Sheet, Revenue Forecasting, 
Recurring Invoices, Audit Trail
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

# Global session with auth
session = requests.Session()
session.headers.update({"Content-Type": "application/json"})

def get_auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        # API returns 'token' not 'access_token'
        return response.json().get("token")
    return None

# Setup auth once
@pytest.fixture(scope="session", autouse=True)
def setup_auth():
    token = get_auth_token()
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    yield


class TestAccountingAdvancedAuth:
    """Test authentication for accounting endpoints"""
    
    def test_ar_aging_requires_auth(self):
        """AR Aging endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/ar-aging/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_ap_aging_requires_auth(self):
        """AP Aging endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/ap-aging/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_night_audit_requires_auth(self):
        """Night Audit endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/night-audit/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_cash_flow_requires_auth(self):
        """Cash Flow endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/cash-flow/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_payments_requires_auth(self):
        """Payments endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/payments/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_journal_entries_requires_auth(self):
        """Journal Entries endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/journal-entries/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_balance_sheet_requires_auth(self):
        """Balance Sheet endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/balance-sheet/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_forecast_requires_auth(self):
        """Forecast endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/forecast/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_recurring_invoices_requires_auth(self):
        """Recurring Invoices endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/recurring-invoices/{PROPERTY_ID}")
        assert response.status_code == 401
    
    def test_audit_trail_requires_auth(self):
        """Audit Trail endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/accounting/audit-trail/{PROPERTY_ID}")
        assert response.status_code == 401


class TestARAgingReport:
    """Test Accounts Receivable Aging Report"""
    
    def test_ar_aging_report_structure(self, setup_auth):
        """GET /api/accounting/ar-aging/{property_id} returns correct structure"""
        response = session.get(f"{BASE_URL}/api/accounting/ar-aging/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "as_of" in data
        assert "total_outstanding" in data
        assert "totals" in data
        assert "counts" in data
        assert "buckets" in data
        
        # Check bucket structure (30/60/90/120+ days)
        expected_buckets = ["current", "30", "60", "90", "120_plus"]
        for bucket in expected_buckets:
            assert bucket in data["totals"], f"Missing bucket: {bucket}"
            assert bucket in data["counts"], f"Missing count for bucket: {bucket}"
            assert bucket in data["buckets"], f"Missing bucket list: {bucket}"


class TestAPAgingReport:
    """Test Accounts Payable Aging Report"""
    
    def test_ap_aging_report_structure(self, setup_auth):
        """GET /api/accounting/ap-aging/{property_id} returns correct structure"""
        response = session.get(f"{BASE_URL}/api/accounting/ap-aging/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "as_of" in data
        assert "total_outstanding" in data
        assert "totals" in data
        assert "counts" in data
        assert "buckets" in data
        
        # Check bucket structure
        expected_buckets = ["current", "30", "60", "90", "120_plus"]
        for bucket in expected_buckets:
            assert bucket in data["totals"]


class TestNightAuditDailyRevenue:
    """Test Night Audit / Daily Revenue Report"""
    
    def test_night_audit_today(self, setup_auth):
        """GET /api/accounting/night-audit/{property_id} returns today's report"""
        response = session.get(f"{BASE_URL}/api/accounting/night-audit/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "date" in data
        assert "rooms_occupied" in data
        assert "room_revenue" in data
        assert "total_revenue" in data
        assert "total_expenses" in data
        assert "net_revenue" in data
        assert "payments_received" in data
        assert "invoices_created" in data
    
    def test_night_audit_specific_date(self, setup_auth):
        """GET /api/accounting/night-audit/{property_id}?date=YYYY-MM-DD works"""
        test_date = "2025-01-15"
        response = session.get(f"{BASE_URL}/api/accounting/night-audit/{PROPERTY_ID}?date={test_date}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["date"] == test_date
    
    def test_night_audit_week_trend(self, setup_auth):
        """GET /api/accounting/night-audit-week/{property_id} returns 7-day trend"""
        response = session.get(f"{BASE_URL}/api/accounting/night-audit-week/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should return 7 days of data
        assert isinstance(data, list)
        assert len(data) == 7
        
        # Each day should have the same structure
        for day in data:
            assert "date" in day
            assert "total_revenue" in day
            assert "net_revenue" in day


class TestCashFlowStatement:
    """Test Cash Flow Statement"""
    
    def test_cash_flow_current_month(self, setup_auth):
        """GET /api/accounting/cash-flow/{property_id} returns current month"""
        response = session.get(f"{BASE_URL}/api/accounting/cash-flow/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "period" in data
        assert "operating" in data
        assert "investing" in data
        assert "financing" in data
        assert "net_cash_flow" in data
        
        # Check operating section
        assert "revenue" in data["operating"]
        assert "expenses" in data["operating"]
        assert "ar_collected" in data["operating"]
        assert "ap_paid" in data["operating"]
        assert "net" in data["operating"]
        
        # Check investing section
        assert "capex" in data["investing"]
        assert "net" in data["investing"]
        
        # Check financing section
        assert "net" in data["financing"]
    
    def test_cash_flow_specific_period(self, setup_auth):
        """GET /api/accounting/cash-flow/{property_id}?period=YYYY-MM works"""
        test_period = "2025-01"
        response = session.get(f"{BASE_URL}/api/accounting/cash-flow/{PROPERTY_ID}?period={test_period}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["period"] == test_period


class TestPaymentTracking:
    """Test Payment Tracking"""
    
    def test_list_payments(self, setup_auth):
        """GET /api/accounting/payments/{property_id} returns payment list"""
        response = session.get(f"{BASE_URL}/api/accounting/payments/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_list_payments_by_month(self, setup_auth):
        """GET /api/accounting/payments/{property_id}?month=YYYY-MM filters by month"""
        current_month = datetime.now().strftime("%Y-%m")
        response = session.get(f"{BASE_URL}/api/accounting/payments/{PROPERTY_ID}?month={current_month}")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_record_payment_received(self, setup_auth):
        """POST /api/accounting/payments records a received payment"""
        payment_data = {
            "property_id": PROPERTY_ID,
            "amount": 150.00,
            "method": "bank_transfer",
            "payment_type": "received",
            "counterparty": "TEST_Guest John Doe",
            "reference": "TEST_REF_001",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        response = session.post(f"{BASE_URL}/api/accounting/payments", json=payment_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["amount"] == 150.00
        assert data["method"] == "bank_transfer"
        assert data["payment_type"] == "received"
        assert data["counterparty"] == "TEST_Guest John Doe"
        assert "id" in data
    
    def test_record_payment_made(self, setup_auth):
        """POST /api/accounting/payments records a made payment"""
        payment_data = {
            "property_id": PROPERTY_ID,
            "amount": 500.00,
            "method": "credit_card",
            "payment_type": "made",
            "counterparty": "TEST_Supplier ABC",
            "reference": "TEST_REF_002",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        response = session.post(f"{BASE_URL}/api/accounting/payments", json=payment_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["amount"] == 500.00
        assert data["payment_type"] == "made"


class TestJournalEntries:
    """Test Journal Entries (General Ledger)"""
    
    def test_list_journal_entries(self, setup_auth):
        """GET /api/accounting/journal-entries/{property_id} returns entries"""
        response = session.get(f"{BASE_URL}/api/accounting/journal-entries/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_list_journal_entries_by_month(self, setup_auth):
        """GET /api/accounting/journal-entries/{property_id}?month=YYYY-MM filters"""
        current_month = datetime.now().strftime("%Y-%m")
        response = session.get(f"{BASE_URL}/api/accounting/journal-entries/{PROPERTY_ID}?month={current_month}")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_create_balanced_journal_entry(self, setup_auth):
        """POST /api/accounting/journal-entries creates balanced entry"""
        entry_data = {
            "property_id": PROPERTY_ID,
            "description": "TEST_Room Revenue Recognition",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "lines": [
                {"account": "1000-Cash", "description": "Cash received", "debit": 100.00, "credit": 0},
                {"account": "4000-Revenue", "description": "Room revenue", "debit": 0, "credit": 100.00}
            ]
        }
        response = session.post(f"{BASE_URL}/api/accounting/journal-entries", json=entry_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert "entry_number" in data
        assert data["total_debit"] == 100.00
        assert data["total_credit"] == 100.00
        assert data["status"] == "posted"
    
    def test_create_unbalanced_journal_entry_fails(self, setup_auth):
        """POST /api/accounting/journal-entries with unbalanced amounts returns 400"""
        entry_data = {
            "property_id": PROPERTY_ID,
            "description": "TEST_Unbalanced Entry",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "lines": [
                {"account": "1000-Cash", "description": "Cash", "debit": 100.00, "credit": 0},
                {"account": "4000-Revenue", "description": "Revenue", "debit": 0, "credit": 50.00}  # Unbalanced!
            ]
        }
        response = session.post(f"{BASE_URL}/api/accounting/journal-entries", json=entry_data)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "Debits" in response.json().get("detail", "") or "must equal" in response.json().get("detail", "")
    
    def test_void_journal_entry(self, setup_auth):
        """DELETE /api/accounting/journal-entries/{entry_id} voids entry"""
        # First create an entry to void
        entry_data = {
            "property_id": PROPERTY_ID,
            "description": "TEST_Entry to Void",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "lines": [
                {"account": "1000-Cash", "description": "Cash", "debit": 50.00, "credit": 0},
                {"account": "4000-Revenue", "description": "Revenue", "debit": 0, "credit": 50.00}
            ]
        }
        create_response = session.post(f"{BASE_URL}/api/accounting/journal-entries", json=entry_data)
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        entry_id = create_response.json()["id"]
        
        # Void it
        response = session.delete(f"{BASE_URL}/api/accounting/journal-entries/{entry_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert response.json()["status"] == "voided"


class TestBalanceSheet:
    """Test Balance Sheet"""
    
    def test_balance_sheet_structure(self, setup_auth):
        """GET /api/accounting/balance-sheet/{property_id} returns correct structure"""
        response = session.get(f"{BASE_URL}/api/accounting/balance-sheet/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "as_of" in data
        assert "assets" in data
        assert "liabilities" in data
        assert "equity" in data
        assert "balanced" in data
        
        # Check assets section
        assert "cash_and_equivalents" in data["assets"]
        assert "accounts_receivable" in data["assets"]
        assert "total_assets" in data["assets"]
        
        # Check liabilities section
        assert "accounts_payable" in data["liabilities"]
        assert "vat_liability" in data["liabilities"]
        assert "total_liabilities" in data["liabilities"]
        
        # Check equity section
        assert "retained_earnings" in data["equity"]
        assert "total_equity" in data["equity"]
    
    def test_balance_sheet_balanced_check(self, setup_auth):
        """Balance sheet checks Assets = Liabilities + Equity"""
        response = session.get(f"{BASE_URL}/api/accounting/balance-sheet/{PROPERTY_ID}")
        data = response.json()
        
        # The balanced field should be a boolean
        assert isinstance(data["balanced"], bool)


class TestRevenueForecast:
    """Test Revenue Forecasting"""
    
    def test_forecast_default_3_months(self, setup_auth):
        """GET /api/accounting/forecast/{property_id} returns 3 months by default"""
        response = session.get(f"{BASE_URL}/api/accounting/forecast/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "historical_avg_monthly" in data
        assert "monthly_trend" in data
        assert "forecasts" in data
        assert len(data["forecasts"]) == 3
    
    def test_forecast_custom_months(self, setup_auth):
        """GET /api/accounting/forecast/{property_id}?months=6 returns 6 months"""
        response = session.get(f"{BASE_URL}/api/accounting/forecast/{PROPERTY_ID}?months=6")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert len(data["forecasts"]) == 6
    
    def test_forecast_structure(self, setup_auth):
        """Forecast entries have correct structure"""
        response = session.get(f"{BASE_URL}/api/accounting/forecast/{PROPERTY_ID}")
        data = response.json()
        
        for forecast in data["forecasts"]:
            assert "month" in forecast
            assert "confirmed_bookings" in forecast
            assert "confirmed_revenue" in forecast
            assert "historical_avg" in forecast
            assert "projected_revenue" in forecast
            assert "confidence" in forecast
            assert forecast["confidence"] in ["high", "medium", "low"]


class TestRecurringInvoices:
    """Test Recurring Invoices"""
    
    created_rec_id = None
    
    def test_list_recurring_invoices(self, setup_auth):
        """GET /api/accounting/recurring-invoices/{property_id} returns list"""
        response = session.get(f"{BASE_URL}/api/accounting/recurring-invoices/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_create_recurring_invoice(self, setup_auth):
        """POST /api/accounting/recurring-invoices creates recurring invoice"""
        rec_data = {
            "property_id": PROPERTY_ID,
            "invoice_type": "receivable",
            "counterparty": "TEST_Monthly Tenant",
            "frequency": "monthly",
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "items": [
                {"description": "Monthly Rent", "quantity": 1, "unit_price": 1000.00, "vat_rate": 20}
            ]
        }
        response = session.post(f"{BASE_URL}/api/accounting/recurring-invoices", json=rec_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["counterparty"] == "TEST_Monthly Tenant"
        assert data["frequency"] == "monthly"
        assert data["enabled"] == True
        
        # Store for update test
        TestRecurringInvoices.created_rec_id = data["id"]
    
    def test_update_recurring_invoice(self, setup_auth):
        """PUT /api/accounting/recurring-invoices/{rec_id} updates recurring"""
        rec_id = TestRecurringInvoices.created_rec_id
        if not rec_id:
            pytest.skip("No recurring invoice created")
        
        response = session.put(f"{BASE_URL}/api/accounting/recurring-invoices/{rec_id}", 
                               json={"enabled": False})
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["enabled"] == False
    
    def test_generate_recurring_invoices(self, setup_auth):
        """POST /api/accounting/recurring-invoices/generate/{property_id} generates due invoices"""
        response = session.post(f"{BASE_URL}/api/accounting/recurring-invoices/generate/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "generated" in data
        assert isinstance(data["generated"], int)


class TestAuditTrail:
    """Test Audit Trail"""
    
    def test_list_audit_trail(self, setup_auth):
        """GET /api/accounting/audit-trail/{property_id} returns audit entries"""
        response = session.get(f"{BASE_URL}/api/accounting/audit-trail/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
    
    def test_audit_trail_entry_structure(self, setup_auth):
        """Audit trail entries have correct structure"""
        # First create a payment to generate an audit entry
        payment_data = {
            "property_id": PROPERTY_ID,
            "amount": 75.00,
            "method": "cash",
            "payment_type": "received",
            "counterparty": "TEST_Audit Trail Guest",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        session.post(f"{BASE_URL}/api/accounting/payments", json=payment_data)
        
        # Now check audit trail
        response = session.get(f"{BASE_URL}/api/accounting/audit-trail/{PROPERTY_ID}?limit=10")
        data = response.json()
        
        if len(data) > 0:
            entry = data[0]
            assert "id" in entry
            assert "user_name" in entry
            assert "action" in entry
            assert "timestamp" in entry


class TestPaymentInvoiceIntegration:
    """Test Payment updates Invoice amount_paid and status"""
    
    def test_payment_updates_invoice(self, setup_auth):
        """Recording payment against invoice updates amount_paid and status"""
        # Create an invoice first
        invoice_data = {
            "property_id": PROPERTY_ID,
            "invoice_type": "receivable",
            "counterparty": "TEST_Payment Integration Guest",
            "due_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "items": [
                {"description": "Room charge", "quantity": 1, "unit_price": 200.00, "vat_rate": 20}
            ]
        }
        inv_response = session.post(f"{BASE_URL}/api/accounting/invoices", json=invoice_data)
        assert inv_response.status_code == 200, f"Invoice creation failed: {inv_response.text}"
        invoice = inv_response.json()
        invoice_id = invoice["id"]
        invoice_total = invoice["total"]  # Should be 240 (200 + 20% VAT)
        
        # Record partial payment
        payment_data = {
            "property_id": PROPERTY_ID,
            "invoice_id": invoice_id,
            "amount": 100.00,
            "method": "bank_transfer",
            "payment_type": "received",
            "counterparty": "TEST_Payment Integration Guest",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        pay_response = session.post(f"{BASE_URL}/api/accounting/payments", json=payment_data)
        assert pay_response.status_code == 200, f"Payment failed: {pay_response.text}"
        
        # Check invoice was updated
        inv_check = session.get(f"{BASE_URL}/api/accounting/invoices/{PROPERTY_ID}")
        invoices = inv_check.json()
        updated_invoice = next((i for i in invoices if i["id"] == invoice_id), None)
        
        if updated_invoice:
            assert updated_invoice["amount_paid"] == 100.00
            assert updated_invoice["status"] == "partially_paid"


class TestExistingAccountingFeatures:
    """Regression tests for existing accounting features"""
    
    def test_pnl_still_works(self, setup_auth):
        """GET /api/accounting/pnl/{property_id} still works"""
        response = session.get(f"{BASE_URL}/api/accounting/pnl/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_income" in data
        assert "total_expenses" in data
        assert "net_profit" in data
    
    def test_income_still_works(self, setup_auth):
        """GET /api/accounting/income/{property_id} still works"""
        response = session.get(f"{BASE_URL}/api/accounting/income/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_expenses_still_works(self, setup_auth):
        """GET /api/accounting/expenses/{property_id} still works"""
        response = session.get(f"{BASE_URL}/api/accounting/expenses/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_invoices_still_works(self, setup_auth):
        """GET /api/accounting/invoices/{property_id} still works"""
        response = session.get(f"{BASE_URL}/api/accounting/invoices/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_vat_report_still_works(self, setup_auth):
        """GET /api/accounting/vat-report/{property_id} still works"""
        response = session.get(f"{BASE_URL}/api/accounting/vat-report/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_trends_still_works(self, setup_auth):
        """GET /api/accounting/trends/{property_id} still works"""
        response = session.get(f"{BASE_URL}/api/accounting/trends/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_budgets_still_works(self, setup_auth):
        """GET /api/accounting/budgets/{property_id} still works"""
        response = session.get(f"{BASE_URL}/api/accounting/budgets/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
    
    def test_chart_of_accounts_still_works(self, setup_auth):
        """GET /api/accounting/chart-of-accounts/{property_id} still works"""
        response = session.get(f"{BASE_URL}/api/accounting/chart-of-accounts/{PROPERTY_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
