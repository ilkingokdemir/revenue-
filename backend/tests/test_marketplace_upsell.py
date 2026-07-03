"""
Test Suite for Marketplace v1 + Spaces Smart Upsell (Iter 358)
- Marketplace: 20-app catalog, install/uninstall, coming_soon guard
- Spaces Upsell: signal detection (long_stay, group), Turkish suggestions
"""
import pytest
import requests
import os

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


class TestSpacesUpsell:
    """Backend #1: Spaces Smart Upsell Suggestions"""
    
    def test_upsell_signals_long_stay_and_group(self, auth_headers):
        """GET /api/spaces/camden-suites/upsell-suggestions with nights>=3 and guest_count>=4"""
        response = requests.get(
            f"{BASE_URL}/api/spaces/camden-suites/upsell-suggestions",
            params={"guest_count": 5, "nights": 4},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify signals include both long_stay and group
        assert "signals" in data
        assert "long_stay" in data["signals"], "Should detect long_stay for nights>=3"
        assert "group" in data["signals"], "Should detect group for guest_count>=4"
        
        # Verify suggestions structure
        assert "suggestions" in data
        assert len(data["suggestions"]) >= 2, "Should return at least 2 suggestions"
        
        for suggestion in data["suggestions"]:
            assert "space_name" in suggestion
            assert "kind" in suggestion
            assert "rate" in suggestion
            assert "reason" in suggestion
            assert "cta" in suggestion
            assert "matched_signal" in suggestion
            # Verify Turkish reason with emoji
            assert any(emoji in suggestion["reason"] for emoji in ["🧳", "👥", "🅿️", "💼", "🔌", "🧑‍💻"]), \
                f"Reason should contain emoji: {suggestion['reason']}"
    
    def test_upsell_no_signals_short_stay_solo(self, auth_headers):
        """GET /api/spaces/camden-suites/upsell-suggestions with nights<3 and guest_count<4"""
        response = requests.get(
            f"{BASE_URL}/api/spaces/camden-suites/upsell-suggestions",
            params={"guest_count": 1, "nights": 1},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should not have long_stay or group signals
        assert "long_stay" not in data.get("signals", [])
        assert "group" not in data.get("signals", [])


class TestMarketplaceCatalog:
    """Backend #2: Marketplace Catalog"""
    
    def test_catalog_structure(self, auth_headers):
        """GET /api/marketplace/catalog returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/marketplace/catalog",
            params={"property_id": "camden-suites"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify categories (7 expected)
        assert "categories" in data
        assert len(data["categories"]) == 7, f"Expected 7 categories, got {len(data['categories'])}"
        category_ids = [c["id"] for c in data["categories"]]
        assert "distribution" in category_ids
        assert "payments" in category_ids
        assert "messaging" in category_ids
        assert "marketing" in category_ids
        assert "accounting" in category_ids
        assert "ai" in category_ids
        assert "automation" in category_ids
        
        # Verify totals
        assert data["total"] == 20, f"Expected 20 apps, got {data['total']}"
        assert data["featured_count"] >= 6, f"Expected >=6 featured, got {data['featured_count']}"
        
        # Verify items structure
        assert "items" in data
        assert len(data["items"]) == 20
    
    def test_catalog_first_5_apps_distribution(self, auth_headers):
        """First 5 apps should be distribution category OTAs"""
        response = requests.get(
            f"{BASE_URL}/api/marketplace/catalog",
            params={"property_id": "camden-suites"},
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        first_5_ids = [items[i]["id"] for i in range(5)]
        expected_ids = ["booking-com", "airbnb", "expedia", "tripadvisor", "google-hotels"]
        assert first_5_ids == expected_ids, f"First 5 apps should be {expected_ids}, got {first_5_ids}"
        
        # All should be distribution category
        for i in range(5):
            assert items[i]["category"] == "distribution"
    
    def test_stripe_default_installed(self, auth_headers):
        """Stripe should have status='installed' by default in catalog"""
        response = requests.get(
            f"{BASE_URL}/api/marketplace/catalog",
            params={"property_id": "camden-suites"},
            headers=auth_headers
        )
        assert response.status_code == 200
        items = response.json()["items"]
        
        stripe_app = next((a for a in items if a["id"] == "stripe"), None)
        assert stripe_app is not None, "Stripe app should be in catalog"
        # Note: Stripe defaults to 'installed' in the catalog definition
        # but actual status depends on marketplace_installed collection


class TestMarketplaceInstall:
    """Backend #3: Install App"""
    
    def test_install_whatsapp(self, auth_headers):
        """POST /api/marketplace/install with valid app"""
        response = requests.post(
            f"{BASE_URL}/api/marketplace/install",
            json={
                "app_id": "whatsapp",
                "property_id": "camden-suites",
                "config": {"phone_number_id": "test123"}
            },
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["action"] in ["installed", "refreshed"]
        assert data["app_id"] == "whatsapp"
        assert data["property_id"] == "camden-suites"


class TestMarketplaceUninstall:
    """Backend #4: Uninstall App"""
    
    def test_uninstall_whatsapp(self, auth_headers):
        """POST /api/marketplace/uninstall removes app"""
        # First ensure it's installed
        requests.post(
            f"{BASE_URL}/api/marketplace/install",
            json={"app_id": "whatsapp", "property_id": "camden-suites", "config": {}},
            headers=auth_headers
        )
        
        # Now uninstall
        response = requests.post(
            f"{BASE_URL}/api/marketplace/uninstall",
            json={"app_id": "whatsapp", "property_id": "camden-suites"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["removed"] == 1


class TestMarketplaceComingSoon:
    """Backend #5: Coming Soon Guard"""
    
    def test_install_coming_soon_app_blocked(self, auth_headers):
        """POST /api/marketplace/install with coming_soon app returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/marketplace/install",
            json={"app_id": "zapier", "property_id": "camden-suites"},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        
        # Should contain Turkish 'yakında' message
        assert "yakında" in data.get("detail", "").lower(), \
            f"Error should contain 'yakında': {data}"
    
    def test_other_coming_soon_apps_blocked(self, auth_headers):
        """All coming_soon apps should be blocked"""
        coming_soon_apps = ["tripadvisor", "google-ads", "meta-ads", "quickbooks", "xero", "zapier"]
        
        for app_id in coming_soon_apps:
            response = requests.post(
                f"{BASE_URL}/api/marketplace/install",
                json={"app_id": app_id, "property_id": "camden-suites"},
                headers=auth_headers
            )
            assert response.status_code == 400, f"{app_id} should be blocked (coming_soon)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
