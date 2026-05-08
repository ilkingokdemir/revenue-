"""
Iteration 58 - Payment Gateway Module Tests
Tests for Stripe checkout, payment transactions, dashboard, settings, webhook handling
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@hotelbox.com"
TEST_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "aldgate-flats"


class TestPaymentGatewayAuth:
    """Authentication tests for payment endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_auth_token(self):
        """Get authentication token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_payment_dashboard_requires_auth(self):
        """Payment dashboard should require authentication"""
        response = self.session.get(f"{BASE_URL}/api/payments/dashboard/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Payment dashboard requires auth")
    
    def test_payment_transactions_requires_auth(self):
        """Payment transactions should require authentication"""
        response = self.session.get(f"{BASE_URL}/api/payments/transactions/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Payment transactions requires auth")
    
    def test_payment_settings_requires_auth(self):
        """Payment settings should require authentication"""
        response = self.session.get(f"{BASE_URL}/api/payments/settings/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Payment settings requires auth")


class TestPaymentDashboard:
    """Payment dashboard analytics tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_payment_dashboard_default_period(self):
        """GET /api/payments/dashboard/{property_id} - default 30d period"""
        response = self.session.get(f"{BASE_URL}/api/payments/dashboard/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify dashboard structure
        assert "period_days" in data, "Missing period_days"
        assert "total_transactions" in data, "Missing total_transactions"
        assert "total_processed" in data, "Missing total_processed"
        assert "total_pending" in data, "Missing total_pending"
        assert "total_failed" in data, "Missing total_failed"
        assert "success_rate" in data, "Missing success_rate"
        assert "by_type" in data, "Missing by_type"
        assert "by_method" in data, "Missing by_method"
        assert "daily_trend" in data, "Missing daily_trend"
        
        assert data["period_days"] == 30, f"Expected 30 days, got {data['period_days']}"
        print(f"PASS: Payment dashboard returns correct structure. Total transactions: {data['total_transactions']}")
    
    def test_payment_dashboard_7d_period(self):
        """GET /api/payments/dashboard/{property_id}?period=7d"""
        response = self.session.get(f"{BASE_URL}/api/payments/dashboard/{PROPERTY_ID}?period=7d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["period_days"] == 7, f"Expected 7 days, got {data['period_days']}"
        print("PASS: Payment dashboard 7d period works")
    
    def test_payment_dashboard_90d_period(self):
        """GET /api/payments/dashboard/{property_id}?period=90d"""
        response = self.session.get(f"{BASE_URL}/api/payments/dashboard/{PROPERTY_ID}?period=90d")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["period_days"] == 90, f"Expected 90 days, got {data['period_days']}"
        print("PASS: Payment dashboard 90d period works")


class TestPaymentTransactions:
    """Payment transactions list tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_list_transactions_no_filter(self):
        """GET /api/payments/transactions/{property_id} - no filters"""
        response = self.session.get(f"{BASE_URL}/api/payments/transactions/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of transactions"
        print(f"PASS: Transactions list returns {len(data)} transactions")
    
    def test_list_transactions_filter_by_status(self):
        """GET /api/payments/transactions/{property_id}?status=paid"""
        response = self.session.get(f"{BASE_URL}/api/payments/transactions/{PROPERTY_ID}?status=paid")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of transactions"
        # Verify all returned transactions have status=paid
        for tx in data:
            assert tx.get("payment_status") == "paid", f"Expected paid status, got {tx.get('payment_status')}"
        print(f"PASS: Transactions filter by status=paid returns {len(data)} transactions")
    
    def test_list_transactions_filter_by_type(self):
        """GET /api/payments/transactions/{property_id}?type=booking"""
        response = self.session.get(f"{BASE_URL}/api/payments/transactions/{PROPERTY_ID}?type=booking")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of transactions"
        # Verify all returned transactions have type=booking
        for tx in data:
            assert tx.get("type") == "booking", f"Expected booking type, got {tx.get('type')}"
        print(f"PASS: Transactions filter by type=booking returns {len(data)} transactions")
    
    def test_list_transactions_filter_by_type_pos(self):
        """GET /api/payments/transactions/{property_id}?type=pos"""
        response = self.session.get(f"{BASE_URL}/api/payments/transactions/{PROPERTY_ID}?type=pos")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of transactions"
        for tx in data:
            assert tx.get("type") == "pos", f"Expected pos type, got {tx.get('type')}"
        print(f"PASS: Transactions filter by type=pos returns {len(data)} transactions")


class TestPaymentSettings:
    """Payment settings CRUD tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_get_payment_settings_auto_create(self):
        """GET /api/payments/settings/{property_id} - auto-creates defaults"""
        response = self.session.get(f"{BASE_URL}/api/payments/settings/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify default settings structure
        assert "property_id" in data, "Missing property_id"
        assert "stripe_enabled" in data, "Missing stripe_enabled"
        assert "pay_at_hotel_enabled" in data, "Missing pay_at_hotel_enabled"
        assert "room_charge_enabled" in data, "Missing room_charge_enabled"
        assert "cash_enabled" in data, "Missing cash_enabled"
        assert "contactless_enabled" in data, "Missing contactless_enabled"
        assert "accepted_cards" in data, "Missing accepted_cards"
        assert "default_currency" in data, "Missing default_currency"
        assert "tipping_enabled" in data, "Missing tipping_enabled"
        assert "tip_percentages" in data, "Missing tip_percentages"
        
        # Verify defaults
        assert data["stripe_enabled"] == True, "stripe_enabled should be True by default"
        assert data["default_currency"] == "GBP", f"Expected GBP, got {data['default_currency']}"
        assert data["tipping_enabled"] == True, "tipping_enabled should be True by default"
        print(f"PASS: Payment settings auto-created with defaults. Currency: {data['default_currency']}")
    
    def test_update_payment_settings(self):
        """PUT /api/payments/settings/{property_id} - update settings"""
        # First get current settings
        get_response = self.session.get(f"{BASE_URL}/api/payments/settings/{PROPERTY_ID}")
        assert get_response.status_code == 200
        
        # Update settings
        updates = {
            "stripe_enabled": True,
            "cash_enabled": False,
            "tipping_enabled": True,
            "default_currency": "EUR"
        }
        response = self.session.put(f"{BASE_URL}/api/payments/settings/{PROPERTY_ID}", json=updates)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["cash_enabled"] == False, "cash_enabled should be False"
        assert data["default_currency"] == "EUR", f"Expected EUR, got {data['default_currency']}"
        print("PASS: Payment settings updated successfully")
        
        # Restore defaults
        restore = {"cash_enabled": True, "default_currency": "GBP"}
        self.session.put(f"{BASE_URL}/api/payments/settings/{PROPERTY_ID}", json=restore)
    
    def test_update_payment_settings_tipping(self):
        """PUT /api/payments/settings/{property_id} - update tipping settings"""
        updates = {
            "tipping_enabled": False,
            "tip_percentages": [5, 10, 15, 25]
        }
        response = self.session.put(f"{BASE_URL}/api/payments/settings/{PROPERTY_ID}", json=updates)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["tipping_enabled"] == False, "tipping_enabled should be False"
        assert data["tip_percentages"] == [5, 10, 15, 25], f"Expected [5,10,15,25], got {data['tip_percentages']}"
        print("PASS: Tipping settings updated successfully")
        
        # Restore defaults
        restore = {"tipping_enabled": True, "tip_percentages": [10, 15, 20]}
        self.session.put(f"{BASE_URL}/api/payments/settings/{PROPERTY_ID}", json=restore)


class TestBookingCheckout:
    """Booking checkout tests (Stripe integration)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_booking_checkout_missing_booking(self):
        """POST /api/payments/booking-checkout - booking not found"""
        response = self.session.post(f"{BASE_URL}/api/payments/booking-checkout", json={
            "booking_id": "nonexistent-booking-id",
            "origin_url": "https://example.com"
        })
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Booking checkout returns 404 for missing booking")


class TestPOSCheckout:
    """POS checkout tests (Stripe integration)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_pos_checkout_missing_order(self):
        """POST /api/payments/pos-checkout - order not found"""
        response = self.session.post(f"{BASE_URL}/api/payments/pos-checkout", json={
            "order_id": "nonexistent-order-id",
            "origin_url": "https://example.com"
        })
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: POS checkout returns 404 for missing order")


class TestPaymentStatus:
    """Payment status check tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_payment_status_invalid_session(self):
        """GET /api/payments/status/{session_id} - invalid session"""
        response = self.session.get(f"{BASE_URL}/api/payments/status/invalid-session-id")
        # Should return error status for invalid session
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have error or unknown status
        assert "status" in data or "payment_status" in data, "Missing status field"
        print(f"PASS: Payment status handles invalid session. Response: {data.get('status', data.get('payment_status'))}")


class TestStripeWebhook:
    """Stripe webhook handler tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_webhook_endpoint_exists(self):
        """POST /api/webhook/stripe - endpoint exists"""
        # Send empty body - should not crash
        response = self.session.post(f"{BASE_URL}/api/webhook/stripe", data=b"")
        # Should return 200 with error status (no valid signature)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Missing status field"
        print(f"PASS: Webhook endpoint exists and handles empty body. Status: {data.get('status')}")


class TestKioskEndpoints:
    """Kiosk public endpoints tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_kiosk_order_no_auth_required(self):
        """POST /api/pos/kiosk/order - public endpoint, no auth"""
        # Create a test kiosk order
        order_data = {
            "property_id": PROPERTY_ID,
            "outlet_id": "test-outlet",
            "outlet_name": "Test Outlet",
            "guest_name": "TEST_Kiosk Guest",
            "payment_method": "card",
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "TEST_Coffee",
                    "price": 3.50,
                    "cost": 1.00,
                    "quantity": 2,
                    "vat_rate": 20,
                    "category": "Hot Drinks"
                }
            ]
        }
        response = self.session.post(f"{BASE_URL}/api/pos/kiosk/order", json=order_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "order_number" in data, "Missing order_number"
        assert "total" in data, "Missing total"
        assert data["order_number"].startswith("KSK-"), f"Expected KSK- prefix, got {data['order_number']}"
        print(f"PASS: Kiosk order created without auth. Order: {data['order_number']}, Total: £{data['total']}")
    
    def test_kiosk_order_empty_items_rejected(self):
        """POST /api/pos/kiosk/order - empty items rejected"""
        order_data = {
            "property_id": PROPERTY_ID,
            "outlet_id": "test-outlet",
            "items": []
        }
        response = self.session.post(f"{BASE_URL}/api/pos/kiosk/order", json=order_data)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Kiosk order with empty items rejected")
    
    def test_kiosk_start_session(self):
        """POST /api/pos/kiosk/start - start kiosk session"""
        session_data = {
            "property_id": PROPERTY_ID,
            "outlet_id": "test-outlet",
            "kiosk_id": "kiosk-test-1"
        }
        response = self.session.post(f"{BASE_URL}/api/pos/kiosk/start", json=session_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "id" in data, "Missing session id"
        assert data["status"] == "active", f"Expected active status, got {data['status']}"
        print(f"PASS: Kiosk session started. ID: {data['id']}")


class TestAIUpsell:
    """AI upselling endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_ai_upsell_requires_auth(self):
        """POST /api/pos/ai-upsell - requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.post(f"{BASE_URL}/api/pos/ai-upsell", json={
            "property_id": PROPERTY_ID,
            "cart_items": []
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: AI upsell requires authentication")
    
    def test_ai_upsell_with_cart(self):
        """POST /api/pos/ai-upsell - with cart items"""
        response = self.session.post(f"{BASE_URL}/api/pos/ai-upsell", json={
            "property_id": PROPERTY_ID,
            "cart_items": [
                {"name": "Burger", "quantity": 1, "category": "Mains"},
                {"name": "Fries", "quantity": 1, "category": "Starters"}
            ]
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "suggestions" in data, "Missing suggestions"
        assert "source" in data, "Missing source"
        assert data["source"] in ["ai", "rules", "rules_fallback"], f"Unexpected source: {data['source']}"
        print(f"PASS: AI upsell returns suggestions. Source: {data['source']}, Count: {len(data['suggestions'])}")


class TestExistingPOSFeatures:
    """Verify existing POS features still work"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_pos_outlets_list(self):
        """GET /api/pos/outlets/{property_id} - list outlets"""
        response = self.session.get(f"{BASE_URL}/api/pos/outlets/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of outlets"
        print(f"PASS: POS outlets list works. Count: {len(data)}")
    
    def test_pos_orders_list(self):
        """GET /api/pos/orders/{property_id} - list orders"""
        response = self.session.get(f"{BASE_URL}/api/pos/orders/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of orders"
        print(f"PASS: POS orders list works. Count: {len(data)}")


class TestExistingAccountingFeatures:
    """Verify existing accounting features still work"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_income_entries_list(self):
        """GET /api/accounting/income/{property_id} - list income entries"""
        response = self.session.get(f"{BASE_URL}/api/accounting/income/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of income entries"
        print(f"PASS: Accounting income list works. Count: {len(data)}")
    
    def test_expense_entries_list(self):
        """GET /api/accounting/expenses/{property_id} - list expense entries"""
        response = self.session.get(f"{BASE_URL}/api/accounting/expenses/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of expense entries"
        print(f"PASS: Accounting expenses list works. Count: {len(data)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
