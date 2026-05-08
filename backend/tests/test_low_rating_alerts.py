"""
Test Low-Rating Alert Features - Iteration 19
Tests:
- POST /api/reviews with rating 1-2 triggers send_negative_review_notification
- GET /api/widget/reviews/new returns reviews with rating field
- GET /api/notifications/log shows logged notifications for low-rating reviews
- Normal reviews (4-5 stars) don't trigger notifications
"""

import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_KEY = "rhk_17354979397db960bcb68db21ed42b7acc103e7940715667"
ADMIN_EMAIL = "admin@hotelbox.com"
ADMIN_PASSWORD = "HotelAdmin2026!"


class TestLowRatingAlerts:
    """Test low-rating alert backend functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get token
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()
    
    def test_admin_login(self):
        """Test admin login works"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        print("PASS: Admin login successful")
    
    def test_create_low_rating_review_triggers_notification(self):
        """Test POST /api/reviews with rating 1 triggers notification"""
        timestamp = datetime.now(timezone.utc).isoformat()
        review_data = {
            "platform": "google",
            "guest_name": f"TEST_LowRating_{timestamp[:19]}",
            "rating": 1,
            "review_text": "Absolutely terrible! The worst hotel experience ever. Dirty rooms, rude staff, broken AC.",
            "room_type": "Standard Room",
            "property_id": "default"
        }
        
        resp = self.session.post(f"{BASE_URL}/api/reviews", json=review_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] == 1
        review_id = data["id"]
        print(f"PASS: Created 1-star review with ID: {review_id}")
        
        # Check notification log for this review
        log_resp = self.session.get(f"{BASE_URL}/api/notifications/log")
        assert log_resp.status_code == 200
        logs = log_resp.json()
        
        # Find notification for our review
        found = any(log.get("review_id") == review_id for log in logs)
        assert found, f"Notification not found for review {review_id}"
        print(f"PASS: Notification logged for 1-star review")
    
    def test_create_2_star_review_triggers_notification(self):
        """Test POST /api/reviews with rating 2 triggers notification"""
        timestamp = datetime.now(timezone.utc).isoformat()
        review_data = {
            "platform": "tripadvisor",
            "guest_name": f"TEST_TwoStar_{timestamp[:19]}",
            "rating": 2,
            "review_text": "Very disappointing stay. Room was not clean and service was slow.",
            "room_type": "Deluxe Room",
            "property_id": "default"
        }
        
        resp = self.session.post(f"{BASE_URL}/api/reviews", json=review_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] == 2
        review_id = data["id"]
        print(f"PASS: Created 2-star review with ID: {review_id}")
        
        # Check notification log
        log_resp = self.session.get(f"{BASE_URL}/api/notifications/log")
        assert log_resp.status_code == 200
        logs = log_resp.json()
        found = any(log.get("review_id") == review_id for log in logs)
        assert found, f"Notification not found for 2-star review {review_id}"
        print(f"PASS: Notification logged for 2-star review")
    
    def test_high_rating_review_no_notification(self):
        """Test POST /api/reviews with rating 4-5 does NOT trigger notification"""
        timestamp = datetime.now(timezone.utc).isoformat()
        review_data = {
            "platform": "booking.com",
            "guest_name": f"TEST_HighRating_{timestamp[:19]}",
            "rating": 5,
            "review_text": "Wonderful stay! Excellent service and beautiful rooms.",
            "room_type": "Suite",
            "property_id": "default"
        }
        
        # Get current notification count
        log_resp_before = self.session.get(f"{BASE_URL}/api/notifications/log")
        count_before = len(log_resp_before.json())
        
        resp = self.session.post(f"{BASE_URL}/api/reviews", json=review_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] == 5
        review_id = data["id"]
        print(f"PASS: Created 5-star review with ID: {review_id}")
        
        # Check notification log - should NOT have new entry for this review
        log_resp_after = self.session.get(f"{BASE_URL}/api/notifications/log")
        logs = log_resp_after.json()
        found = any(log.get("review_id") == review_id for log in logs)
        assert not found, f"Notification should NOT be created for 5-star review"
        print(f"PASS: No notification for 5-star review (as expected)")
    
    def test_widget_reviews_new_returns_rating_field(self):
        """Test GET /api/widget/reviews/new returns reviews with rating field"""
        # First create a review
        timestamp = datetime.now(timezone.utc).isoformat()
        review_data = {
            "platform": "airbnb",
            "guest_name": f"TEST_WidgetRating_{timestamp[:19]}",
            "rating": 1,
            "review_text": "Terrible experience, would not recommend.",
            "property_id": "default"
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/reviews", json=review_data)
        assert create_resp.status_code == 200
        created_review = create_resp.json()
        
        # Get reviews from widget endpoint with since parameter
        since = "2020-01-01T00:00:00Z"
        widget_resp = requests.get(
            f"{BASE_URL}/api/widget/reviews/new?api_key={API_KEY}&property_id=default&since={since}"
        )
        assert widget_resp.status_code == 200
        reviews = widget_resp.json()
        
        # Find our review and verify rating field
        found_review = next((r for r in reviews if r["id"] == created_review["id"]), None)
        assert found_review is not None, "Created review not found in widget/reviews/new"
        assert "rating" in found_review, "Rating field missing from widget/reviews/new response"
        assert found_review["rating"] == 1
        print(f"PASS: Widget reviews/new returns rating field (rating={found_review['rating']})")
    
    def test_widget_reviews_returns_rating_field(self):
        """Test GET /api/widget/reviews returns reviews with rating field"""
        resp = requests.get(f"{BASE_URL}/api/widget/reviews?api_key={API_KEY}&limit=5")
        assert resp.status_code == 200
        reviews = resp.json()
        assert len(reviews) > 0, "No reviews returned"
        
        for review in reviews:
            assert "rating" in review, f"Rating field missing from review {review.get('id')}"
            assert isinstance(review["rating"], int), "Rating should be integer"
            assert 1 <= review["rating"] <= 5, f"Rating {review['rating']} out of range"
        
        print(f"PASS: Widget reviews endpoint returns rating field for all {len(reviews)} reviews")
    
    def test_notification_log_endpoint(self):
        """Test GET /api/notifications/log returns logged notifications"""
        resp = self.session.get(f"{BASE_URL}/api/notifications/log")
        assert resp.status_code == 200
        logs = resp.json()
        assert isinstance(logs, list), "Notification log should be a list"
        
        if len(logs) > 0:
            log = logs[0]
            assert "id" in log
            assert "review_id" in log
            assert "email" in log
            assert "status" in log
            assert "created_at" in log
            # Status should be demo_logged since Resend API key is not configured
            assert log["status"] in ["demo_logged", "sent", "failed"]
            print(f"PASS: Notification log has {len(logs)} entries with correct structure")
        else:
            print("PASS: Notification log endpoint works (empty)")
    
    def test_widget_stats_endpoint(self):
        """Test GET /api/widget/stats still works"""
        resp = requests.get(f"{BASE_URL}/api/widget/stats?api_key={API_KEY}")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_reviews" in data
        assert "average_rating" in data
        assert "response_rate" in data
        assert "pending" in data
        print(f"PASS: Widget stats: {data['total_reviews']} reviews, avg rating {data['average_rating']}")
    
    def test_widget_unread_count(self):
        """Test GET /api/widget/unread-count still works"""
        resp = requests.get(f"{BASE_URL}/api/widget/unread-count?api_key={API_KEY}")
        assert resp.status_code == 200
        data = resp.json()
        assert "unread" in data
        print(f"PASS: Widget unread count: {data['unread']}")
    
    def test_reviews_list_endpoint(self):
        """Test GET /api/reviews still works"""
        resp = self.session.get(f"{BASE_URL}/api/reviews?limit=5")
        assert resp.status_code == 200
        reviews = resp.json()
        assert isinstance(reviews, list)
        print(f"PASS: Reviews list endpoint returns {len(reviews)} reviews")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
