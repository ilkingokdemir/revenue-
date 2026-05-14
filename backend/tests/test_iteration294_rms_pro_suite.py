"""
Iteration 294 - RMS Pro Suite Tests
Testing 6 new RMS Pro features for competitor parity (Flyr, RoomPriceGenie, Duetto, BEONx, IDeaS, Atomize, Lighthouse):

1. RevPAG (Revenue per Available Guest) - BEONx unique metric
2. Quality Score Pricing - review/location/amenities → rate uplift
3. Forecast Accuracy KPI - Cloudbeds 95% benchmark
4. Group Pricing Optimizer (displacement analysis) - IDeaS/Flyr core
5. Autopilot Mode toggle + config
6. Autopilot History

Endpoints tested:
- GET /api/rms-pro/revpag/{property_id}?days=30
- GET /api/rms-pro/quality-score/{property_id}
- GET /api/rms-pro/forecast-accuracy/{property_id}?days=90
- POST /api/rms-pro/group-pricing-quote
- GET /api/rms-pro/autopilot/config
- POST /api/rms-pro/autopilot/config
- GET /api/rms-pro/autopilot/history

RBAC: All endpoints require admin/manager role - receptionist gets 403
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"

# Test property
TEST_PROPERTY_ID = "aldgate-flats"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def receptionist_token():
    """Get receptionist authentication token for RBAC tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": RECEPTIONIST_EMAIL, "password": RECEPTIONIST_PASSWORD}
    )
    assert response.status_code == 200, f"Receptionist login failed: {response.text}"
    data = response.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Admin auth headers"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def receptionist_headers(receptionist_token):
    """Receptionist auth headers for RBAC tests"""
    return {"Authorization": f"Bearer {receptionist_token}", "Content-Type": "application/json"}


# ==================== REVPAG TESTS ====================

class TestRevPAG:
    """RevPAG (Revenue per Available Guest) - BEONx unique metric"""

    def test_revpag_default_30_days(self, admin_headers):
        """GET /api/rms-pro/revpag/{property_id} - default 30 days"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/revpag/{TEST_PROPERTY_ID}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"RevPAG failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "property_id" in data
        assert data["property_id"] == TEST_PROPERTY_ID
        assert "revpag" in data
        assert "revpar" in data
        assert "adr" in data
        assert "occupancy_pct" in data
        assert "avg_party_size" in data
        assert "total_revenue" in data
        assert "total_guest_nights" in data
        assert "total_room_nights" in data
        assert "available_room_nights" in data
        assert "days" in data
        
        # Validate data types
        assert isinstance(data["revpag"], (int, float))
        assert isinstance(data["revpar"], (int, float))
        assert isinstance(data["adr"], (int, float))
        assert isinstance(data["occupancy_pct"], (int, float))
        print(f"✓ RevPAG: £{data['revpag']}, RevPAR: £{data['revpar']}, ADR: £{data['adr']}, Occ: {data['occupancy_pct']}%")

    def test_revpag_custom_days(self, admin_headers):
        """GET /api/rms-pro/revpag/{property_id}?days=90 - custom period"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/revpag/{TEST_PROPERTY_ID}?days=90",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 90
        print(f"✓ RevPAG 90 days: £{data['revpag']}")

    def test_revpag_min_days_clamped(self, admin_headers):
        """GET /api/rms-pro/revpag/{property_id}?days=1 - should clamp to min 7"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/revpag/{TEST_PROPERTY_ID}?days=1",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["days"] >= 7, "Days should be clamped to minimum 7"
        print(f"✓ RevPAG min days clamped to: {data['days']}")


# ==================== QUALITY SCORE TESTS ====================

class TestQualityScore:
    """Quality Score Pricing - BEONx 21+ factors style"""

    def test_quality_score_basic(self, admin_headers):
        """GET /api/rms-pro/quality-score/{property_id}"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/quality-score/{TEST_PROPERTY_ID}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Quality Score failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "property_id" in data
        assert data["property_id"] == TEST_PROPERTY_ID
        assert "quality_score" in data
        assert "recommended_rate_uplift_pct" in data
        assert "factors" in data
        
        # Validate quality_score is 0-100
        assert 0 <= data["quality_score"] <= 100, f"Quality score {data['quality_score']} out of range"
        
        # Validate factors array
        assert isinstance(data["factors"], list)
        assert len(data["factors"]) == 5, "Should have 5 quality factors"
        
        # Validate each factor structure
        factor_names = []
        for f in data["factors"]:
            assert "name" in f
            assert "value" in f
            assert "uplift_pct" in f
            assert "reason" in f
            factor_names.append(f["name"])
        
        # Check expected factor names
        expected_factors = ["Review Score", "Amenities", "Photo Quality", "Response Speed", "Cleaning Quality"]
        for ef in expected_factors:
            assert ef in factor_names, f"Missing factor: {ef}"
        
        print(f"✓ Quality Score: {data['quality_score']}/100, Uplift: {data['recommended_rate_uplift_pct']}%")
        for f in data["factors"]:
            print(f"  - {f['name']}: {f['value']} → {f['uplift_pct']}%")

    def test_quality_score_nonexistent_property(self, admin_headers):
        """GET /api/rms-pro/quality-score/{property_id} - 404 for non-existent"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/quality-score/nonexistent-property-xyz",
            headers=admin_headers
        )
        assert response.status_code == 404
        print("✓ Quality Score returns 404 for non-existent property")


# ==================== FORECAST ACCURACY TESTS ====================

class TestForecastAccuracy:
    """Forecast Accuracy KPI - Cloudbeds 95% benchmark"""

    def test_forecast_accuracy_default(self, admin_headers):
        """GET /api/rms-pro/forecast-accuracy/{property_id} - default 90 days"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/forecast-accuracy/{TEST_PROPERTY_ID}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Forecast Accuracy failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "property_id" in data
        assert data["property_id"] == TEST_PROPERTY_ID
        assert "days" in data
        assert "source" in data
        assert "samples" in data
        assert "scored_samples" in data
        assert "occupancy_accuracy_pct" in data
        assert "revenue_accuracy_pct" in data
        assert "benchmark_industry" in data
        
        # Validate benchmark
        assert data["benchmark_industry"] == 95.0, "Industry benchmark should be 95%"
        
        # If snapshots exist, validate accuracy values
        if data["source"] == "snapshots" and data["samples"] > 0:
            if data["occupancy_accuracy_pct"] is not None:
                assert 0 <= data["occupancy_accuracy_pct"] <= 100
            if data["revenue_accuracy_pct"] is not None:
                assert 0 <= data["revenue_accuracy_pct"] <= 100
        
        print(f"✓ Forecast Accuracy: Occ {data['occupancy_accuracy_pct']}%, Rev {data['revenue_accuracy_pct']}%")
        print(f"  Source: {data['source']}, Samples: {data['samples']}, Scored: {data['scored_samples']}")

    def test_forecast_accuracy_custom_days(self, admin_headers):
        """GET /api/rms-pro/forecast-accuracy/{property_id}?days=180"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/forecast-accuracy/{TEST_PROPERTY_ID}?days=180",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 180
        print(f"✓ Forecast Accuracy 180 days: {data['samples']} samples")


# ==================== GROUP PRICING OPTIMIZER TESTS ====================

class TestGroupPricingOptimizer:
    """Group Pricing Optimizer - IDeaS/Flyr displacement analysis"""

    def test_group_pricing_quote_negotiate(self, admin_headers):
        """POST /api/rms-pro/group-pricing-quote - no requested rate → NEGOTIATE"""
        # Future dates for group booking
        check_in = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=17)).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/group-pricing-quote",
            headers=admin_headers,
            json={
                "property_id": TEST_PROPERTY_ID,
                "check_in": check_in,
                "check_out": check_out,
                "rooms_requested": 5
            }
        )
        assert response.status_code == 200, f"Group Pricing failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "property_id" in data
        assert data["property_id"] == TEST_PROPERTY_ID
        assert "check_in" in data
        assert "check_out" in data
        assert "nights" in data
        assert data["nights"] == 3
        assert "rooms_requested" in data
        assert data["rooms_requested"] == 5
        assert "total_room_nights" in data
        assert data["total_room_nights"] == 15  # 5 rooms × 3 nights
        assert "total_displacement_cost" in data
        assert "recommended_rate_per_night" in data
        assert "recommended_total" in data
        assert "decision" in data
        assert "decision_reason" in data
        assert "per_day" in data
        
        # Without requested_rate, decision should be NEGOTIATE
        assert data["decision"] == "NEGOTIATE"
        assert data["requested_rate"] is None
        
        # Validate per_day array
        assert len(data["per_day"]) == 3
        for day in data["per_day"]:
            assert "date" in day
            assert "available" in day
            assert "current_rate" in day
            assert "displaced_units" in day
            assert "displacement_cost" in day
        
        print(f"✓ Group Pricing NEGOTIATE: Recommended £{data['recommended_rate_per_night']}/night")
        print(f"  Total: £{data['recommended_total']}, Displacement: £{data['total_displacement_cost']}")

    def test_group_pricing_quote_accept(self, admin_headers):
        """POST /api/rms-pro/group-pricing-quote - high rate → ACCEPT"""
        check_in = (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=23)).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/group-pricing-quote",
            headers=admin_headers,
            json={
                "property_id": TEST_PROPERTY_ID,
                "check_in": check_in,
                "check_out": check_out,
                "rooms_requested": 3,
                "requested_rate": 500  # Very high rate should be accepted
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # High rate should result in ACCEPT
        assert data["decision"] == "ACCEPT"
        assert data["requested_rate"] == 500
        print(f"✓ Group Pricing ACCEPT: £500 >= recommended £{data['recommended_rate_per_night']}")

    def test_group_pricing_quote_decline(self, admin_headers):
        """POST /api/rms-pro/group-pricing-quote - low rate → DECLINE"""
        check_in = (datetime.now() + timedelta(days=28)).strftime("%Y-%m-%d")
        check_out = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/group-pricing-quote",
            headers=admin_headers,
            json={
                "property_id": TEST_PROPERTY_ID,
                "check_in": check_in,
                "check_out": check_out,
                "rooms_requested": 5,
                "requested_rate": 1  # Very low rate should be declined
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Very low rate should result in DECLINE
        assert data["decision"] == "DECLINE"
        assert data["requested_rate"] == 1
        print(f"✓ Group Pricing DECLINE: £1 < recommended £{data['recommended_rate_per_night']}")

    def test_group_pricing_quote_missing_fields(self, admin_headers):
        """POST /api/rms-pro/group-pricing-quote - missing required fields → 400"""
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/group-pricing-quote",
            headers=admin_headers,
            json={"property_id": TEST_PROPERTY_ID}  # Missing check_in, check_out
        )
        assert response.status_code == 400
        print("✓ Group Pricing returns 400 for missing required fields")

    def test_group_pricing_quote_invalid_dates(self, admin_headers):
        """POST /api/rms-pro/group-pricing-quote - invalid date format → 400"""
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/group-pricing-quote",
            headers=admin_headers,
            json={
                "property_id": TEST_PROPERTY_ID,
                "check_in": "invalid-date",
                "check_out": "also-invalid",
                "rooms_requested": 3
            }
        )
        assert response.status_code == 400
        print("✓ Group Pricing returns 400 for invalid date format")


# ==================== AUTOPILOT CONFIG TESTS ====================

class TestAutopilotConfig:
    """Autopilot Mode - Atomize/Flyr fire-and-forget"""

    def test_autopilot_get_config(self, admin_headers):
        """GET /api/rms-pro/autopilot/config"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/autopilot/config",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Autopilot config GET failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "enabled" in data
        assert "schedule_hour_utc" in data
        assert "min_gap_pct" in data
        assert "days_ahead" in data
        assert "min_uplift_to_apply_pct" in data
        
        # Validate data types
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["schedule_hour_utc"], int)
        assert 0 <= data["schedule_hour_utc"] <= 23
        assert isinstance(data["min_gap_pct"], (int, float))
        assert isinstance(data["days_ahead"], int)
        assert isinstance(data["min_uplift_to_apply_pct"], (int, float))
        
        print(f"✓ Autopilot Config: enabled={data['enabled']}, hour={data['schedule_hour_utc']}:00 UTC")
        print(f"  min_gap={data['min_gap_pct']}%, days_ahead={data['days_ahead']}, min_uplift={data['min_uplift_to_apply_pct']}%")

    def test_autopilot_set_config_enable(self, admin_headers):
        """POST /api/rms-pro/autopilot/config - enable autopilot"""
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/autopilot/config",
            headers=admin_headers,
            json={
                "enabled": True,
                "schedule_hour_utc": 3,
                "min_gap_pct": 5.0,
                "days_ahead": 14,
                "min_uplift_to_apply_pct": 3.0
            }
        )
        assert response.status_code == 200, f"Autopilot config POST failed: {response.text}"
        data = response.json()
        
        assert data["ok"] is True
        assert "config" in data
        assert data["config"]["enabled"] is True
        assert data["config"]["schedule_hour_utc"] == 3
        assert data["config"]["min_gap_pct"] == 5.0
        assert data["config"]["days_ahead"] == 14
        assert data["config"]["min_uplift_to_apply_pct"] == 3.0
        print("✓ Autopilot enabled successfully")

    def test_autopilot_set_config_disable(self, admin_headers):
        """POST /api/rms-pro/autopilot/config - disable autopilot"""
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/autopilot/config",
            headers=admin_headers,
            json={"enabled": False}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["config"]["enabled"] is False
        print("✓ Autopilot disabled successfully")

    def test_autopilot_config_idempotent(self, admin_headers):
        """POST /api/rms-pro/autopilot/config - idempotent update"""
        config = {
            "enabled": True,
            "schedule_hour_utc": 4,
            "min_gap_pct": 7.5,
            "days_ahead": 21,
            "min_uplift_to_apply_pct": 5.0
        }
        
        # First update
        r1 = requests.post(f"{BASE_URL}/api/rms-pro/autopilot/config", headers=admin_headers, json=config)
        assert r1.status_code == 200
        
        # Second update with same values (idempotent)
        r2 = requests.post(f"{BASE_URL}/api/rms-pro/autopilot/config", headers=admin_headers, json=config)
        assert r2.status_code == 200
        
        # Verify values match
        assert r1.json()["config"]["schedule_hour_utc"] == r2.json()["config"]["schedule_hour_utc"]
        print("✓ Autopilot config is idempotent")

    def test_autopilot_config_clamps_values(self, admin_headers):
        """POST /api/rms-pro/autopilot/config - clamps out-of-range values"""
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/autopilot/config",
            headers=admin_headers,
            json={
                "enabled": False,
                "schedule_hour_utc": 99,  # Should clamp to 23
                "days_ahead": 1  # Should clamp to 7
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["config"]["schedule_hour_utc"] <= 23, "Hour should be clamped to max 23"
        assert data["config"]["days_ahead"] >= 7, "Days ahead should be clamped to min 7"
        print(f"✓ Autopilot config clamps values: hour={data['config']['schedule_hour_utc']}, days={data['config']['days_ahead']}")


# ==================== AUTOPILOT HISTORY TESTS ====================

class TestAutopilotHistory:
    """Autopilot History - past runs"""

    def test_autopilot_history_default(self, admin_headers):
        """GET /api/rms-pro/autopilot/history"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/autopilot/history",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Autopilot history failed: {response.text}"
        data = response.json()
        
        assert "items" in data
        assert isinstance(data["items"], list)
        
        # If there are history items, validate structure
        if len(data["items"]) > 0:
            item = data["items"][0]
            # Expected fields based on autopilot_loop implementation
            assert "run_at" in item or "id" in item
        
        print(f"✓ Autopilot History: {len(data['items'])} runs")

    def test_autopilot_history_with_limit(self, admin_headers):
        """GET /api/rms-pro/autopilot/history?limit=5"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/autopilot/history?limit=5",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) <= 5
        print(f"✓ Autopilot History with limit: {len(data['items'])} items (max 5)")


# ==================== RBAC TESTS ====================

class TestRBACReceptionist403:
    """RBAC: All RMS Pro endpoints should return 403 for receptionist"""

    def test_rbac_revpag_403(self, receptionist_headers):
        """GET /api/rms-pro/revpag/{property_id} - receptionist gets 403"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/revpag/{TEST_PROPERTY_ID}",
            headers=receptionist_headers
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ RBAC: RevPAG returns 403 for receptionist")

    def test_rbac_quality_score_403(self, receptionist_headers):
        """GET /api/rms-pro/quality-score/{property_id} - receptionist gets 403"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/quality-score/{TEST_PROPERTY_ID}",
            headers=receptionist_headers
        )
        assert response.status_code == 403
        print("✓ RBAC: Quality Score returns 403 for receptionist")

    def test_rbac_forecast_accuracy_403(self, receptionist_headers):
        """GET /api/rms-pro/forecast-accuracy/{property_id} - receptionist gets 403"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/forecast-accuracy/{TEST_PROPERTY_ID}",
            headers=receptionist_headers
        )
        assert response.status_code == 403
        print("✓ RBAC: Forecast Accuracy returns 403 for receptionist")

    def test_rbac_group_pricing_403(self, receptionist_headers):
        """POST /api/rms-pro/group-pricing-quote - receptionist gets 403"""
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/group-pricing-quote",
            headers=receptionist_headers,
            json={
                "property_id": TEST_PROPERTY_ID,
                "check_in": "2026-02-01",
                "check_out": "2026-02-03",
                "rooms_requested": 3
            }
        )
        assert response.status_code == 403
        print("✓ RBAC: Group Pricing returns 403 for receptionist")

    def test_rbac_autopilot_config_get_403(self, receptionist_headers):
        """GET /api/rms-pro/autopilot/config - receptionist gets 403"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/autopilot/config",
            headers=receptionist_headers
        )
        assert response.status_code == 403
        print("✓ RBAC: Autopilot Config GET returns 403 for receptionist")

    def test_rbac_autopilot_config_post_403(self, receptionist_headers):
        """POST /api/rms-pro/autopilot/config - receptionist gets 403"""
        response = requests.post(
            f"{BASE_URL}/api/rms-pro/autopilot/config",
            headers=receptionist_headers,
            json={"enabled": True}
        )
        assert response.status_code == 403
        print("✓ RBAC: Autopilot Config POST returns 403 for receptionist")

    def test_rbac_autopilot_history_403(self, receptionist_headers):
        """GET /api/rms-pro/autopilot/history - receptionist gets 403"""
        response = requests.get(
            f"{BASE_URL}/api/rms-pro/autopilot/history",
            headers=receptionist_headers
        )
        assert response.status_code == 403
        print("✓ RBAC: Autopilot History returns 403 for receptionist")


# ==================== EXISTING ENDPOINT REGRESSION TESTS ====================

class TestExistingEndpointRegression:
    """Verify existing Market Robot endpoints still work after RMS Pro addition"""

    def test_competitor_pulse_still_works(self, admin_headers):
        """GET /api/revenue/market-robot/{pid}/competitor-pulse - regression"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/{TEST_PROPERTY_ID}/competitor-pulse?days=14",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Competitor Pulse regression: {response.text}"
        print("✓ Regression: competitor-pulse still works")

    def test_fleet_pulse_still_works(self, admin_headers):
        """GET /api/revenue/market-robot/fleet-pulse - regression"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/fleet-pulse?days=14",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Fleet Pulse regression: {response.text}"
        print("✓ Regression: fleet-pulse still works")

    def test_close_gap_still_works(self, admin_headers):
        """POST /api/revenue/market-robot/{pid}/close-gap - regression"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/{TEST_PROPERTY_ID}/close-gap",
            headers=admin_headers,
            json={"strategy": "half", "days": 14, "dry_run": True}
        )
        assert response.status_code == 200, f"Close Gap regression: {response.text}"
        print("✓ Regression: close-gap still works")

    def test_ai_fleet_optimize_still_works(self, admin_headers):
        """POST /api/revenue/market-robot/ai-fleet-optimize - regression"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/ai-fleet-optimize",
            headers=admin_headers,
            json={"days": 14, "dry_run": True}
        )
        assert response.status_code == 200, f"AI Fleet Optimize regression: {response.text}"
        print("✓ Regression: ai-fleet-optimize still works")

    def test_gap_history_still_works(self, admin_headers):
        """GET /api/revenue/market-robot/gap-history - regression"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history?limit=5",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Gap History regression: {response.text}"
        print("✓ Regression: gap-history still works")

    def test_gap_history_performance_404_for_nonexistent(self, admin_headers):
        """GET /api/revenue/market-robot/gap-history/{id}/performance - 404 for non-existent"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/gap-history/nonexistent-batch-id/performance",
            headers=admin_headers
        )
        assert response.status_code == 404
        print("✓ Regression: gap-history/{id}/performance returns 404 for non-existent")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
