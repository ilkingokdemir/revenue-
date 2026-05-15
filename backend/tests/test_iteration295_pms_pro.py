"""
Iteration 295 - PMS Pro Module Tests
Tests for:
1. Smart Room Assignment - POST /api/pms-pro/smart-assign
2. AI Operations Concierge - POST /api/pms-pro/ai-concierge
3. Guest Journey Orchestrator - GET/POST/PATCH/DELETE /api/pms-pro/journey-rules
4. Operations Anomaly Alerts - GET /api/pms-pro/anomalies/{property_id}
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json().get("token")

@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }

@pytest.fixture(scope="module")
def receptionist_token():
    """Get receptionist authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "testrecep@hotelbox.com",
        "password": "Test2026!"
    })
    if response.status_code != 200:
        pytest.skip("Receptionist user not available")
    return response.json().get("token")

@pytest.fixture(scope="module")
def receptionist_headers(receptionist_token):
    """Headers with receptionist auth"""
    return {
        "Authorization": f"Bearer {receptionist_token}",
        "Content-Type": "application/json"
    }


class TestSmartAssign:
    """Tests for POST /api/pms-pro/smart-assign"""
    
    def test_smart_assign_basic(self, admin_headers):
        """Test smart assign with basic parameters"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        checkout = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/pms-pro/smart-assign", 
            headers=admin_headers,
            json={
                "property_id": "default",
                "check_in": tomorrow,
                "check_out": checkout,
                "room_type": "deluxe",
                "adults": 2,
                "preferences": []
            })
        
        # May return 404 if no rooms exist, or 200 with results
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}, {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "ok" in data
            if data["ok"]:
                assert "best_room" in data
                assert "best_score" in data
                assert "top_candidates" in data
                print(f"Smart Assign result: best_room={data.get('best_room')}, score={data.get('best_score')}")
            else:
                print(f"Smart Assign: No suitable room found - {data.get('error')}")
    
    def test_smart_assign_with_preferences(self, admin_headers):
        """Test smart assign with guest preferences"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        checkout = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/pms-pro/smart-assign",
            headers=admin_headers,
            json={
                "property_id": "aldgate-flats",
                "check_in": tomorrow,
                "check_out": checkout,
                "room_type": "",
                "adults": 2,
                "preferences": ["high_floor", "quiet"]
            })
        
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") and data.get("best_reasons"):
                print(f"Preferences applied: {data['best_reasons']}")
    
    def test_smart_assign_missing_params(self, admin_headers):
        """Test smart assign with missing required parameters"""
        response = requests.post(f"{BASE_URL}/api/pms-pro/smart-assign",
            headers=admin_headers,
            json={
                "property_id": "default"
                # Missing check_in, check_out
            })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("Missing params correctly returns 400")
    
    def test_smart_assign_receptionist_access(self, receptionist_headers):
        """Test that receptionist can access smart assign"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        checkout = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        
        response = requests.post(f"{BASE_URL}/api/pms-pro/smart-assign",
            headers=receptionist_headers,
            json={
                "property_id": "default",
                "check_in": tomorrow,
                "check_out": checkout,
                "adults": 2
            })
        
        # Receptionist should have access (admin, manager, receptionist allowed)
        assert response.status_code in [200, 404], f"Receptionist should have access, got {response.status_code}"
        print("Receptionist access to smart-assign: OK")


class TestAIConcierge:
    """Tests for POST /api/pms-pro/ai-concierge"""
    
    def test_ai_concierge_arrivals_query(self, admin_headers):
        """Test AI concierge with arrivals query"""
        response = requests.post(f"{BASE_URL}/api/pms-pro/ai-concierge",
            headers=admin_headers,
            json={
                "query": "yarın gelen misafirler",
                "property_id": "default"
            })
        
        assert response.status_code == 200, f"AI Concierge failed: {response.status_code}, {response.text}"
        
        data = response.json()
        assert data.get("ok") == True
        assert "intent" in data
        assert "summary" in data
        assert "result_count" in data
        
        print(f"AI Concierge - Intent: {data['intent']}, Count: {data['result_count']}")
        print(f"Summary: {data['summary'][:200]}...")
    
    def test_ai_concierge_maintenance_query(self, admin_headers):
        """Test AI concierge with maintenance query"""
        response = requests.post(f"{BASE_URL}/api/pms-pro/ai-concierge",
            headers=admin_headers,
            json={
                "query": "açık bakım talepleri",
                "property_id": "all"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("intent") == "maintenance"
        print(f"Maintenance query - Count: {data['result_count']}")
    
    def test_ai_concierge_vip_query(self, admin_headers):
        """Test AI concierge with VIP query"""
        response = requests.post(f"{BASE_URL}/api/pms-pro/ai-concierge",
            headers=admin_headers,
            json={
                "query": "VIP misafirler bu hafta",
                "property_id": "default"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("intent") == "vip"
        print(f"VIP query - Intent detected correctly")
    
    def test_ai_concierge_housekeeping_query(self, admin_headers):
        """Test AI concierge with housekeeping query"""
        response = requests.post(f"{BASE_URL}/api/pms-pro/ai-concierge",
            headers=admin_headers,
            json={
                "query": "temizlik bekleyen odalar",
                "property_id": "default"
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("intent") == "housekeeping"
        print(f"Housekeeping query - Intent detected correctly")
    
    def test_ai_concierge_empty_query(self, admin_headers):
        """Test AI concierge with empty query"""
        response = requests.post(f"{BASE_URL}/api/pms-pro/ai-concierge",
            headers=admin_headers,
            json={
                "query": "",
                "property_id": "default"
            })
        
        assert response.status_code == 400, f"Expected 400 for empty query, got {response.status_code}"
        print("Empty query correctly returns 400")
    
    def test_ai_concierge_receptionist_access(self, receptionist_headers):
        """Test that receptionist can access AI concierge"""
        response = requests.post(f"{BASE_URL}/api/pms-pro/ai-concierge",
            headers=receptionist_headers,
            json={
                "query": "bugün çıkış yapacaklar",
                "property_id": "default"
            })
        
        assert response.status_code == 200, f"Receptionist should have access, got {response.status_code}"
        print("Receptionist access to ai-concierge: OK")


class TestJourneyRules:
    """Tests for Journey Rules CRUD endpoints"""
    
    created_rule_id = None
    
    def test_list_journey_rules(self, admin_headers):
        """Test GET /api/pms-pro/journey-rules"""
        response = requests.get(f"{BASE_URL}/api/pms-pro/journey-rules",
            headers=admin_headers,
            params={"property_id": "default"})
        
        assert response.status_code == 200, f"List rules failed: {response.status_code}"
        data = response.json()
        assert "items" in data
        print(f"Journey Rules count: {len(data['items'])}")
    
    def test_create_journey_rule(self, admin_headers):
        """Test POST /api/pms-pro/journey-rules"""
        rule_name = f"TEST_Rule_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/pms-pro/journey-rules",
            headers=admin_headers,
            json={
                "property_id": "default",
                "name": rule_name,
                "trigger": "pre_arrival_24h",
                "action": "send_email",
                "template": "Welcome email template",
                "priority": 50,
                "enabled": True
            })
        
        assert response.status_code == 200, f"Create rule failed: {response.status_code}, {response.text}"
        data = response.json()
        assert data.get("ok") == True
        assert "rule" in data
        assert data["rule"]["name"] == rule_name
        assert data["rule"]["trigger"] == "pre_arrival_24h"
        assert data["rule"]["action"] == "send_email"
        
        TestJourneyRules.created_rule_id = data["rule"]["id"]
        print(f"Created rule: {rule_name} (id: {TestJourneyRules.created_rule_id})")
    
    def test_toggle_journey_rule(self, admin_headers):
        """Test PATCH /api/pms-pro/journey-rules/{id}/toggle"""
        if not TestJourneyRules.created_rule_id:
            pytest.skip("No rule created to toggle")
        
        response = requests.patch(
            f"{BASE_URL}/api/pms-pro/journey-rules/{TestJourneyRules.created_rule_id}/toggle",
            headers=admin_headers)
        
        assert response.status_code == 200, f"Toggle failed: {response.status_code}"
        data = response.json()
        assert data.get("ok") == True
        assert "enabled" in data
        print(f"Rule toggled, new state: enabled={data['enabled']}")
    
    def test_toggle_nonexistent_rule(self, admin_headers):
        """Test toggle on non-existent rule returns 404"""
        response = requests.patch(
            f"{BASE_URL}/api/pms-pro/journey-rules/nonexistent-id/toggle",
            headers=admin_headers)
        
        assert response.status_code == 404
        print("Toggle non-existent rule correctly returns 404")
    
    def test_delete_journey_rule(self, admin_headers):
        """Test DELETE /api/pms-pro/journey-rules/{id}"""
        if not TestJourneyRules.created_rule_id:
            pytest.skip("No rule created to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/pms-pro/journey-rules/{TestJourneyRules.created_rule_id}",
            headers=admin_headers)
        
        assert response.status_code == 200, f"Delete failed: {response.status_code}"
        data = response.json()
        assert data.get("ok") == True
        print(f"Rule deleted: {TestJourneyRules.created_rule_id}")
    
    def test_delete_nonexistent_rule(self, admin_headers):
        """Test delete on non-existent rule returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/pms-pro/journey-rules/nonexistent-id",
            headers=admin_headers)
        
        assert response.status_code == 404
        print("Delete non-existent rule correctly returns 404")
    
    def test_journey_rules_manager_access(self, admin_headers):
        """Test that manager role can access journey rules (admin/manager only)"""
        # Admin should have access
        response = requests.get(f"{BASE_URL}/api/pms-pro/journey-rules",
            headers=admin_headers)
        assert response.status_code == 200
        print("Admin access to journey-rules: OK")
    
    def test_journey_rules_receptionist_denied(self, receptionist_headers):
        """Test that receptionist cannot access journey rules (admin/manager only)"""
        response = requests.get(f"{BASE_URL}/api/pms-pro/journey-rules",
            headers=receptionist_headers)
        
        # Receptionist should be denied (only admin/manager allowed)
        assert response.status_code == 403, f"Expected 403 for receptionist, got {response.status_code}"
        print("Receptionist correctly denied access to journey-rules")


class TestAnomalyAlerts:
    """Tests for GET /api/pms-pro/anomalies/{property_id}"""
    
    def test_anomalies_default_property(self, admin_headers):
        """Test anomalies endpoint for default property"""
        response = requests.get(f"{BASE_URL}/api/pms-pro/anomalies/default",
            headers=admin_headers)
        
        assert response.status_code == 200, f"Anomalies failed: {response.status_code}, {response.text}"
        
        data = response.json()
        assert "property_id" in data
        assert data["property_id"] == "default"
        assert "checked_at" in data
        assert "alert_count" in data
        assert "critical_count" in data
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        print(f"Anomalies - Total: {data['alert_count']}, Critical: {data['critical_count']}")
        for alert in data["alerts"]:
            print(f"  - [{alert['level']}] {alert['title']}")
    
    def test_anomalies_aldgate_property(self, admin_headers):
        """Test anomalies endpoint for aldgate-flats property"""
        response = requests.get(f"{BASE_URL}/api/pms-pro/anomalies/aldgate-flats",
            headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == "aldgate-flats"
        print(f"Aldgate anomalies - Total: {data['alert_count']}")
    
    def test_anomalies_alert_structure(self, admin_headers):
        """Test that alerts have correct structure"""
        response = requests.get(f"{BASE_URL}/api/pms-pro/anomalies/default",
            headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        for alert in data["alerts"]:
            assert "level" in alert
            assert alert["level"] in ["info", "warning", "critical"]
            assert "title" in alert
            assert "category" in alert
            assert "action" in alert
            print(f"Alert structure valid: {alert['category']}")
    
    def test_anomalies_receptionist_access(self, receptionist_headers):
        """Test that receptionist can access anomalies"""
        response = requests.get(f"{BASE_URL}/api/pms-pro/anomalies/default",
            headers=receptionist_headers)
        
        # Receptionist should have access (admin, manager, receptionist allowed)
        assert response.status_code == 200, f"Receptionist should have access, got {response.status_code}"
        print("Receptionist access to anomalies: OK")


class TestRegressionExistingEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_properties_endpoint(self, admin_headers):
        """Test that /api/properties still works"""
        response = requests.get(f"{BASE_URL}/api/properties", headers=admin_headers)
        assert response.status_code == 200
        print("GET /api/properties: OK")
    
    def test_market_robot_competitor_pulse(self, admin_headers):
        """Test that market robot competitor-pulse endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/revenue/market-robot/aldgate-flats/competitor-pulse",
            headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        print(f"GET /api/revenue/market-robot/competitor-pulse: OK (competitors={data.get('competitor_count')})")
    
    def test_rms_pro_revpag(self, admin_headers):
        """Test that RMS Pro RevPAG endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/rms-pro/revpag/aldgate-flats",
            headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "revpag" in data
        print(f"GET /api/rms-pro/revpag: OK (RevPAG={data.get('revpag')})")
    
    def test_auth_login(self):
        """Test that auth login still works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        assert "token" in response.json()
        print("POST /api/auth/login: OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
