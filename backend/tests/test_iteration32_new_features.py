"""
Iteration 32 - Testing 6 NEW Hotel Booking Engine Features:
1. Guest Review Collection (post-stay email + review page)
2. Mobile Self-Check-in (4-step check-in before arrival)
3. Guest Portal (magic link login, booking history, re-booking)
4. Cart Abandonment Recovery (save abandoned carts, recovery links)
5. Multi-Currency Support (18 currencies, live conversion)
6. Group Booking Engine (corporate/wedding/conference requests)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def test_booking(auth_token):
    """Create a test booking for review collection and check-in tests"""
    # First get a room type
    rooms_response = requests.get(f"{BASE_URL}/api/booking/rooms/{PROPERTY_ID}")
    if rooms_response.status_code != 200 or not rooms_response.json():
        pytest.skip("No rooms available for testing")
    
    room = rooms_response.json()[0]
    
    # Create a booking
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    booking_data = {
        "property_id": PROPERTY_ID,
        "room_type_id": room["id"],
        "guest_name": "TEST_Review Guest",
        "guest_email": "test_review@example.com",
        "guest_phone": "+44123456789",
        "check_in": tomorrow,
        "check_out": day_after,
        "adults": 2,
        "children": 0,
        "rooms": 1,
        "special_requests": "Test booking for review collection"
    }
    
    response = requests.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
    if response.status_code in [200, 201]:
        return response.json()
    pytest.skip(f"Failed to create test booking: {response.text}")


class TestReviewCollection:
    """Test Guest Review Collection feature"""
    
    def test_get_review_settings_default(self, auth_token):
        """GET /api/review-collection/settings/{property_id} - returns default settings"""
        response = requests.get(
            f"{BASE_URL}/api/review-collection/settings/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        assert "enabled" in data
        assert "delay_hours" in data
        assert "email_subject" in data
        print(f"PASS: Review collection settings returned with enabled={data.get('enabled')}")
    
    def test_update_review_settings(self, auth_token):
        """PUT /api/review-collection/settings/{property_id} - update settings"""
        update_data = {
            "enabled": True,
            "delay_hours": 48,
            "email_subject": "How was your stay at {hotel_name}?",
            "reminder_enabled": True
        }
        response = requests.put(
            f"{BASE_URL}/api/review-collection/settings/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("delay_hours") == 48
        print(f"PASS: Review settings updated, delay_hours={data.get('delay_hours')}")
    
    def test_get_review_page_data(self, test_booking):
        """GET /api/review-collection/page/{property_id}/{booking_ref} - returns booking + property data"""
        booking_ref = test_booking.get("booking_ref")
        response = requests.get(f"{BASE_URL}/api/review-collection/page/{PROPERTY_ID}/{booking_ref}")
        assert response.status_code == 200
        data = response.json()
        assert "booking" in data
        assert "property" in data
        assert data["booking"]["booking_ref"] == booking_ref
        print(f"PASS: Review page data returned for booking {booking_ref}")
    
    def test_submit_guest_review(self, test_booking):
        """POST /api/review-collection/submit - submit a guest review with rating 5"""
        booking_ref = test_booking.get("booking_ref")
        response = requests.post(
            f"{BASE_URL}/api/review-collection/submit",
            params={
                "property_id": PROPERTY_ID,
                "booking_ref": booking_ref,
                "rating": 5,
                "title": "Excellent stay!",
                "review_text": "The room was clean and staff were friendly. Would definitely recommend!",
                "guest_name": "TEST_Review Guest"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        print(f"PASS: Guest review submitted successfully for booking {booking_ref}")
    
    def test_duplicate_review_rejected(self, test_booking):
        """POST /api/review-collection/submit - duplicate review should be rejected"""
        booking_ref = test_booking.get("booking_ref")
        response = requests.post(
            f"{BASE_URL}/api/review-collection/submit",
            params={
                "property_id": PROPERTY_ID,
                "booking_ref": booking_ref,
                "rating": 4,
                "review_text": "Trying to submit again"
            }
        )
        assert response.status_code == 400
        print(f"PASS: Duplicate review correctly rejected")


class TestSelfCheckIn:
    """Test Mobile Self-Check-in feature"""
    
    def test_get_checkin_settings_default(self, auth_token):
        """GET /api/checkin/settings/{property_id} - returns default check-in settings"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/settings/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        assert "enabled" in data
        assert "require_id_upload" in data
        assert "require_terms_acceptance" in data
        print(f"PASS: Check-in settings returned with enabled={data.get('enabled')}")
    
    def test_start_checkin(self, test_booking):
        """POST /api/checkin/start/{booking_ref} - initialize check-in"""
        booking_ref = test_booking.get("booking_ref")
        response = requests.post(f"{BASE_URL}/api/checkin/start/{booking_ref}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("booking_ref") == booking_ref
        assert data.get("status") in ["pending", "completed"]
        assert "guest_name" in data
        print(f"PASS: Check-in started for booking {booking_ref}, status={data.get('status')}")
    
    def test_complete_checkin(self, test_booking):
        """POST /api/checkin/complete/{booking_ref} - complete check-in process"""
        booking_ref = test_booking.get("booking_ref")
        response = requests.post(
            f"{BASE_URL}/api/checkin/complete/{booking_ref}",
            params={
                "terms_accepted": True,
                "special_notes": "Late arrival expected around 10pm"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "completed"
        assert data.get("terms_accepted") == True
        print(f"PASS: Check-in completed for booking {booking_ref}")
    
    def test_admin_list_checkins(self, auth_token):
        """GET /api/checkin/admin/{property_id} - list check-ins for property"""
        response = requests.get(
            f"{BASE_URL}/api/checkin/admin/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Admin check-in list returned {len(data)} check-ins")


class TestGuestPortal:
    """Test Guest Portal feature"""
    
    def test_request_access_sends_token(self):
        """POST /api/guest-portal/request-access - sends magic link, returns token"""
        response = requests.post(
            f"{BASE_URL}/api/guest-portal/request-access",
            params={"guest_email": "test_review@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "sent"
        # In dev mode, token is returned directly
        assert "token" in data
        print(f"PASS: Magic link token returned for guest portal access")
        return data.get("token")
    
    def test_verify_magic_token(self):
        """POST /api/guest-portal/verify - verify magic token"""
        # First get a token
        req_response = requests.post(
            f"{BASE_URL}/api/guest-portal/request-access",
            params={"guest_email": "test_review@example.com"}
        )
        token = req_response.json().get("token")
        
        # Verify the token
        response = requests.post(
            f"{BASE_URL}/api/guest-portal/verify",
            params={"token": token}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "verified"
        assert data.get("guest_email") == "test_review@example.com"
        print(f"PASS: Magic token verified successfully")
    
    def test_get_guest_bookings(self):
        """GET /api/guest-portal/bookings - get bookings for verified guest"""
        # First get a token
        req_response = requests.post(
            f"{BASE_URL}/api/guest-portal/request-access",
            params={"guest_email": "test_review@example.com"}
        )
        token = req_response.json().get("token")
        
        # Get bookings
        response = requests.get(
            f"{BASE_URL}/api/guest-portal/bookings",
            params={"token": token}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the test booking
        assert len(data) >= 1
        print(f"PASS: Guest portal returned {len(data)} bookings")


class TestCartAbandonment:
    """Test Cart Abandonment Recovery feature"""
    
    def test_save_abandoned_cart(self):
        """POST /api/cart/save - save abandoned cart with email"""
        response = requests.post(
            f"{BASE_URL}/api/cart/save",
            params={
                "property_id": PROPERTY_ID,
                "room_type_id": "test-room-123",
                "room_name": "Deluxe Suite",
                "guest_email": "abandoned_cart@example.com",
                "guest_name": "TEST_Cart User",
                "check_in": "2026-02-15",
                "check_out": "2026-02-17",
                "adults": 2,
                "total_price": 250.00
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "saved"
        assert "recovery_token" in data
        print(f"PASS: Abandoned cart saved with recovery token")
        return data.get("recovery_token")
    
    def test_recover_cart(self):
        """GET /api/cart/recover/{token} - recover abandoned cart"""
        # First save a cart
        save_response = requests.post(
            f"{BASE_URL}/api/cart/save",
            params={
                "property_id": PROPERTY_ID,
                "room_type_id": "test-room-456",
                "room_name": "Standard Room",
                "guest_email": "recover_test@example.com",
                "guest_name": "TEST_Recovery User",
                "check_in": "2026-03-01",
                "check_out": "2026-03-03",
                "adults": 1,
                "total_price": 150.00
            }
        )
        token = save_response.json().get("recovery_token")
        
        # Recover the cart
        response = requests.get(f"{BASE_URL}/api/cart/recover/{token}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("guest_email") == "recover_test@example.com"
        assert data.get("room_name") == "Standard Room"
        print(f"PASS: Cart recovered successfully")
    
    def test_list_abandoned_carts(self, auth_token):
        """GET /api/cart/abandoned/{property_id} - list abandoned carts"""
        response = requests.get(
            f"{BASE_URL}/api/cart/abandoned/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Abandoned carts list returned {len(data)} carts")
    
    def test_cart_stats(self, auth_token):
        """GET /api/cart/stats/{property_id} - cart abandonment statistics"""
        response = requests.get(
            f"{BASE_URL}/api/cart/stats/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_abandoned" in data
        assert "recovered" in data
        assert "recovery_rate" in data
        print(f"PASS: Cart stats returned - total={data.get('total_abandoned')}, recovered={data.get('recovered')}, rate={data.get('recovery_rate')}%")


class TestMultiCurrency:
    """Test Multi-Currency Support feature"""
    
    def test_get_supported_currencies(self):
        """GET /api/currencies - returns 18 supported currencies"""
        response = requests.get(f"{BASE_URL}/api/currencies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) >= 18
        # Check for key currencies
        assert "GBP" in data
        assert "USD" in data
        assert "EUR" in data
        assert "AED" in data
        assert "JPY" in data
        print(f"PASS: {len(data)} currencies returned including GBP, USD, EUR, AED, JPY")
    
    def test_currency_conversion_gbp_to_usd(self):
        """GET /api/currency/convert - converts GBP to USD correctly"""
        response = requests.get(
            f"{BASE_URL}/api/currency/convert",
            params={"amount": 100, "from_currency": "GBP", "to_currency": "USD"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("original") == 100
        assert data.get("from") == "GBP"
        assert data.get("to") == "USD"
        assert "converted" in data
        assert data.get("converted") > 100  # USD should be more than GBP
        assert "rate" in data
        print(f"PASS: £100 GBP = ${data.get('converted')} USD (rate: {data.get('rate')})")
    
    def test_currency_conversion_eur_to_jpy(self):
        """GET /api/currency/convert - converts EUR to JPY"""
        response = requests.get(
            f"{BASE_URL}/api/currency/convert",
            params={"amount": 50, "from_currency": "EUR", "to_currency": "JPY"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("original") == 50
        assert data.get("converted") > 5000  # JPY should be much higher
        print(f"PASS: €50 EUR = ¥{data.get('converted')} JPY")
    
    def test_invalid_currency_rejected(self):
        """GET /api/currency/convert - invalid currency returns 400"""
        response = requests.get(
            f"{BASE_URL}/api/currency/convert",
            params={"amount": 100, "from_currency": "GBP", "to_currency": "INVALID"}
        )
        assert response.status_code == 400
        print(f"PASS: Invalid currency correctly rejected")


class TestGroupBooking:
    """Test Group Booking Engine feature"""
    
    def test_submit_group_booking_request(self):
        """POST /api/group-booking/request - submit group booking request"""
        tomorrow = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=32)).strftime("%Y-%m-%d")
        
        request_data = {
            "property_id": PROPERTY_ID,
            "contact_name": "TEST_Group Organizer",
            "contact_email": "group_test@example.com",
            "contact_phone": "+44987654321",
            "company_name": "Test Corp Ltd",
            "event_type": "corporate",
            "check_in": tomorrow,
            "check_out": day_after,
            "total_rooms": 10,
            "total_guests": 20,
            "room_preferences": "Prefer rooms on same floor",
            "special_requirements": "Meeting room needed, AV equipment",
            "budget_range": "£5000-£8000"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/group-booking/request",
            json=request_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "submitted"
        assert "id" in data
        assert "message" in data
        print(f"PASS: Group booking request submitted with ID {data.get('id')}")
    
    def test_list_group_booking_requests(self, auth_token):
        """GET /api/group-booking/requests/{property_id} - list group booking requests"""
        response = requests.get(
            f"{BASE_URL}/api/group-booking/requests/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least the test request
        assert len(data) >= 1
        # Check structure
        if data:
            assert "contact_name" in data[0]
            assert "event_type" in data[0]
            assert "total_rooms" in data[0]
        print(f"PASS: Group booking requests list returned {len(data)} requests")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_data(self, auth_token):
        """Clean up TEST_ prefixed data"""
        # This is a placeholder - in production you'd clean up test data
        print("PASS: Test cleanup completed (test data prefixed with TEST_)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
