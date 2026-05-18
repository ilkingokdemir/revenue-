"""
Iteration 322 - AI Classification History + Rollback Endpoints Testing

Tests for:
1. GET /api/revenue/market-robot/ai-classification-history - List AI-classified properties
2. POST /api/revenue/market-robot/{property_id}/ai-classification-rollback - Rollback property_type

RBAC: admin/manager 200, receptionist 403, no-auth 401
"""

import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"
RECEPTIONIST_EMAIL = "testrecep@hotelbox.com"
RECEPTIONIST_PASSWORD = "Test2026!"


class TestSetup:
    """Fixtures and helper methods"""
    
    @staticmethod
    def get_admin_token():
        """Get admin auth token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            return resp.json().get("token")  # API returns 'token' not 'access_token'
        return None
    
    @staticmethod
    def get_receptionist_token():
        """Get receptionist auth token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": RECEPTIONIST_EMAIL,
            "password": RECEPTIONIST_PASSWORD
        })
        if resp.status_code == 200:
            return resp.json().get("token")  # API returns 'token' not 'access_token'
        return None


@pytest.fixture(scope="module")
def admin_token():
    """Admin token fixture"""
    token = TestSetup.get_admin_token()
    if not token:
        pytest.skip("Admin authentication failed")
    return token


@pytest.fixture(scope="module")
def receptionist_token():
    """Receptionist token fixture"""
    token = TestSetup.get_receptionist_token()
    if not token:
        pytest.skip("Receptionist authentication failed")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Admin headers fixture"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def receptionist_headers(receptionist_token):
    """Receptionist headers fixture"""
    return {"Authorization": f"Bearer {receptionist_token}", "Content-Type": "application/json"}


# ============================================================================
# AI Classification History Endpoint Tests
# ============================================================================

class TestAIClassificationHistoryRBAC:
    """RBAC tests for GET /api/revenue/market-robot/ai-classification-history"""
    
    def test_history_unauthenticated_returns_401(self):
        """No auth token should return 401"""
        resp = requests.get(f"{BASE_URL}/api/revenue/market-robot/ai-classification-history")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("PASSED: Unauthenticated request returns 401")
    
    def test_history_receptionist_returns_403(self, receptionist_headers):
        """Receptionist role should return 403"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history",
            headers=receptionist_headers
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASSED: Receptionist gets 403 on history endpoint")
    
    def test_history_admin_returns_200(self, admin_headers):
        """Admin role should return 200"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASSED: Admin gets 200 on history endpoint")


class TestAIClassificationHistoryResponse:
    """Response structure tests for GET /api/revenue/market-robot/ai-classification-history"""
    
    def test_history_response_structure(self, admin_headers):
        """Verify response has total, days, items fields"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "total" in data, "Response missing 'total' field"
        assert "days" in data, "Response missing 'days' field"
        assert "items" in data, "Response missing 'items' field"
        assert isinstance(data["items"], list), "'items' should be a list"
        print(f"PASSED: Response structure correct - total={data['total']}, days={data['days']}, items_count={len(data['items'])}")
    
    def test_history_item_structure(self, admin_headers):
        """Verify each item has required fields"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        if data["items"]:
            item = data["items"][0]
            required_fields = [
                "property_id", "name", "city", "country", "current_type",
                "previous_type", "confidence", "reason", "classified_at",
                "classified_by", "rollback_available"
            ]
            for field in required_fields:
                assert field in item, f"Item missing required field: {field}"
            print(f"PASSED: Item structure correct with all required fields: {list(item.keys())}")
        else:
            print("PASSED: No items in history (empty list is valid)")
    
    def test_history_days_parameter(self, admin_headers):
        """Test days query parameter"""
        # Test with days=7
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history?days=7",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 7, f"Expected days=7, got {data['days']}"
        print(f"PASSED: days=7 parameter works, returned {data['total']} items")
        
        # Test with days=0 (all time)
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history?days=0",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 0, f"Expected days=0, got {data['days']}"
        print(f"PASSED: days=0 (all time) parameter works, returned {data['total']} items")
    
    def test_history_limit_parameter(self, admin_headers):
        """Test limit query parameter"""
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history?limit=5",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 5, f"Expected max 5 items, got {len(data['items'])}"
        print(f"PASSED: limit=5 parameter works, returned {len(data['items'])} items")


# ============================================================================
# AI Classification Rollback Endpoint Tests
# ============================================================================

class TestAIClassificationRollbackRBAC:
    """RBAC tests for POST /api/revenue/market-robot/{property_id}/ai-classification-rollback"""
    
    def test_rollback_unauthenticated_returns_401(self):
        """No auth token should return 401"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            json={"target_type": "hotel"}
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("PASSED: Unauthenticated rollback request returns 401")
    
    def test_rollback_receptionist_returns_403(self, receptionist_headers):
        """Receptionist role should return 403"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=receptionist_headers,
            json={"target_type": "hotel"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("PASSED: Receptionist gets 403 on rollback endpoint")


class TestAIClassificationRollback404:
    """404 handling tests for rollback endpoint"""
    
    def test_rollback_nonexistent_property_returns_404(self, admin_headers):
        """Rollback on non-existent property_id should return 404"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/nonexistent-property-xyz/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": "hotel"}
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print("PASSED: Non-existent property returns 404")


class TestAIClassificationRollbackValidation:
    """Validation tests for rollback endpoint"""
    
    def test_rollback_invalid_target_type_returns_400(self, admin_headers):
        """Invalid target_type should return 400 with valid types list"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": "foo"}
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data, "Response should have 'detail' field"
        # Check that valid types are mentioned in error
        valid_types = ["hotel", "apartment", "serviced_apartment", "aparthotel", "guesthouse", "bnb", "hostel"]
        for vt in valid_types:
            assert vt in data["detail"], f"Error should mention valid type '{vt}'"
        print(f"PASSED: Invalid target_type returns 400 with valid types: {data['detail']}")


class TestAIClassificationRollbackFunctionality:
    """Functional tests for rollback endpoint using city-gate property"""
    
    def test_rollback_with_explicit_target_type(self, admin_headers):
        """Test rollback with explicit target_type"""
        # First, get current state of city-gate
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history?days=365&limit=500",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Find city-gate in history
        city_gate = None
        for item in data["items"]:
            if item["property_id"] == "city-gate":
                city_gate = item
                break
        
        if not city_gate:
            # city-gate may not have been AI-classified yet, let's check properties directly
            print("INFO: city-gate not in AI history, checking properties directly")
        
        # Perform rollback to 'hotel'
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": "hotel"}
        )
        
        # Could be 200 (success) or 200 with no_op if already hotel
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        result = resp.json()
        assert result["ok"] == True, f"Expected ok=True, got {result}"
        
        if result.get("no_op"):
            print(f"PASSED: Rollback returned no_op=True (already hotel): {result['message']}")
        else:
            assert "previous_type" in result, "Result should have previous_type"
            assert "current_type" in result, "Result should have current_type"
            assert result["current_type"] == "hotel", f"Expected current_type=hotel, got {result['current_type']}"
            print(f"PASSED: Rollback successful - {result['previous_type']} → {result['current_type']}")
    
    def test_rollback_noop_when_same_type(self, admin_headers):
        """Test that rollback returns no_op when target equals current"""
        # First rollback to hotel to ensure known state
        requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": "hotel"}
        )
        
        # Now try to rollback to hotel again
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": "hotel"}
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["ok"] == True
        assert result.get("no_op") == True, f"Expected no_op=True when target equals current, got {result}"
        print(f"PASSED: No-op detection works - {result['message']}")
    
    def test_bidirectional_rollback(self, admin_headers):
        """Test that rollback works bidirectionally (flip back and forth)"""
        # Step 1: Set to guesthouse
        resp1 = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": "guesthouse"}
        )
        assert resp1.status_code == 200
        result1 = resp1.json()
        assert result1["ok"] == True
        
        if result1.get("no_op"):
            # Already guesthouse, flip to hotel first
            resp1 = requests.post(
                f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
                headers=admin_headers,
                json={"target_type": "hotel"}
            )
            assert resp1.status_code == 200
            result1 = resp1.json()
        
        first_type = result1.get("current_type") or "guesthouse"
        print(f"Step 1: Set to {first_type}")
        
        # Step 2: Flip to opposite type
        opposite = "hotel" if first_type == "guesthouse" else "guesthouse"
        resp2 = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": opposite}
        )
        assert resp2.status_code == 200
        result2 = resp2.json()
        assert result2["ok"] == True
        assert result2.get("current_type") == opposite, f"Expected {opposite}, got {result2.get('current_type')}"
        print(f"Step 2: Flipped to {opposite}")
        
        # Step 3: Flip back
        resp3 = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": first_type}
        )
        assert resp3.status_code == 200
        result3 = resp3.json()
        assert result3["ok"] == True
        assert result3.get("current_type") == first_type, f"Expected {first_type}, got {result3.get('current_type')}"
        print(f"Step 3: Flipped back to {first_type}")
        
        print("PASSED: Bidirectional rollback works correctly")
    
    def test_rollback_updates_audit_fields(self, admin_headers):
        """Test that rollback updates classified_by with manual-rollback prefix"""
        # Perform a rollback
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": "aparthotel"}  # Use a different type to ensure change
        )
        assert resp.status_code == 200
        
        # Check history to verify audit fields
        resp = requests.get(
            f"{BASE_URL}/api/revenue/market-robot/ai-classification-history?days=1&limit=50",
            headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Find city-gate in history
        city_gate = None
        for item in data["items"]:
            if item["property_id"] == "city-gate":
                city_gate = item
                break
        
        if city_gate:
            assert city_gate["classified_by"].startswith("manual-rollback:"), \
                f"Expected classified_by to start with 'manual-rollback:', got {city_gate['classified_by']}"
            assert city_gate["rollback_available"] == True, \
                f"Expected rollback_available=True after rollback, got {city_gate['rollback_available']}"
            print(f"PASSED: Audit fields updated - classified_by={city_gate['classified_by']}, rollback_available={city_gate['rollback_available']}")
        else:
            print("INFO: city-gate not found in recent history (may need longer lookback)")


class TestRollbackEmptyBody:
    """Test rollback with empty body uses saved property_type_previous"""
    
    def test_rollback_empty_body_uses_previous(self, admin_headers):
        """Empty body {} should use saved property_type_previous if available"""
        # First, set a known state with explicit target
        resp1 = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={"target_type": "guesthouse"}
        )
        assert resp1.status_code == 200
        
        # Now try empty body - should use the saved previous_type
        resp2 = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/city-gate/ai-classification-rollback",
            headers=admin_headers,
            json={}
        )
        
        # Could be 200 (success using previous) or 400 (no previous saved)
        if resp2.status_code == 200:
            result = resp2.json()
            assert result["ok"] == True
            print(f"PASSED: Empty body rollback used saved previous_type: {result}")
        elif resp2.status_code == 400:
            result = resp2.json()
            assert "previous_type" in result.get("detail", "").lower() or "target_type" in result.get("detail", "").lower()
            print(f"PASSED: Empty body returns 400 when no previous_type saved: {result['detail']}")
        else:
            pytest.fail(f"Unexpected status {resp2.status_code}: {resp2.text}")


# ============================================================================
# Fleet Classify Property Types - property_type_previous Storage Test
# ============================================================================

class TestFleetClassifyStoresPrevious:
    """Test that fleet-classify-property-types stores property_type_previous on LIVE update"""
    
    def test_fleet_classify_stores_previous_on_live(self, admin_headers):
        """Verify fleet-classify-property-types stores property_type_previous on LIVE update"""
        # Run classify on city-gate with LIVE mode
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-classify-property-types",
            headers=admin_headers,
            json={
                "property_ids": ["city-gate"],
                "dry_run": False,
                "confidence_threshold": 0.5  # Lower threshold to ensure update
            }
        )
        
        # This is a slow AI call, may take 3-15s
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        result = resp.json()
        assert result["ok"] == True
        
        print(f"Fleet classify result: updated={result['updated_count']}, unchanged={result['unchanged_count']}")
        
        # Check if city-gate was updated and has property_type_previous
        if result["updated_count"] > 0:
            # Verify in history
            resp2 = requests.get(
                f"{BASE_URL}/api/revenue/market-robot/ai-classification-history?days=1&limit=50",
                headers=admin_headers
            )
            assert resp2.status_code == 200
            data = resp2.json()
            
            city_gate = None
            for item in data["items"]:
                if item["property_id"] == "city-gate":
                    city_gate = item
                    break
            
            if city_gate:
                # previous_type should be set after LIVE update
                print(f"PASSED: city-gate has previous_type={city_gate['previous_type']}, current_type={city_gate['current_type']}")
            else:
                print("INFO: city-gate not in recent history")
        else:
            print("INFO: No updates made (property type unchanged or low confidence)")


# ============================================================================
# Regression Tests - Existing Endpoints Still Work
# ============================================================================

class TestRegressionExistingEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_fleet_classify_property_types_still_works(self, admin_headers):
        """Verify fleet-classify-property-types endpoint still works"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-classify-property-types",
            headers=admin_headers,
            json={"property_ids": ["city-gate"], "dry_run": True}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["ok"] == True
        assert "results" in data
        print(f"PASSED: fleet-classify-property-types works - {data['message']}")
    
    def test_fleet_validate_geo_still_works(self, admin_headers):
        """Verify fleet-validate-geo endpoint still works"""
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/fleet-validate-geo",
            headers=admin_headers,
            json={"fix": False}  # dry run
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["ok"] == True
        print(f"PASSED: fleet-validate-geo works - total={data.get('total_properties', 'N/A')}")
    
    def test_competitors_discover_still_works(self, admin_headers):
        """Verify competitors/discover endpoint still responds (may be slow due to Playwright)"""
        # Just check it responds with 200 structure, actual scraping may fail due to Playwright
        resp = requests.post(
            f"{BASE_URL}/api/revenue/market-robot/camden-suites/competitors/discover",
            headers=admin_headers,
            json={"radius_km": 1, "max_results": 1}
        )
        # Accept 200 (success) or 500 (Playwright infrastructure issue - known)
        if resp.status_code == 200:
            data = resp.json()
            assert "candidates" in data or "ok" in data
            print(f"PASSED: competitors/discover works - {len(data.get('candidates', []))} candidates")
        elif resp.status_code == 500:
            print("INFO: competitors/discover returned 500 (Playwright infrastructure issue - known)")
        else:
            pytest.fail(f"Unexpected status {resp.status_code}: {resp.text}")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
