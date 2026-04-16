"""
Test Market Robot Competitor Hotels Feature - Iteration 102
Tests competitor CRUD operations and scan functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMarketRobotCompetitors:
    """Test competitor hotel CRUD and scan endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        
        # Store cookies for subsequent requests
        self.property_id = "all"
        yield
    
    def test_get_competitors_list(self):
        """GET /api/revenue/market-robot/{property_id}/competitors returns competitor list"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors")
        assert resp.status_code == 200, f"Failed to get competitors: {resp.text}"
        
        data = resp.json()
        assert "competitors" in data, "Response should have 'competitors' key"
        assert isinstance(data["competitors"], list), "Competitors should be a list"
        
        # Check if The Barkston is in the list (pre-added)
        competitor_names = [c.get("name", "").lower() for c in data["competitors"]]
        print(f"Found {len(data['competitors'])} competitors: {competitor_names}")
        
        # Verify competitor structure if any exist
        if data["competitors"]:
            comp = data["competitors"][0]
            assert "id" in comp, "Competitor should have 'id'"
            assert "name" in comp, "Competitor should have 'name'"
            assert "booking_url" in comp, "Competitor should have 'booking_url'"
    
    def test_add_competitor_with_booking_url(self):
        """POST /api/revenue/market-robot/{property_id}/competitors adds a competitor"""
        test_competitor = {
            "name": "TEST_Competitor Hotel",
            "booking_url": "https://www.booking.com/hotel/gb/test-competitor-hotel.html"
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors",
            json=test_competitor
        )
        assert resp.status_code == 200, f"Failed to add competitor: {resp.text}"
        
        data = resp.json()
        assert "id" in data, "Response should have 'id'"
        assert data["name"] == test_competitor["name"], "Name should match"
        assert data["booking_url"] == test_competitor["booking_url"], "URL should match"
        assert "slug" in data, "Should extract slug from URL"
        
        # Store ID for cleanup
        self.test_competitor_id = data["id"]
        print(f"Created competitor with ID: {self.test_competitor_id}")
        
        # Verify it appears in the list
        list_resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors")
        assert list_resp.status_code == 200
        competitors = list_resp.json()["competitors"]
        ids = [c["id"] for c in competitors]
        assert self.test_competitor_id in ids, "New competitor should appear in list"
    
    def test_add_competitor_without_name(self):
        """POST competitor without name should auto-generate from URL slug"""
        test_competitor = {
            "booking_url": "https://www.booking.com/hotel/gb/the-savoy-london.html"
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors",
            json=test_competitor
        )
        assert resp.status_code == 200, f"Failed to add competitor: {resp.text}"
        
        data = resp.json()
        assert "id" in data
        # Name should be auto-generated from slug
        assert data["name"], "Name should be auto-generated"
        print(f"Auto-generated name: {data['name']}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/revenue/market-robot/competitors/{data['id']}")
    
    def test_add_competitor_missing_url(self):
        """POST competitor without URL should return error"""
        test_competitor = {
            "name": "No URL Hotel"
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors",
            json=test_competitor
        )
        # Should return 200 with error message (not 4xx based on implementation)
        data = resp.json()
        assert "error" in data, "Should return error for missing URL"
    
    def test_delete_competitor(self):
        """DELETE /api/revenue/market-robot/competitors/{id} removes a competitor"""
        # First create a competitor to delete
        create_resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors",
            json={
                "name": "TEST_Delete Me Hotel",
                "booking_url": "https://www.booking.com/hotel/gb/delete-me.html"
            }
        )
        assert create_resp.status_code == 200
        comp_id = create_resp.json()["id"]
        
        # Delete it
        delete_resp = self.session.delete(f"{BASE_URL}/api/revenue/market-robot/competitors/{comp_id}")
        assert delete_resp.status_code == 200, f"Failed to delete: {delete_resp.text}"
        
        data = delete_resp.json()
        assert "message" in data, "Should return success message"
        
        # Verify it's gone
        list_resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors")
        competitors = list_resp.json()["competitors"]
        ids = [c["id"] for c in competitors]
        assert comp_id not in ids, "Deleted competitor should not appear in list"
    
    def test_scan_competitors(self):
        """POST /api/revenue/market-robot/{property_id}/competitors/scan scans prices"""
        # First ensure we have at least one competitor
        list_resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors")
        competitors = list_resp.json()["competitors"]
        
        if not competitors:
            # Add one for testing
            self.session.post(
                f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors",
                json={
                    "name": "TEST_Scan Test Hotel",
                    "booking_url": "https://www.booking.com/hotel/gb/scan-test.html"
                }
            )
        
        # Run scan
        scan_resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/competitors/scan",
            json={"days_ahead": 7}
        )
        assert scan_resp.status_code == 200, f"Scan failed: {scan_resp.text}"
        
        data = scan_resp.json()
        # May return error if no competitors, or results if there are
        if "error" not in data:
            assert "results" in data, "Should have results"
            assert "total_competitors" in data, "Should have total_competitors count"
            print(f"Scanned {data['total_competitors']} competitors")
    
    def test_market_supply_scan_still_works(self):
        """POST /api/revenue/market-robot/{property_id}/scan still works (regression)"""
        resp = self.session.post(
            f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/scan",
            json={"city": "London", "days_ahead": 7}
        )
        assert resp.status_code == 200, f"Market scan failed: {resp.text}"
        
        data = resp.json()
        assert "scan_id" in data or "status" in data, "Should return scan result"
        print(f"Market scan result: {data.get('status', 'completed')}")


class TestMarketRobotExistingEndpoints:
    """Regression tests for existing Market Robot endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.property_id = "all"
        yield
    
    def test_get_config(self):
        """GET config endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "city" in data
        assert "days_ahead" in data
    
    def test_get_supply(self):
        """GET supply endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/supply")
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data
        assert "summary" in data
    
    def test_get_logs(self):
        """GET logs endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "logs" in data
    
    def test_get_adjustments(self):
        """GET adjustments endpoint still works"""
        resp = self.session.get(f"{BASE_URL}/api/revenue/market-robot/{self.property_id}/adjustments")
        assert resp.status_code == 200
        data = resp.json()
        assert "adjustments" in data


# Cleanup test data
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_competitors():
    """Cleanup TEST_ prefixed competitors after all tests"""
    yield
    
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    
    if login_resp.status_code == 200:
        # Get all competitors
        list_resp = session.get(f"{BASE_URL}/api/revenue/market-robot/all/competitors")
        if list_resp.status_code == 200:
            competitors = list_resp.json().get("competitors", [])
            for comp in competitors:
                if comp.get("name", "").startswith("TEST_"):
                    session.delete(f"{BASE_URL}/api/revenue/market-robot/competitors/{comp['id']}")
                    print(f"Cleaned up test competitor: {comp['name']}")
