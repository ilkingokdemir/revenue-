"""
Iteration 74 - Guest Journey Share Link Feature Tests
Tests the new POST /api/guest-journey/share-link/{registration_id} endpoint
for sharing registration links via email, SMS, and WhatsApp channels.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com')

class TestShareLinkEndpoint:
    """Tests for the new share-link endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get a test registration ID
        regs_resp = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/all")
        assert regs_resp.status_code == 200
        regs = regs_resp.json()
        assert len(regs) > 0, "No registrations found for testing"
        self.test_registration = regs[0]
        self.test_registration_id = self.test_registration["id"]
        
    def test_share_link_email_channel(self):
        """Test sharing registration link via email channel"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/share-link/{self.test_registration_id}",
            json={"channel": "email"}
        )
        assert response.status_code == 200, f"Share link email failed: {response.text}"
        data = response.json()
        assert data.get("channel") == "email"
        # Email should be sent (or skipped if no Resend key)
        assert data.get("status") in ["sent", "skipped"], f"Unexpected status: {data}"
        print(f"✓ Email share: {data}")
        
    def test_share_link_sms_channel(self):
        """Test sharing registration link via SMS channel (expected to be skipped without Twilio config)"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/share-link/{self.test_registration_id}",
            json={"channel": "sms"}
        )
        assert response.status_code == 200, f"Share link SMS failed: {response.text}"
        data = response.json()
        assert data.get("channel") == "sms"
        # SMS should be skipped without Twilio configuration
        assert data.get("status") in ["sent", "skipped"], f"Unexpected status: {data}"
        if data.get("status") == "skipped":
            assert "not configured" in data.get("reason", "").lower() or "no phone" in data.get("reason", "").lower()
        print(f"✓ SMS share: {data}")
        
    def test_share_link_whatsapp_channel(self):
        """Test sharing registration link via WhatsApp channel (expected to be skipped/failed without valid config)"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/share-link/{self.test_registration_id}",
            json={"channel": "whatsapp"}
        )
        assert response.status_code == 200, f"Share link WhatsApp failed: {response.text}"
        data = response.json()
        assert data.get("channel") == "whatsapp"
        # WhatsApp should be skipped without configuration, or failed with invalid token
        assert data.get("status") in ["sent", "skipped", "failed"], f"Unexpected status: {data}"
        if data.get("status") == "skipped":
            assert "not configured" in data.get("reason", "").lower() or "no phone" in data.get("reason", "").lower()
        elif data.get("status") == "failed":
            # Expected when WhatsApp is configured but with invalid credentials
            assert "reason" in data
        print(f"✓ WhatsApp share: {data}")
        
    def test_share_link_unknown_channel(self):
        """Test sharing with unknown channel returns error"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/share-link/{self.test_registration_id}",
            json={"channel": "unknown_channel"}
        )
        assert response.status_code == 200, f"Share link unknown channel failed: {response.text}"
        data = response.json()
        assert data.get("status") == "error"
        assert "unknown" in data.get("reason", "").lower()
        print(f"✓ Unknown channel handled: {data}")
        
    def test_share_link_invalid_registration_id(self):
        """Test sharing with invalid registration ID returns 404"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/share-link/invalid-registration-id-12345",
            json={"channel": "email"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ Invalid registration ID returns 404")
        
    def test_share_link_with_custom_phone(self):
        """Test sharing with custom phone number in request"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/share-link/{self.test_registration_id}",
            json={"channel": "sms", "phone": "+447999888777"}
        )
        assert response.status_code == 200, f"Share link with custom phone failed: {response.text}"
        data = response.json()
        assert data.get("channel") == "sms"
        print(f"✓ Custom phone share: {data}")
        
    def test_share_link_with_custom_email(self):
        """Test sharing with custom email in request"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/share-link/{self.test_registration_id}",
            json={"channel": "email", "email": "custom@test.com"}
        )
        assert response.status_code == 200, f"Share link with custom email failed: {response.text}"
        data = response.json()
        assert data.get("channel") == "email"
        print(f"✓ Custom email share: {data}")
        
    def test_share_link_requires_authentication(self):
        """Test that share-link endpoint requires authentication"""
        # Create new session without auth
        unauth_session = requests.Session()
        response = unauth_session.post(
            f"{BASE_URL}/api/guest-journey/share-link/{self.test_registration_id}",
            json={"channel": "email"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Share link requires authentication")


class TestExistingGuestJourneyEndpoints:
    """Regression tests for existing Guest Journey endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
        )
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
    def test_list_registrations_all(self):
        """Test listing all registrations"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/all")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Expected at least one registration"
        # Verify registration structure
        reg = data[0]
        assert "id" in reg
        assert "token" in reg
        assert "guest_name" in reg
        assert "status" in reg
        print(f"✓ List registrations: {len(data)} registrations found")
        
    def test_list_satisfaction_checks(self):
        """Test listing satisfaction checks"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/satisfaction-checks/all")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List satisfaction checks: {len(data)} checks found")
        
    def test_public_registration_page(self):
        """Test public registration page endpoint"""
        # Get a registration token
        regs_resp = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/all")
        regs = regs_resp.json()
        test_token = regs[0]["token"]
        
        # Access public endpoint (no auth needed)
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-journey/registration/{test_token}")
        assert response.status_code == 200, f"Public registration failed: {response.text}"
        data = response.json()
        assert "status" in data
        assert "hotel_name" in data
        assert "booking" in data
        print(f"✓ Public registration page works for token: {test_token[:20]}...")
        
    def test_public_registration_invalid_token(self):
        """Test public registration with invalid token returns 404"""
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-journey/registration/invalid-token-12345")
        assert response.status_code == 404
        print("✓ Invalid registration token returns 404")


class TestPublicFeedbackEndpoint:
    """Tests for public feedback endpoint"""
    
    def test_feedback_invalid_token(self):
        """Test feedback with invalid token returns 404"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/guest-journey/feedback/invalid-feedback-token")
        assert response.status_code == 404
        print("✓ Invalid feedback token returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
