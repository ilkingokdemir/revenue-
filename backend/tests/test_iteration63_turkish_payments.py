"""
Iteration 63 - Turkish Payment Gateway Tests (iyzico & PayTR)
Tests virtual checkout flows for Turkish payment providers in demo/sandbox mode
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client

@pytest.fixture(scope="module")
def test_booking(authenticated_client):
    """Create a test booking for payment tests"""
    # First get property info
    prop_resp = authenticated_client.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
    if prop_resp.status_code != 200:
        pytest.skip("Could not fetch property")
    
    property_data = prop_resp.json()
    room_types = property_data.get("room_types", [])
    if not room_types:
        pytest.skip("No room types available")
    
    room_type = room_types[0]
    
    # Create a booking
    check_in = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    check_out = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")
    
    booking_data = {
        "property_id": "aldgate-flats",
        "room_type_id": room_type.get("id"),
        "guest_name": "TEST_Turkish_Payment_Guest",
        "guest_email": "test_turkish@example.com",
        "guest_phone": "+905551234567",
        "check_in": check_in,
        "check_out": check_out,
        "adults": 2,
        "children": 0,
        "rooms": 1,
        "special_requests": "Turkish payment test booking"
    }
    
    response = authenticated_client.post(f"{BASE_URL}/api/booking/reserve", json=booking_data)
    if response.status_code not in [200, 201]:
        pytest.skip(f"Could not create test booking: {response.text}")
    
    booking = response.json()
    yield booking
    
    # Cleanup - delete test booking
    try:
        authenticated_client.delete(f"{BASE_URL}/api/bookings/{booking.get('id')}")
    except:
        pass


class TestIyzicoCheckout:
    """Tests for iyzico Turkish payment checkout"""
    
    def test_iyzico_checkout_creates_session(self, api_client, test_booking):
        """POST /api/payments/iyzico-checkout - Creates iyzico checkout session"""
        response = api_client.post(f"{BASE_URL}/api/payments/iyzico-checkout", json={
            "booking_id": test_booking.get("id"),
            "origin_url": "https://review-hub-108.preview.emergentagent.com",
            "currency": "TRY",
            "installments": 6
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "url" in data, "Response should contain checkout URL"
        assert "session_id" in data, "Response should contain session_id"
        assert data.get("provider") == "iyzico", "Provider should be iyzico"
        assert "iyzico_" in data.get("session_id", ""), "Session ID should have iyzico prefix"
        
        # In demo mode, URL should point to turkish-pay page
        assert "turkish-pay" in data.get("url", "") or "iyzipay" in data.get("url", ""), \
            "URL should be demo turkish-pay page or real iyzico URL"
        
        print(f"iyzico checkout URL: {data.get('url')[:100]}...")
        print(f"Session ID: {data.get('session_id')}")
        print(f"Mode: {data.get('mode', 'production')}")
    
    def test_iyzico_checkout_invalid_booking(self, api_client):
        """POST /api/payments/iyzico-checkout - Returns 404 for invalid booking"""
        response = api_client.post(f"{BASE_URL}/api/payments/iyzico-checkout", json={
            "booking_id": "nonexistent-booking-id",
            "origin_url": "https://example.com"
        })
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_iyzico_checkout_url_contains_params(self, api_client, test_booking):
        """Verify iyzico demo URL contains required parameters"""
        response = api_client.post(f"{BASE_URL}/api/payments/iyzico-checkout", json={
            "booking_id": test_booking.get("id"),
            "origin_url": "https://review-hub-108.preview.emergentagent.com",
            "currency": "TRY",
            "installments": 12
        })
        
        assert response.status_code == 200
        data = response.json()
        url = data.get("url", "")
        
        # In demo mode, URL should contain these params
        if "turkish-pay" in url:
            assert "provider=iyzico" in url, "URL should have provider=iyzico"
            assert "amount=" in url, "URL should have amount parameter"
            assert "token=" in url, "URL should have token parameter"
            print(f"Demo URL params verified: {url[:150]}...")


class TestPayTRCheckout:
    """Tests for PayTR Turkish payment checkout"""
    
    def test_paytr_checkout_creates_session(self, api_client, test_booking):
        """POST /api/payments/paytr-checkout - Creates PayTR checkout session"""
        response = api_client.post(f"{BASE_URL}/api/payments/paytr-checkout", json={
            "booking_id": test_booking.get("id"),
            "origin_url": "https://review-hub-108.preview.emergentagent.com",
            "currency": "TRY",
            "installments": 9
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "url" in data, "Response should contain checkout URL"
        assert "session_id" in data, "Response should contain session_id"
        assert data.get("provider") == "paytr", "Provider should be paytr"
        assert "paytr_" in data.get("session_id", ""), "Session ID should have paytr prefix"
        
        # In demo mode, URL should point to turkish-pay page
        assert "turkish-pay" in data.get("url", "") or "paytr.com" in data.get("url", ""), \
            "URL should be demo turkish-pay page or real PayTR URL"
        
        print(f"PayTR checkout URL: {data.get('url')[:100]}...")
        print(f"Session ID: {data.get('session_id')}")
        print(f"Mode: {data.get('mode', 'production')}")
    
    def test_paytr_checkout_invalid_booking(self, api_client):
        """POST /api/payments/paytr-checkout - Returns 404 for invalid booking"""
        response = api_client.post(f"{BASE_URL}/api/payments/paytr-checkout", json={
            "booking_id": "nonexistent-booking-id",
            "origin_url": "https://example.com"
        })
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_paytr_checkout_url_contains_params(self, api_client, test_booking):
        """Verify PayTR demo URL contains required parameters"""
        response = api_client.post(f"{BASE_URL}/api/payments/paytr-checkout", json={
            "booking_id": test_booking.get("id"),
            "origin_url": "https://review-hub-108.preview.emergentagent.com",
            "currency": "TRY",
            "installments": 3
        })
        
        assert response.status_code == 200
        data = response.json()
        url = data.get("url", "")
        
        # In demo mode, URL should contain these params
        if "turkish-pay" in url:
            assert "provider=paytr" in url, "URL should have provider=paytr"
            assert "amount=" in url, "URL should have amount parameter"
            assert "token=" in url, "URL should have token parameter"
            print(f"Demo URL params verified: {url[:150]}...")


class TestTurkishDemoConfirm:
    """Tests for Turkish demo payment confirmation"""
    
    def test_demo_confirm_iyzico(self, api_client, test_booking):
        """POST /api/payments/turkish-demo-confirm - Confirms iyzico demo payment"""
        # First create an iyzico checkout session
        checkout_resp = api_client.post(f"{BASE_URL}/api/payments/iyzico-checkout", json={
            "booking_id": test_booking.get("id"),
            "origin_url": "https://review-hub-108.preview.emergentagent.com",
            "currency": "TRY"
        })
        assert checkout_resp.status_code == 200
        session_id = checkout_resp.json().get("session_id", "")
        token = session_id.replace("iyzico_", "")
        
        # Confirm the demo payment
        confirm_resp = api_client.post(f"{BASE_URL}/api/payments/turkish-demo-confirm", json={
            "token": token,
            "provider": "iyzico"
        })
        
        assert confirm_resp.status_code == 200, f"Expected 200, got {confirm_resp.status_code}: {confirm_resp.text}"
        
        data = confirm_resp.json()
        assert data.get("status") == "paid", "Status should be 'paid'"
        assert data.get("provider") == "iyzico", "Provider should be iyzico"
        assert data.get("demo_mode") == True, "Should indicate demo mode"
        assert "amount" in data, "Should return amount"
        assert "booking_ref" in data, "Should return booking reference"
        
        print(f"iyzico demo payment confirmed: {data}")
    
    def test_demo_confirm_paytr(self, api_client, test_booking):
        """POST /api/payments/turkish-demo-confirm - Confirms PayTR demo payment"""
        # First create a PayTR checkout session
        checkout_resp = api_client.post(f"{BASE_URL}/api/payments/paytr-checkout", json={
            "booking_id": test_booking.get("id"),
            "origin_url": "https://review-hub-108.preview.emergentagent.com",
            "currency": "TRY"
        })
        assert checkout_resp.status_code == 200
        session_id = checkout_resp.json().get("session_id", "")
        token = session_id.replace("paytr_", "")
        
        # Confirm the demo payment
        confirm_resp = api_client.post(f"{BASE_URL}/api/payments/turkish-demo-confirm", json={
            "token": token,
            "provider": "paytr"
        })
        
        assert confirm_resp.status_code == 200, f"Expected 200, got {confirm_resp.status_code}: {confirm_resp.text}"
        
        data = confirm_resp.json()
        assert data.get("status") == "paid", "Status should be 'paid'"
        assert data.get("provider") == "paytr", "Provider should be paytr"
        assert data.get("demo_mode") == True, "Should indicate demo mode"
        
        print(f"PayTR demo payment confirmed: {data}")
    
    def test_demo_confirm_invalid_token(self, api_client):
        """POST /api/payments/turkish-demo-confirm - Returns 404 for invalid token"""
        response = api_client.post(f"{BASE_URL}/api/payments/turkish-demo-confirm", json={
            "token": "invalid-token-12345",
            "provider": "iyzico"
        })
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestTransactionRecords:
    """Tests for payment transaction records"""
    
    def test_iyzico_creates_transaction_record(self, authenticated_client, test_booking):
        """Verify iyzico checkout creates transaction record"""
        # Create checkout
        checkout_resp = authenticated_client.post(f"{BASE_URL}/api/payments/iyzico-checkout", json={
            "booking_id": test_booking.get("id"),
            "origin_url": "https://review-hub-108.preview.emergentagent.com",
            "currency": "TRY",
            "installments": 6
        })
        assert checkout_resp.status_code == 200
        session_id = checkout_resp.json().get("session_id")
        
        # Check transactions list
        tx_resp = authenticated_client.get(f"{BASE_URL}/api/payments/transactions/aldgate-flats")
        assert tx_resp.status_code == 200
        
        transactions = tx_resp.json()
        iyzico_tx = next((t for t in transactions if t.get("session_id") == session_id), None)
        
        assert iyzico_tx is not None, "iyzico transaction should be in list"
        assert iyzico_tx.get("payment_method") == "iyzico", "Payment method should be iyzico"
        assert iyzico_tx.get("currency") == "TRY", "Currency should be TRY"
        assert iyzico_tx.get("type") == "booking", "Type should be booking"
        
        print(f"iyzico transaction record: {iyzico_tx.get('id')}")
    
    def test_paytr_creates_transaction_record(self, authenticated_client, test_booking):
        """Verify PayTR checkout creates transaction record"""
        # Create checkout
        checkout_resp = authenticated_client.post(f"{BASE_URL}/api/payments/paytr-checkout", json={
            "booking_id": test_booking.get("id"),
            "origin_url": "https://review-hub-108.preview.emergentagent.com",
            "currency": "TRY",
            "installments": 3
        })
        assert checkout_resp.status_code == 200
        session_id = checkout_resp.json().get("session_id")
        
        # Check transactions list
        tx_resp = authenticated_client.get(f"{BASE_URL}/api/payments/transactions/aldgate-flats")
        assert tx_resp.status_code == 200
        
        transactions = tx_resp.json()
        paytr_tx = next((t for t in transactions if t.get("session_id") == session_id), None)
        
        assert paytr_tx is not None, "PayTR transaction should be in list"
        assert paytr_tx.get("payment_method") == "paytr", "Payment method should be paytr"
        assert paytr_tx.get("currency") == "TRY", "Currency should be TRY"
        
        print(f"PayTR transaction record: {paytr_tx.get('id')}")


class TestBookingEnginePaymentOptions:
    """Tests for booking engine property endpoint with payment options"""
    
    def test_property_endpoint_returns_data(self, api_client):
        """GET /api/booking/property/{id} - Returns property with room types"""
        response = api_client.get(f"{BASE_URL}/api/booking/property/aldgate-flats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "name" in data, "Property should have name"
        assert "room_types" in data, "Property should have room_types"
        assert len(data.get("room_types", [])) > 0, "Property should have at least one room type"
        
        print(f"Property: {data.get('name')}, Room types: {len(data.get('room_types', []))}")


class TestPaymentCallbacks:
    """Tests for Turkish payment callbacks"""
    
    def test_iyzico_callback_endpoint_exists(self, api_client):
        """POST /api/payments/iyzico-callback - Endpoint exists"""
        # Just verify endpoint exists (would need real callback data to test fully)
        response = api_client.post(f"{BASE_URL}/api/payments/iyzico-callback", data={
            "token": "test-token",
            "status": "success"
        })
        # Should return 200 even with test data
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_paytr_callback_endpoint_exists(self, api_client):
        """POST /api/payments/paytr-callback - Endpoint exists"""
        response = api_client.post(f"{BASE_URL}/api/payments/paytr-callback", data={
            "merchant_oid": "test-order",
            "status": "success"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
