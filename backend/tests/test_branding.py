"""
Test suite for White-Label Branding feature
Tests: GET/PUT /api/branding, POST/DELETE /api/branding/logo
"""
import pytest
import requests
import os
import base64

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBrandingAPI:
    """Tests for branding endpoints"""
    
    def test_get_branding_returns_default_settings(self):
        """GET /api/branding should return default branding settings"""
        response = requests.get(f"{BASE_URL}/api/branding")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify default fields exist
        assert "app_name" in data, "Missing app_name field"
        assert "subtitle" in data, "Missing subtitle field"
        assert "primary_color" in data, "Missing primary_color field"
        assert "accent_color" in data, "Missing accent_color field"
        assert "powered_by_text" in data, "Missing powered_by_text field"
        assert "powered_by_visible" in data, "Missing powered_by_visible field"
        
        # Verify default values
        assert data["app_name"] == "Review Hub" or isinstance(data["app_name"], str)
        assert data["primary_color"].startswith("#"), "Primary color should be hex"
        assert data["accent_color"].startswith("#"), "Accent color should be hex"
        print(f"✓ GET /api/branding returns valid branding settings: {data['app_name']}")
    
    def test_update_branding_app_name(self):
        """PUT /api/branding should update app_name"""
        update_data = {"app_name": "TEST_MyHotel Reviews"}
        response = requests.put(f"{BASE_URL}/api/branding", json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["app_name"] == "TEST_MyHotel Reviews", f"Expected 'TEST_MyHotel Reviews', got {data['app_name']}"
        print("✓ PUT /api/branding updates app_name successfully")
        
        # Verify persistence with GET
        get_response = requests.get(f"{BASE_URL}/api/branding")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["app_name"] == "TEST_MyHotel Reviews", "app_name not persisted"
        print("✓ app_name persisted in database")
    
    def test_update_branding_subtitle(self):
        """PUT /api/branding should update subtitle"""
        update_data = {"subtitle": "TEST_Your trusted review management platform"}
        response = requests.put(f"{BASE_URL}/api/branding", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["subtitle"] == "TEST_Your trusted review management platform"
        print("✓ PUT /api/branding updates subtitle successfully")
    
    def test_update_branding_primary_color(self):
        """PUT /api/branding should update primary_color"""
        update_data = {"primary_color": "#1E3A5F"}
        response = requests.put(f"{BASE_URL}/api/branding", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["primary_color"] == "#1E3A5F", f"Expected '#1E3A5F', got {data['primary_color']}"
        print("✓ PUT /api/branding updates primary_color successfully")
    
    def test_update_branding_accent_color(self):
        """PUT /api/branding should update accent_color"""
        update_data = {"accent_color": "#4ECDC4"}
        response = requests.put(f"{BASE_URL}/api/branding", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["accent_color"] == "#4ECDC4", f"Expected '#4ECDC4', got {data['accent_color']}"
        print("✓ PUT /api/branding updates accent_color successfully")
    
    def test_update_branding_powered_by(self):
        """PUT /api/branding should update powered_by_text and powered_by_visible"""
        update_data = {
            "powered_by_text": "TEST_HotelTech Solutions",
            "powered_by_visible": True
        }
        response = requests.put(f"{BASE_URL}/api/branding", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["powered_by_text"] == "TEST_HotelTech Solutions"
        assert data["powered_by_visible"] == True
        print("✓ PUT /api/branding updates powered_by settings successfully")
    
    def test_update_branding_multiple_fields(self):
        """PUT /api/branding should update multiple fields at once"""
        update_data = {
            "app_name": "TEST_Grand Hotel Reviews",
            "subtitle": "TEST_Excellence in hospitality",
            "primary_color": "#003366",
            "accent_color": "#F0C040",
            "powered_by_text": "TEST_GrandTech",
            "powered_by_visible": True
        }
        response = requests.put(f"{BASE_URL}/api/branding", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["app_name"] == "TEST_Grand Hotel Reviews"
        assert data["subtitle"] == "TEST_Excellence in hospitality"
        assert data["primary_color"] == "#003366"
        assert data["accent_color"] == "#F0C040"
        assert data["powered_by_text"] == "TEST_GrandTech"
        assert data["powered_by_visible"] == True
        print("✓ PUT /api/branding updates multiple fields successfully")
    
    def test_upload_logo_valid_image(self):
        """POST /api/branding/logo should accept valid image and return base64 data URI"""
        # Create a minimal valid PNG image (1x1 pixel red)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {"file": ("test_logo.png", png_data, "image/png")}
        response = requests.post(f"{BASE_URL}/api/branding/logo", files=files)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "logo_url" in data, "Response should contain logo_url"
        assert data["logo_url"].startswith("data:image/png;base64,"), "logo_url should be base64 data URI"
        print("✓ POST /api/branding/logo accepts image and returns base64 data URI")
        
        # Verify logo persisted in branding settings
        get_response = requests.get(f"{BASE_URL}/api/branding")
        assert get_response.status_code == 200
        branding = get_response.json()
        assert branding["logo_url"] is not None, "logo_url should be set in branding"
        assert branding["logo_url"].startswith("data:image/"), "logo_url should be data URI"
        print("✓ Logo persisted in branding settings")
    
    def test_upload_logo_rejects_non_image(self):
        """POST /api/branding/logo should reject non-image files"""
        files = {"file": ("test.txt", b"This is not an image", "text/plain")}
        response = requests.post(f"{BASE_URL}/api/branding/logo", files=files)
        assert response.status_code == 400, f"Expected 400 for non-image, got {response.status_code}"
        print("✓ POST /api/branding/logo rejects non-image files")
    
    def test_delete_logo(self):
        """DELETE /api/branding/logo should remove the logo"""
        # First upload a logo
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        files = {"file": ("test_logo.png", png_data, "image/png")}
        requests.post(f"{BASE_URL}/api/branding/logo", files=files)
        
        # Now delete it
        response = requests.delete(f"{BASE_URL}/api/branding/logo")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data, "Response should contain message"
        print("✓ DELETE /api/branding/logo removes logo successfully")
        
        # Verify logo is removed
        get_response = requests.get(f"{BASE_URL}/api/branding")
        branding = get_response.json()
        assert branding["logo_url"] is None, "logo_url should be None after deletion"
        print("✓ Logo removed from branding settings")
    
    def test_branding_updated_at_field(self):
        """PUT /api/branding should update the updated_at timestamp"""
        update_data = {"app_name": "TEST_Timestamp Check"}
        response = requests.put(f"{BASE_URL}/api/branding", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "updated_at" in data, "Response should contain updated_at"
        print(f"✓ Branding has updated_at timestamp: {data.get('updated_at')}")


class TestBrandingRegression:
    """Regression tests to ensure other features still work"""
    
    def test_reviews_endpoint_still_works(self):
        """GET /api/reviews should still work after branding changes"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Reviews endpoint failed: {response.status_code}"
        print("✓ GET /api/reviews still works (regression)")
    
    def test_analytics_endpoint_still_works(self):
        """GET /api/analytics/dashboard should still work"""
        response = requests.get(f"{BASE_URL}/api/analytics/dashboard")
        assert response.status_code == 200, f"Analytics endpoint failed: {response.status_code}"
        print("✓ GET /api/analytics/dashboard still works (regression)")
    
    def test_integrations_endpoint_still_works(self):
        """GET /api/integrations should still work"""
        response = requests.get(f"{BASE_URL}/api/integrations")
        assert response.status_code == 200, f"Integrations endpoint failed: {response.status_code}"
        print("✓ GET /api/integrations still works (regression)")
    
    def test_templates_endpoint_still_works(self):
        """GET /api/templates should still work"""
        response = requests.get(f"{BASE_URL}/api/templates")
        assert response.status_code == 200, f"Templates endpoint failed: {response.status_code}"
        print("✓ GET /api/templates still works (regression)")


class TestBrandingCleanup:
    """Cleanup test data and restore defaults"""
    
    def test_restore_default_branding(self):
        """Restore default branding settings after tests"""
        default_data = {
            "app_name": "Review Hub",
            "subtitle": "Manage all your guest reviews in one place",
            "primary_color": "#3E5245",
            "accent_color": "#D4A373",
            "powered_by_text": "",
            "powered_by_visible": False
        }
        response = requests.put(f"{BASE_URL}/api/branding", json=default_data)
        assert response.status_code == 200
        
        # Delete any uploaded logo
        requests.delete(f"{BASE_URL}/api/branding/logo")
        
        print("✓ Default branding settings restored")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
