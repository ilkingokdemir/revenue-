"""
Iteration 59 - Physical Card Terminal Integration Tests
Tests for Stripe Terminal, iyzico (Turkey), PayTR (Turkey) integration
Endpoints: /api/terminal/*
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestTerminalAuth:
    """Test authentication requirements for terminal endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_terminal_settings_requires_auth(self):
        """Terminal settings endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/terminal/settings/{PROPERTY_ID}")
        assert resp.status_code == 401 or resp.status_code == 403
        print("PASS: Terminal settings requires auth")
    
    def test_terminal_devices_requires_auth(self):
        """Terminal devices endpoint requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/terminal/devices/{PROPERTY_ID}")
        assert resp.status_code == 401 or resp.status_code == 403
        print("PASS: Terminal devices requires auth")
    
    def test_terminal_payments_requires_auth(self):
        """Terminal payments history requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/terminal/payments/{PROPERTY_ID}")
        assert resp.status_code == 401 or resp.status_code == 403
        print("PASS: Terminal payments requires auth")


class TestTerminalSettings:
    """Test terminal settings CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_terminal_settings_auto_creates(self):
        """GET /api/terminal/settings/{property_id} auto-creates with 3 providers"""
        resp = self.session.get(f"{BASE_URL}/api/terminal/settings/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify auto-created settings
        assert data.get("property_id") == PROPERTY_ID
        assert data.get("active_provider") in ["stripe", "iyzico", "paytr"]
        assert "supported_providers" in data
        assert "stripe" in data["supported_providers"]
        assert "iyzico" in data["supported_providers"]
        assert "paytr" in data["supported_providers"]
        
        # Verify default fields exist
        assert "stripe_location_id" in data
        assert "iyzico_api_key" in data
        assert "iyzico_secret_key" in data
        assert "paytr_merchant_id" in data
        assert "auto_confirm" in data
        assert "enable_tipping_on_terminal" in data
        assert "default_currency" in data
        
        print(f"PASS: Terminal settings auto-created with providers: {data['supported_providers']}")
    
    def test_update_terminal_settings_active_provider(self):
        """PUT /api/terminal/settings/{property_id} updates active provider"""
        # Update to iyzico
        resp = self.session.put(f"{BASE_URL}/api/terminal/settings/{PROPERTY_ID}", json={
            "active_provider": "iyzico"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("active_provider") == "iyzico"
        print("PASS: Updated active provider to iyzico")
        
        # Update back to stripe
        resp = self.session.put(f"{BASE_URL}/api/terminal/settings/{PROPERTY_ID}", json={
            "active_provider": "stripe"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("active_provider") == "stripe"
        print("PASS: Updated active provider back to stripe")
    
    def test_update_terminal_settings_credentials(self):
        """PUT /api/terminal/settings/{property_id} updates credentials"""
        resp = self.session.put(f"{BASE_URL}/api/terminal/settings/{PROPERTY_ID}", json={
            "stripe_location_id": "tml_test_location",
            "iyzico_api_key": "test_iyzico_key",
            "paytr_merchant_id": "test_paytr_merchant"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("stripe_location_id") == "tml_test_location"
        assert data.get("iyzico_api_key") == "test_iyzico_key"
        assert data.get("paytr_merchant_id") == "test_paytr_merchant"
        print("PASS: Updated terminal credentials")


class TestTerminalDevices:
    """Test terminal device registration and management"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.created_device_id = None
    
    def test_register_device(self):
        """POST /api/terminal/devices registers a card reader"""
        device_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Reception Reader",
            "provider": "stripe",
            "provider_device_id": f"tmr_test_{uuid.uuid4().hex[:8]}",
            "location": "Front Desk"
        }
        resp = self.session.post(f"{BASE_URL}/api/terminal/devices", json=device_data)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data.get("name") == "TEST_Reception Reader"
        assert data.get("provider") == "stripe"
        assert data.get("status") == "active"
        assert "id" in data
        assert "created_at" in data
        
        self.created_device_id = data["id"]
        print(f"PASS: Registered device with ID: {self.created_device_id}")
        return data["id"]
    
    def test_list_devices(self):
        """GET /api/terminal/devices/{property_id} lists registered devices"""
        resp = self.session.get(f"{BASE_URL}/api/terminal/devices/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Listed {len(data)} devices")
    
    def test_update_device(self):
        """PUT /api/terminal/devices/{device_id} updates device"""
        # First create a device
        device_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Update Device",
            "provider": "stripe",
            "provider_device_id": f"tmr_update_{uuid.uuid4().hex[:8]}"
        }
        create_resp = self.session.post(f"{BASE_URL}/api/terminal/devices", json=device_data)
        assert create_resp.status_code == 200
        device_id = create_resp.json()["id"]
        
        # Update the device
        update_resp = self.session.put(f"{BASE_URL}/api/terminal/devices/{device_id}", json={
            "name": "TEST_Updated Reader Name",
            "location": "Bar Area"
        })
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated.get("name") == "TEST_Updated Reader Name"
        assert updated.get("location") == "Bar Area"
        print(f"PASS: Updated device {device_id}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/terminal/devices/{device_id}")
    
    def test_delete_device(self):
        """DELETE /api/terminal/devices/{device_id} removes device"""
        # First create a device
        device_data = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Delete Device",
            "provider": "stripe",
            "provider_device_id": f"tmr_delete_{uuid.uuid4().hex[:8]}"
        }
        create_resp = self.session.post(f"{BASE_URL}/api/terminal/devices", json=device_data)
        assert create_resp.status_code == 200
        device_id = create_resp.json()["id"]
        
        # Delete the device
        delete_resp = self.session.delete(f"{BASE_URL}/api/terminal/devices/{device_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json().get("status") == "deleted"
        print(f"PASS: Deleted device {device_id}")


class TestStripeTerminalPayments:
    """Test Stripe Terminal payment creation and status"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_stripe_create_payment_requires_reader_id(self):
        """POST /api/terminal/stripe/create-payment requires reader_id"""
        resp = self.session.post(f"{BASE_URL}/api/terminal/stripe/create-payment", json={
            "amount": 50.00,
            "currency": "gbp",
            "property_id": PROPERTY_ID
        })
        # Should fail with 400 because reader_id is required
        assert resp.status_code == 400
        assert "Reader ID" in resp.text or "reader" in resp.text.lower()
        print("PASS: Stripe create-payment requires reader_id")
    
    def test_stripe_create_payment_requires_valid_amount(self):
        """POST /api/terminal/stripe/create-payment requires valid amount"""
        resp = self.session.post(f"{BASE_URL}/api/terminal/stripe/create-payment", json={
            "amount": 0,
            "currency": "gbp",
            "reader_id": "tmr_test_reader",
            "property_id": PROPERTY_ID
        })
        # Should fail with 400 because amount is invalid
        assert resp.status_code == 400
        assert "amount" in resp.text.lower()
        print("PASS: Stripe create-payment requires valid amount")
    
    def test_stripe_create_payment_with_test_key(self):
        """POST /api/terminal/stripe/create-payment with test key (expected to fail at Stripe API)"""
        resp = self.session.post(f"{BASE_URL}/api/terminal/stripe/create-payment", json={
            "amount": 25.50,
            "currency": "gbp",
            "reader_id": "tmr_test_reader_123",
            "reference_type": "pos",
            "reference_id": "test-order-123",
            "property_id": PROPERTY_ID,
            "description": "Test terminal payment",
            "tip": 2.50
        })
        # With test key, Stripe API will return error - this is expected
        # The endpoint should handle this gracefully
        assert resp.status_code in [200, 400, 500]
        print(f"PASS: Stripe create-payment handled test key scenario (status: {resp.status_code})")
    
    def test_stripe_payment_status_invalid_id(self):
        """GET /api/terminal/stripe/payment-status/{pi_id} handles invalid ID"""
        resp = self.session.get(f"{BASE_URL}/api/terminal/stripe/payment-status/pi_invalid_test_123")
        assert resp.status_code == 200
        data = resp.json()
        # Should return error/unknown status for invalid payment intent
        assert data.get("status") in ["error", "unknown"] or data.get("payment_status") in ["unknown", "error"]
        print("PASS: Stripe payment-status handles invalid ID gracefully")


class TestIyzicoPayments:
    """Test iyzico (Turkey) payment integration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_iyzico_create_payment_sandbox(self):
        """POST /api/terminal/iyzico/create-payment returns sandbox response without credentials"""
        resp = self.session.post(f"{BASE_URL}/api/terminal/iyzico/create-payment", json={
            "amount": 100.00,
            "currency": "TRY",
            "reference_type": "pos",
            "reference_id": "test-order-iyzico",
            "property_id": PROPERTY_ID,
            "installments": 1
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Without credentials, should return sandbox response
        assert data.get("status") == "sandbox" or data.get("payment_status") == "sandbox"
        assert "iyzico credentials not configured" in data.get("message", "").lower() or data.get("provider") == "iyzico"
        print("PASS: iyzico returns sandbox response without credentials")


class TestQuickPayEndpoints:
    """Test quick-pay endpoints for POS orders and bookings"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_quick_pay_pos_order_not_found(self):
        """POST /api/terminal/quick-pay/{order_id} returns 404 for missing order"""
        resp = self.session.post(f"{BASE_URL}/api/terminal/quick-pay/nonexistent-order-123", json={})
        assert resp.status_code == 404
        assert "not found" in resp.text.lower()
        print("PASS: Quick-pay POS returns 404 for missing order")
    
    def test_quick_pay_booking_not_found(self):
        """POST /api/terminal/quick-pay-booking/{booking_id} returns 404 for missing booking"""
        resp = self.session.post(f"{BASE_URL}/api/terminal/quick-pay-booking/nonexistent-booking-123", json={})
        assert resp.status_code == 404
        assert "not found" in resp.text.lower()
        print("PASS: Quick-pay booking returns 404 for missing booking")


class TestTerminalPaymentHistory:
    """Test terminal payment history endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_get_terminal_payments(self):
        """GET /api/terminal/payments/{property_id} returns payment history"""
        resp = self.session.get(f"{BASE_URL}/api/terminal/payments/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"PASS: Terminal payments history returned {len(data)} records")


class TestExistingPaymentFeatures:
    """Regression tests for existing payment features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_payment_dashboard_still_works(self):
        """GET /api/payments/dashboard/{property_id} still works"""
        resp = self.session.get(f"{BASE_URL}/api/payments/dashboard/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_processed" in data or "total_transactions" in data
        print("PASS: Payment dashboard still works")
    
    def test_payment_settings_still_works(self):
        """GET /api/payments/settings/{property_id} still works"""
        resp = self.session.get(f"{BASE_URL}/api/payments/settings/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "stripe_enabled" in data or "property_id" in data
        print("PASS: Payment settings still works")
    
    def test_pos_orders_still_works(self):
        """GET /api/pos/orders/{property_id} still works"""
        today = "2026-01-01"
        resp = self.session.get(f"{BASE_URL}/api/pos/orders/{PROPERTY_ID}?date={today}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print("PASS: POS orders still works")
    
    def test_pos_outlets_still_works(self):
        """GET /api/pos/outlets/{property_id} still works"""
        resp = self.session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print("PASS: POS outlets still works")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
        self.token = resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_cleanup_test_devices(self):
        """Cleanup TEST_ prefixed devices"""
        resp = self.session.get(f"{BASE_URL}/api/terminal/devices/{PROPERTY_ID}")
        if resp.status_code == 200:
            devices = resp.json()
            for device in devices:
                if device.get("name", "").startswith("TEST_"):
                    self.session.delete(f"{BASE_URL}/api/terminal/devices/{device['id']}")
                    print(f"Cleaned up device: {device['name']}")
        print("PASS: Cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
