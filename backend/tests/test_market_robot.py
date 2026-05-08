"""
Test Market Robot API endpoints - Iteration 101
Tests: config, scan, supply, logs, adjustments endpoints
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://review-hub-108.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@hotelbox.com"
TEST_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestMarketRobotConfig:
    """Test Market Robot configuration endpoints"""
    
    def test_get_config_default(self, api_client):
        """GET /api/revenue/market-robot/all/config returns default config"""
        response = api_client.get(f"{BASE_URL}/api/revenue/market-robot/all/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify default config structure
        assert "city" in data, "Config should have 'city' field"
        assert "days_ahead" in data, "Config should have 'days_ahead' field"
        assert "auto_pricing" in data, "Config should have 'auto_pricing' field"
        assert "enabled" in data, "Config should have 'enabled' field"
        print(f"✓ Default config: city={data.get('city')}, days_ahead={data.get('days_ahead')}, auto_pricing={data.get('auto_pricing')}")
    
    def test_update_config(self, api_client):
        """PUT /api/revenue/market-robot/all/config saves configuration changes"""
        update_data = {
            "city": "London",
            "days_ahead": 30,
            "auto_pricing": True,
            "enabled": True,
            "max_increase_pct": 35,
            "max_decrease_pct": 25
        }
        response = api_client.put(f"{BASE_URL}/api/revenue/market-robot/all/config", json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("city") == "London", "City should be updated to London"
        assert data.get("days_ahead") == 30, "Days ahead should be 30"
        assert data.get("auto_pricing") == True, "Auto pricing should be enabled"
        print(f"✓ Config updated successfully: {data}")
        
        # Verify persistence with GET
        get_response = api_client.get(f"{BASE_URL}/api/revenue/market-robot/all/config")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data.get("city") == "London", "Config should persist city=London"
        print("✓ Config persisted correctly")


class TestMarketRobotScan:
    """Test Market Robot scan endpoint"""
    
    def test_run_scan(self, api_client):
        """POST /api/revenue/market-robot/all/scan runs a market scan"""
        scan_data = {
            "city": "London",
            "days_ahead": 7  # Small scan for testing
        }
        response = api_client.post(f"{BASE_URL}/api/revenue/market-robot/all/scan", json=scan_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check scan result structure
        assert "scan_id" in data, "Scan result should have scan_id"
        assert "city" in data, "Scan result should have city"
        assert "dates_scanned" in data, "Scan result should have dates_scanned"
        assert "status" in data, "Scan result should have status"
        
        # Verify scan completed
        assert data.get("status") == "completed", f"Scan status should be 'completed', got {data.get('status')}"
        print(f"✓ Scan completed: scan_id={data.get('scan_id')}, dates_scanned={data.get('dates_scanned')}")
        
        # Check snapshots if present
        if "snapshots" in data and len(data["snapshots"]) > 0:
            snapshot = data["snapshots"][0]
            assert "date" in snapshot, "Snapshot should have date"
            assert "unavailable_pct" in snapshot, "Snapshot should have unavailable_pct"
            assert "price_adjustment_pct" in snapshot, "Snapshot should have price_adjustment_pct"
            print(f"✓ Snapshot structure valid: {snapshot.get('date')}, unavail={snapshot.get('unavailable_pct')}%")


class TestMarketRobotSupply:
    """Test Market Robot supply data endpoint"""
    
    def test_get_supply_data(self, api_client):
        """GET /api/revenue/market-robot/all/supply returns supply snapshots"""
        response = api_client.get(f"{BASE_URL}/api/revenue/market-robot/all/supply")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "snapshots" in data, "Response should have 'snapshots' field"
        assert "summary" in data, "Response should have 'summary' field"
        
        # Check summary structure
        summary = data.get("summary", {})
        assert "total_dates" in summary, "Summary should have total_dates"
        assert "avg_unavailable_pct" in summary, "Summary should have avg_unavailable_pct"
        assert "high_demand_days" in summary, "Summary should have high_demand_days"
        assert "low_demand_days" in summary, "Summary should have low_demand_days"
        
        print(f"✓ Supply data: {len(data.get('snapshots', []))} snapshots")
        print(f"✓ Summary: avg_unavail={summary.get('avg_unavailable_pct')}%, high_demand={summary.get('high_demand_days')}, low_demand={summary.get('low_demand_days')}")
        
        # Check snapshot structure if data exists
        snapshots = data.get("snapshots", [])
        if len(snapshots) > 0:
            snap = snapshots[0]
            assert "date" in snap, "Snapshot should have date"
            assert "unavailable_pct" in snap, "Snapshot should have unavailable_pct"
            assert "price_adjustment_pct" in snap, "Snapshot should have price_adjustment_pct"
            print(f"✓ First snapshot: date={snap.get('date')}, unavail={snap.get('unavailable_pct')}%, adj={snap.get('price_adjustment_pct')}%")


class TestMarketRobotLogs:
    """Test Market Robot logs endpoint"""
    
    def test_get_logs(self, api_client):
        """GET /api/revenue/market-robot/all/logs returns scan history"""
        response = api_client.get(f"{BASE_URL}/api/revenue/market-robot/all/logs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "logs" in data, "Response should have 'logs' field"
        
        logs = data.get("logs", [])
        print(f"✓ Logs endpoint returned {len(logs)} scan logs")
        
        # Check log structure if logs exist
        if len(logs) > 0:
            log = logs[0]
            assert "id" in log, "Log should have id"
            assert "city" in log, "Log should have city"
            assert "dates_scanned" in log, "Log should have dates_scanned"
            assert "scanned_at" in log, "Log should have scanned_at"
            print(f"✓ Latest log: id={log.get('id')}, city={log.get('city')}, dates={log.get('dates_scanned')}")


class TestMarketRobotAdjustments:
    """Test Market Robot adjustments endpoint"""
    
    def test_get_adjustments(self, api_client):
        """GET /api/revenue/market-robot/all/adjustments returns rate overrides"""
        response = api_client.get(f"{BASE_URL}/api/revenue/market-robot/all/adjustments")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "adjustments" in data, "Response should have 'adjustments' field"
        
        adjustments = data.get("adjustments", [])
        print(f"✓ Adjustments endpoint returned {len(adjustments)} rate overrides")
        
        # Check adjustment structure if any exist
        if len(adjustments) > 0:
            adj = adjustments[0]
            assert "date" in adj, "Adjustment should have date"
            assert "custom_rate" in adj, "Adjustment should have custom_rate"
            assert "set_by" in adj, "Adjustment should have set_by"
            assert adj.get("set_by") == "market-robot", f"set_by should be 'market-robot', got {adj.get('set_by')}"
            print(f"✓ First adjustment: date={adj.get('date')}, rate={adj.get('custom_rate')}, set_by={adj.get('set_by')}")


class TestMarketRobotIntegration:
    """Integration tests for Market Robot workflow"""
    
    def test_full_workflow(self, api_client):
        """Test complete workflow: config -> scan -> verify supply/logs/adjustments"""
        # 1. Update config
        config_data = {"city": "London", "days_ahead": 7, "auto_pricing": True, "enabled": True}
        config_resp = api_client.put(f"{BASE_URL}/api/revenue/market-robot/all/config", json=config_data)
        assert config_resp.status_code == 200, "Config update should succeed"
        print("✓ Step 1: Config updated")
        
        # 2. Run scan
        scan_resp = api_client.post(f"{BASE_URL}/api/revenue/market-robot/all/scan", json={"city": "London", "days_ahead": 7})
        assert scan_resp.status_code == 200, "Scan should succeed"
        scan_data = scan_resp.json()
        assert scan_data.get("status") == "completed", "Scan should complete"
        print(f"✓ Step 2: Scan completed with {scan_data.get('dates_scanned')} dates")
        
        # 3. Verify supply data updated
        supply_resp = api_client.get(f"{BASE_URL}/api/revenue/market-robot/all/supply")
        assert supply_resp.status_code == 200, "Supply fetch should succeed"
        print("✓ Step 3: Supply data available")
        
        # 4. Verify logs updated
        logs_resp = api_client.get(f"{BASE_URL}/api/revenue/market-robot/all/logs")
        assert logs_resp.status_code == 200, "Logs fetch should succeed"
        logs = logs_resp.json().get("logs", [])
        assert len(logs) > 0, "Should have at least one log entry after scan"
        print(f"✓ Step 4: {len(logs)} log entries found")
        
        # 5. Check adjustments (may or may not have entries depending on supply data)
        adj_resp = api_client.get(f"{BASE_URL}/api/revenue/market-robot/all/adjustments")
        assert adj_resp.status_code == 200, "Adjustments fetch should succeed"
        print(f"✓ Step 5: Adjustments endpoint working ({len(adj_resp.json().get('adjustments', []))} entries)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
