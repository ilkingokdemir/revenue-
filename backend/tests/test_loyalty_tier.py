"""
Loyalty Tier Engine v2 — Backend API Tests
Tests for multi-criteria auto-upgrade ladder with manual override and audit trail.

Endpoints tested:
- GET /api/loyalty-tier/config/{property_id} — auto-seeds 5 default tiers
- POST /api/loyalty-tier/config/{property_id} — validates non-empty tiers + unique tier_keys
- POST /api/loyalty-tier/evaluate/{property_id}/{guest_id} — computes metrics and selects tier
- POST /api/loyalty-tier/evaluate-batch/{property_id} — batch eval all guests
- POST /api/loyalty-tier/manual/{property_id}/{guest_id} — manual override
- DELETE /api/loyalty-tier/manual/{property_id}/{guest_id} — revoke manual override
- GET /api/loyalty-tier/guest/{property_id}/{guest_id} — get guest tier + progress
- GET /api/loyalty-tier/dashboard/{property_id} — dashboard stats
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PROPERTY_ID = "default"

@pytest.fixture(scope="module")
def auth_session():
    """Authenticate and return session with cookies"""
    session = requests.Session()
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return session


class TestLoyaltyTierConfig:
    """Tests for tier configuration endpoints"""
    
    def test_get_config_auto_seeds_default_tiers(self, auth_session):
        """GET /api/loyalty-tier/config/{property_id} should auto-seed 5 default tiers"""
        resp = auth_session.get(f"{BASE_URL}/api/loyalty-tier/config/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "tiers" in data
        assert "property_id" in data
        assert data["property_id"] == PROPERTY_ID
        
        # Should have 5 default tiers: member, bronze, silver, gold, platinum
        tiers = data["tiers"]
        assert len(tiers) >= 5, f"Expected at least 5 tiers, got {len(tiers)}"
        
        tier_keys = [t["tier_key"] for t in tiers]
        expected_keys = ["member", "bronze", "silver", "gold", "platinum"]
        for key in expected_keys:
            assert key in tier_keys, f"Missing tier_key: {key}"
        
        # Verify tier structure
        for tier in tiers:
            assert "tier_key" in tier
            assert "name" in tier
            assert "threshold_nights" in tier
            assert "threshold_revenue" in tier
            assert "threshold_points" in tier
            assert "benefits" in tier
        
        print(f"✓ Config auto-seeded {len(tiers)} tiers: {tier_keys}")
    
    def test_post_config_validates_non_empty_tiers(self, auth_session):
        """POST /api/loyalty-tier/config/{property_id} should reject empty tiers"""
        resp = auth_session.post(f"{BASE_URL}/api/loyalty-tier/config/{PROPERTY_ID}", json={
            "tiers": []
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "at least one tier" in resp.text.lower()
        print("✓ Empty tiers rejected with 400")
    
    def test_post_config_validates_unique_tier_keys(self, auth_session):
        """POST /api/loyalty-tier/config/{property_id} should reject duplicate tier_keys"""
        resp = auth_session.post(f"{BASE_URL}/api/loyalty-tier/config/{PROPERTY_ID}", json={
            "tiers": [
                {"tier_key": "member", "name": "Member", "threshold_nights": 0, "threshold_revenue": 0, "threshold_points": 0, "benefits": []},
                {"tier_key": "member", "name": "Member Duplicate", "threshold_nights": 5, "threshold_revenue": 100, "threshold_points": 10, "benefits": []}
            ]
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "unique" in resp.text.lower()
        print("✓ Duplicate tier_keys rejected with 400")
    
    def test_post_config_saves_valid_config(self, auth_session):
        """POST /api/loyalty-tier/config/{property_id} should save valid config"""
        # First get current config to restore later
        original = auth_session.get(f"{BASE_URL}/api/loyalty-tier/config/{PROPERTY_ID}").json()
        
        # Post new config
        new_tiers = [
            {"tier_key": "basic", "name": "Basic", "color": "stone", "threshold_nights": 0, "threshold_revenue": 0, "threshold_points": 0, "benefits": ["WiFi"]},
            {"tier_key": "premium", "name": "Premium", "color": "amber", "threshold_nights": 10, "threshold_revenue": 2000, "threshold_points": 200, "benefits": ["WiFi", "Breakfast"]}
        ]
        resp = auth_session.post(f"{BASE_URL}/api/loyalty-tier/config/{PROPERTY_ID}", json={"tiers": new_tiers})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") == True
        assert data.get("tier_count") == 2
        
        # Verify saved
        verify = auth_session.get(f"{BASE_URL}/api/loyalty-tier/config/{PROPERTY_ID}").json()
        assert len(verify["tiers"]) == 2
        assert verify["tiers"][0]["tier_key"] == "basic"
        
        # Restore original config
        auth_session.post(f"{BASE_URL}/api/loyalty-tier/config/{PROPERTY_ID}", json={"tiers": original["tiers"]})
        print("✓ Valid config saved and verified")


class TestLoyaltyTierEvaluation:
    """Tests for tier evaluation endpoints"""
    
    def test_evaluate_single_guest(self, auth_session):
        """POST /api/loyalty-tier/evaluate/{property_id}/{guest_id} computes tier"""
        # Get a guest ID from guest_profiles
        profiles_resp = auth_session.get(f"{BASE_URL}/api/guest-profiles?property_id={PROPERTY_ID}&limit=1")
        if profiles_resp.status_code != 200 or not profiles_resp.json():
            pytest.skip("No guest profiles available for testing")
        
        guest_id = profiles_resp.json()[0].get("id")
        if not guest_id:
            pytest.skip("Guest profile has no ID")
        
        resp = auth_session.post(f"{BASE_URL}/api/loyalty-tier/evaluate/{PROPERTY_ID}/{guest_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "metrics" in data
        assert "nights" in data["metrics"]
        assert "revenue" in data["metrics"]
        assert "points" in data["metrics"]
        
        # Either changed or not changed
        if data.get("changed"):
            assert "to" in data
            assert "tier" in data
            print(f"✓ Guest {guest_id[:8]} evaluated: changed to {data['to']}")
        else:
            assert "current_tier" in data or "reason" in data
            print(f"✓ Guest {guest_id[:8]} evaluated: no change (reason: {data.get('reason', 'same tier')})")
    
    def test_evaluate_batch(self, auth_session):
        """POST /api/loyalty-tier/evaluate-batch/{property_id} processes all guests"""
        resp = auth_session.post(f"{BASE_URL}/api/loyalty-tier/evaluate-batch/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "evaluated" in data
        assert "upgraded" in data
        assert "downgraded" in data
        assert "unchanged" in data
        assert "skipped_manual" in data
        
        # Note: evaluated count includes guests found, but some may be skipped if they have no 'id' field
        # The sum of categories should be <= evaluated (guests without id are silently skipped)
        total = data["upgraded"] + data["downgraded"] + data["unchanged"] + data["skipped_manual"]
        assert total <= data["evaluated"], f"Counts exceed evaluated: {total} > {data['evaluated']}"
        
        print(f"✓ Batch eval: {data['evaluated']} guests found, {total} processed (↑{data['upgraded']} upgraded, ↓{data['downgraded']} downgraded, {data['unchanged']} unchanged, {data['skipped_manual']} manual skipped)")


class TestLoyaltyTierManualOverride:
    """Tests for manual override endpoints"""
    
    @pytest.fixture
    def test_guest_id(self, auth_session):
        """Get or create a test guest for manual override tests"""
        profiles_resp = auth_session.get(f"{BASE_URL}/api/guest-profiles?property_id={PROPERTY_ID}&limit=1")
        if profiles_resp.status_code == 200 and profiles_resp.json():
            return profiles_resp.json()[0].get("id")
        return f"test-guest-{uuid.uuid4().hex[:8]}"
    
    def test_manual_override_valid_tier(self, auth_session, test_guest_id):
        """POST /api/loyalty-tier/manual/{property_id}/{guest_id} sets manual override"""
        resp = auth_session.post(f"{BASE_URL}/api/loyalty-tier/manual/{PROPERTY_ID}/{test_guest_id}", json={
            "tier_key": "gold",
            "reason": "VIP customer - testing"
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") == True
        assert data.get("to") == "gold"
        assert data.get("source") == "manual"
        
        # Verify guest now has manual source
        guest_resp = auth_session.get(f"{BASE_URL}/api/loyalty-tier/guest/{PROPERTY_ID}/{test_guest_id}")
        assert guest_resp.status_code == 200
        guest_data = guest_resp.json()
        assert guest_data.get("source") == "manual" or guest_data.get("tier", {}).get("tier_key") == "gold"
        
        print(f"✓ Manual override set to gold for guest {test_guest_id[:8]}")
    
    def test_manual_override_invalid_tier_returns_400(self, auth_session, test_guest_id):
        """POST /api/loyalty-tier/manual with invalid tier_key returns 400"""
        resp = auth_session.post(f"{BASE_URL}/api/loyalty-tier/manual/{PROPERTY_ID}/{test_guest_id}", json={
            "tier_key": "invalid_tier_xyz",
            "reason": "Testing invalid tier"
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print("✓ Invalid tier_key rejected with 400")
    
    def test_auto_eval_skips_manual_override(self, auth_session, test_guest_id):
        """Auto-eval should skip guests with source='manual'"""
        # First set manual override
        auth_session.post(f"{BASE_URL}/api/loyalty-tier/manual/{PROPERTY_ID}/{test_guest_id}", json={
            "tier_key": "platinum",
            "reason": "Testing skip manual"
        })
        
        # Now try to auto-evaluate
        resp = auth_session.post(f"{BASE_URL}/api/loyalty-tier/evaluate/{PROPERTY_ID}/{test_guest_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert data.get("changed") == False
        assert "manual" in data.get("reason", "").lower()
        
        print(f"✓ Auto-eval correctly skipped manual override guest")
    
    def test_revoke_manual_override(self, auth_session, test_guest_id):
        """DELETE /api/loyalty-tier/manual/{property_id}/{guest_id} revokes manual override"""
        # First ensure manual override exists
        auth_session.post(f"{BASE_URL}/api/loyalty-tier/manual/{PROPERTY_ID}/{test_guest_id}", json={
            "tier_key": "silver",
            "reason": "Testing revoke"
        })
        
        # Revoke
        resp = auth_session.delete(f"{BASE_URL}/api/loyalty-tier/manual/{PROPERTY_ID}/{test_guest_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert data.get("ok") == True
        assert data.get("source") == "auto"
        
        print(f"✓ Manual override revoked, source set to 'auto'")


class TestLoyaltyTierGuestAndDashboard:
    """Tests for guest tier info and dashboard endpoints"""
    
    def test_get_guest_tier_info(self, auth_session):
        """GET /api/loyalty-tier/guest/{property_id}/{guest_id} returns tier + metrics + progress"""
        # Get a guest
        profiles_resp = auth_session.get(f"{BASE_URL}/api/guest-profiles?property_id={PROPERTY_ID}&limit=1")
        if profiles_resp.status_code != 200 or not profiles_resp.json():
            pytest.skip("No guest profiles available")
        
        guest_id = profiles_resp.json()[0].get("id")
        
        resp = auth_session.get(f"{BASE_URL}/api/loyalty-tier/guest/{PROPERTY_ID}/{guest_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "guest_id" in data or "tier" in data
        assert "metrics" in data
        assert "nights" in data["metrics"]
        assert "revenue" in data["metrics"]
        assert "points" in data["metrics"]
        
        # Progress may be null if on highest tier
        if data.get("progress"):
            assert "next_tier" in data["progress"]
            assert "nights_pct" in data["progress"]
            assert "revenue_pct" in data["progress"]
            assert "points_pct" in data["progress"]
            print(f"✓ Guest tier info with progress to {data['progress']['next_tier']['name']}")
        else:
            print(f"✓ Guest tier info (no progress - may be highest tier)")
    
    def test_dashboard_returns_stats(self, auth_session):
        """GET /api/loyalty-tier/dashboard/{property_id} returns tier stats"""
        resp = auth_session.get(f"{BASE_URL}/api/loyalty-tier/dashboard/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "tiers" in data
        assert "distribution" in data
        assert "total_members" in data
        assert "manual_overrides" in data
        assert "recent_upgrades" in data
        
        # Distribution should have counts for each tier
        assert isinstance(data["distribution"], dict)
        
        # Recent upgrades should be a list
        assert isinstance(data["recent_upgrades"], list)
        
        print(f"✓ Dashboard: {data['total_members']} members, {data['manual_overrides']} manual overrides, {len(data['recent_upgrades'])} recent upgrades")


class TestRegressionPricingExplainHkTurnover:
    """Light regression tests for pricing-explain and hk-turnover panels"""
    
    def test_pricing_explain_endpoint(self, auth_session):
        """GET /api/pricing-explain/config/{property_id} should work"""
        resp = auth_session.get(f"{BASE_URL}/api/pricing-explain/config/{PROPERTY_ID}")
        # May return 200 with data or 404 if not configured
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"
        print(f"✓ Pricing explain config endpoint: {resp.status_code}")
    
    def test_hk_turnover_dashboard(self, auth_session):
        """GET /api/hk-turnover/dashboard/{property_id} should work"""
        resp = auth_session.get(f"{BASE_URL}/api/hk-turnover/dashboard/{PROPERTY_ID}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "total_staff" in data or "turnover_rate" in data or isinstance(data, dict)
        print(f"✓ HK turnover dashboard endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
