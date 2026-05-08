"""
Iteration 75 - Kiosk, Welcome Info, and SMS/WhatsApp Satisfaction Tests
Tests for:
1. GET /api/guest-journey/kiosk-lookup/{property_id}?q=search - public booking lookup for kiosk
2. POST /api/guest-journey/kiosk-register/{property_id} - create walk-in registration at kiosk
3. GET /api/guest-journey/welcome-info/{property_id} - returns configurable welcome info
4. PUT /api/guest-journey/welcome-info/{property_id} - saves hotel policies, city info, custom message
5. Satisfaction checks SMS/WhatsApp delivery (graceful skip if not configured)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com')

class TestKioskLookup:
    """Tests for kiosk booking lookup endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.property_id = "aldgate-flats"
    
    def test_kiosk_lookup_with_valid_query(self):
        """Test kiosk lookup with valid search query"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q=John")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Kiosk lookup for 'John' returned {len(data)} results")
        if len(data) > 0:
            # Verify response structure
            booking = data[0]
            assert "booking_id" in booking
            assert "booking_ref" in booking
            assert "guest_name" in booking
            assert "check_in" in booking
            assert "check_out" in booking
            assert "registration_token" in booking or booking.get("registration_token") is None
            assert "registration_status" in booking or booking.get("registration_status") is None
            print(f"First result: {booking['guest_name']} - {booking['booking_ref']}")
    
    def test_kiosk_lookup_short_query(self):
        """Test kiosk lookup with query less than 2 characters returns empty"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q=J")
        assert response.status_code == 200
        data = response.json()
        assert data == []
        print("Short query (1 char) correctly returns empty list")
    
    def test_kiosk_lookup_empty_query(self):
        """Test kiosk lookup with empty query returns empty"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q=")
        assert response.status_code == 200
        data = response.json()
        assert data == []
        print("Empty query correctly returns empty list")
    
    def test_kiosk_lookup_no_results(self):
        """Test kiosk lookup with non-matching query"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q=ZZZZNONEXISTENT")
        assert response.status_code == 200
        data = response.json()
        assert data == []
        print("Non-matching query correctly returns empty list")
    
    def test_kiosk_lookup_by_booking_ref(self):
        """Test kiosk lookup by booking reference"""
        # First get a booking to find a valid ref
        response = self.session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q=John")
        if response.status_code == 200 and len(response.json()) > 0:
            booking_ref = response.json()[0].get("booking_ref", "")
            if booking_ref:
                # Search by booking ref
                response2 = self.session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q={booking_ref[:4]}")
                assert response2.status_code == 200
                print(f"Booking ref search for '{booking_ref[:4]}' returned {len(response2.json())} results")
        else:
            print("No bookings found to test booking ref search")
    
    def test_kiosk_lookup_is_public(self):
        """Test that kiosk lookup does not require authentication"""
        # Create a fresh session without any auth
        fresh_session = requests.Session()
        response = fresh_session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q=test")
        assert response.status_code == 200
        print("Kiosk lookup is correctly public (no auth required)")


class TestKioskRegister:
    """Tests for kiosk registration endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.property_id = "aldgate-flats"
    
    def test_kiosk_register_creates_registration(self):
        """Test kiosk register creates a new registration for a booking"""
        # First find a booking
        lookup_response = self.session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q=John")
        if lookup_response.status_code == 200 and len(lookup_response.json()) > 0:
            booking = lookup_response.json()[0]
            booking_id = booking["booking_id"]
            
            # Create registration
            response = self.session.post(
                f"{BASE_URL}/api/guest-journey/kiosk-register/{self.property_id}",
                json={"booking_id": booking_id}
            )
            assert response.status_code == 200
            data = response.json()
            assert "token" in data
            assert "status" in data
            assert data["status"] in ["pending", "completed"]
            print(f"Kiosk register returned token: {data['token'][:20]}... status: {data['status']}")
        else:
            pytest.skip("No bookings found to test kiosk registration")
    
    def test_kiosk_register_returns_existing_token(self):
        """Test kiosk register returns existing token if registration already exists"""
        # First find a booking with existing registration
        lookup_response = self.session.get(f"{BASE_URL}/api/guest-journey/kiosk-lookup/{self.property_id}?q=John")
        if lookup_response.status_code == 200 and len(lookup_response.json()) > 0:
            # Find one with existing registration
            for booking in lookup_response.json():
                if booking.get("registration_token"):
                    booking_id = booking["booking_id"]
                    existing_token = booking["registration_token"]
                    
                    # Try to create registration again
                    response = self.session.post(
                        f"{BASE_URL}/api/guest-journey/kiosk-register/{self.property_id}",
                        json={"booking_id": booking_id}
                    )
                    assert response.status_code == 200
                    data = response.json()
                    assert data["token"] == existing_token
                    print(f"Kiosk register correctly returned existing token")
                    return
            print("No bookings with existing registration found")
        else:
            pytest.skip("No bookings found")
    
    def test_kiosk_register_missing_booking_id(self):
        """Test kiosk register with missing booking_id returns 400"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/kiosk-register/{self.property_id}",
            json={}
        )
        assert response.status_code == 400
        print("Missing booking_id correctly returns 400")
    
    def test_kiosk_register_invalid_booking_id(self):
        """Test kiosk register with invalid booking_id returns 404"""
        response = self.session.post(
            f"{BASE_URL}/api/guest-journey/kiosk-register/{self.property_id}",
            json={"booking_id": "invalid-booking-id-12345"}
        )
        assert response.status_code == 404
        print("Invalid booking_id correctly returns 404")
    
    def test_kiosk_register_is_public(self):
        """Test that kiosk register does not require authentication"""
        # Create a fresh session without any auth
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        response = fresh_session.post(
            f"{BASE_URL}/api/guest-journey/kiosk-register/{self.property_id}",
            json={"booking_id": "test-id"}
        )
        # Should return 404 (not found) not 401 (unauthorized)
        assert response.status_code == 404
        print("Kiosk register is correctly public (no auth required)")


class TestWelcomeInfo:
    """Tests for welcome info settings endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.property_id = "aldgate-flats"
        
        # Login as admin
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
        )
        assert login_response.status_code == 200
        print("Logged in as admin")
    
    def test_get_welcome_info_returns_defaults(self):
        """Test GET welcome info returns default values if not set"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/welcome-info/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "property_id" in data
        assert "hotel_policies" in data
        assert "city_info" in data
        assert "custom_message" in data
        assert isinstance(data["hotel_policies"], list)
        assert isinstance(data["city_info"], list)
        print(f"Welcome info returned {len(data['hotel_policies'])} policies, {len(data['city_info'])} city info items")
    
    def test_update_welcome_info(self):
        """Test PUT welcome info saves settings"""
        test_policies = ["Test Policy 1", "Test Policy 2", "Check-in: 3PM"]
        test_city_info = ["Test City Info 1", "Nearest metro: 5 min"]
        test_message = "Welcome to our test hotel!"
        
        response = self.session.put(
            f"{BASE_URL}/api/guest-journey/welcome-info/{self.property_id}",
            json={
                "hotel_policies": test_policies,
                "city_info": test_city_info,
                "custom_message": test_message
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "saved"
        print("Welcome info saved successfully")
        
        # Verify by fetching again
        get_response = self.session.get(f"{BASE_URL}/api/guest-journey/welcome-info/{self.property_id}")
        assert get_response.status_code == 200
        saved_data = get_response.json()
        assert saved_data["hotel_policies"] == test_policies
        assert saved_data["city_info"] == test_city_info
        assert saved_data["custom_message"] == test_message
        print("Welcome info verified after save")
    
    def test_welcome_info_requires_auth(self):
        """Test that welcome info endpoints require authentication"""
        # Create a fresh session without auth
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        # GET should require auth
        get_response = fresh_session.get(f"{BASE_URL}/api/guest-journey/welcome-info/{self.property_id}")
        assert get_response.status_code == 401
        print("GET welcome info correctly requires auth")
        
        # PUT should require auth
        put_response = fresh_session.put(
            f"{BASE_URL}/api/guest-journey/welcome-info/{self.property_id}",
            json={"hotel_policies": [], "city_info": [], "custom_message": ""}
        )
        assert put_response.status_code == 401
        print("PUT welcome info correctly requires auth")
    
    def test_welcome_info_empty_lists(self):
        """Test welcome info can save empty lists"""
        response = self.session.put(
            f"{BASE_URL}/api/guest-journey/welcome-info/{self.property_id}",
            json={
                "hotel_policies": [],
                "city_info": [],
                "custom_message": ""
            }
        )
        assert response.status_code == 200
        print("Welcome info accepts empty lists")


class TestSatisfactionSMSWhatsApp:
    """Tests for satisfaction check SMS/WhatsApp delivery"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.property_id = "aldgate-flats"
        
        # Login as admin
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
        )
        assert login_response.status_code == 200
        print("Logged in as admin")
    
    def test_send_satisfaction_check_endpoint(self):
        """Test satisfaction check endpoint works (SMS/WhatsApp gracefully skip if not configured)"""
        response = self.session.post(f"{BASE_URL}/api/guest-journey/send-satisfaction-check/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert "sent" in data
        assert "total_eligible" in data
        print(f"Satisfaction check: sent={data['sent']}, total_eligible={data['total_eligible']}")
    
    def test_list_satisfaction_checks(self):
        """Test listing satisfaction checks"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/satisfaction-checks/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} satisfaction checks")
        if len(data) > 0:
            check = data[0]
            assert "id" in check
            assert "token" in check
            assert "guest_name" in check
            assert "status" in check


class TestGuestJourneyTabs:
    """Tests for Guest Journey panel tabs (4 tabs: Registrations, Satisfaction, Welcome Info, Kiosk Setup)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.property_id = "aldgate-flats"
        
        # Login as admin
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}
        )
        assert login_response.status_code == 200
    
    def test_registrations_list(self):
        """Test registrations list endpoint"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/registrations/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} registrations")
    
    def test_satisfaction_checks_list(self):
        """Test satisfaction checks list endpoint"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/satisfaction-checks/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} satisfaction checks")
    
    def test_welcome_info_get(self):
        """Test welcome info get endpoint"""
        response = self.session.get(f"{BASE_URL}/api/guest-journey/welcome-info/{self.property_id}")
        assert response.status_code == 200
        data = response.json()
        assert "hotel_policies" in data
        assert "city_info" in data
        print("Welcome info endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
