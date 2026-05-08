"""
Iteration 176 - Group Requests & Allotments Panel Tests
Tests for B2B/corporate/wedding group booking request admin panel

Endpoints tested:
- POST /api/group-booking/request (PUBLIC) - submit group booking request
- GET /api/group-booking/requests/{property_id} (admin auth) - list requests
- PUT /api/group-booking/{booking_id} (admin auth) - update status/notes/price
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com')

class TestGroupBookingRequests:
    """Group Booking Request endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("token")
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        self.property_id = "aldgate-flats"
    
    def test_01_submit_group_request_public(self):
        """PUBLIC: Submit a group booking request"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "property_id": self.property_id,
            "contact_name": f"TEST_Contact_{unique_id}",
            "contact_email": f"test_{unique_id}@corp.com",
            "contact_phone": "+44123456789",
            "company_name": f"TEST_Corp_{unique_id}",
            "event_type": "corporate",
            "check_in": "2026-04-01",
            "check_out": "2026-04-05",
            "total_rooms": 8,
            "total_guests": 16,
            "room_preferences": "Standard rooms",
            "special_requirements": "Meeting room needed",
            "budget_range": "£4000-£6000"
        }
        
        response = self.session.post(f"{BASE_URL}/api/group-booking/request", json=payload)
        assert response.status_code == 200, f"Submit failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "submitted"
        assert "id" in data
        assert "message" in data
        
        # Store for later tests
        self.__class__.created_request_id = data["id"]
        self.__class__.created_contact_name = payload["contact_name"]
        print(f"✓ Created group request: {data['id']}")
    
    def test_02_list_group_requests_admin(self):
        """ADMIN: List group booking requests for property"""
        response = self.session.get(
            f"{BASE_URL}/api/group-booking/requests/{self.property_id}",
            headers=self.auth_headers
        )
        assert response.status_code == 200, f"List failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of requests"
        assert len(data) > 0, "Expected at least one request"
        
        # Verify structure of first item
        first = data[0]
        required_fields = ["id", "property_id", "contact_name", "contact_email", 
                          "check_in", "check_out", "total_rooms", "total_guests",
                          "status", "created_at"]
        for field in required_fields:
            assert field in first, f"Missing field: {field}"
        
        # Verify sorted by created_at desc (newest first)
        if len(data) > 1:
            first_date = data[0].get("created_at", "")
            second_date = data[1].get("created_at", "")
            assert first_date >= second_date, "Expected sorted by created_at desc"
        
        print(f"✓ Listed {len(data)} group requests")
    
    def test_03_list_requires_auth(self):
        """List endpoint requires authentication"""
        # Use fresh session without auth
        fresh_session = requests.Session()
        response = fresh_session.get(
            f"{BASE_URL}/api/group-booking/requests/{self.property_id}"
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ List endpoint requires auth")
    
    def test_04_update_status_to_quoted(self):
        """ADMIN: Update request status to quoted with price"""
        request_id = getattr(self.__class__, 'created_request_id', None)
        if not request_id:
            pytest.skip("No request created in previous test")
        
        payload = {
            "status": "quoted",
            "admin_notes": "Sent quote via email - TEST",
            "quoted_price": 5500
        }
        
        response = self.session.put(
            f"{BASE_URL}/api/group-booking/{request_id}",
            headers=self.auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "quoted"
        assert data.get("admin_notes") == "Sent quote via email - TEST"
        assert data.get("quoted_price") == 5500
        print(f"✓ Updated request to quoted with price £5500")
    
    def test_05_update_status_to_confirmed(self):
        """ADMIN: Update request status to confirmed"""
        request_id = getattr(self.__class__, 'created_request_id', None)
        if not request_id:
            pytest.skip("No request created in previous test")
        
        payload = {
            "status": "confirmed",
            "admin_notes": "Confirmed and rooms blocked - TEST"
        }
        
        response = self.session.put(
            f"{BASE_URL}/api/group-booking/{request_id}",
            headers=self.auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "confirmed"
        assert "Confirmed" in data.get("admin_notes", "")
        print("✓ Updated request to confirmed")
    
    def test_06_update_status_to_cancelled(self):
        """ADMIN: Update request status to cancelled"""
        request_id = getattr(self.__class__, 'created_request_id', None)
        if not request_id:
            pytest.skip("No request created in previous test")
        
        payload = {
            "status": "cancelled",
            "admin_notes": "Cancelled by client - TEST"
        }
        
        response = self.session.put(
            f"{BASE_URL}/api/group-booking/{request_id}",
            headers=self.auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "cancelled"
        print("✓ Updated request to cancelled")
    
    def test_07_update_requires_auth(self):
        """Update endpoint requires authentication"""
        request_id = getattr(self.__class__, 'created_request_id', None)
        if not request_id:
            pytest.skip("No request created in previous test")
        
        # Use fresh session without auth
        import requests as req
        fresh_session = req.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        response = fresh_session.put(
            f"{BASE_URL}/api/group-booking/{request_id}",
            json={"status": "pending"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ Update endpoint requires auth")
    
    def test_08_verify_request_persisted(self):
        """Verify the created request is in the list"""
        contact_name = getattr(self.__class__, 'created_contact_name', None)
        if not contact_name:
            pytest.skip("No request created in previous test")
        
        response = self.session.get(
            f"{BASE_URL}/api/group-booking/requests/{self.property_id}",
            headers=self.auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        found = any(r.get("contact_name") == contact_name for r in data)
        assert found, f"Created request not found in list"
        print(f"✓ Verified request {contact_name} persisted in database")


class TestRegressionSmoke:
    """Regression smoke tests for existing features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("token")
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_admin_login_works(self):
        """Admin login still works"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "admin"
        assert "token" in data
        print("✓ Admin login works")
    
    def test_concierge_sessions_endpoint(self):
        """Concierge inbox endpoint still works (iter 175)"""
        response = self.session.get(
            f"{BASE_URL}/api/concierge/admin/aldgate-flats/sessions",
            headers=self.auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data or isinstance(data, list)
        print("✓ Concierge inbox endpoint works")
    
    def test_rm_lab_endpoint(self):
        """RM Lab endpoint still works (iter 172)"""
        response = self.session.get(
            f"{BASE_URL}/api/rm-lab/aldgate-flats/accuracy",
            headers=self.auth_headers
        )
        # May return 200 or 404 if no data, but should not error
        assert response.status_code in [200, 404]
        print("✓ RM Lab endpoint accessible")
    
    def test_group_bookings_master_folio_different(self):
        """Verify GroupBookingsPanel (master-folio) is different from GroupRequestsPanel"""
        # This tests that the existing group-bookings endpoint still works
        # (different from group-booking/requests)
        response = self.session.get(
            f"{BASE_URL}/api/group-blocks/aldgate-flats",
            headers=self.auth_headers
        )
        # Should return 200 (may be empty list)
        assert response.status_code == 200
        print("✓ Group blocks (master-folio) endpoint works - different from group requests")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
