"""
Finance Module Backend Tests - Iteration 84
Tests all 8 sub-modules: Dashboard, Earned Salaries, Payroll Runs, Adjustments,
Cash Advances, Adjustment Categories, Expenses, Recurring Expenses
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFinanceModule:
    """Finance Module API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        # Store cookies for subsequent requests
        self.property_id = "all"
        yield
        
        # Cleanup - delete test data
        self._cleanup_test_data()
    
    def _cleanup_test_data(self):
        """Clean up TEST_ prefixed data"""
        pass  # Data cleanup handled by individual tests
    
    # ==================== 1. FINANCE DASHBOARD ====================
    
    def test_finance_dashboard_returns_overview(self):
        """Test finance dashboard returns overview with KPIs"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/{self.property_id}")
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        
        data = response.json()
        assert "period" in data
        assert "overview" in data
        assert "operating_costs" in data
        assert "revenue_sources" in data
        
        # Verify overview KPIs
        overview = data["overview"]
        assert "gross" in overview
        assert "room_revenue" in overview
        assert "adr" in overview
        assert "commission" in overview
        assert "expenses" in overview
        assert "payroll" in overview
        assert "total_costs" in overview
        assert "net" in overview
        assert "margin" in overview
        print(f"Dashboard KPIs: Gross={overview['gross']}, Net={overview['net']}, Margin={overview['margin']}%")
    
    def test_finance_dashboard_with_date_filters(self):
        """Test finance dashboard respects date filters"""
        from_date = "2026-01-01"
        to_date = "2026-01-31"
        response = self.session.get(
            f"{BASE_URL}/api/finance/dashboard/{self.property_id}?from_date={from_date}&to_date={to_date}"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["period"]["from"] == from_date
        assert data["period"]["to"] == to_date
        print(f"Dashboard filtered by period: {from_date} to {to_date}")
    
    def test_finance_dashboard_requires_auth(self):
        """Test finance dashboard requires authentication"""
        unauth_session = requests.Session()
        response = unauth_session.get(f"{BASE_URL}/api/finance/dashboard/{self.property_id}")
        assert response.status_code == 401
        print("Dashboard correctly requires authentication")
    
    # ==================== 2. EARNED SALARIES ====================
    
    def test_earned_salaries_list(self):
        """Test listing earned salaries"""
        response = self.session.get(f"{BASE_URL}/api/finance/earned-salaries/{self.property_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "entries" in data
        assert "stats" in data
        assert "staff_count" in data["stats"]
        assert "working_days" in data["stats"]
        assert "total_rows" in data["stats"]
        assert "total_earned" in data["stats"]
        print(f"Earned salaries stats: {data['stats']}")
    
    def test_earned_salaries_create(self):
        """Test creating an earned salary entry"""
        salary_data = {
            "property_id": self.property_id,
            "staff_id": f"TEST_staff_{uuid.uuid4().hex[:8]}",
            "staff_name": "TEST_John Smith",
            "role": "receptionist",
            "date": "2026-01-15",
            "amount": 150.00,
            "notes": "Test salary entry"
        }
        
        response = self.session.post(f"{BASE_URL}/api/finance/earned-salaries", json=salary_data)
        assert response.status_code == 200, f"Create salary failed: {response.text}"
        
        data = response.json()
        assert data["staff_name"] == salary_data["staff_name"]
        assert data["amount"] == salary_data["amount"]
        assert "id" in data
        print(f"Created salary entry: {data['id']}")
    
    def test_earned_salaries_with_date_filter(self):
        """Test earned salaries with date filter"""
        response = self.session.get(
            f"{BASE_URL}/api/finance/earned-salaries/{self.property_id}?from_date=2026-01-01&to_date=2026-01-31"
        )
        assert response.status_code == 200
        print("Earned salaries date filter works")
    
    # ==================== 3. PAYROLL RUNS ====================
    
    def test_payroll_runs_list(self):
        """Test listing payroll runs"""
        response = self.session.get(f"{BASE_URL}/api/finance/payroll-runs/{self.property_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "runs" in data
        assert "config" in data
        assert "mode" in data["config"]
        assert "frequency" in data["config"]
        print(f"Payroll config: mode={data['config']['mode']}, frequency={data['config']['frequency']}")
    
    def test_payroll_runs_create(self):
        """Test creating a payroll run"""
        run_data = {
            "property_id": self.property_id,
            "period_start": "2026-01-01",
            "period_end": "2026-01-15",
            "staff_count": 5,
            "gross_total": 5000.00,
            "deductions": 500.00,
            "net_total": 4500.00,
            "status": "draft",
            "source": "manual",
            "notes": "TEST_payroll_run"
        }
        
        response = self.session.post(f"{BASE_URL}/api/finance/payroll-runs", json=run_data)
        assert response.status_code == 200, f"Create payroll run failed: {response.text}"
        
        data = response.json()
        assert data["gross_total"] == run_data["gross_total"]
        assert data["status"] == "draft"
        assert "id" in data
        self.payroll_run_id = data["id"]
        print(f"Created payroll run: {data['id']}")
        
        return data["id"]
    
    def test_payroll_runs_approve_workflow(self):
        """Test payroll run approve workflow"""
        # Create a run first
        run_id = self.test_payroll_runs_create()
        
        # Approve the run
        response = self.session.put(f"{BASE_URL}/api/finance/payroll-runs/{run_id}", json={"status": "approved"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "approved"
        print(f"Payroll run {run_id} approved")
    
    def test_payroll_runs_pay_workflow(self):
        """Test payroll run pay workflow"""
        # Create and approve a run first
        run_id = self.test_payroll_runs_create()
        self.session.put(f"{BASE_URL}/api/finance/payroll-runs/{run_id}", json={"status": "approved"})
        
        # Pay the run
        response = self.session.put(f"{BASE_URL}/api/finance/payroll-runs/{run_id}", json={"status": "paid"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "paid"
        print(f"Payroll run {run_id} paid")
    
    def test_payroll_config_update(self):
        """Test updating payroll automation config"""
        config_data = {
            "mode": "play",
            "frequency": "monthly",
            "next_run": "2026-02-01"
        }
        
        response = self.session.put(f"{BASE_URL}/api/finance/payroll-config/{self.property_id}", json=config_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["mode"] == "play"
        print("Payroll config updated")
    
    # ==================== 4. ADJUSTMENTS ====================
    
    def test_adjustments_list(self):
        """Test listing adjustments"""
        response = self.session.get(f"{BASE_URL}/api/finance/adjustments/{self.property_id}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("Adjustments list works")
    
    def test_adjustments_create_addition(self):
        """Test creating an addition adjustment"""
        adj_data = {
            "property_id": self.property_id,
            "employee_id": f"TEST_emp_{uuid.uuid4().hex[:8]}",
            "employee_name": "TEST_Jane Doe",
            "type": "addition",
            "category": "bonus",
            "amount": 200.00,
            "schedule": "one-time",
            "status": "active",
            "effective_date": "2026-01-15",
            "notes": "Test bonus"
        }
        
        response = self.session.post(f"{BASE_URL}/api/finance/adjustments", json=adj_data)
        assert response.status_code == 200, f"Create adjustment failed: {response.text}"
        
        data = response.json()
        assert data["type"] == "addition"
        assert data["category"] == "bonus"
        assert data["amount"] == 200.00
        assert "id" in data
        self.adjustment_id = data["id"]
        print(f"Created addition adjustment: {data['id']}")
        
        return data["id"]
    
    def test_adjustments_create_deduction(self):
        """Test creating a deduction adjustment"""
        adj_data = {
            "property_id": self.property_id,
            "employee_name": "TEST_Bob Wilson",
            "type": "deduction",
            "category": "deduction",
            "amount": 50.00,
            "schedule": "monthly"
        }
        
        response = self.session.post(f"{BASE_URL}/api/finance/adjustments", json=adj_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["type"] == "deduction"
        print(f"Created deduction adjustment: {data['id']}")
    
    def test_adjustments_filter_by_type(self):
        """Test filtering adjustments by type"""
        response = self.session.get(f"{BASE_URL}/api/finance/adjustments/{self.property_id}?adj_type=addition")
        assert response.status_code == 200
        
        data = response.json()
        for adj in data:
            assert adj["type"] == "addition"
        print("Adjustment type filter works")
    
    def test_adjustments_delete(self):
        """Test deleting an adjustment"""
        adj_id = self.test_adjustments_create_addition()
        
        response = self.session.delete(f"{BASE_URL}/api/finance/adjustments/{adj_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        print(f"Deleted adjustment: {adj_id}")
    
    # ==================== 5. CASH ADVANCES ====================
    
    def test_cash_advances_list(self):
        """Test listing cash advances"""
        response = self.session.get(f"{BASE_URL}/api/finance/cash-advances/{self.property_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "advances" in data
        assert "stats" in data
        assert "total_pending" in data["stats"]
        assert "total_deducted" in data["stats"]
        assert "total_cancelled" in data["stats"]
        print(f"Cash advances stats: {data['stats']}")
    
    def test_cash_advances_create(self):
        """Test creating a cash advance"""
        adv_data = {
            "property_id": self.property_id,
            "employee_id": f"TEST_emp_{uuid.uuid4().hex[:8]}",
            "employee_name": "TEST_Alice Brown",
            "amount": 300.00,
            "notes": "Emergency advance"
        }
        
        response = self.session.post(f"{BASE_URL}/api/finance/cash-advances", json=adv_data)
        assert response.status_code == 200, f"Create advance failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "pending"
        assert data["amount"] == 300.00
        assert "id" in data
        print(f"Created cash advance: {data['id']}")
        
        return data["id"]
    
    def test_cash_advances_deduct_workflow(self):
        """Test deducting a cash advance"""
        adv_id = self.test_cash_advances_create()
        
        response = self.session.put(f"{BASE_URL}/api/finance/cash-advances/{adv_id}", json={"status": "deducted"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "deducted"
        print(f"Cash advance {adv_id} deducted")
    
    def test_cash_advances_cancel_workflow(self):
        """Test cancelling a cash advance"""
        adv_id = self.test_cash_advances_create()
        
        response = self.session.put(f"{BASE_URL}/api/finance/cash-advances/{adv_id}", json={"status": "cancelled"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "cancelled"
        print(f"Cash advance {adv_id} cancelled")
    
    # ==================== 6. ADJUSTMENT CATEGORIES ====================
    
    def test_adjustment_categories_list_and_seed(self):
        """Test listing adjustment categories (auto-seeds 8 defaults)"""
        response = self.session.get(f"{BASE_URL}/api/finance/adjustment-categories")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 8, f"Expected at least 8 default categories, got {len(data)}"
        
        # Verify default categories exist
        codes = [c["code"] for c in data]
        expected_codes = ["bonus", "transport", "meal", "accommodation", "phone", "overtime", "holiday", "tips"]
        for code in expected_codes:
            assert code in codes, f"Missing default category: {code}"
        
        print(f"Found {len(data)} adjustment categories including defaults: {expected_codes}")
    
    def test_adjustment_categories_create_custom(self):
        """Test creating a custom category"""
        cat_data = {
            "code": f"test_custom_{uuid.uuid4().hex[:6]}",
            "name": "TEST_Custom Category",
            "calc_type": "fixed",
            "type": "addition",
            "order": 99
        }
        
        response = self.session.post(f"{BASE_URL}/api/finance/adjustment-categories", json=cat_data)
        assert response.status_code == 200, f"Create category failed: {response.text}"
        
        data = response.json()
        assert data["is_system"] == False
        assert data["status"] == "active"
        assert "id" in data
        print(f"Created custom category: {data['id']}")
        
        return data["id"]
    
    def test_adjustment_categories_disable_enable(self):
        """Test disabling and enabling a category"""
        cat_id = self.test_adjustment_categories_create_custom()
        
        # Disable
        response = self.session.put(f"{BASE_URL}/api/finance/adjustment-categories/{cat_id}", json={"status": "disabled"})
        assert response.status_code == 200
        assert response.json()["status"] == "disabled"
        print(f"Category {cat_id} disabled")
        
        # Enable
        response = self.session.put(f"{BASE_URL}/api/finance/adjustment-categories/{cat_id}", json={"status": "active"})
        assert response.status_code == 200
        assert response.json()["status"] == "active"
        print(f"Category {cat_id} enabled")
    
    def test_adjustment_categories_delete_non_system(self):
        """Test deleting a non-system category"""
        cat_id = self.test_adjustment_categories_create_custom()
        
        response = self.session.delete(f"{BASE_URL}/api/finance/adjustment-categories/{cat_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        print(f"Deleted non-system category: {cat_id}")
    
    def test_adjustment_categories_cannot_delete_system(self):
        """Test that system categories cannot be deleted"""
        # Get categories and find a system one
        response = self.session.get(f"{BASE_URL}/api/finance/adjustment-categories")
        categories = response.json()
        
        system_cat = next((c for c in categories if c.get("is_system")), None)
        if system_cat:
            response = self.session.delete(f"{BASE_URL}/api/finance/adjustment-categories/{system_cat['id']}")
            assert response.status_code == 400
            print(f"Correctly prevented deletion of system category: {system_cat['code']}")
        else:
            print("No system category found to test deletion prevention")
    
    # ==================== 7. EXPENSES ====================
    
    def test_expenses_list(self):
        """Test listing expenses"""
        response = self.session.get(f"{BASE_URL}/api/finance/expenses/{self.property_id}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("Expenses list works")
    
    def test_expenses_create(self):
        """Test creating an expense"""
        exp_data = {
            "property_id": self.property_id,
            "date": "2026-01-15",
            "category": "rent",
            "details": "TEST_Monthly office rent",
            "vendor": "TEST_Landlord Inc",
            "amount": 2500.00,
            "status": "pending"
        }
        
        response = self.session.post(f"{BASE_URL}/api/finance/expenses", json=exp_data)
        assert response.status_code == 200, f"Create expense failed: {response.text}"
        
        data = response.json()
        assert data["category"] == "rent"
        assert data["amount"] == 2500.00
        assert data["status"] == "pending"
        assert "id" in data
        print(f"Created expense: {data['id']}")
        
        return data["id"]
    
    def test_expenses_with_date_filter(self):
        """Test expenses with date filter"""
        response = self.session.get(
            f"{BASE_URL}/api/finance/expenses/{self.property_id}?from_date=2026-01-01&to_date=2026-01-31"
        )
        assert response.status_code == 200
        print("Expenses date filter works")
    
    def test_expenses_with_status_filter(self):
        """Test expenses with status filter"""
        response = self.session.get(f"{BASE_URL}/api/finance/expenses/{self.property_id}?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        for exp in data:
            assert exp["status"] == "pending"
        print("Expenses status filter works")
    
    def test_expenses_pay_workflow(self):
        """Test paying an expense"""
        exp_id = self.test_expenses_create()
        
        response = self.session.put(f"{BASE_URL}/api/finance/expenses/{exp_id}", json={"status": "paid"})
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "paid"
        print(f"Expense {exp_id} paid")
    
    def test_expenses_delete(self):
        """Test deleting an expense"""
        exp_id = self.test_expenses_create()
        
        response = self.session.delete(f"{BASE_URL}/api/finance/expenses/{exp_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        print(f"Deleted expense: {exp_id}")
    
    # ==================== 8. RECURRING EXPENSES ====================
    
    def test_recurring_expenses_list(self):
        """Test listing recurring expenses"""
        response = self.session.get(f"{BASE_URL}/api/finance/recurring-expenses/{self.property_id}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("Recurring expenses list works")
    
    def test_recurring_expenses_create(self):
        """Test creating a recurring expense"""
        rec_data = {
            "property_id": self.property_id,
            "name": "TEST_Monthly Insurance",
            "amount": 500.00,
            "frequency": "monthly",
            "category": "insurance",
            "next_run": "2026-02-01",
            "notes": "Test recurring expense"
        }
        
        response = self.session.post(f"{BASE_URL}/api/finance/recurring-expenses", json=rec_data)
        assert response.status_code == 200, f"Create recurring expense failed: {response.text}"
        
        data = response.json()
        assert data["status"] == "active"
        assert data["mode"] == "play"
        assert data["frequency"] == "monthly"
        assert "id" in data
        print(f"Created recurring expense: {data['id']}")
        
        return data["id"]
    
    def test_recurring_expenses_pause_play_toggle(self):
        """Test pausing and playing a recurring expense"""
        rec_id = self.test_recurring_expenses_create()
        
        # Pause
        response = self.session.put(f"{BASE_URL}/api/finance/recurring-expenses/{rec_id}", json={"mode": "pause"})
        assert response.status_code == 200
        assert response.json()["mode"] == "pause"
        print(f"Recurring expense {rec_id} paused")
        
        # Play
        response = self.session.put(f"{BASE_URL}/api/finance/recurring-expenses/{rec_id}", json={"mode": "play"})
        assert response.status_code == 200
        assert response.json()["mode"] == "play"
        print(f"Recurring expense {rec_id} resumed")
    
    def test_recurring_expenses_delete(self):
        """Test deleting a recurring expense"""
        rec_id = self.test_recurring_expenses_create()
        
        response = self.session.delete(f"{BASE_URL}/api/finance/recurring-expenses/{rec_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
        print(f"Deleted recurring expense: {rec_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
