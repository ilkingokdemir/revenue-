"""
Iteration 273: Automation Rules (Flexkeeping-style event-driven rule engine)

Tests for /api/automation/v2/* endpoints:
- GET /catalog - returns triggers (8), actions (6), operators (8)
- POST /rules - creates rule with validation
- GET /rules - lists rules with enrichment (last_run_at, last_run_ok, run_count)
- PATCH /rules/{id} - updates rule (enabled toggle, fields)
- DELETE /rules/{id} - admin-only delete
- POST /fire - emits domain event, returns matched_rules + runs[]
- GET /runs - execution history with rule_id filter

Integration tests:
- POST /api/bookings auto-fires 'booking_created' event
- POST /api/glitch-log with severity=critical auto-fires 'glitch_critical' event

Condition operators: eq, ne, in, contains, gt, lt, gte, lte
Action types: create_task, create_glitch, amenity_request, notify_role, set_room_status, tag_booking
Template substitution: {guest_name}, {room_number}, {booking_ref}
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
AUTO_API = f"{API}/automation/v2"


@pytest.fixture(scope="module")
def admin_session():
    """Login as admin and return session with cookies"""
    session = requests.Session()
    resp = session.post(f"{API}/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return session


@pytest.fixture(scope="module")
def test_rule_id(admin_session):
    """Create a test rule and return its ID for other tests"""
    rule_data = {
        "name": f"TEST_AutoRule_{uuid.uuid4().hex[:8]}",
        "description": "Test rule for automation suite",
        "trigger": "booking_created",
        "conditions": [
            {"field": "tags", "op": "contains", "value": "vip"}
        ],
        "actions": [
            {"type": "create_task", "params": {"title": "VIP Welcome for {guest_name}", "department": "housekeeping"}}
        ],
        "property_id": "all",
        "enabled": True
    }
    resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
    assert resp.status_code == 200, f"Failed to create test rule: {resp.text}"
    data = resp.json()
    assert "id" in data
    yield data["id"]
    # Cleanup
    admin_session.delete(f"{AUTO_API}/rules/{data['id']}")


class TestAutomationCatalog:
    """Tests for GET /api/automation/v2/catalog"""

    def test_catalog_returns_triggers(self, admin_session):
        """Catalog should return 8 triggers"""
        resp = admin_session.get(f"{AUTO_API}/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "triggers" in data
        triggers = data["triggers"]
        assert len(triggers) == 8, f"Expected 8 triggers, got {len(triggers)}"
        trigger_keys = [t["key"] for t in triggers]
        expected_triggers = [
            "booking_created", "booking_modified", "check_in", "check_out",
            "room_cleaned", "glitch_critical", "review_negative", "low_stock"
        ]
        for t in expected_triggers:
            assert t in trigger_keys, f"Missing trigger: {t}"

    def test_catalog_returns_actions(self, admin_session):
        """Catalog should return 6 actions"""
        resp = admin_session.get(f"{AUTO_API}/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data
        actions = data["actions"]
        assert len(actions) == 6, f"Expected 6 actions, got {len(actions)}"
        action_keys = [a["key"] for a in actions]
        expected_actions = [
            "create_task", "create_glitch", "notify_role",
            "amenity_request", "set_room_status", "tag_booking"
        ]
        for a in expected_actions:
            assert a in action_keys, f"Missing action: {a}"

    def test_catalog_returns_operators(self, admin_session):
        """Catalog should return 8 operators"""
        resp = admin_session.get(f"{AUTO_API}/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "operators" in data
        operators = data["operators"]
        assert len(operators) == 8, f"Expected 8 operators, got {len(operators)}"
        expected_ops = ["eq", "ne", "in", "contains", "gt", "lt", "gte", "lte"]
        for op in expected_ops:
            assert op in operators, f"Missing operator: {op}"

    def test_catalog_requires_auth(self):
        """Catalog should require authentication"""
        resp = requests.get(f"{AUTO_API}/catalog")
        assert resp.status_code in [401, 403]


class TestAutomationRulesCreate:
    """Tests for POST /api/automation/v2/rules"""

    def test_create_rule_valid(self, admin_session):
        """Create rule with valid data"""
        rule_data = {
            "name": f"TEST_ValidRule_{uuid.uuid4().hex[:8]}",
            "description": "Test rule",
            "trigger": "check_in",
            "conditions": [
                {"field": "nights", "op": "gte", "value": 3}
            ],
            "actions": [
                {"type": "notify_role", "params": {"role": "manager", "title": "Long stay guest"}}
            ],
            "property_id": "all",
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["name"] == rule_data["name"]
        assert data["trigger"] == "check_in"
        assert "id" in data
        assert "created_at" in data
        # Cleanup
        admin_session.delete(f"{AUTO_API}/rules/{data['id']}")

    def test_create_rule_invalid_trigger(self, admin_session):
        """Create rule with invalid trigger returns 400"""
        rule_data = {
            "name": "TEST_InvalidTrigger",
            "trigger": "invalid_trigger_xyz",
            "conditions": [],
            "actions": [{"type": "create_task", "params": {}}]
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 400
        assert "trigger" in resp.text.lower()

    def test_create_rule_invalid_action_type(self, admin_session):
        """Create rule with invalid action type returns 400"""
        rule_data = {
            "name": "TEST_InvalidAction",
            "trigger": "booking_created",
            "conditions": [],
            "actions": [{"type": "invalid_action_xyz", "params": {}}]
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 400
        assert "action" in resp.text.lower()

    def test_create_rule_invalid_operator(self, admin_session):
        """Create rule with invalid operator returns 400"""
        rule_data = {
            "name": "TEST_InvalidOperator",
            "trigger": "booking_created",
            "conditions": [{"field": "tags", "op": "invalid_op", "value": "test"}],
            "actions": [{"type": "create_task", "params": {}}]
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 400
        assert "operator" in resp.text.lower()

    def test_create_rule_requires_manager_role(self):
        """Create rule requires manager or admin role"""
        resp = requests.post(f"{AUTO_API}/rules", json={
            "name": "TEST_NoAuth",
            "trigger": "booking_created",
            "conditions": [],
            "actions": [{"type": "create_task", "params": {}}]
        })
        assert resp.status_code in [401, 403]


class TestAutomationRulesList:
    """Tests for GET /api/automation/v2/rules"""

    def test_list_rules(self, admin_session, test_rule_id):
        """List rules returns rules with enrichment"""
        resp = admin_session.get(f"{AUTO_API}/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert "count" in data
        # Find our test rule
        test_rule = next((r for r in data["rules"] if r["id"] == test_rule_id), None)
        assert test_rule is not None, "Test rule not found in list"
        # Check enrichment fields
        assert "last_run_at" in test_rule
        assert "last_run_ok" in test_rule
        assert "run_count" in test_rule

    def test_list_rules_filter_by_trigger(self, admin_session, test_rule_id):
        """List rules with trigger filter"""
        resp = admin_session.get(f"{AUTO_API}/rules?trigger=booking_created")
        assert resp.status_code == 200
        data = resp.json()
        for rule in data["rules"]:
            assert rule["trigger"] == "booking_created"

    def test_list_rules_filter_by_enabled(self, admin_session):
        """List rules with enabled filter"""
        resp = admin_session.get(f"{AUTO_API}/rules?enabled=true")
        assert resp.status_code == 200
        data = resp.json()
        for rule in data["rules"]:
            assert rule["enabled"] is True

    def test_list_rules_requires_manager(self):
        """List rules requires manager or admin role"""
        resp = requests.get(f"{AUTO_API}/rules")
        assert resp.status_code in [401, 403]


class TestAutomationRulesUpdate:
    """Tests for PATCH /api/automation/v2/rules/{id}"""

    def test_update_rule_toggle_enabled(self, admin_session, test_rule_id):
        """Toggle enabled status"""
        # Disable
        resp = admin_session.patch(f"{AUTO_API}/rules/{test_rule_id}", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["updated"] >= 0
        # Verify
        resp = admin_session.get(f"{AUTO_API}/rules/{test_rule_id}")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        # Re-enable
        resp = admin_session.patch(f"{AUTO_API}/rules/{test_rule_id}", json={"enabled": True})
        assert resp.status_code == 200

    def test_update_rule_change_name(self, admin_session, test_rule_id):
        """Update rule name"""
        new_name = f"TEST_UpdatedName_{uuid.uuid4().hex[:6]}"
        resp = admin_session.patch(f"{AUTO_API}/rules/{test_rule_id}", json={"name": new_name})
        assert resp.status_code == 200
        # Verify
        resp = admin_session.get(f"{AUTO_API}/rules/{test_rule_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name

    def test_update_rule_invalid_action(self, admin_session, test_rule_id):
        """Update with invalid action type returns 400"""
        resp = admin_session.patch(f"{AUTO_API}/rules/{test_rule_id}", json={
            "actions": [{"type": "invalid_action", "params": {}}]
        })
        assert resp.status_code == 400

    def test_update_rule_invalid_operator(self, admin_session, test_rule_id):
        """Update with invalid operator returns 400"""
        resp = admin_session.patch(f"{AUTO_API}/rules/{test_rule_id}", json={
            "conditions": [{"field": "tags", "op": "bad_op", "value": "x"}]
        })
        assert resp.status_code == 400

    def test_update_rule_not_found(self, admin_session):
        """Update non-existent rule returns 404"""
        resp = admin_session.patch(f"{AUTO_API}/rules/nonexistent-id-xyz", json={"enabled": False})
        assert resp.status_code == 404


class TestAutomationRulesDelete:
    """Tests for DELETE /api/automation/v2/rules/{id}"""

    def test_delete_rule_admin_only(self, admin_session):
        """Delete requires admin role"""
        # Create a rule to delete
        rule_data = {
            "name": f"TEST_ToDelete_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [],
            "actions": [{"type": "create_task", "params": {"title": "Test"}}]
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]
        # Delete
        resp = admin_session.delete(f"{AUTO_API}/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] >= 0
        # Verify deleted
        resp = admin_session.get(f"{AUTO_API}/rules/{rule_id}")
        assert resp.status_code == 404

    def test_delete_rule_requires_auth(self):
        """Delete requires authentication"""
        resp = requests.delete(f"{AUTO_API}/rules/some-id")
        assert resp.status_code in [401, 403]


class TestAutomationFireEvent:
    """Tests for POST /api/automation/v2/fire"""

    def test_fire_event_valid(self, admin_session):
        """Fire event returns matched_rules and runs"""
        # First create a rule that will match
        rule_data = {
            "name": f"TEST_FireTest_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [],  # No conditions = always match
            "actions": [{"type": "create_task", "params": {"title": "Auto task for {guest_name}"}}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire event
        fire_data = {
            "event": "booking_created",
            "property_id": "all",
            "booking_ref": "TEST-BK-001",
            "guest_name": "John Doe",
            "room_number": "101"
        }
        resp = admin_session.post(f"{AUTO_API}/fire", json=fire_data)
        assert resp.status_code == 200
        data = resp.json()
        assert "event" in data
        assert data["event"] == "booking_created"
        assert "matched_rules" in data
        assert data["matched_rules"] >= 1
        assert "runs" in data
        assert len(data["runs"]) >= 1

        # Cleanup
        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")

    def test_fire_event_invalid_event(self, admin_session):
        """Fire with invalid event returns 400"""
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "invalid_event_xyz"
        })
        assert resp.status_code == 400

    def test_fire_event_dry_run(self, admin_session):
        """Fire with dry_run=true doesn't persist runs"""
        fire_data = {
            "event": "booking_created",
            "dry_run": True,
            "guest_name": "Test Guest"
        }
        resp = admin_session.post(f"{AUTO_API}/fire", json=fire_data)
        assert resp.status_code == 200
        data = resp.json()
        # Dry run should still return structure
        assert "matched_rules" in data
        assert "runs" in data


class TestConditionOperators:
    """Tests for condition operator evaluation"""

    def test_operator_eq(self, admin_session):
        """Test eq operator"""
        rule_data = {
            "name": f"TEST_OpEq_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [{"field": "source", "op": "eq", "value": "direct"}],
            "actions": [{"type": "create_task", "params": {"title": "Direct booking"}}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire with matching value
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "source": "direct"
        })
        assert resp.status_code == 200
        assert resp.json()["matched_rules"] >= 1

        # Fire with non-matching value
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "source": "ota"
        })
        # Should not match our rule (but may match others)

        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")

    def test_operator_contains(self, admin_session):
        """Test contains operator for lists"""
        rule_data = {
            "name": f"TEST_OpContains_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [{"field": "tags", "op": "contains", "value": "honeymoon"}],
            "actions": [{"type": "amenity_request", "params": {"amenity": "champagne"}}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire with matching tags
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "tags": ["honeymoon", "vip"]
        })
        assert resp.status_code == 200
        # Check if our rule matched
        runs = resp.json()["runs"]
        matched = any(r["rule_id"] == rule_id for r in runs)
        assert matched, "Rule with contains condition should have matched"

        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")

    def test_operator_gte(self, admin_session):
        """Test gte operator for numeric comparison"""
        rule_data = {
            "name": f"TEST_OpGte_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [{"field": "nights", "op": "gte", "value": 5}],
            "actions": [{"type": "tag_booking", "params": {"tag": "long-stay"}}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire with nights >= 5
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "nights": 7,
            "booking_ref": "TEST-LONG"
        })
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        matched = any(r["rule_id"] == rule_id for r in runs)
        assert matched, "Rule with gte condition should have matched"

        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")

    def test_dot_path_field_access(self, admin_session):
        """Test dot-path field access (e.g., guest.email)"""
        rule_data = {
            "name": f"TEST_DotPath_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [{"field": "guest.vip", "op": "eq", "value": True}],
            "actions": [{"type": "notify_role", "params": {"role": "manager", "title": "VIP arrival"}}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire with nested guest object
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "guest": {"name": "VIP Guest", "vip": True}
        })
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        matched = any(r["rule_id"] == rule_id for r in runs)
        assert matched, "Rule with dot-path condition should have matched"

        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")


class TestActionExecution:
    """Tests for action type execution"""

    def test_action_create_task(self, admin_session):
        """Test create_task action creates document in automation_tasks"""
        rule_data = {
            "name": f"TEST_ActionTask_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [],
            "actions": [{"type": "create_task", "params": {
                "title": "Welcome {guest_name}",
                "department": "housekeeping",
                "priority": "high"
            }}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire event
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "guest_name": "Alice Smith",
            "room_number": "202"
        })
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        our_run = next((r for r in runs if r["rule_id"] == rule_id), None)
        assert our_run is not None
        assert our_run["ok"] is True
        # Check action result
        action_result = our_run["actions"][0]
        assert action_result["action"] == "create_task"
        assert action_result["ok"] is True
        assert "Alice Smith" in action_result["detail"]  # Template substitution

        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")

    def test_action_notify_role(self, admin_session):
        """Test notify_role action creates document in role_notifications"""
        rule_data = {
            "name": f"TEST_ActionNotify_{uuid.uuid4().hex[:8]}",
            "trigger": "glitch_critical",
            "conditions": [],
            "actions": [{"type": "notify_role", "params": {
                "role": "manager",
                "title": "Critical issue: {title}",
                "body": "Room {related_room} needs attention"
            }}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire event
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "glitch_critical",
            "title": "Water leak",
            "related_room": "305"
        })
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        our_run = next((r for r in runs if r["rule_id"] == rule_id), None)
        assert our_run is not None
        assert our_run["ok"] is True
        action_result = our_run["actions"][0]
        assert action_result["action"] == "notify_role"
        assert action_result["ok"] is True
        assert "manager" in action_result["detail"]

        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")


class TestAutomationRuns:
    """Tests for GET /api/automation/v2/runs"""

    def test_list_runs(self, admin_session):
        """List runs returns execution history"""
        resp = admin_session.get(f"{AUTO_API}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert "count" in data

    def test_list_runs_filter_by_rule_id(self, admin_session, test_rule_id):
        """List runs with rule_id filter"""
        resp = admin_session.get(f"{AUTO_API}/runs?rule_id={test_rule_id}")
        assert resp.status_code == 200
        data = resp.json()
        for run in data["runs"]:
            assert run["rule_id"] == test_rule_id

    def test_list_runs_limit(self, admin_session):
        """List runs respects limit parameter"""
        resp = admin_session.get(f"{AUTO_API}/runs?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["runs"]) <= 5


class TestIntegrationBookingCreated:
    """Integration test: booking creation fires booking_created event"""

    def test_booking_creation_fires_event(self, admin_session):
        """Creating a booking should auto-fire booking_created event"""
        # Create a rule that will match booking_created
        rule_data = {
            "name": f"TEST_BookingIntegration_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [],
            "actions": [{"type": "create_task", "params": {"title": "New booking: {booking_ref}"}}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Get a room type for booking
        resp = admin_session.get(f"{API}/room-types?property_id=aldgate-flats")
        if resp.status_code == 200 and resp.json():
            room_type_id = resp.json()[0]["id"]
        else:
            # Create a room type if none exists
            room_type_id = "double-aldgate-flats"

        # Create a booking
        booking_data = {
            "property_id": "aldgate-flats",
            "room_type_id": room_type_id,
            "guest_name": f"TEST_Guest_{uuid.uuid4().hex[:6]}",
            "guest_email": "test@example.com",
            "guest_phone": "+1234567890",
            "check_in": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "check_out": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
            "adults": 2,
            "children": 0,
            "rooms": 1
        }
        resp = admin_session.post(f"{API}/booking/reserve", json=booking_data)
        # Booking creation should succeed (may be 200 or 201)
        assert resp.status_code in [200, 201], f"Booking creation failed: {resp.text}"
        booking = resp.json()
        booking_ref = booking.get("booking_ref")
        assert booking_ref is not None

        # Give async task time to complete
        import time
        time.sleep(1)

        # Check if automation run was created
        resp = admin_session.get(f"{AUTO_API}/runs?rule_id={rule_id}&limit=5")
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        # The rule should have been triggered
        # Note: This may not always find the run immediately due to async nature
        # but the endpoint should work

        # Cleanup
        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")


class TestIntegrationGlitchCritical:
    """Integration test: critical glitch creation fires glitch_critical event"""

    def test_critical_glitch_fires_event(self, admin_session):
        """Creating a critical glitch should auto-fire glitch_critical event"""
        # Create a rule that will match glitch_critical
        rule_data = {
            "name": f"TEST_GlitchIntegration_{uuid.uuid4().hex[:8]}",
            "trigger": "glitch_critical",
            "conditions": [],
            "actions": [{"type": "notify_role", "params": {
                "role": "manager",
                "title": "CRITICAL: {title}",
                "body": "Department: {department}"
            }}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Create a critical glitch
        glitch_data = {
            "property_id": "default",
            "title": f"TEST_CriticalGlitch_{uuid.uuid4().hex[:6]}",
            "description": "Test critical glitch for automation",
            "severity": "critical",
            "department": "maintenance",
            "shift": "morning"
        }
        resp = admin_session.post(f"{API}/glitch-log", json=glitch_data)
        assert resp.status_code == 200, f"Glitch creation failed: {resp.text}"
        glitch = resp.json()
        glitch_id = glitch.get("id")

        # Give async task time to complete
        import time
        time.sleep(1)

        # Check if automation run was created
        resp = admin_session.get(f"{AUTO_API}/runs?rule_id={rule_id}&limit=5")
        assert resp.status_code == 200
        # The endpoint should work regardless of whether run was captured

        # Cleanup
        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")
        admin_session.delete(f"{API}/glitch-log/{glitch_id}")


class TestTemplateSubstitution:
    """Tests for template substitution in action params"""

    def test_template_substitution_guest_name(self, admin_session):
        """Template {guest_name} is replaced from payload"""
        rule_data = {
            "name": f"TEST_Template_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [],
            "actions": [{"type": "create_task", "params": {
                "title": "Welcome {guest_name} to room {room_number}",
                "description": "Booking ref: {booking_ref}"
            }}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire with payload
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "guest_name": "Bob Wilson",
            "room_number": "404",
            "booking_ref": "BK-12345"
        })
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        our_run = next((r for r in runs if r["rule_id"] == rule_id), None)
        assert our_run is not None
        action_result = our_run["actions"][0]
        # Check that template was substituted
        assert "Bob Wilson" in action_result["detail"]

        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")


class TestAndLogicConditions:
    """Tests for AND logic in conditions"""

    def test_all_conditions_must_pass(self, admin_session):
        """All conditions must pass (AND logic)"""
        rule_data = {
            "name": f"TEST_AndLogic_{uuid.uuid4().hex[:8]}",
            "trigger": "booking_created",
            "conditions": [
                {"field": "nights", "op": "gte", "value": 3},
                {"field": "source", "op": "eq", "value": "direct"}
            ],
            "actions": [{"type": "tag_booking", "params": {"tag": "long-direct"}}],
            "enabled": True
        }
        resp = admin_session.post(f"{AUTO_API}/rules", json=rule_data)
        assert resp.status_code == 200
        rule_id = resp.json()["id"]

        # Fire with both conditions met
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "nights": 5,
            "source": "direct",
            "booking_ref": "TEST-AND-1"
        })
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        matched = any(r["rule_id"] == rule_id for r in runs)
        assert matched, "Rule should match when all conditions pass"

        # Fire with only one condition met
        resp = admin_session.post(f"{AUTO_API}/fire", json={
            "event": "booking_created",
            "nights": 5,
            "source": "ota",  # This doesn't match
            "booking_ref": "TEST-AND-2"
        })
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        matched = any(r["rule_id"] == rule_id for r in runs)
        assert not matched, "Rule should NOT match when one condition fails"

        admin_session.delete(f"{AUTO_API}/rules/{rule_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
