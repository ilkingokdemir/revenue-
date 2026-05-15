"""
Iteration 300 - Multi-City Scan Enhancement Tests
Tests for secondary cities feature in Event Intelligence:
- GET/POST/DELETE /api/revenue/events/{pid}/secondary-cities
- GET /api/revenue/events/{pid} with tracked_cities, per_city_counts
- POST /api/revenue/events/{pid}/scan parallel multi-city scan (response shape only)
- POST /api/revenue/events/{pid}/cleanup-foreign with tracked_cities
- RBAC: receptionist gets 403 on secondary-cities endpoints
- Regression: existing endpoints still work
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEP_EMAIL = "testrecep@hotelbox.com"
RECEP_PASSWORD = "Test2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code}")
    # API returns 'token' not 'access_token'
    return resp.json().get("token") or resp.json().get("access_token")


@pytest.fixture(scope="module")
def recep_token():
    """Get receptionist auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": RECEP_EMAIL,
        "password": RECEP_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Receptionist login failed: {resp.status_code}")
    # API returns 'token' not 'access_token'
    return resp.json().get("token") or resp.json().get("access_token")


@pytest.fixture(scope="module")
def test_property_id(admin_token):
    """Create a test property for multi-city testing"""
    pid = f"test-multi-{uuid.uuid4().hex[:8]}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create property
    requests.post(f"{BASE_URL}/api/properties", json={
        "id": pid,
        "name": f"Test Multi-City Property {pid}",
        "city": "London",
        "currency": "GBP"
    }, headers=headers)
    
    # Set up market robot config with primary city
    requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
        "city": "London",
        "enabled": False
    }, headers=headers)
    
    yield pid
    
    # Cleanup: delete test property events and config
    requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)


class TestSecondaryEndpointExists:
    """Test that secondary-cities endpoints exist and return correct structure"""
    
    def test_get_secondary_cities_endpoint_exists(self, admin_token, test_property_id):
        """GET /api/revenue/events/{pid}/secondary-cities returns 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "primary" in data, "Response should have 'primary' field"
        assert "secondary_cities" in data, "Response should have 'secondary_cities' field"
        assert isinstance(data["secondary_cities"], list), "secondary_cities should be a list"
    
    def test_get_secondary_cities_returns_primary(self, admin_token, test_property_id):
        """GET secondary-cities returns the primary city from config"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Primary should be London (set in fixture)
        assert data["primary"].lower() == "london", f"Expected primary='London', got '{data['primary']}'"


class TestAddSecondaryCity:
    """Test POST /api/revenue/events/{pid}/secondary-cities"""
    
    def test_add_secondary_city_success(self, admin_token, test_property_id):
        """Add a secondary city successfully"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                            json={"city": "Brighton"}, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") == True
        assert "Brighton" in data.get("secondary_cities", [])
    
    def test_add_secondary_city_missing_city_returns_400(self, admin_token, test_property_id):
        """400 if city field is missing"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                            json={}, headers=headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    def test_add_secondary_city_empty_city_returns_400(self, admin_token, test_property_id):
        """400 if city is empty string"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                            json={"city": ""}, headers=headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    def test_add_secondary_city_whitespace_only_returns_400(self, admin_token, test_property_id):
        """400 if city is whitespace only"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                            json={"city": "   "}, headers=headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    
    def test_add_secondary_city_same_as_primary_returns_400(self, admin_token, test_property_id):
        """400 if city is same as primary (case-insensitive)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                            json={"city": "London"}, headers=headers)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        
        # Also test case-insensitive
        resp2 = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                             json={"city": "LONDON"}, headers=headers)
        assert resp2.status_code == 400, f"Expected 400 for 'LONDON', got {resp2.status_code}"
        
        resp3 = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                             json={"city": "london"}, headers=headers)
        assert resp3.status_code == 400, f"Expected 400 for 'london', got {resp3.status_code}"
    
    def test_add_secondary_city_duplicate_returns_400(self, admin_token, test_property_id):
        """400 if city already in secondary list (case-insensitive)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # First add Brighton (may already exist from previous test)
        requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                     json={"city": "Brighton"}, headers=headers)
        
        # Try to add again
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                            json={"city": "Brighton"}, headers=headers)
        assert resp.status_code == 400, f"Expected 400 for duplicate, got {resp.status_code}"
        
        # Case-insensitive duplicate
        resp2 = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                             json={"city": "BRIGHTON"}, headers=headers)
        assert resp2.status_code == 400, f"Expected 400 for 'BRIGHTON', got {resp2.status_code}"


class TestSecondaryLimit:
    """Test the 5 secondary cities limit"""
    
    def test_add_secondary_city_limit_5(self, admin_token):
        """400 if trying to add more than 5 secondary cities"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        pid = f"test-limit-{uuid.uuid4().hex[:8]}"
        
        # Create property
        requests.post(f"{BASE_URL}/api/properties", json={
            "id": pid, "name": f"Test Limit {pid}", "city": "London"
        }, headers=headers)
        requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
            "city": "London"
        }, headers=headers)
        
        # Add 5 cities
        cities = ["Brighton", "Oxford", "Cambridge", "Manchester", "Liverpool"]
        for city in cities:
            resp = requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                                json={"city": city}, headers=headers)
            assert resp.status_code == 200, f"Failed to add {city}: {resp.status_code}"
        
        # Try to add 6th city
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                            json={"city": "Bristol"}, headers=headers)
        assert resp.status_code == 400, f"Expected 400 for 6th city, got {resp.status_code}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)


class TestRemoveSecondaryCity:
    """Test DELETE /api/revenue/events/{pid}/secondary-cities/{city_name}"""
    
    def test_remove_secondary_city_success(self, admin_token):
        """Remove a secondary city and its events"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        pid = f"test-remove-{uuid.uuid4().hex[:8]}"
        
        # Create property
        requests.post(f"{BASE_URL}/api/properties", json={
            "id": pid, "name": f"Test Remove {pid}", "city": "London"
        }, headers=headers)
        requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
            "city": "London"
        }, headers=headers)
        
        # Add secondary city
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                     json={"city": "Oxford"}, headers=headers)
        
        # Add an event for Oxford
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/add", json={
            "name": "Oxford Test Event",
            "date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "city": "Oxford",
            "category": "concert",
            "hotel_demand_score": 50,
            "auto_price": False
        }, headers=headers)
        
        # Remove Oxford
        resp = requests.delete(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities/Oxford", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") == True
        assert "Oxford" not in data.get("secondary_cities", [])
        assert data.get("deleted_events", 0) >= 1, "Should have deleted at least 1 event"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)
    
    def test_remove_secondary_city_not_in_list_returns_404(self, admin_token, test_property_id):
        """404 if city is not in secondary list"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.delete(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/NonExistentCity", 
                              headers=headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    
    def test_remove_secondary_city_case_insensitive(self, admin_token):
        """Remove works case-insensitively"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        pid = f"test-case-{uuid.uuid4().hex[:8]}"
        
        # Create property
        requests.post(f"{BASE_URL}/api/properties", json={
            "id": pid, "name": f"Test Case {pid}", "city": "London"
        }, headers=headers)
        requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
            "city": "London"
        }, headers=headers)
        
        # Add "Brighton"
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                     json={"city": "Brighton"}, headers=headers)
        
        # Remove with different case "BRIGHTON"
        resp = requests.delete(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities/BRIGHTON", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)


class TestGetEventsWithTrackedCities:
    """Test GET /api/revenue/events/{pid} returns tracked_cities and per_city_counts"""
    
    def test_get_events_includes_secondary_cities(self, admin_token):
        """GET events returns secondary_cities field"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        pid = f"test-get-{uuid.uuid4().hex[:8]}"
        
        # Create property
        requests.post(f"{BASE_URL}/api/properties", json={
            "id": pid, "name": f"Test Get {pid}", "city": "London"
        }, headers=headers)
        requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
            "city": "London"
        }, headers=headers)
        
        # Add secondary cities
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                     json={"city": "Brighton"}, headers=headers)
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                     json={"city": "Oxford"}, headers=headers)
        
        # Get events
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{pid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "secondary_cities" in data, "Response should have secondary_cities"
        assert "tracked_cities" in data, "Response should have tracked_cities"
        assert "per_city_counts" in data, "Response should have per_city_counts"
        
        assert "Brighton" in data["secondary_cities"]
        assert "Oxford" in data["secondary_cities"]
        assert "London" in data["tracked_cities"]
        assert "Brighton" in data["tracked_cities"]
        assert "Oxford" in data["tracked_cities"]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)
    
    def test_get_events_per_city_counts(self, admin_token):
        """GET events returns per_city_counts with event counts per city"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        pid = f"test-counts-{uuid.uuid4().hex[:8]}"
        
        # Create property
        requests.post(f"{BASE_URL}/api/properties", json={
            "id": pid, "name": f"Test Counts {pid}", "city": "London"
        }, headers=headers)
        requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
            "city": "London"
        }, headers=headers)
        
        # Add secondary city
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                     json={"city": "Brighton"}, headers=headers)
        
        # Add events for each city
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/add", json={
            "name": "London Event 1",
            "date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "city": "London",
            "hotel_demand_score": 50,
            "auto_price": False
        }, headers=headers)
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/add", json={
            "name": "London Event 2",
            "date": (datetime.now() + timedelta(days=31)).strftime("%Y-%m-%d"),
            "city": "London",
            "hotel_demand_score": 60,
            "auto_price": False
        }, headers=headers)
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/add", json={
            "name": "Brighton Event 1",
            "date": (datetime.now() + timedelta(days=32)).strftime("%Y-%m-%d"),
            "city": "Brighton",
            "hotel_demand_score": 70,
            "auto_price": False
        }, headers=headers)
        
        # Get events
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{pid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        per_city = data.get("per_city_counts", {})
        assert per_city.get("London", 0) == 2, f"Expected 2 London events, got {per_city.get('London')}"
        assert per_city.get("Brighton", 0) == 1, f"Expected 1 Brighton event, got {per_city.get('Brighton')}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)


class TestScanResponseShape:
    """Test POST /api/revenue/events/{pid}/scan response shape (DO NOT trigger real GPT)"""
    
    def test_scan_response_includes_tracked_cities(self, admin_token):
        """Scan response includes tracked_cities and per_city breakdown"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        pid = f"test-scan-{uuid.uuid4().hex[:8]}"
        
        # Create property with NO GPT setup (will return 0 events but correct shape)
        requests.post(f"{BASE_URL}/api/properties", json={
            "id": pid, "name": f"Test Scan {pid}", "city": "TestCity123"
        }, headers=headers)
        requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
            "city": "TestCity123"
        }, headers=headers)
        
        # Add secondary city
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                     json={"city": "TestCity456"}, headers=headers)
        
        # Call scan with auto_price=false to minimize side effects
        # Note: This will trigger GPT but with fake cities, should return quickly with 0 events
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{pid}/scan", json={
            "days_ahead": 30,
            "auto_price": False
        }, headers=headers, timeout=120)
        
        # Check response shape (may timeout or return 0 events, but shape should be correct)
        if resp.status_code == 200:
            data = resp.json()
            assert "tracked_cities" in data, "Response should have tracked_cities"
            assert "per_city" in data, "Response should have per_city breakdown"
            assert isinstance(data["per_city"], list), "per_city should be a list"
            assert "TestCity123" in data["tracked_cities"]
            assert "TestCity456" in data["tracked_cities"]
            
            # Check per_city structure
            for pc in data["per_city"]:
                assert "city" in pc, "per_city item should have 'city'"
                assert "found" in pc, "per_city item should have 'found'"
                assert "stored" in pc, "per_city item should have 'stored'"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)


class TestCleanupForeignWithTrackedCities:
    """Test POST /api/revenue/events/{pid}/cleanup-foreign with tracked_cities"""
    
    def test_cleanup_foreign_returns_tracked_cities(self, admin_token):
        """cleanup-foreign response includes tracked_cities"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        pid = f"test-cleanup-{uuid.uuid4().hex[:8]}"
        
        # Create property
        requests.post(f"{BASE_URL}/api/properties", json={
            "id": pid, "name": f"Test Cleanup {pid}", "city": "London"
        }, headers=headers)
        requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
            "city": "London"
        }, headers=headers)
        
        # Add secondary city
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/secondary-cities", 
                     json={"city": "Brighton"}, headers=headers)
        
        # Add events: 2 tracked (London, Brighton), 1 foreign (Paris)
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/add", json={
            "name": "London Event",
            "date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "city": "London",
            "auto_price": False
        }, headers=headers)
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/add", json={
            "name": "Brighton Event",
            "date": (datetime.now() + timedelta(days=31)).strftime("%Y-%m-%d"),
            "city": "Brighton",
            "auto_price": False
        }, headers=headers)
        requests.post(f"{BASE_URL}/api/revenue/events/{pid}/add", json={
            "name": "Paris Event",
            "date": (datetime.now() + timedelta(days=32)).strftime("%Y-%m-%d"),
            "city": "Paris",
            "auto_price": False
        }, headers=headers)
        
        # Run cleanup-foreign
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{pid}/cleanup-foreign", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "tracked_cities" in data, "Response should have tracked_cities"
        assert "London" in data["tracked_cities"]
        assert "Brighton" in data["tracked_cities"]
        assert data.get("deleted", 0) >= 1, "Should have deleted Paris event"
        assert "Paris" in data.get("foreign_cities_removed", [])
        
        # Verify Paris event is gone
        events_resp = requests.get(f"{BASE_URL}/api/revenue/events/{pid}", headers=headers)
        events = events_resp.json().get("events", [])
        event_cities = [e.get("city") for e in events]
        assert "Paris" not in event_cities, "Paris event should be deleted"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)


class TestRBACSecondaryEndpoints:
    """Test RBAC: receptionist gets 403 on secondary-cities endpoints"""
    
    def test_receptionist_cannot_get_secondary_cities(self, recep_token, test_property_id):
        """Receptionist gets 403 on GET secondary-cities"""
        headers = {"Authorization": f"Bearer {recep_token}"}
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", headers=headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    def test_receptionist_cannot_add_secondary_city(self, recep_token, test_property_id):
        """Receptionist gets 403 on POST secondary-cities"""
        headers = {"Authorization": f"Bearer {recep_token}"}
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities", 
                            json={"city": "TestCity"}, headers=headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    def test_receptionist_cannot_remove_secondary_city(self, recep_token, test_property_id):
        """Receptionist gets 403 on DELETE secondary-cities"""
        headers = {"Authorization": f"Bearer {recep_token}"}
        resp = requests.delete(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities/TestCity", 
                              headers=headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
    
    def test_unauthenticated_cannot_access_secondary_cities(self, test_property_id):
        """Unauthenticated request gets 401"""
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}/secondary-cities")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


class TestRegressionExistingEndpoints:
    """Regression tests: existing Event Intelligence endpoints still work"""
    
    def test_get_events_still_works(self, admin_token, test_property_id):
        """GET /api/revenue/events/{pid} returns 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "counts" in data
        assert "city" in data
    
    def test_add_event_still_works(self, admin_token, test_property_id):
        """POST /api/revenue/events/{pid}/add returns 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/add", json={
            "name": "Regression Test Event",
            "date": (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d"),
            "city": "London",
            "category": "concert",
            "hotel_demand_score": 50,
            "auto_price": False
        }, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "event" in data
    
    def test_cleanup_foreign_still_works(self, admin_token, test_property_id):
        """POST /api/revenue/events/{pid}/cleanup-foreign returns 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/cleanup-foreign", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data or "deleted" in data
    
    def test_migrations_endpoint_still_works(self, admin_token, test_property_id):
        """GET /api/revenue/events/{pid}/migrations returns 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_property_id}/migrations", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
    
    def test_rescan_full_still_works(self, admin_token):
        """POST /api/revenue/events/{pid}/rescan-full returns 200 (with fake city)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        pid = f"test-rescan-{uuid.uuid4().hex[:8]}"
        
        # Create property with fake city
        requests.post(f"{BASE_URL}/api/properties", json={
            "id": pid, "name": f"Test Rescan {pid}", "city": "FakeCity999"
        }, headers=headers)
        requests.put(f"{BASE_URL}/api/revenue/market-robot/{pid}/config", json={
            "city": "FakeCity999"
        }, headers=headers)
        
        # Call rescan-full (will return quickly with 0 events for fake city)
        resp = requests.post(f"{BASE_URL}/api/revenue/events/{pid}/rescan-full", json={}, 
                            headers=headers, timeout=120)
        
        # Should return 200 even if 0 events found
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{pid}", headers=headers)


class TestDeleteEventStillWorks:
    """Test DELETE /api/revenue/events/{event_id} still works"""
    
    def test_delete_event_still_works(self, admin_token, test_property_id):
        """DELETE /api/revenue/events/{event_id} returns 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Add an event
        add_resp = requests.post(f"{BASE_URL}/api/revenue/events/{test_property_id}/add", json={
            "name": "Event To Delete",
            "date": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
            "city": "London",
            "auto_price": False
        }, headers=headers)
        assert add_resp.status_code == 200
        event_id = add_resp.json().get("event", {}).get("id")
        
        if event_id:
            # Delete the event
            del_resp = requests.delete(f"{BASE_URL}/api/revenue/events/{event_id}", headers=headers)
            assert del_resp.status_code == 200, f"Expected 200, got {del_resp.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
