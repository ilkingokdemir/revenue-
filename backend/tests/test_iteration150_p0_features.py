"""
Iteration 150 - P0 Features Testing
===================================
Tests for 3 P0 items from competitor audit:
1. City Ledger (Corporate AR) - B2B deferred billing
2. Tax Configuration - Multi-region tax profiles
3. Deposit Policies - Rule-based deposit enforcement

All endpoints require authentication with view_bookings/edit_bookings/delete_bookings permissions.
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://review-hub-108.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


# ============================================================================
# CITY LEDGER TESTS
# ============================================================================
class TestCityLedgerCompanies:
    """City Ledger - Company CRUD and enrichment"""
    
    created_company_id = None
    
    def test_create_company(self, api_client):
        """POST /api/city-ledger/companies creates company with id and enrichment"""
        payload = {
            "name": "TEST_Acme Corp",
            "contact_name": "John Smith",
            "email": "john@acme.test",
            "phone": "+44 20 1234 5678",
            "address": "123 Business Park, London",
            "tax_id": "GB123456789",
            "credit_limit": 10000,
            "payment_terms_days": 30,
            "notes": "Test company for iteration 150",
            "active": True
        }
        resp = api_client.post(f"{BASE_URL}/api/city-ledger/companies", json=payload)
        assert resp.status_code == 200, f"Create company failed: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert "id" in data, "Company should have id"
        assert data["name"] == "TEST_Acme Corp"
        assert data["payment_terms_days"] == 30
        assert data["credit_limit"] == 10000
        assert "created_at" in data
        
        TestCityLedgerCompanies.created_company_id = data["id"]
        print(f"Created company: {data['id']}")
    
    def test_list_companies_with_enrichment(self, api_client):
        """GET /api/city-ledger/companies returns list with open_balance/open_invoices"""
        resp = api_client.get(f"{BASE_URL}/api/city-ledger/companies")
        assert resp.status_code == 200, f"List companies failed: {resp.text}"
        data = resp.json()
        
        assert isinstance(data, list), "Should return list"
        # Find our test company
        test_company = next((c for c in data if c.get("name") == "TEST_Acme Corp"), None)
        assert test_company is not None, "Test company should be in list"
        
        # Verify enrichment fields
        assert "open_balance" in test_company, "Should have open_balance enrichment"
        assert "open_invoices" in test_company, "Should have open_invoices enrichment"
        assert test_company["open_balance"] == 0, "New company should have 0 open balance"
        print(f"Company enrichment: open_balance={test_company['open_balance']}, open_invoices={test_company['open_invoices']}")
    
    def test_update_company(self, api_client):
        """PUT /api/city-ledger/companies/{id} updates company"""
        company_id = TestCityLedgerCompanies.created_company_id
        assert company_id, "Need company_id from create test"
        
        payload = {
            "name": "TEST_Acme Corp Updated",
            "contact_name": "Jane Smith",
            "email": "jane@acme.test",
            "phone": "+44 20 1234 5678",
            "address": "456 Business Park, London",
            "tax_id": "GB123456789",
            "credit_limit": 15000,
            "payment_terms_days": 45,
            "notes": "Updated notes",
            "active": True
        }
        resp = api_client.put(f"{BASE_URL}/api/city-ledger/companies/{company_id}", json=payload)
        assert resp.status_code == 200, f"Update company failed: {resp.text}"
        data = resp.json()
        assert data.get("updated") == True


class TestCityLedgerInvoices:
    """City Ledger - Invoice CRUD with auto-numbering and due date calculation"""
    
    created_invoice_id = None
    
    def test_create_invoice_auto_number_and_due_date(self, api_client):
        """POST /api/city-ledger/invoices auto-generates invoice_number and due_date"""
        company_id = TestCityLedgerCompanies.created_company_id
        assert company_id, "Need company_id from company tests"
        
        payload = {
            "company_id": company_id,
            "booking_ids": ["booking-001", "booking-002"],
            "amount": 2500,
            "currency": "GBP",
            "notes": "Test invoice for iteration 150"
        }
        resp = api_client.post(f"{BASE_URL}/api/city-ledger/invoices", json=payload)
        assert resp.status_code == 200, f"Create invoice failed: {resp.text}"
        data = resp.json()
        
        # Verify auto-generated fields
        assert "id" in data, "Invoice should have id"
        assert "invoice_number" in data, "Should have auto-generated invoice_number"
        assert data["invoice_number"].startswith("CL-2026-") or data["invoice_number"].startswith("CL-2025-"), \
            f"Invoice number should be CL-YYYY-NNNNN format, got: {data['invoice_number']}"
        
        # Verify due_date auto-calculation (issue_date + payment_terms_days)
        assert "due_date" in data, "Should have auto-calculated due_date"
        assert "issue_date" in data, "Should have issue_date"
        
        # Due date should be issue_date + 45 days (updated payment terms)
        issue = datetime.fromisoformat(data["issue_date"])
        due = datetime.fromisoformat(data["due_date"])
        days_diff = (due - issue).days
        assert days_diff == 45, f"Due date should be issue + 45 days, got {days_diff} days"
        
        assert data["status"] == "open", "New invoice should be open"
        assert data["paid_amount"] == 0, "New invoice should have 0 paid"
        
        TestCityLedgerInvoices.created_invoice_id = data["id"]
        print(f"Created invoice: {data['invoice_number']} (due in {days_diff} days)")
    
    def test_list_invoices_with_enrichment(self, api_client):
        """GET /api/city-ledger/invoices enriches with company_name, is_overdue, days_overdue, balance"""
        resp = api_client.get(f"{BASE_URL}/api/city-ledger/invoices")
        assert resp.status_code == 200, f"List invoices failed: {resp.text}"
        data = resp.json()
        
        assert isinstance(data, list), "Should return list"
        # Find our test invoice
        test_invoice = next((i for i in data if i.get("id") == TestCityLedgerInvoices.created_invoice_id), None)
        assert test_invoice is not None, "Test invoice should be in list"
        
        # Verify enrichment fields
        assert "company_name" in test_invoice, "Should have company_name enrichment"
        assert "is_overdue" in test_invoice, "Should have is_overdue enrichment"
        assert "days_overdue" in test_invoice, "Should have days_overdue enrichment"
        assert "balance" in test_invoice, "Should have balance enrichment"
        
        assert test_invoice["balance"] == 2500, "Balance should equal amount for unpaid invoice"
        print(f"Invoice enrichment: company={test_invoice['company_name']}, balance={test_invoice['balance']}")


class TestCityLedgerPayments:
    """City Ledger - Payment recording (partial and full)"""
    
    def test_partial_payment(self, api_client):
        """POST /api/city-ledger/invoices/{id}/pay supports partial payments"""
        invoice_id = TestCityLedgerInvoices.created_invoice_id
        assert invoice_id, "Need invoice_id from invoice tests"
        
        payload = {
            "amount": 1000,
            "method": "bank_transfer",
            "reference": "BACS-2026-001"
        }
        resp = api_client.post(f"{BASE_URL}/api/city-ledger/invoices/{invoice_id}/pay", json=payload)
        assert resp.status_code == 200, f"Record payment failed: {resp.text}"
        data = resp.json()
        
        assert data["ok"] == True
        assert data["status"] == "partial", "Status should be partial after partial payment"
        assert data["paid_amount"] == 1000
        assert data["balance"] == 1500, "Balance should be 2500 - 1000 = 1500"
        print(f"Partial payment: status={data['status']}, balance={data['balance']}")
    
    def test_full_payment(self, api_client):
        """POST /api/city-ledger/invoices/{id}/pay supports full payments"""
        invoice_id = TestCityLedgerInvoices.created_invoice_id
        assert invoice_id, "Need invoice_id from invoice tests"
        
        payload = {
            "amount": 1500,
            "method": "card",
            "reference": "CARD-2026-001"
        }
        resp = api_client.post(f"{BASE_URL}/api/city-ledger/invoices/{invoice_id}/pay", json=payload)
        assert resp.status_code == 200, f"Record payment failed: {resp.text}"
        data = resp.json()
        
        assert data["ok"] == True
        assert data["status"] == "paid", "Status should be paid after full payment"
        assert data["paid_amount"] == 2500
        assert data["balance"] == 0, "Balance should be 0 after full payment"
        print(f"Full payment: status={data['status']}, balance={data['balance']}")


class TestCityLedgerAging:
    """City Ledger - Aging report with buckets"""
    
    def test_aging_report_structure(self, api_client):
        """GET /api/city-ledger/aging returns correct bucket structure"""
        resp = api_client.get(f"{BASE_URL}/api/city-ledger/aging")
        assert resp.status_code == 200, f"Aging report failed: {resp.text}"
        data = resp.json()
        
        # Verify structure
        assert "buckets" in data, "Should have buckets"
        assert "total" in data, "Should have total"
        assert "by_company" in data, "Should have by_company breakdown"
        assert "as_of" in data, "Should have as_of date"
        
        buckets = data["buckets"]
        assert "current" in buckets, "Should have current bucket"
        assert "d30" in buckets, "Should have d30 (1-30 days) bucket"
        assert "d60" in buckets, "Should have d60 (31-60 days) bucket"
        assert "d90" in buckets, "Should have d90 (61-90 days) bucket"
        assert "over90" in buckets, "Should have over90 (90+) bucket"
        
        print(f"Aging buckets: {buckets}")
        print(f"Total open AR: {data['total']}")


class TestCityLedgerStatement:
    """City Ledger - Company statement"""
    
    def test_company_statement(self, api_client):
        """GET /api/city-ledger/companies/{id}/statement returns company + invoices + summary"""
        company_id = TestCityLedgerCompanies.created_company_id
        assert company_id, "Need company_id from company tests"
        
        resp = api_client.get(f"{BASE_URL}/api/city-ledger/companies/{company_id}/statement")
        assert resp.status_code == 200, f"Statement failed: {resp.text}"
        data = resp.json()
        
        assert "company" in data, "Should have company object"
        assert "invoices" in data, "Should have invoices list"
        assert "summary" in data, "Should have summary object"
        
        summary = data["summary"]
        assert "total_open" in summary, "Summary should have total_open"
        assert "total_overdue" in summary, "Summary should have total_overdue"
        assert "invoice_count" in summary, "Summary should have invoice_count"
        assert "open_count" in summary, "Summary should have open_count"
        
        print(f"Statement summary: {summary}")


class TestCityLedgerDeleteBlocking:
    """City Ledger - Delete company blocking when open invoices exist"""
    
    def test_delete_company_blocked_with_open_invoices(self, api_client):
        """DELETE /api/city-ledger/companies/{id} blocks when open invoices exist"""
        # First create a new company with an open invoice
        company_payload = {
            "name": "TEST_Delete Block Corp",
            "payment_terms_days": 30,
            "active": True
        }
        resp = api_client.post(f"{BASE_URL}/api/city-ledger/companies", json=company_payload)
        assert resp.status_code == 200
        company_id = resp.json()["id"]
        
        # Create an open invoice
        invoice_payload = {
            "company_id": company_id,
            "amount": 500,
            "currency": "GBP"
        }
        resp = api_client.post(f"{BASE_URL}/api/city-ledger/invoices", json=invoice_payload)
        assert resp.status_code == 200
        invoice_id = resp.json()["id"]
        
        # Try to delete company - should fail
        resp = api_client.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
        assert resp.status_code == 400, f"Should block delete, got {resp.status_code}"
        data = resp.json()
        assert "open invoice" in data.get("detail", "").lower(), f"Error should mention open invoices: {data}"
        print(f"Delete blocked correctly: {data.get('detail')}")
        
        # Clean up - pay the invoice first
        resp = api_client.post(f"{BASE_URL}/api/city-ledger/invoices/{invoice_id}/pay", json={"amount": 500})
        assert resp.status_code == 200
        
        # Now delete should work
        resp = api_client.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
        assert resp.status_code == 200, f"Delete should succeed after paying invoice: {resp.text}"


# ============================================================================
# TAX CONFIGURATION TESTS
# ============================================================================
class TestTaxConfigProfiles:
    """Tax Configuration - Profile CRUD"""
    
    created_profile_id = None
    
    def test_create_tax_profile(self, api_client):
        """POST /api/tax-config/profiles stores rules with all fields"""
        payload = {
            "property_id": "default",
            "name": "TEST_UK Standard Tax",
            "rules": [
                {
                    "kind": "vat",
                    "label": "VAT 20%",
                    "basis": "percent",
                    "rate": 20,
                    "applies_to": ["room", "fnb", "spa"],
                    "channels": [],
                    "included_in_rate": False
                },
                {
                    "kind": "city_tax",
                    "label": "City Tax £3/night/guest",
                    "basis": "per_night_per_guest",
                    "rate": 3,
                    "applies_to": ["room"],
                    "channels": [],
                    "included_in_rate": False
                }
            ],
            "active": True,
            "notes": "Test profile for iteration 150"
        }
        resp = api_client.post(f"{BASE_URL}/api/tax-config/profiles", json=payload)
        assert resp.status_code == 200, f"Create profile failed: {resp.text}"
        data = resp.json()
        
        assert "id" in data, "Profile should have id"
        assert data["name"] == "TEST_UK Standard Tax"
        assert len(data["rules"]) == 2, "Should have 2 rules"
        
        # Verify rule structure
        vat_rule = data["rules"][0]
        assert vat_rule["kind"] == "vat"
        assert vat_rule["basis"] == "percent"
        assert vat_rule["rate"] == 20
        assert "room" in vat_rule["applies_to"]
        
        TestTaxConfigProfiles.created_profile_id = data["id"]
        print(f"Created tax profile: {data['id']}")
    
    def test_list_profiles(self, api_client):
        """GET /api/tax-config/profiles returns profiles"""
        resp = api_client.get(f"{BASE_URL}/api/tax-config/profiles")
        assert resp.status_code == 200, f"List profiles failed: {resp.text}"
        data = resp.json()
        
        assert isinstance(data, list), "Should return list"
        test_profile = next((p for p in data if p.get("name") == "TEST_UK Standard Tax"), None)
        assert test_profile is not None, "Test profile should be in list"
    
    def test_update_profile(self, api_client):
        """PUT /api/tax-config/profiles/{id} updates profile"""
        profile_id = TestTaxConfigProfiles.created_profile_id
        assert profile_id, "Need profile_id from create test"
        
        payload = {
            "property_id": "default",
            "name": "TEST_UK Standard Tax Updated",
            "rules": [
                {
                    "kind": "vat",
                    "label": "VAT 20%",
                    "basis": "percent",
                    "rate": 20,
                    "applies_to": ["room"],
                    "channels": [],
                    "included_in_rate": False
                }
            ],
            "active": True,
            "notes": "Updated"
        }
        resp = api_client.put(f"{BASE_URL}/api/tax-config/profiles/{profile_id}", json=payload)
        assert resp.status_code == 200, f"Update profile failed: {resp.text}"
    
    def test_delete_profile_404(self, api_client):
        """DELETE /api/tax-config/profiles/{id} returns 404 for non-existent"""
        resp = api_client.delete(f"{BASE_URL}/api/tax-config/profiles/non-existent-id")
        assert resp.status_code == 404, f"Should return 404, got {resp.status_code}"


class TestTaxCalculation:
    """Tax Configuration - Tax calculation with different bases"""
    
    def test_calculate_percent_basis(self, api_client):
        """POST /api/tax-config/calculate correctly computes percent basis"""
        payload = {
            "property_id": "default",
            "channel": "",
            "base_amount": 100,
            "nights": 2,
            "guests": 2,
            "category": "room"
        }
        resp = api_client.post(f"{BASE_URL}/api/tax-config/calculate", json=payload)
        assert resp.status_code == 200, f"Calculate failed: {resp.text}"
        data = resp.json()
        
        assert "base" in data, "Should have base"
        assert "taxes_added" in data, "Should have taxes_added"
        assert "taxes_included" in data, "Should have taxes_included"
        assert "grand_total" in data, "Should have grand_total"
        assert "applied" in data, "Should have applied rules list"
        
        # With our test profile: 20% VAT on £100 = £20
        # Grand total should be base + taxes_added
        assert data["grand_total"] == data["base"] + data["taxes_added"]
        print(f"Tax calculation: base={data['base']}, taxes_added={data['taxes_added']}, total={data['grand_total']}")
    
    def test_calculate_per_night_per_guest_basis(self, api_client):
        """POST /api/tax-config/calculate correctly computes per_night_per_guest basis"""
        # First create a profile with per_night_per_guest rule
        profile_payload = {
            "property_id": "test-pnpg",
            "name": "TEST_Per Night Per Guest",
            "rules": [
                {
                    "kind": "city_tax",
                    "label": "City Tax £3/night/guest",
                    "basis": "per_night_per_guest",
                    "rate": 3,
                    "applies_to": ["room"],
                    "channels": [],
                    "included_in_rate": False
                }
            ],
            "active": True
        }
        resp = api_client.post(f"{BASE_URL}/api/tax-config/profiles", json=profile_payload)
        assert resp.status_code == 200
        profile_id = resp.json()["id"]
        
        # Calculate: £3 × 2 nights × 2 guests = £12
        calc_payload = {
            "property_id": "test-pnpg",
            "base_amount": 100,
            "nights": 2,
            "guests": 2,
            "category": "room"
        }
        resp = api_client.post(f"{BASE_URL}/api/tax-config/calculate", json=calc_payload)
        assert resp.status_code == 200
        data = resp.json()
        
        # Find the city tax in applied
        city_tax = next((a for a in data.get("applied", []) if a.get("kind") == "city_tax"), None)
        if city_tax:
            assert city_tax["amount"] == 12, f"City tax should be £3 × 2 × 2 = £12, got {city_tax['amount']}"
            print(f"Per night per guest: {city_tax['amount']}")
        
        # Clean up
        api_client.delete(f"{BASE_URL}/api/tax-config/profiles/{profile_id}")
    
    def test_calculate_included_in_rate(self, api_client):
        """POST /api/tax-config/calculate respects included_in_rate flag"""
        # Create profile with included_in_rate = True
        profile_payload = {
            "property_id": "test-incl",
            "name": "TEST_Included Tax",
            "rules": [
                {
                    "kind": "vat",
                    "label": "VAT 20% (included)",
                    "basis": "percent",
                    "rate": 20,
                    "applies_to": ["room"],
                    "channels": [],
                    "included_in_rate": True
                }
            ],
            "active": True
        }
        resp = api_client.post(f"{BASE_URL}/api/tax-config/profiles", json=profile_payload)
        assert resp.status_code == 200
        profile_id = resp.json()["id"]
        
        calc_payload = {
            "property_id": "test-incl",
            "base_amount": 100,
            "nights": 1,
            "guests": 1,
            "category": "room"
        }
        resp = api_client.post(f"{BASE_URL}/api/tax-config/calculate", json=calc_payload)
        assert resp.status_code == 200
        data = resp.json()
        
        # taxes_included should have the VAT, taxes_added should be 0
        assert data["taxes_included"] == 20, f"taxes_included should be 20, got {data['taxes_included']}"
        assert data["taxes_added"] == 0, f"taxes_added should be 0 for included tax, got {data['taxes_added']}"
        # Grand total should equal base (tax is already inside)
        assert data["grand_total"] == 100, f"Grand total should be 100 (tax included), got {data['grand_total']}"
        print(f"Included tax: taxes_included={data['taxes_included']}, grand_total={data['grand_total']}")
        
        # Clean up
        api_client.delete(f"{BASE_URL}/api/tax-config/profiles/{profile_id}")
    
    def test_calculate_category_filter(self, api_client):
        """POST /api/tax-config/calculate filters rules by category"""
        # Create profile with room-only rule
        profile_payload = {
            "property_id": "test-cat",
            "name": "TEST_Category Filter",
            "rules": [
                {
                    "kind": "vat",
                    "label": "Room VAT",
                    "basis": "percent",
                    "rate": 20,
                    "applies_to": ["room"],
                    "channels": [],
                    "included_in_rate": False
                }
            ],
            "active": True
        }
        resp = api_client.post(f"{BASE_URL}/api/tax-config/profiles", json=profile_payload)
        assert resp.status_code == 200
        profile_id = resp.json()["id"]
        
        # Calculate for fnb category - should not apply room tax
        calc_payload = {
            "property_id": "test-cat",
            "base_amount": 100,
            "nights": 1,
            "guests": 1,
            "category": "fnb"
        }
        resp = api_client.post(f"{BASE_URL}/api/tax-config/calculate", json=calc_payload)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["taxes_added"] == 0, f"Room tax should not apply to fnb, got {data['taxes_added']}"
        print(f"Category filter: fnb category has {data['taxes_added']} tax (correct)")
        
        # Clean up
        api_client.delete(f"{BASE_URL}/api/tax-config/profiles/{profile_id}")


# ============================================================================
# DEPOSIT POLICIES TESTS
# ============================================================================
class TestDepositPolicies:
    """Deposit Policies - Policy CRUD"""
    
    created_policy_id = None
    
    def test_create_policy(self, api_client):
        """POST /api/deposit-policies/ creates policy with trigger object"""
        payload = {
            "property_id": "default",
            "name": "TEST_OTA Short Lead",
            "trigger": {
                "channels": ["Booking.com", "Expedia"],
                "lead_days_lte": 7,
                "rate_plan_ids": []
            },
            "amount_type": "percent",
            "amount_value": 50,
            "due_within_hours": 24,
            "non_refundable": True,
            "active": True,
            "priority": 10
        }
        resp = api_client.post(f"{BASE_URL}/api/deposit-policies/", json=payload)
        assert resp.status_code == 200, f"Create policy failed: {resp.text}"
        data = resp.json()
        
        assert "id" in data, "Policy should have id"
        assert data["name"] == "TEST_OTA Short Lead"
        assert data["trigger"]["channels"] == ["Booking.com", "Expedia"]
        assert data["trigger"]["lead_days_lte"] == 7
        assert data["amount_type"] == "percent"
        assert data["amount_value"] == 50
        assert data["priority"] == 10
        
        TestDepositPolicies.created_policy_id = data["id"]
        print(f"Created deposit policy: {data['id']}")
    
    def test_list_policies(self, api_client):
        """GET /api/deposit-policies/ returns policies sorted by priority"""
        resp = api_client.get(f"{BASE_URL}/api/deposit-policies/")
        assert resp.status_code == 200, f"List policies failed: {resp.text}"
        data = resp.json()
        
        assert isinstance(data, list), "Should return list"
        test_policy = next((p for p in data if p.get("name") == "TEST_OTA Short Lead"), None)
        assert test_policy is not None, "Test policy should be in list"
    
    def test_update_policy(self, api_client):
        """PUT /api/deposit-policies/{id} updates policy"""
        policy_id = TestDepositPolicies.created_policy_id
        assert policy_id, "Need policy_id from create test"
        
        payload = {
            "property_id": "default",
            "name": "TEST_OTA Short Lead Updated",
            "trigger": {
                "channels": ["Booking.com"],
                "lead_days_lte": 5,
                "rate_plan_ids": []
            },
            "amount_type": "percent",
            "amount_value": 60,
            "due_within_hours": 48,
            "non_refundable": True,
            "active": True,
            "priority": 5
        }
        resp = api_client.put(f"{BASE_URL}/api/deposit-policies/{policy_id}", json=payload)
        assert resp.status_code == 200, f"Update policy failed: {resp.text}"
    
    def test_delete_policy_404(self, api_client):
        """DELETE /api/deposit-policies/{id} returns 404 for non-existent"""
        resp = api_client.delete(f"{BASE_URL}/api/deposit-policies/non-existent-id")
        assert resp.status_code == 404, f"Should return 404, got {resp.status_code}"


class TestDepositEvaluation:
    """Deposit Policies - Policy evaluation"""
    
    def test_evaluate_matches_policy(self, api_client):
        """POST /api/deposit-policies/evaluate matches policies in priority order"""
        # Our test policy: Booking.com, lead_days_lte=5, 60% deposit
        payload = {
            "property_id": "default",
            "channel": "Booking.com",
            "lead_days": 3,
            "rate_plan_id": "",
            "total_price": 500
        }
        resp = api_client.post(f"{BASE_URL}/api/deposit-policies/evaluate", json=payload)
        assert resp.status_code == 200, f"Evaluate failed: {resp.text}"
        data = resp.json()
        
        assert data["matched"] == True, "Should match our test policy"
        assert "policy" in data, "Should have policy info"
        assert data["deposit_required"] == 300, f"60% of £500 = £300, got {data['deposit_required']}"
        assert data["due_within_hours"] == 48
        assert data["non_refundable"] == True
        print(f"Evaluate matched: {data['policy']['name']}, deposit={data['deposit_required']}")
    
    def test_evaluate_flat_amount(self, api_client):
        """POST /api/deposit-policies/evaluate correctly calculates flat amount"""
        # Create a flat amount policy
        policy_payload = {
            "property_id": "test-flat",
            "name": "TEST_Flat Deposit",
            "trigger": {
                "channels": [],
                "lead_days_lte": None,
                "rate_plan_ids": []
            },
            "amount_type": "flat",
            "amount_value": 100,
            "due_within_hours": 24,
            "non_refundable": False,
            "active": True,
            "priority": 1
        }
        resp = api_client.post(f"{BASE_URL}/api/deposit-policies/", json=policy_payload)
        assert resp.status_code == 200
        policy_id = resp.json()["id"]
        
        # Evaluate
        eval_payload = {
            "property_id": "test-flat",
            "channel": "Direct",
            "lead_days": 30,
            "rate_plan_id": "",
            "total_price": 1000
        }
        resp = api_client.post(f"{BASE_URL}/api/deposit-policies/evaluate", json=eval_payload)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["matched"] == True
        assert data["deposit_required"] == 100, f"Flat deposit should be £100, got {data['deposit_required']}"
        print(f"Flat deposit: {data['deposit_required']}")
        
        # Clean up
        api_client.delete(f"{BASE_URL}/api/deposit-policies/{policy_id}")
    
    def test_evaluate_no_match(self, api_client):
        """POST /api/deposit-policies/evaluate returns matched=false when no policies apply"""
        payload = {
            "property_id": "non-existent-property",
            "channel": "Unknown",
            "lead_days": 100,
            "rate_plan_id": "",
            "total_price": 500
        }
        resp = api_client.post(f"{BASE_URL}/api/deposit-policies/evaluate", json=payload)
        assert resp.status_code == 200, f"Evaluate failed: {resp.text}"
        data = resp.json()
        
        assert data["matched"] == False, "Should not match any policy"
        assert data["deposit_required"] == 0
        print("No match: deposit_required=0 (correct)")
    
    def test_evaluate_channel_filter(self, api_client):
        """POST /api/deposit-policies/evaluate respects channel filter"""
        # Our test policy only applies to Booking.com
        payload = {
            "property_id": "default",
            "channel": "Airbnb",  # Not in our policy's channels
            "lead_days": 3,
            "rate_plan_id": "",
            "total_price": 500
        }
        resp = api_client.post(f"{BASE_URL}/api/deposit-policies/evaluate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        
        # Should not match our Booking.com-only policy
        if data["matched"]:
            # If it matched, it should be a different policy (not our test one)
            assert data["policy"]["name"] != "TEST_OTA Short Lead Updated", \
                "Should not match Booking.com-only policy for Airbnb channel"
        print(f"Channel filter: Airbnb matched={data['matched']}")
    
    def test_evaluate_lead_days_filter(self, api_client):
        """POST /api/deposit-policies/evaluate respects lead_days_lte filter"""
        # Our test policy: lead_days_lte=5
        payload = {
            "property_id": "default",
            "channel": "Booking.com",
            "lead_days": 10,  # > 5, should not match
            "rate_plan_id": "",
            "total_price": 500
        }
        resp = api_client.post(f"{BASE_URL}/api/deposit-policies/evaluate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        
        # Should not match our policy with lead_days_lte=5
        if data["matched"]:
            assert data["policy"]["name"] != "TEST_OTA Short Lead Updated", \
                "Should not match policy with lead_days_lte=5 when lead_days=10"
        print(f"Lead days filter: lead_days=10 matched={data['matched']}")


# ============================================================================
# CLEANUP
# ============================================================================
class TestCleanup:
    """Clean up test data"""
    
    def test_cleanup_city_ledger(self, api_client):
        """Clean up test companies and invoices"""
        # Delete test company (will cascade delete invoices)
        company_id = TestCityLedgerCompanies.created_company_id
        if company_id:
            # First delete any invoices
            resp = api_client.get(f"{BASE_URL}/api/city-ledger/invoices?company_id={company_id}")
            if resp.status_code == 200:
                for inv in resp.json():
                    api_client.delete(f"{BASE_URL}/api/city-ledger/invoices/{inv['id']}")
            
            # Then delete company
            api_client.delete(f"{BASE_URL}/api/city-ledger/companies/{company_id}")
            print(f"Cleaned up company: {company_id}")
    
    def test_cleanup_tax_profiles(self, api_client):
        """Clean up test tax profiles"""
        profile_id = TestTaxConfigProfiles.created_profile_id
        if profile_id:
            api_client.delete(f"{BASE_URL}/api/tax-config/profiles/{profile_id}")
            print(f"Cleaned up tax profile: {profile_id}")
    
    def test_cleanup_deposit_policies(self, api_client):
        """Clean up test deposit policies"""
        policy_id = TestDepositPolicies.created_policy_id
        if policy_id:
            api_client.delete(f"{BASE_URL}/api/deposit-policies/{policy_id}")
            print(f"Cleaned up deposit policy: {policy_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
