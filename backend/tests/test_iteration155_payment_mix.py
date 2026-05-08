"""
Iteration 155 - Payment Mix Report Testing
Tests the new Finance dashboard tile that breaks down payments by method
(cash/card/bank_transfer/channel_collection) and for channel_collection,
shows a breakdown by OTA channel.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"


class TestPaymentMixAPI:
    """Payment Mix endpoint tests - GET /api/finance/payment-mix/{property_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and authenticate as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def test_payment_mix_returns_200_for_admin(self):
        """Admin should be able to access payment-mix endpoint"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: Admin can access payment-mix endpoint")
    
    def test_payment_mix_response_structure(self):
        """Verify response contains all required fields"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Check top-level fields
        required_fields = ["total", "direct_captured", "direct_percent", "ota_captured", 
                          "ota_percent", "methods", "channels", "daily", "transactions"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify types
        assert isinstance(data["total"], (int, float)), "total should be a number"
        assert isinstance(data["direct_captured"], (int, float)), "direct_captured should be a number"
        assert isinstance(data["direct_percent"], (int, float)), "direct_percent should be a number"
        assert isinstance(data["ota_captured"], (int, float)), "ota_captured should be a number"
        assert isinstance(data["ota_percent"], (int, float)), "ota_percent should be a number"
        assert isinstance(data["methods"], list), "methods should be an array"
        assert isinstance(data["channels"], list), "channels should be an array"
        assert isinstance(data["daily"], list), "daily should be an array"
        assert isinstance(data["transactions"], int), "transactions should be a number"
        
        print(f"PASS: Response structure is correct. Total: {data['total']}, Transactions: {data['transactions']}")
    
    def test_payment_mix_four_method_buckets(self):
        """Verify all 4 method buckets always appear (even if 0)"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        methods = data["methods"]
        assert len(methods) == 4, f"Expected 4 method buckets, got {len(methods)}"
        
        method_names = [m["method"] for m in methods]
        expected_methods = ["cash", "card", "bank_transfer", "channel_collection"]
        for expected in expected_methods:
            assert expected in method_names, f"Missing method bucket: {expected}"
        
        # Verify each method has required fields
        for method in methods:
            assert "method" in method
            assert "label" in method
            assert "amount" in method
            assert "count" in method
            assert "percent" in method
            # Even if 0, these should be numbers
            assert isinstance(method["amount"], (int, float))
            assert isinstance(method["count"], int)
            assert isinstance(method["percent"], (int, float))
        
        print(f"PASS: All 4 method buckets present: {method_names}")
    
    def test_payment_mix_method_labels(self):
        """Verify method labels are correct"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        expected_labels = {
            "cash": "Cash",
            "card": "Card",
            "bank_transfer": "Bank Transfer",
            "channel_collection": "Channel Collection"
        }
        
        for method in data["methods"]:
            expected_label = expected_labels.get(method["method"])
            assert method["label"] == expected_label, f"Wrong label for {method['method']}: expected {expected_label}, got {method['label']}"
        
        print("PASS: All method labels are correct")
    
    def test_payment_mix_percent_sum(self):
        """Verify method percents sum to ~100% (within rounding)"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if data["total"] > 0:
            total_percent = sum(m["percent"] for m in data["methods"])
            # Allow for rounding errors (99-101%)
            assert 99 <= total_percent <= 101, f"Method percents sum to {total_percent}%, expected ~100%"
            print(f"PASS: Method percents sum to {total_percent}%")
        else:
            print("SKIP: No payments in period, cannot verify percent sum")
    
    def test_payment_mix_channel_percent_sum(self):
        """Verify channel percents sum to 100% of OTA captured"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if data["ota_captured"] > 0 and len(data["channels"]) > 0:
            total_channel_percent = sum(c["percent"] for c in data["channels"])
            # Allow for rounding errors
            assert 99 <= total_channel_percent <= 101, f"Channel percents sum to {total_channel_percent}%, expected ~100%"
            print(f"PASS: Channel percents sum to {total_channel_percent}%")
        else:
            print("SKIP: No OTA payments in period, cannot verify channel percent sum")
    
    def test_payment_mix_channels_sorted_desc(self):
        """Verify channels are sorted by amount descending"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        channels = data["channels"]
        if len(channels) > 1:
            amounts = [c["amount"] for c in channels]
            assert amounts == sorted(amounts, reverse=True), "Channels should be sorted by amount descending"
            print(f"PASS: Channels sorted descending by amount: {amounts}")
        else:
            print("SKIP: Not enough channels to verify sorting")
    
    def test_payment_mix_daily_structure(self):
        """Verify daily array has correct structure"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if len(data["daily"]) > 0:
            day = data["daily"][0]
            required_fields = ["date", "cash", "card", "bank_transfer", "channel_collection", "total"]
            for field in required_fields:
                assert field in day, f"Daily entry missing field: {field}"
            print(f"PASS: Daily entries have correct structure. Sample: {day}")
        else:
            print("SKIP: No daily data to verify")
    
    def test_payment_mix_property_all(self):
        """Verify property_id='all' works (aggregates across all properties)"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/all",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200, f"Expected 200 for property_id='all', got {resp.status_code}"
        data = resp.json()
        assert "total" in data
        assert "methods" in data
        print(f"PASS: property_id='all' works. Total: {data['total']}")
    
    def test_payment_mix_direct_ota_split(self):
        """Verify direct_captured + ota_captured = total"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        calculated_total = data["direct_captured"] + data["ota_captured"]
        # Allow for small rounding differences
        assert abs(calculated_total - data["total"]) < 0.1, \
            f"direct_captured ({data['direct_captured']}) + ota_captured ({data['ota_captured']}) != total ({data['total']})"
        print(f"PASS: Direct ({data['direct_captured']}) + OTA ({data['ota_captured']}) = Total ({data['total']})")


class TestPaymentMixAuth:
    """Test authorization for payment-mix endpoint"""
    
    def test_payment_mix_requires_auth(self):
        """Unauthenticated request should fail"""
        session = requests.Session()
        resp = session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code in [401, 403], f"Expected 401/403 for unauthenticated, got {resp.status_code}"
        print("PASS: Unauthenticated request rejected")
    
    def test_payment_mix_receptionist_denied(self):
        """Receptionist role should NOT be able to access payment-mix"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as receptionist
        login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        
        if login_resp.status_code != 200:
            pytest.skip(f"Receptionist login failed: {login_resp.text}")
        
        token = login_resp.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        resp = session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2026-01-01", "to_date": "2026-12-31"}
        )
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}"
        print("PASS: Receptionist correctly denied access to payment-mix")


class TestPaymentMixEdgeCases:
    """Edge case tests for payment-mix endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and authenticate as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        self.admin_token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
    
    def test_payment_mix_empty_period(self):
        """Test with date range that has no payments"""
        resp = self.session.get(
            f"{BASE_URL}/api/finance/payment-mix/aldgate-flats",
            params={"from_date": "2020-01-01", "to_date": "2020-01-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Should still return valid structure with zeros
        assert data["total"] == 0
        assert data["transactions"] == 0
        assert len(data["methods"]) == 4  # All 4 buckets should still appear
        
        for method in data["methods"]:
            assert method["amount"] == 0
            assert method["count"] == 0
            assert method["percent"] == 0
        
        print("PASS: Empty period returns valid structure with zeros")
    
    def test_payment_mix_default_dates(self):
        """Test without date params (should default to current month)"""
        resp = self.session.get(f"{BASE_URL}/api/finance/payment-mix/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        
        # Should have from_date and to_date in response
        assert "from_date" in data
        assert "to_date" in data
        print(f"PASS: Default dates applied: {data['from_date']} to {data['to_date']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
