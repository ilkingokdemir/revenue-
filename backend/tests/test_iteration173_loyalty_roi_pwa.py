"""
Iteration 173 Tests - Loyalty Member Rates, Marketing ROI, PWA Manifest

Tests:
1. POST /api/booking-widget/loyalty-check (PUBLIC) - check loyalty member status
2. GET /api/marketing/automation/roi/{property_id}?days=90 (admin auth) - ROI tracker
3. POST /api/booking-widget/book with loyalty_tier and loyalty_discount_pct
4. GET /manifest.json - PWA manifest
5. Regression: admin login, rm-lab navigation, booking widget search
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
LOYALTY_TEST_EMAIL = "test_stripe@example.com"  # platinum member
PROPERTY_ID = "aldgate-flats"


class TestLoyaltyCheck:
    """Test POST /api/booking-widget/loyalty-check (PUBLIC endpoint)"""

    def test_loyalty_check_platinum_member(self):
        """Known platinum member should return is_member=true, tier=platinum, discount_pct=18"""
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/loyalty-check",
            json={"guest_email": LOYALTY_TEST_EMAIL}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("is_member") == True, f"Expected is_member=True, got {data}"
        assert data.get("tier") == "platinum", f"Expected tier=platinum, got {data.get('tier')}"
        assert data.get("discount_pct") == 18, f"Expected discount_pct=18, got {data.get('discount_pct')}"
        assert "message" in data, "Expected message field in response"
        print(f"✓ Platinum member check passed: {data}")

    def test_loyalty_check_unknown_email(self):
        """Unknown email should return is_member=false, tier=null, discount_pct=0"""
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/loyalty-check",
            json={"guest_email": "unknown_random_user@example.com"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("is_member") == False, f"Expected is_member=False, got {data}"
        assert data.get("tier") is None, f"Expected tier=None, got {data.get('tier')}"
        assert data.get("discount_pct") == 0, f"Expected discount_pct=0, got {data.get('discount_pct')}"
        print(f"✓ Unknown email check passed: {data}")

    def test_loyalty_check_empty_email(self):
        """Empty email should return 400 error"""
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/loyalty-check",
            json={"guest_email": ""}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"✓ Empty email validation passed")

    def test_loyalty_check_case_insensitive(self):
        """Email check should be case-insensitive"""
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/loyalty-check",
            json={"guest_email": "TEST_STRIPE@EXAMPLE.COM"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should still find the platinum member
        assert data.get("is_member") == True, f"Expected is_member=True (case-insensitive), got {data}"
        print(f"✓ Case-insensitive check passed: {data}")


class TestMarketingROI:
    """Test GET /api/marketing/automation/roi/{property_id}?days=90 (admin auth)"""

    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")

    def test_roi_endpoint_returns_correct_structure(self, auth_token):
        """ROI endpoint should return correct structure with sent, conversions, conv_rate_pct, revenue, by_trigger"""
        response = requests.get(
            f"{BASE_URL}/api/marketing/automation/roi/{PROPERTY_ID}?days=90",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "sent" in data, "Expected 'sent' field"
        assert "conversions" in data, "Expected 'conversions' field"
        assert "conv_rate_pct" in data, "Expected 'conv_rate_pct' field"
        assert "revenue" in data, "Expected 'revenue' field"
        assert "by_trigger" in data, "Expected 'by_trigger' field"
        assert "property_id" in data, "Expected 'property_id' field"
        assert "window_days" in data, "Expected 'window_days' field"
        
        # Verify types
        assert isinstance(data["sent"], int), "sent should be int"
        assert isinstance(data["conversions"], int), "conversions should be int"
        assert isinstance(data["conv_rate_pct"], (int, float)), "conv_rate_pct should be numeric"
        assert isinstance(data["revenue"], (int, float)), "revenue should be numeric"
        assert isinstance(data["by_trigger"], dict), "by_trigger should be dict"
        
        print(f"✓ ROI endpoint structure verified: sent={data['sent']}, conversions={data['conversions']}, revenue={data['revenue']}")

    def test_roi_handles_empty_data_gracefully(self, auth_token):
        """ROI endpoint should handle empty data (zeros) gracefully"""
        response = requests.get(
            f"{BASE_URL}/api/marketing/automation/roi/{PROPERTY_ID}?days=90",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Even with no data, should return valid structure with zeros
        assert data["sent"] >= 0, "sent should be >= 0"
        assert data["conversions"] >= 0, "conversions should be >= 0"
        assert data["revenue"] >= 0, "revenue should be >= 0"
        print(f"✓ ROI handles empty data gracefully")

    def test_roi_by_trigger_structure(self, auth_token):
        """by_trigger should have correct structure for each trigger type"""
        response = requests.get(
            f"{BASE_URL}/api/marketing/automation/roi/{PROPERTY_ID}?days=90",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        by_trigger = data.get("by_trigger", {})
        # If there are triggers, verify structure
        for trigger_name, trigger_data in by_trigger.items():
            assert "sent" in trigger_data, f"Expected 'sent' in {trigger_name}"
            assert "conversions" in trigger_data, f"Expected 'conversions' in {trigger_name}"
            assert "revenue" in trigger_data, f"Expected 'revenue' in {trigger_name}"
            assert "conv_rate_pct" in trigger_data, f"Expected 'conv_rate_pct' in {trigger_name}"
            print(f"  ✓ Trigger '{trigger_name}': sent={trigger_data['sent']}, conv={trigger_data['conversions']}, rev={trigger_data['revenue']}")
        
        print(f"✓ by_trigger structure verified")

    def test_roi_requires_auth(self):
        """ROI endpoint should require authentication"""
        response = requests.get(
            f"{BASE_URL}/api/marketing/automation/roi/{PROPERTY_ID}?days=90"
        )
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"✓ ROI requires auth (got {response.status_code})")


class TestBookingWithLoyaltyDiscount:
    """Test POST /api/booking-widget/book with loyalty discount fields"""

    def test_booking_with_loyalty_discount(self):
        """Booking with loyalty_tier and loyalty_discount_pct should apply discounted rate"""
        import uuid
        booking_data = {
            "property_id": PROPERTY_ID,
            "room_type": "Standard Room",
            "check_in": "2026-03-01",
            "check_out": "2026-03-03",
            "guest_name": f"TEST_Loyalty_{uuid.uuid4().hex[:6]}",
            "guest_email": f"test_loyalty_{uuid.uuid4().hex[:6]}@example.com",
            "guest_phone": "+44123456789",
            "rate": 82,  # Discounted rate (100 * 0.82 = 82 for 18% off)
            "guests": 2,
            "rooms": 1,
            "currency": "GBP",
            "pay_now": False,  # Pay at property to avoid Stripe redirect
            "loyalty_tier": "platinum",
            "loyalty_discount_pct": 18
        }
        
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/book",
            json=booking_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("status") == "confirmed", f"Expected status=confirmed, got {data.get('status')}"
        assert "booking_ref" in data, "Expected booking_ref in response"
        
        booking = data.get("booking", {})
        assert booking.get("rate") == 82, f"Expected rate=82 (discounted), got {booking.get('rate')}"
        
        print(f"✓ Booking with loyalty discount created: ref={data.get('booking_ref')}, rate={booking.get('rate')}")


class TestPWAManifest:
    """Test PWA manifest.json"""

    def test_manifest_json_accessible(self):
        """manifest.json should be accessible and return valid JSON"""
        response = requests.get(f"{BASE_URL}/manifest.json")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "name" in data, "Expected 'name' in manifest"
        assert "short_name" in data, "Expected 'short_name' in manifest"
        assert "icons" in data, "Expected 'icons' in manifest"
        assert "start_url" in data, "Expected 'start_url' in manifest"
        assert "display" in data, "Expected 'display' in manifest"
        
        print(f"✓ manifest.json accessible: name={data.get('name')}, short_name={data.get('short_name')}")


class TestRegressionSmoke:
    """Regression smoke tests"""

    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")

    def test_admin_login_works(self):
        """Admin login should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "token" in data, "Expected token in login response"
        print(f"✓ Admin login works")

    def test_booking_widget_search_works(self):
        """Booking widget check-availability should work"""
        response = requests.post(
            f"{BASE_URL}/api/booking-widget/check-availability",
            json={
                "property_id": PROPERTY_ID,
                "check_in": "2026-02-15",
                "check_out": "2026-02-17"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "available_rooms" in data, "Expected available_rooms in response"
        print(f"✓ Booking widget search works: {len(data.get('available_rooms', []))} rooms available")

    def test_rm_lab_accuracy_endpoint(self, auth_token):
        """RM Lab accuracy endpoint should work"""
        response = requests.get(
            f"{BASE_URL}/api/forecast/accuracy/{PROPERTY_ID}?days=60",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ RM Lab accuracy endpoint works")

    def test_rm_lab_marketing_queue_endpoint(self, auth_token):
        """RM Lab marketing queue endpoint should work"""
        response = requests.get(
            f"{BASE_URL}/api/marketing/automation/queue/{PROPERTY_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ RM Lab marketing queue endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
