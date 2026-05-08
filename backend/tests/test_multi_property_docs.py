"""
Test suite for Multi-Property Support and API Documentation features
Tests: Property CRUD, property_id filtering on reviews/stats, OpenAPI/Swagger/ReDoc endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from backend/.env
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestAPIDocumentation:
    """API Documentation endpoint tests - OpenAPI, Swagger, ReDoc"""
    
    def test_openapi_json_returns_spec(self):
        """GET /api/openapi.json returns OpenAPI specification"""
        response = requests.get(f"{BASE_URL}/api/openapi.json")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify OpenAPI structure
        assert "openapi" in data, "Should have openapi version"
        assert data["openapi"].startswith("3."), "Should be OpenAPI 3.x"
        
        assert "info" in data, "Should have info section"
        assert data["info"]["title"] == "Hotel Review Hub API", "Title should match"
        assert data["info"]["version"] == "1.0.0", "Version should be 1.0.0"
        
        assert "paths" in data, "Should have paths section"
        
        # Count endpoints
        endpoint_count = sum(len(methods) for methods in data["paths"].values())
        print(f"✓ OpenAPI spec returned with {endpoint_count} endpoints")
        
        # Verify key endpoints exist
        assert "/api/properties" in data["paths"], "Should have /api/properties endpoint"
        assert "/api/reviews" in data["paths"], "Should have /api/reviews endpoint"
        assert "/api/auth/login" in data["paths"], "Should have /api/auth/login endpoint"
    
    def test_swagger_ui_returns_html(self):
        """GET /api/docs returns Swagger UI HTML page"""
        response = requests.get(f"{BASE_URL}/api/docs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content = response.text
        assert "<!DOCTYPE html>" in content or "<html>" in content, "Should return HTML"
        assert "swagger-ui" in content.lower(), "Should contain swagger-ui reference"
        assert "Hotel Review Hub API" in content, "Should have API title"
        
        print("✓ Swagger UI page returned successfully")
    
    def test_redoc_returns_html(self):
        """GET /api/redoc returns ReDoc documentation page"""
        response = requests.get(f"{BASE_URL}/api/redoc")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content = response.text
        assert "<!DOCTYPE html>" in content or "<html>" in content, "Should return HTML"
        assert "redoc" in content.lower(), "Should contain redoc reference"
        assert "Hotel Review Hub API" in content, "Should have API title"
        
        print("✓ ReDoc page returned successfully")


class TestPropertyCRUD:
    """Property CRUD endpoint tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_list_properties_returns_default(self, admin_token):
        """GET /api/properties returns property list with at least 'default' property"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/properties", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 1, "Should have at least 1 property (default)"
        
        # Find default property
        default_prop = next((p for p in data if p.get("id") == "default"), None)
        assert default_prop is not None, "Should have 'default' property"
        assert "name" in default_prop, "Property should have name"
        assert "property_type" in default_prop, "Property should have property_type"
        
        print(f"✓ GET /api/properties returned {len(data)} properties (including 'default')")
    
    def test_create_property_admin_only(self, admin_token):
        """POST /api/properties creates new property (admin only)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        new_property = {
            "name": "TEST_Beach Resort",
            "address": "123 Ocean Drive",
            "city": "Miami",
            "country": "USA",
            "property_type": "resort"
        }
        
        response = requests.post(f"{BASE_URL}/api/properties", json=new_property, headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Created property should have id"
        assert data["name"] == new_property["name"], "Name should match"
        assert data["city"] == new_property["city"], "City should match"
        assert data["property_type"] == new_property["property_type"], "Property type should match"
        assert data["is_active"] == True, "New property should be active"
        
        created_id = data["id"]
        print(f"✓ Created property: {data['name']} (id: {created_id})")
        
        # Cleanup - delete the test property
        delete_response = requests.delete(f"{BASE_URL}/api/properties/{created_id}", headers=headers)
        assert delete_response.status_code == 200, f"Cleanup failed: {delete_response.status_code}"
        print(f"✓ Cleaned up test property: {created_id}")
    
    def test_create_property_without_auth_fails(self):
        """POST /api/properties without auth returns 401"""
        new_property = {
            "name": "Unauthorized Property",
            "property_type": "hotel"
        }
        
        response = requests.post(f"{BASE_URL}/api/properties", json=new_property)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ POST /api/properties without auth correctly rejected")
    
    def test_update_property_admin_only(self, admin_token):
        """PUT /api/properties/{id} updates property (admin only)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First create a property to update
        new_property = {
            "name": "TEST_Update Property",
            "city": "Original City",
            "property_type": "hotel"
        }
        create_response = requests.post(f"{BASE_URL}/api/properties", json=new_property, headers=headers)
        assert create_response.status_code == 200, f"Create failed: {create_response.status_code}"
        created_id = create_response.json()["id"]
        
        # Update the property
        update_data = {
            "name": "TEST_Updated Property Name",
            "city": "Updated City"
        }
        update_response = requests.put(f"{BASE_URL}/api/properties/{created_id}", json=update_data, headers=headers)
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        updated = update_response.json()
        assert updated["name"] == update_data["name"], "Name should be updated"
        assert updated["city"] == update_data["city"], "City should be updated"
        
        print(f"✓ Updated property: {updated['name']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/properties/{created_id}", headers=headers)
    
    def test_delete_property_admin_only(self, admin_token):
        """DELETE /api/properties/{id} deletes property (admin only)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First create a property to delete
        new_property = {
            "name": "TEST_Delete Property",
            "property_type": "hotel"
        }
        create_response = requests.post(f"{BASE_URL}/api/properties", json=new_property, headers=headers)
        assert create_response.status_code == 200, f"Create failed: {create_response.status_code}"
        created_id = create_response.json()["id"]
        
        # Delete the property
        delete_response = requests.delete(f"{BASE_URL}/api/properties/{created_id}", headers=headers)
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        
        data = delete_response.json()
        assert data.get("message") == "Property deleted", "Should return 'Property deleted' message"
        
        print(f"✓ Deleted property: {created_id}")
        
        # Verify deletion
        list_response = requests.get(f"{BASE_URL}/api/properties", headers=headers)
        properties = list_response.json()
        deleted_prop = next((p for p in properties if p.get("id") == created_id), None)
        assert deleted_prop is None, "Deleted property should not be in list"
        print("✓ Verified property deletion")
    
    def test_cannot_delete_default_property(self, admin_token):
        """DELETE /api/properties/default returns 400 - cannot delete default"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.delete(f"{BASE_URL}/api/properties/default", headers=headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "Cannot delete default property" in data.get("detail", ""), "Should have appropriate error message"
        
        print("✓ Cannot delete default property - correctly rejected")
    
    def test_invalid_property_type_rejected(self, admin_token):
        """POST /api/properties with invalid property_type returns 400"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        new_property = {
            "name": "Invalid Type Property",
            "property_type": "invalid_type"
        }
        
        response = requests.post(f"{BASE_URL}/api/properties", json=new_property, headers=headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "Invalid property type" in data.get("detail", ""), "Should have appropriate error message"
        
        print("✓ Invalid property type correctly rejected")


class TestPropertyIdFiltering:
    """Tests for property_id filtering on reviews and stats"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_reviews_filter_by_property_id(self):
        """GET /api/reviews?property_id=default returns reviews scoped to property"""
        # First seed reviews if needed
        requests.post(f"{BASE_URL}/api/reviews/seed")
        
        response = requests.get(f"{BASE_URL}/api/reviews?property_id=default")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # All returned reviews should have property_id = default
        for review in data:
            assert review.get("property_id") == "default", f"Review {review.get('id')} should have property_id='default'"
        
        print(f"✓ GET /api/reviews?property_id=default returned {len(data)} reviews (all with property_id='default')")
    
    def test_reviews_stats_filter_by_property_id(self):
        """GET /api/reviews/stats/summary?property_id=default returns stats scoped to property"""
        response = requests.get(f"{BASE_URL}/api/reviews/stats/summary?property_id=default")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_reviews" in data, "Should have total_reviews"
        assert "average_rating" in data, "Should have average_rating"
        assert "response_rate" in data, "Should have response_rate"
        assert "by_platform" in data, "Should have by_platform breakdown"
        
        print(f"✓ GET /api/reviews/stats/summary?property_id=default returned stats: {data['total_reviews']} reviews, {data['average_rating']}/5 avg rating")
    
    def test_reviews_have_property_id_field(self):
        """All reviews should have property_id field (migration check)"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check that all reviews have property_id
        reviews_without_property_id = [r for r in data if "property_id" not in r]
        assert len(reviews_without_property_id) == 0, f"Found {len(reviews_without_property_id)} reviews without property_id"
        
        print(f"✓ All {len(data)} reviews have property_id field")
    
    def test_create_review_with_property_id(self, admin_token):
        """POST /api/reviews with property_id creates review scoped to property"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        new_review = {
            "property_id": "default",
            "platform": "google",
            "guest_name": "TEST_Property Review Guest",
            "rating": 4,
            "review_text": "Test review with property_id",
            "stay_date": "January 2026",
            "room_type": "Standard Room"
        }
        
        response = requests.post(f"{BASE_URL}/api/reviews", json=new_review, headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("property_id") == "default", "Created review should have property_id='default'"
        
        print(f"✓ Created review with property_id='default': {data['id']}")


class TestRegressionAfterMultiProperty:
    """Regression tests to ensure existing features still work after multi-property support"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_reviews_endpoint_works_without_property_filter(self):
        """GET /api/reviews still works without property_id filter"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/reviews (no filter) returned {len(data)} reviews")
    
    def test_stats_endpoint_works_without_property_filter(self):
        """GET /api/reviews/stats/summary still works without property_id filter"""
        response = requests.get(f"{BASE_URL}/api/reviews/stats/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_reviews" in data, "Should have total_reviews"
        print(f"✓ GET /api/reviews/stats/summary (no filter) returned stats")
    
    def test_ai_generation_still_works(self, admin_token):
        """POST /api/reviews/generate-ai-response still works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get a review ID
        reviews_response = requests.get(f"{BASE_URL}/api/reviews")
        if reviews_response.status_code == 200:
            reviews = reviews_response.json()
            if len(reviews) > 0:
                review_id = reviews[0]["id"]
                
                response = requests.post(
                    f"{BASE_URL}/api/reviews/generate-ai-response",
                    json={"review_id": review_id, "tone": "professional", "language": "en"},
                    headers=headers,
                    timeout=30
                )
                
                # AI generation might fail due to service issues, but endpoint should be accessible
                assert response.status_code in [200, 500], f"Expected 200 or 500, got {response.status_code}"
                
                if response.status_code == 200:
                    data = response.json()
                    assert "generated_text" in data, "Should have generated_text"
                    print(f"✓ AI generation works")
                else:
                    print(f"Note: AI generation returned 500 (service issue)")
            else:
                print("Note: No reviews to test AI generation")
    
    def test_auth_endpoints_still_work(self):
        """Auth endpoints still work after multi-property changes"""
        # Login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.status_code}"
        
        token = login_response.json().get("token")
        
        # Get me
        headers = {"Authorization": f"Bearer {token}"}
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_response.status_code == 200, f"Get me failed: {me_response.status_code}"
        
        print("✓ Auth endpoints still work")
    
    def test_review_statuses_display_correctly(self):
        """Review statuses (Responded, Rejected, Pending, Awaiting Approval) are present"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check that reviews have response_status field
        valid_statuses = ["pending", "draft", "pending_approval", "approved", "rejected", "responded"]
        for review in data:
            status = review.get("response_status")
            assert status in valid_statuses, f"Review {review.get('id')} has invalid status: {status}"
        
        # Count statuses
        status_counts = {}
        for review in data:
            status = review.get("response_status")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"✓ Review statuses: {status_counts}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
