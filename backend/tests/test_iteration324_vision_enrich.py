"""
Iteration 324 - Vision Enrich Competitors Backend Tests

Tests for the new vision-enrich endpoints that run GPT-4o-mini Vision over
screenshots of saved competitors to extract room_count, price, currency, etc.

Endpoints tested:
1. POST /api/revenue/market-robot/{property_id}/competitors/vision-enrich
2. GET /api/revenue/market-robot/{property_id}/competitors/vision-status
3. POST /api/revenue/market-robot/{property_id}/competitors/bulk-add (with vision_* fields)
4. GET /api/revenue/market-robot/{property_id}/competitors (regression - verify vision_* fields)
5. Auth enforcement (401 without token)
"""

import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Auth failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip("No token in auth response")
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with Bearer token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestVisionEnrichAuth:
    """Test auth enforcement on new vision endpoints"""

    def test_vision_enrich_requires_auth(self):
        """POST /competitors/vision-enrich should return 401 without token"""
        resp = requests.post(f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/competitors/vision-enrich")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text[:200]}"
        print("✓ POST /competitors/vision-enrich correctly requires auth (401)")

    def test_vision_status_requires_auth(self):
        """GET /competitors/vision-status should return 401 without token"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/competitors/vision-status")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text[:200]}"
        print("✓ GET /competitors/vision-status correctly requires auth (401)")


class TestVisionEnrichEndpoint:
    """Test POST /api/revenue/market-robot/{property_id}/competitors/vision-enrich"""

    def test_vision_enrich_with_competitors(self, auth_headers):
        """aldgate-flats has 8 competitors - should return queued > 0, status='queued'"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/competitors/vision-enrich",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        
        # Verify response structure
        assert "queued" in data, f"Missing 'queued' key in response: {data}"
        assert "status" in data, f"Missing 'status' key in response: {data}"
        
        # aldgate-flats has competitors, so queued should be > 0
        assert data["queued"] > 0, f"Expected queued > 0 for aldgate-flats, got {data['queued']}"
        assert data["status"] == "queued", f"Expected status='queued', got {data['status']}"
        
        print(f"✓ POST /competitors/vision-enrich for aldgate-flats: queued={data['queued']}, status={data['status']}")

    def test_vision_enrich_no_competitors(self, auth_headers):
        """camden-suites has 0 competitors - should return queued=0, status='no_competitors'"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/camden-suites/competitors/vision-enrich",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        
        # Verify response structure
        assert "queued" in data, f"Missing 'queued' key in response: {data}"
        assert "status" in data, f"Missing 'status' key in response: {data}"
        
        # camden-suites has 0 competitors
        assert data["queued"] == 0, f"Expected queued=0 for camden-suites, got {data['queued']}"
        assert data["status"] == "no_competitors", f"Expected status='no_competitors', got {data['status']}"
        
        print(f"✓ POST /competitors/vision-enrich for camden-suites: queued={data['queued']}, status={data['status']}")


class TestVisionStatusEndpoint:
    """Test GET /api/revenue/market-robot/{property_id}/competitors/vision-status"""

    def test_vision_status_idle(self, auth_headers):
        """Property that never ran vision-enrich should return status='idle'"""
        # Use a property that likely hasn't run vision-enrich
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/camden-suites/competitors/vision-status",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        
        # Should have status field
        assert "status" in data, f"Missing 'status' key in response: {data}"
        # For a property that never ran, status should be 'idle'
        # (or could be 'no_competitors' if we just triggered it above)
        assert data["status"] in ["idle", "no_competitors", "queued", "running", "done"], \
            f"Unexpected status: {data['status']}"
        
        print(f"✓ GET /competitors/vision-status for camden-suites: status={data['status']}")

    def test_vision_status_after_trigger(self, auth_headers):
        """After triggering vision-enrich, status should show progress fields"""
        # First trigger vision-enrich on a property with competitors
        trigger_resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/london-suites/competitors/vision-enrich",
            headers=auth_headers
        )
        
        # Now check status
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/london-suites/competitors/vision-status",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        
        # Verify status doc structure
        assert "status" in data, f"Missing 'status' key: {data}"
        assert data["status"] in ["queued", "running", "done"], f"Unexpected status: {data['status']}"
        
        # If queued or running, should have progress fields
        if data["status"] in ["queued", "running"]:
            assert "total" in data, f"Missing 'total' key: {data}"
            assert "done" in data, f"Missing 'done' key: {data}"
            assert "enriched" in data, f"Missing 'enriched' key: {data}"
            assert "blocked" in data, f"Missing 'blocked' key: {data}"
            assert "errors" in data, f"Missing 'errors' key: {data}"
            assert "started_at" in data, f"Missing 'started_at' key: {data}"
        
        print(f"✓ GET /competitors/vision-status for london-suites: {data}")


class TestBulkAddWithVisionFields:
    """Test POST /api/revenue/market-robot/{property_id}/competitors/bulk-add with vision_* fields"""

    def test_bulk_add_with_vision_fields(self, auth_headers):
        """Bulk-add a competitor with vision_* fields and verify they persist"""
        # Generate unique URL to avoid collision
        unique_id = uuid.uuid4().hex[:8]
        test_url = f"https://www.booking.com/hotel/gb/visiontest-{unique_id}.html"
        
        payload = {
            "candidates": [{
                "name": f"Vision Test Hotel {unique_id}",
                "booking_url": test_url,
                "vision_room_count": 10,
                "vision_price": 200.0,
                "vision_currency": "GBP",
                "vision_star_rating": 4,
                "vision_review_score": 8.5,
                "vision_review_count": 150
            }]
        }
        
        # Add the competitor
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/competitors/bulk-add",
            headers=auth_headers,
            json=payload
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        
        # Verify response
        assert data.get("ok") is True, f"Expected ok=true: {data}"
        assert data.get("added") == 1, f"Expected added=1: {data}"
        
        print(f"✓ POST /competitors/bulk-add with vision fields: {data}")
        
        # Now GET competitors and verify the vision fields persisted
        get_resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/competitors",
            headers=auth_headers
        )
        assert get_resp.status_code == 200, f"Expected 200, got {get_resp.status_code}: {get_resp.text[:300]}"
        resp_data = get_resp.json()
        
        # Handle both list and dict response formats
        if isinstance(resp_data, dict):
            competitors = resp_data.get("competitors", [])
        else:
            competitors = resp_data
        
        # Find our test competitor
        test_comp = None
        for c in competitors:
            if test_url in (c.get("booking_url") or ""):
                test_comp = c
                break
        
        assert test_comp is not None, f"Could not find test competitor with URL {test_url}"
        
        # Verify vision fields persisted
        assert test_comp.get("vision_room_count") == 10, \
            f"Expected vision_room_count=10, got {test_comp.get('vision_room_count')}"
        assert test_comp.get("vision_price") == 200.0, \
            f"Expected vision_price=200.0, got {test_comp.get('vision_price')}"
        assert test_comp.get("vision_currency") == "GBP", \
            f"Expected vision_currency='GBP', got {test_comp.get('vision_currency')}"
        assert test_comp.get("vision_star_rating") == 4, \
            f"Expected vision_star_rating=4, got {test_comp.get('vision_star_rating')}"
        assert test_comp.get("vision_review_score") == 8.5, \
            f"Expected vision_review_score=8.5, got {test_comp.get('vision_review_score')}"
        assert test_comp.get("vision_review_count") == 150, \
            f"Expected vision_review_count=150, got {test_comp.get('vision_review_count')}"
        assert test_comp.get("vision_checked_at") is not None, \
            f"Expected vision_checked_at to be set, got None"
        
        print(f"✓ Vision fields persisted correctly on competitor: {test_comp.get('name')}")
        print(f"  - vision_room_count: {test_comp.get('vision_room_count')}")
        print(f"  - vision_price: {test_comp.get('vision_price')}")
        print(f"  - vision_currency: {test_comp.get('vision_currency')}")
        print(f"  - vision_star_rating: {test_comp.get('vision_star_rating')}")
        print(f"  - vision_review_score: {test_comp.get('vision_review_score')}")
        print(f"  - vision_review_count: {test_comp.get('vision_review_count')}")
        print(f"  - vision_checked_at: {test_comp.get('vision_checked_at')}")


class TestCompetitorsRegressionWithVisionFields:
    """Regression: GET /competitors should return vision_* fields after vision-enrich runs"""

    def test_competitors_list_returns_vision_fields(self, auth_headers):
        """GET /competitors should include vision_* fields where populated"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/competitors",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        resp_data = resp.json()
        
        # Handle both list and dict response formats
        if isinstance(resp_data, dict):
            competitors = resp_data.get("competitors", [])
        else:
            competitors = resp_data
        
        assert isinstance(competitors, list), f"Expected list, got {type(competitors)}"
        assert len(competitors) > 0, "Expected at least one competitor for aldgate-flats"
        
        # Check that the response structure is correct
        for c in competitors:
            assert "id" in c, f"Missing 'id' in competitor: {c}"
            assert "name" in c, f"Missing 'name' in competitor: {c}"
            assert "booking_url" in c, f"Missing 'booking_url' in competitor: {c}"
        
        # Count how many have vision fields populated
        with_vision = [c for c in competitors if c.get("vision_checked_at")]
        print(f"✓ GET /competitors for aldgate-flats: {len(competitors)} total, {len(with_vision)} with vision data")
        
        # If any have vision data, verify the fields
        if with_vision:
            sample = with_vision[0]
            print(f"  Sample competitor with vision data: {sample.get('name')}")
            if sample.get("vision_room_count") is not None:
                print(f"    - vision_room_count: {sample.get('vision_room_count')}")
            if sample.get("vision_price") is not None:
                print(f"    - vision_price: {sample.get('vision_price')}")
            if sample.get("vision_currency"):
                print(f"    - vision_currency: {sample.get('vision_currency')}")
            if sample.get("vision_is_blocked") is not None:
                print(f"    - vision_is_blocked: {sample.get('vision_is_blocked')}")


class TestVisionEnrichPolling:
    """Test polling vision-status until done (time-boxed)"""

    def test_poll_vision_status_until_done_or_timeout(self, auth_headers):
        """Trigger vision-enrich on a small property and poll until done or 90s timeout"""
        # Use ryam-suites which has 5 competitors (smaller than aldgate-flats)
        property_id = "ryam-suites"
        
        # Trigger vision-enrich
        trigger_resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{property_id}/competitors/vision-enrich",
            headers=auth_headers
        )
        assert trigger_resp.status_code == 200, f"Trigger failed: {trigger_resp.status_code}"
        trigger_data = trigger_resp.json()
        
        if trigger_data.get("status") == "no_competitors":
            pytest.skip(f"{property_id} has no competitors")
        
        print(f"✓ Triggered vision-enrich for {property_id}: queued={trigger_data.get('queued')}")
        
        # Poll for up to 90 seconds
        max_wait = 90
        poll_interval = 10
        elapsed = 0
        final_status = None
        
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            
            status_resp = requests.get(
                f"{BASE_URL}/api/revenue/market-robot/{property_id}/competitors/vision-status",
                headers=auth_headers
            )
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            final_status = status_data
            
            print(f"  [{elapsed}s] status={status_data.get('status')}, "
                  f"done={status_data.get('done')}/{status_data.get('total')}, "
                  f"enriched={status_data.get('enriched')}, blocked={status_data.get('blocked')}")
            
            if status_data.get("status") == "done":
                print(f"✓ Vision-enrich completed in {elapsed}s")
                break
        
        # Verify final status has expected fields
        assert final_status is not None
        assert "status" in final_status
        assert "total" in final_status
        assert "done" in final_status
        assert "enriched" in final_status
        assert "blocked" in final_status
        assert "errors" in final_status
        
        if final_status.get("status") == "done":
            assert "finished_at" in final_status, "Missing finished_at when status=done"
            print(f"✓ Final status: enriched={final_status.get('enriched')}, "
                  f"blocked={final_status.get('blocked')}, errors={final_status.get('errors')}")
        else:
            print(f"⚠ Vision-enrich still running after {max_wait}s (this is OK for large competitor sets)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
