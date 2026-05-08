"""
Test Suite for Iteration 73 - Guest Journey Bug Fix & QR Code Feature
Tests:
1. Bug fix: property_id='all' support for registrations and satisfaction checks
2. QR code generation feature (frontend)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://review-hub-108.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Test data
TEST_PROPERTY_ID = "aldgate-flats"


class TestGuestJourneyBugFix:
    """Tests for the 'All Branches' bug fix - property_id='all' support"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get auth token
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                self.auth_token = token
        yield
        self.session.close()

    # ==================== BUG FIX: property_id='all' TESTS ====================
    
    def test_get_registrations_all_properties(self):
        """Test GET /api/guest-journey/registrations/all - returns all registrations across properties"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/all")
        print(f"Get all registrations response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Should return registrations (we know there are 13 from previous tests)
        print(f"✓ GET /api/guest-journey/registrations/all returned {len(data)} registrations")
        
        # Verify structure of returned data
        if len(data) > 0:
            reg = data[0]
            assert "id" in reg
            assert "booking_id" in reg
            assert "property_id" in reg
            assert "guest_name" in reg
            assert "token" in reg
            assert "status" in reg
            print(f"✓ Registration structure validated: {reg.get('guest_name')} - {reg.get('status')}")

    def test_get_registrations_all_vs_specific_property(self):
        """Test that 'all' returns more or equal registrations than specific property"""
        # Get all registrations
        all_resp = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/all")
        assert all_resp.status_code == 200
        all_registrations = all_resp.json()
        
        # Get specific property registrations
        specific_resp = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/{TEST_PROPERTY_ID}")
        assert specific_resp.status_code == 200
        specific_registrations = specific_resp.json()
        
        # 'all' should return >= specific property count
        assert len(all_registrations) >= len(specific_registrations), \
            f"'all' ({len(all_registrations)}) should return >= specific property ({len(specific_registrations)})"
        
        print(f"✓ 'all' returns {len(all_registrations)} registrations, '{TEST_PROPERTY_ID}' returns {len(specific_registrations)}")

    def test_get_satisfaction_checks_all_properties(self):
        """Test GET /api/guest-journey/satisfaction-checks/all - returns all satisfaction checks across properties"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/satisfaction-checks/all")
        print(f"Get all satisfaction checks response: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        print(f"✓ GET /api/guest-journey/satisfaction-checks/all returned {len(data)} checks")
        
        # Verify structure if data exists
        if len(data) > 0:
            check = data[0]
            assert "id" in check
            assert "token" in check
            assert "property_id" in check
            assert "guest_name" in check
            assert "status" in check
            print(f"✓ Satisfaction check structure validated: {check.get('guest_name')} - {check.get('status')}")

    def test_get_satisfaction_checks_all_vs_specific_property(self):
        """Test that 'all' returns more or equal satisfaction checks than specific property"""
        # Get all satisfaction checks
        all_resp = self.session.get(f"{BASE_URL}/api/guest-journey/satisfaction-checks/all")
        assert all_resp.status_code == 200
        all_checks = all_resp.json()
        
        # Get specific property satisfaction checks
        specific_resp = self.session.get(f"{BASE_URL}/api/guest-journey/satisfaction-checks/{TEST_PROPERTY_ID}")
        assert specific_resp.status_code == 200
        specific_checks = specific_resp.json()
        
        # 'all' should return >= specific property count
        assert len(all_checks) >= len(specific_checks), \
            f"'all' ({len(all_checks)}) should return >= specific property ({len(specific_checks)})"
        
        print(f"✓ 'all' returns {len(all_checks)} checks, '{TEST_PROPERTY_ID}' returns {len(specific_checks)}")

    # ==================== REGISTRATION TOKEN TESTS (for QR code) ====================
    
    def test_registration_has_token_for_qr(self):
        """Test that registrations have tokens that can be used for QR codes"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/all")
        assert response.status_code == 200
        registrations = response.json()
        
        if len(registrations) > 0:
            reg = registrations[0]
            assert "token" in reg, "Registration should have a token"
            assert reg["token"], "Token should not be empty"
            assert len(reg["token"]) > 20, "Token should be a secure random string"
            
            # Verify the registration URL can be constructed
            expected_url = f"{BASE_URL}/register/{reg['token']}"
            print(f"✓ Registration token exists: {reg['token'][:20]}...")
            print(f"✓ QR code URL would be: {expected_url[:50]}...")
        else:
            pytest.skip("No registrations found to test")

    def test_public_registration_page_accessible(self):
        """Test that public registration page is accessible with valid token"""
        # Get a registration token
        auth_resp = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/all")
        assert auth_resp.status_code == 200
        registrations = auth_resp.json()
        
        if len(registrations) > 0:
            token = registrations[0]["token"]
            
            # Test public endpoint (no auth)
            public_session = requests.Session()
            response = public_session.get(f"{BASE_URL}/api/guest-journey/registration/{token}")
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "hotel_name" in data
            assert "booking" in data
            
            print(f"✓ Public registration page accessible for token: {token[:20]}...")
            public_session.close()
        else:
            pytest.skip("No registrations found to test")


class TestGuestJourneyStats:
    """Tests for stats calculation with 'all' property support"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()

    def test_stats_calculation_from_all_registrations(self):
        """Test that stats can be calculated from 'all' registrations"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/all")
        assert response.status_code == 200
        registrations = response.json()
        
        # Calculate stats like frontend does
        total = len(registrations)
        completed = len([r for r in registrations if r.get("status") == "completed"])
        pending = len([r for r in registrations if r.get("status") == "pending"])
        id_uploaded = len([r for r in registrations if r.get("id_uploaded")])
        
        print(f"✓ Stats from 'all' registrations:")
        print(f"  - Total Sent: {total}")
        print(f"  - Completed: {completed}")
        print(f"  - Pending: {pending}")
        print(f"  - IDs Uploaded: {id_uploaded}")
        
        # Verify counts make sense
        assert total >= 0
        assert completed + pending <= total
        assert id_uploaded <= total


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
