"""
Iteration 237 - Batch 25: Digital Tipping (Stripe Checkout)
Tests for guest-to-staff tipping via Stripe Checkout.

Endpoints:
- GET /api/tipping/landing/{property_id} (PUBLIC) - Landing page info
- POST /api/tipping/session (PUBLIC) - Create Stripe checkout session
- GET /api/tipping/status/{session_id} (PUBLIC) - Poll payment status
- GET /api/tipping/leaderboard/{property_id} (ADMIN) - Staff leaderboard
- GET /api/tipping/list/{property_id} (ADMIN) - List tips with filters
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
PROPERTY_ID = "default"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.cookies.get("access_token") or response.json().get("access_token")
    pytest.skip("Admin login failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def admin_session(admin_token):
    """Session with admin auth"""
    session = requests.Session()
    session.cookies.set("access_token", admin_token)
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestTippingLanding:
    """Test GET /api/tipping/landing/{property_id} (PUBLIC)"""

    def test_landing_returns_property_info(self):
        """Landing endpoint returns property, branding, suggested_amounts, currency"""
        response = requests.get(f"{BASE_URL}/api/tipping/landing/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "property" in data, "Response should contain 'property'"
        assert "branding" in data, "Response should contain 'branding'"
        assert "suggested_amounts" in data, "Response should contain 'suggested_amounts'"
        assert "currency" in data, "Response should contain 'currency'"
        
        # Verify property structure
        assert "id" in data["property"]
        assert "name" in data["property"]
        
        # Verify suggested amounts (should be [2, 5, 10, 20, 50])
        assert data["suggested_amounts"] == [2, 5, 10, 20, 50], f"Expected [2,5,10,20,50], got {data['suggested_amounts']}"
        
        # Verify currency
        assert data["currency"] == "gbp", f"Expected 'gbp', got {data['currency']}"
        print(f"✓ Landing returns property: {data['property']['name']}, amounts: {data['suggested_amounts']}")

    def test_landing_with_staff_id(self):
        """Landing with staff_id query param includes staff info"""
        # First get a staff user ID (admin user)
        response = requests.get(f"{BASE_URL}/api/tipping/landing/{PROPERTY_ID}?staff_id=nonexistent")
        assert response.status_code == 200
        
        data = response.json()
        # staff should be None for nonexistent staff
        assert data.get("staff") is None, "Staff should be None for nonexistent staff_id"
        print("✓ Landing with invalid staff_id returns staff=None")

    def test_landing_no_auth_required(self):
        """Landing endpoint is PUBLIC - no auth required"""
        response = requests.get(f"{BASE_URL}/api/tipping/landing/{PROPERTY_ID}")
        assert response.status_code == 200, "Landing should be accessible without auth"
        print("✓ Landing endpoint is PUBLIC (no auth required)")


class TestTippingSession:
    """Test POST /api/tipping/session (PUBLIC)"""

    def test_create_session_success(self):
        """Create tip session returns session_id, checkout_url, tip_id"""
        payload = {
            "property_id": PROPERTY_ID,
            "amount": 5.00,
            "currency": "gbp",
            "staff_role": "receptionist",
            "guest_name": "TEST_John Smith",
            "message": "Great service!",
            "origin_url": "https://example.com"
        }
        response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Response should contain 'session_id'"
        assert "checkout_url" in data, "Response should contain 'checkout_url'"
        assert "tip_id" in data, "Response should contain 'tip_id'"
        
        # Verify checkout_url is a Stripe URL
        assert "checkout.stripe.com" in data["checkout_url"] or "cs_test_" in data["session_id"], \
            f"Expected Stripe checkout URL, got {data['checkout_url']}"
        
        print(f"✓ Session created: session_id={data['session_id'][:20]}..., tip_id={data['tip_id']}")
        return data

    def test_create_session_minimum_amount(self):
        """Session creation rejects amount < 0.5 with 400"""
        payload = {
            "property_id": PROPERTY_ID,
            "amount": 0.01,  # Below minimum
            "currency": "gbp",
            "origin_url": "https://example.com"
        }
        response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
        assert response.status_code == 400, f"Expected 400 for amount < 0.5, got {response.status_code}"
        
        data = response.json()
        assert "Minimum tip amount is 0.50" in str(data.get("detail", "")), \
            f"Expected 'Minimum tip amount is 0.50' error, got {data}"
        print("✓ Amount < 0.5 rejected with 400 'Minimum tip amount is 0.50'")

    def test_create_session_maximum_amount(self):
        """Session creation rejects amount > 500 with 400"""
        payload = {
            "property_id": PROPERTY_ID,
            "amount": 501,  # Above maximum
            "currency": "gbp",
            "origin_url": "https://example.com"
        }
        response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
        assert response.status_code == 400, f"Expected 400 for amount > 500, got {response.status_code}"
        
        data = response.json()
        assert "Maximum tip amount is 500" in str(data.get("detail", "")), \
            f"Expected 'Maximum tip amount is 500' error, got {data}"
        print("✓ Amount > 500 rejected with 400 'Maximum tip amount is 500'")

    def test_create_session_invalid_currency(self):
        """Session creation rejects invalid currency with 400"""
        payload = {
            "property_id": PROPERTY_ID,
            "amount": 5.00,
            "currency": "XXX",  # Invalid currency
            "origin_url": "https://example.com"
        }
        response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid currency, got {response.status_code}"
        
        data = response.json()
        assert "Unsupported currency" in str(data.get("detail", "")), \
            f"Expected 'Unsupported currency' error, got {data}"
        print("✓ Invalid currency 'XXX' rejected with 400 'Unsupported currency'")

    def test_create_session_invalid_staff_role(self):
        """Session creation rejects invalid staff_role with 400"""
        payload = {
            "property_id": PROPERTY_ID,
            "amount": 5.00,
            "currency": "gbp",
            "staff_role": "invalid_role",  # Invalid role
            "origin_url": "https://example.com"
        }
        response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid staff_role, got {response.status_code}"
        
        data = response.json()
        assert "Invalid staff_role" in str(data.get("detail", "")), \
            f"Expected 'Invalid staff_role' error, got {data}"
        print("✓ Invalid staff_role rejected with 400 'Invalid staff_role'")

    def test_create_session_valid_currencies(self):
        """Session creation accepts valid currencies: gbp, eur, usd, try"""
        # Note: TRY needs higher amount due to Stripe minimum (~50 cents USD equivalent)
        currency_amounts = {
            "gbp": 5.00,
            "eur": 5.00,
            "usd": 5.00,
            "try": 50.00  # ~$1.50 USD, above Stripe minimum
        }
        for currency, amount in currency_amounts.items():
            payload = {
                "property_id": PROPERTY_ID,
                "amount": amount,
                "currency": currency,
                "origin_url": "https://example.com"
            }
            response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
            assert response.status_code == 200, f"Expected 200 for currency '{currency}', got {response.status_code}: {response.text}"
        print(f"✓ All valid currencies accepted: {list(currency_amounts.keys())}")

    def test_create_session_valid_staff_roles(self):
        """Session creation accepts valid staff roles"""
        valid_roles = ["receptionist", "housekeeping", "concierge", "bellhop", "restaurant", "bar", "spa", "other"]
        for role in valid_roles:
            payload = {
                "property_id": PROPERTY_ID,
                "amount": 2.00,
                "currency": "gbp",
                "staff_role": role,
                "origin_url": "https://example.com"
            }
            response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
            assert response.status_code == 200, f"Expected 200 for role '{role}', got {response.status_code}: {response.text}"
        print(f"✓ All valid staff roles accepted: {valid_roles}")

    def test_create_session_no_auth_required(self):
        """Session creation is PUBLIC - no auth required"""
        payload = {
            "property_id": PROPERTY_ID,
            "amount": 5.00,
            "currency": "gbp",
            "origin_url": "https://example.com"
        }
        response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
        assert response.status_code == 200, "Session creation should be accessible without auth"
        print("✓ Session creation endpoint is PUBLIC (no auth required)")


class TestTippingStatus:
    """Test GET /api/tipping/status/{session_id} (PUBLIC)"""

    def test_status_returns_tip_info(self):
        """Status endpoint returns session_id, status, amount, currency"""
        # First create a session
        payload = {
            "property_id": PROPERTY_ID,
            "amount": 10.00,
            "currency": "gbp",
            "origin_url": "https://example.com"
        }
        create_response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]
        
        # Now check status
        response = requests.get(f"{BASE_URL}/api/tipping/status/{session_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "pending", f"Expected 'pending' status, got {data['status']}"
        assert data["amount"] == 10.00
        assert data["currency"] == "gbp"
        print(f"✓ Status returns: session_id, status={data['status']}, amount={data['amount']}, currency={data['currency']}")

    def test_status_not_found(self):
        """Status endpoint returns 404 for nonexistent session"""
        response = requests.get(f"{BASE_URL}/api/tipping/status/nonexistent_session_id")
        assert response.status_code == 404, f"Expected 404 for nonexistent session, got {response.status_code}"
        print("✓ Status returns 404 for nonexistent session")

    def test_status_no_auth_required(self):
        """Status endpoint is PUBLIC - no auth required"""
        # Create a session first
        payload = {
            "property_id": PROPERTY_ID,
            "amount": 5.00,
            "currency": "gbp",
            "origin_url": "https://example.com"
        }
        create_response = requests.post(f"{BASE_URL}/api/tipping/session", json=payload)
        session_id = create_response.json()["session_id"]
        
        response = requests.get(f"{BASE_URL}/api/tipping/status/{session_id}")
        assert response.status_code == 200, "Status should be accessible without auth"
        print("✓ Status endpoint is PUBLIC (no auth required)")


class TestTippingLeaderboard:
    """Test GET /api/tipping/leaderboard/{property_id} (ADMIN)"""

    def test_leaderboard_returns_aggregates(self, admin_session):
        """Leaderboard returns total_amount, total_count, avg_tip, leaderboard, by_role, recent_messages"""
        response = admin_session.get(f"{BASE_URL}/api/tipping/leaderboard/{PROPERTY_ID}?days=30")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_amount" in data, "Response should contain 'total_amount'"
        assert "total_count" in data, "Response should contain 'total_count'"
        assert "avg_tip" in data, "Response should contain 'avg_tip'"
        assert "leaderboard" in data, "Response should contain 'leaderboard'"
        assert "by_role" in data, "Response should contain 'by_role'"
        assert "recent_messages" in data, "Response should contain 'recent_messages'"
        assert "days" in data, "Response should contain 'days'"
        
        print(f"✓ Leaderboard returns: total_amount={data['total_amount']}, total_count={data['total_count']}, avg_tip={data['avg_tip']}")

    def test_leaderboard_validates_days(self, admin_session):
        """Leaderboard validates days parameter (1..365)"""
        # Test days < 1
        response = admin_session.get(f"{BASE_URL}/api/tipping/leaderboard/{PROPERTY_ID}?days=0")
        assert response.status_code == 400, f"Expected 400 for days=0, got {response.status_code}"
        
        # Test days > 365
        response = admin_session.get(f"{BASE_URL}/api/tipping/leaderboard/{PROPERTY_ID}?days=400")
        assert response.status_code == 400, f"Expected 400 for days=400, got {response.status_code}"
        
        # Test valid days
        for days in [1, 30, 90, 365]:
            response = admin_session.get(f"{BASE_URL}/api/tipping/leaderboard/{PROPERTY_ID}?days={days}")
            assert response.status_code == 200, f"Expected 200 for days={days}, got {response.status_code}"
        
        print("✓ Leaderboard validates days parameter (1..365)")

    def test_leaderboard_requires_auth(self):
        """Leaderboard requires authentication"""
        response = requests.get(f"{BASE_URL}/api/tipping/leaderboard/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Leaderboard requires authentication (401 without token)")


class TestTippingList:
    """Test GET /api/tipping/list/{property_id} (ADMIN)"""

    def test_list_returns_tips(self, admin_session):
        """List endpoint returns tip rows"""
        response = admin_session.get(f"{BASE_URL}/api/tipping/list/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "rows" in data, "Response should contain 'rows'"
        assert "count" in data, "Response should contain 'count'"
        assert isinstance(data["rows"], list), "'rows' should be a list"
        
        print(f"✓ List returns {data['count']} tips")

    def test_list_filter_by_status(self, admin_session):
        """List endpoint filters by status"""
        # Filter by pending
        response = admin_session.get(f"{BASE_URL}/api/tipping/list/{PROPERTY_ID}?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        for row in data["rows"]:
            assert row["status"] == "pending", f"Expected status='pending', got {row['status']}"
        
        print(f"✓ List filters by status=pending ({data['count']} rows)")

    def test_list_requires_auth(self):
        """List requires authentication"""
        response = requests.get(f"{BASE_URL}/api/tipping/list/{PROPERTY_ID}")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ List requires authentication (401 without token)")


class TestTippingRBAC:
    """Test RBAC for admin endpoints"""

    def test_receptionist_cannot_access_leaderboard(self):
        """Receptionist role cannot access leaderboard (403)"""
        # Login as receptionist
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testrecep@hotelbox.com", "password": "Test2026!"}
        )
        if login_response.status_code != 200:
            pytest.skip("Receptionist user not available")
        
        token = login_response.cookies.get("access_token") or login_response.json().get("access_token")
        session = requests.Session()
        session.cookies.set("access_token", token)
        
        response = session.get(f"{BASE_URL}/api/tipping/leaderboard/{PROPERTY_ID}")
        assert response.status_code == 403, f"Expected 403 for receptionist, got {response.status_code}"
        print("✓ Receptionist cannot access leaderboard (403)")

    def test_receptionist_cannot_access_list(self):
        """Receptionist role cannot access list (403)"""
        # Login as receptionist
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testrecep@hotelbox.com", "password": "Test2026!"}
        )
        if login_response.status_code != 200:
            pytest.skip("Receptionist user not available")
        
        token = login_response.cookies.get("access_token") or login_response.json().get("access_token")
        session = requests.Session()
        session.cookies.set("access_token", token)
        
        response = session.get(f"{BASE_URL}/api/tipping/list/{PROPERTY_ID}")
        assert response.status_code == 403, f"Expected 403 for receptionist, got {response.status_code}"
        print("✓ Receptionist cannot access list (403)")


class TestWebhookTipHandling:
    """Test webhook handling for tip payments (already wired in server.py)"""

    def test_webhook_endpoint_exists(self):
        """Webhook endpoint exists at /api/webhook/stripe"""
        # Just verify the endpoint exists (we can't fully test without Stripe signature)
        response = requests.post(f"{BASE_URL}/api/webhook/stripe", data=b"test")
        # Should not be 404
        assert response.status_code != 404, "Webhook endpoint should exist"
        print("✓ Webhook endpoint /api/webhook/stripe exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
