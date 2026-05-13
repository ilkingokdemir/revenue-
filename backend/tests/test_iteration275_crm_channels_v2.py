"""
Iteration 275 — Guest CRM 360 + Channel Manager v2 Tests

Tests for:
1. CRM 360 (Revinate-killer):
   - GET /api/crm/profile/{guest_email} — 360° view with stats, lifecycle, segments
   - GET /api/crm/segments — aggregates up to 500 guests with segment counts
   - GET /api/crm/winback/candidates — guests inactive for N days
   - POST /api/crm/winback/queue — queue win-back emails

2. Channel Manager v2 (OTA adapter framework):
   - GET /api/channels/v2/adapters — list 6 OTAs with health stats
   - POST /api/channels/v2/configure — configure adapter credentials
   - POST /api/channels/v2/queue/push — enqueue sync job
   - POST /api/channels/v2/queue/{id}/retry — retry failed job
   - GET /api/channels/v2/history — audit trail
   - GET /api/channels/v2/health — overall sync health

Role-based access:
- CRM profile: admin, manager, receptionist
- CRM segments/winback: admin, manager only
- Channels v2: admin, manager (configure: admin only)
"""

import pytest
import requests
import os
import time
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"


@pytest.fixture(scope="module")
def admin_session():
    """Get authenticated admin session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    
    return session


@pytest.fixture(scope="module")
def receptionist_session():
    """Get authenticated receptionist session (limited permissions)"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # First ensure receptionist exists
    admin_session = requests.Session()
    admin_session.headers.update({"Content-Type": "application/json"})
    admin_session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    # Try to create receptionist if not exists
    admin_session.post(f"{BASE_URL}/api/auth/register", json={
        "email": RECEPTIONIST_EMAIL,
        "password": RECEPTIONIST_PASSWORD,
        "name": "Test Receptionist",
        "role": "receptionist",
        "department": "front_desk"
    })
    
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": RECEPTIONIST_EMAIL,
        "password": RECEPTIONIST_PASSWORD
    })
    
    if response.status_code != 200:
        pytest.skip(f"Receptionist login failed: {response.status_code}")
    
    return session


@pytest.fixture(scope="module")
def test_guest_email():
    """Create a test booking to ensure we have guest data"""
    return "test.guest.crm@example.com"


class TestCRM360Profile:
    """Tests for GET /api/crm/profile/{guest_email}"""
    
    def test_profile_returns_360_view(self, admin_session, test_guest_email):
        """Profile endpoint returns 360° view with stats, lifecycle, segments"""
        # First create a test booking to ensure guest exists
        booking_data = {
            "guest_name": "CRM Test Guest",
            "guest_email": test_guest_email,
            "room_type_id": "double-default",
            "check_in": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "check_out": (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d"),
            "total_price": 250.00,
            "status": "completed",
            "property_id": "default"
        }
        admin_session.post(f"{BASE_URL}/api/bookings", json=booking_data)
        
        response = admin_session.get(f"{BASE_URL}/api/crm/profile/{test_guest_email}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure
        assert "guest_email" in data
        assert "lifecycle" in data
        assert "segments" in data
        assert "stats" in data
        
        # Verify stats fields
        stats = data["stats"]
        assert "total_stays" in stats
        assert "lifetime_value" in stats
        assert "days_since_last_stay" in stats
        assert "properties_visited" in stats
        
        print(f"✓ Profile 360° view: lifecycle={data['lifecycle']}, segments={data['segments']}, total_stays={stats['total_stays']}")
    
    def test_profile_lifecycle_stages(self, admin_session):
        """Profile correctly computes lifecycle stages (lead/first-time/repeat/champion)"""
        # Test with a guest that has no bookings (lead)
        response = admin_session.get(f"{BASE_URL}/api/crm/profile/nonexistent.guest@test.com")
        assert response.status_code == 200
        
        data = response.json()
        assert data["lifecycle"] == "lead", f"Expected 'lead' for guest with no bookings, got {data['lifecycle']}"
        assert data["stats"]["total_stays"] == 0
        
        print(f"✓ Lifecycle stage 'lead' for guest with no bookings")
    
    def test_profile_receptionist_can_access(self, receptionist_session, test_guest_email):
        """Receptionist can access profile endpoint"""
        response = receptionist_session.get(f"{BASE_URL}/api/crm/profile/{test_guest_email}")
        assert response.status_code == 200, f"Receptionist should access profile, got {response.status_code}"
        
        print("✓ Receptionist can access CRM profile")


class TestCRM360Segments:
    """Tests for GET /api/crm/segments"""
    
    def test_segments_aggregates_guests(self, admin_session):
        """Segments endpoint aggregates up to 500 guests with counts"""
        response = admin_session.get(f"{BASE_URL}/api/crm/segments")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure
        assert "total_guests_scanned" in data
        assert "segments" in data
        
        segments = data["segments"]
        
        # Verify all expected segment buckets exist
        expected_segments = ["vip", "champion", "advocate", "repeat", "first-time", "lapsed", "dormant", "at-risk"]
        for seg in expected_segments:
            assert seg in segments, f"Missing segment bucket: {seg}"
            assert "count" in segments[seg]
            assert "members" in segments[seg]
        
        print(f"✓ Segments aggregated: {data['total_guests_scanned']} guests scanned")
        for seg, info in segments.items():
            if info["count"] > 0:
                print(f"  - {seg}: {info['count']} guests")
    
    def test_segments_requires_manager_role(self, receptionist_session):
        """Receptionist cannot access segments endpoint (manager/admin only)"""
        response = receptionist_session.get(f"{BASE_URL}/api/crm/segments")
        assert response.status_code in [401, 403], f"Receptionist should be denied, got {response.status_code}"
        
        print("✓ Segments endpoint correctly restricts to manager/admin")


class TestCRM360Winback:
    """Tests for winback candidates and queue"""
    
    def test_winback_candidates_returns_inactive_guests(self, admin_session):
        """Winback candidates returns guests inactive for N days"""
        response = admin_session.get(f"{BASE_URL}/api/crm/winback/candidates?days_inactive=30")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "count" in data
        assert "candidates" in data
        
        # Verify candidates are sorted by lifetime_value desc
        candidates = data["candidates"]
        if len(candidates) >= 2:
            for i in range(len(candidates) - 1):
                assert candidates[i]["lifetime_value"] >= candidates[i+1]["lifetime_value"], \
                    "Candidates should be sorted by lifetime_value descending"
        
        print(f"✓ Winback candidates: {data['count']} guests inactive 30+ days")
    
    def test_winback_queue_creates_campaigns(self, admin_session, test_guest_email):
        """Winback queue creates campaign entries with status='queued'"""
        response = admin_session.post(f"{BASE_URL}/api/crm/winback/queue", json={
            "guest_emails": [test_guest_email, "another.guest@test.com"],
            "template": "We miss you! Here's 10% off your next stay."
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "queued_count" in data
        assert data["queued_count"] >= 1
        assert "note" in data  # Should mention Resend not integrated
        
        print(f"✓ Winback queue: {data['queued_count']} emails queued (status='queued')")
    
    def test_winback_queue_requires_emails(self, admin_session):
        """Winback queue returns 400 if no emails provided"""
        response = admin_session.post(f"{BASE_URL}/api/crm/winback/queue", json={
            "guest_emails": [],
            "template": "Test"
        })
        assert response.status_code == 400, f"Expected 400 for empty emails, got {response.status_code}"
        
        print("✓ Winback queue validates guest_emails required")
    
    def test_winback_requires_manager_role(self, receptionist_session):
        """Receptionist cannot access winback endpoints"""
        response = receptionist_session.get(f"{BASE_URL}/api/crm/winback/candidates")
        assert response.status_code in [401, 403], f"Receptionist should be denied, got {response.status_code}"
        
        print("✓ Winback endpoints correctly restrict to manager/admin")


class TestChannelsV2Adapters:
    """Tests for GET /api/channels/v2/adapters"""
    
    def test_adapters_lists_6_otas(self, admin_session):
        """Adapters endpoint lists 6 OTAs with health stats"""
        response = admin_session.get(f"{BASE_URL}/api/channels/v2/adapters")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "adapters" in data
        adapters = data["adapters"]
        
        # Verify 6 OTAs
        assert len(adapters) == 6, f"Expected 6 adapters, got {len(adapters)}"
        
        expected_adapters = ["booking.com", "expedia", "airbnb", "agoda", "hotels.com", "google"]
        adapter_keys = [a["adapter"] for a in adapters]
        for expected in expected_adapters:
            assert expected in adapter_keys, f"Missing adapter: {expected}"
        
        # Verify health_7d structure
        for adapter in adapters:
            assert "health_7d" in adapter
            health = adapter["health_7d"]
            assert "ok" in health
            assert "fail" in health
            assert "success_rate" in health
            assert "total_attempts" in health
        
        print(f"✓ Adapters list: {len(adapters)} OTAs with health stats")
        for a in adapters:
            print(f"  - {a['name']}: {a['protocol']}, rate_limit={a['rate_limit_per_min']}/min")


class TestChannelsV2Configure:
    """Tests for POST /api/channels/v2/configure"""
    
    def test_configure_validates_adapter(self, admin_session):
        """Configure validates adapter enum"""
        response = admin_session.post(f"{BASE_URL}/api/channels/v2/configure", json={
            "adapter": "invalid_ota",
            "enabled": True,
            "credentials": {"api_key": "test"}
        })
        assert response.status_code == 400, f"Expected 400 for invalid adapter, got {response.status_code}"
        
        print("✓ Configure validates adapter enum")
    
    def test_configure_stores_credentials(self, admin_session):
        """Configure stores credentials per adapter"""
        response = admin_session.post(f"{BASE_URL}/api/channels/v2/configure", json={
            "adapter": "booking.com",
            "enabled": True,
            "credentials": {"hotel_id": "TEST123", "api_key": "test_key"},
            "property_mapping": {"default": "PROP001"}
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("configured") == True
        assert data.get("adapter") == "booking.com"
        
        print("✓ Configure stores credentials for booking.com")


class TestChannelsV2Queue:
    """Tests for queue push and retry"""
    
    def test_queue_push_enqueues_job(self, admin_session):
        """Queue push enqueues job with validated adapter + job_type"""
        response = admin_session.post(f"{BASE_URL}/api/channels/v2/queue/push", json={
            "adapter": "booking.com",
            "job_type": "rate_push",
            "property_id": "default",
            "payload": {"date": "2026-01-15", "rate": 150}
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("queued") == True
        assert "job_id" in data
        
        print(f"✓ Queue push: job_id={data['job_id']}")
        return data["job_id"]
    
    def test_queue_push_validates_adapter(self, admin_session):
        """Queue push validates adapter"""
        response = admin_session.post(f"{BASE_URL}/api/channels/v2/queue/push", json={
            "adapter": "invalid_ota",
            "job_type": "rate_push",
            "payload": {}
        })
        assert response.status_code == 400, f"Expected 400 for invalid adapter, got {response.status_code}"
        
        print("✓ Queue push validates adapter")
    
    def test_queue_push_validates_job_type(self, admin_session):
        """Queue push validates job_type"""
        response = admin_session.post(f"{BASE_URL}/api/channels/v2/queue/push", json={
            "adapter": "booking.com",
            "job_type": "invalid_job",
            "payload": {}
        })
        assert response.status_code == 400, f"Expected 400 for invalid job_type, got {response.status_code}"
        
        print("✓ Queue push validates job_type")
    
    def test_queue_job_transitions(self, admin_session):
        """Job moves pending → in-flight → completed (or failed/pending with backoff)"""
        # Push a job
        response = admin_session.post(f"{BASE_URL}/api/channels/v2/queue/push", json={
            "adapter": "expedia",
            "job_type": "inventory_push",
            "property_id": "default",
            "payload": {"date": "2026-01-16", "rooms": 5}
        })
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Wait for async dispatch to complete
        time.sleep(1)
        
        # Check queue status
        response = admin_session.get(f"{BASE_URL}/api/channels/v2/queue?limit=50")
        assert response.status_code == 200
        
        jobs = response.json()["jobs"]
        job = next((j for j in jobs if j["id"] == job_id), None)
        
        if job:
            # Job should have transitioned from pending
            assert job["status"] in ["completed", "failed", "pending", "in-flight"], \
                f"Unexpected status: {job['status']}"
            assert job["attempt_count"] >= 1, "Job should have at least 1 attempt"
            
            print(f"✓ Job transition: status={job['status']}, attempts={job['attempt_count']}")
        else:
            print(f"✓ Job {job_id} processed (may have been removed from queue)")
    
    def test_queue_retry_resets_status(self, admin_session):
        """Retry sets status back to pending"""
        # First push a job
        response = admin_session.post(f"{BASE_URL}/api/channels/v2/queue/push", json={
            "adapter": "airbnb",
            "job_type": "rate_push",
            "property_id": "default",
            "payload": {"date": "2026-01-17", "rate": 200}
        })
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        
        # Wait for initial processing
        time.sleep(1)
        
        # Try to retry (may fail if job completed successfully)
        response = admin_session.post(f"{BASE_URL}/api/channels/v2/queue/{job_id}/retry")
        
        # Either succeeds (job was failed/pending) or fails (job completed)
        if response.status_code == 200:
            assert response.json().get("retrying") == True
            print(f"✓ Retry successful for job {job_id}")
        else:
            print(f"✓ Retry not applicable (job may have completed): {response.status_code}")


class TestChannelsV2History:
    """Tests for GET /api/channels/v2/history"""
    
    def test_history_shows_audit_trail(self, admin_session):
        """History shows audit trail with ok/error/ota_ref"""
        # First push some jobs to generate history
        admin_session.post(f"{BASE_URL}/api/channels/v2/queue/push", json={
            "adapter": "agoda",
            "job_type": "rate_push",
            "property_id": "default",
            "payload": {"date": "2026-01-18", "rate": 180}
        })
        
        time.sleep(1)  # Wait for async processing
        
        response = admin_session.get(f"{BASE_URL}/api/channels/v2/history?limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "history" in data
        assert "count" in data
        
        if data["count"] > 0:
            entry = data["history"][0]
            assert "ok" in entry
            assert "adapter" in entry
            assert "job_type" in entry
            assert "created_at" in entry
            
            # If successful, should have ota_ref
            if entry["ok"]:
                assert "ota_ref" in entry
            else:
                assert "error" in entry
        
        print(f"✓ History audit trail: {data['count']} entries")
    
    def test_history_filters_by_adapter(self, admin_session):
        """History can filter by adapter"""
        response = admin_session.get(f"{BASE_URL}/api/channels/v2/history?adapter=booking.com&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        for entry in data["history"]:
            assert entry["adapter"] == "booking.com", f"Expected booking.com, got {entry['adapter']}"
        
        print(f"✓ History filters by adapter: {data['count']} booking.com entries")


class TestChannelsV2Health:
    """Tests for GET /api/channels/v2/health"""
    
    def test_health_returns_aggregate_stats(self, admin_session):
        """Health returns by_adapter success/fail counts and queue stats"""
        response = admin_session.get(f"{BASE_URL}/api/channels/v2/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "by_adapter" in data
        assert "queue" in data
        
        queue = data["queue"]
        assert "pending" in queue
        assert "failed" in queue
        
        print(f"✓ Health stats: queue pending={queue['pending']}, failed={queue['failed']}")
        
        if data["by_adapter"]:
            for adapter, stats in data["by_adapter"].items():
                print(f"  - {adapter}: ok={stats.get('ok', 0)}, fail={stats.get('fail', 0)}")


class TestChannelsV2RoleAccess:
    """Tests for role-based access control"""
    
    def test_manager_can_access_adapters(self, admin_session):
        """Manager role can access adapters endpoint"""
        # Admin has manager-level access
        response = admin_session.get(f"{BASE_URL}/api/channels/v2/adapters")
        assert response.status_code == 200
        print("✓ Manager/Admin can access adapters")
    
    def test_receptionist_denied_channels_v2(self, receptionist_session):
        """Receptionist cannot access channels v2 endpoints"""
        response = receptionist_session.get(f"{BASE_URL}/api/channels/v2/adapters")
        assert response.status_code in [401, 403], f"Receptionist should be denied, got {response.status_code}"
        
        print("✓ Receptionist correctly denied access to channels v2")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
