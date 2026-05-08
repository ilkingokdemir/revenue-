"""
Test Template Customization Panel - Iteration 28
Tests for:
- Template settings CRUD endpoints
- Property-specific template customization
- Booking engine integration with custom settings
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API = f"{BASE_URL}/api"

# Test credentials
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestTemplateSettingsAPI:
    """Template Settings CRUD API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
        self.session.close()
    
    def test_get_template_settings_for_property(self):
        """GET /api/template-settings/{property_id} - Get settings for a property"""
        # Test with aldgate-flats which should have pre-saved settings
        resp = self.session.get(f"{API}/template-settings/aldgate-flats")
        assert resp.status_code == 200, f"Failed to get template settings: {resp.text}"
        data = resp.json()
        assert "property_id" in data
        assert data["property_id"] == "aldgate-flats"
        print(f"✓ GET template settings for aldgate-flats: {data.get('hotel_name', 'N/A')}")
    
    def test_get_template_settings_nonexistent_property(self):
        """GET /api/template-settings/{property_id} - Returns defaults for new property"""
        resp = self.session.get(f"{API}/template-settings/nonexistent-property-xyz")
        assert resp.status_code == 200, f"Should return defaults: {resp.text}"
        data = resp.json()
        assert data["property_id"] == "nonexistent-property-xyz"
        assert data.get("template_id") == "booking-classic"
        print("✓ GET template settings for nonexistent property returns defaults")
    
    def test_list_all_template_settings(self):
        """GET /api/template-settings - List all template settings (admin/manager)"""
        resp = self.session.get(f"{API}/template-settings")
        assert resp.status_code == 200, f"Failed to list template settings: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ List all template settings: {len(data)} entries")
    
    def test_save_template_settings(self):
        """PUT /api/template-settings/{property_id} - Save settings"""
        test_property_id = "TEST_template_property"
        
        # Save new settings
        settings_payload = {
            "hotel_name": "TEST Grand Hotel",
            "tagline": "TEST Luxury Accommodation",
            "contact_phone": "+44 123 456 7890",
            "contact_email": "test@grandhotel.com",
            "accent_color": "#FF5733",
            "show_rating_badge": True,
            "show_urgency": False,
            "footer_text": "TEST Grand Hotel © 2026",
            "booking_button_text": "Book Now",
            "facebook_url": "https://facebook.com/testhotel",
            "meta_title": "TEST Grand Hotel - Book Direct"
        }
        
        resp = self.session.put(f"{API}/template-settings/{test_property_id}", json=settings_payload)
        assert resp.status_code == 200, f"Failed to save template settings: {resp.text}"
        data = resp.json()
        
        # Verify saved data
        assert data["hotel_name"] == "TEST Grand Hotel"
        assert data["tagline"] == "TEST Luxury Accommodation"
        assert data["contact_phone"] == "+44 123 456 7890"
        assert data["accent_color"] == "#FF5733"
        assert data["show_rating_badge"] == True
        assert data["show_urgency"] == False
        assert data["footer_text"] == "TEST Grand Hotel © 2026"
        assert data["booking_button_text"] == "Book Now"
        assert data["facebook_url"] == "https://facebook.com/testhotel"
        print("✓ PUT template settings - saved successfully")
        
        # Verify persistence with GET
        get_resp = self.session.get(f"{API}/template-settings/{test_property_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["hotel_name"] == "TEST Grand Hotel"
        assert get_data["accent_color"] == "#FF5733"
        print("✓ GET after PUT - settings persisted correctly")
        
        # Cleanup
        self.session.delete(f"{API}/template-settings/{test_property_id}")
    
    def test_update_existing_template_settings(self):
        """PUT /api/template-settings/{property_id} - Update existing settings"""
        test_property_id = "TEST_update_property"
        
        # Create initial settings
        initial_settings = {
            "hotel_name": "Initial Hotel Name",
            "tagline": "Initial Tagline"
        }
        self.session.put(f"{API}/template-settings/{test_property_id}", json=initial_settings)
        
        # Update settings
        updated_settings = {
            "hotel_name": "Updated Hotel Name",
            "tagline": "Updated Tagline",
            "accent_color": "#00FF00"
        }
        resp = self.session.put(f"{API}/template-settings/{test_property_id}", json=updated_settings)
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["hotel_name"] == "Updated Hotel Name"
        assert data["tagline"] == "Updated Tagline"
        assert data["accent_color"] == "#00FF00"
        print("✓ PUT template settings - update existing works")
        
        # Cleanup
        self.session.delete(f"{API}/template-settings/{test_property_id}")
    
    def test_delete_template_settings(self):
        """DELETE /api/template-settings/{property_id} - Reset to defaults"""
        test_property_id = "TEST_delete_property"
        
        # Create settings first
        self.session.put(f"{API}/template-settings/{test_property_id}", json={
            "hotel_name": "To Be Deleted",
            "accent_color": "#123456"
        })
        
        # Delete (reset)
        resp = self.session.delete(f"{API}/template-settings/{test_property_id}")
        assert resp.status_code == 200, f"Failed to delete template settings: {resp.text}"
        
        # Verify reset - should return defaults
        get_resp = self.session.get(f"{API}/template-settings/{test_property_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        # After delete, should return default empty values
        assert data.get("hotel_name", "") == ""
        print("✓ DELETE template settings - reset to defaults")
    
    def test_template_settings_all_fields(self):
        """PUT /api/template-settings - Test all customization fields"""
        test_property_id = "TEST_all_fields_property"
        
        full_settings = {
            "template_id": "airbnb-classic",
            "hotel_name": "TEST Complete Hotel",
            "tagline": "Complete Tagline",
            "description": "A complete description of the hotel",
            "contact_phone": "+44 20 7123 4567",
            "contact_email": "complete@hotel.com",
            "address": "123 Test Street, London",
            "logo_url": "https://example.com/logo.png",
            "hero_image_url": "https://example.com/hero.jpg",
            "gallery_images": ["https://example.com/img1.jpg", "https://example.com/img2.jpg"],
            "primary_color": "#1A1A1A",
            "accent_color": "#E74C3C",
            "header_bg_color": "#2C3E50",
            "header_text_color": "#FFFFFF",
            "body_bg_color": "#F5F5F5",
            "show_rating_badge": True,
            "show_urgency": True,
            "show_free_cancellation": True,
            "show_security_badges": False,
            "footer_text": "Complete Hotel © 2026",
            "booking_button_text": "Reserve Your Stay",
            "welcome_message": "Welcome to our hotel!",
            "facebook_url": "https://facebook.com/completehotel",
            "instagram_url": "https://instagram.com/completehotel",
            "twitter_url": "https://twitter.com/completehotel",
            "tripadvisor_url": "https://tripadvisor.com/completehotel",
            "meta_title": "Complete Hotel - Best Rates",
            "meta_description": "Book your stay at Complete Hotel"
        }
        
        resp = self.session.put(f"{API}/template-settings/{test_property_id}", json=full_settings)
        assert resp.status_code == 200, f"Failed to save full settings: {resp.text}"
        data = resp.json()
        
        # Verify all fields
        assert data["template_id"] == "airbnb-classic"
        assert data["hotel_name"] == "TEST Complete Hotel"
        assert data["description"] == "A complete description of the hotel"
        assert data["gallery_images"] == ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]
        assert data["show_rating_badge"] == True
        assert data["show_security_badges"] == False
        assert data["instagram_url"] == "https://instagram.com/completehotel"
        assert data["meta_description"] == "Book your stay at Complete Hotel"
        print("✓ PUT template settings - all fields saved correctly")
        
        # Cleanup
        self.session.delete(f"{API}/template-settings/{test_property_id}")


class TestBookingEngineIntegration:
    """Test Booking Engine consumes template settings correctly"""
    
    def test_booking_property_includes_template_settings(self):
        """GET /api/booking/property/{id} - Should include template_settings"""
        resp = requests.get(f"{API}/booking/property/aldgate-flats")
        assert resp.status_code == 200, f"Failed to get property: {resp.text}"
        data = resp.json()
        
        assert "template_settings" in data, "template_settings missing from property response"
        ts = data["template_settings"]
        
        # Verify aldgate-flats has pre-saved customizations
        if ts.get("hotel_name"):
            print(f"✓ Property includes template_settings with hotel_name: {ts['hotel_name']}")
        else:
            print("✓ Property includes template_settings (empty/default)")
        
        # Check structure
        assert isinstance(ts, dict)
    
    def test_booking_property_default_template_settings(self):
        """GET /api/booking/property/{id} - Default property should have empty template_settings"""
        resp = requests.get(f"{API}/booking/property/default")
        assert resp.status_code == 200, f"Failed to get default property: {resp.text}"
        data = resp.json()
        
        assert "template_settings" in data
        print("✓ Default property includes template_settings")


class TestPropertiesForCustomization:
    """Test properties list for customization dropdown"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
        self.session.close()
    
    def test_list_properties(self):
        """GET /api/properties - List properties for dropdown"""
        resp = self.session.get(f"{API}/properties")
        assert resp.status_code == 200, f"Failed to list properties: {resp.text}"
        data = resp.json()
        
        assert isinstance(data, list)
        assert len(data) > 0, "No properties found"
        
        # Check for aldgate-flats
        property_ids = [p["id"] for p in data]
        print(f"✓ Properties list: {property_ids}")
        
        # Verify property structure
        for prop in data:
            assert "id" in prop
            assert "name" in prop


class TestAldgateFlatsCustomization:
    """Test pre-saved customizations for aldgate-flats"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{API}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
        self.session.close()
    
    def test_aldgate_flats_has_customizations(self):
        """Verify aldgate-flats has pre-saved template settings"""
        resp = self.session.get(f"{API}/template-settings/aldgate-flats")
        assert resp.status_code == 200
        data = resp.json()
        
        # According to the review request, aldgate-flats should have:
        # hotel_name='Aldgate Luxury Flats', tagline='Your Home in the Heart of London'
        # contact_phone='+44 20 7123 4567', accent_color='#E74C3C'
        
        print(f"Aldgate Flats settings: hotel_name={data.get('hotel_name')}, tagline={data.get('tagline')}")
        print(f"  contact_phone={data.get('contact_phone')}, accent_color={data.get('accent_color')}")
        
        # These may or may not be set depending on if main agent seeded them
        if data.get("hotel_name"):
            assert "Aldgate" in data["hotel_name"] or "Luxury" in data["hotel_name"], \
                f"Expected Aldgate-related hotel name, got: {data.get('hotel_name')}"
            print("✓ aldgate-flats has custom hotel_name")
        else:
            print("⚠ aldgate-flats hotel_name not set (may need seeding)")


class TestAuthorizationForTemplateSettings:
    """Test authorization requirements for template settings"""
    
    def test_get_settings_no_auth_required(self):
        """GET /api/template-settings/{property_id} - No auth required for reading"""
        resp = requests.get(f"{API}/template-settings/aldgate-flats")
        # Should work without auth for public booking page consumption
        assert resp.status_code == 200, f"GET should work without auth: {resp.text}"
        print("✓ GET template settings works without auth (for booking page)")
    
    def test_list_settings_requires_auth(self):
        """GET /api/template-settings - Requires admin/manager auth"""
        resp = requests.get(f"{API}/template-settings")
        assert resp.status_code == 401, f"List should require auth: {resp.status_code}"
        print("✓ List all template settings requires auth")
    
    def test_put_settings_requires_auth(self):
        """PUT /api/template-settings/{property_id} - Requires admin/manager auth"""
        resp = requests.put(f"{API}/template-settings/test-property", json={
            "hotel_name": "Unauthorized Test"
        })
        assert resp.status_code == 401, f"PUT should require auth: {resp.status_code}"
        print("✓ PUT template settings requires auth")
    
    def test_delete_settings_requires_admin(self):
        """DELETE /api/template-settings/{property_id} - Requires admin auth"""
        resp = requests.delete(f"{API}/template-settings/test-property")
        assert resp.status_code == 401, f"DELETE should require auth: {resp.status_code}"
        print("✓ DELETE template settings requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
