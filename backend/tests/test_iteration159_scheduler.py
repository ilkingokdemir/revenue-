"""
Iteration 159 - Scheduler API Tests
Tests for the lightweight asyncio-based scheduler that enables nightly auto-capture of deposits.

Endpoints tested:
- GET /api/scheduler/config - List scheduler configs
- PUT /api/scheduler/config/{pid}/{job} - Upsert scheduler config
- GET /api/scheduler/history - Get scheduler run history
- POST /api/scheduler/trigger/{pid}/{job} - Manual trigger a job
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_PROPERTY_ID = "aldgate-flats"
TEST_JOB = "auto_deposit_capture"

class TestSchedulerAuth:
    """Test authentication requirements for scheduler endpoints"""
    
    def test_get_config_requires_auth(self):
        """GET /api/scheduler/config requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scheduler/config")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/scheduler/config requires auth")
    
    def test_put_config_requires_auth(self):
        """PUT /api/scheduler/config/{pid}/{job} requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/scheduler/config/{TEST_PROPERTY_ID}/{TEST_JOB}",
            json={"enabled": True, "cron_hour": 2, "cron_minute": 0}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: PUT /api/scheduler/config requires auth")
    
    def test_get_history_requires_auth(self):
        """GET /api/scheduler/history requires authentication"""
        response = requests.get(f"{BASE_URL}/api/scheduler/history")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/scheduler/history requires auth")
    
    def test_trigger_requires_auth(self):
        """POST /api/scheduler/trigger/{pid}/{job} requires authentication"""
        response = requests.post(f"{BASE_URL}/api/scheduler/trigger/{TEST_PROPERTY_ID}/{TEST_JOB}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/scheduler/trigger requires auth")


class TestSchedulerConfig:
    """Test scheduler config CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.cookies = login_response.cookies
        self.headers = {"Cookie": "; ".join([f"{c.name}={c.value}" for c in self.cookies])}
    
    def test_get_config_returns_list(self):
        """GET /api/scheduler/config returns list of configs"""
        response = requests.get(f"{BASE_URL}/api/scheduler/config", cookies=self.cookies)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: GET /api/scheduler/config returns list ({len(data)} configs)")
    
    def test_get_config_with_property_filter(self):
        """GET /api/scheduler/config?property_id= filters by property"""
        response = requests.get(
            f"{BASE_URL}/api/scheduler/config?property_id={TEST_PROPERTY_ID}",
            cookies=self.cookies
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # All returned configs should match the property_id
        for cfg in data:
            assert cfg.get("property_id") == TEST_PROPERTY_ID, f"Config property_id mismatch: {cfg}"
        print(f"PASS: GET /api/scheduler/config?property_id= filters correctly ({len(data)} configs)")
    
    def test_put_config_creates_new(self):
        """PUT /api/scheduler/config/{pid}/{job} creates new config"""
        payload = {
            "enabled": True,
            "cron_hour": 3,
            "cron_minute": 30,
            "notes": "Test nightly run"
        }
        response = requests.put(
            f"{BASE_URL}/api/scheduler/config/{TEST_PROPERTY_ID}/{TEST_JOB}",
            json=payload,
            cookies=self.cookies
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify returned config matches input
        assert data.get("property_id") == TEST_PROPERTY_ID
        assert data.get("job") == TEST_JOB
        assert data.get("enabled") == True
        assert data.get("cron_hour") == 3
        assert data.get("cron_minute") == 30
        assert data.get("notes") == "Test nightly run"
        assert "updated_at" in data
        print("PASS: PUT /api/scheduler/config creates/updates config correctly")
    
    def test_put_config_updates_existing(self):
        """PUT /api/scheduler/config/{pid}/{job} updates existing config"""
        # First create
        requests.put(
            f"{BASE_URL}/api/scheduler/config/{TEST_PROPERTY_ID}/{TEST_JOB}",
            json={"enabled": True, "cron_hour": 2, "cron_minute": 0},
            cookies=self.cookies
        )
        
        # Then update
        payload = {
            "enabled": False,
            "cron_hour": 4,
            "cron_minute": 15,
            "notes": "Updated schedule"
        }
        response = requests.put(
            f"{BASE_URL}/api/scheduler/config/{TEST_PROPERTY_ID}/{TEST_JOB}",
            json=payload,
            cookies=self.cookies
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("enabled") == False
        assert data.get("cron_hour") == 4
        assert data.get("cron_minute") == 15
        assert data.get("notes") == "Updated schedule"
        print("PASS: PUT /api/scheduler/config updates existing config")
    
    def test_put_config_invalid_cron_hour(self):
        """PUT with invalid cron_hour (e.g. 25) returns 400"""
        payload = {
            "enabled": True,
            "cron_hour": 25,  # Invalid - must be 0-23
            "cron_minute": 0
        }
        response = requests.put(
            f"{BASE_URL}/api/scheduler/config/{TEST_PROPERTY_ID}/{TEST_JOB}",
            json=payload,
            cookies=self.cookies
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: PUT with invalid cron_hour=25 returns 400")
    
    def test_put_config_invalid_cron_minute(self):
        """PUT with invalid cron_minute (e.g. 60) returns 400"""
        payload = {
            "enabled": True,
            "cron_hour": 2,
            "cron_minute": 60  # Invalid - must be 0-59
        }
        response = requests.put(
            f"{BASE_URL}/api/scheduler/config/{TEST_PROPERTY_ID}/{TEST_JOB}",
            json=payload,
            cookies=self.cookies
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: PUT with invalid cron_minute=60 returns 400")
    
    def test_put_config_unknown_job(self):
        """PUT with unknown job (not in JOB_HANDLERS) returns 400"""
        payload = {
            "enabled": True,
            "cron_hour": 2,
            "cron_minute": 0
        }
        response = requests.put(
            f"{BASE_URL}/api/scheduler/config/{TEST_PROPERTY_ID}/unknown_job_xyz",
            json=payload,
            cookies=self.cookies
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Unknown job" in data.get("detail", ""), f"Expected 'Unknown job' in error: {data}"
        print("PASS: PUT with unknown job returns 400")


class TestSchedulerHistory:
    """Test scheduler history endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        self.cookies = login_response.cookies
    
    def test_get_history_returns_list(self):
        """GET /api/scheduler/history returns list sorted by ran_at desc"""
        response = requests.get(f"{BASE_URL}/api/scheduler/history", cookies=self.cookies)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Verify sorted descending by ran_at
        if len(data) >= 2:
            for i in range(len(data) - 1):
                assert data[i].get("ran_at", "") >= data[i+1].get("ran_at", ""), "History not sorted desc by ran_at"
        print(f"PASS: GET /api/scheduler/history returns sorted list ({len(data)} entries)")
    
    def test_get_history_with_property_filter(self):
        """GET /api/scheduler/history?property_id= filters by property"""
        response = requests.get(
            f"{BASE_URL}/api/scheduler/history?property_id={TEST_PROPERTY_ID}",
            cookies=self.cookies
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # All returned entries should match the property_id
        for entry in data:
            assert entry.get("property_id") == TEST_PROPERTY_ID, f"History entry property_id mismatch: {entry}"
        print(f"PASS: GET /api/scheduler/history?property_id= filters correctly ({len(data)} entries)")
    
    def test_get_history_limit_parameter(self):
        """GET /api/scheduler/history?limit= respects limit"""
        response = requests.get(
            f"{BASE_URL}/api/scheduler/history?limit=5",
            cookies=self.cookies
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5, f"Expected max 5 entries, got {len(data)}"
        print(f"PASS: GET /api/scheduler/history?limit=5 returns max 5 entries ({len(data)} returned)")


class TestSchedulerTrigger:
    """Test manual job trigger endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        self.cookies = login_response.cookies
    
    def test_trigger_unknown_job_returns_400(self):
        """POST /api/scheduler/trigger/{pid}/{job} with bad job returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/scheduler/trigger/{TEST_PROPERTY_ID}/nonexistent_job",
            cookies=self.cookies
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Unknown job" in data.get("detail", ""), f"Expected 'Unknown job' in error: {data}"
        print("PASS: POST /api/scheduler/trigger with unknown job returns 400")
    
    def test_trigger_auto_deposit_capture(self):
        """POST /api/scheduler/trigger/{pid}/auto_deposit_capture runs job and records history"""
        # Get history count before
        history_before = requests.get(
            f"{BASE_URL}/api/scheduler/history?property_id={TEST_PROPERTY_ID}",
            cookies=self.cookies
        ).json()
        count_before = len(history_before)
        
        # Trigger the job
        response = requests.post(
            f"{BASE_URL}/api/scheduler/trigger/{TEST_PROPERTY_ID}/{TEST_JOB}",
            cookies=self.cookies
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data.get("status") == "triggered", f"Expected status='triggered', got {data}"
        assert "result" in data, "Response should contain 'result'"
        result = data["result"]
        assert "ran" in result, "Result should contain 'ran'"
        assert "charged" in result, "Result should contain 'charged'"
        assert "failed" in result, "Result should contain 'failed'"
        assert "skipped" in result, "Result should contain 'skipped'"
        print(f"PASS: POST /api/scheduler/trigger runs job - ran:{result['ran']}, charged:{result['charged']}, skipped:{result['skipped']}, failed:{result['failed']}")
        
        # Verify history was recorded
        time.sleep(0.5)  # Small delay for DB write
        history_after = requests.get(
            f"{BASE_URL}/api/scheduler/history?property_id={TEST_PROPERTY_ID}",
            cookies=self.cookies
        ).json()
        
        assert len(history_after) > count_before, "History should have new entry after trigger"
        
        # Check the latest entry
        latest = history_after[0]
        assert latest.get("trigger") == "manual", f"Expected trigger='manual', got {latest.get('trigger')}"
        assert latest.get("job") == TEST_JOB, f"Expected job='{TEST_JOB}', got {latest.get('job')}"
        assert latest.get("property_id") == TEST_PROPERTY_ID
        print("PASS: Manual trigger recorded to scheduler_history with trigger='manual'")


class TestSchedulerIntegration:
    """Integration tests for scheduler with deposit automation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        self.cookies = login_response.cookies
    
    def test_full_workflow_config_trigger_history(self):
        """Full workflow: configure schedule → trigger → verify history"""
        # 1. Configure schedule
        config_payload = {
            "enabled": True,
            "cron_hour": 2,
            "cron_minute": 30,
            "notes": "Integration test schedule"
        }
        config_response = requests.put(
            f"{BASE_URL}/api/scheduler/config/{TEST_PROPERTY_ID}/{TEST_JOB}",
            json=config_payload,
            cookies=self.cookies
        )
        assert config_response.status_code == 200
        print("Step 1: Config saved successfully")
        
        # 2. Verify config is retrievable
        configs = requests.get(
            f"{BASE_URL}/api/scheduler/config?property_id={TEST_PROPERTY_ID}",
            cookies=self.cookies
        ).json()
        my_config = next((c for c in configs if c.get("job") == TEST_JOB), None)
        assert my_config is not None, "Config should be retrievable"
        assert my_config.get("enabled") == True
        assert my_config.get("cron_hour") == 2
        assert my_config.get("cron_minute") == 30
        print("Step 2: Config verified in list")
        
        # 3. Trigger job manually
        trigger_response = requests.post(
            f"{BASE_URL}/api/scheduler/trigger/{TEST_PROPERTY_ID}/{TEST_JOB}",
            cookies=self.cookies
        )
        assert trigger_response.status_code == 200
        result = trigger_response.json().get("result", {})
        print(f"Step 3: Job triggered - ran:{result.get('ran')}, skipped:{result.get('skipped')}")
        
        # 4. Verify history entry
        time.sleep(0.5)
        history = requests.get(
            f"{BASE_URL}/api/scheduler/history?property_id={TEST_PROPERTY_ID}&limit=1",
            cookies=self.cookies
        ).json()
        assert len(history) > 0, "History should have entries"
        latest = history[0]
        assert latest.get("trigger") == "manual"
        assert latest.get("job") == TEST_JOB
        assert "result" in latest
        print("Step 4: History entry verified")
        
        print("PASS: Full workflow integration test completed")


class TestSchedulerRoleAccess:
    """Test that only admin/manager can access scheduler endpoints"""
    
    def test_receptionist_cannot_access_config(self):
        """Receptionist role should not access scheduler config"""
        # Login as receptionist
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testrecep@hotelbox.com",
            "password": "Test2026!"
        })
        if login_response.status_code != 200:
            pytest.skip("Receptionist test user not available")
        
        cookies = login_response.cookies
        response = requests.get(f"{BASE_URL}/api/scheduler/config", cookies=cookies)
        # Should be 403 Forbidden for non-admin/manager
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Receptionist cannot access scheduler config")
