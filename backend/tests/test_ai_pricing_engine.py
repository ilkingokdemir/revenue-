"""
AI Pricing Engine Backend Tests (Iter 339)
Tests for /api/revenue/ai-pricing/{property_id}/* endpoints
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for requests"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

class TestAIPricingConfig:
    """Tests for AI Pricing config endpoints"""
    
    def test_get_config_default(self, auth_headers):
        """GET /api/revenue/ai-pricing/{property_id}/config returns default config"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/config",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify default config structure
        assert data["property_id"] == "aldgate-flats"
        assert "enabled" in data
        assert "auto_apply" in data
        assert "auto_apply_threshold_pct" in data
        assert "use_llm" in data
        assert "min_rate_pct" in data
        assert "max_rate_pct" in data
        assert "days_horizon" in data
        
        # Verify default values
        assert data["days_horizon"] == 30
        assert isinstance(data["auto_apply_threshold_pct"], (int, float))
    
    def test_put_config_updates(self, auth_headers):
        """PUT /api/revenue/ai-pricing/{property_id}/config persists updates"""
        # Update config
        update_payload = {
            "auto_apply": True,
            "auto_apply_threshold_pct": 8.5,
            "use_llm": False
        }
        response = requests.put(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/config",
            headers=auth_headers,
            json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify updates persisted
        assert data["auto_apply"] == True
        assert data["auto_apply_threshold_pct"] == 8.5
        assert data["use_llm"] == False
        
        # Verify GET returns updated values
        get_response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/config",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["auto_apply"] == True
        assert get_data["auto_apply_threshold_pct"] == 8.5
    
    def test_put_config_clamps_threshold(self, auth_headers):
        """PUT config clamps threshold to valid range (0.5-25)"""
        # Test clamping to max
        response = requests.put(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/config",
            headers=auth_headers,
            json={"auto_apply_threshold_pct": 100}  # Should clamp to 25
        )
        assert response.status_code == 200
        assert response.json()["auto_apply_threshold_pct"] == 25.0
        
        # Test clamping to min
        response = requests.put(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/config",
            headers=auth_headers,
            json={"auto_apply_threshold_pct": 0.1}  # Should clamp to 0.5
        )
        assert response.status_code == 200
        assert response.json()["auto_apply_threshold_pct"] == 0.5


class TestAIPricingSuggestions:
    """Tests for AI Pricing suggestions endpoint"""
    
    def test_get_suggestions_structure(self, auth_headers):
        """GET /api/revenue/ai-pricing/{property_id}/suggestions returns proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/suggestions",
            params={"days": 7, "use_llm": False},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify top-level structure
        assert "property_id" in data
        assert "currency" in data
        assert "currency_symbol" in data
        assert "horizon_days" in data
        assert "config" in data
        assert "suggestions" in data
        assert "summary" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "total" in summary
        assert "auto_eligible" in summary
        assert "outside_threshold" in summary
        assert "avg_delta_pct" in summary
        assert "uplift_estimate" in summary
    
    def test_suggestions_have_required_fields(self, auth_headers):
        """Each suggestion has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/suggestions",
            params={"days": 3, "use_llm": False},
            headers=auth_headers
        )
        assert response.status_code == 200
        suggestions = response.json().get("suggestions", [])
        
        if suggestions:
            s = suggestions[0]
            # Required fields
            assert "date" in s
            assert "days_out" in s
            assert "suggested_rate" in s
            assert "lead_time_mult" in s
            assert "occupancy_mult" in s
            assert "auto_apply_eligible" in s
            assert "delta_vs_current_pct" in s
            assert "status" in s
    
    def test_days_out_zero_for_today(self, auth_headers):
        """days_out=0 for today (timezone-safe)"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/suggestions",
            params={"days": 3, "use_llm": False},
            headers=auth_headers
        )
        assert response.status_code == 200
        suggestions = response.json().get("suggestions", [])
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_suggestions = [s for s in suggestions if s["date"] == today]
        
        for s in today_suggestions:
            assert s["days_out"] == 0, f"Expected days_out=0 for today, got {s['days_out']}"


class TestAIPricingAcceptReject:
    """Tests for accept/reject endpoints"""
    
    def test_accept_single_item(self, auth_headers):
        """POST /api/revenue/ai-pricing/{property_id}/accept accepts items"""
        # Get a pending suggestion
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/camden-suites/suggestions",
            params={"days": 7, "use_llm": False},
            headers=auth_headers
        )
        assert response.status_code == 200
        suggestions = response.json().get("suggestions", [])
        pending = [s for s in suggestions if s["status"] == "pending"]
        
        if pending:
            item = pending[0]
            accept_response = requests.post(
                f"{BASE_URL}/api/revenue/ai-pricing/camden-suites/accept",
                headers=auth_headers,
                json={"items": [item]}
            )
            assert accept_response.status_code == 200
            assert accept_response.json()["accepted"] >= 1
    
    def test_reject_with_reason(self, auth_headers):
        """POST /api/revenue/ai-pricing/{property_id}/reject records rejection"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/ai-pricing/camden-suites/reject",
            headers=auth_headers,
            json={
                "date": "2026-05-25",
                "room_type_id": "",
                "reason": "Test rejection from pytest"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["date"] == "2026-05-25"
        assert "Test rejection" in data["reason"]
    
    def test_reject_requires_date(self, auth_headers):
        """POST reject without date returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/revenue/ai-pricing/camden-suites/reject",
            headers=auth_headers,
            json={"reason": "No date provided"}
        )
        assert response.status_code == 400


class TestAIPricingAutoApply:
    """Tests for auto-apply endpoint"""
    
    def test_run_auto_apply_disabled(self, auth_headers):
        """run-auto-apply returns skipped_reason when disabled"""
        # First disable auto_apply
        requests.put(
            f"{BASE_URL}/api/revenue/ai-pricing/camden-suites/config",
            headers=auth_headers,
            json={"auto_apply": False}
        )
        
        # Run auto-apply
        response = requests.post(
            f"{BASE_URL}/api/revenue/ai-pricing/camden-suites/run-auto-apply",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["applied"] == 0
        assert "skipped_reason" in data
        assert "disabled" in data["skipped_reason"].lower()
    
    def test_run_auto_apply_enabled(self, auth_headers):
        """run-auto-apply applies when enabled"""
        # Enable auto_apply
        requests.put(
            f"{BASE_URL}/api/revenue/ai-pricing/camden-suites/config",
            headers=auth_headers,
            json={"auto_apply": True, "auto_apply_threshold_pct": 10}
        )
        
        # Run auto-apply
        response = requests.post(
            f"{BASE_URL}/api/revenue/ai-pricing/camden-suites/run-auto-apply",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Should not have skipped_reason when enabled
        assert "skipped_reason" not in data or data.get("skipped_reason") is None
        assert "applied" in data
        assert "summary" in data


class TestAIPricingHistory:
    """Tests for history endpoint"""
    
    def test_get_history(self, auth_headers):
        """GET /api/revenue/ai-pricing/{property_id}/history returns decisions"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/history",
            params={"limit": 10},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "property_id" in data
        assert "count" in data
        assert "items" in data
        assert isinstance(data["items"], list)
        
        # Verify items are sorted by decided_at desc
        if len(data["items"]) >= 2:
            for i in range(len(data["items"]) - 1):
                assert data["items"][i]["decided_at"] >= data["items"][i+1]["decided_at"]


class TestAIPricingMinMaxRate:
    """Tests for min/max rate clamping"""
    
    def test_clamped_flag_set(self, auth_headers):
        """Suggestions have clamped flag when raw exceeds bounds"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/suggestions",
            params={"days": 30, "use_llm": False},
            headers=auth_headers
        )
        assert response.status_code == 200
        suggestions = response.json().get("suggestions", [])
        
        # Check that clamped field exists
        for s in suggestions[:5]:
            assert "clamped" in s
            assert isinstance(s["clamped"], bool)
            
            # If clamped, raw_rate should differ from suggested_rate
            if s["clamped"]:
                assert s["raw_rate"] != s["suggested_rate"]


class TestAIPricingAuth:
    """Tests for authentication requirements"""
    
    def test_config_requires_auth(self):
        """Config endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/config"
        )
        assert response.status_code == 401
    
    def test_suggestions_requires_auth(self):
        """Suggestions endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/revenue/ai-pricing/aldgate-flats/suggestions"
        )
        assert response.status_code == 401
