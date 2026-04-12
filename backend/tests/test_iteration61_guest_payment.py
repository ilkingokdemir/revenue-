"""
Iteration 61 - Guest Payment Portal Tests
Tests for Cloudbeds-style guest-facing payment page:
- Send payment links (admin)
- View folio (public)
- Pay via Stripe (public)
- Check payment status (public)
- List payment links (admin)
- Add extra charges (admin)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable is required")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Test booking from seed data
TEST_BOOKING_ID = "48ae77e7-95fa-487f-8f01-1fbbbc4366fa"
TEST_BOOKING_REF = "MHB-D7777DC7"
TEST_PROPERTY_ID = "aldgate-flats"


@pytest.fixture(scope="module")
def admin_session():
    """Create authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
    token = login_resp.json().get("access_token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"✓ Admin login successful")
    return session


@pytest.fixture
def fresh_payment_link(admin_session):
    """Create a fresh payment link for testing"""
    response = admin_session.post(f"{BASE_URL}/api/guest-payment/send-link", json={
        "booking_id": TEST_BOOKING_ID,
        "extra_charges": [],
        "notes": "Test payment link"
    })
    assert response.status_code == 200, f"Failed to create payment link: {response.text}"
    data = response.json()
    return {
        "token": data["token"],
        "link_id": data["payment_link_id"],
        "amount": data["amount"],
        "url": data["url"]
    }


class TestGuestPaymentSendLink:
    """Tests for sending payment links (admin)"""
    
    def test_send_payment_link_success(self, admin_session):
        """POST /api/guest-payment/send-link - Admin sends payment link"""
        response = admin_session.post(f"{BASE_URL}/api/guest-payment/send-link", json={
            "booking_id": TEST_BOOKING_ID,
            "extra_charges": [],
            "notes": "Test payment link"
        })
        
        assert response.status_code == 200, f"Send payment link failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "status" in data
        assert data["status"] == "sent"
        assert "payment_link_id" in data
        assert "token" in data
        assert "amount" in data
        assert "url" in data
        
        # Verify URL format
        assert "/pay/" in data["url"]
        assert data["token"] in data["url"]
        
        print(f"✓ Payment link sent: {data['url']}")
        print(f"  Amount: £{data['amount']}")
        print(f"  Token: {data['token'][:20]}...")
    
    def test_send_payment_link_with_extra_charges(self, admin_session):
        """POST /api/guest-payment/send-link - With extra charges"""
        response = admin_session.post(f"{BASE_URL}/api/guest-payment/send-link", json={
            "booking_id": TEST_BOOKING_ID,
            "extra_charges": [
                {"description": "Minibar", "amount": 25.00, "category": "minibar"},
                {"description": "Room Service", "amount": 45.00, "category": "restaurant"}
            ],
            "notes": "Please pay before checkout"
        })
        
        assert response.status_code == 200, f"Send payment link with charges failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "sent"
        assert data["amount"] >= 70  # At least the extra charges
        
        print(f"✓ Payment link with extra charges sent: £{data['amount']}")
    
    def test_send_payment_link_invalid_booking(self, admin_session):
        """POST /api/guest-payment/send-link - Invalid booking ID"""
        response = admin_session.post(f"{BASE_URL}/api/guest-payment/send-link", json={
            "booking_id": "invalid-booking-id-12345",
            "extra_charges": [],
            "notes": ""
        })
        
        assert response.status_code == 404, f"Expected 404 for invalid booking: {response.text}"
        print("✓ Invalid booking returns 404")


class TestGuestPaymentFolio:
    """Tests for viewing folio (public)"""
    
    def test_get_folio_success(self, fresh_payment_link):
        """GET /api/guest-payment/folio/{token} - Public: View folio"""
        token = fresh_payment_link["token"]
        
        # Public endpoint - no auth needed
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-payment/folio/{token}")
        
        assert response.status_code == 200, f"Get folio failed: {response.text}"
        data = response.json()
        
        # Verify folio structure
        assert "status" in data
        assert "hotel_name" in data
        assert "booking" in data
        assert "folio_items" in data
        assert "balance_due" in data
        assert "currency" in data
        
        # Verify booking details
        booking = data["booking"]
        assert "booking_ref" in booking
        assert "guest_name" in booking
        assert "check_in" in booking
        assert "check_out" in booking
        assert "nights" in booking
        assert "room_name" in booking
        
        # Verify folio items exist
        assert isinstance(data["folio_items"], list)
        assert len(data["folio_items"]) > 0
        
        print(f"✓ Folio retrieved for {booking['guest_name']}")
        print(f"  Hotel: {data['hotel_name']}")
        print(f"  Booking Ref: {booking['booking_ref']}")
        print(f"  Room: {booking['room_name']}")
        print(f"  Nights: {booking['nights']}")
        print(f"  Balance Due: £{data['balance_due']}")
        print(f"  Folio Items: {len(data['folio_items'])}")
    
    def test_get_folio_with_extra_charges(self, admin_session):
        """GET /api/guest-payment/folio/{token} - Folio with extra charges"""
        # Create payment link with extra charges
        response = admin_session.post(f"{BASE_URL}/api/guest-payment/send-link", json={
            "booking_id": TEST_BOOKING_ID,
            "extra_charges": [
                {"description": "Minibar - Wine", "amount": 15.00, "category": "minibar"},
                {"description": "Laundry Service", "amount": 20.00, "category": "laundry"}
            ],
            "notes": ""
        })
        assert response.status_code == 200
        token = response.json()["token"]
        
        public_session = requests.Session()
        folio_resp = public_session.get(f"{BASE_URL}/api/guest-payment/folio/{token}")
        
        assert folio_resp.status_code == 200, f"Get folio with charges failed: {folio_resp.text}"
        data = folio_resp.json()
        
        # Check for extra charges in folio items
        categories = set(item.get("category") for item in data["folio_items"])
        
        assert "minibar" in categories, "Should have minibar category"
        assert "laundry" in categories, "Should have laundry category"
        
        print(f"✓ Folio with extra charges retrieved")
        print(f"  Categories: {categories}")
        print(f"  Total Charges: £{data['total_charges']}")
        print(f"  Balance Due: £{data['balance_due']}")
    
    def test_get_folio_invalid_token(self):
        """GET /api/guest-payment/folio/{token} - Invalid token"""
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-payment/folio/invalid-token-12345")
        
        assert response.status_code == 404, f"Expected 404 for invalid token: {response.text}"
        print("✓ Invalid token returns 404")
    
    def test_folio_contains_room_charges(self, fresh_payment_link):
        """Folio should contain room charges by night"""
        token = fresh_payment_link["token"]
        
        public_session = requests.Session()
        folio_resp = public_session.get(f"{BASE_URL}/api/guest-payment/folio/{token}")
        assert folio_resp.status_code == 200
        folio = folio_resp.json()
        
        # Check for room category items
        room_items = [item for item in folio["folio_items"] if item.get("category") == "room"]
        
        assert len(room_items) > 0, "Folio should contain room charges"
        
        print(f"✓ Folio contains {len(room_items)} room charge(s)")
        for item in room_items:
            print(f"  - {item['description']}: £{item['amount']}")


class TestGuestPaymentStripe:
    """Tests for Stripe payment (public)"""
    
    def test_pay_folio_creates_stripe_session(self, fresh_payment_link):
        """POST /api/guest-payment/pay/{token} - Creates Stripe checkout session"""
        token = fresh_payment_link["token"]
        
        public_session = requests.Session()
        response = public_session.post(f"{BASE_URL}/api/guest-payment/pay/{token}")
        
        assert response.status_code == 200, f"Pay folio failed: {response.text}"
        data = response.json()
        
        # Verify Stripe checkout URL returned
        assert "url" in data
        assert "checkout.stripe.com" in data["url"]
        assert "session_id" in data
        
        print(f"✓ Stripe checkout session created")
        print(f"  URL: {data['url'][:80]}...")
        print(f"  Session ID: {data['session_id'][:30]}...")
    
    def test_pay_folio_invalid_token(self):
        """POST /api/guest-payment/pay/{token} - Invalid token"""
        public_session = requests.Session()
        response = public_session.post(f"{BASE_URL}/api/guest-payment/pay/invalid-token-12345")
        
        assert response.status_code == 404, f"Expected 404 for invalid token: {response.text}"
        print("✓ Pay with invalid token returns 404")


class TestGuestPaymentStatus:
    """Tests for payment status (public)"""
    
    def test_check_payment_status(self, fresh_payment_link):
        """GET /api/guest-payment/status/{token} - Check payment status"""
        token = fresh_payment_link["token"]
        
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-payment/status/{token}")
        
        assert response.status_code == 200, f"Check status failed: {response.text}"
        data = response.json()
        
        assert "status" in data
        # Status should be pending since we haven't completed payment
        assert data["status"] in ["pending", "paid", "expired", "cancelled"]
        
        print(f"✓ Payment status: {data['status']}")
    
    def test_check_payment_status_with_session_id(self, fresh_payment_link):
        """GET /api/guest-payment/status/{token}?session_id=xxx - With Stripe session"""
        token = fresh_payment_link["token"]
        
        # First create a Stripe session
        public_session = requests.Session()
        pay_resp = public_session.post(f"{BASE_URL}/api/guest-payment/pay/{token}")
        assert pay_resp.status_code == 200
        session_id = pay_resp.json()["session_id"]
        
        # Check status with session_id
        response = public_session.get(f"{BASE_URL}/api/guest-payment/status/{token}?session_id={session_id}")
        
        # Should return 200 even if Stripe check fails with test key
        assert response.status_code == 200, f"Check status with session failed: {response.text}"
        data = response.json()
        
        assert "status" in data
        print(f"✓ Payment status with session_id: {data['status']}")
    
    def test_check_payment_status_invalid_token(self):
        """GET /api/guest-payment/status/{token} - Invalid token"""
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-payment/status/invalid-token-12345")
        
        assert response.status_code == 404, f"Expected 404 for invalid token: {response.text}"
        print("✓ Status check with invalid token returns 404")


class TestGuestPaymentAdmin:
    """Tests for admin endpoints"""
    
    def test_list_payment_links(self, admin_session):
        """GET /api/guest-payment/links/{property_id} - Admin: List payment links"""
        response = admin_session.get(f"{BASE_URL}/api/guest-payment/links/{TEST_PROPERTY_ID}")
        
        assert response.status_code == 200, f"List payment links failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        
        if len(data) > 0:
            link = data[0]
            assert "id" in link
            assert "booking_id" in link
            assert "booking_ref" in link
            assert "guest_name" in link
            assert "amount" in link
            assert "status" in link
            assert "token" in link
            
            print(f"✓ Listed {len(data)} payment links for {TEST_PROPERTY_ID}")
            for l in data[:3]:
                print(f"  - {l['booking_ref']}: {l['guest_name']} - £{l['amount']} ({l['status']})")
        else:
            print(f"✓ No payment links found for {TEST_PROPERTY_ID}")
    
    def test_list_payment_links_requires_auth(self):
        """GET /api/guest-payment/links/{property_id} - Requires authentication"""
        public_session = requests.Session()
        response = public_session.get(f"{BASE_URL}/api/guest-payment/links/{TEST_PROPERTY_ID}")
        
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403], f"Expected 401/403 without auth: {response.status_code}"
        print("✓ List payment links requires authentication")
    
    def test_add_extra_charge(self, admin_session, fresh_payment_link):
        """POST /api/guest-payment/add-charge/{link_id} - Admin: Add extra charge"""
        link_id = fresh_payment_link["link_id"]
        
        response = admin_session.post(f"{BASE_URL}/api/guest-payment/add-charge/{link_id}", json={
            "description": "Spa Treatment",
            "amount": 75.00,
            "category": "spa"
        })
        
        assert response.status_code == 200, f"Add charge failed: {response.text}"
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "added"
        assert "new_amount" in data
        
        print(f"✓ Extra charge added")
        print(f"  New total: £{data['new_amount']}")
    
    def test_add_extra_charge_invalid_link(self, admin_session):
        """POST /api/guest-payment/add-charge/{link_id} - Invalid link ID"""
        response = admin_session.post(f"{BASE_URL}/api/guest-payment/add-charge/invalid-link-id", json={
            "description": "Test",
            "amount": 10.00,
            "category": "other"
        })
        
        assert response.status_code == 404, f"Expected 404 for invalid link: {response.text}"
        print("✓ Add charge to invalid link returns 404")
    
    def test_add_extra_charge_requires_auth(self, fresh_payment_link):
        """POST /api/guest-payment/add-charge/{link_id} - Requires authentication"""
        link_id = fresh_payment_link["link_id"]
        
        public_session = requests.Session()
        public_session.headers.update({"Content-Type": "application/json"})
        response = public_session.post(f"{BASE_URL}/api/guest-payment/add-charge/{link_id}", json={
            "description": "Test",
            "amount": 10.00,
            "category": "other"
        })
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth: {response.status_code}"
        print("✓ Add charge requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
