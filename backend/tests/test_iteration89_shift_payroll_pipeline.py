"""
Iteration 89 - Shift-to-Payroll Pipeline Tests
Tests:
1. Shift creation auto-calculates hours_worked from start_time/end_time
2. Shift creation auto-calculates earned_amount (daily rate flat, hourly rate = hours × rate)
3. POST /api/shifts/sync-to-salaries creates earned salary entries from completed/approved shifts
4. Sync is idempotent (doesn't duplicate if same shift_id already synced)
5. Finance Dashboard includes payroll from earned salaries in total_costs
6. Finance Dashboard shows correct Net = Gross Revenue - Expenses - Payroll - Commission
7. Hourly calculation: 6h shift at £11.44/hr = £68.64
8. Daily calculation: 8h shift at £80/day = £80
9. Earned salaries entries created by sync have shift_id, hours, pay_type, source='shift'
10. Regression tests for existing Finance, Operations, Shifts features
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestShiftPayrollPipeline:
    """Test shift-to-payroll pipeline features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        # Store cookies for authenticated requests
        self.property_id = "all"
        self.test_staff_id = None
        self.test_shift_ids = []
        yield
        
        # Cleanup test data
        self._cleanup()
    
    def _cleanup(self):
        """Clean up test data"""
        # Delete test shifts
        for shift_id in self.test_shift_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}")
            except:
                pass
        
        # Delete test staff
        if self.test_staff_id:
            try:
                self.session.delete(f"{BASE_URL}/api/shifts/staff/{self.test_staff_id}")
            except:
                pass
    
    # ==================== SHIFT HOURS CALCULATION TESTS ====================
    
    def test_shift_auto_calculates_hours_worked(self):
        """Test that shift creation auto-calculates hours_worked from start_time/end_time"""
        # Create test staff first
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_HoursCalc_Staff",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80,
            "currency": "GBP"
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create shift with 8-hour duration (09:00 to 17:00)
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-15",
            "week_start": "2026-01-12",
            "start_time": "09:00",
            "end_time": "17:00",
            "pay_type": "daily",
            "pay_rate": 80
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        # Verify hours_worked is auto-calculated
        assert "hours_worked" in shift, "hours_worked field missing"
        assert shift["hours_worked"] == 8.0, f"Expected 8.0 hours, got {shift['hours_worked']}"
        print(f"✓ Shift auto-calculated hours_worked: {shift['hours_worked']}h")
    
    def test_shift_6_hour_calculation(self):
        """Test 6-hour shift calculation (10:00 to 16:00)"""
        # Create staff
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_6Hour_Staff",
            "role": "housekeeper",
            "pay_type": "hourly",
            "pay_rate": 11.44,
            "currency": "GBP"
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create 6-hour shift
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-15",
            "week_start": "2026-01-12",
            "start_time": "10:00",
            "end_time": "16:00",
            "pay_type": "hourly",
            "pay_rate": 11.44
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        assert shift["hours_worked"] == 6.0, f"Expected 6.0 hours, got {shift['hours_worked']}"
        print(f"✓ 6-hour shift calculated correctly: {shift['hours_worked']}h")
    
    # ==================== EARNED AMOUNT CALCULATION TESTS ====================
    
    def test_daily_rate_earned_amount_flat(self):
        """Test daily rate: 8h shift at £80/day = £80 (flat rate)"""
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_DailyRate_Staff",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80,
            "currency": "GBP"
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create 8-hour shift with daily rate
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-15",
            "week_start": "2026-01-12",
            "start_time": "09:00",
            "end_time": "17:00",
            "pay_type": "daily",
            "pay_rate": 80
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        # Daily rate should be flat regardless of hours
        assert "earned_amount" in shift, "earned_amount field missing"
        assert shift["earned_amount"] == 80.0, f"Expected £80.00 (daily flat), got £{shift['earned_amount']}"
        print(f"✓ Daily rate earned_amount is flat: £{shift['earned_amount']}")
    
    def test_hourly_rate_earned_amount_calculated(self):
        """Test hourly rate: 6h shift at £11.44/hr = £68.64"""
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_HourlyRate_Staff",
            "role": "housekeeper",
            "pay_type": "hourly",
            "pay_rate": 11.44,
            "currency": "GBP"
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create 6-hour shift with hourly rate
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-15",
            "week_start": "2026-01-12",
            "start_time": "10:00",
            "end_time": "16:00",
            "pay_type": "hourly",
            "pay_rate": 11.44
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        # Hourly rate: 6h × £11.44 = £68.64
        expected_earned = round(6 * 11.44, 2)
        assert shift["earned_amount"] == expected_earned, f"Expected £{expected_earned}, got £{shift['earned_amount']}"
        print(f"✓ Hourly rate earned_amount calculated: 6h × £11.44 = £{shift['earned_amount']}")
    
    # ==================== SYNC TO SALARIES TESTS ====================
    
    def test_sync_to_salaries_creates_entries(self):
        """Test POST /api/shifts/sync-to-salaries creates earned salary entries"""
        # Create staff
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_Sync_Staff",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80,
            "currency": "GBP"
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create shift and mark as completed
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-15",
            "week_start": "2026-01-12",
            "start_time": "09:00",
            "end_time": "17:00",
            "status": "completed",
            "pay_type": "daily",
            "pay_rate": 80
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        # Sync to salaries
        sync_response = self.session.post(f"{BASE_URL}/api/shifts/sync-to-salaries", json={
            "week_start": "2026-01-12",
            "property_id": self.property_id
        })
        assert sync_response.status_code == 200
        sync_result = sync_response.json()
        
        assert "synced" in sync_result, "synced count missing"
        assert sync_result["synced"] >= 1, f"Expected at least 1 synced, got {sync_result['synced']}"
        print(f"✓ Sync created {sync_result['synced']} salary entries from {sync_result['total_shifts_processed']} shifts")
    
    def test_sync_is_idempotent(self):
        """Test sync doesn't duplicate if same shift_id already synced"""
        # Create staff
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_Idempotent_Staff",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80,
            "currency": "GBP"
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create completed shift
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-16",
            "week_start": "2026-01-12",
            "start_time": "09:00",
            "end_time": "17:00",
            "status": "approved",
            "pay_type": "daily",
            "pay_rate": 80
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        # First sync
        sync1 = self.session.post(f"{BASE_URL}/api/shifts/sync-to-salaries", json={
            "week_start": "2026-01-12",
            "property_id": self.property_id
        })
        assert sync1.status_code == 200
        first_synced = sync1.json()["synced"]
        
        # Second sync - should not create duplicates
        sync2 = self.session.post(f"{BASE_URL}/api/shifts/sync-to-salaries", json={
            "week_start": "2026-01-12",
            "property_id": self.property_id
        })
        assert sync2.status_code == 200
        second_synced = sync2.json()["synced"]
        
        # Second sync should create 0 new entries (idempotent)
        assert second_synced == 0, f"Expected 0 duplicates, but synced {second_synced} more"
        print(f"✓ Sync is idempotent: First sync={first_synced}, Second sync={second_synced}")
    
    def test_synced_salary_has_required_fields(self):
        """Test earned salaries entries have shift_id, hours, pay_type, source='shift'"""
        # Create staff
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_SalaryFields_Staff",
            "role": "housekeeper",
            "pay_type": "hourly",
            "pay_rate": 11.44,
            "currency": "GBP"
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create completed shift
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-17",
            "week_start": "2026-01-12",
            "start_time": "10:00",
            "end_time": "16:00",
            "status": "completed",
            "pay_type": "hourly",
            "pay_rate": 11.44
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        # Sync to salaries
        self.session.post(f"{BASE_URL}/api/shifts/sync-to-salaries", json={
            "week_start": "2026-01-12",
            "property_id": self.property_id
        })
        
        # Get earned salaries and find the one with our shift_id
        salaries_response = self.session.get(f"{BASE_URL}/api/finance/earned-salaries/{self.property_id}?from_date=2026-01-17&to_date=2026-01-17")
        assert salaries_response.status_code == 200
        salaries_data = salaries_response.json()
        
        # Find our synced salary entry
        our_salary = None
        for entry in salaries_data.get("entries", []):
            if entry.get("shift_id") == shift["id"]:
                our_salary = entry
                break
        
        assert our_salary is not None, "Synced salary entry not found"
        assert our_salary.get("shift_id") == shift["id"], "shift_id missing or incorrect"
        assert our_salary.get("hours") == 6.0, f"hours should be 6.0, got {our_salary.get('hours')}"
        assert our_salary.get("pay_type") == "hourly", f"pay_type should be 'hourly', got {our_salary.get('pay_type')}"
        assert our_salary.get("source") == "shift", f"source should be 'shift', got {our_salary.get('source')}"
        print(f"✓ Synced salary has required fields: shift_id={our_salary['shift_id']}, hours={our_salary['hours']}, pay_type={our_salary['pay_type']}, source={our_salary['source']}")
    
    # ==================== FINANCE DASHBOARD TESTS ====================
    
    def test_finance_dashboard_includes_payroll(self):
        """Test Finance Dashboard includes payroll from earned salaries in total_costs"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "overview" in data, "overview missing"
        overview = data["overview"]
        
        # Check payroll field exists
        assert "payroll" in overview, "payroll field missing from overview"
        assert "total_costs" in overview, "total_costs field missing from overview"
        
        print(f"✓ Finance Dashboard includes payroll: £{overview['payroll']}")
        print(f"  Total costs: £{overview['total_costs']}")
    
    def test_finance_dashboard_net_calculation(self):
        """Test Finance Dashboard shows correct Net = Gross Revenue - Expenses - Payroll - Commission"""
        response = self.session.get(f"{BASE_URL}/api/finance/dashboard/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        
        overview = data["overview"]
        gross = overview.get("gross", 0)
        expenses = overview.get("expenses", 0)
        payroll = overview.get("payroll", 0)
        commission = overview.get("commission", 0)
        total_costs = overview.get("total_costs", 0)
        net = overview.get("net", 0)
        
        # Verify total_costs = expenses + payroll + commission
        expected_total_costs = round(expenses + payroll + commission, 2)
        assert abs(total_costs - expected_total_costs) < 0.01, f"total_costs mismatch: expected {expected_total_costs}, got {total_costs}"
        
        # Verify net = gross - total_costs
        expected_net = round(gross - total_costs, 2)
        assert abs(net - expected_net) < 0.01, f"net mismatch: expected {expected_net}, got {net}"
        
        print(f"✓ Finance Dashboard calculation correct:")
        print(f"  Gross: £{gross}")
        print(f"  Expenses: £{expenses}")
        print(f"  Payroll: £{payroll}")
        print(f"  Commission: £{commission}")
        print(f"  Total Costs: £{total_costs} (expected: £{expected_total_costs})")
        print(f"  Net: £{net} (expected: £{expected_net})")
    
    # ==================== REGRESSION TESTS ====================
    
    def test_shifts_staff_crud(self):
        """Regression: Shifts staff CRUD operations"""
        # Create
        create_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_CRUD_Staff",
            "role": "maintenance",
            "pay_type": "daily",
            "pay_rate": 100,
            "currency": "GBP"
        })
        assert create_response.status_code == 200
        staff = create_response.json()
        self.test_staff_id = staff["id"]
        assert staff["name"] == "TEST_CRUD_Staff"
        
        # Read
        list_response = self.session.get(f"{BASE_URL}/api/shifts/staff/{self.property_id}")
        assert list_response.status_code == 200
        
        # Update
        update_response = self.session.put(f"{BASE_URL}/api/shifts/staff/{staff['id']}", json={
            "pay_rate": 120
        })
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["pay_rate"] == 120
        
        # Delete
        delete_response = self.session.delete(f"{BASE_URL}/api/shifts/staff/{staff['id']}")
        assert delete_response.status_code == 200
        self.test_staff_id = None
        
        print("✓ Shifts staff CRUD operations working")
    
    def test_shifts_entries_crud(self):
        """Regression: Shifts entries CRUD operations"""
        # Create staff first
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_EntryCRUD_Staff",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create shift
        create_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-18",
            "week_start": "2026-01-12",
            "start_time": "09:00",
            "end_time": "17:00",
            "pay_type": "daily",
            "pay_rate": 80
        })
        assert create_response.status_code == 200
        shift = create_response.json()
        self.test_shift_ids.append(shift["id"])
        
        # Read
        list_response = self.session.get(f"{BASE_URL}/api/shifts/entries/{self.property_id}?week_start=2026-01-12")
        assert list_response.status_code == 200
        
        # Update
        update_response = self.session.put(f"{BASE_URL}/api/shifts/entries/{shift['id']}", json={
            "status": "completed"
        })
        assert update_response.status_code == 200
        
        # Delete
        delete_response = self.session.delete(f"{BASE_URL}/api/shifts/entries/{shift['id']}")
        assert delete_response.status_code == 200
        self.test_shift_ids.remove(shift["id"])
        
        print("✓ Shifts entries CRUD operations working")
    
    def test_shifts_bulk_actions(self):
        """Regression: Shifts bulk actions"""
        # Create staff
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_Bulk_Staff",
            "role": "housekeeper",
            "pay_type": "daily",
            "pay_rate": 80
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # Create shift
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-19",
            "week_start": "2026-01-19",
            "start_time": "09:00",
            "end_time": "17:00",
            "status": "planned",
            "pay_type": "daily",
            "pay_rate": 80
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        # Test publish-all
        publish_response = self.session.post(f"{BASE_URL}/api/shifts/bulk/publish-all", json={
            "week_start": "2026-01-19",
            "property_id": self.property_id
        })
        assert publish_response.status_code == 200
        
        # Test mark-completed
        completed_response = self.session.post(f"{BASE_URL}/api/shifts/bulk/mark-completed", json={
            "week_start": "2026-01-19",
            "property_id": self.property_id
        })
        assert completed_response.status_code == 200
        
        # Test approve-completed
        approve_response = self.session.post(f"{BASE_URL}/api/shifts/bulk/approve-completed", json={
            "week_start": "2026-01-19",
            "property_id": self.property_id
        })
        assert approve_response.status_code == 200
        
        # Clean up
        self.session.post(f"{BASE_URL}/api/shifts/bulk/clear-week", json={
            "week_start": "2026-01-19",
            "property_id": self.property_id
        })
        self.test_shift_ids = []
        
        print("✓ Shifts bulk actions working")
    
    def test_payroll_summary(self):
        """Regression: Payroll summary endpoint"""
        response = self.session.get(f"{BASE_URL}/api/shifts/payroll/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Payroll summary should return a list"
        print(f"✓ Payroll summary working, {len(data)} staff entries")
    
    def test_finance_earned_salaries(self):
        """Regression: Finance earned salaries endpoint"""
        response = self.session.get(f"{BASE_URL}/api/finance/earned-salaries/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data, "entries field missing"
        assert "stats" in data, "stats field missing"
        print(f"✓ Finance earned salaries working, {len(data['entries'])} entries")
    
    def test_finance_expenses(self):
        """Regression: Finance expenses endpoint"""
        response = self.session.get(f"{BASE_URL}/api/finance/expenses/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Expenses should return a list"
        print(f"✓ Finance expenses working, {len(data)} entries")
    
    def test_finance_payroll_runs(self):
        """Regression: Finance payroll runs endpoint"""
        response = self.session.get(f"{BASE_URL}/api/finance/payroll-runs/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data, "runs field missing"
        assert "config" in data, "config field missing"
        print(f"✓ Finance payroll runs working, {len(data['runs'])} runs")
    
    def test_operations_reception_report(self):
        """Regression: Operations reception report endpoint"""
        response = self.session.get(f"{BASE_URL}/api/operations/reception/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data, "stats field missing"
        print("✓ Operations reception report working")
    
    def test_operations_routine_templates(self):
        """Regression: Operations routine templates endpoint"""
        response = self.session.get(f"{BASE_URL}/api/operations/routine-templates/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Routine templates should return a list"
        print(f"✓ Operations routine templates working, {len(data)} templates")


class TestShiftPayrollCalculationEdgeCases:
    """Test edge cases for shift-to-payroll calculations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        
        self.property_id = "all"
        self.test_staff_id = None
        self.test_shift_ids = []
        yield
        
        # Cleanup
        for shift_id in self.test_shift_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/shifts/entries/{shift_id}")
            except:
                pass
        if self.test_staff_id:
            try:
                self.session.delete(f"{BASE_URL}/api/shifts/staff/{self.test_staff_id}")
            except:
                pass
    
    def test_zero_pay_rate_shift(self):
        """Test shift with zero pay rate"""
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_ZeroRate_Staff",
            "role": "volunteer",
            "pay_type": "daily",
            "pay_rate": 0
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-20",
            "week_start": "2026-01-19",
            "start_time": "09:00",
            "end_time": "17:00",
            "pay_type": "daily",
            "pay_rate": 0
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        assert shift["earned_amount"] == 0, f"Expected £0, got £{shift['earned_amount']}"
        print(f"✓ Zero pay rate handled correctly: £{shift['earned_amount']}")
    
    def test_short_shift_hourly(self):
        """Test short 2-hour shift with hourly rate"""
        staff_response = self.session.post(f"{BASE_URL}/api/shifts/staff", json={
            "property_id": self.property_id,
            "name": "TEST_ShortShift_Staff",
            "role": "housekeeper",
            "pay_type": "hourly",
            "pay_rate": 15.00
        })
        assert staff_response.status_code == 200
        staff = staff_response.json()
        self.test_staff_id = staff["id"]
        
        # 2-hour shift
        shift_response = self.session.post(f"{BASE_URL}/api/shifts/entries", json={
            "property_id": self.property_id,
            "staff_id": staff["id"],
            "staff_name": staff["name"],
            "role": staff["role"],
            "date": "2026-01-20",
            "week_start": "2026-01-19",
            "start_time": "14:00",
            "end_time": "16:00",
            "pay_type": "hourly",
            "pay_rate": 15.00
        })
        assert shift_response.status_code == 200
        shift = shift_response.json()
        self.test_shift_ids.append(shift["id"])
        
        assert shift["hours_worked"] == 2.0, f"Expected 2.0 hours, got {shift['hours_worked']}"
        assert shift["earned_amount"] == 30.0, f"Expected £30.00, got £{shift['earned_amount']}"
        print(f"✓ Short 2-hour shift: {shift['hours_worked']}h × £15 = £{shift['earned_amount']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
