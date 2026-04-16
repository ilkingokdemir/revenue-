"""
Iteration 104 - Event Intelligence Integration with Dynamic Pricing Tests
Tests the Event Intelligence module and its integration with the AI Dynamic Pricing Engine.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEventIntelligenceIntegration:
    """Test Event Intelligence endpoints and Dynamic Pricing integration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - login and get token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    # ==================== Dynamic Pricing Calculate Tests ====================
    
    def test_dynamic_pricing_calculate_returns_90_days(self):
        """POST /api/revenue/dynamic-pricing/all/calculate returns 90 days of prices"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate",
            headers=self.headers,
            json={"days": 90}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "room_types" in data
        assert "summary" in data
        assert "data_sources" in data
        
        # Verify summary
        assert data["summary"]["total_days"] == 90
        assert "increases" in data["summary"]
        assert "decreases" in data["summary"]
        assert "avg_change_pct" in data["summary"]
        assert "avg_ai_price" in data["summary"]
        assert "event_days" in data["summary"]  # Event days count
    
    def test_dynamic_pricing_calculate_includes_event_data_source(self):
        """Calculate response includes events_loaded in data_sources"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate",
            headers=self.headers,
            json={"days": 90}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify data_sources includes events
        assert "events_loaded" in data["data_sources"]
        assert data["data_sources"]["events_loaded"] >= 0
    
    def test_dynamic_pricing_calculate_includes_event_in_breakdown(self):
        """Calculate response includes event factor in price breakdown"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate",
            headers=self.headers,
            json={"days": 90}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find a day with an event
        prices = data["room_types"][0]["prices"]
        event_days = [p for p in prices if p.get("event")]
        
        if event_days:
            event_day = event_days[0]
            assert "event" in event_day
            assert "event_impact" in event_day
            assert event_day["event_impact"] in ["mega", "large", "medium", "small"]
            # Check breakdown includes event factor
            assert "event" in event_day.get("breakdown", {})
    
    def test_dynamic_pricing_calculate_price_columns(self):
        """Calculate response includes all required price columns"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate",
            headers=self.headers,
            json={"days": 90}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check first price entry has all columns
        price = data["room_types"][0]["prices"][0]
        required_columns = [
            "date", "day", "dow", "days_ahead", "base_rate", "current_rate",
            "ai_price", "change_pct", "our_occupancy", "market_unavail",
            "competitor_avg", "event", "event_impact", "breakdown", "is_today"
        ]
        for col in required_columns:
            assert col in price, f"Missing column: {col}"
    
    # ==================== Dynamic Pricing Apply Tests ====================
    
    def test_dynamic_pricing_apply_returns_applied_count(self):
        """POST /api/revenue/dynamic-pricing/all/apply applies prices"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/dynamic-pricing/all/apply",
            headers=self.headers,
            json={"days": 90}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "applied" in data
        assert data["applied"] == 90
        assert data["days"] == 90
        assert "room_types" in data
    
    # ==================== Event Intelligence Get Tests ====================
    
    def test_get_events_returns_list_and_counts(self):
        """GET /api/revenue/events/all returns events and counts"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/events/all",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "counts" in data
        assert isinstance(data["events"], list)
        
        # Verify counts structure
        counts = data["counts"]
        assert "mega" in counts
        assert "large" in counts
        assert "medium" in counts
        assert "small" in counts
        assert "total" in counts
    
    def test_get_events_event_structure(self):
        """Events have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/events/all",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["events"]:
            event = data["events"][0]
            required_fields = ["id", "property_id", "name", "date", "impact", "category"]
            for field in required_fields:
                assert field in event, f"Missing field: {field}"
    
    # ==================== Event Intelligence Add Tests ====================
    
    def test_add_manual_event_success(self):
        """POST /api/revenue/events/all/add creates event with prices_adjusted"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/events/all/add",
            headers=self.headers,
            json={
                "name": "TEST_Iteration104_Concert",
                "date": "2026-07-15",
                "end_date": "2026-07-15",
                "venue": "O2 Arena",
                "category": "concert",
                "estimated_attendance": 60000,
                "description": "Test event for iteration 104"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "TEST_Iteration104_Concert"
        assert data["impact"] == "mega"  # 60000 attendance = mega
        assert "prices_adjusted" in data
        assert data["prices_adjusted"] >= 0
    
    def test_add_manual_event_impact_calculation(self):
        """Event impact is calculated based on attendance"""
        # Test mega (50k+)
        response = requests.post(
            f"{BASE_URL}/api/revenue/events/all/add",
            headers=self.headers,
            json={"name": "TEST_Mega_Event", "date": "2026-08-01", "estimated_attendance": 55000}
        )
        assert response.status_code == 200
        assert response.json()["impact"] == "mega"
        
        # Test large (20k-50k)
        response = requests.post(
            f"{BASE_URL}/api/revenue/events/all/add",
            headers=self.headers,
            json={"name": "TEST_Large_Event", "date": "2026-08-02", "estimated_attendance": 25000}
        )
        assert response.status_code == 200
        assert response.json()["impact"] == "large"
        
        # Test medium (5k-20k)
        response = requests.post(
            f"{BASE_URL}/api/revenue/events/all/add",
            headers=self.headers,
            json={"name": "TEST_Medium_Event", "date": "2026-08-03", "estimated_attendance": 10000}
        )
        assert response.status_code == 200
        assert response.json()["impact"] == "medium"
        
        # Test small (1k-5k)
        response = requests.post(
            f"{BASE_URL}/api/revenue/events/all/add",
            headers=self.headers,
            json={"name": "TEST_Small_Event", "date": "2026-08-04", "estimated_attendance": 2000}
        )
        assert response.status_code == 200
        assert response.json()["impact"] == "small"
    
    # ==================== Integration Tests ====================
    
    def test_event_affects_dynamic_pricing(self):
        """Events affect dynamic pricing calculations"""
        # First get events count
        events_response = requests.get(
            f"{BASE_URL}/api/revenue/events/all",
            headers=self.headers
        )
        events_count = events_response.json()["counts"]["total"]
        
        # Calculate prices
        calc_response = requests.post(
            f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate",
            headers=self.headers,
            json={"days": 90}
        )
        assert calc_response.status_code == 200
        data = calc_response.json()
        
        # Verify events are loaded
        assert data["data_sources"]["events_loaded"] > 0
        
        # Verify event_days in summary
        assert data["summary"]["event_days"] > 0
    
    def test_summary_kpis_present(self):
        """Summary includes all required KPIs"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/dynamic-pricing/all/calculate",
            headers=self.headers,
            json={"days": 90}
        )
        assert response.status_code == 200
        summary = response.json()["summary"]
        
        # All KPIs from UI
        assert "total_days" in summary  # Days Priced
        assert "increases" in summary   # Price Increases
        assert "decreases" in summary   # Price Decreases
        assert "avg_change_pct" in summary  # Avg Change
        assert "avg_ai_price" in summary    # Avg AI Price
        assert "event_days" in summary      # Event days count


class TestEventIntelligenceCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        self.token = login_response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_cleanup_test_events(self):
        """Clean up TEST_ prefixed events"""
        # Get all events
        response = requests.get(f"{BASE_URL}/api/revenue/events/all", headers=self.headers)
        events = response.json().get("events", [])
        
        # Delete TEST_ events
        deleted = 0
        for event in events:
            if event.get("name", "").startswith("TEST_"):
                del_response = requests.delete(
                    f"{BASE_URL}/api/revenue/events/{event['id']}",
                    headers=self.headers
                )
                if del_response.status_code == 200:
                    deleted += 1
        
        print(f"Cleaned up {deleted} test events")
        assert True  # Always pass cleanup
