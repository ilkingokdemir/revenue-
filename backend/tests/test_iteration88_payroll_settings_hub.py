"""
Iteration 88 - Testing Enhanced Payroll Automation & Settings Hub
Tests:
1. Enhanced Payroll Runs: Configure button, Play/Pause toggle, MODE/FREQUENCY/LAST RUN/NEXT RUN fields
2. Enhanced Payroll Runs: Automation Plan (window, rule, upcoming dates, timezone)
3. Settings Hub: Seed defaults (currencies, room categories, booking sources, expense categories)
4. Settings Hub: CRUD for 6 settings sections
5. Regression: Finance tabs still work
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

class TestAuth:
    """Authentication for testing"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return session


class TestPayrollConfig(TestAuth):
    """Test Enhanced Payroll Automation Config"""
    
    def test_get_payroll_runs_with_config(self, auth_session):
        """GET /api/finance/payroll-runs/{property_id} returns runs and config"""
        response = auth_session.get(f"{BASE_URL}/api/finance/payroll-runs/all")
        assert response.status_code == 200
        data = response.json()
        
        # Should return runs array and config object
        assert "runs" in data, "Response should have 'runs' array"
        assert "config" in data, "Response should have 'config' object"
        
        # Config should have mode, frequency, next_run
        config = data["config"]
        assert "mode" in config, "Config should have 'mode'"
        assert "frequency" in config, "Config should have 'frequency'"
        print(f"PASS: Payroll runs endpoint returns runs and config")
    
    def test_update_payroll_config(self, auth_session):
        """PUT /api/finance/payroll-config/{property_id} updates config"""
        config_data = {
            "mode": "pause",
            "frequency": "monthly",
            "next_run": "2026-02-01",
            "rule": "Every month on day 1",
            "window_start": "2026-01-01",
            "timezone": "Europe/London"
        }
        
        response = auth_session.put(f"{BASE_URL}/api/finance/payroll-config/all", json=config_data)
        assert response.status_code == 200
        data = response.json()
        
        # Verify config was saved
        assert data.get("mode") == "pause", "Mode should be 'pause'"
        assert data.get("frequency") == "monthly", "Frequency should be 'monthly'"
        assert data.get("next_run") == "2026-02-01", "Next run should be set"
        assert data.get("rule") == "Every month on day 1", "Rule should be set"
        assert data.get("timezone") == "Europe/London", "Timezone should be set"
        print(f"PASS: Payroll config updated successfully")
    
    def test_toggle_payroll_mode_to_play(self, auth_session):
        """PUT /api/finance/payroll-config/{property_id} can toggle mode to play"""
        config_data = {
            "mode": "play",
            "frequency": "monthly",
            "next_run": "2026-02-01"
        }
        
        response = auth_session.put(f"{BASE_URL}/api/finance/payroll-config/all", json=config_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("mode") == "play", "Mode should be 'play'"
        print(f"PASS: Payroll mode toggled to 'play'")
    
    def test_toggle_payroll_mode_to_pause(self, auth_session):
        """PUT /api/finance/payroll-config/{property_id} can toggle mode to pause"""
        config_data = {
            "mode": "pause",
            "frequency": "monthly",
            "next_run": "2026-02-01"
        }
        
        response = auth_session.put(f"{BASE_URL}/api/finance/payroll-config/all", json=config_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("mode") == "pause", "Mode should be 'pause'"
        print(f"PASS: Payroll mode toggled to 'pause'")
    
    def test_create_payroll_run_with_source(self, auth_session):
        """POST /api/finance/payroll-runs creates run with source field"""
        run_data = {
            "property_id": "all",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "staff_count": 5,
            "gross_total": 10000,
            "deductions": 1000,
            "net_total": 9000,  # Frontend calculates and sends this
            "source": "manual",
            "notes": "TEST_payroll_run"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/finance/payroll-runs", json=run_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("source") == "manual", "Source should be 'manual'"
        assert data.get("gross_total") == 10000, "Gross total should be set"
        assert "id" in data, "Should return id"
        
        # Store for cleanup
        self.__class__.test_payroll_run_id = data["id"]
        print(f"PASS: Payroll run created with source field")


class TestSettingsHubSeedDefaults(TestAuth):
    """Test Settings Hub Seed Defaults"""
    
    def test_seed_defaults_endpoint(self, auth_session):
        """GET /api/settings/seed-defaults seeds default data"""
        response = auth_session.get(f"{BASE_URL}/api/settings/seed-defaults")
        assert response.status_code == 200
        data = response.json()
        
        # Should return seeded collections (or empty if already seeded)
        assert "seeded" in data, "Response should have 'seeded' array"
        print(f"PASS: Seed defaults endpoint works, seeded: {data['seeded']}")


class TestSettingsHubCurrencies(TestAuth):
    """Test Currencies CRUD"""
    
    def test_list_currencies(self, auth_session):
        """GET /api/settings/currencies returns currencies"""
        response = auth_session.get(f"{BASE_URL}/api/settings/currencies")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        # After seeding, should have at least 4 currencies
        if len(data) >= 4:
            # Check for expected currencies
            codes = [c.get("code") for c in data]
            assert "GBP" in codes, "Should have GBP"
            assert "EUR" in codes, "Should have EUR"
            assert "USD" in codes, "Should have USD"
            assert "TRY" in codes, "Should have TRY"
            print(f"PASS: Currencies list returns {len(data)} currencies with expected codes")
        else:
            print(f"PASS: Currencies list returns {len(data)} currencies")
    
    def test_create_currency(self, auth_session):
        """POST /api/settings/currencies creates currency"""
        currency_data = {
            "code": "TEST",
            "name": "Test Currency",
            "symbol": "T$"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/settings/currencies", json=currency_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("code") == "TEST", "Code should match"
        assert data.get("name") == "Test Currency", "Name should match"
        assert "id" in data, "Should return id"
        
        self.__class__.test_currency_id = data["id"]
        print(f"PASS: Currency created successfully")
    
    def test_delete_currency(self, auth_session):
        """DELETE /api/settings/currencies/{id} deletes currency"""
        if not hasattr(self.__class__, 'test_currency_id'):
            pytest.skip("No test currency to delete")
        
        response = auth_session.delete(f"{BASE_URL}/api/settings/currencies/{self.__class__.test_currency_id}")
        assert response.status_code == 200
        print(f"PASS: Currency deleted successfully")


class TestSettingsHubRoomCategories(TestAuth):
    """Test Room Categories CRUD"""
    
    def test_list_room_categories(self, auth_session):
        """GET /api/settings/room-categories returns room categories"""
        response = auth_session.get(f"{BASE_URL}/api/settings/room-categories")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        if len(data) >= 4:
            codes = [c.get("code") for c in data]
            assert "STD" in codes, "Should have Standard"
            assert "DLX" in codes, "Should have Deluxe"
            print(f"PASS: Room categories list returns {len(data)} categories")
        else:
            print(f"PASS: Room categories list returns {len(data)} categories")
    
    def test_create_room_category(self, auth_session):
        """POST /api/settings/room-categories creates room category"""
        category_data = {
            "code": "TEST",
            "name": "Test Room",
            "description": "Test room category"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/settings/room-categories", json=category_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("code") == "TEST", "Code should match"
        assert "id" in data, "Should return id"
        
        self.__class__.test_room_cat_id = data["id"]
        print(f"PASS: Room category created successfully")
    
    def test_delete_room_category(self, auth_session):
        """DELETE /api/settings/room-categories/{id} deletes room category"""
        if not hasattr(self.__class__, 'test_room_cat_id'):
            pytest.skip("No test room category to delete")
        
        response = auth_session.delete(f"{BASE_URL}/api/settings/room-categories/{self.__class__.test_room_cat_id}")
        assert response.status_code == 200
        print(f"PASS: Room category deleted successfully")


class TestSettingsHubBookingSources(TestAuth):
    """Test Booking Sources CRUD with Commission Rates"""
    
    def test_list_booking_sources(self, auth_session):
        """GET /api/settings/booking-sources returns booking sources with commission rates"""
        response = auth_session.get(f"{BASE_URL}/api/settings/booking-sources")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        if len(data) >= 6:
            # Check for expected sources with commission rates
            for source in data:
                assert "commission_rate" in source, f"Source {source.get('name')} should have commission_rate"
            
            # Check specific commission rates
            booking_com = next((s for s in data if s.get("code") == "booking_com"), None)
            if booking_com:
                assert booking_com.get("commission_rate") == 15, "Booking.com should have 15% commission"
            
            direct = next((s for s in data if s.get("code") == "direct"), None)
            if direct:
                assert direct.get("commission_rate") == 0, "Direct should have 0% commission"
            
            print(f"PASS: Booking sources list returns {len(data)} sources with commission rates")
        else:
            print(f"PASS: Booking sources list returns {len(data)} sources")
    
    def test_create_booking_source(self, auth_session):
        """POST /api/settings/booking-sources creates booking source with commission"""
        source_data = {
            "code": "test_ota",
            "name": "Test OTA",
            "commission_rate": 12
        }
        
        response = auth_session.post(f"{BASE_URL}/api/settings/booking-sources", json=source_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("code") == "test_ota", "Code should match"
        assert data.get("commission_rate") == 12, "Commission rate should be 12"
        assert "id" in data, "Should return id"
        
        self.__class__.test_source_id = data["id"]
        print(f"PASS: Booking source created with commission rate")
    
    def test_delete_booking_source(self, auth_session):
        """DELETE /api/settings/booking-sources/{id} deletes booking source"""
        if not hasattr(self.__class__, 'test_source_id'):
            pytest.skip("No test booking source to delete")
        
        response = auth_session.delete(f"{BASE_URL}/api/settings/booking-sources/{self.__class__.test_source_id}")
        assert response.status_code == 200
        print(f"PASS: Booking source deleted successfully")


class TestSettingsHubExpenseCategories(TestAuth):
    """Test Expense Categories CRUD"""
    
    def test_list_expense_categories(self, auth_session):
        """GET /api/settings/expense-categories returns expense categories"""
        response = auth_session.get(f"{BASE_URL}/api/settings/expense-categories")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        if len(data) >= 7:
            codes = [c.get("code") for c in data]
            assert "rent" in codes, "Should have Rent"
            assert "commission" in codes, "Should have Commission"
            assert "laundry" in codes, "Should have Laundry"
            print(f"PASS: Expense categories list returns {len(data)} categories")
        else:
            print(f"PASS: Expense categories list returns {len(data)} categories")
    
    def test_create_expense_category(self, auth_session):
        """POST /api/settings/expense-categories creates expense category"""
        category_data = {
            "code": "test_expense",
            "name": "Test Expense"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/settings/expense-categories", json=category_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("code") == "test_expense", "Code should match"
        assert "id" in data, "Should return id"
        
        self.__class__.test_expense_cat_id = data["id"]
        print(f"PASS: Expense category created successfully")
    
    def test_delete_expense_category(self, auth_session):
        """DELETE /api/settings/expense-categories/{id} deletes expense category"""
        if not hasattr(self.__class__, 'test_expense_cat_id'):
            pytest.skip("No test expense category to delete")
        
        response = auth_session.delete(f"{BASE_URL}/api/settings/expense-categories/{self.__class__.test_expense_cat_id}")
        assert response.status_code == 200
        print(f"PASS: Expense category deleted successfully")


class TestSettingsHubLaundryProviders(TestAuth):
    """Test Laundry Providers CRUD"""
    
    def test_list_laundry_providers(self, auth_session):
        """GET /api/settings/laundry-providers returns laundry providers"""
        response = auth_session.get(f"{BASE_URL}/api/settings/laundry-providers")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        print(f"PASS: Laundry providers list returns {len(data)} providers")
    
    def test_create_laundry_provider(self, auth_session):
        """POST /api/settings/laundry-providers creates laundry provider"""
        provider_data = {
            "name": "Test Laundry Co",
            "contact": "John Smith",
            "phone": "+44 123 456 7890",
            "email": "test@laundry.com"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/settings/laundry-providers", json=provider_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("name") == "Test Laundry Co", "Name should match"
        assert "id" in data, "Should return id"
        
        self.__class__.test_laundry_id = data["id"]
        print(f"PASS: Laundry provider created successfully")
    
    def test_delete_laundry_provider(self, auth_session):
        """DELETE /api/settings/laundry-providers/{id} deletes laundry provider"""
        if not hasattr(self.__class__, 'test_laundry_id'):
            pytest.skip("No test laundry provider to delete")
        
        response = auth_session.delete(f"{BASE_URL}/api/settings/laundry-providers/{self.__class__.test_laundry_id}")
        assert response.status_code == 200
        print(f"PASS: Laundry provider deleted successfully")


class TestSettingsHubDocumentTypes(TestAuth):
    """Test Booking Document Types CRUD"""
    
    def test_list_document_types(self, auth_session):
        """GET /api/settings/document-types returns document types"""
        response = auth_session.get(f"{BASE_URL}/api/settings/document-types")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        print(f"PASS: Document types list returns {len(data)} types")
    
    def test_create_document_type(self, auth_session):
        """POST /api/settings/document-types creates document type"""
        doc_data = {
            "code": "test_doc",
            "name": "Test Document"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/settings/document-types", json=doc_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("code") == "test_doc", "Code should match"
        assert "id" in data, "Should return id"
        
        self.__class__.test_doc_id = data["id"]
        print(f"PASS: Document type created successfully")
    
    def test_delete_document_type(self, auth_session):
        """DELETE /api/settings/document-types/{id} deletes document type"""
        if not hasattr(self.__class__, 'test_doc_id'):
            pytest.skip("No test document type to delete")
        
        response = auth_session.delete(f"{BASE_URL}/api/settings/document-types/{self.__class__.test_doc_id}")
        assert response.status_code == 200
        print(f"PASS: Document type deleted successfully")


class TestFinanceRegression(TestAuth):
    """Regression tests for existing Finance tabs"""
    
    def test_finance_dashboard(self, auth_session):
        """GET /api/finance/dashboard/{property_id} still works"""
        response = auth_session.get(f"{BASE_URL}/api/finance/dashboard/all")
        assert response.status_code == 200
        data = response.json()
        
        assert "overview" in data, "Should have overview"
        assert "period" in data, "Should have period"
        print(f"PASS: Finance dashboard endpoint works")
    
    def test_finance_earned_salaries(self, auth_session):
        """GET /api/finance/earned-salaries/{property_id} still works"""
        response = auth_session.get(f"{BASE_URL}/api/finance/earned-salaries/all")
        assert response.status_code == 200
        data = response.json()
        
        assert "entries" in data, "Should have entries"
        assert "stats" in data, "Should have stats"
        print(f"PASS: Earned salaries endpoint works")
    
    def test_finance_adjustments(self, auth_session):
        """GET /api/finance/adjustments/{property_id} still works"""
        response = auth_session.get(f"{BASE_URL}/api/finance/adjustments/all")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        print(f"PASS: Adjustments endpoint works")
    
    def test_finance_cash_advances(self, auth_session):
        """GET /api/finance/cash-advances/{property_id} still works"""
        response = auth_session.get(f"{BASE_URL}/api/finance/cash-advances/all")
        assert response.status_code == 200
        data = response.json()
        
        assert "advances" in data, "Should have advances"
        assert "stats" in data, "Should have stats"
        print(f"PASS: Cash advances endpoint works")
    
    def test_finance_adjustment_categories(self, auth_session):
        """GET /api/finance/adjustment-categories still works"""
        response = auth_session.get(f"{BASE_URL}/api/finance/adjustment-categories")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        print(f"PASS: Adjustment categories endpoint works")
    
    def test_finance_expenses(self, auth_session):
        """GET /api/finance/expenses/{property_id} still works"""
        response = auth_session.get(f"{BASE_URL}/api/finance/expenses/all")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        print(f"PASS: Expenses endpoint works")
    
    def test_finance_recurring_expenses(self, auth_session):
        """GET /api/finance/recurring-expenses/{property_id} still works"""
        response = auth_session.get(f"{BASE_URL}/api/finance/recurring-expenses/all")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Should return array"
        print(f"PASS: Recurring expenses endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
