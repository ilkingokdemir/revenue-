"""
Test suite for Iteration 18: Real-time Red Popup Notifications with Sound
Tests the new /api/widget/reviews/new endpoint and notification popup functionality
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_KEY = "rhk_17354979397db960bcb68db21ed42b7acc103e7940715667"

class TestWidgetNewReviewsEndpoint:
    """Tests for GET /api/widget/reviews/new endpoint"""
    
    def test_new_reviews_without_api_key_returns_401(self):
        """GET /api/widget/reviews/new without api_key returns 401"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews/new")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/widget/reviews/new without api_key returns 401")
    
    def test_new_reviews_with_invalid_api_key_returns_401(self):
        """GET /api/widget/reviews/new with invalid api_key returns 401"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews/new?api_key=invalid_key")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/widget/reviews/new with invalid api_key returns 401")
    
    def test_new_reviews_without_since_returns_empty_array(self):
        """GET /api/widget/reviews/new without since parameter returns empty array"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews/new?api_key={API_KEY}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data == [], f"Expected empty array, got {data}"
        print("PASS: GET /api/widget/reviews/new without since returns empty array")
    
    def test_new_reviews_with_old_since_returns_reviews(self):
        """GET /api/widget/reviews/new with old since timestamp returns reviews"""
        # Use a timestamp from 30 days ago to get all recent reviews
        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        response = requests.get(f"{BASE_URL}/api/widget/reviews/new?api_key={API_KEY}&since={old_timestamp}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/widget/reviews/new with old since returns {len(data)} reviews")
    
    def test_new_reviews_with_future_since_returns_empty(self):
        """GET /api/widget/reviews/new with future since timestamp returns empty array"""
        future_timestamp = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        response = requests.get(f"{BASE_URL}/api/widget/reviews/new?api_key={API_KEY}&since={future_timestamp}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data == [], f"Expected empty array for future timestamp, got {len(data)} reviews"
        print("PASS: GET /api/widget/reviews/new with future since returns empty array")
    
    def test_new_reviews_with_property_id_filter(self):
        """GET /api/widget/reviews/new with property_id filter works"""
        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        response = requests.get(f"{BASE_URL}/api/widget/reviews/new?api_key={API_KEY}&property_id=default&since={old_timestamp}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        # Verify all returned reviews have the correct property_id
        for review in data:
            assert review.get("property_id") == "default", f"Review has wrong property_id: {review.get('property_id')}"
        print(f"PASS: GET /api/widget/reviews/new with property_id filter returns {len(data)} reviews")
    
    def test_new_reviews_response_structure(self):
        """Verify response structure contains required fields for notification popup"""
        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        response = requests.get(f"{BASE_URL}/api/widget/reviews/new?api_key={API_KEY}&since={old_timestamp}")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            review = data[0]
            # Required fields for notification popup
            required_fields = ["id", "guest_name", "platform", "rating", "review_text"]
            for field in required_fields:
                assert field in review, f"Missing required field: {field}"
            
            # Verify rating is 1-5
            assert 1 <= review["rating"] <= 5, f"Rating out of range: {review['rating']}"
            print(f"PASS: Response structure contains all required fields: {required_fields}")
        else:
            print("SKIP: No reviews to verify structure (empty response)")


class TestCreateReviewForNotification:
    """Tests for creating a review and verifying it appears in new reviews endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin login failed")
    
    def test_create_review_and_verify_in_new_endpoint(self, admin_token):
        """Create a review and verify it appears in /widget/reviews/new"""
        # Record timestamp before creating review
        before_timestamp = datetime.now(timezone.utc).isoformat()
        
        # Create a new review
        review_data = {
            "property_id": "default",
            "platform": "google",
            "guest_name": "TEST_NotificationTest_User",
            "rating": 4,
            "review_text": "This is a test review for notification popup testing.",
            "stay_date": "2026-01-10",
            "room_type": "Standard Room"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/reviews",
            json=review_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert create_response.status_code == 200, f"Failed to create review: {create_response.status_code}"
        created_review = create_response.json()
        review_id = created_review.get("id")
        print(f"Created test review with ID: {review_id}")
        
        # Verify the review appears in /widget/reviews/new
        new_response = requests.get(
            f"{BASE_URL}/api/widget/reviews/new?api_key={API_KEY}&since={before_timestamp}"
        )
        assert new_response.status_code == 200
        new_reviews = new_response.json()
        
        # Find our test review
        found = any(r.get("id") == review_id for r in new_reviews)
        assert found, f"Created review {review_id} not found in new reviews endpoint"
        print(f"PASS: Created review appears in /widget/reviews/new endpoint")
        
        # Cleanup - delete the test review
        # Note: There's no delete endpoint, so we'll leave it for now


class TestExistingWidgetEndpoints:
    """Verify existing widget endpoints still work"""
    
    def test_widget_reviews_endpoint(self):
        """GET /api/widget/reviews still works"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={API_KEY}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/widget/reviews returns {len(data)} reviews")
    
    def test_widget_stats_endpoint(self):
        """GET /api/widget/stats still works"""
        response = requests.get(f"{BASE_URL}/api/widget/stats?api_key={API_KEY}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total_reviews" in data, "Missing total_reviews in stats"
        assert "average_rating" in data, "Missing average_rating in stats"
        assert "response_rate" in data, "Missing response_rate in stats"
        assert "pending" in data, "Missing pending in stats"
        print(f"PASS: GET /api/widget/stats returns: total={data['total_reviews']}, avg={data['average_rating']}, rate={data['response_rate']}%, pending={data['pending']}")
    
    def test_widget_unread_count_endpoint(self):
        """GET /api/widget/unread-count still works"""
        response = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key={API_KEY}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "unread" in data, "Missing unread count in response"
        print(f"PASS: GET /api/widget/unread-count returns unread={data['unread']}")


class TestMainAppStillWorks:
    """Verify main app functionality is not broken"""
    
    def test_admin_login(self):
        """Admin login still works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.status_code}"
        data = response.json()
        assert "token" in data, "Missing token in login response"
        assert data.get("role") == "admin", f"Expected admin role, got {data.get('role')}"
        print("PASS: Admin login works correctly")
    
    def test_reviews_endpoint(self):
        """GET /api/reviews still works"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = login_response.json().get("token")
        
        response = requests.get(
            f"{BASE_URL}/api/reviews",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/reviews returns {len(data)} reviews")
    
    def test_dashboard_stats(self):
        """GET /api/reviews/stats/summary still works"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        token = login_response.json().get("token")
        
        response = requests.get(
            f"{BASE_URL}/api/reviews/stats/summary",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total_reviews" in data, "Missing total_reviews"
        print(f"PASS: Dashboard stats: total={data.get('total_reviews')}, avg={data.get('average_rating')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
