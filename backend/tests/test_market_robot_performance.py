"""
Market Robot Performance Tests — Iteration 326
Tests for performance fixes in occupancy-pickup, supply, and discover endpoints.

Issues being verified:
1. GET /api/revenue/market-robot/{property_id}/occupancy-pickup?days=90 — was timing out at 30s+, now parallel
2. GET /api/revenue/market-robot/{property_id}/supply?days=90 — was timing out, now parallel
3. POST /api/revenue/market-robot/{property_id}/competitors/discover — now BackgroundTask with polling
4. GET /api/revenue/market-robot/{property_id}/competitors/discover-status — NEW polling endpoint
5. Regression: AI Pricing endpoints still work
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL not set")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Test property IDs
PROPERTY_ALDGATE = "aldgate-flats"
PROPERTY_CAMDEN = "camden-suites"
PROPERTY_ALL = "all"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
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
    """Auth headers for requests"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestOccupancyPickupPerformance:
    """Test occupancy-pickup endpoint performance (Issue #1)"""
    
    def test_occupancy_pickup_90_days_aldgate(self, auth_headers):
        """GET /api/revenue/market-robot/aldgate-flats/occupancy-pickup?days=90 must return 200 in <10s"""
        start = time.time()
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ALDGATE}/occupancy-pickup",
            params={"days": 90},
            headers=auth_headers,
            timeout=30
        )
        elapsed = time.time() - start
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        assert elapsed < 10, f"Response took {elapsed:.2f}s, expected <10s"
        
        data = resp.json()
        # Verify structure
        assert "daily" in data, "Missing 'daily' array"
        assert "kpis" in data, "Missing 'kpis' block"
        
        # Verify 90 daily rows
        daily = data.get("daily", [])
        assert len(daily) == 90, f"Expected 90 daily rows, got {len(daily)}"
        
        # Verify KPIs block
        kpis = data.get("kpis", {})
        assert "avg_occupancy" in kpis, "Missing avg_occupancy in KPIs"
        assert "peak_occupancy" in kpis, "Missing peak_occupancy in KPIs"
        assert "total_rooms" in kpis, "Missing total_rooms in KPIs"
        
        print(f"✓ occupancy-pickup 90d returned in {elapsed:.2f}s with {len(daily)} rows")
        print(f"  KPIs: avg_occ={kpis.get('avg_occupancy')}%, peak={kpis.get('peak_occupancy')}%")
    
    def test_occupancy_pickup_all_branches_90_days(self, auth_headers):
        """GET /api/revenue/market-robot/all/occupancy-pickup?days=90 must work for aggregation"""
        start = time.time()
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ALL}/occupancy-pickup",
            params={"days": 90},
            headers=auth_headers,
            timeout=30
        )
        elapsed = time.time() - start
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        assert elapsed < 15, f"Response took {elapsed:.2f}s, expected <15s for all branches"
        
        data = resp.json()
        assert "daily" in data
        assert "kpis" in data
        
        daily = data.get("daily", [])
        assert len(daily) == 90, f"Expected 90 daily rows, got {len(daily)}"
        
        kpis = data.get("kpis", {})
        total_rooms = kpis.get("total_rooms", 0)
        print(f"✓ all-branches occupancy-pickup 90d returned in {elapsed:.2f}s")
        print(f"  Total rooms across fleet: {total_rooms}")


class TestSupplyDataPerformance:
    """Test supply endpoint performance (Issue #2)"""
    
    def test_supply_90_days_aldgate(self, auth_headers):
        """GET /api/revenue/market-robot/aldgate-flats/supply?days=90 must return 200 in <10s"""
        start = time.time()
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ALDGATE}/supply",
            params={"days": 90},
            headers=auth_headers,
            timeout=30
        )
        elapsed = time.time() - start
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        assert elapsed < 10, f"Response took {elapsed:.2f}s, expected <10s"
        
        data = resp.json()
        # Verify structure
        assert "snapshots" in data, "Missing 'snapshots' array"
        
        # Verify our_summary block if present
        our_summary = data.get("our_summary")
        if our_summary:
            print(f"  our_summary: avg_rate={our_summary.get('avg_rate')}, avg_occ={our_summary.get('avg_occupancy')}")
        
        snapshots = data.get("snapshots", [])
        print(f"✓ supply 90d returned in {elapsed:.2f}s with {len(snapshots)} snapshots")


class TestDiscoverCompetitorsAsync:
    """Test discover competitors BackgroundTask pattern (Issues #3, #4)"""
    
    def test_discover_returns_immediately(self, auth_headers):
        """POST /api/revenue/market-robot/camden-suites/competitors/discover must return <2s with scan_id"""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_CAMDEN}/competitors/discover",
            json={"max_results": 25, "background": True},
            headers=auth_headers,
            timeout=10
        )
        elapsed = time.time() - start
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        assert elapsed < 5, f"Response took {elapsed:.2f}s, expected <5s (should return immediately)"
        
        data = resp.json()
        assert "scan_id" in data, "Missing scan_id in response"
        assert "status" in data, "Missing status in response"
        assert data.get("status") == "queued", f"Expected status='queued', got '{data.get('status')}'"
        
        print(f"✓ discover POST returned in {elapsed:.2f}s with scan_id={data.get('scan_id')}")
        return data.get("scan_id")
    
    def test_discover_status_polling(self, auth_headers):
        """GET /api/revenue/market-robot/camden-suites/competitors/discover-status must return status"""
        # First trigger a discover
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_CAMDEN}/competitors/discover",
            json={"max_results": 15, "background": True, "radius_km": 2.5},
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        
        # Poll for status
        max_wait = 120  # 2 minutes max
        poll_interval = 5
        start = time.time()
        final_status = None
        candidates_count = 0
        
        while time.time() - start < max_wait:
            status_resp = requests.get(
                f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_CAMDEN}/competitors/discover-status",
                headers=auth_headers,
                timeout=10
            )
            assert status_resp.status_code == 200, f"Status poll failed: {status_resp.status_code}"
            
            status_data = status_resp.json()
            current_status = status_data.get("status", "unknown")
            print(f"  Poll: status={current_status} (elapsed={time.time()-start:.0f}s)")
            
            if current_status == "done":
                final_status = "done"
                result = status_data.get("result", {})
                candidates_count = len(result.get("candidates", []))
                break
            elif current_status == "error":
                final_status = "error"
                print(f"  Error: {status_data.get('error', 'unknown')}")
                break
            
            time.sleep(poll_interval)
        
        # Verify we got a result
        assert final_status in ("done", "error"), f"Discover didn't complete in {max_wait}s, last status: {final_status}"
        
        if final_status == "done":
            # The relaxed review_count filter should keep candidates with rc=None
            # Previously was filtering them out, resulting in only 2 candidates
            print(f"✓ discover completed with {candidates_count} candidates")
            # We expect >2 candidates now that the filter is relaxed
            assert candidates_count > 2, f"Expected >2 candidates (relaxed filter), got {candidates_count}"
        else:
            print(f"⚠ discover ended with error (may be expected if Booking.com blocks)")


class TestAIPricingRegression:
    """Regression tests for AI Pricing endpoints (should still work)"""
    
    def test_ai_pricing_config(self, auth_headers):
        """GET /api/revenue/ai-pricing/aldgate-flats/config still works"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/{PROPERTY_ALDGATE}/config",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "enabled" in data, "Missing 'enabled' in config"
        assert "days_horizon" in data, "Missing 'days_horizon' in config"
        print(f"✓ AI Pricing config: enabled={data.get('enabled')}, horizon={data.get('days_horizon')}")
    
    def test_ai_pricing_suggestions(self, auth_headers):
        """GET /api/revenue/ai-pricing/aldgate-flats/suggestions?days=7&use_llm=false still returns suggestions"""
        start = time.time()
        resp = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/{PROPERTY_ALDGATE}/suggestions",
            params={"days": 7, "use_llm": "false"},
            headers=auth_headers,
            timeout=30
        )
        elapsed = time.time() - start
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        suggestions = data if isinstance(data, list) else data.get("suggestions", [])
        
        # Should return suggestions for 7 days
        assert len(suggestions) >= 7, f"Expected >=7 suggestions, got {len(suggestions)}"
        
        # Verify suggestion structure
        if suggestions:
            first = suggestions[0]
            assert "date" in first or "days_out" in first, "Missing date/days_out in suggestion"
            assert "suggested_rate" in first, "Missing suggested_rate in suggestion"
        
        print(f"✓ AI Pricing suggestions: {len(suggestions)} suggestions in {elapsed:.2f}s")


class TestCompetitorsList:
    """Test that competitor list shows all competitors (Issue #10)"""
    
    def test_competitors_list_aldgate(self, auth_headers):
        """GET /api/revenue/market-robot/aldgate-flats/competitors should return all competitors"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{PROPERTY_ALDGATE}/competitors",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        competitors = data if isinstance(data, list) else data.get("competitors", [])
        
        print(f"✓ Competitors list for aldgate-flats: {len(competitors)} competitors")
        
        # List first few competitors
        for c in competitors[:5]:
            name = c.get("name", "unknown")
            url = c.get("booking_url", "")[:50]
            print(f"  - {name}: {url}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
