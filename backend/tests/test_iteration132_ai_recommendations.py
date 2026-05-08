"""
Iteration 132 - AI-Powered Marketplace Recommendations Tests
Tests the new GPT-5.2 powered recommendation system for the Integrations Marketplace.

Features tested:
- POST /api/marketplace/recommendations/{pid}/generate - AI recommendation generation
- GET /api/marketplace/recommendations/{pid} - Cached recommendations retrieval
- Auth: Both endpoints require admin/manager role
- Regression: Existing marketplace endpoints still work (catalog, install, toggle, sync, uninstall)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAIRecommendations:
    """AI-powered marketplace recommendations tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        data = login_resp.json()
        # Token field is 'token' not 'access_token'
        token = data.get("token")
        assert token, f"No token in response: {data}"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        yield
    
    # ============== GET /api/marketplace/recommendations/{pid} ==============
    
    def test_get_recommendations_before_generate_returns_none_status(self):
        """GET recommendations before any generation should return {status: 'none'}"""
        # Use a unique property ID that hasn't had recommendations generated
        unique_pid = "test-no-recs-property"
        resp = self.session.get(f"{BASE_URL}/api/marketplace/recommendations/{unique_pid}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "none", f"Expected status='none', got: {data}"
    
    def test_get_recommendations_requires_auth(self):
        """GET recommendations without auth should return 401"""
        no_auth_session = requests.Session()
        resp = no_auth_session.get(f"{BASE_URL}/api/marketplace/recommendations/all")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    
    # ============== POST /api/marketplace/recommendations/{pid}/generate ==============
    
    def test_generate_recommendations_success(self):
        """POST generate should return 3 AI recommendations with required fields"""
        # This test uses real GPT-5.2 via Emergent LLM Key - may take 5-10 seconds
        resp = self.session.post(f"{BASE_URL}/api/marketplace/recommendations/all/generate", timeout=60)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        
        # Check required top-level fields
        assert "headline" in data, f"Missing 'headline' in response: {data}"
        assert "recommendations" in data, f"Missing 'recommendations' in response: {data}"
        assert "generated_at" in data, f"Missing 'generated_at' in response: {data}"
        assert "signal_snapshot" in data, f"Missing 'signal_snapshot' in response: {data}"
        
        # Check recommendations array
        recs = data["recommendations"]
        assert isinstance(recs, list), f"recommendations should be a list: {recs}"
        assert len(recs) == 3, f"Expected exactly 3 recommendations, got {len(recs)}: {recs}"
        
        # Check each recommendation has required fields
        required_fields = ["id", "title", "reason", "impact", "priority", "cat", "domain", "name", "desc"]
        for i, rec in enumerate(recs):
            for field in required_fields:
                assert field in rec, f"Recommendation {i} missing field '{field}': {rec}"
            
            # Priority should be 'high' or 'medium'
            assert rec["priority"] in ["high", "medium"], f"Invalid priority: {rec['priority']}"
        
        # Check signal_snapshot
        snapshot = data["signal_snapshot"]
        assert "bookings" in snapshot, f"Missing 'bookings' in signal_snapshot: {snapshot}"
        assert "revenue" in snapshot, f"Missing 'revenue' in signal_snapshot: {snapshot}"
        assert "connected_count" in snapshot, f"Missing 'connected_count' in signal_snapshot: {snapshot}"
        assert "top_sources" in snapshot, f"Missing 'top_sources' in signal_snapshot: {snapshot}"
        
        print(f"✓ Generated recommendations: {[r['title'] for r in recs]}")
        print(f"✓ Headline: {data['headline']}")
    
    def test_generate_recommendations_requires_auth(self):
        """POST generate without auth should return 401"""
        no_auth_session = requests.Session()
        resp = no_auth_session.post(f"{BASE_URL}/api/marketplace/recommendations/all/generate")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    
    def test_generate_recommendations_idempotent(self):
        """Calling generate twice should upsert (update) the recommendations"""
        # First call
        resp1 = self.session.post(f"{BASE_URL}/api/marketplace/recommendations/all/generate", timeout=60)
        assert resp1.status_code == 200, f"First generate failed: {resp1.text}"
        data1 = resp1.json()
        generated_at_1 = data1.get("generated_at")
        
        # Wait a moment
        time.sleep(2)
        
        # Second call
        resp2 = self.session.post(f"{BASE_URL}/api/marketplace/recommendations/all/generate", timeout=60)
        assert resp2.status_code == 200, f"Second generate failed: {resp2.text}"
        data2 = resp2.json()
        generated_at_2 = data2.get("generated_at")
        
        # generated_at should be different (newer)
        assert generated_at_2 != generated_at_1, f"generated_at should be updated: {generated_at_1} vs {generated_at_2}"
        print(f"✓ Idempotent: First={generated_at_1}, Second={generated_at_2}")
    
    def test_get_recommendations_after_generate_returns_cached(self):
        """GET recommendations after generate should return cached document"""
        # First generate
        gen_resp = self.session.post(f"{BASE_URL}/api/marketplace/recommendations/all/generate", timeout=60)
        assert gen_resp.status_code == 200, f"Generate failed: {gen_resp.text}"
        gen_data = gen_resp.json()
        
        # Then GET
        get_resp = self.session.get(f"{BASE_URL}/api/marketplace/recommendations/all")
        assert get_resp.status_code == 200, f"GET failed: {get_resp.text}"
        get_data = get_resp.json()
        
        # Should have same structure
        assert "recommendations" in get_data, f"Missing recommendations in cached: {get_data}"
        assert "headline" in get_data, f"Missing headline in cached: {get_data}"
        assert get_data.get("generated_at") == gen_data.get("generated_at"), "generated_at should match"
        print(f"✓ Cached recommendations match generated")
    
    def test_recommendations_not_already_installed(self):
        """AI recommendations should NOT include already-installed integrations"""
        # First, install an integration
        install_resp = self.session.post(f"{BASE_URL}/api/marketplace/install/all/stripe", json={})
        assert install_resp.status_code == 200, f"Install failed: {install_resp.text}"
        
        try:
            # Generate recommendations
            gen_resp = self.session.post(f"{BASE_URL}/api/marketplace/recommendations/all/generate", timeout=60)
            assert gen_resp.status_code == 200, f"Generate failed: {gen_resp.text}"
            data = gen_resp.json()
            
            # Check that 'stripe' is NOT in recommendations
            rec_ids = [r["id"] for r in data.get("recommendations", [])]
            assert "stripe" not in rec_ids, f"Stripe should not be recommended (already installed): {rec_ids}"
            print(f"✓ Recommendations exclude installed integrations: {rec_ids}")
        finally:
            # Cleanup - uninstall stripe
            self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/all/stripe")


class TestMarketplaceRegression:
    """Regression tests for existing marketplace endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_catalog_returns_124_integrations(self):
        """Catalog should return 124 integrations"""
        resp = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert resp.status_code == 200, f"Catalog failed: {resp.text}"
        data = resp.json()
        
        assert data.get("total_available") == 124, f"Expected 124 integrations, got {data.get('total_available')}"
        print(f"✓ Catalog has {data.get('total_available')} integrations")
    
    def test_catalog_returns_17_categories(self):
        """Catalog should return 17 categories"""
        resp = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert resp.status_code == 200, f"Catalog failed: {resp.text}"
        data = resp.json()
        
        categories = data.get("categories", [])
        assert len(categories) == 17, f"Expected 17 categories, got {len(categories)}"
        
        expected_cats = ["ota", "payments", "channel", "revenue", "messaging", "ai", "reviews", 
                        "locks", "accounting", "pos", "analytics", "ops", "marketing", 
                        "productivity", "storage", "identity", "compliance"]
        actual_cats = [c["id"] for c in categories]
        for cat in expected_cats:
            assert cat in actual_cats, f"Missing category: {cat}"
        print(f"✓ All 17 categories present")
    
    def test_install_toggle_sync_uninstall_flow(self):
        """Full CRUD flow: install -> toggle -> sync -> uninstall"""
        test_integration = "kayak"
        
        # Install
        install_resp = self.session.post(f"{BASE_URL}/api/marketplace/install/all/{test_integration}", json={})
        assert install_resp.status_code == 200, f"Install failed: {install_resp.text}"
        assert install_resp.json().get("ok") == True
        print(f"✓ Installed {test_integration}")
        
        # Toggle (disable)
        toggle_resp = self.session.post(f"{BASE_URL}/api/marketplace/toggle/all/{test_integration}")
        assert toggle_resp.status_code == 200, f"Toggle failed: {toggle_resp.text}"
        assert toggle_resp.json().get("enabled") == False
        print(f"✓ Toggled {test_integration} to disabled")
        
        # Toggle again (enable)
        toggle_resp2 = self.session.post(f"{BASE_URL}/api/marketplace/toggle/all/{test_integration}")
        assert toggle_resp2.status_code == 200, f"Toggle2 failed: {toggle_resp2.text}"
        assert toggle_resp2.json().get("enabled") == True
        print(f"✓ Toggled {test_integration} to enabled")
        
        # Sync
        sync_resp = self.session.post(f"{BASE_URL}/api/marketplace/sync/all/{test_integration}")
        assert sync_resp.status_code == 200, f"Sync failed: {sync_resp.text}"
        assert "last_sync" in sync_resp.json()
        print(f"✓ Synced {test_integration}")
        
        # Uninstall
        uninstall_resp = self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/all/{test_integration}")
        assert uninstall_resp.status_code == 200, f"Uninstall failed: {uninstall_resp.text}"
        assert uninstall_resp.json().get("uninstalled") == True
        print(f"✓ Uninstalled {test_integration}")
    
    def test_catalog_category_filter(self):
        """Category filter should work"""
        resp = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all?category=ota")
        assert resp.status_code == 200, f"Filter failed: {resp.text}"
        data = resp.json()
        
        integrations = data.get("integrations", [])
        assert len(integrations) > 0, "Should have OTA integrations"
        for i in integrations:
            assert i["cat"] == "ota", f"Non-OTA integration in filtered results: {i}"
        print(f"✓ Category filter works: {len(integrations)} OTA integrations")
    
    def test_catalog_search_filter(self):
        """Search filter should work"""
        resp = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all?q=stripe")
        assert resp.status_code == 200, f"Search failed: {resp.text}"
        data = resp.json()
        
        integrations = data.get("integrations", [])
        assert len(integrations) >= 1, "Should find Stripe"
        found_stripe = any(i["id"] == "stripe" for i in integrations)
        assert found_stripe, f"Stripe not found in search results: {integrations}"
        print(f"✓ Search filter works")
    
    def test_install_invalid_integration_returns_404(self):
        """Installing non-existent integration should return 404"""
        resp = self.session.post(f"{BASE_URL}/api/marketplace/install/all/nonexistent-integration", json={})
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"✓ Invalid integration returns 404")
    
    def test_uninstall_not_installed_returns_404(self):
        """Uninstalling not-installed integration should return 404"""
        resp = self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/all/nonexistent-integration")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"✓ Uninstall not-installed returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
