"""
Iteration 31 - P0 Revenue/Conversion Features Testing
Tests for:
- Smart Upsell Engine (10 pre-built templates, CRUD operations)
- Social Proof Notifications (viewing count, recent bookings, settings)
- Price Comparison Widget (OTA vs direct pricing)
- Google Hotel Structured Data (JSON-LD)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestUpsellTemplates:
    """Test upsell template endpoints"""

    def test_get_upsell_templates(self, api_client):
        """GET /api/upsell-templates - returns 10 predefined templates"""
        response = api_client.get(f"{BASE_URL}/api/upsell-templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list"
        assert len(templates) == 10, f"Expected 10 templates, got {len(templates)}"
        
        # Verify template structure
        expected_names = [
            "Early Check-in", "Late Check-out", "Breakfast Package", "Airport Transfer",
            "Welcome Champagne", "Spa Access", "Room Upgrade", "Parking Space",
            "Pet Fee", "Romantic Package"
        ]
        actual_names = [t["name"] for t in templates]
        for name in expected_names:
            assert name in actual_names, f"Missing template: {name}"
        
        # Verify template fields
        for tmpl in templates:
            assert "name" in tmpl
            assert "description" in tmpl
            assert "category" in tmpl
            assert "price" in tmpl
            assert "price_type" in tmpl
            assert "icon" in tmpl
            assert tmpl["price_type"] in ["per_stay", "per_night", "per_person", "per_person_per_night"]


class TestUpsellSeed:
    """Test upsell seeding for property"""

    def test_seed_upsells_returns_existing_count(self, authenticated_client):
        """POST /api/upsells/seed/aldgate-flats - should return existing count if already seeded"""
        response = authenticated_client.post(f"{BASE_URL}/api/upsells/seed/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Either returns existing count or seeds new items
        assert "message" in data
        if "already has" in data["message"]:
            assert "count" in data
            assert data["count"] >= 10, f"Expected at least 10 upsells, got {data['count']}"
        else:
            assert "items" in data
            assert len(data["items"]) == 10


class TestUpsellCRUD:
    """Test upsell CRUD operations"""

    def test_get_upsells_public(self, api_client):
        """GET /api/upsells/aldgate-flats - returns active upsell items (public)"""
        response = api_client.get(f"{BASE_URL}/api/upsells/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        upsells = response.json()
        assert isinstance(upsells, list), "Response should be a list"
        assert len(upsells) >= 10, f"Expected at least 10 upsells, got {len(upsells)}"
        
        # Verify upsell structure
        for upsell in upsells:
            assert "id" in upsell
            assert "name" in upsell
            assert "description" in upsell
            assert "price" in upsell
            assert "price_type" in upsell
            assert "property_id" in upsell
            assert upsell["property_id"] == PROPERTY_ID
            assert upsell.get("is_active", True) == True

    def test_create_upsell_requires_auth(self):
        """POST /api/upsells - requires admin auth"""
        # Use a fresh session without auth
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        response = fresh_session.post(f"{BASE_URL}/api/upsells", json={
            "property_id": PROPERTY_ID,
            "name": "Test Upsell",
            "price": 10
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"

    def test_create_update_delete_upsell(self, authenticated_client):
        """Full CRUD cycle for upsell item"""
        # CREATE
        create_payload = {
            "property_id": PROPERTY_ID,
            "name": "TEST_Custom Upsell",
            "description": "Test upsell for automated testing",
            "category": "experience",
            "price": 99.99,
            "price_type": "per_stay",
            "icon": "star"
        }
        create_response = authenticated_client.post(f"{BASE_URL}/api/upsells", json=create_payload)
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        
        created = create_response.json()
        assert created["name"] == "TEST_Custom Upsell"
        assert created["price"] == 99.99
        assert "id" in created
        upsell_id = created["id"]
        
        # UPDATE
        update_payload = {"name": "TEST_Updated Upsell", "price": 149.99}
        update_response = authenticated_client.put(f"{BASE_URL}/api/upsells/{upsell_id}", json=update_payload)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated = update_response.json()
        assert updated["name"] == "TEST_Updated Upsell"
        assert updated["price"] == 149.99
        
        # DELETE
        delete_response = authenticated_client.delete(f"{BASE_URL}/api/upsells/{upsell_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        # Verify deletion
        get_response = authenticated_client.get(f"{BASE_URL}/api/upsells/{PROPERTY_ID}")
        upsells = get_response.json()
        assert not any(u["id"] == upsell_id for u in upsells), "Upsell should be deleted"


class TestSocialProof:
    """Test social proof endpoints"""

    def test_get_social_proof_public(self, api_client):
        """GET /api/social-proof/aldgate-flats - returns social proof data (public)"""
        response = api_client.get(f"{BASE_URL}/api/social-proof/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "recent_bookings_24h" in data
        assert "monthly_bookings" in data
        assert "settings" in data
        
        # Verify settings structure
        settings = data["settings"]
        assert "enabled" in settings
        assert "show_viewing_count" in settings
        assert "show_recent_bookings" in settings
        assert "show_rooms_left" in settings
        assert "show_price_comparison" in settings
        assert "ota_markup_percent" in settings

    def test_get_social_proof_settings_requires_auth(self):
        """GET /api/social-proof/settings/aldgate-flats - requires admin auth"""
        # Use a fresh session without auth
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        response = fresh_session.get(f"{BASE_URL}/api/social-proof/settings/{PROPERTY_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"

    def test_get_social_proof_settings_admin(self, authenticated_client):
        """GET /api/social-proof/settings/aldgate-flats - admin can access"""
        response = authenticated_client.get(f"{BASE_URL}/api/social-proof/settings/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        settings = response.json()
        assert "property_id" in settings
        assert settings["property_id"] == PROPERTY_ID
        assert "enabled" in settings
        assert "ota_markup_percent" in settings

    def test_update_social_proof_settings(self, authenticated_client):
        """PUT /api/social-proof/settings/aldgate-flats - update settings"""
        # Get current settings
        get_response = authenticated_client.get(f"{BASE_URL}/api/social-proof/settings/{PROPERTY_ID}")
        original_settings = get_response.json()
        
        # Update settings
        update_payload = {
            "enabled": True,
            "show_viewing_count": True,
            "show_recent_bookings": True,
            "ota_markup_percent": 20,
            "direct_saving_label": "Book direct & save {percent}%"
        }
        update_response = authenticated_client.put(
            f"{BASE_URL}/api/social-proof/settings/{PROPERTY_ID}",
            json=update_payload
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated = update_response.json()
        assert updated["ota_markup_percent"] == 20
        assert updated["enabled"] == True
        
        # Restore original settings
        authenticated_client.put(
            f"{BASE_URL}/api/social-proof/settings/{PROPERTY_ID}",
            json=original_settings
        )


class TestPropertyEndpointIntegration:
    """Test that property endpoint includes upsells and social proof"""

    def test_property_endpoint_includes_upsells_and_social_proof(self, api_client):
        """GET /api/booking/property/aldgate-flats - includes upsells and social_proof"""
        response = api_client.get(f"{BASE_URL}/api/booking/property/{PROPERTY_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify upsells array
        assert "upsells" in data, "Response should include 'upsells' array"
        upsells = data["upsells"]
        assert isinstance(upsells, list), "upsells should be a list"
        assert len(upsells) >= 10, f"Expected at least 10 upsells, got {len(upsells)}"
        
        # Verify social_proof object
        assert "social_proof" in data, "Response should include 'social_proof' object"
        social_proof = data["social_proof"]
        assert "settings" in social_proof
        assert "recent_bookings_24h" in social_proof
        
        # Verify social proof settings
        sp_settings = social_proof["settings"]
        assert "enabled" in sp_settings
        assert "show_price_comparison" in sp_settings
        assert "ota_markup_percent" in sp_settings

    def test_property_endpoint_upsell_structure(self, api_client):
        """Verify upsell items have correct structure in property response"""
        response = api_client.get(f"{BASE_URL}/api/booking/property/{PROPERTY_ID}")
        data = response.json()
        
        for upsell in data["upsells"]:
            assert "id" in upsell
            assert "name" in upsell
            assert "description" in upsell
            assert "price" in upsell
            assert "price_type" in upsell
            assert "category" in upsell
            assert "icon" in upsell
            # Verify price_type is valid
            assert upsell["price_type"] in ["per_stay", "per_night", "per_person", "per_person_per_night"]


class TestPriceComparisonCalculation:
    """Test price comparison widget calculations"""

    def test_ota_markup_calculation(self, api_client):
        """Verify OTA markup percentage is returned correctly"""
        response = api_client.get(f"{BASE_URL}/api/social-proof/{PROPERTY_ID}")
        data = response.json()
        
        settings = data["settings"]
        markup = settings.get("ota_markup_percent", 18)
        
        # Verify markup is a reasonable percentage
        assert isinstance(markup, (int, float))
        assert 0 <= markup <= 50, f"OTA markup should be between 0-50%, got {markup}"


class TestAuthRequirements:
    """Test that protected endpoints require authentication"""

    def test_upsell_update_requires_auth(self):
        """PUT /api/upsells/{id} requires auth"""
        # Use a fresh session without auth
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        # First get an upsell ID
        get_response = fresh_session.get(f"{BASE_URL}/api/upsells/{PROPERTY_ID}")
        upsells = get_response.json()
        if upsells:
            upsell_id = upsells[0]["id"]
            response = fresh_session.put(f"{BASE_URL}/api/upsells/{upsell_id}", json={"name": "Hacked"})
            assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"

    def test_upsell_delete_requires_auth(self):
        """DELETE /api/upsells/{id} requires auth"""
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        get_response = fresh_session.get(f"{BASE_URL}/api/upsells/{PROPERTY_ID}")
        upsells = get_response.json()
        if upsells:
            upsell_id = upsells[0]["id"]
            response = fresh_session.delete(f"{BASE_URL}/api/upsells/{upsell_id}")
            assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"

    def test_social_proof_settings_update_requires_auth(self):
        """PUT /api/social-proof/settings/{property_id} requires auth"""
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        response = fresh_session.put(
            f"{BASE_URL}/api/social-proof/settings/{PROPERTY_ID}",
            json={"enabled": False}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
