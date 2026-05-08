"""
Iteration 85 - Finance Dashboard Enhancements Tests
Tests for:
1. GET /api/finance/dashboard-history/{property_id} - 6-month historical data
2. GET /api/finance/dashboard/{property_id} - expense_details array in response
3. PUT /api/finance/expenses/{id} - Pay button functionality (mark as paid)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFinanceDashboardEnhancements:
    """Tests for new Finance Dashboard features in iteration 85"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    # ==================== Dashboard History Endpoint Tests ====================
    
    def test_dashboard_history_returns_6_months(self):
        """GET /api/finance/dashboard-history/{property_id} returns 6-month data"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard-history/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 6, f"Expected 6 months of data, got {len(data)}"
        
        # Verify each month has required fields
        for month_data in data:
            assert "month" in month_data, "Each entry should have 'month' field"
            assert "revenue" in month_data, "Each entry should have 'revenue' field"
            assert "costs" in month_data, "Each entry should have 'costs' field"
            assert "profit" in month_data, "Each entry should have 'profit' field"
            
            # Verify data types
            assert isinstance(month_data["revenue"], (int, float)), "Revenue should be numeric"
            assert isinstance(month_data["costs"], (int, float)), "Costs should be numeric"
            assert isinstance(month_data["profit"], (int, float)), "Profit should be numeric"
        
        print(f"PASS: Dashboard history returns 6 months with correct structure")
    
    def test_dashboard_history_custom_months(self):
        """GET /api/finance/dashboard-history/{property_id}?months=3 returns custom months"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard-history/all?months=3")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert len(data) == 3, f"Expected 3 months of data, got {len(data)}"
        print(f"PASS: Dashboard history respects months parameter")
    
    def test_dashboard_history_profit_calculation(self):
        """Verify profit = revenue - costs in history data"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard-history/all")
        assert response.status_code == 200
        
        data = response.json()
        for month_data in data:
            expected_profit = round(month_data["revenue"] - month_data["costs"], 2)
            actual_profit = round(month_data["profit"], 2)
            assert actual_profit == expected_profit, f"Profit mismatch for {month_data['month']}: expected {expected_profit}, got {actual_profit}"
        
        print(f"PASS: Profit calculation is correct (revenue - costs)")
    
    def test_dashboard_history_requires_auth(self):
        """Dashboard history endpoint requires authentication"""
        unauth_session = requests.Session()
        response = unauth_session.get(f"{BASE_URL}/api/finance/dashboard-history/all")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print(f"PASS: Dashboard history requires authentication")
    
    def test_dashboard_history_with_property_id(self):
        """Dashboard history works with specific property_id"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard-history/test-property")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert len(data) == 6, "Should return 6 months even for specific property"
        print(f"PASS: Dashboard history works with specific property_id")
    
    # ==================== Dashboard Expense Details Tests ====================
    
    def test_dashboard_includes_expense_details(self):
        """GET /api/finance/dashboard/{property_id} includes expense_details array"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "expense_details" in data, "Response should include expense_details array"
        assert isinstance(data["expense_details"], list), "expense_details should be a list"
        
        print(f"PASS: Dashboard includes expense_details array")
    
    def test_expense_details_structure(self):
        """Verify expense_details has correct structure"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/all")
        assert response.status_code == 200
        
        data = response.json()
        expense_details = data.get("expense_details", [])
        
        # If there are expenses, verify structure
        if len(expense_details) > 0:
            expense = expense_details[0]
            required_fields = ["id", "date", "category", "vendor", "details", "amount", "status"]
            for field in required_fields:
                assert field in expense, f"Expense should have '{field}' field"
            
            # Verify amount is numeric
            assert isinstance(expense["amount"], (int, float)), "Amount should be numeric"
            print(f"PASS: Expense details have correct structure with {len(expense_details)} items")
        else:
            print(f"PASS: Expense details array is empty (no expenses in period)")
    
    def test_dashboard_overview_includes_margin(self):
        """Dashboard overview includes margin percentage"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/all")
        assert response.status_code == 200
        
        data = response.json()
        overview = data.get("overview", {})
        assert "margin" in overview, "Overview should include margin"
        assert isinstance(overview["margin"], (int, float)), "Margin should be numeric"
        print(f"PASS: Dashboard overview includes margin: {overview['margin']}%")
    
    def test_dashboard_revenue_sources(self):
        """Dashboard includes revenue_sources with Source/Count/Revenue"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/all")
        assert response.status_code == 200
        
        data = response.json()
        assert "revenue_sources" in data, "Response should include revenue_sources"
        
        revenue_sources = data.get("revenue_sources", [])
        if len(revenue_sources) > 0:
            source = revenue_sources[0]
            assert "source" in source, "Revenue source should have 'source' field"
            assert "count" in source, "Revenue source should have 'count' field"
            assert "revenue" in source, "Revenue source should have 'revenue' field"
            print(f"PASS: Revenue sources have correct structure with {len(revenue_sources)} sources")
        else:
            print(f"PASS: Revenue sources array is empty (no bookings in period)")
    
    # ==================== Pay Expense Tests ====================
    
    def test_create_and_pay_expense(self):
        """Create expense and mark as paid via PUT"""
        # Create a test expense
        create_response = self.session.post(f"{BASE_URL}/api/finance/expenses", json={
            "property_id": "all",
            "date": "2026-01-15",
            "category": "other",
            "vendor": "TEST_PayTest Vendor",
            "details": "Test expense for pay button",
            "amount": 100.00,
            "status": "pending"
        })
        assert create_response.status_code == 200, f"Failed to create expense: {create_response.text}"
        
        expense = create_response.json()
        expense_id = expense.get("id")
        assert expense_id, "Created expense should have an id"
        assert expense.get("status") == "pending", "New expense should be pending"
        
        # Pay the expense
        pay_response = self.session.put(f"{BASE_URL}/api/finance/expenses/{expense_id}", json={
            "status": "paid"
        })
        assert pay_response.status_code == 200, f"Failed to pay expense: {pay_response.text}"
        
        paid_expense = pay_response.json()
        assert paid_expense.get("status") == "paid", f"Expense status should be 'paid', got {paid_expense.get('status')}"
        
        # Verify via GET
        get_response = self.session.get(f"{BASE_URL}/api/finance/expenses/all")
        assert get_response.status_code == 200
        
        expenses = get_response.json()
        found = next((e for e in expenses if e.get("id") == expense_id), None)
        assert found, "Expense should be found in list"
        assert found.get("status") == "paid", "Expense should be marked as paid"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/finance/expenses/{expense_id}")
        print(f"PASS: Create and pay expense workflow works correctly")
    
    def test_expense_status_in_dashboard_details(self):
        """Verify expense status (paid/accrued) appears in dashboard expense_details"""
        # Create a pending expense
        create_response = self.session.post(f"{BASE_URL}/api/finance/expenses", json={
            "property_id": "all",
            "date": "2026-01-15",
            "category": "other",
            "vendor": "TEST_StatusCheck Vendor",
            "amount": 50.00,
            "status": "pending"
        })
        assert create_response.status_code == 200
        expense_id = create_response.json().get("id")
        
        # Check dashboard shows pending status
        dashboard_response = self.session.get(f"{BASE_URL}/api/finance/dashboard/all?from_date=2026-01-01&to_date=2026-01-31")
        assert dashboard_response.status_code == 200
        
        expense_details = dashboard_response.json().get("expense_details", [])
        found = next((e for e in expense_details if e.get("id") == expense_id), None)
        if found:
            assert found.get("status") == "pending", "Expense should show pending status"
        
        # Pay the expense
        self.session.put(f"{BASE_URL}/api/finance/expenses/{expense_id}", json={"status": "paid"})
        
        # Check dashboard shows paid status
        dashboard_response2 = self.session.get(f"{BASE_URL}/api/finance/dashboard/all?from_date=2026-01-01&to_date=2026-01-31")
        expense_details2 = dashboard_response2.json().get("expense_details", [])
        found2 = next((e for e in expense_details2 if e.get("id") == expense_id), None)
        if found2:
            assert found2.get("status") == "paid", "Expense should show paid status after update"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/finance/expenses/{expense_id}")
        print(f"PASS: Expense status correctly reflected in dashboard expense_details")
    
    # ==================== Regression Tests ====================
    
    def test_dashboard_still_returns_overview(self):
        """Regression: Dashboard still returns overview with all KPIs"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/all")
        assert response.status_code == 200
        
        data = response.json()
        overview = data.get("overview", {})
        
        required_kpis = ["gross", "room_revenue", "adr", "commission", "expenses", "payroll", "total_costs", "net", "margin"]
        for kpi in required_kpis:
            assert kpi in overview, f"Overview should include '{kpi}'"
        
        print(f"PASS: Dashboard overview includes all {len(required_kpis)} KPIs")
    
    def test_dashboard_still_returns_operating_costs(self):
        """Regression: Dashboard still returns operating_costs breakdown"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/all")
        assert response.status_code == 200
        
        data = response.json()
        assert "operating_costs" in data, "Response should include operating_costs"
        assert isinstance(data["operating_costs"], list), "operating_costs should be a list"
        print(f"PASS: Dashboard includes operating_costs breakdown")
    
    def test_dashboard_period_filter(self):
        """Regression: Dashboard respects from_date and to_date filters"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/all?from_date=2026-01-01&to_date=2026-01-31")
        assert response.status_code == 200
        
        data = response.json()
        period = data.get("period", {})
        assert period.get("from") == "2026-01-01", "Period from should match filter"
        assert period.get("to") == "2026-01-31", "Period to should match filter"
        print(f"PASS: Dashboard respects date filters")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
