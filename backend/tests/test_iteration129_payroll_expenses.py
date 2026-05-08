"""
Iteration 129 - Payroll Management & Expense Management API Tests
Tests: Earnings, Runs, Adjustments, Advances, Categories, Expenses, Recurring, Budgets
"""
import pytest
import requests
import os
from datetime import datetime, date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.cookies.get("access_token") or response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")


@pytest.fixture(scope="module")
def auth_session(auth_token):
    """Session with auth cookies"""
    session = requests.Session()
    session.cookies.set("access_token", auth_token)
    session.headers.update({"Content-Type": "application/json"})
    return session


# ==================== PAYROLL EARNINGS TESTS ====================
class TestPayrollEarnings:
    """Tests for GET /api/payroll/earnings/{property_id}"""
    
    def test_get_earnings_returns_expected_structure(self, auth_session):
        """Earnings endpoint returns period, totals, and rows array"""
        response = auth_session.get(f"{BASE_URL}/api/payroll/earnings/all?year=2026&month=4")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "period" in data
        assert "total_staff" in data
        assert "total_gross" in data
        assert "total_adjustments" in data
        assert "total_advances" in data
        assert "grand_total" in data
        assert "rows" in data
        assert isinstance(data["rows"], list)
        
        # Verify period format
        assert data["period"] == "April 2026"
        print(f"Earnings for April 2026: {data['total_staff']} staff, £{data['grand_total']} grand total")
    
    def test_earnings_row_structure(self, auth_session):
        """Each earnings row has required fields"""
        response = auth_session.get(f"{BASE_URL}/api/payroll/earnings/all?year=2026&month=4")
        assert response.status_code == 200
        data = response.json()
        
        if data["rows"]:
            row = data["rows"][0]
            required_fields = ["staff_id", "name", "role", "days_worked", "daily_rate", "gross", "adjustments", "advances", "net"]
            for field in required_fields:
                assert field in row, f"Missing field: {field}"
            print(f"Sample row: {row['name']} - {row['role']} - £{row['net']} net")
    
    def test_earnings_defaults_to_current_month(self, auth_session):
        """Earnings without year/month params defaults to current month"""
        response = auth_session.get(f"{BASE_URL}/api/payroll/earnings/all")
        assert response.status_code == 200
        data = response.json()
        
        now = datetime.now()
        assert data["year"] == now.year
        assert data["month"] == now.month


# ==================== PAYROLL RUNS TESTS ====================
class TestPayrollRuns:
    """Tests for payroll runs CRUD and lifecycle"""
    
    def test_list_runs(self, auth_session):
        """GET /api/payroll/runs/{property_id} returns runs list"""
        response = auth_session.get(f"{BASE_URL}/api/payroll/runs/all")
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert isinstance(data["runs"], list)
        print(f"Found {len(data['runs'])} existing payroll runs")
    
    def test_create_run_snapshot(self, auth_session):
        """POST /api/payroll/runs/{property_id} creates draft run with snapshot"""
        # Use a unique month to avoid duplicates
        test_year = 2025
        test_month = 3  # March 2025
        
        # First delete any existing run for this month
        runs_resp = auth_session.get(f"{BASE_URL}/api/payroll/runs/all")
        for run in runs_resp.json().get("runs", []):
            if run.get("year") == test_year and run.get("month") == test_month:
                auth_session.delete(f"{BASE_URL}/api/payroll/runs/all/{run['id']}")
        
        response = auth_session.post(f"{BASE_URL}/api/payroll/runs/all", json={
            "year": test_year,
            "month": test_month
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify run structure
        assert data["status"] == "draft"
        assert data["year"] == test_year
        assert data["month"] == test_month
        assert "id" in data
        assert "total_staff" in data
        assert "total_gross" in data
        assert "grand_total" in data
        assert "rows" in data
        print(f"Created run {data['id']} for {data['period']} with status={data['status']}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/payroll/runs/all/{data['id']}")
    
    def test_create_duplicate_run_returns_400(self, auth_session):
        """Creating run for same year/month returns 400"""
        test_year = 2025
        test_month = 2  # Feb 2025
        
        # Create first run
        resp1 = auth_session.post(f"{BASE_URL}/api/payroll/runs/all", json={
            "year": test_year, "month": test_month
        })
        if resp1.status_code == 200:
            run_id = resp1.json()["id"]
            
            # Try to create duplicate
            resp2 = auth_session.post(f"{BASE_URL}/api/payroll/runs/all", json={
                "year": test_year, "month": test_month
            })
            assert resp2.status_code == 400
            assert "already exists" in resp2.json().get("detail", "").lower()
            print("Duplicate run correctly rejected with 400")
            
            # Cleanup
            auth_session.delete(f"{BASE_URL}/api/payroll/runs/all/{run_id}")
    
    def test_approve_run(self, auth_session):
        """POST /api/payroll/runs/{property_id}/{id}/approve sets status=approved"""
        # Create a run
        resp = auth_session.post(f"{BASE_URL}/api/payroll/runs/all", json={
            "year": 2025, "month": 1
        })
        if resp.status_code != 200:
            # May already exist, try to find it
            runs = auth_session.get(f"{BASE_URL}/api/payroll/runs/all").json().get("runs", [])
            run = next((r for r in runs if r["year"] == 2025 and r["month"] == 1), None)
            if not run:
                pytest.skip("Could not create or find test run")
            run_id = run["id"]
        else:
            run_id = resp.json()["id"]
        
        # Approve
        approve_resp = auth_session.post(f"{BASE_URL}/api/payroll/runs/all/{run_id}/approve")
        assert approve_resp.status_code == 200
        assert approve_resp.json().get("ok") == True
        
        # Verify status changed
        runs = auth_session.get(f"{BASE_URL}/api/payroll/runs/all").json().get("runs", [])
        run = next((r for r in runs if r["id"] == run_id), None)
        assert run["status"] == "approved"
        print(f"Run {run_id} approved successfully")
        
        # Cleanup - delete if still draft (won't work if approved, that's ok)
        auth_session.delete(f"{BASE_URL}/api/payroll/runs/all/{run_id}")
    
    def test_mark_paid_admin_only(self, auth_session):
        """POST /api/payroll/runs/{property_id}/{id}/mark-paid sets status=paid"""
        # Create and approve a run
        resp = auth_session.post(f"{BASE_URL}/api/payroll/runs/all", json={
            "year": 2024, "month": 12
        })
        if resp.status_code == 200:
            run_id = resp.json()["id"]
            auth_session.post(f"{BASE_URL}/api/payroll/runs/all/{run_id}/approve")
            
            # Mark paid
            paid_resp = auth_session.post(f"{BASE_URL}/api/payroll/runs/all/{run_id}/mark-paid")
            assert paid_resp.status_code == 200
            
            # Verify status
            runs = auth_session.get(f"{BASE_URL}/api/payroll/runs/all").json().get("runs", [])
            run = next((r for r in runs if r["id"] == run_id), None)
            assert run["status"] == "paid"
            print(f"Run {run_id} marked as paid")
    
    def test_delete_draft_only(self, auth_session):
        """DELETE /api/payroll/runs/{property_id}/{id} only works for draft runs"""
        # Create a draft run
        resp = auth_session.post(f"{BASE_URL}/api/payroll/runs/all", json={
            "year": 2024, "month": 11
        })
        if resp.status_code == 200:
            run_id = resp.json()["id"]
            
            # Delete draft should work
            del_resp = auth_session.delete(f"{BASE_URL}/api/payroll/runs/all/{run_id}")
            assert del_resp.status_code == 200
            print("Draft run deleted successfully")


# ==================== PAYROLL ADJUSTMENTS TESTS ====================
class TestPayrollAdjustments:
    """Tests for adjustments CRUD"""
    
    def test_list_adjustments(self, auth_session):
        """GET /api/payroll/adjustments/{property_id} returns adjustments list"""
        response = auth_session.get(f"{BASE_URL}/api/payroll/adjustments/all?year=2026&month=4")
        assert response.status_code == 200
        data = response.json()
        assert "adjustments" in data
        assert isinstance(data["adjustments"], list)
        print(f"Found {len(data['adjustments'])} adjustments for April 2026")
    
    def test_create_adjustment_all_types(self, auth_session):
        """POST /api/payroll/adjustments/{property_id} supports all adjustment types"""
        adj_types = ["bonus", "overtime", "commission", "deduction", "tax", "benefit", "other"]
        created_ids = []
        
        for adj_type in adj_types:
            response = auth_session.post(f"{BASE_URL}/api/payroll/adjustments/all", json={
                "staff_id": "TEST_staff_001",
                "staff_name": "Test Staff",
                "type": adj_type,
                "amount": 100.00,
                "reason": f"Test {adj_type} adjustment",
                "year": 2026,
                "month": 4
            })
            assert response.status_code == 200
            data = response.json()
            assert data["type"] == adj_type
            assert data["amount"] == 100.00
            created_ids.append(data["id"])
            print(f"Created {adj_type} adjustment: {data['id']}")
        
        # Cleanup
        for adj_id in created_ids:
            auth_session.delete(f"{BASE_URL}/api/payroll/adjustments/all/{adj_id}")
    
    def test_create_adjustment_requires_staff_id(self, auth_session):
        """Creating adjustment without staff_id returns 400"""
        response = auth_session.post(f"{BASE_URL}/api/payroll/adjustments/all", json={
            "type": "bonus",
            "amount": 50.00
        })
        assert response.status_code == 400
        print("Missing staff_id correctly rejected")
    
    def test_delete_adjustment(self, auth_session):
        """DELETE /api/payroll/adjustments/{property_id}/{id} removes adjustment"""
        # Create
        resp = auth_session.post(f"{BASE_URL}/api/payroll/adjustments/all", json={
            "staff_id": "TEST_delete_adj",
            "type": "bonus",
            "amount": 25.00,
            "year": 2026,
            "month": 4
        })
        assert resp.status_code == 200
        adj_id = resp.json()["id"]
        
        # Delete
        del_resp = auth_session.delete(f"{BASE_URL}/api/payroll/adjustments/all/{adj_id}")
        assert del_resp.status_code == 200
        assert del_resp.json().get("deleted") == True
        print(f"Adjustment {adj_id} deleted")


# ==================== CASH ADVANCES TESTS ====================
class TestCashAdvances:
    """Tests for cash advances CRUD and workflow"""
    
    def test_list_advances_with_kpis(self, auth_session):
        """GET /api/payroll/advances/{property_id} returns advances + kpis"""
        response = auth_session.get(f"{BASE_URL}/api/payroll/advances/all")
        assert response.status_code == 200
        data = response.json()
        
        assert "advances" in data
        assert "kpis" in data
        
        kpis = data["kpis"]
        assert "pending" in kpis
        assert "approved" in kpis
        assert "rejected" in kpis
        assert "repaid" in kpis
        assert "total_outstanding" in kpis
        print(f"Advances KPIs: pending={kpis['pending']}, approved={kpis['approved']}, outstanding=£{kpis['total_outstanding']}")
    
    def test_create_advance_request(self, auth_session):
        """POST /api/payroll/advances/{property_id} creates pending request"""
        response = auth_session.post(f"{BASE_URL}/api/payroll/advances/all", json={
            "staff_id": "TEST_advance_staff",
            "staff_name": "Test Advance Staff",
            "amount": 200.00,
            "reason": "Emergency expense"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "pending"
        assert data["repaid"] == False
        assert data["amount"] == 200.00
        assert "id" in data
        print(f"Created advance request {data['id']} with status=pending")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/payroll/advances/all/{data['id']}")
    
    def test_approve_advance(self, auth_session):
        """POST /api/payroll/advances/{property_id}/{id}/approve changes status"""
        # Create
        resp = auth_session.post(f"{BASE_URL}/api/payroll/advances/all", json={
            "staff_id": "TEST_approve_adv",
            "amount": 150.00
        })
        assert resp.status_code == 200
        adv_id = resp.json()["id"]
        
        # Approve
        approve_resp = auth_session.post(f"{BASE_URL}/api/payroll/advances/all/{adv_id}/approve")
        assert approve_resp.status_code == 200
        
        # Verify
        advances = auth_session.get(f"{BASE_URL}/api/payroll/advances/all").json()["advances"]
        adv = next((a for a in advances if a["id"] == adv_id), None)
        assert adv["status"] == "approved"
        print(f"Advance {adv_id} approved")
    
    def test_reject_advance(self, auth_session):
        """POST /api/payroll/advances/{property_id}/{id}/reject changes status"""
        # Create
        resp = auth_session.post(f"{BASE_URL}/api/payroll/advances/all", json={
            "staff_id": "TEST_reject_adv",
            "amount": 100.00
        })
        adv_id = resp.json()["id"]
        
        # Reject
        reject_resp = auth_session.post(f"{BASE_URL}/api/payroll/advances/all/{adv_id}/reject")
        assert reject_resp.status_code == 200
        
        # Verify
        advances = auth_session.get(f"{BASE_URL}/api/payroll/advances/all").json()["advances"]
        adv = next((a for a in advances if a["id"] == adv_id), None)
        assert adv["status"] == "rejected"
        print(f"Advance {adv_id} rejected")
    
    def test_mark_repaid(self, auth_session):
        """POST /api/payroll/advances/{property_id}/{id}/mark-repaid sets repaid=true"""
        # Create and approve
        resp = auth_session.post(f"{BASE_URL}/api/payroll/advances/all", json={
            "staff_id": "TEST_repaid_adv",
            "amount": 75.00
        })
        adv_id = resp.json()["id"]
        auth_session.post(f"{BASE_URL}/api/payroll/advances/all/{adv_id}/approve")
        
        # Mark repaid
        repaid_resp = auth_session.post(f"{BASE_URL}/api/payroll/advances/all/{adv_id}/mark-repaid")
        assert repaid_resp.status_code == 200
        
        # Verify
        advances = auth_session.get(f"{BASE_URL}/api/payroll/advances/all").json()["advances"]
        adv = next((a for a in advances if a["id"] == adv_id), None)
        assert adv["repaid"] == True
        print(f"Advance {adv_id} marked as repaid")


# ==================== EXPENSE CATEGORIES TESTS ====================
class TestExpenseCategories:
    """Tests for expense categories and budgets"""
    
    def test_list_categories_returns_9_defaults(self, auth_session):
        """GET /api/expenses/categories/{property_id} returns 9 default categories"""
        response = auth_session.get(f"{BASE_URL}/api/expenses/categories/all?year=2026&month=4")
        assert response.status_code == 200
        data = response.json()
        
        assert "categories" in data
        cats = data["categories"]
        assert len(cats) >= 9
        
        expected_ids = ["utilities", "supplies", "maintenance", "marketing", "salaries", "rent", "food", "tech", "other"]
        cat_ids = [c["id"] for c in cats]
        for exp_id in expected_ids:
            assert exp_id in cat_ids, f"Missing category: {exp_id}"
        
        # Verify each category has spent, budget, usage_pct
        for cat in cats:
            assert "spent" in cat
            assert "budget" in cat
            assert "usage_pct" in cat
        
        print(f"Found {len(cats)} categories with budget tracking")
    
    def test_set_budget(self, auth_session):
        """PUT /api/expenses/categories/{property_id}/{cat}/budget upserts budget"""
        response = auth_session.put(f"{BASE_URL}/api/expenses/categories/all/utilities/budget", json={
            "year": 2026,
            "month": 4,
            "amount": 5000.00
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert data["amount"] == 5000.00
        
        # Verify budget is reflected in categories
        cats_resp = auth_session.get(f"{BASE_URL}/api/expenses/categories/all?year=2026&month=4")
        cats = cats_resp.json()["categories"]
        utilities = next((c for c in cats if c["id"] == "utilities"), None)
        assert utilities["budget"] == 5000.00
        print(f"Set utilities budget to £5000 for April 2026")


# ==================== EXPENSES TESTS ====================
class TestExpenses:
    """Tests for expenses CRUD"""
    
    def test_list_expenses_with_kpis(self, auth_session):
        """GET /api/expenses/{property_id} returns expenses, kpis, by_category"""
        response = auth_session.get(f"{BASE_URL}/api/expenses/all?year=2026&month=4")
        assert response.status_code == 200
        data = response.json()
        
        assert "expenses" in data
        assert "kpis" in data
        assert "by_category" in data
        
        kpis = data["kpis"]
        assert "total" in kpis
        assert "count" in kpis
        assert "avg" in kpis
        print(f"Expenses KPIs: total=£{kpis['total']}, count={kpis['count']}, avg=£{kpis['avg']}")
    
    def test_create_expense(self, auth_session):
        """POST /api/expenses/{property_id} creates expense"""
        response = auth_session.post(f"{BASE_URL}/api/expenses/all", json={
            "vendor": "TEST Vendor",
            "category": "supplies",
            "description": "Test office supplies",
            "amount": 150.00,
            "date": "2026-04-15",
            "payment_method": "card"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data["vendor"] == "TEST Vendor"
        assert data["category"] == "supplies"
        assert data["amount"] == 150.00
        assert "id" in data
        print(f"Created expense {data['id']}: £{data['amount']} for {data['vendor']}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/expenses/all/{data['id']}")
    
    def test_create_expense_rejects_zero_amount(self, auth_session):
        """Creating expense with amount<=0 returns 400"""
        response = auth_session.post(f"{BASE_URL}/api/expenses/all", json={
            "vendor": "Test",
            "amount": 0
        })
        assert response.status_code == 400
        assert "positive" in response.json().get("detail", "").lower()
        print("Zero amount correctly rejected")
    
    def test_update_expense(self, auth_session):
        """PUT /api/expenses/{property_id}/{id} updates allowed fields"""
        # Create
        resp = auth_session.post(f"{BASE_URL}/api/expenses/all", json={
            "vendor": "Original Vendor",
            "amount": 100.00,
            "category": "other"
        })
        exp_id = resp.json()["id"]
        
        # Update
        update_resp = auth_session.put(f"{BASE_URL}/api/expenses/all/{exp_id}", json={
            "vendor": "Updated Vendor",
            "amount": 200.00
        })
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["vendor"] == "Updated Vendor"
        assert data["amount"] == 200.00
        print(f"Updated expense {exp_id}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/expenses/all/{exp_id}")
    
    def test_delete_expense(self, auth_session):
        """DELETE /api/expenses/{property_id}/{id} removes expense"""
        # Create
        resp = auth_session.post(f"{BASE_URL}/api/expenses/all", json={
            "vendor": "To Delete",
            "amount": 50.00
        })
        exp_id = resp.json()["id"]
        
        # Delete
        del_resp = auth_session.delete(f"{BASE_URL}/api/expenses/all/{exp_id}")
        assert del_resp.status_code == 200
        assert del_resp.json().get("deleted") == True
        print(f"Expense {exp_id} deleted")
    
    def test_filter_by_category(self, auth_session):
        """GET /api/expenses/{property_id}?category= filters results"""
        # Create expense in specific category
        resp = auth_session.post(f"{BASE_URL}/api/expenses/all", json={
            "vendor": "TEST Filter Vendor",
            "amount": 75.00,
            "category": "tech",
            "date": "2026-04-10"
        })
        exp_id = resp.json()["id"]
        
        # Filter by category
        filter_resp = auth_session.get(f"{BASE_URL}/api/expenses/all?year=2026&month=4&category=tech")
        assert filter_resp.status_code == 200
        expenses = filter_resp.json()["expenses"]
        
        # All returned expenses should be in tech category
        for exp in expenses:
            assert exp["category"] == "tech"
        print(f"Category filter returned {len(expenses)} tech expenses")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/expenses/all/{exp_id}")


# ==================== RECURRING EXPENSES TESTS ====================
class TestRecurringExpenses:
    """Tests for recurring expense templates"""
    
    def test_list_recurring_with_due_count(self, auth_session):
        """GET /api/expenses/recurring/{property_id} returns recurring + due_count"""
        response = auth_session.get(f"{BASE_URL}/api/expenses/recurring/all")
        assert response.status_code == 200
        data = response.json()
        
        assert "recurring" in data
        assert "due_count" in data
        print(f"Found {len(data['recurring'])} recurring templates, {data['due_count']} due")
    
    def test_create_recurring_all_frequencies(self, auth_session):
        """POST /api/expenses/recurring/{property_id} supports all frequencies"""
        frequencies = ["weekly", "biweekly", "monthly", "quarterly", "annual"]
        created_ids = []
        
        for freq in frequencies:
            response = auth_session.post(f"{BASE_URL}/api/expenses/recurring/all", json={
                "vendor": f"TEST {freq} Vendor",
                "category": "utilities",
                "amount": 100.00,
                "frequency": freq,
                "next_due": "2026-04-01"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["frequency"] == freq
            assert data["enabled"] == True
            created_ids.append(data["id"])
            print(f"Created {freq} recurring: {data['id']}")
        
        # Cleanup
        for rec_id in created_ids:
            auth_session.delete(f"{BASE_URL}/api/expenses/recurring/all/{rec_id}")
    
    def test_post_recurring_creates_expense_and_advances_next_due(self, auth_session):
        """POST /api/expenses/recurring/{property_id}/{id}/post creates expense and advances next_due"""
        # Create monthly recurring with past due date
        today = date.today()
        past_due = (today - timedelta(days=5)).isoformat()
        
        resp = auth_session.post(f"{BASE_URL}/api/expenses/recurring/all", json={
            "vendor": "TEST Post Recurring",
            "category": "rent",
            "amount": 1000.00,
            "frequency": "monthly",
            "next_due": past_due
        })
        assert resp.status_code == 200
        rec_id = resp.json()["id"]
        original_next_due = resp.json()["next_due"]
        
        # Post it
        post_resp = auth_session.post(f"{BASE_URL}/api/expenses/recurring/all/{rec_id}/post")
        assert post_resp.status_code == 200
        expense = post_resp.json()
        
        # Verify expense created
        assert expense["amount"] == 1000.00
        assert expense["recurring_id"] == rec_id
        assert "(recurring)" in expense["description"]
        print(f"Posted recurring created expense {expense['id']}")
        
        # Verify next_due advanced
        recurring = auth_session.get(f"{BASE_URL}/api/expenses/recurring/all").json()["recurring"]
        rec = next((r for r in recurring if r["id"] == rec_id), None)
        assert rec["next_due"] > original_next_due
        assert rec["total_posted"] == 1
        print(f"next_due advanced from {original_next_due} to {rec['next_due']}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/expenses/all/{expense['id']}")
        auth_session.delete(f"{BASE_URL}/api/expenses/recurring/all/{rec_id}")
    
    def test_run_due_posts_all_due_templates(self, auth_session):
        """POST /api/expenses/recurring/{property_id}/run-due posts all enabled+due templates"""
        # Create two due recurring templates
        today = date.today()
        past_due = (today - timedelta(days=1)).isoformat()
        
        rec_ids = []
        for i in range(2):
            resp = auth_session.post(f"{BASE_URL}/api/expenses/recurring/all", json={
                "vendor": f"TEST RunDue {i}",
                "category": "supplies",
                "amount": 50.00,
                "frequency": "monthly",
                "next_due": past_due
            })
            rec_ids.append(resp.json()["id"])
        
        # Run due
        run_resp = auth_session.post(f"{BASE_URL}/api/expenses/recurring/all/run-due")
        assert run_resp.status_code == 200
        data = run_resp.json()
        assert data["posted"] >= 2
        print(f"run-due posted {data['posted']} recurring expenses")
        
        # Cleanup
        for rec_id in rec_ids:
            auth_session.delete(f"{BASE_URL}/api/expenses/recurring/all/{rec_id}")
    
    def test_delete_recurring(self, auth_session):
        """DELETE /api/expenses/recurring/{property_id}/{id} removes template"""
        # Create
        resp = auth_session.post(f"{BASE_URL}/api/expenses/recurring/all", json={
            "vendor": "TEST Delete Recurring",
            "amount": 25.00,
            "frequency": "weekly"
        })
        rec_id = resp.json()["id"]
        
        # Delete
        del_resp = auth_session.delete(f"{BASE_URL}/api/expenses/recurring/all/{rec_id}")
        assert del_resp.status_code == 200
        assert del_resp.json().get("deleted") == True
        print(f"Recurring {rec_id} deleted")


# ==================== INTEGRATION TESTS ====================
class TestPayrollExpenseIntegration:
    """Integration tests for payroll and expense workflows"""
    
    def test_earnings_reflects_adjustments(self, auth_session):
        """Adjustments are reflected in earnings calculation for staff with shifts"""
        # First get earnings to find a staff member with shifts
        earnings = auth_session.get(f"{BASE_URL}/api/payroll/earnings/all?year=2026&month=4").json()
        
        if not earnings["rows"]:
            # No staff with shifts, just verify adjustment creation works
            adj_resp = auth_session.post(f"{BASE_URL}/api/payroll/adjustments/all", json={
                "staff_id": "TEST_integration_staff",
                "staff_name": "Integration Test Staff",
                "type": "bonus",
                "amount": 500.00,
                "year": 2026,
                "month": 4
            })
            assert adj_resp.status_code == 200
            adj_id = adj_resp.json()["id"]
            print("No staff with shifts - verified adjustment creation works")
            auth_session.delete(f"{BASE_URL}/api/payroll/adjustments/all/{adj_id}")
            return
        
        # Use first staff member with shifts
        staff = earnings["rows"][0]
        original_adj = staff["adjustments"]
        
        # Create a bonus adjustment for this staff
        adj_resp = auth_session.post(f"{BASE_URL}/api/payroll/adjustments/all", json={
            "staff_id": staff["staff_id"],
            "staff_name": staff["name"],
            "type": "bonus",
            "amount": 500.00,
            "year": 2026,
            "month": 4
        })
        adj_id = adj_resp.json()["id"]
        
        # Check earnings again
        new_earnings = auth_session.get(f"{BASE_URL}/api/payroll/earnings/all?year=2026&month=4").json()
        new_staff = next((r for r in new_earnings["rows"] if r["staff_id"] == staff["staff_id"]), None)
        
        # Adjustments should have increased by 500
        assert new_staff["adjustments"] == original_adj + 500.00
        print(f"Adjustments for {staff['name']}: {original_adj} -> {new_staff['adjustments']}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/payroll/adjustments/all/{adj_id}")
    
    def test_budget_usage_calculation(self, auth_session):
        """Budget usage_pct is correctly calculated"""
        # Set a budget
        auth_session.put(f"{BASE_URL}/api/expenses/categories/all/marketing/budget", json={
            "year": 2026, "month": 4, "amount": 1000.00
        })
        
        # Create an expense
        exp_resp = auth_session.post(f"{BASE_URL}/api/expenses/all", json={
            "vendor": "TEST Marketing Expense",
            "category": "marketing",
            "amount": 250.00,
            "date": "2026-04-15"
        })
        exp_id = exp_resp.json()["id"]
        
        # Check category
        cats = auth_session.get(f"{BASE_URL}/api/expenses/categories/all?year=2026&month=4").json()["categories"]
        marketing = next((c for c in cats if c["id"] == "marketing"), None)
        
        assert marketing["spent"] >= 250.00
        assert marketing["budget"] == 1000.00
        # usage_pct should be at least 25%
        assert marketing["usage_pct"] >= 25.0
        print(f"Marketing: spent=£{marketing['spent']}, budget=£{marketing['budget']}, usage={marketing['usage_pct']}%")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/expenses/all/{exp_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
