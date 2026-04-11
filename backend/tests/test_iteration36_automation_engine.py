"""
Iteration 36 - Automation Engine Tests
Tests for the automated guest journey messaging feature:
- 6 pre-built automation rules (Pre-Arrival, Day-of-Arrival, Mid-Stay, Post-Checkout, WhatsApp Follow-up, Cart Abandonment)
- Rule CRUD operations
- Run automation endpoint
- Logs and stats endpoints
- Template preview
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session for all tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json().get("token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


class TestAutomationRulesAPI:
    """Test automation rules CRUD endpoints"""
    
    def test_get_rules_returns_6_defaults(self, auth_session):
        """GET /api/automation/rules/{property_id} should return 6 default rules on first call"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed to get rules: {resp.text}"
        
        rules = resp.json()
        assert isinstance(rules, list), "Response should be a list"
        assert len(rules) == 6, f"Expected 6 default rules, got {len(rules)}"
        
        # Verify rule structure
        for rule in rules:
            assert "id" in rule, "Rule should have id"
            assert "name" in rule, "Rule should have name"
            assert "trigger" in rule, "Rule should have trigger"
            assert "channel" in rule, "Rule should have channel"
            assert "message_template" in rule, "Rule should have message_template"
            assert "enabled" in rule, "Rule should have enabled flag"
            assert "property_id" in rule, "Rule should have property_id"
            assert rule["property_id"] == PROPERTY_ID
        
        # Verify expected triggers are present
        triggers = [r["trigger"] for r in rules]
        assert "pre_arrival" in triggers, "Should have pre_arrival rule"
        assert "day_of_arrival" in triggers, "Should have day_of_arrival rule"
        assert "during_stay" in triggers, "Should have during_stay rule"
        assert "post_checkout" in triggers, "Should have post_checkout rule"
        assert "cart_abandonment" in triggers, "Should have cart_abandonment rule"
        
        # Verify channels
        channels = [r["channel"] for r in rules]
        assert "email" in channels, "Should have email channel rules"
        assert "whatsapp" in channels, "Should have whatsapp channel rules"
        
        print(f"✓ GET rules returned {len(rules)} default rules with correct structure")
    
    def test_get_rules_idempotent(self, auth_session):
        """Calling GET rules multiple times should return same 6 rules (not duplicate)"""
        resp1 = auth_session.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        resp2 = auth_session.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert len(resp1.json()) == len(resp2.json()), "Should not create duplicate rules"
        print("✓ GET rules is idempotent")
    
    def test_create_new_rule(self, auth_session):
        """POST /api/automation/rules should create a new rule"""
        new_rule = {
            "property_id": PROPERTY_ID,
            "name": "TEST Custom Welcome",
            "trigger": "pre_arrival",
            "timing_hours": -48,
            "channel": "email",
            "subject": "Welcome to our hotel!",
            "message_template": "Dear {guest_name}, we look forward to your arrival!",
            "enabled": True
        }
        
        resp = auth_session.post(f"{BASE_URL}/api/automation/rules", json=new_rule)
        assert resp.status_code == 200, f"Failed to create rule: {resp.text}"
        
        created = resp.json()
        assert "id" in created, "Created rule should have id"
        assert created["name"] == new_rule["name"]
        assert created["trigger"] == new_rule["trigger"]
        assert created["channel"] == new_rule["channel"]
        assert created["enabled"] == True
        
        # Store for cleanup
        TestAutomationRulesAPI.created_rule_id = created["id"]
        print(f"✓ Created new rule with id: {created['id']}")
    
    def test_toggle_rule(self, auth_session):
        """POST /api/automation/rules/{id}/toggle should toggle enabled state"""
        # Get a rule to toggle
        resp = auth_session.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        rules = resp.json()
        rule_id = rules[0]["id"]
        original_state = rules[0]["enabled"]
        
        # Toggle
        toggle_resp = auth_session.post(f"{BASE_URL}/api/automation/rules/{rule_id}/toggle")
        assert toggle_resp.status_code == 200, f"Failed to toggle: {toggle_resp.text}"
        
        result = toggle_resp.json()
        assert "enabled" in result
        assert result["enabled"] != original_state, "Enabled state should be toggled"
        
        # Toggle back
        toggle_back = auth_session.post(f"{BASE_URL}/api/automation/rules/{rule_id}/toggle")
        assert toggle_back.status_code == 200
        assert toggle_back.json()["enabled"] == original_state
        
        print(f"✓ Toggle rule works correctly")
    
    def test_update_rule(self, auth_session):
        """PUT /api/automation/rules/{id} should update rule"""
        rule_id = getattr(TestAutomationRulesAPI, 'created_rule_id', None)
        if not rule_id:
            pytest.skip("No created rule to update")
        
        updates = {
            "name": "TEST Updated Welcome",
            "timing_hours": -72
        }
        
        resp = auth_session.put(f"{BASE_URL}/api/automation/rules/{rule_id}", json=updates)
        assert resp.status_code == 200, f"Failed to update: {resp.text}"
        
        updated = resp.json()
        assert updated["name"] == updates["name"]
        assert updated["timing_hours"] == updates["timing_hours"]
        print(f"✓ Updated rule successfully")
    
    def test_delete_rule(self, auth_session):
        """DELETE /api/automation/rules/{id} should delete rule"""
        rule_id = getattr(TestAutomationRulesAPI, 'created_rule_id', None)
        if not rule_id:
            pytest.skip("No created rule to delete")
        
        resp = auth_session.delete(f"{BASE_URL}/api/automation/rules/{rule_id}")
        assert resp.status_code == 200, f"Failed to delete: {resp.text}"
        assert resp.json().get("status") == "deleted"
        print(f"✓ Deleted rule successfully")


class TestAutomationRunAPI:
    """Test automation execution endpoint"""
    
    def test_run_automation_no_bookings(self, auth_session):
        """POST /api/automation/run/{property_id} should work even with no matching bookings"""
        resp = auth_session.post(f"{BASE_URL}/api/automation/run/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed to run automation: {resp.text}"
        
        result = resp.json()
        assert "message" in result
        assert "sent" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        
        print(f"✓ Run automation returned: {result['message']}")
    
    def test_run_automation_returns_per_rule_stats(self, auth_session):
        """Run automation should return stats per rule"""
        resp = auth_session.post(f"{BASE_URL}/api/automation/run/{PROPERTY_ID}")
        assert resp.status_code == 200
        
        result = resp.json()
        for rule_result in result["results"]:
            assert "rule" in rule_result, "Should have rule name"
            assert "trigger" in rule_result, "Should have trigger type"
            assert "channel" in rule_result, "Should have channel"
            assert "matched" in rule_result, "Should have matched count"
            assert "sent" in rule_result, "Should have sent count"
        
        print(f"✓ Run automation returns per-rule stats: {len(result['results'])} rules processed")


class TestAutomationLogsAPI:
    """Test automation logs endpoint"""
    
    def test_get_logs(self, auth_session):
        """GET /api/automation/logs/{property_id} should return logs"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/logs/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed to get logs: {resp.text}"
        
        logs = resp.json()
        assert isinstance(logs, list), "Logs should be a list"
        
        # If there are logs, verify structure
        if logs:
            log = logs[0]
            assert "id" in log
            assert "rule_id" in log
            assert "rule_name" in log
            assert "property_id" in log
            assert "guest_name" in log
            assert "channel" in log
            assert "status" in log
            assert "created_at" in log
        
        print(f"✓ GET logs returned {len(logs)} entries")
    
    def test_get_logs_with_limit(self, auth_session):
        """GET /api/automation/logs/{property_id}?limit=10 should respect limit"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/logs/{PROPERTY_ID}?limit=10")
        assert resp.status_code == 200
        
        logs = resp.json()
        assert len(logs) <= 10, "Should respect limit parameter"
        print(f"✓ GET logs with limit works")


class TestAutomationStatsAPI:
    """Test automation stats endpoint"""
    
    def test_get_stats(self, auth_session):
        """GET /api/automation/stats/{property_id} should return stats"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/stats/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed to get stats: {resp.text}"
        
        stats = resp.json()
        
        # Verify all expected fields
        assert "total_rules" in stats, "Should have total_rules"
        assert "active_rules" in stats, "Should have active_rules"
        assert "total_sent" in stats, "Should have total_sent"
        assert "sent_today" in stats, "Should have sent_today"
        assert "failed" in stats, "Should have failed count"
        assert "queued" in stats, "Should have queued count"
        assert "by_channel" in stats, "Should have by_channel breakdown"
        assert "by_rule" in stats, "Should have by_rule breakdown"
        
        # Verify types
        assert isinstance(stats["total_rules"], int)
        assert isinstance(stats["active_rules"], int)
        assert isinstance(stats["total_sent"], int)
        assert isinstance(stats["by_channel"], dict)
        assert isinstance(stats["by_rule"], dict)
        
        # Should have 6 rules after seeding
        assert stats["total_rules"] >= 6, f"Expected at least 6 rules, got {stats['total_rules']}"
        
        print(f"✓ GET stats returned: {stats['active_rules']} active of {stats['total_rules']} total rules, {stats['total_sent']} sent")


class TestAutomationPreviewAPI:
    """Test template preview endpoint"""
    
    def test_preview_template(self, auth_session):
        """POST /api/automation/preview should fill template with sample data"""
        template = "Dear {guest_name}, your booking {booking_ref} for {room_type} is confirmed. Check-in: {check_in}, Check-out: {check_out}. Total: {total_price}"
        
        resp = auth_session.post(f"{BASE_URL}/api/automation/preview", json={
            "message_template": template,
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200, f"Failed to preview: {resp.text}"
        
        result = resp.json()
        assert "preview" in result
        
        preview = result["preview"]
        # Verify placeholders are replaced
        assert "{guest_name}" not in preview, "guest_name should be replaced"
        assert "{booking_ref}" not in preview, "booking_ref should be replaced"
        assert "{room_type}" not in preview, "room_type should be replaced"
        assert "{check_in}" not in preview, "check_in should be replaced"
        assert "{check_out}" not in preview, "check_out should be replaced"
        assert "{total_price}" not in preview, "total_price should be replaced"
        
        # Verify sample data is used
        assert "John Smith" in preview, "Should use sample guest name"
        assert "BK-2026-0412" in preview, "Should use sample booking ref"
        
        print(f"✓ Preview template works: {preview[:100]}...")
    
    def test_preview_with_links(self, auth_session):
        """Preview should fill link placeholders"""
        template = "Check-in here: {checkin_link}\nLeave a review: {review_link}\nGuest portal: {portal_link}"
        
        resp = auth_session.post(f"{BASE_URL}/api/automation/preview", json={
            "message_template": template,
            "property_id": PROPERTY_ID
        })
        assert resp.status_code == 200
        
        preview = resp.json()["preview"]
        assert "{checkin_link}" not in preview
        assert "{review_link}" not in preview
        assert "{portal_link}" not in preview
        
        print(f"✓ Preview fills link placeholders")


class TestAutomationRuleDefaults:
    """Test that default rules have correct configuration"""
    
    def test_pre_arrival_rule_config(self, auth_session):
        """Pre-arrival rule should be configured correctly"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        rules = resp.json()
        
        pre_arrival = next((r for r in rules if r["trigger"] == "pre_arrival" and r["channel"] == "email"), None)
        assert pre_arrival is not None, "Should have pre-arrival email rule"
        assert pre_arrival["timing_hours"] == -24, "Pre-arrival should be 24h before"
        assert "subject" in pre_arrival and pre_arrival["subject"], "Should have email subject"
        assert "{guest_name}" in pre_arrival["message_template"], "Template should have guest_name variable"
        
        print(f"✓ Pre-arrival rule configured correctly")
    
    def test_day_of_arrival_rule_config(self, auth_session):
        """Day-of-arrival rule should be WhatsApp"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        rules = resp.json()
        
        day_of = next((r for r in rules if r["trigger"] == "day_of_arrival"), None)
        assert day_of is not None, "Should have day-of-arrival rule"
        assert day_of["channel"] == "whatsapp", "Day-of-arrival should be WhatsApp"
        assert day_of["timing_hours"] == 0, "Should be on the day"
        
        print(f"✓ Day-of-arrival rule configured correctly")
    
    def test_post_checkout_rules(self, auth_session):
        """Should have both email and WhatsApp post-checkout rules"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        rules = resp.json()
        
        post_checkout_rules = [r for r in rules if r["trigger"] == "post_checkout"]
        assert len(post_checkout_rules) >= 2, "Should have at least 2 post-checkout rules"
        
        channels = [r["channel"] for r in post_checkout_rules]
        assert "email" in channels, "Should have email post-checkout"
        assert "whatsapp" in channels, "Should have WhatsApp post-checkout"
        
        print(f"✓ Post-checkout rules configured correctly ({len(post_checkout_rules)} rules)")
    
    def test_cart_abandonment_rule(self, auth_session):
        """Cart abandonment rule should exist"""
        resp = auth_session.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        rules = resp.json()
        
        cart_rule = next((r for r in rules if r["trigger"] == "cart_abandonment"), None)
        assert cart_rule is not None, "Should have cart abandonment rule"
        assert cart_rule["channel"] == "email", "Cart abandonment should be email"
        assert "{cart_link}" in cart_rule["message_template"], "Should have cart_link variable"
        
        print(f"✓ Cart abandonment rule configured correctly")


class TestAutomationAuth:
    """Test that automation endpoints require authentication"""
    
    def test_rules_requires_auth(self):
        """GET rules should require authentication"""
        resp = requests.get(f"{BASE_URL}/api/automation/rules/{PROPERTY_ID}")
        assert resp.status_code in [401, 403], "Should require auth"
        print("✓ Rules endpoint requires auth")
    
    def test_run_requires_auth(self):
        """POST run should require authentication"""
        resp = requests.post(f"{BASE_URL}/api/automation/run/{PROPERTY_ID}")
        assert resp.status_code in [401, 403], "Should require auth"
        print("✓ Run endpoint requires auth")
    
    def test_stats_requires_auth(self):
        """GET stats should require authentication"""
        resp = requests.get(f"{BASE_URL}/api/automation/stats/{PROPERTY_ID}")
        assert resp.status_code in [401, 403], "Should require auth"
        print("✓ Stats endpoint requires auth")
    
    def test_logs_requires_auth(self):
        """GET logs should require authentication"""
        resp = requests.get(f"{BASE_URL}/api/automation/logs/{PROPERTY_ID}")
        assert resp.status_code in [401, 403], "Should require auth"
        print("✓ Logs endpoint requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
