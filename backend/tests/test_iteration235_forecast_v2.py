"""
Iteration 235 - Batch 23: Forecast V2 Tests
Tests for 24-month horizon, demand calendar, and pickup curve endpoints.
"""
import pytest
import requests
import os
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "default"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Auth failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestForecastV2Horizon:
    """Tests for GET /api/forecast-v2/horizon/{property_id}"""

    def test_horizon_default_24_months(self, auth_headers):
        """Test horizon endpoint returns 24 months by default"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/horizon/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "forecast" in data, "Missing 'forecast' array"
        assert "historical" in data, "Missing 'historical' dict"
        assert "yoy_growth_pct" in data, "Missing 'yoy_growth_pct'"
        assert "avg_adr" in data, "Missing 'avg_adr'"
        assert "avg_los" in data, "Missing 'avg_los'"
        
        # Verify forecast has 24 items
        assert len(data["forecast"]) == 24, f"Expected 24 forecast items, got {len(data['forecast'])}"
        
        # Verify forecast item structure
        first_item = data["forecast"][0]
        assert "period" in first_item, "Missing 'period' in forecast item"
        assert "label" in first_item, "Missing 'label' in forecast item"
        assert "bookings" in first_item, "Missing 'bookings' in forecast item"
        assert "revenue" in first_item, "Missing 'revenue' in forecast item"
        assert "adr" in first_item, "Missing 'adr' in forecast item"
        assert "los" in first_item, "Missing 'los' in forecast item"
        assert "confidence" in first_item, "Missing 'confidence' in forecast item"
        assert "vs_last_year" in first_item, "Missing 'vs_last_year' in forecast item"
        print(f"✓ Horizon default 24 months: {len(data['forecast'])} items, YoY: {data['yoy_growth_pct']}%")

    def test_horizon_custom_months(self, auth_headers):
        """Test horizon with custom months parameter"""
        for months in [6, 12, 18, 36]:
            response = requests.get(
                f"{BASE_URL}/api/forecast-v2/horizon/{PROPERTY_ID}?months={months}",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Expected 200 for months={months}, got {response.status_code}"
            data = response.json()
            assert len(data["forecast"]) == months, f"Expected {months} items, got {len(data['forecast'])}"
            print(f"✓ Horizon with months={months}: {len(data['forecast'])} items")

    def test_horizon_validation_months_too_low(self, auth_headers):
        """Test horizon rejects months < 3"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/horizon/{PROPERTY_ID}?months=0",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for months=0, got {response.status_code}"
        print("✓ Horizon rejects months=0 with 400")

    def test_horizon_validation_months_too_high(self, auth_headers):
        """Test horizon rejects months > 36"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/horizon/{PROPERTY_ID}?months=40",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for months=40, got {response.status_code}"
        print("✓ Horizon rejects months=40 with 400")

    def test_horizon_requires_auth(self):
        """Test horizon requires authentication"""
        response = requests.get(f"{BASE_URL}/api/forecast-v2/horizon/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Horizon requires auth (401 without token)")


class TestForecastV2DemandCalendar:
    """Tests for GET /api/forecast-v2/demand-calendar/{property_id}"""

    def test_demand_calendar_default_90_days(self, auth_headers):
        """Test demand calendar returns 90 days by default"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/demand-calendar/{PROPERTY_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "days" in data, "Missing 'days' array"
        assert "avg_demand_score" in data, "Missing 'avg_demand_score'"
        assert "peak_days_count" in data, "Missing 'peak_days_count'"
        assert "trough_days_count" in data, "Missing 'trough_days_count'"
        assert "rooms_count" in data, "Missing 'rooms_count'"
        
        # Verify days count
        assert len(data["days"]) == 90, f"Expected 90 days, got {len(data['days'])}"
        
        # Verify day item structure
        first_day = data["days"][0]
        assert "date" in first_day, "Missing 'date'"
        assert "dow" in first_day, "Missing 'dow'"
        assert "occupancy_pct" in first_day, "Missing 'occupancy_pct'"
        assert "otb" in first_day, "Missing 'otb'"
        assert "demand_score" in first_day, "Missing 'demand_score'"
        assert "tier" in first_day, "Missing 'tier'"
        assert "tier_label" in first_day, "Missing 'tier_label'"
        assert "holiday" in first_day, "Missing 'holiday' (can be null)"
        assert "is_weekend" in first_day, "Missing 'is_weekend'"
        print(f"✓ Demand calendar default 90 days: {len(data['days'])} days, avg_score: {data['avg_demand_score']}")

    def test_demand_calendar_custom_days(self, auth_headers):
        """Test demand calendar with custom days parameter"""
        for days in [30, 60, 180, 365]:
            response = requests.get(
                f"{BASE_URL}/api/forecast-v2/demand-calendar/{PROPERTY_ID}?days={days}",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Expected 200 for days={days}, got {response.status_code}"
            data = response.json()
            assert len(data["days"]) == days, f"Expected {days} days, got {len(data['days'])}"
            print(f"✓ Demand calendar with days={days}: {len(data['days'])} days")

    def test_demand_calendar_validation_days_too_low(self, auth_headers):
        """Test demand calendar rejects days < 7"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/demand-calendar/{PROPERTY_ID}?days=5",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for days=5, got {response.status_code}"
        print("✓ Demand calendar rejects days=5 with 400")

    def test_demand_calendar_validation_days_too_high(self, auth_headers):
        """Test demand calendar rejects days > 365"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/demand-calendar/{PROPERTY_ID}?days=400",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for days=400, got {response.status_code}"
        print("✓ Demand calendar rejects days=400 with 400")

    def test_demand_calendar_tier_values(self, auth_headers):
        """Test demand calendar tier values are valid"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/demand-calendar/{PROPERTY_ID}?days=90",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        valid_tiers = {"peak", "high", "medium", "low", "trough"}
        for day in data["days"]:
            assert day["tier"] in valid_tiers, f"Invalid tier: {day['tier']}"
            # Verify tier matches score
            score = day["demand_score"]
            if score >= 80:
                assert day["tier"] == "peak", f"Score {score} should be peak, got {day['tier']}"
            elif score >= 60:
                assert day["tier"] == "high", f"Score {score} should be high, got {day['tier']}"
            elif score >= 40:
                assert day["tier"] == "medium", f"Score {score} should be medium, got {day['tier']}"
            elif score >= 20:
                assert day["tier"] == "low", f"Score {score} should be low, got {day['tier']}"
            else:
                assert day["tier"] == "trough", f"Score {score} should be trough, got {day['tier']}"
        print(f"✓ All {len(data['days'])} days have valid tier values matching scores")

    def test_demand_calendar_requires_auth(self):
        """Test demand calendar requires authentication"""
        response = requests.get(f"{BASE_URL}/api/forecast-v2/demand-calendar/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Demand calendar requires auth (401 without token)")


class TestForecastV2PickupCurve:
    """Tests for GET /api/forecast-v2/pickup-curve/{property_id}"""

    def test_pickup_curve_valid_date(self, auth_headers):
        """Test pickup curve with valid target date"""
        target_date = (date.today() + timedelta(days=30)).isoformat()
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/pickup-curve/{PROPERTY_ID}?target_date={target_date}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "target_date" in data, "Missing 'target_date'"
        assert "days_to_go" in data, "Missing 'days_to_go'"
        assert "current_otb" in data, "Missing 'current_otb'"
        assert "actual_curve" in data, "Missing 'actual_curve'"
        assert "historical_avg_curve" in data, "Missing 'historical_avg_curve'"
        assert "pace_vs_hist_pct" in data, "Missing 'pace_vs_hist_pct'"
        assert "pace_status" in data, "Missing 'pace_status'"
        
        # Verify actual_curve has 91 points (lead_days 90 to 0)
        assert len(data["actual_curve"]) == 91, f"Expected 91 points in actual_curve, got {len(data['actual_curve'])}"
        
        # Verify curve point structure
        first_point = data["actual_curve"][0]
        assert "lead_day" in first_point, "Missing 'lead_day' in curve point"
        assert "bookings" in first_point, "Missing 'bookings' in curve point"
        
        # Verify pace_status is valid
        valid_statuses = {"ahead", "behind", "on_track", "no_history"}
        assert data["pace_status"] in valid_statuses, f"Invalid pace_status: {data['pace_status']}"
        
        print(f"✓ Pickup curve: {len(data['actual_curve'])} points, OTB: {data['current_otb']}, pace: {data['pace_status']}")

    def test_pickup_curve_invalid_date_format(self, auth_headers):
        """Test pickup curve rejects invalid date format"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/pickup-curve/{PROPERTY_ID}?target_date=invalid-date",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for invalid date, got {response.status_code}"
        print("✓ Pickup curve rejects invalid date format with 400")

    def test_pickup_curve_invalid_date_format_2(self, auth_headers):
        """Test pickup curve rejects non-YYYY-MM-DD format"""
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/pickup-curve/{PROPERTY_ID}?target_date=15-06-2026",
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for DD-MM-YYYY format, got {response.status_code}"
        print("✓ Pickup curve rejects DD-MM-YYYY format with 400")

    def test_pickup_curve_requires_auth(self):
        """Test pickup curve requires authentication"""
        target_date = (date.today() + timedelta(days=30)).isoformat()
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/pickup-curve/{PROPERTY_ID}?target_date={target_date}"
        )
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Pickup curve requires auth (401 without token)")


class TestForecastV2RBAC:
    """Tests for RBAC on Forecast V2 endpoints"""

    def test_receptionist_can_access_demand_calendar(self):
        """Test receptionist role can access demand-calendar (has receptionist in allowed roles)"""
        # Login as receptionist
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testrecep@hotelbox.com", "password": "Test2026!"}
        )
        if response.status_code != 200:
            pytest.skip("Receptionist login failed")
        
        token = response.json().get("access_token") or response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Demand calendar allows receptionist
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/demand-calendar/{PROPERTY_ID}",
            headers=headers
        )
        assert response.status_code == 200, f"Receptionist should access demand-calendar, got {response.status_code}"
        print("✓ Receptionist can access demand-calendar")

    def test_receptionist_cannot_access_horizon(self):
        """Test receptionist role cannot access horizon (admin/manager only)"""
        # Login as receptionist
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testrecep@hotelbox.com", "password": "Test2026!"}
        )
        if response.status_code != 200:
            pytest.skip("Receptionist login failed")
        
        token = response.json().get("access_token") or response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Horizon requires admin/manager
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/horizon/{PROPERTY_ID}",
            headers=headers
        )
        assert response.status_code == 403, f"Receptionist should be denied horizon, got {response.status_code}"
        print("✓ Receptionist denied access to horizon (403)")

    def test_receptionist_cannot_access_pickup_curve(self):
        """Test receptionist role cannot access pickup-curve (admin/manager only)"""
        # Login as receptionist
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testrecep@hotelbox.com", "password": "Test2026!"}
        )
        if response.status_code != 200:
            pytest.skip("Receptionist login failed")
        
        token = response.json().get("access_token") or response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        target_date = (date.today() + timedelta(days=30)).isoformat()
        response = requests.get(
            f"{BASE_URL}/api/forecast-v2/pickup-curve/{PROPERTY_ID}?target_date={target_date}",
            headers=headers
        )
        assert response.status_code == 403, f"Receptionist should be denied pickup-curve, got {response.status_code}"
        print("✓ Receptionist denied access to pickup-curve (403)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
