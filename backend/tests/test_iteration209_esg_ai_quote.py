"""
Iteration 209 - Sustainability/ESG Dashboard + AI Auto-Quote Tests

Tests:
1. ESG Config endpoints (GET/POST /api/esg/{property_id}/config)
2. ESG Reading endpoints (POST/DELETE /api/esg/{property_id}/reading)
3. ESG Dashboard endpoint (GET /api/esg/{property_id}/dashboard)
4. AI Auto-Quote endpoint (POST /api/group-booking/{booking_id}/ai-quote)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.cookies.get("access_token") or response.json().get("access_token")
    pytest.skip("Authentication failed")

@pytest.fixture(scope="module")
def auth_session(auth_token):
    """Session with auth cookies"""
    session = requests.Session()
    session.cookies.set("access_token", auth_token)
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def test_property_id():
    """Use aldgate-flats as test property"""
    return "aldgate-flats"


# ============================================================
# ESG CONFIG TESTS
# ============================================================
class TestESGConfig:
    """Tests for ESG configuration endpoints"""
    
    def test_get_config_returns_defaults(self, auth_session, test_property_id):
        """GET /api/esg/{property_id}/config returns default config when none exists"""
        response = auth_session.get(f"{BASE_URL}/api/esg/{test_property_id}/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify default baseline values
        assert "kwh_baseline_per_rn" in data
        assert "water_baseline_per_rn" in data
        assert "waste_baseline_per_rn" in data
        assert "co2_factor_grid" in data
        
        # Verify initiatives array with 10 default items
        assert "initiatives" in data
        assert isinstance(data["initiatives"], list)
        assert len(data["initiatives"]) >= 10, f"Expected at least 10 initiatives, got {len(data['initiatives'])}"
        
        # Verify initiative structure
        first_init = data["initiatives"][0]
        assert "key" in first_init
        assert "label" in first_init
        assert "weight" in first_init
        assert "active" in first_init
        print(f"ESG config returned with {len(data['initiatives'])} initiatives")
    
    def test_save_config_upserts(self, auth_session, test_property_id):
        """POST /api/esg/{property_id}/config upserts configuration"""
        # First get current config
        get_resp = auth_session.get(f"{BASE_URL}/api/esg/{test_property_id}/config")
        current_config = get_resp.json()
        
        # Modify some initiatives to be active
        initiatives = current_config.get("initiatives", [])
        for i, init in enumerate(initiatives):
            if init["key"] in ["led_lighting", "linen_reuse", "low_flow"]:
                initiatives[i]["active"] = True
        
        # Save config with custom baselines
        payload = {
            "kwh_baseline_per_rn": 28.0,
            "water_baseline_per_rn": 220.0,
            "waste_baseline_per_rn": 0.9,
            "co2_factor_grid": 0.21,
            "initiatives": initiatives
        }
        
        response = auth_session.post(f"{BASE_URL}/api/esg/{test_property_id}/config", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("ok") == True
        assert "config" in data
        
        # Verify saved values
        saved = data["config"]
        assert saved["kwh_baseline_per_rn"] == 28.0
        assert saved["water_baseline_per_rn"] == 220.0
        print("ESG config saved successfully with custom baselines")
    
    def test_config_requires_auth(self, test_property_id):
        """Config endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/esg/{test_property_id}/config")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


# ============================================================
# ESG READING TESTS
# ============================================================
class TestESGReadings:
    """Tests for ESG monthly reading endpoints"""
    
    @pytest.fixture
    def test_reading_id(self):
        """Store reading ID for cleanup"""
        return {"id": None}
    
    def test_add_reading_success(self, auth_session, test_property_id, test_reading_id):
        """POST /api/esg/{property_id}/reading creates a monthly reading"""
        payload = {
            "month": "2026-01",
            "kwh": 4500,
            "water_litres": 55000,
            "waste_kg": 120,
            "gas_kwh": 800,
            "notes": "Test reading for January 2026"
        }
        
        response = auth_session.post(f"{BASE_URL}/api/esg/{test_property_id}/reading", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["month"] == "2026-01"
        assert data["kwh"] == 4500
        assert data["water_litres"] == 55000
        assert data["waste_kg"] == 120
        test_reading_id["id"] = data["id"]
        print(f"Reading created with ID: {data['id']}")
    
    def test_add_reading_idempotent(self, auth_session, test_property_id):
        """POST same month replaces existing reading (idempotent)"""
        # Add first reading
        payload1 = {"month": "2026-02", "kwh": 3000, "water_litres": 40000, "waste_kg": 100}
        resp1 = auth_session.post(f"{BASE_URL}/api/esg/{test_property_id}/reading", json=payload1)
        assert resp1.status_code == 200
        id1 = resp1.json()["id"]
        
        # Add second reading for same month
        payload2 = {"month": "2026-02", "kwh": 3500, "water_litres": 45000, "waste_kg": 110}
        resp2 = auth_session.post(f"{BASE_URL}/api/esg/{test_property_id}/reading", json=payload2)
        assert resp2.status_code == 200
        id2 = resp2.json()["id"]
        
        # IDs should be different (old one deleted, new one created)
        assert id1 != id2
        
        # Verify only one reading exists for that month via dashboard
        dash_resp = auth_session.get(f"{BASE_URL}/api/esg/{test_property_id}/dashboard?months=12")
        trend = dash_resp.json().get("trend", [])
        feb_readings = [r for r in trend if r["month"] == "2026-02"]
        assert len(feb_readings) <= 1, "Should only have one reading per month"
        print("Idempotent reading replacement verified")
    
    def test_add_reading_invalid_month(self, auth_session, test_property_id):
        """POST with invalid month format returns 400"""
        payload = {"month": "2026-1", "kwh": 1000}  # Invalid format
        response = auth_session.post(f"{BASE_URL}/api/esg/{test_property_id}/reading", json=payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Invalid month format correctly rejected")
    
    def test_delete_reading_success(self, auth_session, test_property_id):
        """DELETE /api/esg/{property_id}/reading/{reading_id} removes reading"""
        # First create a reading to delete
        payload = {"month": "2026-03", "kwh": 2000, "water_litres": 30000, "waste_kg": 80}
        create_resp = auth_session.post(f"{BASE_URL}/api/esg/{test_property_id}/reading", json=payload)
        reading_id = create_resp.json()["id"]
        
        # Delete it
        delete_resp = auth_session.delete(f"{BASE_URL}/api/esg/{test_property_id}/reading/{reading_id}")
        assert delete_resp.status_code == 200, f"Expected 200, got {delete_resp.status_code}"
        assert delete_resp.json().get("ok") == True
        print(f"Reading {reading_id} deleted successfully")
    
    def test_delete_reading_not_found(self, auth_session, test_property_id):
        """DELETE with unknown reading_id returns 404"""
        fake_id = str(uuid.uuid4())
        response = auth_session.delete(f"{BASE_URL}/api/esg/{test_property_id}/reading/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Delete non-existent reading correctly returns 404")


# ============================================================
# ESG DASHBOARD TESTS
# ============================================================
class TestESGDashboard:
    """Tests for ESG dashboard endpoint"""
    
    def test_dashboard_returns_all_fields(self, auth_session, test_property_id):
        """GET /api/esg/{property_id}/dashboard returns complete dashboard data"""
        response = auth_session.get(f"{BASE_URL}/api/esg/{test_property_id}/dashboard?months=12")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        required_fields = [
            "esg_score", "grade", "intensity_score", "initiatives_score",
            "active_initiatives_count", "total_initiatives_count",
            "latest", "trend", "config", "initiatives", "as_of"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify score is 0-100
        assert 0 <= data["esg_score"] <= 100, f"ESG score out of range: {data['esg_score']}"
        
        # Verify grade is valid
        assert data["grade"] in ["A+", "A", "B", "C", "D"], f"Invalid grade: {data['grade']}"
        
        # Verify config structure
        config = data["config"]
        assert "kwh_baseline_per_rn" in config
        assert "water_baseline_per_rn" in config
        assert "waste_baseline_per_rn" in config
        assert "co2_factor_grid" in config
        
        print(f"Dashboard: ESG Score={data['esg_score']}, Grade={data['grade']}")
    
    def test_dashboard_trend_has_computed_fields(self, auth_session, test_property_id):
        """Dashboard trend rows have computed intensity metrics"""
        # First ensure we have a reading
        payload = {"month": "2026-04", "kwh": 5000, "water_litres": 60000, "waste_kg": 130}
        auth_session.post(f"{BASE_URL}/api/esg/{test_property_id}/reading", json=payload)
        
        response = auth_session.get(f"{BASE_URL}/api/esg/{test_property_id}/dashboard?months=12")
        data = response.json()
        trend = data.get("trend", [])
        
        if trend:
            row = trend[-1]  # Latest row
            computed_fields = [
                "kwh_per_rn", "water_per_rn", "waste_per_rn",
                "co2_total_kg", "co2_per_rn", "room_nights"
            ]
            for field in computed_fields:
                assert field in row, f"Missing computed field: {field}"
            
            # Verify baseline comparison fields exist
            baseline_fields = ["kwh_vs_baseline_pct", "water_vs_baseline_pct", "waste_vs_baseline_pct"]
            for field in baseline_fields:
                assert field in row, f"Missing baseline field: {field}"
            
            print(f"Trend row computed: kWh/RN={row['kwh_per_rn']}, CO2/RN={row['co2_per_rn']}")
        else:
            print("No trend data yet (no readings)")
    
    def test_dashboard_months_param(self, auth_session, test_property_id):
        """Dashboard respects months query parameter"""
        # Test with different month values
        for months in [3, 6, 12, 24]:
            response = auth_session.get(f"{BASE_URL}/api/esg/{test_property_id}/dashboard?months={months}")
            assert response.status_code == 200
        print("Months parameter accepted for various values")


# ============================================================
# AI AUTO-QUOTE TESTS
# ============================================================
class TestAIAutoQuote:
    """Tests for AI Auto-Quote endpoint on group bookings"""
    
    @pytest.fixture
    def test_group_booking_id(self, auth_session, test_property_id):
        """Create a test group booking request"""
        payload = {
            "property_id": test_property_id,
            "contact_name": "Test Corporate Client",
            "contact_email": "corporate@test.com",
            "contact_phone": "+44 20 1234 5678",
            "company_name": "Test Corp Ltd",
            "event_type": "corporate",
            "check_in": "2026-05-01",
            "check_out": "2026-05-05",
            "total_rooms": 8,
            "total_guests": 12,
            "room_preferences": "Mix of double and twin rooms",
            "special_requirements": "Meeting room needed",
            "budget_range": "£3000-£4000"
        }
        response = requests.post(f"{BASE_URL}/api/group-booking/request", json=payload)
        if response.status_code == 200:
            return response.json().get("id")
        pytest.skip("Failed to create test group booking")
    
    def test_ai_quote_returns_quote(self, auth_session, test_group_booking_id):
        """POST /api/group-booking/{booking_id}/ai-quote returns quote data"""
        response = auth_session.post(f"{BASE_URL}/api/group-booking/{test_group_booking_id}/ai-quote")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        required_fields = ["suggested_total", "per_room_per_night", "discount_pct", "currency", "reasoning"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify numeric values
        assert isinstance(data["suggested_total"], (int, float))
        assert data["suggested_total"] > 0
        assert isinstance(data["per_room_per_night"], (int, float))
        assert isinstance(data["discount_pct"], (int, float))
        
        # Verify currency
        assert data["currency"] == "GBP"
        
        # Verify reasoning is a string
        assert isinstance(data["reasoning"], str)
        assert len(data["reasoning"]) > 10
        
        # Check if fallback or real AI
        is_fallback = data.get("fallback", False)
        print(f"AI Quote: £{data['suggested_total']} ({data['discount_pct']}% off) - {'Heuristic' if is_fallback else 'GPT-5.2'}")
        print(f"Reasoning: {data['reasoning'][:100]}...")
    
    def test_ai_quote_not_found(self, auth_session):
        """POST with unknown booking_id returns 404"""
        fake_id = str(uuid.uuid4())
        response = auth_session.post(f"{BASE_URL}/api/group-booking/{fake_id}/ai-quote")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("AI quote for non-existent booking correctly returns 404")
    
    def test_ai_quote_requires_auth(self, test_group_booking_id):
        """AI quote endpoint requires authentication"""
        # Create a booking first via public endpoint
        payload = {
            "property_id": "aldgate-flats",
            "contact_name": "Auth Test",
            "contact_email": "auth@test.com",
            "event_type": "wedding",
            "check_in": "2026-06-01",
            "check_out": "2026-06-03",
            "total_rooms": 5,
            "total_guests": 10
        }
        create_resp = requests.post(f"{BASE_URL}/api/group-booking/request", json=payload)
        if create_resp.status_code == 200:
            booking_id = create_resp.json().get("id")
            # Try to get AI quote without auth
            response = requests.post(f"{BASE_URL}/api/group-booking/{booking_id}/ai-quote")
            assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
            print("AI quote endpoint correctly requires authentication")


# ============================================================
# REGRESSION TESTS
# ============================================================
class TestRegression:
    """Smoke tests for existing features"""
    
    def test_login_works(self):
        """Admin login still works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        print("Login working")
    
    def test_group_requests_list(self, auth_session, test_property_id):
        """Group requests list endpoint still works"""
        response = auth_session.get(f"{BASE_URL}/api/group-booking/requests/{test_property_id}")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("Group requests list working")
    
    def test_concierge_inbox(self, auth_session, test_property_id):
        """Concierge inbox endpoint still works"""
        response = auth_session.get(f"{BASE_URL}/api/concierge/{test_property_id}/inbox")
        assert response.status_code == 200
        print("Concierge inbox working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
