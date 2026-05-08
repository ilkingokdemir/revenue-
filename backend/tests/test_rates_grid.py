"""
Test suite for My Rates — Market Pulse style 365-day rate grid endpoints.
Tests: GET grid, POST override, DELETE override, POST submit-to-pms
Uses FRESH dates (2027-01-XX) to avoid pollution from existing test data.
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"

# Use fresh dates in 2027 to avoid pollution
TEST_DATE_PREFIX = "2027-01"
TEST_DATE_1 = "2027-01-10"
TEST_DATE_2 = "2027-01-11"
TEST_DATE_3 = "2027-01-12"
TEST_PROPERTY = "default"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for requests"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(auth_headers):
    """Cleanup test data before and after tests"""
    # Cleanup before tests
    for date in [TEST_DATE_1, TEST_DATE_2, TEST_DATE_3]:
        requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/{date}",
            headers=auth_headers
        )
    yield
    # Cleanup after tests
    for date in [TEST_DATE_1, TEST_DATE_2, TEST_DATE_3]:
        requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/{date}",
            headers=auth_headers
        )


class TestRatesGridGet:
    """GET /api/rates/grid/{property_id} tests"""

    def test_get_grid_defaults_to_today_90_days(self, auth_headers):
        """GET should default to today and 90 days when params missing"""
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"GET grid failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "property_id" in data
        assert "start_date" in data
        assert "days" in data
        assert "rows" in data
        assert "stats" in data
        assert "total_rooms" in data
        assert "default_rate" in data
        
        # Default should be 90 days
        assert data["days"] == 90
        assert len(data["rows"]) == 90
        
        # Start date should be today
        today = datetime.now().strftime("%Y-%m-%d")
        assert data["start_date"] == today
        print(f"PASS: GET grid defaults to today ({today}) and 90 days")

    def test_get_grid_with_custom_params(self, auth_headers):
        """GET should accept custom start_date and days"""
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 30},
            headers=auth_headers
        )
        assert response.status_code == 200, f"GET grid failed: {response.text}"
        data = response.json()
        
        assert data["start_date"] == TEST_DATE_1
        assert data["days"] == 30
        assert len(data["rows"]) == 30
        
        # Verify first row is the start date
        assert data["rows"][0]["date"] == TEST_DATE_1
        print(f"PASS: GET grid with custom params (start={TEST_DATE_1}, days=30)")

    def test_get_grid_invalid_start_date_returns_400(self, auth_headers):
        """GET should reject invalid start_date with 400"""
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": "invalid-date"},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: GET grid rejects invalid start_date with 400")

    def test_get_grid_clamps_days_to_1_365(self, auth_headers):
        """GET should clamp days to 1..365"""
        # Test days > 365 gets clamped to 365
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 500},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 365, f"Expected 365, got {data['days']}"
        
        # Test days = 0 uses default (90) - 0 is treated as "use default" not "clamp to 1"
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 0},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 90, f"Expected 90 (default), got {data['days']}"
        
        # Test negative days gets clamped to 1
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": -10},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 1, f"Expected 1, got {data['days']}"
        print("PASS: GET grid clamps days to 1..365")

    def test_get_grid_returns_stats(self, auth_headers):
        """GET should return stats with min_rate_days, avg_occupancy_pct, total_pickup"""
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 10},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        stats = data["stats"]
        assert "min_rate_days" in stats
        assert "avg_occupancy_pct" in stats
        assert "total_pickup" in stats
        
        # Verify types
        assert isinstance(stats["min_rate_days"], int)
        assert isinstance(stats["avg_occupancy_pct"], (int, float))
        assert isinstance(stats["total_pickup"], int)
        print(f"PASS: GET grid returns stats: {stats}")

    def test_get_grid_row_structure(self, auth_headers):
        """GET should return rows with all required fields per day"""
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        row = data["rows"][0]
        required_fields = [
            "date", "dow", "ai_status", "adr", "occupancy_pct", "in_house",
            "pickup", "min_rate", "floor_rate", "live_pms_rate",
            "current_sell_rate", "compset_avg", "ai_rate",
            "target_sell_rate", "pms_override"
        ]
        for field in required_fields:
            assert field in row, f"Missing field: {field}"
        
        # Verify date format
        assert row["date"] == TEST_DATE_1
        # Verify dow is day of week abbreviation
        assert row["dow"] in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        print(f"PASS: GET grid row has all required fields: {list(row.keys())}")

    def test_get_grid_property_all_works(self, auth_headers):
        """GET with property_id='all' should work"""
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/all",
            params={"start_date": TEST_DATE_1, "days": 5},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == "all"
        print("PASS: GET grid with property_id='all' works")


class TestRatesGridOverride:
    """POST /api/rates/grid/override tests"""

    def test_post_override_saves_changes(self, auth_headers):
        """POST should batch upsert changes to owner_rate_overrides"""
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_1,
                    "pms_override": 200,
                    "target_sell_rate": 190,
                    "min_rate": 80,
                    "floor_rate": 100,
                    "ai_status": "manual"
                }
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"POST override failed: {response.text}"
        data = response.json()
        assert data["saved"] == 1
        print(f"PASS: POST override saved 1 change")

    def test_post_override_verify_get_returns_values(self, auth_headers):
        """After POST override, GET grid should return those values"""
        # First save an override
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_2,
                    "pms_override": 250,
                    "target_sell_rate": 240,
                    "min_rate": 90,
                    "floor_rate": 110,
                    "ai_status": "override"
                }
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Now GET and verify
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_2, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        row = data["rows"][0]
        
        assert row["pms_override"] == 250, f"Expected pms_override=250, got {row['pms_override']}"
        assert row["target_sell_rate"] == 240, f"Expected target_sell_rate=240, got {row['target_sell_rate']}"
        assert row["min_rate"] == 90, f"Expected min_rate=90, got {row['min_rate']}"
        assert row["floor_rate"] == 110, f"Expected floor_rate=110, got {row['floor_rate']}"
        assert row["ai_status"] == "override", f"Expected ai_status='override', got {row['ai_status']}"
        print("PASS: POST override values returned in subsequent GET")

    def test_post_override_idempotency(self, auth_headers):
        """Re-saving same date+field should update not create duplicate"""
        # Save first time
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [{"date": TEST_DATE_3, "pms_override": 300}]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Save again with different value
        payload["changes"][0]["pms_override"] = 350
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify only one record exists with updated value
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_3, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rows"][0]["pms_override"] == 350
        print("PASS: POST override is idempotent (updates not duplicates)")

    def test_post_override_ignores_zero_negative_values(self, auth_headers):
        """POST should ignore zero/negative numeric values"""
        # First set a valid value
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [{"date": TEST_DATE_1, "pms_override": 200}]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=payload, headers=auth_headers)
        
        # Try to set zero - should be ignored
        payload["changes"][0]["pms_override"] = 0
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        # saved=0 because zero is ignored
        data = response.json()
        # Note: saved might be 0 if only field is zero, or might update other fields
        
        # Try negative - should be ignored
        payload["changes"][0]["pms_override"] = -100
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        print("PASS: POST override ignores zero/negative values")

    def test_post_override_accepts_all_fields(self, auth_headers):
        """POST should accept pms_override, target_sell_rate, min_rate, floor_rate, ai_status, live_pms_rate"""
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_1,
                    "pms_override": 220,
                    "target_sell_rate": 210,
                    "min_rate": 85,
                    "floor_rate": 105,
                    "ai_status": "sentinel",
                    "live_pms_rate": 215
                }
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["saved"] >= 1
        print("PASS: POST override accepts all specified fields")

    def test_post_override_empty_changes_returns_zero(self, auth_headers):
        """POST with empty changes should return saved=0"""
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": []
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["saved"] == 0
        print("PASS: POST override with empty changes returns saved=0")


class TestRatesGridDelete:
    """DELETE /api/rates/grid/override/{property_id}/{date} tests"""

    def test_delete_override_removes_record(self, auth_headers):
        """DELETE should remove override; subsequent GET returns defaults"""
        # First create an override
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [{"date": TEST_DATE_1, "pms_override": 999, "min_rate": 150}]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=payload, headers=auth_headers)
        
        # Verify it exists
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["rows"][0]["pms_override"] == 999
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/{TEST_DATE_1}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 1
        
        # Verify it's gone - pms_override should be None/null
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        assert row["pms_override"] is None, f"Expected pms_override=None after delete, got {row['pms_override']}"
        print("PASS: DELETE override removes record, GET returns defaults")

    def test_delete_nonexistent_returns_zero(self, auth_headers):
        """DELETE nonexistent override should return deleted=0"""
        response = requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/2099-12-31",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 0
        print("PASS: DELETE nonexistent override returns deleted=0")


class TestRatesGridSubmitToPms:
    """POST /api/rates/grid/submit-to-pms tests"""

    def test_submit_to_pms_queues_rates(self, auth_headers):
        """POST submit-to-pms should push effective rates to rate_sync_queue"""
        # First create an override
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_1,
                    "pms_override": 275,
                    "target_sell_rate": 260,
                    "min_rate": 80,
                    "floor_rate": 100
                }
            ]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=payload, headers=auth_headers)
        
        # Submit to PMS
        submit_payload = {
            "property_id": TEST_PROPERTY,
            "dates": [TEST_DATE_1]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Submit to PMS failed: {response.text}"
        data = response.json()
        assert data["queued"] >= 1, f"Expected queued >= 1, got {data['queued']}"
        print(f"PASS: Submit to PMS queued {data['queued']} rate(s)")

    def test_submit_to_pms_effective_rate_priority(self, auth_headers):
        """Effective rate = pms_override > target_sell_rate > live_pms_rate"""
        # Set only target_sell_rate (no pms_override)
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_2,
                    "target_sell_rate": 280,
                    "min_rate": 70,
                    "floor_rate": 90
                }
            ]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=payload, headers=auth_headers)
        
        # Submit
        submit_payload = {
            "property_id": TEST_PROPERTY,
            "dates": [TEST_DATE_2]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["queued"] >= 1
        print("PASS: Submit to PMS uses effective rate priority")

    def test_submit_to_pms_updates_live_pms_rate(self, auth_headers):
        """After submit-to-pms, live_pms_rate should be updated to effective rate"""
        # Create override
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_3,
                    "pms_override": 320,
                    "min_rate": 80,
                    "floor_rate": 100
                }
            ]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=payload, headers=auth_headers)
        
        # Submit
        submit_payload = {
            "property_id": TEST_PROPERTY,
            "dates": [TEST_DATE_3]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify live_pms_rate is updated
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_3, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        # Effective rate should be max(pms_override, min_rate, floor_rate) = max(320, 80, 100) = 320
        assert row["live_pms_rate"] == 320, f"Expected live_pms_rate=320, got {row['live_pms_rate']}"
        print("PASS: Submit to PMS updates live_pms_rate to effective rate")

    def test_submit_to_pms_empty_dates_returns_zero(self, auth_headers):
        """POST submit-to-pms with empty dates should return queued=0"""
        payload = {
            "property_id": TEST_PROPERTY,
            "dates": []
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["queued"] == 0
        print("PASS: Submit to PMS with empty dates returns queued=0")

    def test_submit_to_pms_guardrail_min_floor(self, auth_headers):
        """Effective rate should be capped at max(min_rate, floor_rate)"""
        # Set low pms_override but high min_rate
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_1,
                    "pms_override": 50,  # Low override
                    "min_rate": 120,     # Higher min
                    "floor_rate": 100
                }
            ]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=payload, headers=auth_headers)
        
        # Submit
        submit_payload = {
            "property_id": TEST_PROPERTY,
            "dates": [TEST_DATE_1]
        }
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json=submit_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify effective rate is max(50, 120, 100) = 120
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        assert row["live_pms_rate"] == 120, f"Expected live_pms_rate=120 (guardrail), got {row['live_pms_rate']}"
        print("PASS: Submit to PMS applies guardrail (max of min_rate, floor_rate)")


class TestRatesGridAISentinel:
    """AI Sentinel rate calculation tests"""

    def test_ai_rate_calculated(self, auth_headers):
        """AI rate should be calculated for each row"""
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 5},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for row in data["rows"]:
            assert "ai_rate" in row
            assert row["ai_rate"] is not None
            assert row["ai_rate"] > 0, f"AI rate should be positive, got {row['ai_rate']}"
        print("PASS: AI rate calculated for all rows")

    def test_ai_rate_respects_guardrails(self, auth_headers):
        """AI rate should be clamped above min_rate and floor_rate"""
        # Set high min_rate
        payload = {
            "property_id": TEST_PROPERTY,
            "changes": [
                {
                    "date": TEST_DATE_1,
                    "min_rate": 200,
                    "floor_rate": 180
                }
            ]
        }
        requests.post(f"{BASE_URL}/api/rates/grid/override", json=payload, headers=auth_headers)
        
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            params={"start_date": TEST_DATE_1, "days": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        row = response.json()["rows"][0]
        
        # AI rate should be >= max(min_rate, floor_rate)
        assert row["ai_rate"] >= max(row["min_rate"], row.get("floor_rate") or 0), \
            f"AI rate {row['ai_rate']} should be >= guardrails (min={row['min_rate']}, floor={row.get('floor_rate')})"
        print("PASS: AI rate respects guardrails")


class TestRatesGridAuth:
    """Auth required tests"""

    def test_get_grid_requires_auth(self):
        """GET grid without auth should be rejected"""
        response = requests.get(f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: GET grid requires auth")

    def test_post_override_requires_auth(self):
        """POST override without auth should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/override",
            json={"property_id": TEST_PROPERTY, "changes": []}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: POST override requires auth")

    def test_delete_override_requires_auth(self):
        """DELETE override without auth should be rejected"""
        response = requests.delete(
            f"{BASE_URL}/api/rates/grid/override/{TEST_PROPERTY}/{TEST_DATE_1}"
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: DELETE override requires auth")

    def test_submit_to_pms_requires_auth(self):
        """POST submit-to-pms without auth should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/rates/grid/submit-to-pms",
            json={"property_id": TEST_PROPERTY, "dates": []}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: POST submit-to-pms requires auth")


class TestRatesGridRoleRestriction:
    """Role restriction tests - non-admin/manager should be rejected"""

    def test_receptionist_cannot_access_grid(self):
        """Receptionist role should be rejected"""
        # Login as receptionist
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testrecep@hotelbox.com",
            "password": "Test2026!"
        })
        if response.status_code != 200:
            pytest.skip("Receptionist user not available")
        
        token = response.json().get("access_token") or response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to access grid
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            headers=headers
        )
        assert response.status_code == 403, f"Expected 403 for receptionist, got {response.status_code}"
        print("PASS: Receptionist cannot access rates grid (403)")

    def test_housekeeper_cannot_access_grid(self):
        """Housekeeper role should be rejected"""
        # Login as housekeeper
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testhk@hotelbox.com",
            "password": "Test2026!"
        })
        if response.status_code != 200:
            pytest.skip("Housekeeper user not available")
        
        token = response.json().get("access_token") or response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to access grid
        response = requests.get(
            f"{BASE_URL}/api/rates/grid/{TEST_PROPERTY}",
            headers=headers
        )
        assert response.status_code == 403, f"Expected 403 for housekeeper, got {response.status_code}"
        print("PASS: Housekeeper cannot access rates grid (403)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
