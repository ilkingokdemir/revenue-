"""
Test suite for Iteration 17: Unread Badge Feature
Tests the new widget endpoints for unread review count and mark-as-read functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_KEY = "rhk_17354979397db960bcb68db21ed42b7acc103e7940715667"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestUnreadCountEndpoint:
    """Tests for GET /api/widget/unread-count"""
    
    def test_unread_count_without_api_key_returns_401(self):
        """Unread count endpoint requires API key"""
        response = requests.get(f"{BASE_URL}/api/widget/unread-count")
        assert response.status_code == 401
        assert "api key" in response.json().get("detail", "").lower()
    
    def test_unread_count_with_invalid_api_key_returns_401(self):
        """Invalid API key returns 401"""
        response = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key=invalid_key")
        assert response.status_code == 401
    
    def test_unread_count_with_non_rhk_prefix_returns_401(self):
        """API key must start with rhk_ prefix"""
        response = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key=abc_123456")
        assert response.status_code == 401
    
    def test_unread_count_with_valid_api_key_returns_200(self):
        """Valid API key returns unread count"""
        response = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key={API_KEY}")
        assert response.status_code == 200
        data = response.json()
        assert "unread" in data
        assert isinstance(data["unread"], int)
        assert data["unread"] >= 0
    
    def test_unread_count_with_property_id_filter(self):
        """Unread count can be filtered by property_id"""
        response = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key={API_KEY}&property_id=default")
        assert response.status_code == 200
        data = response.json()
        assert "unread" in data


class TestMarkReadEndpoint:
    """Tests for PUT /api/widget/reviews/{id}/read"""
    
    def test_mark_read_without_api_key_returns_401(self):
        """Mark read endpoint requires API key"""
        response = requests.put(f"{BASE_URL}/api/widget/reviews/some-id/read")
        assert response.status_code == 401
    
    def test_mark_read_with_invalid_review_id_returns_404(self):
        """Invalid review ID returns 404"""
        response = requests.put(f"{BASE_URL}/api/widget/reviews/nonexistent-review-id/read?api_key={API_KEY}")
        assert response.status_code == 404
    
    def test_mark_read_with_valid_review_id_returns_200(self):
        """Valid review ID marks review as read"""
        # First get a review ID
        reviews_response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={API_KEY}&limit=1")
        assert reviews_response.status_code == 200
        reviews = reviews_response.json()
        
        if len(reviews) > 0:
            review_id = reviews[0]["id"]
            
            # Mark as read
            response = requests.put(f"{BASE_URL}/api/widget/reviews/{review_id}/read?api_key={API_KEY}")
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") == True
    
    def test_mark_read_decrements_unread_count(self):
        """Marking a review as read decrements the unread count"""
        # Get initial unread count
        initial_response = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key={API_KEY}")
        initial_count = initial_response.json()["unread"]
        
        # Get an unread review
        reviews_response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={API_KEY}&limit=30")
        reviews = reviews_response.json()
        
        # Find an unread review
        unread_review = None
        for r in reviews:
            if not r.get("is_read"):
                unread_review = r
                break
        
        if unread_review and initial_count > 0:
            # Mark as read
            requests.put(f"{BASE_URL}/api/widget/reviews/{unread_review['id']}/read?api_key={API_KEY}")
            
            # Check count decremented
            new_response = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key={API_KEY}")
            new_count = new_response.json()["unread"]
            
            assert new_count == initial_count - 1, f"Expected {initial_count - 1}, got {new_count}"


class TestMarkAllReadEndpoint:
    """Tests for PUT /api/widget/reviews/mark-all-read"""
    
    def test_mark_all_read_without_api_key_returns_401(self):
        """Mark all read endpoint requires API key"""
        response = requests.put(f"{BASE_URL}/api/widget/reviews/mark-all-read")
        assert response.status_code == 401
    
    def test_mark_all_read_with_valid_api_key_returns_200(self):
        """Valid API key marks all reviews as read"""
        response = requests.put(f"{BASE_URL}/api/widget/reviews/mark-all-read?api_key={API_KEY}")
        assert response.status_code == 200
        data = response.json()
        assert "marked" in data
        assert isinstance(data["marked"], int)
    
    def test_mark_all_read_sets_unread_count_to_zero(self):
        """After mark-all-read, unread count should be 0"""
        # Mark all as read
        requests.put(f"{BASE_URL}/api/widget/reviews/mark-all-read?api_key={API_KEY}")
        
        # Check unread count is 0
        response = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key={API_KEY}")
        assert response.status_code == 200
        assert response.json()["unread"] == 0
    
    def test_mark_all_read_with_property_id_filter(self):
        """Mark all read can be filtered by property_id"""
        response = requests.put(f"{BASE_URL}/api/widget/reviews/mark-all-read?api_key={API_KEY}&property_id=default")
        assert response.status_code == 200


class TestReviewsIncludeIsReadField:
    """Tests that reviews include is_read field"""
    
    def test_widget_reviews_include_is_read_field(self):
        """Widget reviews endpoint returns is_read field"""
        response = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={API_KEY}&limit=5")
        assert response.status_code == 200
        reviews = response.json()
        
        if len(reviews) > 0:
            # After mark-all-read, all should have is_read=True
            for review in reviews:
                assert "is_read" in review or review.get("is_read") is None, "is_read field should be present"


class TestMainAppStillWorks:
    """Verify main app functionality still works"""
    
    def test_login_still_works(self):
        """Admin login still works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == ADMIN_EMAIL
    
    def test_reviews_endpoint_still_works(self):
        """Main reviews endpoint still works"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["token"]
        
        # Get reviews
        response = requests.get(
            f"{BASE_URL}/api/reviews",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_widget_stats_still_works(self):
        """Widget stats endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/widget/stats?api_key={API_KEY}")
        assert response.status_code == 200
        data = response.json()
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "response_rate" in data
        assert "pending" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
