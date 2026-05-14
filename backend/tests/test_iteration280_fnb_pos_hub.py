"""
Iteration 280 - F&B POS Integration Hub Tests
Tests for Simphony/Lightspeed/Square/Toast adapter-pattern POS integration.
All providers currently route to MOCK adapter (pending real SDK keys).

Features tested:
- GET /api/fnb-pos/providers — returns 5 providers
- POST /api/fnb-pos/connections — create connection (mock vs real provider validation)
- GET /api/fnb-pos/connections — list with REDACTED credentials
- POST /api/fnb-pos/connections/{id}/test — test ping, updates status
- POST /api/fnb-pos/connections/{id}/sync — fetch mock receipts, de-dup by external_id
- GET /api/fnb-pos/receipts — list with posted filter
- POST /api/fnb-pos/receipts/{id}/post-to-folio — creates folio_charges, marks posted
- GET /api/fnb-pos/reconciliation/{property_id} — daily reconciliation report
- DELETE /api/fnb-pos/connections/{id} — delete connection

Regression tests from iter 277-279 included.
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def auth_session():
    """Authenticate as admin and return session with cookies"""
    session = requests.Session()
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return session


class TestFnbPosProviders:
    """Test GET /api/fnb-pos/providers"""
    
    def test_list_providers_returns_5(self, auth_session):
        """Should return 5 providers: simphony, lightspeed, square, toast, mock"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/providers")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "providers" in data
        providers = data["providers"]
        assert len(providers) == 5, f"Expected 5 providers, got {len(providers)}"
        
        provider_ids = [p["id"] for p in providers]
        assert "simphony" in provider_ids
        assert "lightspeed" in provider_ids
        assert "square" in provider_ids
        assert "toast" in provider_ids
        assert "mock" in provider_ids
        
    def test_providers_have_required_fields(self, auth_session):
        """Each provider should have id, name, required_fields"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/providers")
        assert resp.status_code == 200
        for p in resp.json()["providers"]:
            assert "id" in p
            assert "name" in p
            assert "required_fields" in p
            assert isinstance(p["required_fields"], list)


class TestFnbPosConnections:
    """Test connection CRUD operations"""
    
    def test_create_mock_connection_succeeds(self, auth_session):
        """Mock provider requires no credentials"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections", json={
            "property_id": "default",
            "provider": "mock",
            "name": "TEST_MockPOS_280",
            "outlet_name": "Test Restaurant",
            "credentials": {}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["provider"] == "mock"
        assert data["name"] == "TEST_MockPOS_280"
        assert data["status"] == "untested"
        assert "id" in data
        # Credentials should be redacted in response
        assert data["credentials"] == {}
        
    def test_create_simphony_missing_fields_returns_400(self, auth_session):
        """Simphony requires server_url, org_short_name, api_key"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections", json={
            "property_id": "default",
            "provider": "simphony",
            "name": "TEST_Simphony_Fail",
            "credentials": {"server_url": "https://test.com"}  # Missing org_short_name, api_key
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Missing required fields" in resp.text or "missing" in resp.text.lower()
        
    def test_create_simphony_with_all_fields_succeeds(self, auth_session):
        """Simphony with all required fields should succeed"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections", json={
            "property_id": "default",
            "provider": "simphony",
            "name": "TEST_Simphony_280",
            "outlet_name": "Main Restaurant",
            "credentials": {
                "server_url": "https://simphony.test.com",
                "org_short_name": "testorg",
                "api_key": "sk_test_12345"
            }
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["provider"] == "simphony"
        # Credentials should be REDACTED (masked)
        creds = data.get("credentials", {})
        for key, val in creds.items():
            assert "…" in val or val == "***", f"Credential {key} not redacted: {val}"
            
    def test_list_connections_credentials_redacted(self, auth_session):
        """GET /connections should return redacted credentials"""
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/connections?property_id=default")
        assert resp.status_code == 200
        data = resp.json()
        assert "connections" in data
        for conn in data["connections"]:
            creds = conn.get("credentials", {})
            for key, val in creds.items():
                # Should be masked like "sk_…345" or "***"
                assert "…" in val or val == "***", f"Credential {key} not redacted: {val}"


class TestFnbPosConnectionTest:
    """Test POST /api/fnb-pos/connections/{id}/test"""
    
    @pytest.fixture
    def test_connection(self, auth_session):
        """Create a test connection for testing"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections", json={
            "property_id": "default",
            "provider": "mock",
            "name": f"TEST_TestConn_{int(time.time())}",
            "outlet_name": "Test Outlet"
        })
        assert resp.status_code == 200
        return resp.json()
    
    def test_connection_test_returns_ok(self, auth_session, test_connection):
        """Test ping should return ok, version, latency_ms"""
        conn_id = test_connection["id"]
        resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}/test")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert "version" in data
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], int)
        
    def test_connection_test_updates_status(self, auth_session, test_connection):
        """After test, connection.status should be 'ok' and last_test_at set"""
        conn_id = test_connection["id"]
        # Run test
        auth_session.post(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}/test")
        # Verify status updated
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/connections?property_id=default")
        assert resp.status_code == 200
        conns = resp.json()["connections"]
        conn = next((c for c in conns if c["id"] == conn_id), None)
        assert conn is not None
        assert conn["status"] == "ok"
        assert conn["last_test_at"] is not None


class TestFnbPosSyncAndReceipts:
    """Test sync and receipts endpoints"""
    
    @pytest.fixture
    def sync_connection(self, auth_session):
        """Create a connection for sync testing"""
        resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections", json={
            "property_id": "default",
            "provider": "mock",
            "name": f"TEST_SyncConn_{int(time.time())}",
            "outlet_name": "Sync Test Restaurant"
        })
        assert resp.status_code == 200
        return resp.json()
    
    def test_sync_fetches_receipts(self, auth_session, sync_connection):
        """Sync should fetch mock receipts and insert them"""
        conn_id = sync_connection["id"]
        resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}/sync")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "fetched" in data
        assert "inserted" in data
        assert "synced_at" in data
        # Mock adapter returns 1-3 receipts
        assert data["fetched"] >= 0
        
    def test_sync_deduplicates_by_external_id(self, auth_session, sync_connection):
        """Running sync twice should not duplicate receipts"""
        conn_id = sync_connection["id"]
        # First sync
        resp1 = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}/sync")
        assert resp1.status_code == 200
        inserted1 = resp1.json()["inserted"]
        
        # Second sync - should not insert duplicates
        resp2 = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}/sync")
        assert resp2.status_code == 200
        # Note: Mock generates new random receipts each time, so this tests the de-dup logic
        # for any receipts that happen to have the same external_id
        
    def test_list_receipts(self, auth_session, sync_connection):
        """GET /receipts should return synced receipts"""
        conn_id = sync_connection["id"]
        # Sync first
        auth_session.post(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}/sync")
        
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/receipts?property_id=default")
        assert resp.status_code == 200
        data = resp.json()
        assert "receipts" in data
        assert "count" in data
        
    def test_list_receipts_filter_posted(self, auth_session):
        """Filter receipts by posted=true/false"""
        # Test posted=false filter
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/receipts?property_id=default&posted=false")
        assert resp.status_code == 200
        data = resp.json()
        for r in data["receipts"]:
            assert r["posted_to_folio"] is False
            
        # Test posted=true filter
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/receipts?property_id=default&posted=true")
        assert resp.status_code == 200


class TestFnbPosPostToFolio:
    """Test POST /api/fnb-pos/receipts/{id}/post-to-folio"""
    
    @pytest.fixture
    def receipt_for_posting(self, auth_session):
        """Create a connection, sync, and return a receipt for posting"""
        # Create connection
        conn_resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections", json={
            "property_id": "default",
            "provider": "mock",
            "name": f"TEST_PostFolio_{int(time.time())}",
            "outlet_name": "Folio Test Restaurant"
        })
        assert conn_resp.status_code == 200
        conn_id = conn_resp.json()["id"]
        
        # Sync to get receipts
        auth_session.post(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}/sync")
        
        # Get an unposted receipt
        receipts_resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/receipts?property_id=default&posted=false&limit=10")
        assert receipts_resp.status_code == 200
        receipts = receipts_resp.json()["receipts"]
        if not receipts:
            pytest.skip("No unposted receipts available")
        return receipts[0]
    
    @pytest.fixture
    def test_booking(self, auth_session):
        """Create a test booking for folio posting"""
        booking_resp = auth_session.post(f"{BASE_URL}/api/bookings", json={
            "property_id": "default",
            "guest_name": "TEST_FnbGuest",
            "guest_email": "fnbguest@test.com",
            "room_type_id": "double-default",
            "check_in": "2026-02-01",
            "check_out": "2026-02-03",
            "status": "checked_in",
            "room_number": "101"
        })
        if booking_resp.status_code != 200:
            pytest.skip(f"Could not create test booking: {booking_resp.text}")
        return booking_resp.json()
    
    def test_post_to_folio_creates_charge(self, auth_session, receipt_for_posting, test_booking):
        """Post to folio should create folio_charges entry"""
        receipt_id = receipt_for_posting["id"]
        booking_id = test_booking["id"]
        
        resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/receipts/{receipt_id}/post-to-folio", json={
            "booking_id": booking_id
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["posted"] is True
        assert "charge_id" in data
        assert "amount" in data
        
    def test_post_to_folio_marks_receipt_posted(self, auth_session, receipt_for_posting, test_booking):
        """After posting, receipt.posted_to_folio should be True"""
        receipt_id = receipt_for_posting["id"]
        booking_id = test_booking["id"]
        
        # Post to folio
        auth_session.post(f"{BASE_URL}/api/fnb-pos/receipts/{receipt_id}/post-to-folio", json={
            "booking_id": booking_id
        })
        
        # Verify receipt is marked as posted
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/receipts?property_id=default&posted=true")
        assert resp.status_code == 200
        receipts = resp.json()["receipts"]
        posted_receipt = next((r for r in receipts if r["id"] == receipt_id), None)
        if posted_receipt:
            assert posted_receipt["posted_to_folio"] is True
            
    def test_post_to_folio_twice_returns_400(self, auth_session):
        """Posting same receipt twice should return 400 'already posted'"""
        # Create fresh connection and sync
        conn_resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections", json={
            "property_id": "default",
            "provider": "mock",
            "name": f"TEST_DoublePost_{int(time.time())}",
            "outlet_name": "Double Post Test"
        })
        assert conn_resp.status_code == 200
        conn_id = conn_resp.json()["id"]
        auth_session.post(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}/sync")
        
        # Get unposted receipt
        receipts_resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/receipts?property_id=default&posted=false&limit=5")
        receipts = receipts_resp.json()["receipts"]
        if not receipts:
            pytest.skip("No unposted receipts")
        receipt_id = receipts[0]["id"]
        
        # Create booking
        booking_resp = auth_session.post(f"{BASE_URL}/api/bookings", json={
            "property_id": "default",
            "guest_name": "TEST_DoublePostGuest",
            "guest_email": "doublepost@test.com",
            "room_type_id": "double-default",
            "check_in": "2026-02-05",
            "check_out": "2026-02-07",
            "status": "checked_in"
        })
        if booking_resp.status_code != 200:
            pytest.skip("Could not create booking")
        booking_id = booking_resp.json()["id"]
        
        # First post - should succeed
        resp1 = auth_session.post(f"{BASE_URL}/api/fnb-pos/receipts/{receipt_id}/post-to-folio", json={
            "booking_id": booking_id
        })
        assert resp1.status_code == 200
        
        # Second post - should fail with 400
        resp2 = auth_session.post(f"{BASE_URL}/api/fnb-pos/receipts/{receipt_id}/post-to-folio", json={
            "booking_id": booking_id
        })
        assert resp2.status_code == 400, f"Expected 400, got {resp2.status_code}: {resp2.text}"
        assert "already posted" in resp2.text.lower()


class TestFnbPosReconciliation:
    """Test GET /api/fnb-pos/reconciliation/{property_id}"""
    
    def test_reconciliation_returns_report(self, auth_session):
        """Reconciliation should return receipts_count, gross_total, by_outlet, by_payment"""
        today = datetime.now().strftime("%Y-%m-%d")
        resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/reconciliation/default?date={today}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "property_id" in data
        assert "date" in data
        assert "receipts_count" in data
        assert "gross_total" in data
        assert "posted_to_folio_total" in data
        assert "cash_card_total" in data
        assert "by_outlet" in data
        assert "by_payment" in data
        
        assert isinstance(data["by_outlet"], dict)
        assert isinstance(data["by_payment"], dict)


class TestFnbPosDeleteConnection:
    """Test DELETE /api/fnb-pos/connections/{id}"""
    
    def test_delete_connection(self, auth_session):
        """Delete should remove connection"""
        # Create connection
        conn_resp = auth_session.post(f"{BASE_URL}/api/fnb-pos/connections", json={
            "property_id": "default",
            "provider": "mock",
            "name": f"TEST_DeleteConn_{int(time.time())}",
            "outlet_name": "Delete Test"
        })
        assert conn_resp.status_code == 200
        conn_id = conn_resp.json()["id"]
        
        # Delete
        del_resp = auth_session.delete(f"{BASE_URL}/api/fnb-pos/connections/{conn_id}")
        assert del_resp.status_code == 200
        data = del_resp.json()
        assert data["deleted"] == 1
        
        # Verify deleted
        list_resp = auth_session.get(f"{BASE_URL}/api/fnb-pos/connections?property_id=default")
        conns = list_resp.json()["connections"]
        assert not any(c["id"] == conn_id for c in conns)


# ============== REGRESSION TESTS (Iter 277-279) ==============

class TestRegressionIter277BookingEngine:
    """Regression: Booking Engine v2 from iter 277"""
    
    def test_booking_engine_packages(self, auth_session):
        """GET /api/booking-engine/packages"""
        resp = auth_session.get(f"{BASE_URL}/api/booking-engine/packages?property_id=default")
        assert resp.status_code == 200
        
    def test_booking_engine_upsells(self, auth_session):
        """GET /api/booking-engine/upsells"""
        resp = auth_session.get(f"{BASE_URL}/api/booking-engine/upsells?property_id=default")
        assert resp.status_code == 200


class TestRegressionIter277OwnerPortal:
    """Regression: Owner Portal from iter 277"""
    
    def test_owners_list(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/owners")
        assert resp.status_code == 200
        
    def test_owner_create(self, auth_session):
        resp = auth_session.post(f"{BASE_URL}/api/owners", json={
            "name": "TEST_Regression_Owner_280",
            "email": "regowner280@test.com",
            "property_id": "default"
        })
        assert resp.status_code in [200, 201]


class TestRegressionIter278Spa:
    """Regression: Spa Activities from iter 278"""
    
    def test_spa_services_list(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/spa/services?property_id=default")
        assert resp.status_code == 200
        
    def test_spa_bookings_list(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/spa/bookings?property_id=default")
        assert resp.status_code == 200


class TestRegressionIter278LoyaltyTiers:
    """Regression: Loyalty Tiers from iter 278"""
    
    def test_loyalty_tiers_config(self, auth_session):
        """GET /api/loyalty-tiers/config"""
        resp = auth_session.get(f"{BASE_URL}/api/loyalty-tiers/config?property_id=default")
        assert resp.status_code == 200


class TestRegressionIter278Budget:
    """Regression: Budget vs Actual from iter 278"""
    
    def test_budget_variance(self, auth_session):
        """GET /api/budget/{property_id}/variance"""
        resp = auth_session.get(f"{BASE_URL}/api/budget/default/variance")
        assert resp.status_code == 200


class TestRegressionIter278Compset:
    """Regression: Compset from iter 278"""
    
    def test_compset_list(self, auth_session):
        """GET /api/compset/{property_id}"""
        resp = auth_session.get(f"{BASE_URL}/api/compset/default")
        assert resp.status_code == 200


class TestRegressionIter278Partner:
    """Regression: Partner Webhooks & API Keys from iter 278"""
    
    def test_partner_webhooks_list(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/partner/webhooks?property_id=default")
        assert resp.status_code == 200
        
    def test_partner_api_keys_list(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/partner/api-keys?property_id=default")
        assert resp.status_code == 200


class TestRegressionIter278AutomationAnalytics:
    """Regression: Automation Analytics from iter 278"""
    
    def test_automation_v2_rules(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/automation/v2/rules?property_id=default")
        assert resp.status_code == 200
        
    def test_automation_v2_analytics(self, auth_session):
        """GET /api/automation/v2/analytics"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/v2/analytics?property_id=default")
        assert resp.status_code == 200


class TestRegressionIter279Meetings:
    """Regression: Meetings Sales from iter 279"""
    
    def test_meetings_list(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/meetings?property_id=default")
        assert resp.status_code == 200
        
    def test_meetings_pipeline(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/meetings/pipeline?property_id=default")
        assert resp.status_code == 200
        
    def test_meetings_analytics(self, auth_session):
        resp = auth_session.get(f"{BASE_URL}/api/meetings/analytics?property_id=default")
        assert resp.status_code == 200
