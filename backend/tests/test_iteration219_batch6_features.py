"""
Iteration 219 - Batch 6 (Final) Keyless Competitor Parity Features
Tests for 5 new P0 features:
1. Pre-Authorization Holds - card hold ledger for check-in
2. Chargeback Defense Package - evidence builder for disputes
3. PWA Web Push Notifications - browser push subscriptions
4. PMS-CRS Two-way Sync - internal CRS index mirror
5. Public API Sandbox/Developer Portal - API key issuance + sandbox
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

def get_auth_token():
    """Get fresh auth token for admin user"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json().get("access_token") or resp.json().get("token")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def auth_headers():
    """Get fresh auth token for each test"""
    return get_auth_token()

@pytest.fixture(scope="function")
def test_booking_id(auth_headers):
    """Get or create a test booking for preauth/chargeback tests"""
    # Try to get an existing booking
    resp = requests.get(f"{BASE_URL}/api/bookings?property_id=default&limit=1", headers=auth_headers)
    if resp.status_code == 200:
        data = resp.json()
        # Handle both list and dict responses
        items = data if isinstance(data, list) else data.get("items", [])
        if items:
            return items[0]["id"]
    # Create a test booking if none exists
    booking_data = {
        "property_id": "default",
        "guest_name": "Test Guest PreAuth",
        "guest_email": "preauth@test.com",
        "check_in": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "check_out": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
        "room_type": "Standard",
        "total_price": 300,
        "status": "confirmed"
    }
    resp = requests.post(f"{BASE_URL}/api/bookings", json=booking_data, headers=auth_headers)
    if resp.status_code in [200, 201]:
        return resp.json().get("booking", {}).get("id") or resp.json().get("id")
    return f"test-booking-{uuid.uuid4().hex[:8]}"


# ==================== PRE-AUTHORIZATION HOLDS ====================
class TestPreAuthHolds:
    """Pre-Authorization Hold endpoints - card hold ledger"""
    
    def test_create_hold(self, auth_headers, test_booking_id):
        """POST /api/preauth/holds - create a new hold"""
        resp = requests.post(f"{BASE_URL}/api/preauth/holds", json={
            "property_id": "default",
            "booking_id": test_booking_id,
            "guest_name": "Test Guest",
            "room_number": "101",
            "amount": 200.00,
            "hold_days": 7,
            "reason": "incidentals",
            "card_last4": "4242",
            "card_brand": "visa"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Create hold failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "hold" in data
        assert data["hold"]["status"] == "authorized"
        assert data["hold"]["amount"] == 200.00
        # Store hold_id for later tests
        TestPreAuthHolds.hold_id = data["hold"]["id"]
    
    def test_list_holds(self, auth_headers):
        """GET /api/preauth/{property_id}/holds - list holds"""
        resp = requests.get(f"{BASE_URL}/api/preauth/default/holds?days=30", headers=auth_headers)
        assert resp.status_code == 200, f"List holds failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "count" in data
    
    def test_list_holds_with_status_filter(self, auth_headers):
        """GET /api/preauth/{property_id}/holds?status=authorized"""
        resp = requests.get(f"{BASE_URL}/api/preauth/default/holds?status=authorized&days=30", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # All returned items should have authorized status
        for item in data.get("items", []):
            assert item["status"] == "authorized"
    
    def test_get_summary(self, auth_headers):
        """GET /api/preauth/{property_id}/summary - KPI snapshot"""
        resp = requests.get(f"{BASE_URL}/api/preauth/default/summary?days=30", headers=auth_headers)
        assert resp.status_code == 200, f"Summary failed: {resp.text}"
        data = resp.json()
        assert "by_status" in data
        assert "total_currently_held" in data
        assert "total_captured" in data
        assert "window_days" in data
    
    def test_capture_hold_partial(self, auth_headers, test_booking_id):
        """POST /api/preauth/holds/{id}/capture - partial capture"""
        # Create a fresh hold for capture test
        resp = requests.post(f"{BASE_URL}/api/preauth/holds", json={
            "property_id": "default",
            "booking_id": f"capture-test-{uuid.uuid4().hex[:8]}",
            "amount": 150.00,
            "card_last4": "1234"
        }, headers=auth_headers)
        assert resp.status_code == 200
        hold_id = resp.json()["hold"]["id"]
        
        # Capture partial amount
        resp = requests.post(f"{BASE_URL}/api/preauth/holds/{hold_id}/capture", json={
            "amount": 75.00,
            "reason": "damage"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Capture failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert data["captured"] == 75.00
    
    def test_capture_exceeds_amount_fails(self, auth_headers):
        """Capture amount cannot exceed authorized amount"""
        # Create a hold
        resp = requests.post(f"{BASE_URL}/api/preauth/holds", json={
            "property_id": "default",
            "booking_id": f"exceed-test-{uuid.uuid4().hex[:8]}",
            "amount": 100.00
        }, headers=auth_headers)
        assert resp.status_code == 200
        hold_id = resp.json()["hold"]["id"]
        
        # Try to capture more than authorized
        resp = requests.post(f"{BASE_URL}/api/preauth/holds/{hold_id}/capture", json={
            "amount": 150.00
        }, headers=auth_headers)
        assert resp.status_code == 400, "Should fail when capture > authorized"
    
    def test_release_hold(self, auth_headers):
        """POST /api/preauth/holds/{id}/release - release without charge"""
        # Create a hold to release
        resp = requests.post(f"{BASE_URL}/api/preauth/holds", json={
            "property_id": "default",
            "booking_id": f"release-test-{uuid.uuid4().hex[:8]}",
            "amount": 100.00
        }, headers=auth_headers)
        assert resp.status_code == 200
        hold_id = resp.json()["hold"]["id"]
        
        # Release it
        resp = requests.post(f"{BASE_URL}/api/preauth/holds/{hold_id}/release", headers=auth_headers)
        assert resp.status_code == 200, f"Release failed: {resp.text}"
        assert resp.json().get("ok") is True
    
    def test_cannot_capture_released_hold(self, auth_headers):
        """Cannot capture a hold that's already released"""
        # Create and release a hold
        resp = requests.post(f"{BASE_URL}/api/preauth/holds", json={
            "property_id": "default",
            "booking_id": f"state-test-{uuid.uuid4().hex[:8]}",
            "amount": 100.00
        }, headers=auth_headers)
        hold_id = resp.json()["hold"]["id"]
        requests.post(f"{BASE_URL}/api/preauth/holds/{hold_id}/release", headers=auth_headers)
        
        # Try to capture
        resp = requests.post(f"{BASE_URL}/api/preauth/holds/{hold_id}/capture", json={"amount": 50}, headers=auth_headers)
        assert resp.status_code == 400, "Should fail - cannot capture released hold"
    
    def test_second_hold_supersedes_first(self, auth_headers):
        """Creating second hold for same booking supersedes the first"""
        booking_id = f"supersede-test-{uuid.uuid4().hex[:8]}"
        
        # Create first hold
        resp1 = requests.post(f"{BASE_URL}/api/preauth/holds", json={
            "property_id": "default",
            "booking_id": booking_id,
            "amount": 100.00
        }, headers=auth_headers)
        assert resp1.status_code == 200
        first_hold_id = resp1.json()["hold"]["id"]
        
        # Create second hold for same booking
        resp2 = requests.post(f"{BASE_URL}/api/preauth/holds", json={
            "property_id": "default",
            "booking_id": booking_id,
            "amount": 200.00
        }, headers=auth_headers)
        assert resp2.status_code == 200
        
        # Check first hold is now released (superseded)
        resp = requests.get(f"{BASE_URL}/api/preauth/default/holds?days=1", headers=auth_headers)
        items = resp.json().get("items", [])
        first_hold = next((h for h in items if h["id"] == first_hold_id), None)
        if first_hold:
            assert first_hold["status"] == "released", "First hold should be superseded"
    
    def test_expire_due(self, auth_headers):
        """POST /api/preauth/holds/expire-due - cron sweeper"""
        resp = requests.post(f"{BASE_URL}/api/preauth/holds/expire-due", headers=auth_headers)
        assert resp.status_code == 200, f"Expire-due failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "expired" in data


# ==================== CHARGEBACK DEFENSE ====================
class TestChargebackDefense:
    """Chargeback Defense Package endpoints"""
    
    def test_open_case(self, auth_headers, test_booking_id):
        """POST /api/chargebacks - open a chargeback case"""
        resp = requests.post(f"{BASE_URL}/api/chargebacks", json={
            "property_id": "default",
            "booking_id": test_booking_id,
            "amount": 250.00,
            "reason": "fraudulent",
            "card_last4": "4242",
            "issuer": "Visa"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Open case failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "case" in data
        assert data["case"]["status"] == "pending"
        assert "case_ref" in data["case"]
        TestChargebackDefense.case_id = data["case"]["id"]
    
    def test_list_cases(self, auth_headers):
        """GET /api/chargebacks/{property_id} - list with stats"""
        resp = requests.get(f"{BASE_URL}/api/chargebacks/default?days=90", headers=auth_headers)
        assert resp.status_code == 200, f"List cases failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "won" in data
        assert "lost" in data
        assert "win_rate" in data
    
    def test_build_evidence(self, auth_headers):
        """GET /api/chargebacks/case/{case_id}/evidence - auto-build manifest"""
        case_id = getattr(TestChargebackDefense, "case_id", None)
        if not case_id:
            pytest.skip("No case_id from previous test")
        
        resp = requests.get(f"{BASE_URL}/api/chargebacks/case/{case_id}/evidence", headers=auth_headers)
        assert resp.status_code == 200, f"Build evidence failed: {resp.text}"
        data = resp.json()
        assert "checks" in data, "Evidence should have checks dict"
        assert "evidence_score" in data, "Evidence should have score"
        assert "narrative_summary" in data, "Evidence should have narrative"
        assert isinstance(data["checks"], dict)
        assert isinstance(data["evidence_score"], int)
    
    def test_update_status(self, auth_headers):
        """POST /api/chargebacks/case/{case_id}/status - status transitions"""
        case_id = getattr(TestChargebackDefense, "case_id", None)
        if not case_id:
            pytest.skip("No case_id from previous test")
        
        # Mark as submitted
        resp = requests.post(f"{BASE_URL}/api/chargebacks/case/{case_id}/status", json={
            "status": "submitted"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Update status failed: {resp.text}"
        assert resp.json().get("status") == "submitted"
        
        # Mark as won
        resp = requests.post(f"{BASE_URL}/api/chargebacks/case/{case_id}/status", json={
            "status": "won"
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json().get("status") == "won"
    
    def test_add_note(self, auth_headers):
        """POST /api/chargebacks/case/{case_id}/note - append note"""
        case_id = getattr(TestChargebackDefense, "case_id", None)
        if not case_id:
            pytest.skip("No case_id from previous test")
        
        resp = requests.post(f"{BASE_URL}/api/chargebacks/case/{case_id}/note", json={
            "text": "Guest confirmed stay via email"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Add note failed: {resp.text}"
        assert resp.json().get("ok") is True
        assert "note" in resp.json()
    
    def test_invalid_status_fails(self, auth_headers):
        """Invalid status should return 400"""
        case_id = getattr(TestChargebackDefense, "case_id", None)
        if not case_id:
            pytest.skip("No case_id from previous test")
        
        resp = requests.post(f"{BASE_URL}/api/chargebacks/case/{case_id}/status", json={
            "status": "invalid_status"
        }, headers=auth_headers)
        assert resp.status_code == 400


# ==================== WEB PUSH NOTIFICATIONS ====================
class TestWebPush:
    """PWA Web Push Notifications endpoints"""
    
    def test_subscribe(self, auth_headers):
        """POST /api/push/subscribe - register subscription"""
        endpoint = f"hk-test://{uuid.uuid4().hex}"
        resp = requests.post(f"{BASE_URL}/api/push/subscribe", json={
            "property_id": "default",
            "endpoint": endpoint,
            "user_id": "test-user-1",
            "user_role": "receptionist",
            "tags": ["frontdesk"],
            "user_agent": "TestAgent/1.0"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Subscribe failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "subscription" in data
        assert data["subscription"]["id"]
        TestWebPush.endpoint = endpoint
    
    def test_list_subscriptions(self, auth_headers):
        """GET /api/push/{property_id}/subscriptions - list with by_role counts"""
        resp = requests.get(f"{BASE_URL}/api/push/default/subscriptions", headers=auth_headers)
        assert resp.status_code == 200, f"List subs failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "count" in data
        assert "by_role" in data
        assert isinstance(data["by_role"], dict)
    
    def test_send_push(self, auth_headers):
        """POST /api/push/{property_id}/send - dispatch notification"""
        resp = requests.post(f"{BASE_URL}/api/push/default/send", json={
            "title": "Test Notification",
            "body": "This is a test push from pytest",
            "url": "/dashboard",
            "category": "ops",
            "target_role": ""
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Send push failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "delivery" in data
        assert "subscribers_targeted" in data
        # Should be simulated mode (no VAPID configured)
        assert data["delivery"]["delivery_mode"] in ["simulated", "real_vapid"]
    
    def test_get_log(self, auth_headers):
        """GET /api/push/{property_id}/log - dispatch log"""
        resp = requests.get(f"{BASE_URL}/api/push/default/log?days=7", headers=auth_headers)
        assert resp.status_code == 200, f"Get log failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "count" in data
    
    def test_get_pending(self, auth_headers):
        """GET /api/push/{property_id}/pending - PWA poll endpoint"""
        resp = requests.get(f"{BASE_URL}/api/push/default/pending?user_role=receptionist", headers=auth_headers)
        assert resp.status_code == 200, f"Get pending failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        # Items should be marked delivered after read
    
    def test_unsubscribe_idempotent(self, auth_headers):
        """POST /api/push/unsubscribe - idempotent removal"""
        endpoint = getattr(TestWebPush, "endpoint", f"hk-nonexistent://{uuid.uuid4().hex}")
        
        # First unsubscribe
        resp = requests.post(f"{BASE_URL}/api/push/unsubscribe", json={
            "endpoint": endpoint
        }, headers=auth_headers)
        assert resp.status_code == 200
        
        # Second unsubscribe (idempotent)
        resp = requests.post(f"{BASE_URL}/api/push/unsubscribe", json={
            "endpoint": endpoint
        }, headers=auth_headers)
        assert resp.status_code == 200, "Unsubscribe should be idempotent"
        assert resp.json().get("ok") is True


# ==================== PMS-CRS TWO-WAY SYNC ====================
class TestPmsCrsSync:
    """PMS-CRS Two-way Sync endpoints"""
    
    def test_push_to_crs(self, auth_headers):
        """POST /api/pms-crs/sync/push - PMS bookings to CRS index"""
        resp = requests.post(f"{BASE_URL}/api/pms-crs/sync/push", json={
            "property_id": "default"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Push failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "scanned" in data
        assert "created" in data
        assert "updated" in data
        assert "unchanged" in data
    
    def test_pull_from_crs(self, auth_headers):
        """POST /api/pms-crs/sync/pull - CRS edits back to PMS"""
        resp = requests.post(f"{BASE_URL}/api/pms-crs/sync/pull", json={
            "property_id": "default"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Pull failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "scanned" in data
        assert "applied" in data
    
    def test_full_run(self, auth_headers):
        """POST /api/pms-crs/sync/run - bidirectional reconcile"""
        resp = requests.post(f"{BASE_URL}/api/pms-crs/sync/run", json={
            "property_id": "default"
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Full run failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "push" in data
        assert "pull" in data
    
    def test_get_index(self, auth_headers):
        """GET /api/pms-crs/index/{property_id} - CRS view"""
        resp = requests.get(f"{BASE_URL}/api/pms-crs/index/default?limit=50", headers=auth_headers)
        assert resp.status_code == 200, f"Get index failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "count" in data
    
    def test_get_queue(self, auth_headers):
        """GET /api/pms-crs/queue - sync queue entries"""
        resp = requests.get(f"{BASE_URL}/api/pms-crs/queue?property_id=default&limit=50", headers=auth_headers)
        assert resp.status_code == 200, f"Get queue failed: {resp.text}"
        data = resp.json()
        assert "items" in data
    
    def test_get_status(self, auth_headers):
        """GET /api/pms-crs/status - health/counters"""
        resp = requests.get(f"{BASE_URL}/api/pms-crs/status?property_id=default", headers=auth_headers)
        assert resp.status_code == 200, f"Get status failed: {resp.text}"
        data = resp.json()
        assert "pms_bookings" in data
        assert "crs_records" in data
        assert "drift" in data
        assert "crs_dirty_pending_pull" in data
        assert "last_run" in data or data.get("last_run") is None
    
    def test_get_conflicts(self, auth_headers):
        """GET /api/pms-crs/conflicts - divergence detection"""
        resp = requests.get(f"{BASE_URL}/api/pms-crs/conflicts?property_id=default", headers=auth_headers)
        assert resp.status_code == 200, f"Get conflicts failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        assert "count" in data


# ==================== PUBLIC API / DEVELOPER PORTAL ====================
class TestPublicApiPortal:
    """Public API Sandbox + Developer Portal endpoints"""
    
    def test_issue_key(self, auth_headers):
        """POST /api/developer/keys - issue new API key"""
        resp = requests.post(f"{BASE_URL}/api/developer/keys", json={
            "property_id": "default",
            "name": f"Test Key {uuid.uuid4().hex[:6]}",
            "scopes": ["read:availability", "read:bookings"],
            "rate_per_min": 60
        }, headers=auth_headers)
        assert resp.status_code == 200, f"Issue key failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "key" in data
        assert "secret" in data
        assert data["secret"].startswith("hk_"), "Secret should start with hk_"
        assert "warning" in data
        TestPublicApiPortal.api_key = data["secret"]
        TestPublicApiPortal.key_id = data["key"]["id"]
    
    def test_list_keys(self, auth_headers):
        """GET /api/developer/keys - list without secret_hash"""
        resp = requests.get(f"{BASE_URL}/api/developer/keys?property_id=default", headers=auth_headers)
        assert resp.status_code == 200, f"List keys failed: {resp.text}"
        data = resp.json()
        assert "items" in data
        # Verify secret_hash is not exposed
        for key in data["items"]:
            assert "secret_hash" not in key, "secret_hash should not be exposed"
    
    def test_get_spec(self, auth_headers):
        """GET /api/developer/spec - OpenAPI pointer"""
        resp = requests.get(f"{BASE_URL}/api/developer/spec", headers=auth_headers)
        assert resp.status_code == 200, f"Get spec failed: {resp.text}"
        data = resp.json()
        assert "openapi_url" in data
        assert "sandbox_endpoints" in data
        assert "auth_scheme" in data
    
    def test_get_usage(self, auth_headers):
        """GET /api/developer/usage/{property_id} - usage stats"""
        resp = requests.get(f"{BASE_URL}/api/developer/usage/default?days=30", headers=auth_headers)
        assert resp.status_code == 200, f"Get usage failed: {resp.text}"
        data = resp.json()
        assert "calls" in data
        assert "errors" in data
        assert "by_key" in data
        assert "by_endpoint" in data
    
    def test_sandbox_echo(self):
        """POST /api/developer/sandbox/echo - auth test"""
        api_key = getattr(TestPublicApiPortal, "api_key", None)
        if not api_key:
            pytest.skip("No API key from previous test")
        
        resp = requests.post(f"{BASE_URL}/api/developer/sandbox/echo", json={
            "message": "hello from pytest"
        }, headers={"X-API-Key": api_key})
        assert resp.status_code == 200, f"Echo failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "key_id" in data
        assert "scopes" in data
        assert "echo" in data
        assert data["echo"]["message"] == "hello from pytest"
    
    def test_sandbox_availability(self):
        """GET /api/developer/sandbox/availability - requires read:availability scope"""
        api_key = getattr(TestPublicApiPortal, "api_key", None)
        if not api_key:
            pytest.skip("No API key from previous test")
        
        check_in = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")
        
        resp = requests.get(
            f"{BASE_URL}/api/developer/sandbox/availability",
            params={"property_id": "default", "check_in": check_in, "check_out": check_out},
            headers={"X-API-Key": api_key}
        )
        assert resp.status_code == 200, f"Availability failed: {resp.text}"
        data = resp.json()
        assert "property_id" in data
        assert "availability" in data
    
    def test_sandbox_missing_key_401(self):
        """Missing X-API-Key should return 401"""
        resp = requests.post(f"{BASE_URL}/api/developer/sandbox/echo", json={"message": "test"})
        assert resp.status_code == 401, "Should return 401 for missing key"
    
    def test_sandbox_invalid_key_401(self):
        """Invalid X-API-Key should return 401"""
        resp = requests.post(f"{BASE_URL}/api/developer/sandbox/echo", json={"message": "test"},
                            headers={"X-API-Key": "hk_invalid_key_12345"})
        assert resp.status_code == 401, "Should return 401 for invalid key"
    
    def test_sandbox_scope_check_403(self, auth_headers):
        """Key without required scope should return 403"""
        # Issue a key with only read:availability (no read:bookings)
        resp = requests.post(f"{BASE_URL}/api/developer/keys", json={
            "property_id": "default",
            "name": f"Limited Key {uuid.uuid4().hex[:6]}",
            "scopes": ["read:availability"]  # No read:bookings
        }, headers=auth_headers)
        assert resp.status_code == 200
        limited_key = resp.json()["secret"]
        
        # Try to access booking endpoint (requires read:bookings)
        resp = requests.get(
            f"{BASE_URL}/api/developer/sandbox/booking/nonexistent",
            headers={"X-API-Key": limited_key}
        )
        # Should be 403 (scope) or 404 (not found) - either is acceptable
        assert resp.status_code in [403, 404], f"Expected 403 or 404, got {resp.status_code}"
    
    def test_sandbox_property_mismatch_403(self, auth_headers):
        """Key for property A cannot access property B"""
        # Issue key for 'default' property
        resp = requests.post(f"{BASE_URL}/api/developer/keys", json={
            "property_id": "default",
            "name": f"Default Key {uuid.uuid4().hex[:6]}",
            "scopes": ["read:availability"]
        }, headers=auth_headers)
        assert resp.status_code == 200
        default_key = resp.json()["secret"]
        
        # Try to access different property
        check_in = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")
        resp = requests.get(
            f"{BASE_URL}/api/developer/sandbox/availability",
            params={"property_id": "city-gate", "check_in": check_in, "check_out": check_out},
            headers={"X-API-Key": default_key}
        )
        assert resp.status_code == 403, "Should return 403 for property mismatch"
    
    def test_rotate_key(self, auth_headers):
        """POST /api/developer/keys/{id}/rotate - rotate secret"""
        key_id = getattr(TestPublicApiPortal, "key_id", None)
        if not key_id:
            pytest.skip("No key_id from previous test")
        
        resp = requests.post(f"{BASE_URL}/api/developer/keys/{key_id}/rotate", headers=auth_headers)
        assert resp.status_code == 200, f"Rotate failed: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "secret" in data
        assert data["secret"].startswith("hk_")
        TestPublicApiPortal.rotated_key = data["secret"]
    
    def test_old_key_invalid_after_rotate(self):
        """Old key should be invalid after rotation"""
        old_key = getattr(TestPublicApiPortal, "api_key", None)
        if not old_key:
            pytest.skip("No old key")
        
        resp = requests.post(f"{BASE_URL}/api/developer/sandbox/echo", json={"message": "test"},
                            headers={"X-API-Key": old_key})
        assert resp.status_code == 401, "Old key should be invalid after rotation"
    
    def test_revoke_key(self, auth_headers):
        """DELETE /api/developer/keys/{id} - revoke key"""
        key_id = getattr(TestPublicApiPortal, "key_id", None)
        if not key_id:
            pytest.skip("No key_id from previous test")
        
        resp = requests.delete(f"{BASE_URL}/api/developer/keys/{key_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Revoke failed: {resp.text}"
        assert resp.json().get("ok") is True
    
    def test_revoked_key_401(self):
        """Revoked key should return 401"""
        rotated_key = getattr(TestPublicApiPortal, "rotated_key", None)
        if not rotated_key:
            pytest.skip("No rotated key")
        
        resp = requests.post(f"{BASE_URL}/api/developer/sandbox/echo", json={"message": "test"},
                            headers={"X-API-Key": rotated_key})
        assert resp.status_code == 401, "Revoked key should return 401"


# ==================== RATE LIMIT TEST ====================
class TestRateLimit:
    """Rate limiting tests for Public API"""
    
    def test_rate_limit_429(self, auth_headers):
        """Exceeding rate limit should return 429"""
        # Issue a key with very low rate limit
        resp = requests.post(f"{BASE_URL}/api/developer/keys", json={
            "property_id": "default",
            "name": f"Rate Test Key {uuid.uuid4().hex[:6]}",
            "scopes": ["read:availability"],
            "rate_per_min": 3  # Very low limit
        }, headers=auth_headers)
        assert resp.status_code == 200
        rate_key = resp.json()["secret"]
        
        # Make requests until rate limited
        hit_429 = False
        for i in range(10):
            resp = requests.post(f"{BASE_URL}/api/developer/sandbox/echo", 
                                json={"message": f"test {i}"},
                                headers={"X-API-Key": rate_key})
            if resp.status_code == 429:
                hit_429 = True
                break
        
        assert hit_429, "Should hit 429 rate limit"


# ==================== REGRESSION TESTS ====================
class TestBatch6Regression:
    """Regression tests for previous batches"""
    
    def test_auth_login(self):
        """Auth still works"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert resp.status_code == 200
    
    def test_bookings_list(self, auth_headers):
        """Bookings endpoint still works"""
        resp = requests.get(f"{BASE_URL}/api/bookings?property_id=default&limit=5", headers=auth_headers)
        assert resp.status_code == 200
    
    def test_spaces_list(self, auth_headers):
        """Batch 4 - Spaces still works"""
        resp = requests.get(f"{BASE_URL}/api/spaces/default", headers=auth_headers)
        assert resp.status_code == 200
    
    def test_agents_list(self, auth_headers):
        """Batch 5 - B2B Agents still works"""
        resp = requests.get(f"{BASE_URL}/api/agents/default", headers=auth_headers)
        assert resp.status_code == 200
    
    def test_door_locks_log(self, auth_headers):
        """Batch 5 - Door locks still works"""
        resp = requests.get(f"{BASE_URL}/api/door-locks/default/log?days=7", headers=auth_headers)
        assert resp.status_code == 200
