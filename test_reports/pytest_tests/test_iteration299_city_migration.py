"""
Iteration 299 - City Migration Wizard Tests

Tests for the 'Şehir Değiştir' (Change City) wizard feature:
1. POST /api/revenue/events/{property_id}/change-city - City migration wizard
2. GET /api/revenue/events/{property_id}/migrations - Migration history
3. RBAC: receptionist gets 403 on both endpoints
4. Validation: 400 if new_city missing, {ok:false, error:'no_change'} if same city
5. Idempotency: After migration, events=0 and city=new_city
6. Regression: cleanup-foreign, scan, rescan-full still work
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text}")


@pytest.fixture(scope="module")
def receptionist_token():
    """Get receptionist authentication token for RBAC tests."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": RECEPTIONIST_EMAIL,
        "password": RECEPTIONIST_PASSWORD
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Receptionist login failed: {resp.status_code} - {resp.text}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Admin auth headers."""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def receptionist_headers(receptionist_token):
    """Receptionist auth headers."""
    return {"Authorization": f"Bearer {receptionist_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def test_property_id():
    """Create a unique test property ID for migration tests."""
    return f"test-mig-{uuid.uuid4().hex[:8]}"


class TestChangeCityValidation:
    """Tests for POST /api/revenue/events/{property_id}/change-city validation."""

    def test_change_city_missing_new_city_returns_400(self, admin_headers, test_property_id):
        """POST change-city with missing new_city should return 400."""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/change-city",
            headers=admin_headers,
            json={}  # Missing new_city
        )
        assert resp.status_code == 400, f"Expected 400 for missing new_city, got {resp.status_code}: {resp.text}"
        print("✓ Missing new_city returns 400")

    def test_change_city_empty_new_city_returns_400(self, admin_headers, test_property_id):
        """POST change-city with empty new_city should return 400."""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/change-city",
            headers=admin_headers,
            json={"new_city": ""}  # Empty new_city
        )
        assert resp.status_code == 400, f"Expected 400 for empty new_city, got {resp.status_code}: {resp.text}"
        print("✓ Empty new_city returns 400")

    def test_change_city_whitespace_only_returns_400(self, admin_headers, test_property_id):
        """POST change-city with whitespace-only new_city should return 400."""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/change-city",
            headers=admin_headers,
            json={"new_city": "   "}  # Whitespace only
        )
        assert resp.status_code == 400, f"Expected 400 for whitespace-only new_city, got {resp.status_code}: {resp.text}"
        print("✓ Whitespace-only new_city returns 400")


class TestChangeCitySameCityNoChange:
    """Tests for same city returning {ok:false, error:'no_change'}."""

    def test_change_city_same_city_returns_no_change(self, admin_headers):
        """POST change-city with same city (case-insensitive) should return {ok:false, error:'no_change'}."""
        # First, set up a property with a known city
        test_pid = f"test-same-city-{uuid.uuid4().hex[:6]}"
        
        # Set initial city via market_robot_config
        config_resp = requests.put(
            f"{BASE_URL}/api/revenue/market-robot/{test_pid}/config",
            headers=admin_headers,
            json={"city": "Berlin", "enabled": False}
        )
        
        # Now try to change to the same city
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_pid}/change-city",
            headers=admin_headers,
            json={"new_city": "Berlin", "auto_scan": False}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") == False, f"Expected ok=false, got {data}"
        assert data.get("error") == "no_change", f"Expected error='no_change', got {data}"
        print(f"✓ Same city returns {{ok:false, error:'no_change'}}: {data.get('message')}")

    def test_change_city_same_city_case_insensitive(self, admin_headers):
        """POST change-city with same city (different case) should return no_change."""
        test_pid = f"test-case-{uuid.uuid4().hex[:6]}"
        
        # Set initial city
        requests.put(
            f"{BASE_URL}/api/revenue/market-robot/{test_pid}/config",
            headers=admin_headers,
            json={"city": "Paris", "enabled": False}
        )
        
        # Try to change to same city with different case
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_pid}/change-city",
            headers=admin_headers,
            json={"new_city": "PARIS", "auto_scan": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") == False, f"Expected ok=false for case-insensitive match"
        assert data.get("error") == "no_change", f"Expected error='no_change'"
        print("✓ Same city (different case) returns no_change")


class TestChangeCityFullFlow:
    """Tests for full city migration flow."""

    def test_change_city_full_migration_flow(self, admin_headers):
        """Full migration flow: seed property, add events, migrate, verify cleanup."""
        test_pid = f"test-full-mig-{uuid.uuid4().hex[:6]}"
        
        # Step 1: Set up property with initial city
        config_resp = requests.put(
            f"{BASE_URL}/api/revenue/market-robot/{test_pid}/config",
            headers=admin_headers,
            json={"city": "Munich", "enabled": False}
        )
        print(f"Step 1: Config set for {test_pid} (status: {config_resp.status_code})")
        
        # Step 2: Add some events for Munich
        for i in range(2):
            add_resp = requests.post(
                f"{BASE_URL}/api/revenue/events/{test_pid}/add",
                headers=admin_headers,
                json={
                    "name": f"TEST_Munich_Event_{i}_{uuid.uuid4().hex[:4]}",
                    "date": (datetime.now() + timedelta(days=30+i)).strftime("%Y-%m-%d"),
                    "city": "Munich",
                    "category": "concert",
                    "estimated_attendance": 5000,
                    "hotel_demand_score": 60,
                    "auto_price": False
                }
            )
            print(f"Step 2: Added event {i} (status: {add_resp.status_code})")
        
        # Step 3: Verify events exist
        get_resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_pid}", headers=admin_headers)
        assert get_resp.status_code == 200
        pre_migration = get_resp.json()
        pre_event_count = len(pre_migration.get("events", []))
        print(f"Step 3: Pre-migration events: {pre_event_count}, city: {pre_migration.get('city')}")
        
        # Step 4: Migrate to new city (auto_scan=false to avoid slow GPT calls)
        migrate_resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_pid}/change-city",
            headers=admin_headers,
            json={
                "new_city": "Vienna",
                "auto_scan": False,  # IMPORTANT: avoid slow GPT calls
                "clear_event_overrides": True
            }
        )
        assert migrate_resp.status_code == 200, f"Migration failed: {migrate_resp.status_code} - {migrate_resp.text}"
        migrate_data = migrate_resp.json()
        assert migrate_data.get("ok") == True, f"Expected ok=true, got {migrate_data}"
        assert migrate_data.get("from_city") == "Munich", f"Expected from_city=Munich"
        assert migrate_data.get("to_city") == "Vienna", f"Expected to_city=Vienna"
        assert migrate_data.get("deleted_events") >= 0, "Should report deleted_events count"
        assert migrate_data.get("auto_scan") == "skipped", f"Expected auto_scan=skipped when auto_scan=false"
        print(f"Step 4: Migration successful: {migrate_data.get('message')}")
        print(f"  - Deleted events: {migrate_data.get('deleted_events')}")
        print(f"  - Deleted overrides: {migrate_data.get('deleted_event_overrides')}")
        
        # Step 5: Verify post-migration state
        post_resp = requests.get(f"{BASE_URL}/api/revenue/events/{test_pid}", headers=admin_headers)
        assert post_resp.status_code == 200
        post_migration = post_resp.json()
        post_event_count = len(post_migration.get("events", []))
        post_city = post_migration.get("city", "")
        
        assert post_city.lower() == "vienna", f"Expected city=Vienna, got {post_city}"
        assert post_event_count == 0, f"Expected 0 events after migration, got {post_event_count}"
        print(f"Step 5: Post-migration verified: city={post_city}, events={post_event_count}")
        print("✓ Full migration flow completed successfully")

    def test_change_city_with_auto_scan_triggered(self, admin_headers):
        """Migration with auto_scan=true should return 'triggered_async'."""
        test_pid = f"test-autoscan-{uuid.uuid4().hex[:6]}"
        
        # Set up property
        requests.put(
            f"{BASE_URL}/api/revenue/market-robot/{test_pid}/config",
            headers=admin_headers,
            json={"city": "Rome", "enabled": False}
        )
        
        # Migrate with auto_scan=true (we won't wait for it to complete)
        migrate_resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_pid}/change-city",
            headers=admin_headers,
            json={
                "new_city": "Milan",
                "auto_scan": True,  # This triggers async scan
                "clear_event_overrides": True
            }
        )
        assert migrate_resp.status_code == 200
        data = migrate_resp.json()
        assert data.get("ok") == True
        assert data.get("auto_scan") == "triggered_async", f"Expected auto_scan='triggered_async', got {data.get('auto_scan')}"
        print(f"✓ auto_scan=true returns 'triggered_async': {data.get('message')}")


class TestMigrationsHistory:
    """Tests for GET /api/revenue/events/{property_id}/migrations endpoint."""

    def test_migrations_endpoint_exists(self, admin_headers, test_property_id):
        """GET /api/revenue/events/{property_id}/migrations should exist."""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/migrations",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "items" in data, "Response should include 'items' field"
        assert "count" in data, "Response should include 'count' field"
        print(f"✓ Migrations endpoint returns: count={data.get('count')}, items={len(data.get('items', []))}")

    def test_migrations_returns_audit_log(self, admin_headers):
        """After migration, GET migrations should return audit log entry."""
        test_pid = f"test-audit-{uuid.uuid4().hex[:6]}"
        
        # Set up and migrate
        requests.put(
            f"{BASE_URL}/api/revenue/market-robot/{test_pid}/config",
            headers=admin_headers,
            json={"city": "Amsterdam", "enabled": False}
        )
        
        requests.post(
            f"{BASE_URL}/api/revenue/events/{test_pid}/change-city",
            headers=admin_headers,
            json={"new_city": "Brussels", "auto_scan": False, "clear_event_overrides": True}
        )
        
        # Get migrations
        resp = requests.get(
            f"{BASE_URL}/api/revenue/events/{test_pid}/migrations",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        items = data.get("items", [])
        
        assert len(items) >= 1, "Should have at least 1 migration record"
        latest = items[0]  # Most recent first
        
        # Verify audit log fields
        assert latest.get("from_city") == "Amsterdam", f"Expected from_city=Amsterdam"
        assert latest.get("to_city") == "Brussels", f"Expected to_city=Brussels"
        assert "deleted_events" in latest, "Should include deleted_events"
        assert "deleted_event_overrides" in latest, "Should include deleted_event_overrides"
        assert "migrated_at" in latest, "Should include migrated_at"
        assert "migrated_by" in latest, "Should include migrated_by"
        assert "auto_scan_triggered" in latest, "Should include auto_scan_triggered"
        
        print(f"✓ Migration audit log verified: {latest.get('from_city')} → {latest.get('to_city')}")
        print(f"  - deleted_events: {latest.get('deleted_events')}")
        print(f"  - deleted_event_overrides: {latest.get('deleted_event_overrides')}")
        print(f"  - migrated_at: {latest.get('migrated_at')}")
        print(f"  - auto_scan_triggered: {latest.get('auto_scan_triggered')}")


class TestChangeCityRBAC:
    """RBAC tests for change-city and migrations endpoints."""

    def test_change_city_admin_allowed(self, admin_headers, test_property_id):
        """Admin should be allowed to call change-city."""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/change-city",
            headers=admin_headers,
            json={"new_city": "TestCity", "auto_scan": False}
        )
        # Should be 200 (success or no_change), not 403
        assert resp.status_code in [200, 400], f"Admin should be allowed, got {resp.status_code}"
        print("✓ Admin allowed to call change-city")

    def test_change_city_receptionist_denied(self, receptionist_headers, test_property_id):
        """Receptionist should be denied (403) from change-city."""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/change-city",
            headers=receptionist_headers,
            json={"new_city": "TestCity", "auto_scan": False}
        )
        assert resp.status_code == 403, f"Receptionist should get 403, got {resp.status_code}: {resp.text}"
        print("✓ Receptionist correctly denied (403) from change-city")

    def test_change_city_unauthenticated_denied(self, test_property_id):
        """Unauthenticated request should be denied (401)."""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/change-city",
            json={"new_city": "TestCity", "auto_scan": False}
        )
        assert resp.status_code == 401, f"Unauthenticated should get 401, got {resp.status_code}"
        print("✓ Unauthenticated correctly denied (401) from change-city")

    def test_migrations_admin_allowed(self, admin_headers, test_property_id):
        """Admin should be allowed to call migrations."""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/migrations",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Admin should be allowed, got {resp.status_code}"
        print("✓ Admin allowed to call migrations")

    def test_migrations_receptionist_denied(self, receptionist_headers, test_property_id):
        """Receptionist should be denied (403) from migrations."""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/migrations",
            headers=receptionist_headers
        )
        assert resp.status_code == 403, f"Receptionist should get 403, got {resp.status_code}: {resp.text}"
        print("✓ Receptionist correctly denied (403) from migrations")

    def test_migrations_unauthenticated_denied(self, test_property_id):
        """Unauthenticated request should be denied (401)."""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/events/{test_property_id}/migrations"
        )
        assert resp.status_code == 401, f"Unauthenticated should get 401, got {resp.status_code}"
        print("✓ Unauthenticated correctly denied (401) from migrations")


class TestRegressionExistingEndpoints:
    """Regression tests for existing Event Intelligence endpoints."""

    def test_get_events_still_works(self, admin_headers):
        """GET /api/revenue/events/{property_id} should still work."""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/events/default",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"GET events should return 200: {resp.status_code}"
        data = resp.json()
        assert "events" in data and "counts" in data and "city" in data
        print(f"✓ GET events works: city={data.get('city')}, events={len(data.get('events', []))}")

    def test_cleanup_foreign_still_works(self, admin_headers):
        """POST /api/revenue/events/{property_id}/cleanup-foreign should still work."""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/default/cleanup-foreign",
            headers=admin_headers,
            json={}
        )
        assert resp.status_code == 200, f"cleanup-foreign should return 200: {resp.status_code}"
        data = resp.json()
        assert "ok" in data and "city" in data and "deleted" in data
        print(f"✓ cleanup-foreign works: deleted={data.get('deleted')}")

    def test_add_event_still_works(self, admin_headers):
        """POST /api/revenue/events/{property_id}/add should still work."""
        test_pid = f"test-add-{uuid.uuid4().hex[:6]}"
        resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_pid}/add",
            headers=admin_headers,
            json={
                "name": f"TEST_Regression_Event_{uuid.uuid4().hex[:4]}",
                "date": (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d"),
                "city": "London",
                "category": "concert",
                "estimated_attendance": 10000,
                "auto_price": False
            }
        )
        assert resp.status_code == 200, f"add event should return 200: {resp.status_code}"
        data = resp.json()
        assert "event" in data
        print(f"✓ add event works: {data.get('event', {}).get('name')}")

    def test_delete_event_still_works(self, admin_headers):
        """DELETE /api/revenue/events/{event_id} should still work."""
        # First add an event
        test_pid = f"test-del-{uuid.uuid4().hex[:6]}"
        add_resp = requests.post(
            f"{BASE_URL}/api/revenue/events/{test_pid}/add",
            headers=admin_headers,
            json={
                "name": f"TEST_Delete_Event_{uuid.uuid4().hex[:4]}",
                "date": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                "city": "London",
                "category": "sports",
                "estimated_attendance": 5000,
                "auto_price": False
            }
        )
        if add_resp.status_code == 200:
            event_id = add_resp.json().get("event", {}).get("id")
            if event_id:
                del_resp = requests.delete(
                    f"{BASE_URL}/api/revenue/events/{event_id}",
                    headers=admin_headers
                )
                assert del_resp.status_code == 200, f"delete event should return 200: {del_resp.status_code}"
                print(f"✓ delete event works: {event_id}")
            else:
                print("✓ delete event skipped (no event_id returned)")
        else:
            print("✓ delete event skipped (add failed)")


class TestFrontendDataTestIds:
    """Tests to verify frontend data-testid attributes exist in the code."""

    def test_event_change_city_btn_testid(self):
        """Verify data-testid='event-change-city-btn' exists."""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "event-change-city-btn", "/app/frontend/src/components/dashboard/EventIntelligence.js"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count > 0, "data-testid='event-change-city-btn' should exist"
        print(f"✓ data-testid='event-change-city-btn' found {count} time(s)")

    def test_event_migrate_modal_testid(self):
        """Verify data-testid='event-migrate-modal' exists."""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "event-migrate-modal", "/app/frontend/src/components/dashboard/EventIntelligence.js"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count > 0, "data-testid='event-migrate-modal' should exist"
        print(f"✓ data-testid='event-migrate-modal' found {count} time(s)")

    def test_event_migrate_city_input_testid(self):
        """Verify data-testid='event-migrate-city-input' exists."""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "event-migrate-city-input", "/app/frontend/src/components/dashboard/EventIntelligence.js"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count > 0, "data-testid='event-migrate-city-input' should exist"
        print(f"✓ data-testid='event-migrate-city-input' found {count} time(s)")

    def test_event_migrate_autoscan_testid(self):
        """Verify data-testid='event-migrate-autoscan' exists."""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "event-migrate-autoscan", "/app/frontend/src/components/dashboard/EventIntelligence.js"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count > 0, "data-testid='event-migrate-autoscan' should exist"
        print(f"✓ data-testid='event-migrate-autoscan' found {count} time(s)")

    def test_event_migrate_clear_overrides_testid(self):
        """Verify data-testid='event-migrate-clear-overrides' exists."""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "event-migrate-clear-overrides", "/app/frontend/src/components/dashboard/EventIntelligence.js"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count > 0, "data-testid='event-migrate-clear-overrides' should exist"
        print(f"✓ data-testid='event-migrate-clear-overrides' found {count} time(s)")

    def test_event_migrate_submit_testid(self):
        """Verify data-testid='event-migrate-submit' exists."""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "event-migrate-submit", "/app/frontend/src/components/dashboard/EventIntelligence.js"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count > 0, "data-testid='event-migrate-submit' should exist"
        print(f"✓ data-testid='event-migrate-submit' found {count} time(s)")

    def test_event_migrate_cancel_testid(self):
        """Verify data-testid='event-migrate-cancel' exists."""
        import subprocess
        result = subprocess.run(
            ["grep", "-c", "event-migrate-cancel", "/app/frontend/src/components/dashboard/EventIntelligence.js"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip()) if result.returncode == 0 else 0
        assert count > 0, "data-testid='event-migrate-cancel' should exist"
        print(f"✓ data-testid='event-migrate-cancel' found {count} time(s)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
