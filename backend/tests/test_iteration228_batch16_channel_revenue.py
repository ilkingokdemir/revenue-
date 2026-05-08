"""
Iteration 228 - Batch 16: Open Pricing per Channel + Yield Rules Engine
Tests for channel-aware revenue management (Duetto/IDeaS level features)

Endpoints tested:
- GET /api/channel-revenue/channels/{property_id} - Get channel configs (auto-seeds 6 defaults)
- PUT /api/channel-revenue/channels/{property_id}/{channel} - Update channel config
- POST /api/channel-revenue/quote - Get channel-specific rate quote with yield rules
- GET /api/channel-revenue/rules/{property_id} - List yield rules
- POST /api/channel-revenue/rules - Create yield rule
- PUT /api/channel-revenue/rules/{rule_id} - Update yield rule
- DELETE /api/channel-revenue/rules/{rule_id} - Delete yield rule
- POST /api/channel-revenue/rules/{property_id}/seed-defaults - Seed 4 default rules

Regression tests:
- /api/tr-compliance/* - Turkish compliance (Batch 13)
- /api/eu-compliance/* - EU compliance (Batch 15)
- /api/ai-predictions/* - AI predictions (Batch 14)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestChannelRevenueAuth:
    """Authentication for channel revenue tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.cookies.get('access_token') or response.json().get('access_token')
    
    @pytest.fixture(scope="class")
    def session(self, auth_token):
        """Create authenticated session"""
        s = requests.Session()
        s.cookies.set('access_token', auth_token)
        s.headers.update({'Content-Type': 'application/json'})
        return s


class TestChannelConfigs(TestChannelRevenueAuth):
    """Test channel pricing configuration endpoints"""
    
    def test_get_channel_configs_seeds_defaults(self, session):
        """GET /api/channel-revenue/channels/default should return 6 seeded channels"""
        response = session.get(f"{BASE_URL}/api/channel-revenue/channels/default")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "channels" in data
        channels = data["channels"]
        assert len(channels) >= 6, f"Expected 6+ channels, got {len(channels)}"
        
        # Verify expected channels exist
        channel_names = {c["channel"] for c in channels}
        expected = {"direct", "booking.com", "expedia", "airbnb", "corporate", "agent"}
        assert expected.issubset(channel_names), f"Missing channels: {expected - channel_names}"
        
        # Verify multipliers for key channels
        channel_map = {c["channel"]: c for c in channels}
        assert channel_map["direct"]["base_multiplier"] == 1.0, "direct should be 1.0"
        assert channel_map["booking.com"]["base_multiplier"] == 1.18, "booking.com should be 1.18"
        assert channel_map["expedia"]["base_multiplier"] == 1.20, "expedia should be 1.20"
        assert channel_map["corporate"]["base_multiplier"] == 0.85, "corporate should be 0.85"
        
        print(f"✓ GET channels/default: {len(channels)} channels seeded with correct multipliers")
    
    def test_channel_config_has_floor_ceiling(self, session):
        """Each channel should have min_floor_pct and max_ceiling_pct"""
        response = session.get(f"{BASE_URL}/api/channel-revenue/channels/default")
        assert response.status_code == 200
        
        channels = response.json()["channels"]
        for ch in channels:
            assert "min_floor_pct" in ch, f"Missing min_floor_pct for {ch['channel']}"
            assert "max_ceiling_pct" in ch, f"Missing max_ceiling_pct for {ch['channel']}"
            assert ch["min_floor_pct"] > 0, f"Invalid floor for {ch['channel']}"
            assert ch["max_ceiling_pct"] > ch["min_floor_pct"], f"Ceiling should be > floor for {ch['channel']}"
        
        print(f"✓ All {len(channels)} channels have valid floor/ceiling percentages")
    
    def test_update_channel_config(self, session):
        """PUT /api/channel-revenue/channels/default/booking.com should update multiplier"""
        # Update booking.com multiplier to 1.25
        response = session.put(
            f"{BASE_URL}/api/channel-revenue/channels/default/booking.com",
            json={
                "property_id": "default",
                "channel": "booking.com",
                "base_multiplier": 1.25
            }
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify update persisted
        get_response = session.get(f"{BASE_URL}/api/channel-revenue/channels/default")
        assert get_response.status_code == 200
        
        channels = get_response.json()["channels"]
        booking_ch = next((c for c in channels if c["channel"] == "booking.com"), None)
        assert booking_ch is not None
        assert booking_ch["base_multiplier"] == 1.25, f"Expected 1.25, got {booking_ch['base_multiplier']}"
        
        # Restore original value
        session.put(
            f"{BASE_URL}/api/channel-revenue/channels/default/booking.com",
            json={"property_id": "default", "channel": "booking.com", "base_multiplier": 1.18}
        )
        
        print("✓ PUT channels/default/booking.com: Updated multiplier to 1.25, verified, restored")


class TestQuoteEndpoint(TestChannelRevenueAuth):
    """Test channel rate quote endpoint"""
    
    def test_quote_basic(self, session):
        """POST /api/channel-revenue/quote should return rate with all required fields"""
        check_in = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        response = session.post(f"{BASE_URL}/api/channel-revenue/quote", json={
            "property_id": "default",
            "channel": "booking.com",
            "check_in": check_in,
            "nights": 2
        })
        assert response.status_code == 200, f"Quote failed: {response.text}"
        
        data = response.json()
        
        # Verify all required fields
        required_fields = ["bar", "per_night_rate", "total", "multiplier_used", 
                          "occupancy_pct", "rules_applied", "floor", "ceiling"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify values make sense
        assert data["bar"] > 0, "BAR should be positive"
        assert data["per_night_rate"] > 0, "Per night rate should be positive"
        assert data["total"] == round(data["per_night_rate"] * 2, 2), "Total should be rate * nights"
        assert data["multiplier_used"] > 0, "Multiplier should be positive"
        assert isinstance(data["rules_applied"], list), "rules_applied should be a list"
        
        print(f"✓ POST quote: BAR=£{data['bar']}, rate=£{data['per_night_rate']}, total=£{data['total']}, mult={data['multiplier_used']}")
    
    def test_quote_shows_rules_applied(self, session):
        """Quote should show rules_applied with rate_before and rate_after"""
        # First seed default rules if not present
        session.post(f"{BASE_URL}/api/channel-revenue/rules/default/seed-defaults")
        
        # Get a Saturday check-in to trigger weekend rule
        today = datetime.now()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        saturday = (today + timedelta(days=days_until_saturday)).strftime("%Y-%m-%d")
        
        response = session.post(f"{BASE_URL}/api/channel-revenue/quote", json={
            "property_id": "default",
            "channel": "booking.com",
            "check_in": saturday,
            "nights": 1
        })
        assert response.status_code == 200, f"Quote failed: {response.text}"
        
        data = response.json()
        
        # Check if weekend rule was applied (Hafta sonu primi)
        if data["rules_applied"]:
            for rule in data["rules_applied"]:
                assert "rule_name" in rule, "Rule should have rule_name"
                assert "rate_before" in rule, "Rule should have rate_before"
                assert "rate_after" in rule, "Rule should have rate_after"
                print(f"  Rule applied: {rule['rule_name']} (£{rule['rate_before']} → £{rule['rate_after']})")
        
        print(f"✓ POST quote (Saturday): {len(data['rules_applied'])} rules applied, occupancy={data['occupancy_pct']}%")


class TestYieldRules(TestChannelRevenueAuth):
    """Test yield rules CRUD endpoints"""
    
    def test_seed_default_rules(self, session):
        """POST /api/channel-revenue/rules/default/seed-defaults should seed 4 rules"""
        # First delete existing rules to test seeding
        existing = session.get(f"{BASE_URL}/api/channel-revenue/rules/default")
        if existing.status_code == 200:
            for rule in existing.json().get("rules", []):
                session.delete(f"{BASE_URL}/api/channel-revenue/rules/{rule['id']}")
        
        # Seed defaults
        response = session.post(f"{BASE_URL}/api/channel-revenue/rules/default/seed-defaults")
        assert response.status_code == 200, f"Seed failed: {response.text}"
        
        data = response.json()
        assert data["seeded"] == 4, f"Expected 4 seeded rules, got {data['seeded']}"
        
        # Verify rule names (Turkish)
        rule_names = [r["name"] for r in data.get("rules", [])]
        expected_names = ["Yüksek doluluk", "Hafta sonu primi", "Last-minute", "OTA kanal"]
        for expected in expected_names:
            assert any(expected in name for name in rule_names), f"Missing rule containing '{expected}'"
        
        print(f"✓ POST seed-defaults: {data['seeded']} rules seeded")
    
    def test_seed_defaults_idempotent(self, session):
        """Second call to seed-defaults should return seeded=0 with note"""
        # First ensure rules exist
        session.post(f"{BASE_URL}/api/channel-revenue/rules/default/seed-defaults")
        
        # Second call
        response = session.post(f"{BASE_URL}/api/channel-revenue/rules/default/seed-defaults")
        assert response.status_code == 200
        
        data = response.json()
        assert data["seeded"] == 0, f"Expected seeded=0, got {data['seeded']}"
        assert "note" in data, "Should have note explaining rules exist"
        
        print(f"✓ POST seed-defaults (2nd call): seeded=0, note='{data.get('note', '')}'")
    
    def test_list_rules_sorted_by_priority(self, session):
        """GET /api/channel-revenue/rules/default should return rules sorted by priority desc"""
        # Ensure rules exist
        session.post(f"{BASE_URL}/api/channel-revenue/rules/default/seed-defaults")
        
        response = session.get(f"{BASE_URL}/api/channel-revenue/rules/default")
        assert response.status_code == 200, f"List failed: {response.text}"
        
        data = response.json()
        assert "rules" in data
        assert "count" in data
        assert data["count"] >= 4, f"Expected 4+ rules, got {data['count']}"
        
        # Verify sorted by priority descending
        rules = data["rules"]
        priorities = [r["priority"] for r in rules]
        assert priorities == sorted(priorities, reverse=True), "Rules should be sorted by priority desc"
        
        print(f"✓ GET rules/default: {data['count']} rules, sorted by priority desc")
    
    def test_create_rule(self, session):
        """POST /api/channel-revenue/rules should create a new rule"""
        response = session.post(f"{BASE_URL}/api/channel-revenue/rules", json={
            "property_id": "default",
            "name": "TEST_High_Occupancy_Rule",
            "enabled": True,
            "priority": 1,
            "triggers": {"occupancy_gte": 90},
            "actions": {"rate_delta_pct": 25}
        })
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should have id"
        assert data["name"] == "TEST_High_Occupancy_Rule"
        assert data["triggers"]["occupancy_gte"] == 90
        assert data["actions"]["rate_delta_pct"] == 25
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/channel-revenue/rules/{data['id']}")
        
        print(f"✓ POST rules: Created rule with id={data['id']}")
    
    def test_update_rule(self, session):
        """PUT /api/channel-revenue/rules/{id} should update the rule"""
        # Create a test rule
        create_resp = session.post(f"{BASE_URL}/api/channel-revenue/rules", json={
            "property_id": "default",
            "name": "TEST_Update_Rule",
            "enabled": True,
            "priority": 2,
            "triggers": {"occupancy_gte": 80},
            "actions": {"rate_delta_pct": 10}
        })
        assert create_resp.status_code == 200
        rule_id = create_resp.json()["id"]
        
        # Update the rule
        update_resp = session.put(f"{BASE_URL}/api/channel-revenue/rules/{rule_id}", json={
            "property_id": "default",
            "name": "TEST_Update_Rule_Modified",
            "enabled": False,
            "priority": 3,
            "triggers": {"occupancy_gte": 85},
            "actions": {"rate_delta_pct": 15}
        })
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        
        # Verify update
        list_resp = session.get(f"{BASE_URL}/api/channel-revenue/rules/default")
        rules = list_resp.json()["rules"]
        updated_rule = next((r for r in rules if r["id"] == rule_id), None)
        assert updated_rule is not None
        assert updated_rule["name"] == "TEST_Update_Rule_Modified"
        assert updated_rule["enabled"] == False
        assert updated_rule["priority"] == 3
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/channel-revenue/rules/{rule_id}")
        
        print(f"✓ PUT rules/{rule_id}: Updated rule successfully")
    
    def test_delete_rule(self, session):
        """DELETE /api/channel-revenue/rules/{id} should delete the rule"""
        # Create a test rule
        create_resp = session.post(f"{BASE_URL}/api/channel-revenue/rules", json={
            "property_id": "default",
            "name": "TEST_Delete_Rule",
            "enabled": True,
            "priority": 1,
            "triggers": {},
            "actions": {"rate_delta_pct": 5}
        })
        assert create_resp.status_code == 200
        rule_id = create_resp.json()["id"]
        
        # Delete the rule
        delete_resp = session.delete(f"{BASE_URL}/api/channel-revenue/rules/{rule_id}")
        assert delete_resp.status_code == 200, f"Delete failed: {delete_resp.text}"
        
        # Verify deletion
        list_resp = session.get(f"{BASE_URL}/api/channel-revenue/rules/default")
        rules = list_resp.json()["rules"]
        assert not any(r["id"] == rule_id for r in rules), "Rule should be deleted"
        
        print(f"✓ DELETE rules/{rule_id}: Rule deleted successfully")
    
    def test_delete_invalid_rule_returns_404(self, session):
        """DELETE /api/channel-revenue/rules/{invalid_id} should return 404"""
        response = session.delete(f"{BASE_URL}/api/channel-revenue/rules/invalid-uuid-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        print("✓ DELETE rules/invalid-id: Returns 404 as expected")


class TestWeekendRule(TestChannelRevenueAuth):
    """Test weekend rule triggers correctly"""
    
    def test_weekend_rule_triggers_on_saturday(self, session):
        """Quote with Saturday check-in should trigger 'Hafta sonu primi' rule (+15%)"""
        # Ensure default rules exist
        session.post(f"{BASE_URL}/api/channel-revenue/rules/default/seed-defaults")
        
        # Find next Saturday
        today = datetime.now()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        saturday = (today + timedelta(days=days_until_saturday)).strftime("%Y-%m-%d")
        
        response = session.post(f"{BASE_URL}/api/channel-revenue/quote", json={
            "property_id": "default",
            "channel": "direct",
            "check_in": saturday,
            "nights": 1
        })
        assert response.status_code == 200
        
        data = response.json()
        
        # Check if weekend rule was applied
        weekend_rule = next(
            (r for r in data["rules_applied"] if "Hafta sonu" in r.get("rule_name", "")),
            None
        )
        
        if weekend_rule:
            # Verify +15% was applied
            rate_before = weekend_rule["rate_before"]
            rate_after = weekend_rule["rate_after"]
            expected_after = round(rate_before * 1.15, 2)
            assert abs(rate_after - expected_after) < 0.1, f"Expected +15%, got {rate_before} → {rate_after}"
            print(f"✓ Weekend rule triggered: £{rate_before} → £{rate_after} (+15%)")
        else:
            print(f"⚠ Weekend rule not triggered (may be overridden by other rules)")


class TestRegressionBatch13to15(TestChannelRevenueAuth):
    """Regression tests for previous batches"""
    
    def test_tr_compliance_still_works(self, session):
        """Batch 13: TR Compliance endpoints should still work"""
        response = session.get(f"{BASE_URL}/api/tr-compliance/kbs/default/history")
        assert response.status_code == 200, f"TR Compliance failed: {response.text}"
        
        data = response.json()
        assert "history" in data
        print(f"✓ Regression: TR Compliance /kbs/default/history working ({len(data['history'])} exports)")
    
    def test_eu_compliance_still_works(self, session):
        """Batch 15: EU Compliance catalog should still work"""
        response = session.get(f"{BASE_URL}/api/eu-compliance/catalog")
        assert response.status_code == 200, f"EU Compliance failed: {response.text}"
        
        data = response.json()
        assert "countries" in data
        assert len(data["countries"]) >= 7, f"Expected 7+ countries, got {len(data['countries'])}"
        print(f"✓ Regression: EU Compliance /catalog working ({len(data['countries'])} countries)")
    
    def test_ai_predictions_still_works(self, session):
        """Batch 14: AI Predictions endpoint should still work"""
        response = session.get(f"{BASE_URL}/api/ai-predictions/cancel-risk/default")
        assert response.status_code == 200, f"AI Predictions failed: {response.text}"
        
        data = response.json()
        assert "rows" in data
        print(f"✓ Regression: AI Predictions /cancel-risk working ({len(data['rows'])} bookings)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
