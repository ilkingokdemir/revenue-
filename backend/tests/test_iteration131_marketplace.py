"""
Iteration 131 - Integrations Marketplace API Tests
Tests for:
- GET /api/marketplace/catalog/{pid} - returns 124 integrations, 17 categories, featured list
- POST /api/marketplace/install/{pid}/{integration_id} - installs integration
- POST /api/marketplace/toggle/{pid}/{integration_id} - toggles enabled state
- POST /api/marketplace/sync/{pid}/{integration_id} - updates last_sync
- DELETE /api/marketplace/uninstall/{pid}/{integration_id} - removes integration
- Auth: endpoints require admin or manager role
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMarketplaceAuth:
    """Test authentication requirements for marketplace endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_admin_token(self):
        """Login as admin and return token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        return data.get("token")
    
    def test_catalog_requires_auth(self):
        """Catalog endpoint should require authentication"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Catalog requires authentication")
    
    def test_install_requires_auth(self):
        """Install endpoint should require authentication"""
        response = self.session.post(f"{BASE_URL}/api/marketplace/install/all/stripe", json={})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Install requires authentication")
    
    def test_toggle_requires_auth(self):
        """Toggle endpoint should require authentication"""
        response = self.session.post(f"{BASE_URL}/api/marketplace/toggle/all/stripe")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Toggle requires authentication")
    
    def test_sync_requires_auth(self):
        """Sync endpoint should require authentication"""
        response = self.session.post(f"{BASE_URL}/api/marketplace/sync/all/stripe")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Sync requires authentication")
    
    def test_uninstall_requires_auth(self):
        """Uninstall endpoint should require authentication"""
        response = self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/all/stripe")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Uninstall requires authentication")


class TestMarketplaceCatalog:
    """Test catalog endpoint functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_catalog_returns_124_integrations(self):
        """Catalog should return 124 available integrations"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "total_available" in data, "Missing total_available field"
        assert data["total_available"] == 124, f"Expected 124 integrations, got {data['total_available']}"
        print(f"PASS: Catalog returns {data['total_available']} integrations")
    
    def test_catalog_returns_17_categories(self):
        """Catalog should return 17 categories"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data, "Missing categories field"
        assert len(data["categories"]) == 17, f"Expected 17 categories, got {len(data['categories'])}"
        print(f"PASS: Catalog returns {len(data['categories'])} categories")
    
    def test_catalog_returns_featured_list(self):
        """Catalog should return featured integrations"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200
        data = response.json()
        assert "featured" in data, "Missing featured field"
        assert len(data["featured"]) > 0, "Featured list should not be empty"
        # Verify featured items have featured=True
        for item in data["featured"]:
            assert item.get("featured") == True, f"Featured item {item['id']} should have featured=True"
        print(f"PASS: Catalog returns {len(data['featured'])} featured integrations")
    
    def test_catalog_integration_structure(self):
        """Each integration should have required fields"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200
        data = response.json()
        assert "integrations" in data, "Missing integrations field"
        assert len(data["integrations"]) > 0, "Integrations list should not be empty"
        
        # Check first integration has required fields
        item = data["integrations"][0]
        required_fields = ["id", "name", "cat", "domain", "desc", "installed", "enabled", "status"]
        for field in required_fields:
            assert field in item, f"Integration missing field: {field}"
        print(f"PASS: Integration structure is correct with fields: {required_fields}")
    
    def test_catalog_category_structure(self):
        """Each category should have required fields"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200
        data = response.json()
        
        cat = data["categories"][0]
        required_fields = ["id", "name", "icon", "color", "count", "installed"]
        for field in required_fields:
            assert field in cat, f"Category missing field: {field}"
        print(f"PASS: Category structure is correct with fields: {required_fields}")
    
    def test_catalog_filter_by_category(self):
        """Catalog should filter by category"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all?category=ota")
        assert response.status_code == 200
        data = response.json()
        
        # All returned integrations should be in OTA category
        for item in data["integrations"]:
            assert item["cat"] == "ota", f"Integration {item['id']} should be in OTA category"
        print(f"PASS: Category filter works - returned {len(data['integrations'])} OTA integrations")
    
    def test_catalog_search_filter(self):
        """Catalog should filter by search query"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all?q=stripe")
        assert response.status_code == 200
        data = response.json()
        
        # Should find Stripe
        found = any(item["id"] == "stripe" for item in data["integrations"])
        assert found, "Search for 'stripe' should return Stripe integration"
        print(f"PASS: Search filter works - found Stripe in {len(data['integrations'])} results")
    
    def test_catalog_combined_filters(self):
        """Catalog should support combined category and search filters"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all?category=payments&q=pay")
        assert response.status_code == 200
        data = response.json()
        
        # All results should be in payments category and match search
        for item in data["integrations"]:
            assert item["cat"] == "payments", f"Integration {item['id']} should be in payments category"
            assert "pay" in item["name"].lower() or "pay" in item["desc"].lower(), f"Integration {item['id']} should match search 'pay'"
        print(f"PASS: Combined filters work - returned {len(data['integrations'])} results")


class TestMarketplaceInstallFlow:
    """Test install/toggle/sync/uninstall flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Clean up test integration if exists
        self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/test-property/TEST_kayak")
    
    def test_install_integration(self):
        """Install should create integration record with status=connected"""
        response = self.session.post(f"{BASE_URL}/api/marketplace/install/test-property/kayak", json={})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") == True, "Install should return ok=True"
        assert "installed" in data, "Install should return installed object"
        assert data["installed"]["status"] == "connected", f"Status should be 'connected', got {data['installed']['status']}"
        assert data["installed"]["enabled"] == True, "Enabled should be True after install"
        assert data["installed"]["integration_id"] == "kayak", "Integration ID should match"
        print(f"PASS: Install returns status=connected, enabled=True")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/test-property/kayak")
    
    def test_install_invalid_integration(self):
        """Install should return 404 for invalid integration ID"""
        response = self.session.post(f"{BASE_URL}/api/marketplace/install/test-property/invalid-integration-xyz", json={})
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Install returns 404 for invalid integration")
    
    def test_catalog_reflects_installed_state(self):
        """Catalog should show installed=true after install"""
        # Install
        self.session.post(f"{BASE_URL}/api/marketplace/install/test-property/trivago", json={})
        
        # Check catalog
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/test-property?q=trivago")
        assert response.status_code == 200
        data = response.json()
        
        trivago = next((i for i in data["integrations"] if i["id"] == "trivago"), None)
        assert trivago is not None, "Trivago should be in catalog"
        assert trivago["installed"] == True, "Trivago should show installed=True"
        assert trivago["enabled"] == True, "Trivago should show enabled=True"
        assert trivago["status"] == "connected", "Trivago should show status=connected"
        print("PASS: Catalog reflects installed state correctly")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/test-property/trivago")
    
    def test_toggle_integration(self):
        """Toggle should flip enabled state"""
        # Install first
        self.session.post(f"{BASE_URL}/api/marketplace/install/test-property/hostelworld", json={})
        
        # Toggle (should disable)
        response = self.session.post(f"{BASE_URL}/api/marketplace/toggle/test-property/hostelworld")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True, "Toggle should return ok=True"
        assert data.get("enabled") == False, "First toggle should disable (enabled=False)"
        print("PASS: Toggle disables integration")
        
        # Toggle again (should enable)
        response = self.session.post(f"{BASE_URL}/api/marketplace/toggle/test-property/hostelworld")
        assert response.status_code == 200
        data = response.json()
        assert data.get("enabled") == True, "Second toggle should enable (enabled=True)"
        print("PASS: Toggle enables integration")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/test-property/hostelworld")
    
    def test_toggle_not_installed(self):
        """Toggle should return 404 for not installed integration"""
        response = self.session.post(f"{BASE_URL}/api/marketplace/toggle/test-property/not-installed-xyz")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Toggle returns 404 for not installed integration")
    
    def test_sync_integration(self):
        """Sync should update last_sync timestamp"""
        # Install first
        self.session.post(f"{BASE_URL}/api/marketplace/install/test-property/trip-com", json={})
        time.sleep(0.1)  # Small delay to ensure different timestamp
        
        # Sync
        response = self.session.post(f"{BASE_URL}/api/marketplace/sync/test-property/trip-com")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") == True, "Sync should return ok=True"
        assert "last_sync" in data, "Sync should return last_sync timestamp"
        print(f"PASS: Sync returns last_sync={data['last_sync']}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/test-property/trip-com")
    
    def test_uninstall_integration(self):
        """Uninstall should remove integration record"""
        # Install first
        self.session.post(f"{BASE_URL}/api/marketplace/install/test-property/despegar", json={})
        
        # Uninstall
        response = self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/test-property/despegar")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("uninstalled") == True, "Uninstall should return uninstalled=True"
        print("PASS: Uninstall returns uninstalled=True")
        
        # Verify catalog shows not installed
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/test-property?q=despegar")
        data = response.json()
        despegar = next((i for i in data["integrations"] if i["id"] == "despegar"), None)
        assert despegar is not None, "Despegar should be in catalog"
        assert despegar["installed"] == False, "Despegar should show installed=False after uninstall"
        print("PASS: Catalog reflects uninstalled state")
    
    def test_uninstall_not_installed(self):
        """Uninstall should return 404 for not installed integration"""
        response = self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/test-property/not-installed-abc")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Uninstall returns 404 for not installed integration")


class TestMarketplaceTotalInstalled:
    """Test total_installed count accuracy"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_total_installed_increases_after_install(self):
        """total_installed should increase after installing"""
        # Get initial count
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/count-test-property")
        initial_count = response.json()["total_installed"]
        
        # Install
        self.session.post(f"{BASE_URL}/api/marketplace/install/count-test-property/agoda", json={})
        
        # Get new count
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/count-test-property")
        new_count = response.json()["total_installed"]
        
        assert new_count == initial_count + 1, f"Expected {initial_count + 1}, got {new_count}"
        print(f"PASS: total_installed increased from {initial_count} to {new_count}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/count-test-property/agoda")
    
    def test_total_installed_decreases_after_uninstall(self):
        """total_installed should decrease after uninstalling"""
        # Install first
        self.session.post(f"{BASE_URL}/api/marketplace/install/count-test-property/vrbo", json={})
        
        # Get count after install
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/count-test-property")
        count_after_install = response.json()["total_installed"]
        
        # Uninstall
        self.session.delete(f"{BASE_URL}/api/marketplace/uninstall/count-test-property/vrbo")
        
        # Get count after uninstall
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/count-test-property")
        count_after_uninstall = response.json()["total_installed"]
        
        assert count_after_uninstall == count_after_install - 1, f"Expected {count_after_install - 1}, got {count_after_uninstall}"
        print(f"PASS: total_installed decreased from {count_after_install} to {count_after_uninstall}")


class TestMarketplaceCategories:
    """Test category-specific functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200
        token = response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_all_17_categories_present(self):
        """All 17 categories should be present"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200
        data = response.json()
        
        expected_categories = [
            "ota", "payments", "channel", "revenue", "messaging", "ai", "reviews",
            "locks", "accounting", "pos", "analytics", "ops", "marketing",
            "productivity", "storage", "identity", "compliance"
        ]
        
        actual_ids = [c["id"] for c in data["categories"]]
        for cat_id in expected_categories:
            assert cat_id in actual_ids, f"Category {cat_id} should be present"
        
        print(f"PASS: All 17 categories present: {actual_ids}")
    
    def test_category_counts_are_accurate(self):
        """Category counts should match actual integrations"""
        response = self.session.get(f"{BASE_URL}/api/marketplace/catalog/all")
        assert response.status_code == 200
        data = response.json()
        
        # Count integrations per category
        cat_counts = {}
        for item in data["integrations"]:
            cat = item["cat"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        
        # Verify counts match
        for cat in data["categories"]:
            expected = cat_counts.get(cat["id"], 0)
            actual = cat["count"]
            assert actual == expected, f"Category {cat['id']} count mismatch: expected {expected}, got {actual}"
        
        print(f"PASS: All category counts are accurate")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
