"""
Iteration 282 — Owner Self-Service Portal Login Tests

Tests for:
- POST /api/owners/{owner_id}/set-credentials (admin sets/resets PIN)
- POST /api/owner-auth/login (owner login with email+PIN)
- GET /api/owner-auth/me (owner profile)
- GET /api/owner-auth/dashboard (YTD performance)
- GET /api/owner-auth/statement.pdf (PDF download)
- POST /api/owner-auth/logout
- Token segregation (owner vs staff tokens)
- Regression tests for existing owner portal endpoints
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Admin credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestOwnerSelfService:
    """All owner self-service tests in one class to share fixtures properly"""

    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token for staff endpoints"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        return data.get("token") or data.get("access_token")

    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}

    @pytest.fixture(scope="class")
    def test_owner(self, admin_headers):
        """Create a test owner for self-service tests"""
        owner_data = {
            "name": f"TEST_Owner_{uuid.uuid4().hex[:8]}",
            "email": f"test_owner_{uuid.uuid4().hex[:8]}@example.com",
            "phone": "+44123456789",
            "company": "Test REIT Corp",
            "management_fee_percent": 25
        }
        response = requests.post(
            f"{BASE_URL}/api/owners",
            json=owner_data,
            headers=admin_headers
        )
        assert response.status_code in [200, 201], f"Failed to create test owner: {response.text}"
        owner = response.json()
        yield owner
        # Cleanup: delete test owner
        try:
            requests.delete(f"{BASE_URL}/api/owners/{owner['id']}", headers=admin_headers)
        except:
            pass

    # ============ Credentials Setup Tests ============

    def test_set_credentials_generate_pin(self, admin_headers, test_owner):
        """Admin can generate a 6-digit PIN for an owner"""
        response = requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"generate": True},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["ok"] is True
        assert data["pin_generated"] is True
        assert data["pin"] is not None
        assert len(data["pin"]) == 6
        assert data["pin"].isdigit(), "PIN should be numeric"
        print(f"✓ Generated PIN: {data['pin']}")

    def test_set_credentials_explicit_pin(self, admin_headers, test_owner):
        """Admin can set an explicit PIN for an owner"""
        explicit_pin = "123456"
        response = requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": explicit_pin},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["ok"] is True
        print(f"✓ Set explicit PIN successfully")

    def test_set_credentials_short_pin_rejected(self, admin_headers, test_owner):
        """PIN shorter than 4 chars should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": "123"},
            headers=admin_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Short PIN rejected correctly")

    def test_set_credentials_nonexistent_owner(self, admin_headers):
        """Setting credentials for non-existent owner returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/owners/nonexistent-owner-id/set-credentials",
            json={"generate": True},
            headers=admin_headers
        )
        assert response.status_code == 404
        print("✓ Non-existent owner returns 404")

    def test_set_credentials_requires_admin(self, test_owner):
        """Non-admin cannot set owner credentials"""
        response = requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"generate": True}
        )
        assert response.status_code == 401
        print("✓ Unauthenticated request rejected")

    # ============ Owner Login Tests ============

    def test_login_success(self, admin_headers, test_owner):
        """Owner can login with valid email + PIN"""
        pin = "654321"
        # Set PIN first
        requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": pin},
            headers=admin_headers
        )
        
        response = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": test_owner["email"], "pin": pin}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "owner" in data
        assert data["owner"]["id"] == test_owner["id"]
        assert data["owner"]["email"] == test_owner["email"]
        print(f"✓ Owner login successful, got token")

    def test_login_wrong_pin(self, admin_headers, test_owner):
        """Login with wrong PIN returns 401"""
        # Set a known PIN first
        requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": "111111"},
            headers=admin_headers
        )
        
        response = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": test_owner["email"], "pin": "000000"}
        )
        assert response.status_code == 401
        print("✓ Wrong PIN returns 401")

    def test_login_nonexistent_email(self):
        """Login with non-existent email returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": "nonexistent@example.com", "pin": "123456"}
        )
        assert response.status_code == 401
        print("✓ Non-existent email returns 401")

    def test_login_missing_fields(self):
        """Login without email or PIN returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": "test@example.com"}
        )
        assert response.status_code == 400
        print("✓ Missing PIN returns 400")

    # ============ Login Disabled Tests ============

    def test_login_disabled_returns_403(self, admin_headers):
        """Owner with login_enabled=false gets 403"""
        # Create a disabled owner
        owner_data = {
            "name": f"TEST_DisabledOwner_{uuid.uuid4().hex[:8]}",
            "email": f"disabled_owner_{uuid.uuid4().hex[:8]}@example.com",
            "management_fee_percent": 20
        }
        response = requests.post(
            f"{BASE_URL}/api/owners",
            json=owner_data,
            headers=admin_headers
        )
        assert response.status_code in [200, 201]
        owner = response.json()
        
        # Set credentials with login_enabled=false
        response = requests.post(
            f"{BASE_URL}/api/owners/{owner['id']}/set-credentials",
            json={"pin": "111111", "login_enabled": False},
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Try to login
        response = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": owner["email"], "pin": "111111"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Disabled owner login returns 403")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/owners/{owner['id']}", headers=admin_headers)

    # ============ Authenticated Owner Endpoints Tests ============

    def test_me_returns_owner_profile(self, admin_headers, test_owner):
        """GET /api/owner-auth/me returns owner profile"""
        pin = "999888"
        requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": pin},
            headers=admin_headers
        )
        
        login_resp = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": test_owner["email"], "pin": pin}
        )
        owner_token = login_resp.json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/owner-auth/me",
            headers=owner_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["id"] == test_owner["id"]
        assert data["email"] == test_owner["email"]
        assert "password_hash" not in data, "password_hash should not be exposed"
        print(f"✓ /me returns owner profile without password_hash")

    def test_me_without_auth_returns_401(self):
        """GET /api/owner-auth/me without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/owner-auth/me")
        assert response.status_code == 401
        print("✓ /me without auth returns 401")

    def test_dashboard_returns_ytd_data(self, admin_headers, test_owner):
        """GET /api/owner-auth/dashboard returns YTD performance"""
        pin = "888777"
        requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": pin},
            headers=admin_headers
        )
        
        login_resp = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": test_owner["email"], "pin": pin}
        )
        owner_token = login_resp.json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/owner-auth/dashboard?year=2026",
            headers=owner_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "months" in data
        assert len(data["months"]) == 12, "Should have 12 months"
        assert "total" in data
        assert "management_fee_percent" in data
        print(f"✓ Dashboard returns 12 months + total + management_fee_percent")

    def test_statement_pdf_returns_pdf(self, admin_headers, test_owner):
        """GET /api/owner-auth/statement.pdf returns PDF"""
        pin = "777666"
        requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": pin},
            headers=admin_headers
        )
        
        login_resp = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": test_owner["email"], "pin": pin}
        )
        owner_token = login_resp.json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/owner-auth/statement.pdf?month=2026-02",
            headers=owner_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        assert "application/pdf" in response.headers.get("Content-Type", "")
        assert len(response.content) > 2000, "PDF should be >2KB"
        assert response.content[:5] == b"%PDF-", "Should start with %PDF-"
        print(f"✓ statement.pdf returns valid PDF ({len(response.content)} bytes)")

    def test_logout_returns_ok(self, admin_headers, test_owner):
        """POST /api/owner-auth/logout returns {ok: true}"""
        pin = "666555"
        requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": pin},
            headers=admin_headers
        )
        
        login_resp = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": test_owner["email"], "pin": pin}
        )
        owner_token = login_resp.json()["access_token"]
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/owner-auth/logout",
            headers=owner_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["ok"] is True
        print("✓ Logout returns {ok: true}")

    # ============ Token Segregation Tests ============

    def test_staff_token_cannot_access_owner_me(self, admin_token):
        """Staff JWT cannot access /api/owner-auth/me"""
        response = requests.get(
            f"{BASE_URL}/api/owner-auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Staff token rejected on owner /me endpoint")

    def test_owner_token_cannot_access_staff_endpoints(self, admin_headers, test_owner):
        """Owner JWT cannot access staff endpoints like /api/bookings"""
        pin = "555444"
        requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": pin},
            headers=admin_headers
        )
        
        login_resp = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": test_owner["email"], "pin": pin}
        )
        owner_token = login_resp.json()["access_token"]
        
        response = requests.get(
            f"{BASE_URL}/api/bookings",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Owner token rejected on staff /bookings endpoint")

    def test_owner_token_cannot_access_users(self, admin_headers, test_owner):
        """Owner JWT cannot access /api/users"""
        pin = "444333"
        requests.post(
            f"{BASE_URL}/api/owners/{test_owner['id']}/set-credentials",
            json={"pin": pin},
            headers=admin_headers
        )
        
        login_resp = requests.post(
            f"{BASE_URL}/api/owner-auth/login",
            json={"email": test_owner["email"], "pin": pin}
        )
        owner_token = login_resp.json()["access_token"]
        
        response = requests.get(
            f"{BASE_URL}/api/users",
            headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Owner token rejected on staff /users endpoint")

    # ============ Admin Owner Endpoints Regression Tests ============

    def test_list_owners(self, admin_headers):
        """GET /api/owners still works"""
        response = requests.get(
            f"{BASE_URL}/api/owners",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "owners" in data
        print(f"✓ GET /api/owners returns {len(data['owners'])} owners")

    def test_get_owner_statement(self, admin_headers, test_owner):
        """GET /api/owners/{id}/statement still works"""
        response = requests.get(
            f"{BASE_URL}/api/owners/{test_owner['id']}/statement?month=2026-01",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "gross_revenue" in data
        assert "net_distribution" in data
        print("✓ Admin owner statement endpoint works")

    def test_get_owner_statement_pdf(self, admin_headers, test_owner):
        """GET /api/owners/{id}/statement.pdf still works"""
        response = requests.get(
            f"{BASE_URL}/api/owners/{test_owner['id']}/statement.pdf?month=2026-01",
            headers=admin_headers
        )
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("Content-Type", "")
        print("✓ Admin owner PDF endpoint works")


class TestRegressionIter277to281:
    """Regression tests for iterations 277-281"""

    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("token") or data.get("access_token")

    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}

    def test_spa_services(self, admin_headers):
        """Spa services endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/spa/services",
            headers=admin_headers
        )
        assert response.status_code == 200
        print("✓ Spa services endpoint works")

    def test_meetings_list(self, admin_headers):
        """Meetings list endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/meetings",
            headers=admin_headers
        )
        assert response.status_code == 200
        print("✓ Meetings list endpoint works")

    def test_fnb_pos_providers(self, admin_headers):
        """F&B POS providers endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/fnb-pos/providers",
            headers=admin_headers
        )
        assert response.status_code == 200
        print("✓ F&B POS providers endpoint works")

    def test_banquet_orders(self, admin_headers):
        """Banquet orders endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/banquet-orders/aldgate-flats",
            headers=admin_headers
        )
        assert response.status_code == 200
        print("✓ Banquet orders endpoint works")

    def test_channel_parity(self, admin_headers):
        """Channel parity endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/channel-parity/aldgate-flats",
            headers=admin_headers
        )
        assert response.status_code == 200
        print("✓ Channel parity endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
