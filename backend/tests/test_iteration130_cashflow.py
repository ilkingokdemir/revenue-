"""
Iteration 130 - Cash Flow Forecast API Tests
Tests the /api/finance/cash-flow-forecast/{property_id} endpoint that aggregates:
- Confirmed future bookings (inflows on check_in)
- Recurring expenses (outflows on next_due)
- Recurring invoices (inflows on next_due)
- Estimated payroll (avg of last 3 approved/paid runs, posted on last day of month)
- Manually dated future expenses
"""
import pytest
import requests
import os
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")

@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestCashFlowForecastBasic:
    """Basic Cash Flow Forecast endpoint tests"""
    
    def test_forecast_30_days_returns_correct_structure(self, auth_headers):
        """Test 30-day forecast returns all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required top-level fields
        required_fields = [
            "period_days", "start", "end", "opening_balance", "total_inflows",
            "total_outflows", "net", "ending_balance", "lowest_balance",
            "lowest_date", "at_risk", "payroll_estimate_monthly", "counts", "days"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify counts structure
        assert "bookings" in data["counts"]
        assert "recurring_invoices" in data["counts"]
        assert "recurring_expenses" in data["counts"]
        assert "future_expenses" in data["counts"]
        
        # Verify period_days matches
        assert data["period_days"] == 30
        
    def test_days_array_length_equals_period_days(self, auth_headers):
        """Test that days array length equals period_days"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["days"]) == data["period_days"]
        assert len(data["days"]) == 30
        
    def test_day_structure_has_required_fields(self, auth_headers):
        """Test each day has required fields: date, inflows, outflows, net, running_balance, items"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for day in data["days"]:
            assert "date" in day
            assert "inflows" in day
            assert "outflows" in day
            assert "net" in day
            assert "running_balance" in day
            assert "items" in day
            assert "in" in day["items"]
            assert "out" in day["items"]


class TestCashFlowForecastCalculations:
    """Test cash flow calculations"""
    
    def test_ending_balance_calculation(self, auth_headers):
        """Test ending_balance == opening_balance + total_inflows - total_outflows"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        expected_ending = data["opening_balance"] + data["total_inflows"] - data["total_outflows"]
        # Allow for small rounding differences
        assert abs(data["ending_balance"] - expected_ending) < 0.01
        
    def test_running_balance_accumulates_correctly(self, auth_headers):
        """Test running_balance monotonically accumulates day by day"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        prev_balance = data["opening_balance"]
        for day in data["days"]:
            expected_balance = prev_balance + day["inflows"] - day["outflows"]
            # Allow for small rounding differences
            assert abs(day["running_balance"] - expected_balance) < 0.01, \
                f"Day {day['date']}: expected {expected_balance}, got {day['running_balance']}"
            prev_balance = day["running_balance"]
            
    def test_net_equals_inflows_minus_outflows(self, auth_headers):
        """Test each day's net equals inflows - outflows"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for day in data["days"]:
            expected_net = day["inflows"] - day["outflows"]
            assert abs(day["net"] - expected_net) < 0.01


class TestCashFlowForecastPeriods:
    """Test different period selections"""
    
    def test_60_days_period(self, auth_headers):
        """Test 60-day forecast returns correct window size"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=60&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_days"] == 60
        assert len(data["days"]) == 60
        
    def test_90_days_period(self, auth_headers):
        """Test 90-day forecast returns correct window size"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=90&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_days"] == 90
        assert len(data["days"]) == 90
        
    def test_invalid_days_defaults_to_30(self, auth_headers):
        """Test invalid days value (e.g., 15) defaults to 30"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=15&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_days"] == 30
        assert len(data["days"]) == 30
        
    def test_invalid_days_45_defaults_to_30(self, auth_headers):
        """Test another invalid days value (45) defaults to 30"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=45&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_days"] == 30


class TestCashFlowForecastOpeningBalance:
    """Test opening balance variations"""
    
    def test_opening_balance_zero_works(self, auth_headers):
        """Test opening_balance=0 still works"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=0",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["opening_balance"] == 0.0
        # Ending balance should equal net (since opening is 0)
        assert abs(data["ending_balance"] - data["net"]) < 0.01
        
    def test_negative_opening_balance_triggers_at_risk(self, auth_headers):
        """Test at_risk=true when lowest_balance<0"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=-100",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["opening_balance"] == -100.0
        assert data["lowest_balance"] < 0
        assert data["at_risk"] == True
        
    def test_high_opening_balance_not_at_risk(self, auth_headers):
        """Test at_risk=false when lowest_balance>=0"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=100000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["lowest_balance"] >= 0
        assert data["at_risk"] == False


class TestCashFlowForecastAuth:
    """Test authentication requirements"""
    
    def test_requires_auth_401_without_token(self):
        """Test endpoint requires admin/manager auth (401 without token)"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000"
        )
        assert response.status_code == 401
        
    def test_requires_auth_401_with_invalid_token(self):
        """Test endpoint returns 401 with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401


class TestCashFlowForecastBookings:
    """Test booking inflows"""
    
    def test_bookings_count_in_response(self, auth_headers):
        """Test bookings count is returned in counts"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "bookings" in data["counts"]
        assert isinstance(data["counts"]["bookings"], int)
        
    def test_bookings_contribute_to_inflows(self, auth_headers):
        """Test bookings with check_in in window count as inflows"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # If there are bookings, total_inflows should be > 0
        if data["counts"]["bookings"] > 0:
            assert data["total_inflows"] > 0
            
    def test_booking_items_in_day_structure(self, auth_headers):
        """Test booking items appear in day items.in array"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find a day with inflows
        for day in data["days"]:
            if day["inflows"] > 0 and len(day["items"]["in"]) > 0:
                item = day["items"]["in"][0]
                assert "kind" in item
                assert "label" in item
                assert "amount" in item
                break


class TestCashFlowForecastPropertyFilter:
    """Test property filtering"""
    
    def test_all_property_filter(self, auth_headers):
        """Test 'all' property_id returns aggregated data"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_days"] == 30
        
    def test_specific_property_filter(self, auth_headers):
        """Test specific property_id filters data"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/aldgate-flats?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["period_days"] == 30


class TestCashFlowForecastDateRange:
    """Test date range in response"""
    
    def test_start_date_is_today(self, auth_headers):
        """Test start date is today"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        today = date.today().isoformat()
        assert data["start"] == today
        
    def test_end_date_is_correct(self, auth_headers):
        """Test end date is start + (days-1)"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        today = date.today()
        expected_end = (today + timedelta(days=29)).isoformat()
        assert data["end"] == expected_end
        
    def test_first_day_date_matches_start(self, auth_headers):
        """Test first day in array has date matching start"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["days"][0]["date"] == data["start"]
        
    def test_last_day_date_matches_end(self, auth_headers):
        """Test last day in array has date matching end"""
        response = requests.get(
            f"{BASE_URL}/api/finance/cash-flow-forecast/all?days=30&opening_balance=10000",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["days"][-1]["date"] == data["end"]
