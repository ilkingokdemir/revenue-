"""
Iteration 287 Tests - Developer Portal, Wholesaler Network, Lead Funnel, Lighthouse Adapter

Tests for:
1. Public Developer Portal (Mews Marketplace v2 parity)
   - GET /api/dev-portal/info (no auth)
   - POST /api/dev-portal/register
   - POST /api/dev-portal/login
   - GET /api/dev-portal/me
   - POST /api/dev-portal/apps (OAuth app creation)
   - GET /api/dev-portal/apps
   - POST /api/dev-portal/apps/{id}/keys (API key generation)
   - GET /api/dev-portal/apps/{id}/keys
   - DELETE /api/dev-portal/apps/{id}/keys/{key_id}
   - GET /api/dev-portal/apps/{id}/stats
   - POST /api/dev-portal/apps/{id}/revenue-share/opt-in
   - Admin: GET /api/dev-portal/admin/apps
   - Admin: POST /api/dev-portal/admin/apps/{id}/approve
   - Admin: POST /api/dev-portal/admin/apps/{id}/suspend

2. Wholesaler / Net Rate Network (Cloudbeds Hotel Trader parity)
   - GET /api/wholesaler/providers
   - POST /api/wholesaler/connections
   - GET /api/wholesaler/connections
   - PATCH /api/wholesaler/connections/{id}
   - DELETE /api/wholesaler/connections/{id}
   - POST /api/wholesaler/connections/{id}/test
   - POST /api/wholesaler/connections/{id}/push
   - POST /api/wholesaler/dispatch
   - GET /api/wholesaler/inbound-bookings
   - GET /api/wholesaler/queue

3. Lead Funnel Bridge
   - POST /api/lead-funnel/ingest-concierge-sessions/{property_id}
   - GET /api/lead-funnel/leads
   - PATCH /api/lead-funnel/leads/{id}
   - POST /api/lead-funnel/leads/{id}/convert

4. Lighthouse Compset Adapter
   - GET /api/lighthouse-adapter/status
   - POST /api/lighthouse-adapter/refresh/{property_id}
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test developer credentials
TEST_DEV_EMAIL = f"test_dev_{uuid.uuid4().hex[:8]}@example.com"
TEST_DEV_PASSWORD = "TestDev2026!"
TEST_DEV_NAME = "Test Developer 287"
TEST_DEV_COMPANY = "Test Company 287"


@pytest.fixture(scope="module")
def admin_session():
    """Get admin session with auth cookie"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login as admin
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return session


@pytest.fixture(scope="module")
def developer_token():
    """Register a new developer and get their token"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Register developer
    resp = session.post(f"{BASE_URL}/api/dev-portal/register", json={
        "email": TEST_DEV_EMAIL,
        "password": TEST_DEV_PASSWORD,
        "name": TEST_DEV_NAME,
        "company": TEST_DEV_COMPANY
    })
    assert resp.status_code == 200, f"Developer registration failed: {resp.text}"
    data = resp.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def developer_session(developer_token):
    """Get developer session with Bearer token"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {developer_token}"
    })
    return session


class TestDevPortalPublic:
    """Developer Portal - Public endpoints (no auth)"""
    
    def test_info_endpoint_returns_metadata(self):
        """GET /api/dev-portal/info returns platform metadata"""
        resp = requests.get(f"{BASE_URL}/api/dev-portal/info")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify required fields
        assert data["platform"] == "HotelBox Developer Portal"
        assert "version" in data
        assert "scopes" in data
        assert len(data["scopes"]) == 10, f"Expected 10 scopes, got {len(data['scopes'])}"
        
        # Verify rate limits
        assert "rate_limits" in data
        assert data["rate_limits"]["default"] == "10 req/sec per app"
        
        # Verify revenue share program
        assert "revenue_share_program" in data
        assert data["revenue_share_program"]["default_share_percent"] == 10
        
        # Verify sandbox info
        assert "sandbox" in data
        assert data["sandbox"]["free"] == True
        print(f"✓ Dev portal info: {len(data['scopes'])} scopes, rate limit: {data['rate_limits']['default']}")
    
    def test_register_developer_success(self):
        """POST /api/dev-portal/register creates developer account"""
        unique_email = f"test_reg_{uuid.uuid4().hex[:8]}@example.com"
        resp = requests.post(f"{BASE_URL}/api/dev-portal/register", json={
            "email": unique_email,
            "password": "TestPass2026!",
            "name": "Test Registration",
            "company": "Test Corp"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "developer" in data
        assert data["developer"]["email"] == unique_email
        print(f"✓ Developer registered: {unique_email}")
    
    def test_register_duplicate_email_returns_409(self):
        """POST /api/dev-portal/register with duplicate email returns 409"""
        # First registration
        unique_email = f"test_dup_{uuid.uuid4().hex[:8]}@example.com"
        resp1 = requests.post(f"{BASE_URL}/api/dev-portal/register", json={
            "email": unique_email,
            "password": "TestPass2026!",
            "name": "First Dev"
        })
        assert resp1.status_code == 200
        
        # Duplicate registration
        resp2 = requests.post(f"{BASE_URL}/api/dev-portal/register", json={
            "email": unique_email,
            "password": "TestPass2026!",
            "name": "Second Dev"
        })
        assert resp2.status_code == 409
        print(f"✓ Duplicate email correctly rejected with 409")
    
    def test_register_short_password_returns_400(self):
        """POST /api/dev-portal/register with short password returns 400"""
        resp = requests.post(f"{BASE_URL}/api/dev-portal/register", json={
            "email": f"test_short_{uuid.uuid4().hex[:8]}@example.com",
            "password": "short",  # Less than 8 chars
            "name": "Test"
        })
        assert resp.status_code == 400
        print(f"✓ Short password correctly rejected with 400")
    
    def test_login_developer_success(self, developer_token):
        """POST /api/dev-portal/login validates credentials"""
        resp = requests.post(f"{BASE_URL}/api/dev-portal/login", json={
            "email": TEST_DEV_EMAIL,
            "password": TEST_DEV_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["developer"]["email"] == TEST_DEV_EMAIL
        print(f"✓ Developer login successful")
    
    def test_login_invalid_credentials_returns_401(self):
        """POST /api/dev-portal/login with wrong password returns 401"""
        resp = requests.post(f"{BASE_URL}/api/dev-portal/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        assert resp.status_code == 401
        print(f"✓ Invalid credentials correctly rejected with 401")


class TestDevPortalAuthenticated:
    """Developer Portal - Authenticated developer endpoints"""
    
    def test_me_returns_developer_profile(self, developer_session):
        """GET /api/dev-portal/me returns developer profile without password_hash"""
        resp = developer_session.get(f"{BASE_URL}/api/dev-portal/me")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["email"] == TEST_DEV_EMAIL
        assert data["name"] == TEST_DEV_NAME
        assert data["company"] == TEST_DEV_COMPANY
        assert "password_hash" not in data
        print(f"✓ Developer profile retrieved (no password_hash)")
    
    def test_create_oauth_app(self, developer_session):
        """POST /api/dev-portal/apps creates OAuth app with client_id and client_secret"""
        resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps", json={
            "name": "TEST_App_287",
            "description": "Test OAuth app for iteration 287",
            "category": "pms_integration",
            "scopes": ["read:bookings", "write:bookings"]
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify client_id format (hb_*)
        assert data["client_id"].startswith("hb_"), f"client_id should start with hb_, got {data['client_id']}"
        
        # Verify client_secret is returned (one-time only)
        assert "client_secret" in data
        assert len(data["client_secret"]) > 20
        
        # Verify other fields
        assert data["name"] == "TEST_App_287"
        assert data["status"] == "pending_review"
        assert data["revenue_share_enrolled"] == False
        assert "note" in data  # Warning about one-time secret
        
        print(f"✓ OAuth app created: client_id={data['client_id'][:15]}...")
        return data["id"]
    
    def test_list_apps_without_secrets(self, developer_session):
        """GET /api/dev-portal/apps lists apps without client_secret_hash"""
        resp = developer_session.get(f"{BASE_URL}/api/dev-portal/apps")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        
        # Verify no secrets in response
        for app in data["items"]:
            assert "client_secret_hash" not in app
            assert "client_secret" not in app
        
        print(f"✓ Listed {data['count']} apps (no secrets exposed)")
    
    def test_create_api_key(self, developer_session):
        """POST /api/dev-portal/apps/{id}/keys generates API key with hbk_* prefix"""
        # First create an app
        app_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps", json={
            "name": "TEST_KeyApp_287"
        })
        assert app_resp.status_code == 200
        app_id = app_resp.json()["id"]
        
        # Create API key
        key_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps/{app_id}/keys", json={
            "label": "Test API Key",
            "scopes": ["read:bookings"]
        })
        assert key_resp.status_code == 200
        key_data = key_resp.json()
        
        # Verify key format (hbk_*)
        assert key_data["key"].startswith("hbk_"), f"API key should start with hbk_, got {key_data['key'][:10]}"
        assert "prefix" in key_data
        assert key_data["prefix"] == key_data["key"][:10]
        assert "note" in key_data  # Warning about one-time key
        
        print(f"✓ API key created: prefix={key_data['prefix']}")
        return app_id, key_data["id"]
    
    def test_list_keys_without_hash(self, developer_session):
        """GET /api/dev-portal/apps/{id}/keys lists keys without key_hash"""
        # Create app and key
        app_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps", json={
            "name": "TEST_ListKeys_287"
        })
        app_id = app_resp.json()["id"]
        developer_session.post(f"{BASE_URL}/api/dev-portal/apps/{app_id}/keys", json={
            "label": "Key for listing"
        })
        
        # List keys
        resp = developer_session.get(f"{BASE_URL}/api/dev-portal/apps/{app_id}/keys")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "items" in data
        for key in data["items"]:
            assert "key_hash" not in key
            assert "key" not in key  # Full key not returned
            assert "prefix" in key
        
        print(f"✓ Listed {data['count']} keys (no hashes exposed)")
    
    def test_revoke_api_key(self, developer_session):
        """DELETE /api/dev-portal/apps/{id}/keys/{key_id} revokes key"""
        # Create app and key
        app_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps", json={
            "name": "TEST_RevokeKey_287"
        })
        app_id = app_resp.json()["id"]
        key_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps/{app_id}/keys", json={
            "label": "Key to revoke"
        })
        key_id = key_resp.json()["id"]
        
        # Revoke key
        del_resp = developer_session.delete(f"{BASE_URL}/api/dev-portal/apps/{app_id}/keys/{key_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["ok"] == True
        
        print(f"✓ API key revoked successfully")
    
    def test_app_stats(self, developer_session):
        """GET /api/dev-portal/apps/{id}/stats returns usage statistics"""
        # Create app
        app_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps", json={
            "name": "TEST_Stats_287"
        })
        app_id = app_resp.json()["id"]
        
        # Get stats
        resp = developer_session.get(f"{BASE_URL}/api/dev-portal/apps/{app_id}/stats")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["app_id"] == app_id
        assert "total_calls" in data
        assert "keys" in data
        assert "rate_limit" in data
        
        print(f"✓ App stats retrieved: total_calls={data['total_calls']}")
    
    def test_revenue_share_opt_in(self, developer_session):
        """POST /api/dev-portal/apps/{id}/revenue-share/opt-in enrolls in revenue share"""
        # Create app
        app_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps", json={
            "name": "TEST_RevShare_287"
        })
        app_id = app_resp.json()["id"]
        
        # Opt in to revenue share
        resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps/{app_id}/revenue-share/opt-in", json={
            "share_percent": 15,
            "payout_email": "payout@example.com"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["ok"] == True
        assert data["share_percent"] == 15
        
        print(f"✓ Revenue share opt-in: {data['share_percent']}%")


class TestDevPortalAdmin:
    """Developer Portal - Admin endpoints"""
    
    def test_admin_list_all_apps(self, admin_session):
        """GET /api/dev-portal/admin/apps returns all apps with developer info"""
        resp = admin_session.get(f"{BASE_URL}/api/dev-portal/admin/apps")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        
        # Verify enrichment with developer info
        if data["items"]:
            app = data["items"][0]
            assert "developer_email" in app or "developer_id" in app
        
        print(f"✓ Admin listed {data['count']} apps")
    
    def test_admin_approve_app(self, admin_session, developer_session):
        """POST /api/dev-portal/admin/apps/{id}/approve updates status to approved"""
        # Create app as developer
        app_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps", json={
            "name": "TEST_Approve_287"
        })
        app_id = app_resp.json()["id"]
        
        # Approve as admin
        resp = admin_session.post(f"{BASE_URL}/api/dev-portal/admin/apps/{app_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["ok"] == True
        
        # Verify status changed
        apps_resp = admin_session.get(f"{BASE_URL}/api/dev-portal/admin/apps")
        approved_app = next((a for a in apps_resp.json()["items"] if a["id"] == app_id), None)
        assert approved_app["status"] == "approved"
        
        print(f"✓ App approved by admin")
    
    def test_admin_suspend_app(self, admin_session, developer_session):
        """POST /api/dev-portal/admin/apps/{id}/suspend updates status to suspended"""
        # Create app as developer
        app_resp = developer_session.post(f"{BASE_URL}/api/dev-portal/apps", json={
            "name": "TEST_Suspend_287"
        })
        app_id = app_resp.json()["id"]
        
        # Suspend as admin
        resp = admin_session.post(f"{BASE_URL}/api/dev-portal/admin/apps/{app_id}/suspend", json={
            "reason": "Test suspension"
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] == True
        
        # Verify status changed
        apps_resp = admin_session.get(f"{BASE_URL}/api/dev-portal/admin/apps")
        suspended_app = next((a for a in apps_resp.json()["items"] if a["id"] == app_id), None)
        assert suspended_app["status"] == "suspended"
        
        print(f"✓ App suspended by admin")


class TestWholesalerProviders:
    """Wholesaler Network - Provider catalog"""
    
    def test_list_providers(self, admin_session):
        """GET /api/wholesaler/providers returns 5 providers"""
        resp = admin_session.get(f"{BASE_URL}/api/wholesaler/providers")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "items" in data
        assert len(data["items"]) == 5, f"Expected 5 providers, got {len(data['items'])}"
        
        # Verify provider IDs
        provider_ids = {p["id"] for p in data["items"]}
        expected = {"hotelbeds", "tbo", "travelgate", "gta", "mock"}
        assert provider_ids == expected, f"Expected providers {expected}, got {provider_ids}"
        
        # Verify provider structure
        for p in data["items"]:
            assert "auth_fields" in p
            assert "supports_push" in p
            assert "default_commission" in p
            assert "partner_count_global" in p
        
        print(f"✓ Listed 5 providers: {', '.join(provider_ids)}")


class TestWholesalerConnections:
    """Wholesaler Network - Connection management"""
    
    def test_create_connection(self, admin_session):
        """POST /api/wholesaler/connections creates connection"""
        resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections", json={
            "property_id": "aldgate-flats",
            "provider": "mock",
            "label": "TEST_Connection_287",
            "commission_percent": 12
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["provider"] == "mock"
        assert data["property_id"] == "aldgate-flats"
        assert data["commission_percent"] == 12
        assert data["status"] == "configured"
        assert data["is_active"] == True
        
        # Verify credentials are redacted
        assert all(v == "***" for v in data.get("credentials", {}).values()) or data.get("credentials") == {}
        
        print(f"✓ Connection created: {data['id'][:8]}...")
        return data["id"]
    
    def test_create_connection_unknown_provider_returns_400(self, admin_session):
        """POST /api/wholesaler/connections with unknown provider returns 400"""
        resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections", json={
            "property_id": "aldgate-flats",
            "provider": "unknown_provider"
        })
        assert resp.status_code == 400
        print(f"✓ Unknown provider correctly rejected with 400")
    
    def test_list_connections(self, admin_session):
        """GET /api/wholesaler/connections lists connections"""
        resp = admin_session.get(f"{BASE_URL}/api/wholesaler/connections")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        
        # Verify credentials not exposed
        for conn in data["items"]:
            assert "credentials" not in conn
        
        print(f"✓ Listed {data['count']} connections")
    
    def test_test_connection(self, admin_session):
        """POST /api/wholesaler/connections/{id}/test updates status to online"""
        # Create connection
        create_resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections", json={
            "property_id": "aldgate-flats",
            "provider": "mock",
            "label": "TEST_TestConn_287"
        })
        conn_id = create_resp.json()["id"]
        
        # Test connection
        resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections/{conn_id}/test")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["ok"] == True
        assert data["status"] == "online"
        assert "result" in data
        
        print(f"✓ Connection tested: status={data['status']}")
    
    def test_push_rates(self, admin_session):
        """POST /api/wholesaler/connections/{id}/push creates queued job"""
        # Create connection
        create_resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections", json={
            "property_id": "aldgate-flats",
            "provider": "mock",
            "label": "TEST_PushConn_287"
        })
        conn_id = create_resp.json()["id"]
        
        # Push rates
        resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections/{conn_id}/push", json={
            "dates": [
                {"date": "2026-02-01", "rate": 100},
                {"date": "2026-02-02", "rate": 110}
            ],
            "room_type_id": "standard"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["ok"] == True
        assert data["pushed"] == 2
        assert "reference" in data
        
        print(f"✓ Pushed 2 rates, reference={data['reference']}")
    
    def test_push_rates_no_dates_returns_400(self, admin_session):
        """POST /api/wholesaler/connections/{id}/push without dates returns 400"""
        # Create connection
        create_resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections", json={
            "property_id": "aldgate-flats",
            "provider": "mock"
        })
        conn_id = create_resp.json()["id"]
        
        # Push without dates
        resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections/{conn_id}/push", json={})
        assert resp.status_code == 400
        print(f"✓ Push without dates correctly rejected with 400")
    
    def test_patch_connection(self, admin_session):
        """PATCH /api/wholesaler/connections/{id} updates connection"""
        # Create connection
        create_resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections", json={
            "property_id": "aldgate-flats",
            "provider": "mock",
            "commission_percent": 10
        })
        conn_id = create_resp.json()["id"]
        
        # Patch
        resp = admin_session.patch(f"{BASE_URL}/api/wholesaler/connections/{conn_id}", json={
            "commission_percent": 15,
            "label": "Updated Label"
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] == True
        
        print(f"✓ Connection patched")
    
    def test_delete_connection(self, admin_session):
        """DELETE /api/wholesaler/connections/{id} removes connection"""
        # Create connection
        create_resp = admin_session.post(f"{BASE_URL}/api/wholesaler/connections", json={
            "property_id": "aldgate-flats",
            "provider": "mock",
            "label": "TEST_DeleteConn_287"
        })
        conn_id = create_resp.json()["id"]
        
        # Delete
        resp = admin_session.delete(f"{BASE_URL}/api/wholesaler/connections/{conn_id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] == True
        
        print(f"✓ Connection deleted")


class TestWholesalerDispatch:
    """Wholesaler Network - Inbound dispatch and bookings"""
    
    def test_dispatch_inbound(self, admin_session):
        """POST /api/wholesaler/dispatch polls connections for inbound bookings"""
        # Ensure at least one active connection exists
        admin_session.post(f"{BASE_URL}/api/wholesaler/connections", json={
            "property_id": "aldgate-flats",
            "provider": "mock",
            "label": "TEST_DispatchConn_287"
        })
        
        # Dispatch
        resp = admin_session.post(f"{BASE_URL}/api/wholesaler/dispatch")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["ok"] == True
        assert "total_new" in data
        assert "connections_polled" in data
        assert "per_provider" in data
        
        print(f"✓ Dispatch: {data['total_new']} new bookings from {data['connections_polled']} connections")
    
    def test_list_inbound_bookings(self, admin_session):
        """GET /api/wholesaler/inbound-bookings lists imported bookings"""
        resp = admin_session.get(f"{BASE_URL}/api/wholesaler/inbound-bookings")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        
        # Verify booking structure if any exist
        if data["items"]:
            booking = data["items"][0]
            assert "external_id" in booking
            assert "guest_name" in booking
            assert "check_in" in booking
            assert "net_rate" in booking
        
        print(f"✓ Listed {data['count']} inbound bookings")
    
    def test_list_queue(self, admin_session):
        """GET /api/wholesaler/queue lists sync jobs"""
        resp = admin_session.get(f"{BASE_URL}/api/wholesaler/queue")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        
        print(f"✓ Listed {data['count']} queue jobs")


class TestLeadFunnel:
    """Lead Funnel Bridge - Web Concierge to CRM"""
    
    def test_ingest_concierge_sessions(self, admin_session):
        """POST /api/lead-funnel/ingest-concierge-sessions/{property_id} creates leads"""
        # First, create a web concierge session with intent keywords
        chat_resp = admin_session.post(f"{BASE_URL}/api/web-concierge/chat", json={
            "property_id": "aldgate-flats",
            "session_id": f"test_session_{uuid.uuid4().hex[:8]}",
            "message": "Merhaba, 2 kişi için rezervasyon yapmak istiyorum. Fiyatlar nedir?"
        })
        # Chat may return 200 or other status depending on implementation
        
        # Ingest sessions
        resp = admin_session.post(f"{BASE_URL}/api/lead-funnel/ingest-concierge-sessions/aldgate-flats", json={
            "limit": 100,
            "cutoff_hours": 168
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["ok"] == True
        assert "scanned" in data
        assert "created" in data
        assert "skipped_duplicates" in data
        
        print(f"✓ Ingested: scanned={data['scanned']}, created={data['created']}, skipped={data['skipped_duplicates']}")
    
    def test_list_leads(self, admin_session):
        """GET /api/lead-funnel/leads lists leads with counts_by_status"""
        resp = admin_session.get(f"{BASE_URL}/api/lead-funnel/leads?property_id=aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "items" in data
        assert "count" in data
        assert "counts_by_status" in data
        
        # Verify counts structure
        counts = data["counts_by_status"]
        for status in ["new", "contacted", "qualified", "won", "lost"]:
            assert status in counts
        
        print(f"✓ Listed {data['count']} leads, counts: {counts}")
    
    def test_update_lead_status(self, admin_session):
        """PATCH /api/lead-funnel/leads/{id} updates status"""
        # Get existing leads or create one via ingest
        admin_session.post(f"{BASE_URL}/api/lead-funnel/ingest-concierge-sessions/aldgate-flats", json={
            "limit": 10
        })
        
        leads_resp = admin_session.get(f"{BASE_URL}/api/lead-funnel/leads?property_id=aldgate-flats")
        leads = leads_resp.json().get("items", [])
        
        if leads:
            lead_id = leads[0]["id"]
            
            # Update status
            resp = admin_session.patch(f"{BASE_URL}/api/lead-funnel/leads/{lead_id}", json={
                "status": "contacted",
                "notes": "Called and left voicemail"
            })
            assert resp.status_code == 200
            assert resp.json()["ok"] == True
            
            print(f"✓ Lead status updated to 'contacted'")
        else:
            print(f"⚠ No leads to update (skipped)")
    
    def test_convert_lead(self, admin_session):
        """POST /api/lead-funnel/leads/{id}/convert marks as won"""
        # Get existing leads
        leads_resp = admin_session.get(f"{BASE_URL}/api/lead-funnel/leads?property_id=aldgate-flats")
        leads = leads_resp.json().get("items", [])
        
        if leads:
            lead_id = leads[0]["id"]
            
            # Convert lead
            resp = admin_session.post(f"{BASE_URL}/api/lead-funnel/leads/{lead_id}/convert", json={
                "booking_id": "test-booking-123"
            })
            assert resp.status_code == 200
            assert resp.json()["ok"] == True
            
            print(f"✓ Lead converted to booking")
        else:
            print(f"⚠ No leads to convert (skipped)")
    
    def test_convert_lead_without_booking_id_returns_400(self, admin_session):
        """POST /api/lead-funnel/leads/{id}/convert without booking_id returns 400"""
        leads_resp = admin_session.get(f"{BASE_URL}/api/lead-funnel/leads?property_id=aldgate-flats")
        leads = leads_resp.json().get("items", [])
        
        if leads:
            lead_id = leads[0]["id"]
            resp = admin_session.post(f"{BASE_URL}/api/lead-funnel/leads/{lead_id}/convert", json={})
            assert resp.status_code == 400
            print(f"✓ Convert without booking_id correctly rejected with 400")
        else:
            print(f"⚠ No leads to test (skipped)")


class TestLighthouseAdapter:
    """Lighthouse Compset Adapter"""
    
    def test_adapter_status(self, admin_session):
        """GET /api/lighthouse-adapter/status returns mock status without API key"""
        resp = admin_session.get(f"{BASE_URL}/api/lighthouse-adapter/status")
        assert resp.status_code == 200
        data = resp.json()
        
        # Without LIGHTHOUSE_API_KEY, should be mock
        assert data["provider"] == "mock"
        assert data["real_data"] == False
        assert "note" in data
        
        print(f"✓ Lighthouse status: provider={data['provider']}, real_data={data['real_data']}")
    
    def test_refresh_compset(self, admin_session):
        """POST /api/lighthouse-adapter/refresh/{property_id} returns mock snapshot"""
        resp = admin_session.post(f"{BASE_URL}/api/lighthouse-adapter/refresh/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify snapshot structure
        assert data["provider"] == "lighthouse_mock"
        assert data["property_id"] == "aldgate-flats"
        assert "competitors" in data
        assert len(data["competitors"]) == 5
        
        # Verify competitor names
        competitor_names = {c["name"] for c in data["competitors"]}
        expected_names = {"Marriott London City", "Hilton Whitechapel", "Premier Inn Aldgate", 
                         "ibis London City", "Holiday Inn Express"}
        assert competitor_names == expected_names
        
        # Verify market average and data points
        assert "market_average" in data
        assert "data_points_sampled" in data
        assert data["data_points_sampled"] >= 2_800_000_000
        
        print(f"✓ Compset refresh: {len(data['competitors'])} competitors, market_avg=£{data['market_average']}")


class TestRegressionIter286:
    """Regression tests for previous iteration features"""
    
    def test_agents_endpoint(self, admin_session):
        """GET /api/agents still works (Iter 286)"""
        resp = admin_session.get(f"{BASE_URL}/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        print(f"✓ Regression: /api/agents works ({data.get('count', len(data.get('items', [])))} agents)")
    
    def test_vacation_rental_summary(self, admin_session):
        """GET /api/vacation-rental/summary still works (Iter 286)"""
        resp = admin_session.get(f"{BASE_URL}/api/vacation-rental/summary?year=2026")
        assert resp.status_code == 200
        data = resp.json()
        # Data is nested under 'kpis' key
        assert "kpis" in data or "property_count" in data
        kpis = data.get("kpis", data)
        print(f"✓ Regression: /api/vacation-rental/summary works ({kpis.get('property_count')} properties)")
    
    def test_properties_endpoint(self, admin_session):
        """GET /api/properties still works"""
        resp = admin_session.get(f"{BASE_URL}/api/properties")
        assert resp.status_code == 200
        print(f"✓ Regression: /api/properties works")
    
    def test_open_pricing_segments(self, admin_session):
        """GET /api/open-pricing/segments still works (Iter 285)"""
        resp = admin_session.get(f"{BASE_URL}/api/open-pricing/segments")
        assert resp.status_code == 200
        print(f"✓ Regression: /api/open-pricing/segments works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
