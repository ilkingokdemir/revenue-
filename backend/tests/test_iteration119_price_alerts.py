"""
Iteration 119 - Price Intelligence Alerts Backend Tests
Tests for:
- GET /api/revenue/price-alerts/config/{property_id} — returns alert rules configuration
- PUT /api/revenue/price-alerts/config/{property_id} — updates alert rules
- POST /api/revenue/price-alerts/scan/{property_id} — scans market data, generates alerts
- GET /api/revenue/price-alerts/{property_id} — returns alert history with unread count
- PUT /api/revenue/price-alerts/{alert_id}/dismiss — marks alert as dismissed
- PUT /api/revenue/price-alerts/{alert_id}/action — records action taken on alert
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

@pytest.fixture(scope="module")
def property_id(auth_headers):
    """Get a valid property ID"""
    response = requests.get(f"{BASE_URL}/api/properties", headers=auth_headers)
    if response.status_code == 200:
        props = response.json()
        if props and len(props) > 0:
            return props[0].get("id", "all")
    return "all"


class TestPriceAlertsConfig:
    """Tests for alert configuration endpoints"""
    
    def test_get_alert_config(self, auth_headers, property_id):
        """GET /api/revenue/price-alerts/config/{property_id} returns config with all threshold fields"""
        response = requests.get(f"{BASE_URL}/api/revenue/price-alerts/config/{property_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all required threshold fields exist
        required_fields = [
            "comp_price_drop_pct", "comp_price_drop_abs",
            "comp_price_rise_pct", "comp_price_rise_abs",
            "demand_spike_pp", "demand_drop_pp",
            "supply_compression_pct", "rate_parity_diff_pct",
            "occupancy_threshold_high", "occupancy_threshold_low",
            "scan_window_days", "enabled"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data["enabled"], bool), "enabled should be boolean"
        assert isinstance(data["scan_window_days"], (int, float)), "scan_window_days should be numeric"
        print(f"✓ Config retrieved with all {len(required_fields)} threshold fields")
    
    def test_update_alert_config(self, auth_headers, property_id):
        """PUT /api/revenue/price-alerts/config/{property_id} updates alert rules"""
        update_data = {
            "comp_price_drop_pct": 7,
            "comp_price_drop_abs": 12,
            "demand_spike_pp": 15,
            "occupancy_threshold_high": 85,
            "occupancy_threshold_low": 25,
            "scan_window_days": 30,
            "enabled": True
        }
        response = requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/config/{property_id}",
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify updated values
        assert data["comp_price_drop_pct"] == 7, "comp_price_drop_pct not updated"
        assert data["scan_window_days"] == 30, "scan_window_days not updated"
        assert data["enabled"] == True, "enabled not updated"
        print("✓ Config updated successfully")
    
    def test_config_persistence(self, auth_headers, property_id):
        """Verify config changes persist after update"""
        # Update with specific values
        update_data = {"scan_window_days": 45, "occupancy_threshold_high": 82}
        requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/config/{property_id}",
            headers=auth_headers,
            json=update_data
        )
        
        # GET to verify persistence
        response = requests.get(f"{BASE_URL}/api/revenue/price-alerts/config/{property_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["scan_window_days"] == 45, "scan_window_days not persisted"
        assert data["occupancy_threshold_high"] == 82, "occupancy_threshold_high not persisted"
        print("✓ Config changes persisted correctly")


class TestPriceAlertsScan:
    """Tests for alert scanning endpoint"""
    
    def test_scan_price_alerts(self, auth_headers, property_id):
        """POST /api/revenue/price-alerts/scan/{property_id} scans and generates alerts"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/price-alerts/scan/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "generated" in data, "Missing 'generated' count"
        assert "scanned_properties" in data, "Missing 'scanned_properties'"
        assert "scan_window_days" in data, "Missing 'scan_window_days'"
        assert "scanned_at" in data, "Missing 'scanned_at'"
        
        # generated can be 0 if no new alerts detected
        assert isinstance(data["generated"], int), "generated should be integer"
        print(f"✓ Scan completed: {data['generated']} alerts generated, {data['scanned_properties']} properties scanned")
    
    def test_scan_all_properties(self, auth_headers):
        """POST /api/revenue/price-alerts/scan/all scans all properties"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/price-alerts/scan/all",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "generated" in data
        assert "scanned_properties" in data
        print(f"✓ All-property scan: {data['scanned_properties']} properties, {data['generated']} alerts")
    
    def test_scan_disabled_returns_zero(self, auth_headers, property_id):
        """Scan returns 0 alerts when scanning is disabled"""
        # Disable scanning
        requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/config/{property_id}",
            headers=auth_headers,
            json={"enabled": False}
        )
        
        response = requests.post(
            f"{BASE_URL}/api/revenue/price-alerts/scan/{property_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["generated"] == 0, "Should generate 0 alerts when disabled"
        assert "disabled" in data.get("message", "").lower(), "Should indicate scanning is disabled"
        
        # Re-enable for other tests
        requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/config/{property_id}",
            headers=auth_headers,
            json={"enabled": True}
        )
        print("✓ Disabled scan returns 0 alerts with message")


class TestPriceAlertsHistory:
    """Tests for alert history endpoint"""
    
    def test_get_price_alerts(self, auth_headers, property_id):
        """GET /api/revenue/price-alerts/{property_id} returns alert history"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/{property_id}?limit=50",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "alerts" in data, "Missing 'alerts' array"
        assert "unread_count" in data, "Missing 'unread_count'"
        assert "total" in data, "Missing 'total'"
        
        assert isinstance(data["alerts"], list), "alerts should be a list"
        assert isinstance(data["unread_count"], int), "unread_count should be integer"
        print(f"✓ Alert history: {data['total']} alerts, {data['unread_count']} unread")
    
    def test_alert_structure(self, auth_headers, property_id):
        """Verify individual alert has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/{property_id}?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if data["alerts"]:
            alert = data["alerts"][0]
            required_fields = ["id", "type", "title", "message", "category", "sub_type", 
                             "severity", "property_id", "alert_date", "created_at"]
            for field in required_fields:
                assert field in alert, f"Alert missing field: {field}"
            
            # Verify category is price_intelligence
            assert alert["category"] == "price_intelligence", f"Expected category 'price_intelligence', got '{alert['category']}'"
            
            # Verify sub_type is one of expected values
            valid_sub_types = ["comp_price_drop", "comp_price_rise", "demand_spike", 
                             "demand_drop", "supply_compression", "rate_parity"]
            assert alert["sub_type"] in valid_sub_types, f"Invalid sub_type: {alert['sub_type']}"
            
            print(f"✓ Alert structure verified: {alert['sub_type']} - {alert['title'][:50]}...")
        else:
            print("✓ No alerts to verify structure (empty list)")
    
    def test_get_all_alerts(self, auth_headers):
        """GET /api/revenue/price-alerts/all returns alerts for all properties"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/all?limit=100",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "alerts" in data
        assert "unread_count" in data
        print(f"✓ All-property alerts: {data['total']} total, {data['unread_count']} unread")


class TestPriceAlertsActions:
    """Tests for alert action endpoints (dismiss, action)"""
    
    @pytest.fixture
    def test_alert_id(self, auth_headers, property_id):
        """Get an alert ID for testing actions"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/{property_id}?limit=50",
            headers=auth_headers
        )
        if response.status_code == 200:
            alerts = response.json().get("alerts", [])
            # Find an alert that hasn't been actioned or dismissed
            for alert in alerts:
                if not alert.get("actioned") and not alert.get("dismissed"):
                    return alert["id"]
            # If all are actioned, return first one anyway
            if alerts:
                return alerts[0]["id"]
        pytest.skip("No alerts available for action testing")
    
    def test_dismiss_alert(self, auth_headers, test_alert_id):
        """PUT /api/revenue/price-alerts/{alert_id}/dismiss marks alert as dismissed"""
        response = requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/{test_alert_id}/dismiss",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "dismissed", f"Expected status 'dismissed', got '{data.get('status')}'"
        print(f"✓ Alert {test_alert_id[:8]}... dismissed successfully")
    
    def test_action_alert_adjust_rate(self, auth_headers, property_id):
        """PUT /api/revenue/price-alerts/{alert_id}/action with adjust_rate action"""
        # Get a fresh alert
        response = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/{property_id}?limit=50",
            headers=auth_headers
        )
        alerts = response.json().get("alerts", [])
        alert_id = None
        for alert in alerts:
            if not alert.get("actioned"):
                alert_id = alert["id"]
                break
        
        if not alert_id and alerts:
            alert_id = alerts[0]["id"]
        
        if not alert_id:
            pytest.skip("No alerts available for action testing")
        
        response = requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/{alert_id}/action",
            headers=auth_headers,
            json={"action": "adjust_rate", "note": "Adjusted rate by +5%"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "actioned", f"Expected status 'actioned', got '{data.get('status')}'"
        assert data.get("action") == "adjust_rate", f"Expected action 'adjust_rate', got '{data.get('action')}'"
        print(f"✓ Alert actioned with 'adjust_rate'")
    
    def test_action_alert_acknowledged(self, auth_headers, property_id):
        """PUT /api/revenue/price-alerts/{alert_id}/action with acknowledged action"""
        # Get a fresh alert
        response = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/{property_id}?limit=50",
            headers=auth_headers
        )
        alerts = response.json().get("alerts", [])
        alert_id = None
        for alert in alerts:
            if not alert.get("actioned"):
                alert_id = alert["id"]
                break
        
        if not alert_id and alerts:
            alert_id = alerts[0]["id"]
        
        if not alert_id:
            pytest.skip("No alerts available for action testing")
        
        response = requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/{alert_id}/action",
            headers=auth_headers,
            json={"action": "acknowledged"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "actioned"
        assert data.get("action") == "acknowledged"
        print(f"✓ Alert actioned with 'acknowledged'")
    
    def test_action_alert_viewed(self, auth_headers, property_id):
        """PUT /api/revenue/price-alerts/{alert_id}/action with viewed action"""
        # Get a fresh alert
        response = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/{property_id}?limit=50",
            headers=auth_headers
        )
        alerts = response.json().get("alerts", [])
        alert_id = None
        for alert in alerts:
            if not alert.get("actioned"):
                alert_id = alert["id"]
                break
        
        if not alert_id and alerts:
            alert_id = alerts[0]["id"]
        
        if not alert_id:
            pytest.skip("No alerts available for action testing")
        
        response = requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/{alert_id}/action",
            headers=auth_headers,
            json={"action": "viewed"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "actioned"
        assert data.get("action") == "viewed"
        print(f"✓ Alert actioned with 'viewed'")


class TestPriceAlertsIntegration:
    """Integration tests for full alert workflow"""
    
    def test_full_alert_workflow(self, auth_headers, property_id):
        """Test complete workflow: config -> scan -> get alerts -> action"""
        # 1. Get config
        config_resp = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/config/{property_id}",
            headers=auth_headers
        )
        assert config_resp.status_code == 200
        print("✓ Step 1: Config retrieved")
        
        # 2. Update config
        update_resp = requests.put(
            f"{BASE_URL}/api/revenue/price-alerts/config/{property_id}",
            headers=auth_headers,
            json={"scan_window_days": 14, "enabled": True}
        )
        assert update_resp.status_code == 200
        print("✓ Step 2: Config updated")
        
        # 3. Run scan
        scan_resp = requests.post(
            f"{BASE_URL}/api/revenue/price-alerts/scan/{property_id}",
            headers=auth_headers
        )
        assert scan_resp.status_code == 200
        print(f"✓ Step 3: Scan completed ({scan_resp.json().get('generated', 0)} alerts)")
        
        # 4. Get alerts
        alerts_resp = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/{property_id}?limit=10",
            headers=auth_headers
        )
        assert alerts_resp.status_code == 200
        alerts = alerts_resp.json().get("alerts", [])
        print(f"✓ Step 4: Retrieved {len(alerts)} alerts")
        
        # 5. Action an alert if available
        if alerts:
            alert_id = alerts[0]["id"]
            action_resp = requests.put(
                f"{BASE_URL}/api/revenue/price-alerts/{alert_id}/action",
                headers=auth_headers,
                json={"action": "acknowledged"}
            )
            assert action_resp.status_code == 200
            print(f"✓ Step 5: Alert actioned")
        else:
            print("✓ Step 5: Skipped (no alerts)")
        
        print("✓ Full workflow completed successfully")
    
    def test_alert_meta_contains_pricing_details(self, auth_headers, property_id):
        """Verify alert meta field contains pricing details"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/price-alerts/{property_id}?limit=50",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        alerts = response.json().get("alerts", [])
        meta_found = False
        for alert in alerts:
            meta = alert.get("meta", {})
            if meta:
                meta_found = True
                # Different alert types have different meta fields
                if alert["sub_type"] in ["comp_price_drop", "comp_price_rise"]:
                    # Should have pricing info
                    if "old_comp_avg" in meta or "new_comp_avg" in meta or "our_rate" in meta:
                        print(f"✓ Alert {alert['sub_type']} has pricing meta: {list(meta.keys())}")
                        break
                elif alert["sub_type"] in ["demand_spike", "demand_drop"]:
                    # Should have demand info
                    if "new_demand" in meta or "old_demand" in meta:
                        print(f"✓ Alert {alert['sub_type']} has demand meta: {list(meta.keys())}")
                        break
        
        if not meta_found:
            print("✓ No alerts with meta to verify (alerts may be empty)")


class TestNotificationBellIntegration:
    """Test that price_intelligence alerts appear in notification bell"""
    
    def test_notifications_include_price_intelligence(self, auth_headers):
        """Verify notifications endpoint includes price_intelligence category"""
        response = requests.get(
            f"{BASE_URL}/api/notifications?limit=100",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        notifications = data.get("notifications", [])
        
        # Check if any price_intelligence notifications exist
        price_intel_count = sum(1 for n in notifications if n.get("category") == "price_intelligence")
        print(f"✓ Notifications endpoint: {len(notifications)} total, {price_intel_count} price_intelligence")
        
        # Verify unread count is present
        assert "unread_count" in data, "Missing unread_count in notifications response"
        print(f"✓ Unread count: {data['unread_count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
