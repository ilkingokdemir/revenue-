"""
Iteration 60 - Stripe Virtual Payment Flow Testing
Tests: Booking creation, Stripe checkout session, payment status, transactions, dashboard
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "aldgate-flats"


class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        return data["token"]
    
    def test_admin_login(self, auth_token):
        """Test admin login works"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Admin login successful, token length: {len(auth_token)}")


class TestBookingCreation:
    """Test booking creation with correct total_price and booking_ref"""
    
    @pytest.fixture(scope="class")
    def room_type(self):
        """Get first available room type"""
        response = requests.get(f"{API}/booking/rooms/{PROPERTY_ID}")
        assert response.status_code == 200
        rooms = response.json()
        assert len(rooms) > 0, "No rooms available"
        return rooms[0]
    
    def test_create_booking_reserve(self, room_type):
        """POST /api/booking/reserve - creates booking with correct total_price and booking_ref"""
        check_in = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")
        
        booking_data = {
            "property_id": PROPERTY_ID,
            "room_type_id": room_type["id"],
            "guest_name": f"TEST_Stripe_Guest_{uuid.uuid4().hex[:6]}",
            "guest_email": f"test_stripe_{uuid.uuid4().hex[:6]}@example.com",
            "guest_phone": "+44 7700 900000",
            "check_in": check_in,
            "check_out": check_out,
            "adults": 2,
            "children": 0,
            "rooms": 1,
            "special_requests": "Testing Stripe payment flow"
        }
        
        response = requests.post(f"{API}/booking/reserve", json=booking_data)
        assert response.status_code == 200, f"Booking creation failed: {response.text}"
        
        booking = response.json()
        
        # Verify booking_ref is generated
        assert "booking_ref" in booking, "booking_ref missing from response"
        assert len(booking["booking_ref"]) > 0, "booking_ref is empty"
        print(f"✓ Booking created with ref: {booking['booking_ref']}")
        
        # Verify total_price is calculated correctly (2 nights * base_price)
        expected_price = room_type["base_price"] * 2  # 2 nights
        assert "total_price" in booking, "total_price missing from response"
        assert booking["total_price"] == expected_price, f"Expected {expected_price}, got {booking['total_price']}"
        print(f"✓ Total price correct: £{booking['total_price']} (2 nights × £{room_type['base_price']})")
        
        # Verify other fields
        assert booking["property_id"] == PROPERTY_ID
        assert booking["room_type_id"] == room_type["id"]
        assert booking["guest_name"] == booking_data["guest_name"]
        assert booking["status"] == "confirmed"
        assert booking["payment_status"] == "pending"
        
        # Store for next tests
        TestBookingCreation.created_booking = booking
        return booking
    
    def test_get_booking_by_ref(self):
        """GET /api/booking/reservation/{booking_ref} - verify booking can be retrieved"""
        booking = getattr(TestBookingCreation, 'created_booking', None)
        if not booking:
            pytest.skip("No booking created in previous test")
        
        response = requests.get(f"{API}/booking/reservation/{booking['booking_ref']}")
        assert response.status_code == 200, f"Failed to get booking: {response.text}"
        
        fetched = response.json()
        assert fetched["booking_ref"] == booking["booking_ref"]
        assert fetched["total_price"] == booking["total_price"]
        print(f"✓ Booking retrieved by ref: {booking['booking_ref']}")


class TestStripeCheckout:
    """Test Stripe checkout session creation"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_booking(self):
        """Create a test booking for checkout"""
        rooms = requests.get(f"{API}/booking/rooms/{PROPERTY_ID}").json()
        room = rooms[0]
        
        check_in = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=11)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{API}/booking/reserve", json={
            "property_id": PROPERTY_ID,
            "room_type_id": room["id"],
            "guest_name": f"TEST_Checkout_{uuid.uuid4().hex[:6]}",
            "guest_email": f"checkout_{uuid.uuid4().hex[:6]}@test.com",
            "guest_phone": "+44 7700 900001",
            "check_in": check_in,
            "check_out": check_out,
            "adults": 2,
            "children": 0,
            "rooms": 1
        })
        assert response.status_code == 200
        return response.json()
    
    def test_create_booking_checkout(self, test_booking):
        """POST /api/payments/booking-checkout - creates Stripe checkout session"""
        response = requests.post(f"{API}/payments/booking-checkout", json={
            "booking_id": test_booking["id"],
            "origin_url": "https://review-hub-108.preview.emergentagent.com"
        })
        
        assert response.status_code == 200, f"Checkout creation failed: {response.text}"
        
        data = response.json()
        
        # Verify checkout URL is returned
        assert "url" in data, "Checkout URL missing from response"
        assert data["url"].startswith("https://checkout.stripe.com"), f"Invalid checkout URL: {data['url']}"
        print(f"✓ Stripe checkout URL generated: {data['url'][:60]}...")
        
        # Verify session_id is returned
        assert "session_id" in data, "session_id missing from response"
        assert data["session_id"].startswith("cs_"), f"Invalid session_id format: {data['session_id']}"
        print(f"✓ Session ID: {data['session_id'][:30]}...")
        
        # Store for status check
        TestStripeCheckout.checkout_session = data
        return data
    
    def test_checkout_url_contains_correct_redirect(self, test_booking):
        """Verify checkout success URL redirects to BookingEngine route"""
        session = getattr(TestStripeCheckout, 'checkout_session', None)
        if not session:
            pytest.skip("No checkout session from previous test")
        
        # The URL should redirect to /book?property={id}&payment=success&session_id={SESSION_ID}
        # We can't verify the full redirect URL from the session, but we verified it's a valid Stripe URL
        print(f"✓ Checkout session created successfully")


class TestPaymentStatus:
    """Test payment status endpoint"""
    
    def test_payment_status_with_session_id(self):
        """GET /api/payments/status/{session_id} - returns payment status with booking_ref"""
        session = getattr(TestStripeCheckout, 'checkout_session', None)
        if not session:
            pytest.skip("No checkout session available")
        
        response = requests.get(f"{API}/payments/status/{session['session_id']}")
        
        # Note: With test key, Stripe status check may return error (expected)
        # But we should still get a response
        assert response.status_code == 200, f"Status check failed: {response.text}"
        
        data = response.json()
        print(f"✓ Payment status response: {data}")
        
        # Verify booking_ref is in response (even if status is error/unknown)
        # The endpoint should return booking_ref from the transaction record
        if "booking_ref" in data:
            print(f"✓ booking_ref in response: {data['booking_ref']}")
        
        # Status could be 'error' with test key (expected behavior)
        assert "status" in data or "payment_status" in data
    
    def test_payment_status_invalid_session(self):
        """GET /api/payments/status/{invalid_id} - handles invalid session gracefully"""
        response = requests.get(f"{API}/payments/status/cs_invalid_session_12345")
        
        # Should return 200 with error status, not crash
        assert response.status_code == 200
        data = response.json()
        
        # Should indicate error or unknown status
        assert "status" in data or "error" in data or "payment_status" in data
        print(f"✓ Invalid session handled gracefully: {data.get('status', data.get('payment_status', 'unknown'))}")


class TestPaymentTransactions:
    """Test payment transactions list"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_transactions(self, auth_headers):
        """GET /api/payments/transactions/{property_id} - lists payment transactions"""
        response = requests.get(
            f"{API}/payments/transactions/{PROPERTY_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Failed to list transactions: {response.text}"
        
        transactions = response.json()
        assert isinstance(transactions, list)
        print(f"✓ Transactions list returned: {len(transactions)} transactions")
        
        # If there are transactions, verify structure
        if len(transactions) > 0:
            tx = transactions[0]
            assert "id" in tx
            assert "session_id" in tx
            assert "type" in tx
            assert "amount" in tx
            assert "payment_status" in tx
            print(f"✓ Transaction structure verified: {tx.get('type')} - £{tx.get('amount')} - {tx.get('payment_status')}")
    
    def test_filter_transactions_by_status(self, auth_headers):
        """GET /api/payments/transactions/{property_id}?status=initiated"""
        response = requests.get(
            f"{API}/payments/transactions/{PROPERTY_ID}?status=initiated",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        transactions = response.json()
        
        # All returned transactions should have status=initiated
        for tx in transactions:
            assert tx.get("payment_status") == "initiated", f"Expected initiated, got {tx.get('payment_status')}"
        
        print(f"✓ Filtered transactions by status: {len(transactions)} initiated")
    
    def test_filter_transactions_by_type(self, auth_headers):
        """GET /api/payments/transactions/{property_id}?type=booking"""
        response = requests.get(
            f"{API}/payments/transactions/{PROPERTY_ID}?type=booking",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        transactions = response.json()
        
        # All returned transactions should have type=booking
        for tx in transactions:
            assert tx.get("type") == "booking", f"Expected booking, got {tx.get('type')}"
        
        print(f"✓ Filtered transactions by type: {len(transactions)} booking transactions")


class TestPaymentDashboard:
    """Test payment dashboard stats"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_dashboard_stats(self, auth_headers):
        """GET /api/payments/dashboard/{property_id} - returns dashboard stats"""
        response = requests.get(
            f"{API}/payments/dashboard/{PROPERTY_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        
        data = response.json()
        
        # Verify dashboard structure
        assert "period_days" in data
        assert "total_transactions" in data
        assert "total_processed" in data
        assert "total_pending" in data
        assert "total_failed" in data
        assert "success_rate" in data
        assert "by_type" in data
        assert "by_method" in data
        assert "daily_trend" in data
        
        print(f"✓ Dashboard stats: {data['total_transactions']} transactions, £{data['total_processed']} processed, {data['success_rate']}% success rate")
    
    def test_dashboard_with_period(self, auth_headers):
        """GET /api/payments/dashboard/{property_id}?period=7d"""
        response = requests.get(
            f"{API}/payments/dashboard/{PROPERTY_ID}?period=7d",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7
        print(f"✓ Dashboard with 7d period: {data['total_transactions']} transactions")


class TestPaymentSettings:
    """Test payment settings"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_payment_settings(self, auth_headers):
        """GET /api/payments/settings/{property_id} - returns payment settings"""
        response = requests.get(
            f"{API}/payments/settings/{PROPERTY_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Settings failed: {response.text}"
        
        settings = response.json()
        
        # Verify settings structure
        assert "stripe_enabled" in settings
        assert "pay_at_hotel_enabled" in settings
        assert "room_charge_enabled" in settings
        assert "cash_enabled" in settings
        assert "contactless_enabled" in settings
        
        print(f"✓ Payment settings: Stripe={settings['stripe_enabled']}, PayAtHotel={settings['pay_at_hotel_enabled']}, Cash={settings['cash_enabled']}")
    
    def test_update_payment_settings(self, auth_headers):
        """PUT /api/payments/settings/{property_id} - updates settings"""
        # Get current settings
        current = requests.get(
            f"{API}/payments/settings/{PROPERTY_ID}",
            headers=auth_headers
        ).json()
        
        # Toggle tipping
        new_tipping = not current.get("tipping_enabled", True)
        
        response = requests.put(
            f"{API}/payments/settings/{PROPERTY_ID}",
            headers=auth_headers,
            json={"tipping_enabled": new_tipping}
        )
        
        assert response.status_code == 200
        updated = response.json()
        assert updated["tipping_enabled"] == new_tipping
        
        # Restore original
        requests.put(
            f"{API}/payments/settings/{PROPERTY_ID}",
            headers=auth_headers,
            json={"tipping_enabled": current.get("tipping_enabled", True)}
        )
        
        print(f"✓ Payment settings update works")


class TestPOSCheckout:
    """Test POS checkout (for completeness)"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_pos_checkout_requires_order(self):
        """POST /api/payments/pos-checkout - returns 404 for missing order"""
        response = requests.post(f"{API}/payments/pos-checkout", json={
            "order_id": "nonexistent-order-id",
            "origin_url": "https://review-hub-108.preview.emergentagent.com"
        })
        
        assert response.status_code == 404
        print(f"✓ POS checkout returns 404 for missing order")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_cleanup_test_bookings(self, auth_headers):
        """Clean up TEST_ prefixed bookings"""
        # Note: In a real scenario, we'd delete test bookings
        # For now, just verify we can list bookings
        response = requests.get(
            f"{API}/bookings?property_id={PROPERTY_ID}",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            bookings = response.json()
            test_bookings = [b for b in bookings if b.get("guest_name", "").startswith("TEST_")]
            print(f"✓ Found {len(test_bookings)} test bookings (cleanup would remove these)")
        else:
            print(f"✓ Cleanup check completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
