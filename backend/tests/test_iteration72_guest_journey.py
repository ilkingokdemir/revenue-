"""
Test Suite for Iteration 72 - Guest Journey Feature
Tests: Pre-arrival registration, ID upload, satisfaction checks, feedback
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://review-hub-108.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Test booking data from main agent
TEST_BOOKING_ID = "98ac6cd2-3328-4796-8eb8-aa12a82872c9"
TEST_BOOKING_REF = "BK-TEST001"
TEST_PROPERTY_ID = "aldgate-flats"
TEST_REGISTRATION_TOKEN = "Q8sKO_RH3uuAA4ACeZY11ObBd8GmDTkUyYbNJHMdudY"


class TestGuestJourneyBackend:
    """Guest Journey API Tests"""
    
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
            token = login_resp.json().get("token")  # API returns "token" not "access_token"
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                self.auth_token = token
        yield
        self.session.close()

    # ==================== REGISTRATION LINK TESTS ====================
    
    def test_send_registration_link_success(self):
        """Test POST /api/guest-journey/send-registration/{booking_id} - sends registration link"""
        response = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/{TEST_BOOKING_ID}")
        print(f"Send registration link response: {response.status_code} - {response.text[:200]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "status" in data
        assert data["status"] == "sent"
        assert "token" in data
        assert "url" in data
        assert "/register/" in data["url"]
        print(f"✓ Registration link sent successfully, token: {data['token'][:20]}...")

    def test_send_registration_link_invalid_booking(self):
        """Test POST /api/guest-journey/send-registration/{booking_id} - invalid booking returns 404"""
        response = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/invalid-booking-id")
        print(f"Invalid booking response: {response.status_code}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid booking correctly returns 404")

    # ==================== GET REGISTRATION (PUBLIC) TESTS ====================
    
    def test_get_registration_form_success(self):
        """Test GET /api/guest-journey/registration/{token} - public endpoint returns registration form data"""
        # First send a registration link to get a valid token
        send_resp = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/{TEST_BOOKING_ID}")
        if send_resp.status_code == 200:
            token = send_resp.json().get("token")
        else:
            token = TEST_REGISTRATION_TOKEN
        
        # Now test the public GET endpoint (no auth needed)
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-journey/registration/{token}")
        print(f"Get registration form response: {response.status_code} - {response.text[:300]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate response structure
        assert "status" in data
        assert "token" in data
        assert "hotel_name" in data
        assert "booking" in data
        assert "form_data" in data
        assert "id_uploaded" in data
        assert "terms_accepted" in data
        assert "policies" in data
        
        # Validate booking data
        booking = data["booking"]
        assert "booking_ref" in booking
        assert "guest_name" in booking
        assert "guest_email" in booking
        assert "check_in" in booking
        assert "check_out" in booking
        
        print(f"✓ Registration form data retrieved: hotel={data['hotel_name']}, status={data['status']}")
        public_session.close()

    def test_get_registration_form_invalid_token(self):
        """Test GET /api/guest-journey/registration/{token} - invalid token returns 404"""
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-journey/registration/invalid-token-xyz")
        print(f"Invalid token response: {response.status_code}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid token correctly returns 404")
        public_session.close()

    # ==================== SUBMIT REGISTRATION (PUBLIC) TESTS ====================
    
    def test_submit_registration_success(self):
        """Test POST /api/guest-journey/registration/{token} - public endpoint submits registration form"""
        # First send a registration link to get a valid token
        send_resp = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/{TEST_BOOKING_ID}")
        if send_resp.status_code == 200:
            token = send_resp.json().get("token")
        else:
            token = TEST_REGISTRATION_TOKEN
        
        # Submit registration form (public endpoint)
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        form_data = {
            "form_data": {
                "full_name": "Test Guest",
                "email": "testguest@example.com",
                "phone": "+44 7123 456789",
                "nationality": "British",
                "date_of_birth": "1990-01-15",
                "address": "123 Test Street, London",
                "passport_number": "AB123456",
                "emergency_contact": "Jane Doe +44 7987 654321",
                "special_requests": "Early check-in if possible"
            },
            "terms_accepted": True,
            "signature": "Test Guest"
        }
        
        response = public_session.post(f"{BASE_URL}/api/guest-journey/registration/{token}", json=form_data)
        print(f"Submit registration response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "status" in data
        assert data["status"] == "submitted"
        assert "completed" in data
        assert data["completed"] == True
        
        print("✓ Registration form submitted successfully")
        public_session.close()

    def test_submit_registration_without_terms(self):
        """Test POST /api/guest-journey/registration/{token} - submission without terms stays pending"""
        # First send a registration link to get a valid token
        send_resp = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/{TEST_BOOKING_ID}")
        if send_resp.status_code == 200:
            token = send_resp.json().get("token")
        else:
            pytest.skip("Could not get registration token")
        
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        form_data = {
            "form_data": {
                "full_name": "Test Guest",
                "nationality": "British"
            },
            "terms_accepted": False,
            "signature": ""
        }
        
        response = public_session.post(f"{BASE_URL}/api/guest-journey/registration/{token}", json=form_data)
        print(f"Submit without terms response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["completed"] == False
        
        print("✓ Registration without terms correctly stays pending")
        public_session.close()

    # ==================== ID UPLOAD (PUBLIC) TESTS ====================
    
    def test_upload_id_success(self):
        """Test POST /api/guest-journey/upload-id/{token} - public endpoint uploads guest ID document"""
        # First send a registration link to get a valid token
        send_resp = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/{TEST_BOOKING_ID}")
        if send_resp.status_code == 200:
            token = send_resp.json().get("token")
        else:
            token = TEST_REGISTRATION_TOKEN
        
        # Upload a test file (public endpoint)
        public_session = requests.Session()
        
        # Create a simple test image file
        test_file_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('test_id.png', test_file_content, 'image/png')}
        response = public_session.post(f"{BASE_URL}/api/guest-journey/upload-id/{token}", files=files)
        print(f"Upload ID response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "status" in data
        assert data["status"] == "uploaded"
        assert "filename" in data
        
        print(f"✓ ID document uploaded successfully: {data['filename']}")
        public_session.close()

    def test_upload_id_invalid_token(self):
        """Test POST /api/guest-journey/upload-id/{token} - invalid token returns 404"""
        public_session = requests.Session()
        test_file_content = b'test file content'
        files = {'file': ('test.txt', test_file_content, 'text/plain')}
        
        response = public_session.post(f"{BASE_URL}/api/guest-journey/upload-id/invalid-token", files=files)
        print(f"Upload with invalid token response: {response.status_code}")
        
        assert response.status_code == 404
        print("✓ Upload with invalid token correctly returns 404")
        public_session.close()

    # ==================== RECEPTION UPLOAD ID TESTS ====================
    
    def test_reception_upload_id_success(self):
        """Test POST /api/guest-journey/reception-upload-id/{booking_id} - reception uploads guest ID"""
        test_file_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('reception_id.png', test_file_content, 'image/png')}
        
        # Create new request without Content-Type header (let requests set it for multipart)
        response = requests.post(
            f"{BASE_URL}/api/guest-journey/reception-upload-id/{TEST_BOOKING_ID}",
            files=files,
            headers={"Authorization": f"Bearer {self.auth_token}"} if hasattr(self, 'auth_token') else {}
        )
        print(f"Reception upload ID response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["status"] == "uploaded"
        
        print("✓ Reception ID upload successful")

    def test_reception_upload_id_invalid_booking(self):
        """Test POST /api/guest-journey/reception-upload-id/{booking_id} - invalid booking returns 404"""
        test_file_content = b'test content'
        files = {'file': ('test.txt', test_file_content, 'text/plain')}
        
        response = requests.post(
            f"{BASE_URL}/api/guest-journey/reception-upload-id/invalid-booking-id",
            files=files,
            headers={"Authorization": f"Bearer {self.auth_token}"} if hasattr(self, 'auth_token') else {}
        )
        print(f"Reception upload invalid booking response: {response.status_code}")
        
        assert response.status_code == 404
        print("✓ Reception upload with invalid booking correctly returns 404")

    # ==================== LIST REGISTRATIONS TESTS ====================
    
    def test_list_registrations_success(self):
        """Test GET /api/guest-journey/registrations/{property_id} - lists all registrations for property"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/{TEST_PROPERTY_ID}")
        print(f"List registrations response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            reg = data[0]
            # Validate registration structure
            assert "id" in reg
            assert "booking_id" in reg
            assert "guest_name" in reg
            assert "status" in reg
            assert "id_uploaded" in reg
            assert "terms_accepted" in reg
            print(f"✓ Found {len(data)} registrations, first: {reg.get('guest_name')} - {reg.get('status')}")
        else:
            print("✓ Registrations list returned (empty)")

    def test_list_registrations_requires_auth(self):
        """Test GET /api/guest-journey/registrations/{property_id} - requires authentication"""
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-journey/registrations/{TEST_PROPERTY_ID}")
        print(f"List registrations without auth response: {response.status_code}")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ List registrations correctly requires authentication")
        public_session.close()

    # ==================== SATISFACTION CHECK TESTS ====================
    
    def test_send_satisfaction_checks(self):
        """Test POST /api/guest-journey/send-satisfaction-check/{property_id} - sends satisfaction checks"""
        response = self.session.post(f"{BASE_URL}/api/guest-journey/send-satisfaction-check/{TEST_PROPERTY_ID}")
        print(f"Send satisfaction checks response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "sent" in data
        assert "total_eligible" in data
        
        print(f"✓ Satisfaction checks: sent={data['sent']}, eligible={data['total_eligible']}")

    def test_list_satisfaction_checks(self):
        """Test GET /api/guest-journey/satisfaction-checks/{property_id} - lists satisfaction checks"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/satisfaction-checks/{TEST_PROPERTY_ID}")
        print(f"List satisfaction checks response: {response.status_code} - {response.text[:500]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            check = data[0]
            assert "id" in check
            assert "token" in check
            assert "guest_name" in check
            assert "status" in check
            print(f"✓ Found {len(data)} satisfaction checks")
        else:
            print("✓ Satisfaction checks list returned (empty)")

    # ==================== FEEDBACK (PUBLIC) TESTS ====================
    
    def test_get_feedback_form_invalid_token(self):
        """Test GET /api/guest-journey/feedback/{token} - invalid token returns 404"""
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-journey/feedback/invalid-feedback-token")
        print(f"Get feedback invalid token response: {response.status_code}")
        
        assert response.status_code == 404
        print("✓ Feedback with invalid token correctly returns 404")
        public_session.close()

    def test_submit_feedback_invalid_token(self):
        """Test POST /api/guest-journey/feedback/{token} - invalid token returns 404"""
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        
        response = public_session.post(
            f"{BASE_URL}/api/guest-journey/feedback/invalid-feedback-token",
            json={"response": "all_good", "message": ""}
        )
        print(f"Submit feedback invalid token response: {response.status_code}")
        
        assert response.status_code == 404
        print("✓ Submit feedback with invalid token correctly returns 404")
        public_session.close()

    # ==================== INTEGRATION TEST ====================
    
    def test_full_registration_flow(self):
        """Test complete registration flow: send link -> get form -> submit -> verify"""
        # Step 1: Send registration link
        send_resp = self.session.post(f"{BASE_URL}/api/guest-journey/send-registration/{TEST_BOOKING_ID}")
        assert send_resp.status_code == 200
        token = send_resp.json()["token"]
        print(f"Step 1: Registration link sent, token: {token[:20]}...")
        
        # Step 2: Get registration form (public)
        public_session = requests.Session()
        get_resp = public_session.get(f"{BASE_URL}/api/guest-journey/registration/{token}")
        assert get_resp.status_code == 200
        form_data = get_resp.json()
        assert form_data["status"] == "pending"
        print(f"Step 2: Form retrieved, hotel: {form_data['hotel_name']}")
        
        # Step 3: Upload ID
        test_file = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {'file': ('passport.png', test_file, 'image/png')}
        upload_resp = public_session.post(f"{BASE_URL}/api/guest-journey/upload-id/{token}", files=files)
        assert upload_resp.status_code == 200
        print("Step 3: ID uploaded")
        
        # Step 4: Submit registration
        public_session.headers.update({"Content-Type": "application/json"})
        submit_data = {
            "form_data": {
                "full_name": "Integration Test Guest",
                "email": "integration@test.com",
                "nationality": "British"
            },
            "terms_accepted": True,
            "signature": "Integration Test Guest"
        }
        submit_resp = public_session.post(f"{BASE_URL}/api/guest-journey/registration/{token}", json=submit_data)
        assert submit_resp.status_code == 200
        assert submit_resp.json()["completed"] == True
        print("Step 4: Registration submitted and completed")
        
        # Step 5: Verify in registrations list
        list_resp = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/{TEST_PROPERTY_ID}")
        assert list_resp.status_code == 200
        registrations = list_resp.json()
        found = any(r.get("token") == token for r in registrations)
        assert found, "Registration not found in list"
        print("Step 5: Registration verified in list")
        
        print("✓ Full registration flow completed successfully!")
        public_session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
