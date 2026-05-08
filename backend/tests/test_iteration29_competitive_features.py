"""
Iteration 29 - Competitive Features Testing
Tests for: Promo Codes, Add-ons, Hotel Policies, Property Facilities, Amenity/Facility Catalogs
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROPERTY_ID = "aldgate-flats"

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_admin_login(self, auth_token):
        """Test admin login returns valid token"""
        assert auth_token is not None
        assert len(auth_token) > 50


class TestAmenityCatalog:
    """Amenity catalog API tests"""
    
    def test_get_amenity_catalog(self):
        """GET /api/amenities/catalog - returns full categorized amenity catalog"""
        response = requests.get(f"{BASE_URL}/api/amenities/catalog")
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected categories exist
        expected_categories = ["bathroom", "bedroom", "kitchen", "technology", "entertainment", "business", "safety", "accessibility", "wellness", "services"]
        for cat in expected_categories:
            assert cat in data, f"Missing category: {cat}"
            assert "label" in data[cat], f"Category {cat} missing label"
            assert "items" in data[cat], f"Category {cat} missing items"
            assert len(data[cat]["items"]) > 0, f"Category {cat} has no items"
        
        # Verify specific amenities exist
        assert "En-suite bathroom" in data["bathroom"]["items"]
        assert "Air conditioning" in data["bedroom"]["items"]
        assert "Free WiFi" in data["technology"]["items"]


class TestFacilityCatalog:
    """Facility catalog API tests"""
    
    def test_get_facility_catalog(self):
        """GET /api/facilities/catalog - returns full categorized facility catalog"""
        response = requests.get(f"{BASE_URL}/api/facilities/catalog")
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected categories exist
        expected_categories = ["general", "dining", "wellness", "business", "transport", "outdoor", "family", "laundry"]
        for cat in expected_categories:
            assert cat in data, f"Missing category: {cat}"
            assert "label" in data[cat], f"Category {cat} missing label"
            assert "items" in data[cat], f"Category {cat} missing items"
        
        # Verify specific facilities exist
        assert "24-hour front desk" in data["general"]["items"]
        assert "Restaurant" in data["dining"]["items"]
        assert "Swimming pool (indoor)" in data["wellness"]["items"]


class TestPropertyFacilities:
    """Property facilities API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_property_facilities(self):
        """GET /api/property-facilities/{property_id} - returns property facilities"""
        response = requests.get(f"{BASE_URL}/api/property-facilities/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "property_id" in data
        assert "facilities" in data
        assert isinstance(data["facilities"], list)
    
    def test_save_property_facilities(self, auth_headers):
        """PUT /api/property-facilities/{property_id} - saves facilities"""
        test_facilities = ["24-hour front desk", "Free WiFi", "Restaurant", "Gym / Fitness centre"]
        response = requests.put(
            f"{BASE_URL}/api/property-facilities/{PROPERTY_ID}",
            json=test_facilities,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["property_id"] == PROPERTY_ID
        assert set(data["facilities"]) == set(test_facilities)
        
        # Verify persistence with GET
        get_response = requests.get(f"{BASE_URL}/api/property-facilities/{PROPERTY_ID}")
        assert get_response.status_code == 200
        assert set(get_response.json()["facilities"]) == set(test_facilities)


class TestHotelPolicies:
    """Hotel policies API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_hotel_policies(self):
        """GET /api/hotel-policies/{property_id} - returns hotel policies"""
        response = requests.get(f"{BASE_URL}/api/hotel-policies/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "property_id" in data
        assert "check_in_from" in data
        assert "check_in_until" in data
        assert "check_out_from" in data
        assert "check_out_until" in data
        assert "cancellation_policy" in data
        assert "children_policy" in data
        assert "pet_policy" in data
        assert "smoking_policy" in data
        assert "payment_methods" in data
    
    def test_update_hotel_policies(self, auth_headers):
        """PUT /api/hotel-policies/{property_id} - updates policies"""
        update_data = {
            "check_in_from": "14:00",
            "check_in_until": "22:00",
            "check_out_from": "08:00",
            "check_out_until": "12:00",
            "cancellation_policy": "moderate",
            "cancellation_hours": 48,
            "cancellation_text": "Free cancellation up to 48 hours before check-in."
        }
        response = requests.put(
            f"{BASE_URL}/api/hotel-policies/{PROPERTY_ID}",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify updates
        assert data["check_in_from"] == "14:00"
        assert data["check_in_until"] == "22:00"
        assert data["check_out_from"] == "08:00"
        assert data["check_out_until"] == "12:00"
        assert data["cancellation_policy"] == "moderate"
        assert data["cancellation_hours"] == 48
        
        # Verify persistence with GET
        get_response = requests.get(f"{BASE_URL}/api/hotel-policies/{PROPERTY_ID}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["check_in_from"] == "14:00"
        assert get_data["cancellation_policy"] == "moderate"


class TestPromoCodes:
    """Promo codes API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_promo_code(self):
        """Unique test promo code"""
        return f"TEST{uuid.uuid4().hex[:6].upper()}"
    
    def test_list_promo_codes(self, auth_headers):
        """GET /api/promo-codes - lists all promo codes"""
        response = requests.get(f"{BASE_URL}/api/promo-codes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_promo_code(self, auth_headers, test_promo_code):
        """POST /api/promo-codes - creates a new promo code"""
        promo_data = {
            "code": test_promo_code,
            "description": "Test 25% summer discount",
            "discount_type": "percentage",
            "discount_value": 25,
            "property_id": "",
            "min_nights": 2,
            "max_uses": 100
        }
        response = requests.post(
            f"{BASE_URL}/api/promo-codes",
            json=promo_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert data["code"] == test_promo_code.upper()
        assert data["discount_type"] == "percentage"
        assert data["discount_value"] == 25
        assert data["is_active"] == True
        assert "id" in data
        
        return data["id"]
    
    def test_validate_promo_code_success(self, auth_headers, test_promo_code):
        """POST /api/promo-codes/validate - validates active promo code"""
        # First create the code
        promo_data = {
            "code": f"VALID{uuid.uuid4().hex[:4].upper()}",
            "description": "Valid test code",
            "discount_type": "percentage",
            "discount_value": 15,
            "min_nights": 1
        }
        create_response = requests.post(
            f"{BASE_URL}/api/promo-codes",
            json=promo_data,
            headers=auth_headers
        )
        assert create_response.status_code == 200
        
        # Validate the code
        validate_response = requests.post(
            f"{BASE_URL}/api/promo-codes/validate",
            params={"code": promo_data["code"], "nights": 2, "subtotal": 200}
        )
        assert validate_response.status_code == 200
        data = validate_response.json()
        
        assert data["valid"] == True
        assert data["code"] == promo_data["code"].upper()
        assert data["discount_type"] == "percentage"
        assert data["discount_value"] == 15
        assert data["discount_amount"] == 30  # 15% of 200
    
    def test_validate_promo_code_invalid(self):
        """POST /api/promo-codes/validate - rejects invalid code"""
        response = requests.post(
            f"{BASE_URL}/api/promo-codes/validate",
            params={"code": "INVALIDCODE123", "nights": 1, "subtotal": 100}
        )
        assert response.status_code == 404
        assert "Invalid" in response.json()["detail"]
    
    def test_toggle_promo_code(self, auth_headers):
        """PUT /api/promo-codes/{id}/toggle - toggles active status"""
        # Create a code to toggle
        promo_data = {
            "code": f"TOGGLE{uuid.uuid4().hex[:4].upper()}",
            "discount_type": "fixed",
            "discount_value": 20
        }
        create_response = requests.post(
            f"{BASE_URL}/api/promo-codes",
            json=promo_data,
            headers=auth_headers
        )
        code_id = create_response.json()["id"]
        
        # Toggle off
        toggle_response = requests.put(
            f"{BASE_URL}/api/promo-codes/{code_id}/toggle",
            headers=auth_headers
        )
        assert toggle_response.status_code == 200
        assert toggle_response.json()["is_active"] == False
        
        # Toggle back on
        toggle_response2 = requests.put(
            f"{BASE_URL}/api/promo-codes/{code_id}/toggle",
            headers=auth_headers
        )
        assert toggle_response2.status_code == 200
        assert toggle_response2.json()["is_active"] == True
    
    def test_delete_promo_code(self, auth_headers):
        """DELETE /api/promo-codes/{id} - deletes promo code"""
        # Create a code to delete
        promo_data = {
            "code": f"DELETE{uuid.uuid4().hex[:4].upper()}",
            "discount_type": "percentage",
            "discount_value": 10
        }
        create_response = requests.post(
            f"{BASE_URL}/api/promo-codes",
            json=promo_data,
            headers=auth_headers
        )
        code_id = create_response.json()["id"]
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/promo-codes/{code_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"


class TestAddOns:
    """Add-on services API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_add_ons_public(self):
        """GET /api/add-ons/{property_id} - returns active add-ons (public)"""
        response = requests.get(f"{BASE_URL}/api/add-ons/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned add-ons should be active
        for addon in data:
            assert addon["is_active"] == True
    
    def test_list_all_add_ons_admin(self, auth_headers):
        """GET /api/add-ons - lists all add-ons (admin)"""
        response = requests.get(
            f"{BASE_URL}/api/add-ons",
            params={"property_id": PROPERTY_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_add_on(self, auth_headers):
        """POST /api/add-ons - creates a new add-on"""
        addon_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST Airport Shuttle {uuid.uuid4().hex[:4]}",
            "description": "Private transfer from airport",
            "category": "transport",
            "price": 50,
            "price_type": "per_stay"
        }
        response = requests.post(
            f"{BASE_URL}/api/add-ons",
            json=addon_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert data["name"] == addon_data["name"]
        assert data["price"] == 50
        assert data["price_type"] == "per_stay"
        assert data["category"] == "transport"
        assert data["is_active"] == True
        assert "id" in data
        
        return data["id"]
    
    def test_toggle_add_on(self, auth_headers):
        """PUT /api/add-ons/{id}/toggle - toggles active status"""
        # Create an add-on to toggle
        addon_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST Toggle Addon {uuid.uuid4().hex[:4]}",
            "price": 25,
            "price_type": "per_night"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/add-ons",
            json=addon_data,
            headers=auth_headers
        )
        addon_id = create_response.json()["id"]
        
        # Toggle off
        toggle_response = requests.put(
            f"{BASE_URL}/api/add-ons/{addon_id}/toggle",
            headers=auth_headers
        )
        assert toggle_response.status_code == 200
        assert toggle_response.json()["is_active"] == False
        
        # Toggle back on
        toggle_response2 = requests.put(
            f"{BASE_URL}/api/add-ons/{addon_id}/toggle",
            headers=auth_headers
        )
        assert toggle_response2.status_code == 200
        assert toggle_response2.json()["is_active"] == True
    
    def test_delete_add_on(self, auth_headers):
        """DELETE /api/add-ons/{id} - deletes add-on"""
        # Create an add-on to delete
        addon_data = {
            "property_id": PROPERTY_ID,
            "name": f"TEST Delete Addon {uuid.uuid4().hex[:4]}",
            "price": 30
        }
        create_response = requests.post(
            f"{BASE_URL}/api/add-ons",
            json=addon_data,
            headers=auth_headers
        )
        addon_id = create_response.json()["id"]
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/add-ons/{addon_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"


class TestBookingPropertyEndpoint:
    """Test booking property endpoint includes new data"""
    
    def test_booking_property_includes_all_data(self):
        """GET /api/booking/property/{id} - includes template_settings, facilities, policies, add_ons"""
        response = requests.get(f"{BASE_URL}/api/booking/property/{PROPERTY_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all new fields are present
        assert "template_settings" in data, "Missing template_settings"
        assert "facilities" in data, "Missing facilities"
        assert "policies" in data, "Missing policies"
        assert "add_ons" in data, "Missing add_ons"
        
        # Verify policies structure
        policies = data["policies"]
        assert "check_in_from" in policies
        assert "check_out_until" in policies
        assert "cancellation_policy" in policies
        
        # Verify add_ons is a list
        assert isinstance(data["add_ons"], list)
        
        # Verify facilities is a list
        assert isinstance(data["facilities"], list)


class TestAuthorizationRequirements:
    """Test that protected endpoints require authentication"""
    
    def test_promo_codes_list_requires_auth(self):
        """GET /api/promo-codes requires authentication"""
        response = requests.get(f"{BASE_URL}/api/promo-codes")
        assert response.status_code == 401
    
    def test_promo_codes_create_requires_auth(self):
        """POST /api/promo-codes requires authentication"""
        response = requests.post(f"{BASE_URL}/api/promo-codes", json={
            "code": "NOAUTH",
            "discount_type": "percentage",
            "discount_value": 10
        })
        assert response.status_code == 401
    
    def test_add_ons_list_admin_requires_auth(self):
        """GET /api/add-ons (admin list) requires authentication"""
        response = requests.get(f"{BASE_URL}/api/add-ons")
        assert response.status_code == 401
    
    def test_add_ons_create_requires_auth(self):
        """POST /api/add-ons requires authentication"""
        response = requests.post(f"{BASE_URL}/api/add-ons", json={
            "property_id": PROPERTY_ID,
            "name": "Unauthorized",
            "price": 10
        })
        assert response.status_code == 401
    
    def test_policies_update_requires_auth(self):
        """PUT /api/hotel-policies/{id} requires authentication"""
        response = requests.put(f"{BASE_URL}/api/hotel-policies/{PROPERTY_ID}", json={
            "check_in_from": "16:00"
        })
        assert response.status_code == 401
    
    def test_facilities_update_requires_auth(self):
        """PUT /api/property-facilities/{id} requires authentication"""
        response = requests.put(f"{BASE_URL}/api/property-facilities/{PROPERTY_ID}", json=["WiFi"])
        assert response.status_code == 401


# Public endpoints should NOT require auth
class TestPublicEndpoints:
    """Test that public endpoints work without authentication"""
    
    def test_amenity_catalog_public(self):
        """GET /api/amenities/catalog is public"""
        response = requests.get(f"{BASE_URL}/api/amenities/catalog")
        assert response.status_code == 200
    
    def test_facility_catalog_public(self):
        """GET /api/facilities/catalog is public"""
        response = requests.get(f"{BASE_URL}/api/facilities/catalog")
        assert response.status_code == 200
    
    def test_hotel_policies_public(self):
        """GET /api/hotel-policies/{id} is public"""
        response = requests.get(f"{BASE_URL}/api/hotel-policies/{PROPERTY_ID}")
        assert response.status_code == 200
    
    def test_property_facilities_public(self):
        """GET /api/property-facilities/{id} is public"""
        response = requests.get(f"{BASE_URL}/api/property-facilities/{PROPERTY_ID}")
        assert response.status_code == 200
    
    def test_add_ons_property_public(self):
        """GET /api/add-ons/{property_id} is public"""
        response = requests.get(f"{BASE_URL}/api/add-ons/{PROPERTY_ID}")
        assert response.status_code == 200
    
    def test_promo_code_validate_public(self):
        """POST /api/promo-codes/validate is public"""
        response = requests.post(
            f"{BASE_URL}/api/promo-codes/validate",
            params={"code": "ANYCODE", "nights": 1, "subtotal": 100}
        )
        # Should return 404 (not found) not 401 (unauthorized)
        assert response.status_code == 404
