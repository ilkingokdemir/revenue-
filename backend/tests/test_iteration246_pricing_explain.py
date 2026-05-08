"""
Batch 34 — AI Pricing Explainability Tests
Tests for POST /api/pricing/explain, GET /api/pricing/explain/history/{property_id},
GET /api/pricing/explain/dashboard/{property_id}, POST /api/pricing/explain/{id}/decision
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def session():
    """Create authenticated session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Login
    login_resp = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return s


class TestPricingExplainAuth:
    """Test authentication requirements"""
    
    def test_explain_requires_auth(self):
        """POST /api/pricing/explain requires authentication"""
        resp = requests.post(f"{BASE_URL}/api/pricing/explain", json={
            "property_id": "default",
            "room_type": "Standard",
            "target_date": "2026-05-15",
            "current_rate": 1500,
            "proposed_rate": 1750,
            "occupancy_pct": 78
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ POST /api/pricing/explain requires auth (401)")
    
    def test_history_requires_auth(self):
        """GET /api/pricing/explain/history/{property_id} requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/pricing/explain/history/default")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ GET /api/pricing/explain/history requires auth (401)")
    
    def test_dashboard_requires_auth(self):
        """GET /api/pricing/explain/dashboard/{property_id} requires authentication"""
        resp = requests.get(f"{BASE_URL}/api/pricing/explain/dashboard/default")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ GET /api/pricing/explain/dashboard requires auth (401)")
    
    def test_decision_requires_auth(self):
        """POST /api/pricing/explain/{id}/decision requires authentication"""
        resp = requests.post(f"{BASE_URL}/api/pricing/explain/fake-id/decision", json={
            "decision": "accept"
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ POST /api/pricing/explain/{id}/decision requires auth (401)")


class TestPricingExplainValidation:
    """Test input validation"""
    
    def test_occupancy_pct_validation_too_high(self, session):
        """occupancy_pct > 100 returns 422"""
        resp = session.post(f"{BASE_URL}/api/pricing/explain", json={
            "property_id": "default",
            "room_type": "Standard",
            "target_date": "2026-05-15",
            "current_rate": 1500,
            "proposed_rate": 1750,
            "occupancy_pct": 150  # Invalid: > 100
        })
        assert resp.status_code == 422, f"Expected 422 for occupancy_pct > 100, got {resp.status_code}"
        print("✓ occupancy_pct > 100 returns 422")
    
    def test_occupancy_pct_validation_negative(self, session):
        """occupancy_pct < 0 returns 422"""
        resp = session.post(f"{BASE_URL}/api/pricing/explain", json={
            "property_id": "default",
            "room_type": "Standard",
            "target_date": "2026-05-15",
            "current_rate": 1500,
            "proposed_rate": 1750,
            "occupancy_pct": -10  # Invalid: < 0
        })
        assert resp.status_code == 422, f"Expected 422 for occupancy_pct < 0, got {resp.status_code}"
        print("✓ occupancy_pct < 0 returns 422")


class TestPricingExplainAI:
    """Test AI explanation generation (takes ~5-10s)"""
    
    def test_explain_returns_valid_response(self, session):
        """POST /api/pricing/explain returns 200 with valid structure"""
        payload = {
            "property_id": "default",
            "room_type": "TEST_Standard",
            "target_date": "2026-05-20",
            "current_rate": 1500,
            "proposed_rate": 1750,
            "occupancy_pct": 78,
            "pace_lead_30d": 0.12,
            "demand_signals": ["Hafta sonu", "Arama hacmi artışı"],
            "events": ["Konser - Stadyum"],
            "comp_set": [
                {"name": "Rakip A", "rate": 1700},
                {"name": "Rakip B", "rate": 1820}
            ],
            "notes": "Test explanation"
        }
        resp = session.post(f"{BASE_URL}/api/pricing/explain", json=payload, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        
        # Verify required fields
        assert "id" in data, "Response missing 'id'"
        assert "narrative" in data, "Response missing 'narrative'"
        assert "confidence" in data, "Response missing 'confidence'"
        assert "key_drivers" in data, "Response missing 'key_drivers'"
        assert "risks" in data, "Response missing 'risks'"
        assert "alternative_rates" in data, "Response missing 'alternative_rates'"
        
        # Verify narrative is non-empty Turkish text
        assert len(data["narrative"]) > 0, "Narrative should not be empty"
        
        # Verify confidence is 0-100
        assert 0 <= data["confidence"] <= 100, f"Confidence {data['confidence']} not in 0-100"
        
        # Verify key_drivers has 3-5 items with correct structure
        assert 3 <= len(data["key_drivers"]) <= 6, f"Expected 3-5 drivers, got {len(data['key_drivers'])}"
        for driver in data["key_drivers"]:
            assert "label" in driver, "Driver missing 'label'"
            assert "weight" in driver, "Driver missing 'weight'"
            assert "direction" in driver, "Driver missing 'direction'"
            assert driver["direction"] in ("up", "down", "neutral"), f"Invalid direction: {driver['direction']}"
        
        # Verify risks has 1-3 items
        assert 1 <= len(data["risks"]) <= 5, f"Expected 1-3 risks, got {len(data['risks'])}"
        
        # Verify alternative_rates has 2 items
        assert len(data["alternative_rates"]) >= 2, f"Expected 2 alternatives, got {len(data['alternative_rates'])}"
        for alt in data["alternative_rates"]:
            assert "rate" in alt, "Alternative missing 'rate'"
            assert "scenario" in alt, "Alternative missing 'scenario'"
        
        print(f"✓ POST /api/pricing/explain returns valid response (confidence={data['confidence']}, {len(data['key_drivers'])} drivers, {len(data['risks'])} risks, {len(data['alternative_rates'])} alternatives)")
        
        # Store ID for decision tests
        pytest.explain_id = data["id"]
        pytest.proposed_rate = data["proposed_rate"]
        pytest.current_rate = data["current_rate"]


class TestPricingExplainHistory:
    """Test history endpoint"""
    
    def test_history_returns_items(self, session):
        """GET /api/pricing/explain/history/{property_id} returns recent items"""
        resp = session.get(f"{BASE_URL}/api/pricing/explain/history/default?limit=50")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "items" in data, "Response missing 'items'"
        assert "count" in data, "Response missing 'count'"
        assert isinstance(data["items"], list), "items should be a list"
        
        # Verify items are sorted by created_at desc
        if len(data["items"]) >= 2:
            for i in range(len(data["items"]) - 1):
                assert data["items"][i]["created_at"] >= data["items"][i+1]["created_at"], \
                    "Items should be sorted by created_at desc"
        
        print(f"✓ GET /api/pricing/explain/history returns {data['count']} items sorted desc")


class TestPricingExplainDashboard:
    """Test dashboard KPIs endpoint"""
    
    def test_dashboard_returns_kpis(self, session):
        """GET /api/pricing/explain/dashboard/{property_id} returns KPIs"""
        resp = session.get(f"{BASE_URL}/api/pricing/explain/dashboard/default")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        
        # Verify all required KPI fields
        required_fields = [
            "total", "pending", "accepted", "rejected", "overridden",
            "accept_rate_pct", "avg_confidence", "avg_abs_delta_pct"
        ]
        for field in required_fields:
            assert field in data, f"Dashboard missing '{field}'"
        
        # Verify types
        assert isinstance(data["total"], int), "total should be int"
        assert isinstance(data["pending"], int), "pending should be int"
        assert isinstance(data["accepted"], int), "accepted should be int"
        assert isinstance(data["rejected"], int), "rejected should be int"
        assert isinstance(data["overridden"], int), "overridden should be int"
        assert isinstance(data["accept_rate_pct"], (int, float)), "accept_rate_pct should be numeric"
        assert isinstance(data["avg_confidence"], (int, float)), "avg_confidence should be numeric"
        assert isinstance(data["avg_abs_delta_pct"], (int, float)), "avg_abs_delta_pct should be numeric"
        
        print(f"✓ GET /api/pricing/explain/dashboard returns KPIs (total={data['total']}, pending={data['pending']}, accepted={data['accepted']}, accept_rate={data['accept_rate_pct']}%)")


class TestPricingExplainDecision:
    """Test decision endpoint"""
    
    def test_decision_invalid_string_returns_400(self, session):
        """Invalid decision string returns 400"""
        # First create a new explanation to test with
        payload = {
            "property_id": "default",
            "room_type": "TEST_Decision",
            "target_date": "2026-05-21",
            "current_rate": 1000,
            "proposed_rate": 1200,
            "occupancy_pct": 65
        }
        create_resp = session.post(f"{BASE_URL}/api/pricing/explain", json=payload, timeout=30)
        assert create_resp.status_code == 200, f"Failed to create explanation: {create_resp.text}"
        exp_id = create_resp.json()["id"]
        
        # Test invalid decision
        resp = session.post(f"{BASE_URL}/api/pricing/explain/{exp_id}/decision", json={
            "decision": "invalid_decision"
        })
        assert resp.status_code == 400, f"Expected 400 for invalid decision, got {resp.status_code}"
        print("✓ Invalid decision string returns 400")
    
    def test_decision_nonexistent_id_returns_404(self, session):
        """Non-existent ID returns 404"""
        resp = session.post(f"{BASE_URL}/api/pricing/explain/nonexistent-uuid-12345/decision", json={
            "decision": "accept"
        })
        assert resp.status_code == 404, f"Expected 404 for non-existent ID, got {resp.status_code}"
        print("✓ Non-existent ID returns 404")
    
    def test_decision_accept_sets_proposed_rate(self, session):
        """decision='accept' sets decision_rate=proposed_rate"""
        # Create new explanation
        payload = {
            "property_id": "default",
            "room_type": "TEST_Accept",
            "target_date": "2026-05-22",
            "current_rate": 1000,
            "proposed_rate": 1200,
            "occupancy_pct": 70
        }
        create_resp = session.post(f"{BASE_URL}/api/pricing/explain", json=payload, timeout=30)
        assert create_resp.status_code == 200
        exp = create_resp.json()
        exp_id = exp["id"]
        proposed_rate = exp["proposed_rate"]
        
        # Accept
        resp = session.post(f"{BASE_URL}/api/pricing/explain/{exp_id}/decision", json={
            "decision": "accept"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["decision"] == "accept"
        assert data["final_rate"] == proposed_rate, f"Expected final_rate={proposed_rate}, got {data['final_rate']}"
        print(f"✓ decision='accept' sets decision_rate={proposed_rate}")
    
    def test_decision_reject_sets_current_rate(self, session):
        """decision='reject' sets decision_rate=current_rate"""
        # Create new explanation
        payload = {
            "property_id": "default",
            "room_type": "TEST_Reject",
            "target_date": "2026-05-23",
            "current_rate": 1000,
            "proposed_rate": 1200,
            "occupancy_pct": 70
        }
        create_resp = session.post(f"{BASE_URL}/api/pricing/explain", json=payload, timeout=30)
        assert create_resp.status_code == 200
        exp = create_resp.json()
        exp_id = exp["id"]
        current_rate = exp["current_rate"]
        
        # Reject
        resp = session.post(f"{BASE_URL}/api/pricing/explain/{exp_id}/decision", json={
            "decision": "reject"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["decision"] == "reject"
        assert data["final_rate"] == current_rate, f"Expected final_rate={current_rate}, got {data['final_rate']}"
        print(f"✓ decision='reject' sets decision_rate={current_rate}")
    
    def test_decision_override_requires_final_rate(self, session):
        """decision='override' requires positive final_rate"""
        # Create new explanation
        payload = {
            "property_id": "default",
            "room_type": "TEST_Override_NoRate",
            "target_date": "2026-05-24",
            "current_rate": 1000,
            "proposed_rate": 1200,
            "occupancy_pct": 70
        }
        create_resp = session.post(f"{BASE_URL}/api/pricing/explain", json=payload, timeout=30)
        assert create_resp.status_code == 200
        exp_id = create_resp.json()["id"]
        
        # Override without final_rate
        resp = session.post(f"{BASE_URL}/api/pricing/explain/{exp_id}/decision", json={
            "decision": "override"
        })
        assert resp.status_code == 400, f"Expected 400 for override without final_rate, got {resp.status_code}"
        print("✓ decision='override' without final_rate returns 400")
    
    def test_decision_override_with_final_rate(self, session):
        """decision='override' with final_rate works"""
        # Create new explanation
        payload = {
            "property_id": "default",
            "room_type": "TEST_Override_WithRate",
            "target_date": "2026-05-25",
            "current_rate": 1000,
            "proposed_rate": 1200,
            "occupancy_pct": 70
        }
        create_resp = session.post(f"{BASE_URL}/api/pricing/explain", json=payload, timeout=30)
        assert create_resp.status_code == 200
        exp_id = create_resp.json()["id"]
        
        # Override with final_rate
        override_rate = 1150
        resp = session.post(f"{BASE_URL}/api/pricing/explain/{exp_id}/decision", json={
            "decision": "override",
            "final_rate": override_rate
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["decision"] == "override"
        assert data["final_rate"] == override_rate, f"Expected final_rate={override_rate}, got {data['final_rate']}"
        print(f"✓ decision='override' with final_rate={override_rate} works")
    
    def test_decision_idempotent_returns_400(self, session):
        """Second decision on same ID returns 400 'already decided'"""
        # Create new explanation
        payload = {
            "property_id": "default",
            "room_type": "TEST_Idempotent",
            "target_date": "2026-05-26",
            "current_rate": 1000,
            "proposed_rate": 1200,
            "occupancy_pct": 70
        }
        create_resp = session.post(f"{BASE_URL}/api/pricing/explain", json=payload, timeout=30)
        assert create_resp.status_code == 200
        exp_id = create_resp.json()["id"]
        
        # First decision
        resp1 = session.post(f"{BASE_URL}/api/pricing/explain/{exp_id}/decision", json={
            "decision": "accept"
        })
        assert resp1.status_code == 200
        
        # Second decision should fail
        resp2 = session.post(f"{BASE_URL}/api/pricing/explain/{exp_id}/decision", json={
            "decision": "reject"
        })
        assert resp2.status_code == 400, f"Expected 400 for second decision, got {resp2.status_code}"
        assert "already" in resp2.text.lower(), f"Expected 'already decided' message, got: {resp2.text}"
        print("✓ Second decision on same ID returns 400 'already decided'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
