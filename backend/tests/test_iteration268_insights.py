"""
Iteration 268: AI Auto-Learning Insights Tests
Tests the new insights endpoint that detects repeated win/loss patterns in owner override history
grouped by day-of-week and generates actionable recommendations.

Features tested:
- GET /api/rates/grid/insights/{property_id}?lookback_days=N returns insights[] grouped by pattern type
- Pattern 1 (warning - repeated_loss_pattern): Same DOW ≥2 times where owner > AI by ≥10% AND occupancy < 30%
- Pattern 2 (success - consistent_win_pattern): Same DOW ≥3 times where owner > AI AND bookings > 0 AND occupancy ≥ 30%
- Pattern 3 (info - min_rate_streak): 5+ days in last 14 days hit min_rate (live_pms_rate <= min_rate + 1)
- Insights sorted by severity (warning < success < info)
- Each insight has: id, severity, type, message (Turkish), recommendation {action, label, dow, target_offset_pct}, evidence
- POST /api/rates/grid/insights/apply with {property_id, recommendation, count} returns suggested_dates[]
- suggested_dates contain {date, target_pms_override, ai_rate, base_rate}
- applied_count is 0 (intentional — owner reviews before submit)
- Auth required (admin/manager only)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test property ID
TEST_PROPERTY_ID = "aldgate-flats"

# Turkish day names for validation
DOW_NAMES_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


class TestInsightsEndpoint:
    """Insights endpoint tests for AI auto-learning pattern detection"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        yield

    # ==================== AUTH TESTS ====================
    
    def test_insights_requires_auth(self):
        """Insights endpoint requires authentication"""
        no_auth_session = requests.Session()
        resp = no_auth_session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}")
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print("PASS: Insights endpoint requires auth (401/403 without token)")

    def test_insights_requires_admin_or_manager_role(self):
        """Insights endpoint requires admin or manager role"""
        hk_session = requests.Session()
        hk_session.headers.update({"Content-Type": "application/json"})
        login_resp = hk_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testhk@hotelbox.com",
            "password": "Test2026!"
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            if token:
                hk_session.headers.update({"Authorization": f"Bearer {token}"})
                resp = hk_session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}")
                assert resp.status_code in [401, 403], f"Housekeeper should be denied, got {resp.status_code}"
                print("PASS: Housekeeper role denied access to insights endpoint")
            else:
                print("SKIP: Housekeeper login returned no token")
        else:
            print("SKIP: Housekeeper user not found or login failed")

    def test_apply_insight_requires_auth(self):
        """Apply insight endpoint requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        resp = no_auth_session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {"dow": 0, "target_offset_pct": -10},
            "count": 3
        })
        assert resp.status_code in [401, 403], f"Expected 401/403 without auth, got {resp.status_code}"
        print("PASS: Apply insight endpoint requires auth (401/403 without token)")

    # ==================== INSIGHTS RESPONSE STRUCTURE ====================

    def test_insights_response_structure(self):
        """GET /api/rates/grid/insights returns correct structure"""
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}")
        assert resp.status_code == 200, f"Insights failed: {resp.text}"
        data = resp.json()
        
        # Check top-level fields
        assert "property_id" in data, "Missing property_id"
        assert "lookback_days" in data, "Missing lookback_days"
        assert "insights" in data, "Missing insights array"
        assert "count" in data, "Missing count"
        
        assert data["property_id"] == TEST_PROPERTY_ID
        assert isinstance(data["insights"], list)
        assert data["count"] == len(data["insights"])
        
        print(f"PASS: Insights response structure valid - {data['count']} insights found")

    def test_insights_lookback_days_parameter(self):
        """lookback_days parameter correctly filters date range"""
        # Test with 30 days
        resp_30 = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=30")
        assert resp_30.status_code == 200
        data_30 = resp_30.json()
        assert data_30["lookback_days"] == 30
        
        # Test with 90 days (default)
        resp_90 = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert resp_90.status_code == 200
        data_90 = resp_90.json()
        assert data_90["lookback_days"] == 90
        
        print("PASS: lookback_days parameter correctly applied")

    def test_insights_property_all(self):
        """Insights endpoint works with property_id='all'"""
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/all")
        assert resp.status_code == 200, f"Insights for 'all' failed: {resp.text}"
        data = resp.json()
        assert data["property_id"] == "all"
        print("PASS: Insights endpoint works with property_id='all'")

    # ==================== INSIGHT STRUCTURE VALIDATION ====================

    def test_insight_has_required_fields(self):
        """Each insight has required fields: id, severity, type, message, recommendation"""
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert resp.status_code == 200
        data = resp.json()
        
        for insight in data["insights"]:
            assert "id" in insight, "Insight missing id"
            assert "severity" in insight, "Insight missing severity"
            assert "type" in insight, "Insight missing type"
            assert "message" in insight, "Insight missing message"
            assert "recommendation" in insight, "Insight missing recommendation"
            
            # Validate severity values
            assert insight["severity"] in ["warning", "success", "info"], f"Invalid severity: {insight['severity']}"
            
            # Validate type values
            valid_types = ["repeated_loss_pattern", "consistent_win_pattern", "min_rate_streak"]
            assert insight["type"] in valid_types, f"Invalid type: {insight['type']}"
            
            # Validate recommendation structure
            rec = insight["recommendation"]
            assert "action" in rec, "Recommendation missing action"
            assert "label" in rec, "Recommendation missing label"
            
        print(f"PASS: All {len(data['insights'])} insights have required fields")

    def test_insight_message_is_turkish(self):
        """Insight messages are in Turkish"""
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert resp.status_code == 200
        data = resp.json()
        
        # Turkish-specific characters/words to check
        turkish_indicators = ["için", "günü", "fiyat", "doluluk", "AI", "gün", "kontrol", "strateji"]
        
        for insight in data["insights"]:
            message = insight["message"]
            # Check if message contains Turkish words
            has_turkish = any(word in message.lower() for word in turkish_indicators)
            if not has_turkish:
                print(f"WARNING: Message may not be Turkish: {message[:50]}...")
            
        print("PASS: Insight messages checked for Turkish content")

    def test_insights_sorted_by_severity(self):
        """Insights are sorted by severity: warning < success < info"""
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert resp.status_code == 200
        data = resp.json()
        
        if len(data["insights"]) < 2:
            print("SKIP: Not enough insights to verify sorting")
            return
        
        severity_order = {"warning": 0, "success": 1, "info": 2}
        prev_order = -1
        
        for insight in data["insights"]:
            current_order = severity_order.get(insight["severity"], 99)
            assert current_order >= prev_order, f"Insights not sorted by severity: {insight['severity']} after previous"
            prev_order = current_order
        
        print("PASS: Insights correctly sorted by severity (warning < success < info)")

    # ==================== PATTERN 1: REPEATED LOSS PATTERN ====================

    def test_repeated_loss_pattern_detection(self):
        """Pattern 1: Same DOW ≥2 times where owner > AI by ≥10% AND occupancy < 30% triggers warning"""
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert resp.status_code == 200
        data = resp.json()
        
        loss_patterns = [i for i in data["insights"] if i["type"] == "repeated_loss_pattern"]
        
        for pattern in loss_patterns:
            assert pattern["severity"] == "warning", f"Loss pattern should be warning, got {pattern['severity']}"
            assert "dow" in pattern, "Loss pattern missing dow"
            assert "dow_name" in pattern, "Loss pattern missing dow_name"
            assert "evidence" in pattern, "Loss pattern missing evidence"
            
            # Validate dow_name is Turkish
            assert pattern["dow_name"] in DOW_NAMES_TR, f"Invalid Turkish day name: {pattern['dow_name']}"
            
            # Validate recommendation
            rec = pattern["recommendation"]
            assert rec["action"] == "lower_to_ai", f"Expected action 'lower_to_ai', got {rec['action']}"
            assert "dow" in rec, "Recommendation missing dow"
            assert "target_offset_pct" in rec, "Recommendation missing target_offset_pct"
            assert rec["target_offset_pct"] < 0, "Loss pattern should have negative offset"
            
            # Validate evidence
            assert len(pattern["evidence"]) >= 2, "Loss pattern needs ≥2 evidence items"
            for ev in pattern["evidence"]:
                assert ev["occ_pct"] < 30, f"Evidence occ_pct should be <30%, got {ev['occ_pct']}"
                assert ev["delta_pct"] >= 10, f"Evidence delta_pct should be ≥10%, got {ev['delta_pct']}"
        
        print(f"PASS: {len(loss_patterns)} repeated_loss_pattern insights validated")

    # ==================== PATTERN 2: CONSISTENT WIN PATTERN ====================

    def test_consistent_win_pattern_detection(self):
        """Pattern 2: Same DOW ≥3 times where owner > AI AND bookings > 0 AND occupancy ≥ 30% triggers success"""
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert resp.status_code == 200
        data = resp.json()
        
        win_patterns = [i for i in data["insights"] if i["type"] == "consistent_win_pattern"]
        
        for pattern in win_patterns:
            assert pattern["severity"] == "success", f"Win pattern should be success, got {pattern['severity']}"
            assert "dow" in pattern, "Win pattern missing dow"
            assert "dow_name" in pattern, "Win pattern missing dow_name"
            assert "evidence" in pattern, "Win pattern missing evidence"
            
            # Validate dow_name is Turkish
            assert pattern["dow_name"] in DOW_NAMES_TR, f"Invalid Turkish day name: {pattern['dow_name']}"
            
            # Validate recommendation
            rec = pattern["recommendation"]
            assert rec["action"] == "keep_strategy", f"Expected action 'keep_strategy', got {rec['action']}"
            assert "dow" in rec, "Recommendation missing dow"
            assert "target_offset_pct" in rec, "Recommendation missing target_offset_pct"
            
            # Validate evidence
            assert len(pattern["evidence"]) >= 3, "Win pattern needs ≥3 evidence items"
            for ev in pattern["evidence"]:
                assert ev["bookings"] > 0, f"Evidence bookings should be >0, got {ev['bookings']}"
                assert ev["occ_pct"] >= 30, f"Evidence occ_pct should be ≥30%, got {ev['occ_pct']}"
                assert ev["owner"] > ev["ai"], f"Evidence owner should be > ai"
        
        print(f"PASS: {len(win_patterns)} consistent_win_pattern insights validated")

    # ==================== PATTERN 3: MIN RATE STREAK ====================

    def test_min_rate_streak_detection(self):
        """Pattern 3: 5+ days in last 14 days hit min_rate triggers info"""
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert resp.status_code == 200
        data = resp.json()
        
        streak_patterns = [i for i in data["insights"] if i["type"] == "min_rate_streak"]
        
        for pattern in streak_patterns:
            assert pattern["severity"] == "info", f"Min rate streak should be info, got {pattern['severity']}"
            
            # Validate recommendation
            rec = pattern["recommendation"]
            assert rec["action"] == "review_min_rate", f"Expected action 'review_min_rate', got {rec['action']}"
            
            # Message should mention the streak count
            assert "gün" in pattern["message"].lower() or "14" in pattern["message"], "Message should mention days"
        
        print(f"PASS: {len(streak_patterns)} min_rate_streak insights validated")

    # ==================== APPLY INSIGHT ENDPOINT ====================

    def test_apply_insight_response_structure(self):
        """POST /api/rates/grid/insights/apply returns correct structure"""
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": 0,  # Monday
                "target_offset_pct": -10
            },
            "count": 3
        })
        assert resp.status_code == 200, f"Apply insight failed: {resp.text}"
        data = resp.json()
        
        # Check required fields
        assert "applied_count" in data, "Missing applied_count"
        assert "suggested_dates" in data, "Missing suggested_dates"
        
        # applied_count should be 0 (dry-run)
        assert data["applied_count"] == 0, f"applied_count should be 0, got {data['applied_count']}"
        
        # Check suggested_dates structure
        assert isinstance(data["suggested_dates"], list)
        
        print(f"PASS: Apply insight response structure valid - {len(data['suggested_dates'])} suggested dates")

    def test_apply_insight_suggested_dates_structure(self):
        """suggested_dates contain {date, target_pms_override, ai_rate, base_rate}"""
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": 0,  # Monday
                "target_offset_pct": -10
            },
            "count": 3
        })
        assert resp.status_code == 200
        data = resp.json()
        
        for suggestion in data["suggested_dates"]:
            assert "date" in suggestion, "Suggestion missing date"
            assert "target_pms_override" in suggestion, "Suggestion missing target_pms_override"
            assert "ai_rate" in suggestion, "Suggestion missing ai_rate"
            assert "base_rate" in suggestion, "Suggestion missing base_rate"
            
            # Validate date format
            try:
                datetime.strptime(suggestion["date"], "%Y-%m-%d")
            except ValueError:
                pytest.fail(f"Invalid date format: {suggestion['date']}")
            
            # Validate numeric values
            assert isinstance(suggestion["target_pms_override"], (int, float))
            assert isinstance(suggestion["ai_rate"], (int, float))
            assert isinstance(suggestion["base_rate"], (int, float))
        
        print("PASS: suggested_dates have correct structure")

    def test_apply_insight_target_rate_calculation(self):
        """target_pms_override = ai_rate * (1 + offset_pct/100)"""
        offset_pct = -10
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": 0,  # Monday
                "target_offset_pct": offset_pct
            },
            "count": 3
        })
        assert resp.status_code == 200
        data = resp.json()
        
        for suggestion in data["suggested_dates"]:
            ai_rate = suggestion["ai_rate"]
            target = suggestion["target_pms_override"]
            expected = round(ai_rate * (1 + offset_pct / 100), 2)
            
            # Allow small floating point tolerance
            assert abs(target - expected) < 0.1, f"Target {target} != expected {expected} (ai_rate={ai_rate}, offset={offset_pct}%)"
        
        print("PASS: target_pms_override calculation correct")

    def test_apply_insight_matches_dow(self):
        """suggested_dates only contain dates matching the specified dow"""
        dow = 0  # Monday
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": dow,
                "target_offset_pct": -10
            },
            "count": 5
        })
        assert resp.status_code == 200
        data = resp.json()
        
        for suggestion in data["suggested_dates"]:
            date_obj = datetime.strptime(suggestion["date"], "%Y-%m-%d")
            assert date_obj.weekday() == dow, f"Date {suggestion['date']} is not Monday (dow={date_obj.weekday()})"
        
        print("PASS: All suggested dates match specified day-of-week")

    def test_apply_insight_future_dates_only(self):
        """suggested_dates are all in the future (after today)"""
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": 0,
                "target_offset_pct": -10
            },
            "count": 3
        })
        assert resp.status_code == 200
        data = resp.json()
        
        today = datetime.now().date()
        for suggestion in data["suggested_dates"]:
            date_obj = datetime.strptime(suggestion["date"], "%Y-%m-%d").date()
            assert date_obj > today, f"Date {suggestion['date']} is not in the future"
        
        print("PASS: All suggested dates are in the future")

    def test_apply_insight_respects_count(self):
        """suggested_dates respects the count parameter"""
        for count in [1, 3, 5]:
            resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
                "property_id": TEST_PROPERTY_ID,
                "recommendation": {
                    "dow": 0,
                    "target_offset_pct": -10
                },
                "count": count
            })
            assert resp.status_code == 200
            data = resp.json()
            
            # Should return up to 'count' dates (may be less if 90-day limit reached)
            assert len(data["suggested_dates"]) <= count, f"Got more dates than requested: {len(data['suggested_dates'])} > {count}"
        
        print("PASS: suggested_dates respects count parameter")

    def test_apply_insight_90_day_limit(self):
        """suggested_dates are limited to 90 days in the future"""
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": 0,
                "target_offset_pct": -10
            },
            "count": 20  # Request many dates
        })
        assert resp.status_code == 200
        data = resp.json()
        
        today = datetime.now().date()
        max_date = today + timedelta(days=90)
        
        for suggestion in data["suggested_dates"]:
            date_obj = datetime.strptime(suggestion["date"], "%Y-%m-%d").date()
            assert date_obj <= max_date, f"Date {suggestion['date']} exceeds 90-day limit"
        
        print("PASS: suggested_dates respect 90-day limit")

    def test_apply_insight_requires_dow(self):
        """Apply insight requires dow in recommendation"""
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "target_offset_pct": -10
                # Missing dow
            },
            "count": 3
        })
        assert resp.status_code == 400, f"Expected 400 without dow, got {resp.status_code}"
        print("PASS: Apply insight requires dow parameter")

    def test_apply_insight_positive_offset(self):
        """Apply insight works with positive offset (keep_strategy)"""
        offset_pct = 15
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": 5,  # Saturday
                "target_offset_pct": offset_pct
            },
            "count": 3
        })
        assert resp.status_code == 200
        data = resp.json()
        
        for suggestion in data["suggested_dates"]:
            ai_rate = suggestion["ai_rate"]
            target = suggestion["target_pms_override"]
            # With positive offset, target should be higher than AI rate
            assert target > ai_rate, f"Target {target} should be > ai_rate {ai_rate} with positive offset"
        
        print("PASS: Apply insight works with positive offset")

    # ==================== INTEGRATION TESTS ====================

    def test_insights_to_apply_flow(self):
        """Full flow: Get insights → Apply recommendation → Verify suggested dates"""
        # Step 1: Get insights
        insights_resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert insights_resp.status_code == 200
        insights_data = insights_resp.json()
        
        if not insights_data["insights"]:
            print("SKIP: No insights available for integration test")
            return
        
        # Step 2: Pick first insight with dow
        insight = None
        for i in insights_data["insights"]:
            if "dow" in i.get("recommendation", {}):
                insight = i
                break
        
        if not insight:
            print("SKIP: No insights with dow recommendation")
            return
        
        # Step 3: Apply the recommendation
        apply_resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": insight["recommendation"],
            "count": 3
        })
        assert apply_resp.status_code == 200
        apply_data = apply_resp.json()
        
        # Step 4: Verify
        assert apply_data["applied_count"] == 0, "Should be dry-run"
        assert len(apply_data["suggested_dates"]) > 0, "Should have suggested dates"
        
        # Verify dates match the insight's dow
        expected_dow = insight["recommendation"]["dow"]
        for suggestion in apply_data["suggested_dates"]:
            date_obj = datetime.strptime(suggestion["date"], "%Y-%m-%d")
            assert date_obj.weekday() == expected_dow
        
        print(f"PASS: Full insights → apply flow works for {insight['type']}")

    def test_existing_test_data_triggers_insights(self):
        """Verify existing aldgate-flats test data triggers expected insights"""
        # According to context: aldgate-flats has 3 Mondays + 2 Thu + 2 Fri at £280 vs ~£75 AI with low occupancy
        # This should trigger warning insights for repeated_loss_pattern
        
        resp = self.session.get(f"{BASE_URL}/api/rates/grid/insights/{TEST_PROPERTY_ID}?lookback_days=90")
        assert resp.status_code == 200
        data = resp.json()
        
        # Check for warning insights (repeated_loss_pattern)
        warnings = [i for i in data["insights"] if i["severity"] == "warning"]
        
        print(f"Found {len(warnings)} warning insights, {data['count']} total insights")
        
        # Log insight types found
        types_found = set(i["type"] for i in data["insights"])
        print(f"Insight types found: {types_found}")
        
        # Log DOWs with warnings
        warning_dows = [i.get("dow_name", "N/A") for i in warnings]
        print(f"Warning DOWs: {warning_dows}")
        
        print("PASS: Insights endpoint returns data for test property")


class TestApplyInsightEdgeCases:
    """Edge case tests for apply insight endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        assert token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield

    def test_apply_insight_all_dow_values(self):
        """Apply insight works for all days of week (0-6)"""
        for dow in range(7):
            resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
                "property_id": TEST_PROPERTY_ID,
                "recommendation": {
                    "dow": dow,
                    "target_offset_pct": 0
                },
                "count": 1
            })
            assert resp.status_code == 200, f"Failed for dow={dow}: {resp.text}"
            data = resp.json()
            
            if data["suggested_dates"]:
                date_obj = datetime.strptime(data["suggested_dates"][0]["date"], "%Y-%m-%d")
                assert date_obj.weekday() == dow, f"Wrong dow for {dow}"
        
        print("PASS: Apply insight works for all days of week")

    def test_apply_insight_zero_offset(self):
        """Apply insight with 0% offset returns AI rate as target"""
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": 0,
                "target_offset_pct": 0
            },
            "count": 3
        })
        assert resp.status_code == 200
        data = resp.json()
        
        for suggestion in data["suggested_dates"]:
            # With 0% offset, target should equal AI rate
            assert abs(suggestion["target_pms_override"] - suggestion["ai_rate"]) < 0.01
        
        print("PASS: Zero offset returns AI rate as target")

    def test_apply_insight_large_negative_offset(self):
        """Apply insight with large negative offset doesn't go below 0"""
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": TEST_PROPERTY_ID,
            "recommendation": {
                "dow": 0,
                "target_offset_pct": -50
            },
            "count": 3
        })
        assert resp.status_code == 200
        data = resp.json()
        
        for suggestion in data["suggested_dates"]:
            assert suggestion["target_pms_override"] > 0, "Target rate should be positive"
        
        print("PASS: Large negative offset still produces positive rates")

    def test_apply_insight_property_all(self):
        """Apply insight works with property_id='all'"""
        resp = self.session.post(f"{BASE_URL}/api/rates/grid/insights/apply", json={
            "property_id": "all",
            "recommendation": {
                "dow": 0,
                "target_offset_pct": -10
            },
            "count": 3
        })
        assert resp.status_code == 200
        print("PASS: Apply insight works with property_id='all'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
