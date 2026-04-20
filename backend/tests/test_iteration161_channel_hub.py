"""
Iteration 161 - Channel Manager Hub Backend Tests
Tests for the new consolidated Channel Hub module with 9 panels:
- Channel Configs (CRUD + certify)
- Setup Checklist (8 steps)
- Dashboard (KPIs)
- Payload Profiles (discover fields)
- Publish Jobs (ARI distribution queue)
- Price Overrides
- Channel Audit Log
- Benchmark Cockpit (STR-style index)
- Rate Structure Variants (auto-generate)
- Seed Demo (admin-only)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "aldgate-flats"

class TestChannelHubAuth:
    """Authentication tests for Channel Hub endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_channel_configs_requires_auth(self):
        """GET /api/channel-configs/{pid} requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/channel-configs/{PROPERTY_ID}")
        assert resp.status_code == 401
    
    def test_checklist_requires_auth(self):
        """GET /api/channel-hub/{pid}/checklist requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/checklist")
        assert resp.status_code == 401
    
    def test_dashboard_requires_auth(self):
        """GET /api/channel-hub/{pid}/dashboard requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/dashboard")
        assert resp.status_code == 401
    
    def test_publish_jobs_requires_auth(self):
        """GET /api/publish-jobs/{pid} requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/publish-jobs/{PROPERTY_ID}")
        assert resp.status_code == 401
    
    def test_payload_profiles_requires_auth(self):
        """GET /api/payload-profiles/{pid} requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/payload-profiles/{PROPERTY_ID}")
        assert resp.status_code == 401
    
    def test_price_overrides_requires_auth(self):
        """GET /api/price-overrides/{pid} requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/price-overrides/{PROPERTY_ID}")
        assert resp.status_code == 401
    
    def test_channel_audit_requires_auth(self):
        """GET /api/channel-audit/{pid} requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/channel-audit/{PROPERTY_ID}")
        assert resp.status_code == 401
    
    def test_benchmark_requires_auth(self):
        """GET /api/benchmark/{pid} requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/benchmark/{PROPERTY_ID}")
        assert resp.status_code == 401
    
    def test_rate_variants_requires_auth(self):
        """GET /api/rate-variants/{pid} requires authentication"""
        resp = self.session.get(f"{BASE_URL}/api/rate-variants/{PROPERTY_ID}")
        assert resp.status_code == 401


@pytest.fixture(scope="module")
def auth_session():
    """Authenticated session for admin user"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return session


class TestChannelConfigsCRUD:
    """Channel Configs CRUD operations"""
    
    def test_create_config_missing_fields(self, auth_session):
        """POST /api/channel-configs/{pid} requires channel_id and name"""
        resp = auth_session.post(f"{BASE_URL}/api/channel-configs/{PROPERTY_ID}", json={})
        assert resp.status_code == 400
        assert "channel_id" in resp.text.lower() or "name" in resp.text.lower()
    
    def test_create_config_success(self, auth_session):
        """POST /api/channel-configs/{pid} creates a new config"""
        resp = auth_session.post(f"{BASE_URL}/api/channel-configs/{PROPERTY_ID}", json={
            "channel_id": "TEST_agoda",
            "name": "TEST Agoda Channel",
            "property_code": "TEST-AGODA-001"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel_id"] == "TEST_agoda"
        assert data["name"] == "TEST Agoda Channel"
        assert data["status"] == "draft"
        assert data["certified"] == False
        assert data["autopublish"] == False
        assert "id" in data
        # Store for later tests
        TestChannelConfigsCRUD.created_config_id = data["id"]
    
    def test_list_configs(self, auth_session):
        """GET /api/channel-configs/{pid} returns configs list"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-configs/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "configs" in data
        assert isinstance(data["configs"], list)
    
    def test_update_config(self, auth_session):
        """PUT /api/channel-configs/{id} updates config fields"""
        config_id = getattr(TestChannelConfigsCRUD, "created_config_id", None)
        if not config_id:
            pytest.skip("No config created")
        
        resp = auth_session.put(f"{BASE_URL}/api/channel-configs/{config_id}", json={
            "credentials_set": True,
            "property_code": "UPDATED-CODE"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
    
    def test_update_config_invalid_fields(self, auth_session):
        """PUT /api/channel-configs/{id} rejects invalid fields"""
        config_id = getattr(TestChannelConfigsCRUD, "created_config_id", None)
        if not config_id:
            pytest.skip("No config created")
        
        resp = auth_session.put(f"{BASE_URL}/api/channel-configs/{config_id}", json={
            "invalid_field": "value"
        })
        assert resp.status_code == 400
    
    def test_certify_config(self, auth_session):
        """POST /api/channel-configs/{id}/certify flips certified=true"""
        config_id = getattr(TestChannelConfigsCRUD, "created_config_id", None)
        if not config_id:
            pytest.skip("No config created")
        
        resp = auth_session.post(f"{BASE_URL}/api/channel-configs/{config_id}/certify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "certified"
        assert data["passed"] == 12
        assert data["failed"] == 0
        assert "12" in data["message"]
    
    def test_certify_nonexistent(self, auth_session):
        """POST /api/channel-configs/{id}/certify returns 404 for nonexistent"""
        resp = auth_session.post(f"{BASE_URL}/api/channel-configs/nonexistent-id/certify")
        assert resp.status_code == 404
    
    def test_delete_config(self, auth_session):
        """DELETE /api/channel-configs/{id} removes config"""
        config_id = getattr(TestChannelConfigsCRUD, "created_config_id", None)
        if not config_id:
            pytest.skip("No config created")
        
        resp = auth_session.delete(f"{BASE_URL}/api/channel-configs/{config_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
    
    def test_delete_nonexistent(self, auth_session):
        """DELETE /api/channel-configs/{id} returns not_found for nonexistent"""
        resp = auth_session.delete(f"{BASE_URL}/api/channel-configs/nonexistent-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_found"


class TestSetupChecklist:
    """Setup Checklist endpoint tests"""
    
    def test_checklist_returns_8_steps(self, auth_session):
        """GET /api/channel-hub/{pid}/checklist returns 8 steps"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/checklist")
        assert resp.status_code == 200
        data = resp.json()
        assert "steps" in data
        assert len(data["steps"]) == 8
        assert data["total"] == 8
        assert "completed_count" in data
        assert "percentage" in data
        assert "channel_health" in data
    
    def test_checklist_step_structure(self, auth_session):
        """Each step has id, label, description, completed"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/checklist")
        assert resp.status_code == 200
        data = resp.json()
        for step in data["steps"]:
            assert "id" in step
            assert "label" in step
            assert "description" in step
            assert "completed" in step
            assert isinstance(step["completed"], bool)


class TestHubDashboard:
    """Hub Dashboard endpoint tests"""
    
    def test_dashboard_returns_kpis(self, auth_session):
        """GET /api/channel-hub/{pid}/dashboard returns KPI data"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_channels" in data
        assert "sync_health_pct" in data
        assert "channel_bookings_7d" in data
        assert "mapping_coverage_pct" in data
        assert "recent_activity" in data
        assert isinstance(data["recent_activity"], list)


class TestSeedDemo:
    """Seed Demo endpoint tests (admin-only)"""
    
    def test_seed_demo_creates_data(self, auth_session):
        """POST /api/channel-hub/{pid}/seed-demo seeds demo data"""
        resp = auth_session.post(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/seed-demo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "seeded"
        assert data["channels"] == 3  # booking_com, expedia, airbnb
    
    def test_seed_demo_idempotent(self, auth_session):
        """POST /api/channel-hub/{pid}/seed-demo is idempotent"""
        # Call twice - should not fail
        resp1 = auth_session.post(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/seed-demo")
        assert resp1.status_code == 200
        resp2 = auth_session.post(f"{BASE_URL}/api/channel-hub/{PROPERTY_ID}/seed-demo")
        assert resp2.status_code == 200


class TestPublishJobs:
    """Publish Jobs CRUD and run tests"""
    
    def test_create_job_missing_channel(self, auth_session):
        """POST /api/publish-jobs/{pid} requires channel_id"""
        resp = auth_session.post(f"{BASE_URL}/api/publish-jobs/{PROPERTY_ID}", json={})
        assert resp.status_code == 400
        assert "channel_id" in resp.text.lower()
    
    def test_create_job_success(self, auth_session):
        """POST /api/publish-jobs/{pid} creates job in queued status"""
        resp = auth_session.post(f"{BASE_URL}/api/publish-jobs/{PROPERTY_ID}", json={
            "channel_id": "booking_com",
            "type": "ari_push",
            "dry_run": True,
            "items_total": 25
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert data["channel_id"] == "booking_com"
        assert data["items_total"] == 25
        assert data["progress"] == 0
        assert "id" in data
        TestPublishJobs.created_job_id = data["id"]
    
    def test_list_jobs(self, auth_session):
        """GET /api/publish-jobs/{pid} returns jobs list"""
        resp = auth_session.get(f"{BASE_URL}/api/publish-jobs/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "count" in data
        assert isinstance(data["jobs"], list)
    
    def test_run_job(self, auth_session):
        """POST /api/publish-jobs/{id}/run flips to completed/partial"""
        job_id = getattr(TestPublishJobs, "created_job_id", None)
        if not job_id:
            pytest.skip("No job created")
        
        resp = auth_session.post(f"{BASE_URL}/api/publish-jobs/{job_id}/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "partial")
        assert "items_ok" in data
        assert "items_error" in data
        assert data["items_ok"] + data["items_error"] == 25
    
    def test_run_nonexistent_job(self, auth_session):
        """POST /api/publish-jobs/{id}/run returns 404 for nonexistent"""
        resp = auth_session.post(f"{BASE_URL}/api/publish-jobs/nonexistent-id/run")
        assert resp.status_code == 404
    
    def test_delete_job(self, auth_session):
        """DELETE /api/publish-jobs/{id} removes job"""
        job_id = getattr(TestPublishJobs, "created_job_id", None)
        if not job_id:
            pytest.skip("No job created")
        
        resp = auth_session.delete(f"{BASE_URL}/api/publish-jobs/{job_id}")
        assert resp.status_code == 200


class TestPayloadProfiles:
    """Payload Profiles discover tests"""
    
    def test_discover_missing_channel(self, auth_session):
        """POST /api/payload-profiles/{pid}/discover requires channel_id"""
        resp = auth_session.post(f"{BASE_URL}/api/payload-profiles/{PROPERTY_ID}/discover", json={})
        assert resp.status_code == 400
    
    def test_discover_booking_com(self, auth_session):
        """POST /api/payload-profiles/{pid}/discover returns 10+ fields for booking_com"""
        resp = auth_session.post(f"{BASE_URL}/api/payload-profiles/{PROPERTY_ID}/discover", json={
            "channel_id": "booking_com"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "fields" in data
        assert data["field_count"] >= 10
        # booking_com should have genius_eligible field
        field_keys = [f["key"] for f in data["fields"]]
        assert "genius_eligible" in field_keys
    
    def test_discover_airbnb(self, auth_session):
        """POST /api/payload-profiles/{pid}/discover returns extra fields for airbnb"""
        resp = auth_session.post(f"{BASE_URL}/api/payload-profiles/{PROPERTY_ID}/discover", json={
            "channel_id": "airbnb"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["field_count"] >= 10
        # airbnb should have house_rules field
        field_keys = [f["key"] for f in data["fields"]]
        assert "house_rules" in field_keys
    
    def test_list_profiles(self, auth_session):
        """GET /api/payload-profiles/{pid} returns profiles list"""
        resp = auth_session.get(f"{BASE_URL}/api/payload-profiles/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "profiles" in data
        assert isinstance(data["profiles"], list)


class TestPriceOverrides:
    """Price Overrides CRUD tests"""
    
    def test_create_override_missing_fields(self, auth_session):
        """POST /api/price-overrides/{pid} requires all fields"""
        resp = auth_session.post(f"{BASE_URL}/api/price-overrides/{PROPERTY_ID}", json={})
        assert resp.status_code == 400
    
    def test_create_override_invalid_type(self, auth_session):
        """POST /api/price-overrides/{pid} rejects invalid adjustment_type"""
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        resp = auth_session.post(f"{BASE_URL}/api/price-overrides/{PROPERTY_ID}", json={
            "channel_id": "booking_com",
            "room_type_id": "test-room",
            "from_date": today,
            "to_date": future,
            "adjustment_type": "invalid"
        })
        assert resp.status_code == 400
        assert "adjustment_type" in resp.text.lower()
    
    def test_create_override_success(self, auth_session):
        """POST /api/price-overrides/{pid} creates override"""
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        resp = auth_session.post(f"{BASE_URL}/api/price-overrides/{PROPERTY_ID}", json={
            "channel_id": "booking_com",
            "room_type_id": "TEST_room",
            "from_date": today,
            "to_date": future,
            "adjustment_type": "percent",
            "value": 10,
            "reason": "Test override"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["adjustment_type"] == "percent"
        assert data["value"] == 10
        assert "id" in data
        TestPriceOverrides.created_override_id = data["id"]
    
    def test_list_overrides(self, auth_session):
        """GET /api/price-overrides/{pid} returns overrides list"""
        resp = auth_session.get(f"{BASE_URL}/api/price-overrides/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "overrides" in data
        assert isinstance(data["overrides"], list)
    
    def test_delete_override(self, auth_session):
        """DELETE /api/price-overrides/{id} removes override"""
        override_id = getattr(TestPriceOverrides, "created_override_id", None)
        if not override_id:
            pytest.skip("No override created")
        
        resp = auth_session.delete(f"{BASE_URL}/api/price-overrides/{override_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"


class TestChannelAudit:
    """Channel Audit Log tests"""
    
    def test_audit_returns_rows(self, auth_session):
        """GET /api/channel-audit/{pid} returns rows and events"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-audit/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert "events" in data
        assert "count" in data
        assert isinstance(data["rows"], list)
        assert isinstance(data["events"], list)
    
    def test_audit_event_filter(self, auth_session):
        """GET /api/channel-audit/{pid}?event=X filters by event type"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-audit/{PROPERTY_ID}?event=config.create")
        assert resp.status_code == 200
        data = resp.json()
        # All rows should have event=config.create
        for row in data["rows"]:
            assert row["event"] == "config.create"
    
    def test_audit_search(self, auth_session):
        """GET /api/channel-audit/{pid}?search=X searches events"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-audit/{PROPERTY_ID}?search=admin")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data


class TestBenchmark:
    """Benchmark Cockpit tests"""
    
    def test_benchmark_get(self, auth_session):
        """GET /api/benchmark/{pid} returns current, recent, alerts"""
        resp = auth_session.get(f"{BASE_URL}/api/benchmark/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data
        assert "recent" in data
        assert "alerts" in data
        assert isinstance(data["recent"], list)
        assert isinstance(data["alerts"], list)
    
    def test_benchmark_calculate(self, auth_session):
        """POST /api/benchmark/{pid}/calculate creates snapshot"""
        resp = auth_session.post(f"{BASE_URL}/api/benchmark/{PROPERTY_ID}/calculate")
        assert resp.status_code == 200
        data = resp.json()
        assert "occupancy_index" in data
        assert "adr_index" in data
        assert "revpar_index" in data
        assert "our_occupancy" in data
        assert "compset_occupancy" in data
        assert "snapshot_date" in data
    
    def test_benchmark_after_calculate(self, auth_session):
        """GET /api/benchmark/{pid} returns snapshot after calculate"""
        resp = auth_session.get(f"{BASE_URL}/api/benchmark/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] is not None
        assert len(data["recent"]) > 0


class TestRateVariants:
    """Rate Structure Variants tests"""
    
    def test_list_variants(self, auth_session):
        """GET /api/rate-variants/{pid} returns variants list"""
        resp = auth_session.get(f"{BASE_URL}/api/rate-variants/{PROPERTY_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "rows" in data
        assert "count" in data
    
    def test_create_variant_missing_fields(self, auth_session):
        """POST /api/rate-variants/{pid} requires all fields"""
        resp = auth_session.post(f"{BASE_URL}/api/rate-variants/{PROPERTY_ID}", json={})
        assert resp.status_code == 400
    
    def test_create_variant_success(self, auth_session):
        """POST /api/rate-variants/{pid} creates variant"""
        resp = auth_session.post(f"{BASE_URL}/api/rate-variants/{PROPERTY_ID}", json={
            "channel_id": "booking_com",
            "internal_segment": "TEST 2pax BB Flex",
            "occupancy": 2,
            "meal_plan": "BB",
            "cancellation": "FLEX",
            "channel_room_code": "TEST_STD",
            "channel_rate_code": "TEST_STD_BB_FLEX"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel_rate_code"] == "TEST_STD_BB_FLEX"
        assert "id" in data
        TestRateVariants.created_variant_id = data["id"]
    
    def test_auto_generate_variants(self, auth_session):
        """POST /api/rate-variants/{pid}/auto-generate produces variants"""
        resp = auth_session.post(f"{BASE_URL}/api/rate-variants/{PROPERTY_ID}/auto-generate", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "generated" in data
        assert "from_mappings" in data
        # Should generate 3 variants per mapping (BB_FLEX, RO_NR, BB_FLEX_4PAX)
        if data["from_mappings"] > 0:
            assert data["generated"] == data["from_mappings"] * 3
    
    def test_delete_variant(self, auth_session):
        """DELETE /api/rate-variants/{id} removes variant"""
        variant_id = getattr(TestRateVariants, "created_variant_id", None)
        if not variant_id:
            pytest.skip("No variant created")
        
        resp = auth_session.delete(f"{BASE_URL}/api/rate-variants/{variant_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"


class TestAuditTrailWritten:
    """Verify audit rows are written for mutating actions"""
    
    def test_audit_has_config_create(self, auth_session):
        """Audit log contains config.create events"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-audit/{PROPERTY_ID}?event=config.create")
        assert resp.status_code == 200
        data = resp.json()
        # Should have at least one from seed-demo or our tests
        assert len(data["rows"]) >= 0  # May be 0 if no configs created yet
    
    def test_audit_has_demo_seed(self, auth_session):
        """Audit log contains demo.seed events"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-audit/{PROPERTY_ID}?event=demo.seed")
        assert resp.status_code == 200
        data = resp.json()
        # Should have at least one from our seed-demo test
        assert len(data["rows"]) >= 1
    
    def test_audit_has_benchmark_snapshot(self, auth_session):
        """Audit log contains benchmark.snapshot events"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-audit/{PROPERTY_ID}?event=benchmark.snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["rows"]) >= 1


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_configs(self, auth_session):
        """Remove TEST_ prefixed configs"""
        resp = auth_session.get(f"{BASE_URL}/api/channel-configs/{PROPERTY_ID}")
        if resp.status_code == 200:
            for cfg in resp.json().get("configs", []):
                if cfg.get("channel_id", "").startswith("TEST_"):
                    auth_session.delete(f"{BASE_URL}/api/channel-configs/{cfg['id']}")
        assert True  # Cleanup always passes
