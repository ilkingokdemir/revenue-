"""
Iteration 297 - AI Journey Rule Suggestions Tests
Tests for GPT-5.2 powered journey rule suggestions via Emergent LLM Key.

Features tested:
1. GET /api/pms-pro/journey-rules/suggest - AI suggestions with stats
2. POST /api/pms-pro/journey-rules/suggest/accept - Bulk create as disabled
3. RBAC: receptionist gets 403 on both endpoints
4. Validation: empty suggestions[] returns 400
5. Regression: iter 296 journey engine features still work
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Valid triggers and actions for validation
VALID_TRIGGERS = [
    "booking_confirmed", "pre_arrival_24h", "pre_arrival_1h", "checked_in",
    "mid_stay", "pre_checkout_2h", "checked_out", "no_show", "late_checkout_requested",
]
VALID_ACTIONS = [
    "send_email", "send_sms", "send_app_push", "create_task",
    "send_qr_key", "offer_upsell", "trigger_housekeeping", "notify_manager",
]


class TestAuth:
    """Authentication helpers"""
    
    @staticmethod
    def get_admin_token():
        """Get admin token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        if resp.status_code == 200:
            return resp.json().get("token")  # API returns 'token' not 'access_token'
        pytest.skip(f"Admin login failed: {resp.status_code}")
    
    @staticmethod
    def get_receptionist_token():
        """Get receptionist token for RBAC tests"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testrecep@hotelbox.com",
            "password": "Test2026!"
        })
        if resp.status_code == 200:
            return resp.json().get("token")  # API returns 'token' not 'access_token'
        pytest.skip(f"Receptionist login failed: {resp.status_code}")


@pytest.fixture(scope="module")
def admin_headers():
    token = TestAuth.get_admin_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def receptionist_headers():
    token = TestAuth.get_receptionist_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ==================== AI SUGGESTIONS ENDPOINT ====================

class TestJourneyAISuggest:
    """GET /api/pms-pro/journey-rules/suggest tests"""
    
    def test_suggest_returns_suggestions_and_stats(self, admin_headers):
        """AI suggest endpoint returns suggestions array and stats object"""
        # Note: This may take 8-15s due to GPT-5.2 call
        resp = requests.get(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest",
            params={"property_id": "default"},
            headers=admin_headers,
            timeout=30
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "suggestions" in data, "Response must have 'suggestions' key"
        assert "stats" in data, "Response must have 'stats' key"
        assert isinstance(data["suggestions"], list), "suggestions must be a list"
        assert isinstance(data["stats"], dict), "stats must be a dict"
        
        # Verify stats structure
        stats = data["stats"]
        expected_stat_keys = [
            "total_bookings_30d", "vip_bookings_30d", "no_shows_30d",
            "late_checkout_30d", "negative_reviews_30d", "open_complaints_30d",
            "stale_maintenance", "existing_journey_rules"
        ]
        for key in expected_stat_keys:
            assert key in stats, f"stats missing key: {key}"
        
        print(f"AI returned {len(data['suggestions'])} suggestions")
        print(f"Stats: {stats}")
    
    def test_suggest_validates_trigger_action_enums(self, admin_headers):
        """Each suggestion has valid trigger and action from allowed enums"""
        resp = requests.get(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest",
            params={"property_id": "default"},
            headers=admin_headers,
            timeout=30
        )
        assert resp.status_code == 200
        
        data = resp.json()
        suggestions = data.get("suggestions", [])
        
        for i, s in enumerate(suggestions):
            assert "name" in s, f"Suggestion {i} missing 'name'"
            assert "trigger" in s, f"Suggestion {i} missing 'trigger'"
            assert "action" in s, f"Suggestion {i} missing 'action'"
            assert s["trigger"] in VALID_TRIGGERS, f"Suggestion {i} has invalid trigger: {s['trigger']}"
            assert s["action"] in VALID_ACTIONS, f"Suggestion {i} has invalid action: {s['action']}"
            
            # Optional fields
            if "rationale" in s:
                assert isinstance(s["rationale"], str)
            if "template" in s:
                assert isinstance(s["template"], str)
            if "priority" in s:
                assert isinstance(s["priority"], int)
        
        print(f"All {len(suggestions)} suggestions have valid trigger/action enums")
    
    def test_suggest_receptionist_gets_403(self, receptionist_headers):
        """Receptionist role cannot access suggest endpoint"""
        resp = requests.get(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest",
            params={"property_id": "default"},
            headers=receptionist_headers,
            timeout=10
        )
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}"
        print("RBAC: Receptionist correctly denied access to suggest endpoint")
    
    def test_suggest_unauthenticated_gets_401(self):
        """Unauthenticated request returns 401"""
        resp = requests.get(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest",
            params={"property_id": "default"},
            timeout=10
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ==================== ACCEPT SUGGESTIONS ENDPOINT ====================

class TestJourneyAIAccept:
    """POST /api/pms-pro/journey-rules/suggest/accept tests"""
    
    def test_accept_creates_disabled_rules(self, admin_headers):
        """Accept endpoint creates rules with enabled=false and ai_suggested=true"""
        # Create test suggestions
        test_suggestions = [
            {
                "name": f"TEST_AI_Rule_{int(time.time())}",
                "trigger": "pre_arrival_24h",
                "action": "send_email",
                "template": "Merhaba {{guest_name}}, yarın sizi bekliyoruz!",
                "priority": 50,
                "rationale": "VIP misafirlere özel karşılama"
            }
        ]
        
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest/accept",
            json={"property_id": "default", "suggestions": test_suggestions},
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("created") == 1
        assert "rules" in data
        assert len(data["rules"]) == 1
        
        created_rule = data["rules"][0]
        assert created_rule["enabled"] is False, "Created rule should be disabled by default"
        assert created_rule["ai_suggested"] is True, "Created rule should have ai_suggested=true"
        assert "ai_rationale" in created_rule, "Created rule should have ai_rationale"
        assert created_rule["ai_rationale"] == test_suggestions[0]["rationale"]
        
        # Cleanup
        rule_id = created_rule["id"]
        requests.delete(f"{BASE_URL}/api/pms-pro/journey-rules/{rule_id}", headers=admin_headers)
        print(f"Accept created rule with enabled=false, ai_suggested=true, cleaned up")
    
    def test_accept_bulk_creates_multiple_rules(self, admin_headers):
        """Accept endpoint can bulk-create multiple rules"""
        ts = int(time.time())
        test_suggestions = [
            {"name": f"TEST_Bulk1_{ts}", "trigger": "checked_in", "action": "send_app_push", "priority": 60},
            {"name": f"TEST_Bulk2_{ts}", "trigger": "no_show", "action": "notify_manager", "priority": 70},
        ]
        
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest/accept",
            json={"property_id": "default", "suggestions": test_suggestions},
            headers=admin_headers
        )
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("created") == 2
        assert len(data["rules"]) == 2
        
        # Verify both are disabled
        for rule in data["rules"]:
            assert rule["enabled"] is False
            assert rule["ai_suggested"] is True
        
        # Cleanup
        for rule in data["rules"]:
            requests.delete(f"{BASE_URL}/api/pms-pro/journey-rules/{rule['id']}", headers=admin_headers)
        print(f"Bulk accept created {data['created']} rules, all disabled, cleaned up")
    
    def test_accept_empty_suggestions_returns_400(self, admin_headers):
        """Accept with empty suggestions[] returns 400"""
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest/accept",
            json={"property_id": "default", "suggestions": []},
            headers=admin_headers
        )
        assert resp.status_code == 400, f"Expected 400 for empty suggestions, got {resp.status_code}"
        print("Validation: Empty suggestions[] correctly returns 400")
    
    def test_accept_receptionist_gets_403(self, receptionist_headers):
        """Receptionist role cannot access accept endpoint"""
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest/accept",
            json={"property_id": "default", "suggestions": [{"name": "Test", "trigger": "checked_in", "action": "send_email"}]},
            headers=receptionist_headers
        )
        assert resp.status_code == 403, f"Expected 403 for receptionist, got {resp.status_code}"
        print("RBAC: Receptionist correctly denied access to accept endpoint")
    
    def test_accept_unauthenticated_gets_401(self):
        """Unauthenticated request returns 401"""
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/journey-rules/suggest/accept",
            json={"property_id": "default", "suggestions": [{"name": "Test", "trigger": "checked_in", "action": "send_email"}]}
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ==================== REGRESSION: ITER 296 JOURNEY ENGINE ====================

class TestRegressionIter296:
    """Regression tests for iter 296 journey engine features"""
    
    def test_journey_run_once_still_works(self, admin_headers):
        """POST /api/pms-pro/journey-engine/run-once still works"""
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/journey-engine/run-once",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert "rules_processed" in data
        assert "fires" in data
        print(f"Run-once: {data['rules_processed']} rules, {data['fires']} fires")
    
    def test_journey_fires_history_still_works(self, admin_headers):
        """GET /api/pms-pro/journey-fires still works"""
        resp = requests.get(
            f"{BASE_URL}/api/pms-pro/journey-fires",
            params={"property_id": "default", "limit": 10},
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        print(f"Fires history: {len(data['items'])} records")
    
    def test_journey_rules_crud_still_works(self, admin_headers):
        """Journey rules CRUD still works"""
        # Create
        ts = int(time.time())
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/journey-rules",
            json={
                "property_id": "default",
                "name": f"TEST_Regression_{ts}",
                "trigger": "mid_stay",
                "action": "create_task",
                "template": "Mid-stay check",
                "priority": 100
            },
            headers=admin_headers
        )
        assert resp.status_code == 200
        rule_id = resp.json()["rule"]["id"]
        
        # Toggle
        resp = requests.patch(
            f"{BASE_URL}/api/pms-pro/journey-rules/{rule_id}/toggle",
            headers=admin_headers
        )
        assert resp.status_code == 200
        
        # Delete
        resp = requests.delete(
            f"{BASE_URL}/api/pms-pro/journey-rules/{rule_id}",
            headers=admin_headers
        )
        assert resp.status_code == 200
        print("Journey rules CRUD regression passed")
    
    def test_test_fire_still_works(self, admin_headers):
        """POST /api/pms-pro/journey-rules/{id}/test-fire still works"""
        # First create a rule
        ts = int(time.time())
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/journey-rules",
            json={
                "property_id": "default",
                "name": f"TEST_TestFire_{ts}",
                "trigger": "checked_in",
                "action": "notify_manager",
                "priority": 100
            },
            headers=admin_headers
        )
        assert resp.status_code == 200
        rule_id = resp.json()["rule"]["id"]
        
        # Get a booking to test-fire against
        bookings_resp = requests.get(
            f"{BASE_URL}/api/bookings",
            params={"limit": 1},
            headers=admin_headers
        )
        bookings_data = bookings_resp.json() if bookings_resp.status_code == 200 else []
        # Handle both list and {items: [...]} response formats
        bookings_list = bookings_data if isinstance(bookings_data, list) else bookings_data.get("items", [])
        if bookings_list:
            booking_id = bookings_list[0].get("id") or bookings_list[0].get("booking_id")
            if booking_id:
                # Test-fire
                resp = requests.post(
                    f"{BASE_URL}/api/pms-pro/journey-rules/{rule_id}/test-fire",
                    json={"booking_id": booking_id},
                    headers=admin_headers
                )
                assert resp.status_code == 200
                print(f"Test-fire regression passed with booking {booking_id}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/pms-pro/journey-rules/{rule_id}", headers=admin_headers)


# ==================== REGRESSION: ITER 295 PMS PRO ====================

class TestRegressionIter295:
    """Regression tests for iter 295 PMS Pro features"""
    
    def test_smart_assign_still_works(self, admin_headers):
        """POST /api/pms-pro/smart-assign still works"""
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/smart-assign",
            json={
                "property_id": "default",
                "check_in": "2026-02-01",
                "check_out": "2026-02-03",
                "room_type": "deluxe",
                "adults": 2
            },
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        # May return ok=false if no rooms, but endpoint works
        assert "ok" in data
        print(f"Smart-assign regression: ok={data.get('ok')}")
    
    def test_ai_concierge_still_works(self, admin_headers):
        """POST /api/pms-pro/ai-concierge still works"""
        resp = requests.post(
            f"{BASE_URL}/api/pms-pro/ai-concierge",
            json={"query": "Yarın gelen VIP'leri göster", "property_id": "default"},
            headers=admin_headers,
            timeout=30
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert "summary" in data
        assert "intent" in data
        print(f"AI Concierge regression: intent={data.get('intent')}")
    
    def test_anomalies_still_works(self, admin_headers):
        """GET /api/pms-pro/anomalies/{property_id} still works"""
        resp = requests.get(
            f"{BASE_URL}/api/pms-pro/anomalies/default",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data
        assert "alert_count" in data
        print(f"Anomalies regression: {data.get('alert_count')} alerts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
