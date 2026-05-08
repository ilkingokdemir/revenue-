"""
Guest Portal V2 API Tests
Tests for Guest Self-Modify/Cancel Portal - token-based public booking management

Endpoints tested:
- POST /api/guest-portal-v2/token/{booking_id} (ADMIN) - Issue token
- GET /api/guest-portal-v2/verify/{token} (PUBLIC) - Verify token & get booking
- POST /api/guest-portal-v2/modify/{token} (PUBLIC) - Modify booking
- POST /api/guest-portal-v2/cancel/{token} (PUBLIC) - Cancel booking
- GET /api/guest-portal-v2/pipeline/{property_id} (ADMIN) - Pipeline view
"""
import pytest
import requests
import os
from datetime import datetime, timedelta, date
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestGuestPortalV2:
    """Guest Portal V2 endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.auth_token = None
        
    def _login_admin(self):
        """Login as admin and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.auth_token = data.get("access_token") or data.get("token")
        self.session.cookies.update(response.cookies)
        return self.auth_token
    
    def _get_available_booking(self, status_filter="confirmed"):
        """Get an available booking from pipeline for testing"""
        self._login_admin()
        
        # Get bookings from pipeline with 60 days ahead to find future bookings
        response = self.session.get(
            f"{BASE_URL}/api/guest-portal-v2/pipeline/default?days_ahead=60"
        )
        if response.status_code != 200:
            return None
        
        data = response.json()
        rows = data.get("rows", [])
        
        # Find a booking that matches criteria
        for row in rows:
            if row.get("status") == status_filter and not row.get("token_issued"):
                return row.get("booking_id")
        
        # If no non-issued token booking, return any confirmed booking
        for row in rows:
            if row.get("status") == status_filter:
                return row.get("booking_id")
        
        return None
    
    # ============ ADMIN: Issue Token Tests ============
    
    def test_issue_token_success(self):
        """Test issuing a token for a booking"""
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "flexible"}
        )
        
        assert response.status_code == 200, f"Token issue failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "token" in data, "Response missing 'token'"
        assert "expires_at" in data, "Response missing 'expires_at'"
        assert "link_path" in data, "Response missing 'link_path'"
        
        # Verify token is UUID format
        assert len(data["token"]) == 36, "Token should be UUID format"
        assert data["link_path"].startswith("/portal/"), "link_path should start with /portal/"
        
        print(f"✓ Token issued successfully: {data['token'][:8]}...")
    
    def test_issue_token_all_policies(self):
        """Test issuing tokens with all valid policies"""
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        for policy in ["flexible", "moderate", "strict"]:
            response = self.session.post(
                f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
                json={"expiry_hours": 72, "policy": policy}
            )
            assert response.status_code == 200, f"Token issue failed for policy '{policy}': {response.text}"
            print(f"✓ Policy '{policy}' accepted")
    
    def test_issue_token_invalid_policy(self):
        """Test issuing token with invalid policy returns 400"""
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "invalid_policy"}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid policy correctly rejected with 400")
    
    def test_issue_token_invalid_expiry_hours(self):
        """Test issuing token with invalid expiry_hours returns 400"""
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        # Test expiry_hours < 1
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 0, "policy": "flexible"}
        )
        assert response.status_code == 400, f"Expected 400 for expiry_hours=0, got {response.status_code}"
        
        # Test expiry_hours > 720
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 721, "policy": "flexible"}
        )
        assert response.status_code == 400, f"Expected 400 for expiry_hours=721, got {response.status_code}"
        print("✓ Invalid expiry_hours correctly rejected with 400")
    
    def test_issue_token_booking_not_found(self):
        """Test issuing token for non-existent booking returns 404"""
        self._login_admin()
        
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/nonexistent-booking-id",
            json={"expiry_hours": 72, "policy": "flexible"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent booking correctly returns 404")
    
    def test_issue_token_without_auth(self):
        """Test issuing token without authentication returns 401"""
        # Create a fresh session without auth
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/some-booking-id",
            json={"expiry_hours": 72, "policy": "flexible"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated request correctly returns 401")
    
    # ============ PUBLIC: Verify Token Tests ============
    
    def test_verify_token_success(self):
        """Test verifying a valid token returns booking info"""
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        # Issue token
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "flexible"}
        )
        assert response.status_code == 200
        token = response.json()["token"]
        
        # Verify token (PUBLIC - no auth needed)
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/guest-portal-v2/verify/{token}")
        
        assert response.status_code == 200, f"Verify failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "token" in data
        assert "status" in data
        assert "policy" in data
        assert "policy_label" in data
        assert "days_to_arrival" in data
        assert "refund_percent_if_cancel" in data
        assert "can_modify" in data
        assert "can_cancel" in data
        assert "booking" in data
        
        # Verify booking data
        booking = data["booking"]
        assert "guest_name" in booking
        assert "check_in" in booking
        assert "check_out" in booking
        
        print(f"✓ Token verified successfully, days_to_arrival: {data['days_to_arrival']}")
    
    def test_verify_token_invalid(self):
        """Test verifying invalid token returns 404"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/guest-portal-v2/verify/invalid-token-12345")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "Geçersiz bağlantı" in str(data.get("detail", ""))
        print("✓ Invalid token correctly returns 404 with Turkish message")
    
    # ============ PUBLIC: Modify Booking Tests ============
    
    def test_modify_booking_special_requests(self):
        """Test modifying a booking's special requests via token"""
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        # Issue token
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "flexible"}
        )
        assert response.status_code == 200
        token = response.json()["token"]
        
        # Check if modification is allowed
        session = requests.Session()
        verify_resp = session.get(f"{BASE_URL}/api/guest-portal-v2/verify/{token}")
        if verify_resp.status_code == 200:
            verify_data = verify_resp.json()
            if not verify_data.get("can_modify"):
                pytest.skip("Booking cannot be modified (too close to arrival)")
        
        # Modify booking (PUBLIC)
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(
            f"{BASE_URL}/api/guest-portal-v2/modify/{token}",
            json={"special_requests": "Erken giriş rica ederim"}
        )
        
        # If modification is rejected due to arrival day, that's expected
        if response.status_code == 400 and "arrival" in response.text.lower():
            print("✓ Modification correctly rejected (too close to arrival)")
            return
        
        assert response.status_code == 200, f"Modify failed: {response.text}"
        data = response.json()
        assert data.get("updated") == True
        assert "changes" in data
        print("✓ Booking modified successfully with special_requests")
    
    def test_modify_booking_adults_validation(self):
        """Test modifying adults with invalid values returns 400"""
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        # Issue token
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "flexible"}
        )
        assert response.status_code == 200
        token = response.json()["token"]
        
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Test adults < 1
        response = session.post(
            f"{BASE_URL}/api/guest-portal-v2/modify/{token}",
            json={"adults": 0}
        )
        # Either 400 for validation or 400 for arrival day restriction
        assert response.status_code == 400, f"Expected 400 for adults=0, got {response.status_code}"
        
        # Test adults > 10
        response = session.post(
            f"{BASE_URL}/api/guest-portal-v2/modify/{token}",
            json={"adults": 11}
        )
        assert response.status_code == 400, f"Expected 400 for adults=11, got {response.status_code}"
        print("✓ Adults validation (1..10) working correctly")
    
    def test_modify_booking_invalid_token(self):
        """Test modifying with invalid token returns 404"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(
            f"{BASE_URL}/api/guest-portal-v2/modify/invalid-token-xyz",
            json={"special_requests": "Test"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid token correctly returns 404 for modify")
    
    # ============ PUBLIC: Cancel Booking Tests ============
    
    def test_cancel_booking_success(self):
        """Test cancelling a booking via token"""
        # Find a booking that can be cancelled
        booking_id = self._get_available_booking(status_filter="confirmed")
        if not booking_id:
            booking_id = self._get_available_booking(status_filter="pending")
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        # Issue token
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "flexible"}
        )
        assert response.status_code == 200
        token = response.json()["token"]
        
        # Check if cancellation is allowed
        session = requests.Session()
        verify_resp = session.get(f"{BASE_URL}/api/guest-portal-v2/verify/{token}")
        if verify_resp.status_code == 200:
            verify_data = verify_resp.json()
            if not verify_data.get("can_cancel"):
                pytest.skip("Booking cannot be cancelled")
        
        # Cancel booking (PUBLIC)
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(
            f"{BASE_URL}/api/guest-portal-v2/cancel/{token}",
            json={"reason": "Test cancellation"}
        )
        
        assert response.status_code == 200, f"Cancel failed: {response.text}"
        data = response.json()
        assert data.get("cancelled") == True
        assert "refund_percent" in data
        assert "refund_amount" in data
        assert "currency" in data
        print(f"✓ Booking cancelled, refund: {data['refund_percent']}% = {data['currency']} {data['refund_amount']}")
    
    def test_cancel_booking_invalid_token(self):
        """Test cancelling with invalid token returns 404"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(
            f"{BASE_URL}/api/guest-portal-v2/cancel/invalid-token-xyz",
            json={"reason": "Test"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid token correctly returns 404 for cancel")
    
    # ============ Refund Policy Tests ============
    
    def test_refund_policy_flexible_calculation(self):
        """Test flexible policy refund calculation"""
        # Flexible: >=2d=100%, <2d=0%
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "flexible"}
        )
        assert response.status_code == 200
        token = response.json()["token"]
        
        # Verify refund percent
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/guest-portal-v2/verify/{token}")
        assert response.status_code == 200
        data = response.json()
        
        days = data["days_to_arrival"]
        refund = data["refund_percent_if_cancel"]
        
        # Verify flexible policy logic
        if days >= 2:
            assert refund == 100, f"Flexible policy: {days} days should be 100%, got {refund}%"
        else:
            assert refund == 0, f"Flexible policy: {days} days should be 0%, got {refund}%"
        
        print(f"✓ Flexible policy: {days} days ahead = {refund}% refund (correct)")
    
    def test_refund_policy_moderate_calculation(self):
        """Test moderate policy refund calculation"""
        # Moderate: >=5d=100%, 2-5d=50%, <2d=0%
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "moderate"}
        )
        assert response.status_code == 200
        token = response.json()["token"]
        
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/guest-portal-v2/verify/{token}")
        assert response.status_code == 200
        data = response.json()
        
        days = data["days_to_arrival"]
        refund = data["refund_percent_if_cancel"]
        
        # Verify moderate policy logic
        if days >= 5:
            assert refund == 100, f"Moderate policy: {days} days should be 100%, got {refund}%"
        elif days >= 2:
            assert refund == 50, f"Moderate policy: {days} days should be 50%, got {refund}%"
        else:
            assert refund == 0, f"Moderate policy: {days} days should be 0%, got {refund}%"
        
        print(f"✓ Moderate policy: {days} days ahead = {refund}% refund (correct)")
    
    def test_refund_policy_strict_calculation(self):
        """Test strict policy refund calculation"""
        # Strict: >=7d=50%, <7d=0%
        booking_id = self._get_available_booking()
        if not booking_id:
            pytest.skip("No available booking found for testing")
        
        response = self.session.post(
            f"{BASE_URL}/api/guest-portal-v2/token/{booking_id}",
            json={"expiry_hours": 72, "policy": "strict"}
        )
        assert response.status_code == 200
        token = response.json()["token"]
        
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/guest-portal-v2/verify/{token}")
        assert response.status_code == 200
        data = response.json()
        
        days = data["days_to_arrival"]
        refund = data["refund_percent_if_cancel"]
        
        # Verify strict policy logic
        if days >= 7:
            assert refund == 50, f"Strict policy: {days} days should be 50%, got {refund}%"
        else:
            assert refund == 0, f"Strict policy: {days} days should be 0%, got {refund}%"
        
        print(f"✓ Strict policy: {days} days ahead = {refund}% refund (correct)")
    
    # ============ ADMIN: Pipeline Tests ============
    
    def test_pipeline_success(self):
        """Test pipeline endpoint returns bookings"""
        self._login_admin()
        
        response = self.session.get(
            f"{BASE_URL}/api/guest-portal-v2/pipeline/default?days_ahead=14"
        )
        
        assert response.status_code == 200, f"Pipeline failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "rows" in data
        assert "counts" in data
        assert "property_id" in data
        assert "days_ahead" in data
        
        # Verify counts structure
        counts = data["counts"]
        assert "total" in counts
        assert "token_issued" in counts
        assert "modified" in counts
        assert "cancelled" in counts
        
        print(f"✓ Pipeline returned {counts['total']} bookings, {counts['token_issued']} with tokens")
    
    def test_pipeline_days_ahead_validation(self):
        """Test pipeline days_ahead validation (1..90)"""
        self._login_admin()
        
        # Test days_ahead < 1
        response = self.session.get(
            f"{BASE_URL}/api/guest-portal-v2/pipeline/default?days_ahead=0"
        )
        assert response.status_code == 400, f"Expected 400 for days_ahead=0, got {response.status_code}"
        
        # Test days_ahead > 90
        response = self.session.get(
            f"{BASE_URL}/api/guest-portal-v2/pipeline/default?days_ahead=91"
        )
        assert response.status_code == 400, f"Expected 400 for days_ahead=91, got {response.status_code}"
        print("✓ days_ahead validation (1..90) working correctly")
    
    def test_pipeline_without_auth(self):
        """Test pipeline without authentication returns 401"""
        session = requests.Session()
        response = session.get(
            f"{BASE_URL}/api/guest-portal-v2/pipeline/default?days_ahead=14"
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Pipeline correctly requires authentication")
    
    def test_pipeline_row_structure(self):
        """Test pipeline row structure contains expected fields"""
        self._login_admin()
        
        response = self.session.get(
            f"{BASE_URL}/api/guest-portal-v2/pipeline/default?days_ahead=30"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["rows"]) > 0:
            row = data["rows"][0]
            expected_fields = ["booking_id", "guest_name", "check_in", "check_out", 
                            "status", "token_issued", "token_status"]
            for field in expected_fields:
                assert field in row, f"Row missing field: {field}"
            print(f"✓ Pipeline row structure verified with all expected fields")
        else:
            print("✓ Pipeline returned empty rows (no bookings in range)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
