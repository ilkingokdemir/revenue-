"""
Test Widget API Endpoints - Iteration 16
Tests the embeddable reviews widget feature:
- GET /api/widget/reviews - Get reviews via API key auth
- GET /api/widget/stats - Get stats via API key auth
- POST /api/widget/generate-response - Generate AI response via API key auth
- verify_api_key middleware - Validates API key and increments request_count
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test API key provided in the review request
TEST_API_KEY = "rhk_17354979397db960bcb68db21ed42b7acc103e7940715667"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestWidgetAPIAuth:
    """Test widget API authentication via API key"""
    
    def test_widget_reviews_without_api_key_returns_401(self):
        """GET /api/widget/reviews without api_key returns 401"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "api_key" in data["detail"].lower() or "api key" in data["detail"].lower()
        print("PASS: Widget reviews without API key returns 401")
    
    def test_widget_reviews_with_invalid_api_key_returns_401(self):
        """GET /api/widget/reviews with invalid api_key returns 401"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key=INVALID")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Widget reviews with invalid API key returns 401")
    
    def test_widget_reviews_with_non_rhk_prefix_returns_401(self):
        """GET /api/widget/reviews with non-rhk_ prefix returns 401"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key=abc_123456")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Widget reviews with non-rhk_ prefix returns 401")
    
    def test_widget_stats_without_api_key_returns_401(self):
        """GET /api/widget/stats without api_key returns 401"""
        response = requests.get(f"{BASE_URL}/api/widget/stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Widget stats without API key returns 401")


class TestWidgetReviewsEndpoint:
    """Test GET /api/widget/reviews endpoint"""
    
    def test_widget_reviews_with_valid_api_key_returns_200(self):
        """GET /api/widget/reviews with valid api_key returns 200 and list"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={TEST_API_KEY}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of reviews"
        print(f"PASS: Widget reviews returns 200 with {len(data)} reviews")
    
    def test_widget_reviews_returns_review_structure(self):
        """Widget reviews returns proper review structure"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={TEST_API_KEY}")
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0:
            review = data[0]
            # Check required fields
            assert "id" in review, "Review missing 'id'"
            assert "platform" in review, "Review missing 'platform'"
            assert "guest_name" in review, "Review missing 'guest_name'"
            assert "rating" in review, "Review missing 'rating'"
            assert "review_text" in review, "Review missing 'review_text'"
            assert "response_status" in review, "Review missing 'response_status'"
            print(f"PASS: Review structure is correct with fields: id, platform, guest_name, rating, review_text, response_status")
        else:
            print("SKIP: No reviews to verify structure")
    
    def test_widget_reviews_filter_by_platform(self):
        """Widget reviews can filter by platform"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={TEST_API_KEY}&platform=google")
        assert response.status_code == 200
        data = response.json()
        for review in data:
            assert review["platform"] == "google", f"Expected platform 'google', got '{review['platform']}'"
        print(f"PASS: Platform filter works - {len(data)} google reviews")
    
    def test_widget_reviews_filter_by_status(self):
        """Widget reviews can filter by status"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={TEST_API_KEY}&status=pending")
        assert response.status_code == 200
        data = response.json()
        for review in data:
            assert review["response_status"] == "pending", f"Expected status 'pending', got '{review['response_status']}'"
        print(f"PASS: Status filter works - {len(data)} pending reviews")
    
    def test_widget_reviews_limit_parameter(self):
        """Widget reviews respects limit parameter (max 50)"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={TEST_API_KEY}&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5, f"Expected max 5 reviews, got {len(data)}"
        print(f"PASS: Limit parameter works - returned {len(data)} reviews")
    
    def test_widget_reviews_max_limit_is_50(self):
        """Widget reviews max limit is 50"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={TEST_API_KEY}&limit=100")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 50, f"Expected max 50 reviews, got {len(data)}"
        print(f"PASS: Max limit enforced - returned {len(data)} reviews (max 50)")


class TestWidgetStatsEndpoint:
    """Test GET /api/widget/stats endpoint"""
    
    def test_widget_stats_with_valid_api_key_returns_200(self):
        """GET /api/widget/stats with valid api_key returns 200"""
        response = requests.get(f"{BASE_URL}/api/widget/stats?api_key={TEST_API_KEY}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Widget stats returns 200")
    
    def test_widget_stats_returns_correct_structure(self):
        """Widget stats returns correct structure with all required fields"""
        response = requests.get(f"{BASE_URL}/api/widget/stats?api_key={TEST_API_KEY}")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "total_reviews" in data, "Stats missing 'total_reviews'"
        assert "average_rating" in data, "Stats missing 'average_rating'"
        assert "response_rate" in data, "Stats missing 'response_rate'"
        assert "pending" in data, "Stats missing 'pending'"
        
        # Check data types
        assert isinstance(data["total_reviews"], int), "total_reviews should be int"
        assert isinstance(data["average_rating"], (int, float)), "average_rating should be number"
        assert isinstance(data["response_rate"], (int, float)), "response_rate should be number"
        assert isinstance(data["pending"], int), "pending should be int"
        
        print(f"PASS: Stats structure correct - total: {data['total_reviews']}, avg: {data['average_rating']}, rate: {data['response_rate']}%, pending: {data['pending']}")
    
    def test_widget_stats_values_are_reasonable(self):
        """Widget stats values are within reasonable ranges"""
        response = requests.get(f"{BASE_URL}/api/widget/stats?api_key={TEST_API_KEY}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_reviews"] >= 0, "total_reviews should be >= 0"
        assert 0 <= data["average_rating"] <= 5, "average_rating should be 0-5"
        assert 0 <= data["response_rate"] <= 100, "response_rate should be 0-100"
        assert data["pending"] >= 0, "pending should be >= 0"
        
        print("PASS: Stats values are within reasonable ranges")


class TestWidgetGenerateResponse:
    """Test POST /api/widget/generate-response endpoint"""
    
    def test_widget_generate_response_without_api_key_returns_401(self):
        """POST /api/widget/generate-response without api_key returns 401"""
        response = requests.post(f"{BASE_URL}/api/widget/generate-response", json={
            "review_id": "test-id",
            "language": "en",
            "tone": "professional"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Generate response without API key returns 401")
    
    def test_widget_generate_response_missing_review_id_returns_400(self):
        """POST /api/widget/generate-response without review_id returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/widget/generate-response?api_key={TEST_API_KEY}",
            json={"language": "en", "tone": "professional"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Generate response without review_id returns 400")
    
    def test_widget_generate_response_invalid_review_id_returns_404(self):
        """POST /api/widget/generate-response with invalid review_id returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/widget/generate-response?api_key={TEST_API_KEY}",
            json={"review_id": "nonexistent-review-id", "language": "en", "tone": "professional"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Generate response with invalid review_id returns 404")


class TestAPIKeyRequestCount:
    """Test that verify_api_key middleware increments request_count"""
    
    def test_api_key_request_count_increments(self):
        """API key request_count increments on valid requests"""
        # Login as admin to check API key details
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json()["token"]
        
        # Get initial API key state
        headers = {"Authorization": f"Bearer {token}"}
        keys_response = requests.get(f"{BASE_URL}/api/api-keys", headers=headers)
        assert keys_response.status_code == 200
        
        keys = keys_response.json()
        test_key = None
        for key in keys:
            if key.get("key") == TEST_API_KEY or key.get("key_masked", "").startswith("rhk_1735"):
                test_key = key
                break
        
        if test_key is None:
            print("SKIP: Test API key not found in list")
            return
        
        initial_count = test_key.get("request_count", 0)
        
        # Make a widget request
        requests.get(f"{BASE_URL}/api/widget/stats?api_key={TEST_API_KEY}")
        
        # Check updated count
        keys_response = requests.get(f"{BASE_URL}/api/api-keys", headers=headers)
        keys = keys_response.json()
        for key in keys:
            if key.get("key") == TEST_API_KEY or key.get("key_masked", "").startswith("rhk_1735"):
                new_count = key.get("request_count", 0)
                assert new_count > initial_count, f"request_count should have increased from {initial_count}"
                print(f"PASS: API key request_count incremented from {initial_count} to {new_count}")
                return
        
        print("SKIP: Could not verify request_count increment")


class TestMainAppStillWorks:
    """Verify main app login and reviews dashboard still work"""
    
    def test_admin_login_still_works(self):
        """Admin login with admin@hotelbox.com / HotelAdmin2026! works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Login response missing token"
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        print("PASS: Admin login still works")
    
    def test_reviews_endpoint_still_works(self):
        """GET /api/reviews still works (main app)"""
        response = requests.get(f"{BASE_URL}/api/reviews")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of reviews"
        print(f"PASS: Reviews endpoint works - {len(data)} reviews")
    
    def test_integration_guide_still_works(self):
        """GET /api/integration-guide still works"""
        response = requests.get(f"{BASE_URL}/api/integration-guide")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "title" in data
        assert "MyHotelBox" in data["title"]
        print("PASS: Integration guide endpoint still works")
    
    def test_webhooks_endpoint_still_works(self):
        """Webhooks endpoint requires auth (401 without token)"""
        response = requests.get(f"{BASE_URL}/api/webhooks")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Webhooks endpoint requires auth (401)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
