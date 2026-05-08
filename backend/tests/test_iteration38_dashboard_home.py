"""
Iteration 38 - Dashboard Home API Tests
Tests the new dashboard overview endpoint and verifies all data aggregation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDashboardOverviewAPI:
    """Dashboard Overview endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for all tests"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_dashboard_overview_returns_200(self):
        """Test dashboard overview endpoint returns 200 for valid property"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Dashboard overview returns 200")
    
    def test_dashboard_overview_has_bookings_section(self):
        """Test dashboard overview contains bookings data"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        assert "bookings" in data, "Missing 'bookings' section"
        bookings = data["bookings"]
        
        # Verify all required booking fields
        required_fields = ["today_checkins", "today_checkouts", "current_guests", 
                          "tomorrow_checkins", "total", "total_rooms", "occupancy"]
        for field in required_fields:
            assert field in bookings, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(bookings["today_checkins"], int)
        assert isinstance(bookings["today_checkouts"], int)
        assert isinstance(bookings["current_guests"], int)
        assert isinstance(bookings["tomorrow_checkins"], int)
        assert isinstance(bookings["total"], int)
        assert isinstance(bookings["total_rooms"], int)
        assert isinstance(bookings["occupancy"], (int, float))
        
        print(f"PASS: Bookings section valid - {bookings['total']} total bookings, {bookings['tomorrow_checkins']} tomorrow check-ins")
    
    def test_dashboard_overview_has_revenue_section(self):
        """Test dashboard overview contains revenue data"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        assert "revenue" in data, "Missing 'revenue' section"
        revenue = data["revenue"]
        
        # Verify all required revenue fields
        required_fields = ["month_total", "month_bookings", "week_total", "week_bookings"]
        for field in required_fields:
            assert field in revenue, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(revenue["month_total"], (int, float))
        assert isinstance(revenue["month_bookings"], int)
        assert isinstance(revenue["week_total"], (int, float))
        assert isinstance(revenue["week_bookings"], int)
        
        print(f"PASS: Revenue section valid - £{revenue['month_total']} this month, £{revenue['week_total']} this week")
    
    def test_dashboard_overview_has_messaging_section(self):
        """Test dashboard overview contains messaging data"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        assert "messaging" in data, "Missing 'messaging' section"
        messaging = data["messaging"]
        
        # Verify all required messaging fields
        required_fields = ["unread", "open", "total"]
        for field in required_fields:
            assert field in messaging, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(messaging["unread"], int)
        assert isinstance(messaging["open"], int)
        assert isinstance(messaging["total"], int)
        
        print(f"PASS: Messaging section valid - {messaging['unread']} unread, {messaging['open']} open conversations")
    
    def test_dashboard_overview_has_reviews_section(self):
        """Test dashboard overview contains reviews data"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        assert "reviews" in data, "Missing 'reviews' section"
        reviews = data["reviews"]
        
        # Verify all required reviews fields
        required_fields = ["total", "pending", "avg_rating"]
        for field in required_fields:
            assert field in reviews, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(reviews["total"], int)
        assert isinstance(reviews["pending"], int)
        assert isinstance(reviews["avg_rating"], (int, float))
        
        print(f"PASS: Reviews section valid - {reviews['total']} total, avg rating {reviews['avg_rating']}")
    
    def test_dashboard_overview_has_automation_section(self):
        """Test dashboard overview contains automation data"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        assert "automation" in data, "Missing 'automation' section"
        automation = data["automation"]
        
        # Verify all required automation fields
        required_fields = ["sent_today", "failed_today"]
        for field in required_fields:
            assert field in automation, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(automation["sent_today"], int)
        assert isinstance(automation["failed_today"], int)
        
        print(f"PASS: Automation section valid - {automation['sent_today']} sent today, {automation['failed_today']} failed")
    
    def test_dashboard_overview_has_recent_activity(self):
        """Test dashboard overview contains recent activity arrays"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        assert "recent" in data, "Missing 'recent' section"
        recent = data["recent"]
        
        # Verify all required recent arrays
        required_arrays = ["bookings", "messages", "reviews"]
        for arr in required_arrays:
            assert arr in recent, f"Missing array: {arr}"
            assert isinstance(recent[arr], list), f"{arr} should be a list"
            assert len(recent[arr]) <= 5, f"{arr} should have max 5 items"
        
        print(f"PASS: Recent activity valid - {len(recent['bookings'])} bookings, {len(recent['messages'])} messages, {len(recent['reviews'])} reviews")
    
    def test_recent_bookings_structure(self):
        """Test recent bookings have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        if len(data["recent"]["bookings"]) > 0:
            booking = data["recent"]["bookings"][0]
            required_fields = ["guest_name", "booking_ref", "check_in", "check_out", "total_price"]
            for field in required_fields:
                assert field in booking, f"Recent booking missing field: {field}"
            print(f"PASS: Recent booking structure valid - {booking['guest_name']} (#{booking['booking_ref']})")
        else:
            print("PASS: No recent bookings to validate structure")
    
    def test_recent_messages_structure(self):
        """Test recent messages have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        if len(data["recent"]["messages"]) > 0:
            message = data["recent"]["messages"][0]
            required_fields = ["guest_name", "channel", "last_message_preview", "last_message_at"]
            for field in required_fields:
                assert field in message, f"Recent message missing field: {field}"
            print(f"PASS: Recent message structure valid - {message['guest_name']} via {message['channel']}")
        else:
            print("PASS: No recent messages to validate structure")
    
    def test_recent_reviews_structure(self):
        """Test recent reviews have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/aldgate-flats",
            headers=self.headers
        )
        data = response.json()
        
        if len(data["recent"]["reviews"]) > 0:
            review = data["recent"]["reviews"][0]
            required_fields = ["rating", "platform"]
            for field in required_fields:
                assert field in review, f"Recent review missing field: {field}"
            print(f"PASS: Recent review structure valid - {review.get('guest_name', 'Guest')} ({review['rating']} stars)")
        else:
            print("PASS: No recent reviews to validate structure")
    
    def test_dashboard_overview_all_properties(self):
        """Test dashboard overview with 'all' property_id aggregates all data"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/all",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should have all sections
        assert "bookings" in data
        assert "revenue" in data
        assert "messaging" in data
        assert "reviews" in data
        assert "automation" in data
        assert "recent" in data
        
        print(f"PASS: Dashboard overview 'all' works - {data['bookings']['total']} total bookings across all properties")
    
    def test_dashboard_overview_requires_auth(self):
        """Test dashboard overview requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/overview/aldgate-flats")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("PASS: Dashboard overview requires authentication")


class TestDashboardRegressionAPIs:
    """Regression tests for existing APIs that dashboard depends on"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token for all tests"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json()["token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_messaging_conversations_api(self):
        """Test messaging conversations API still works"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/conversations/aldgate-flats",
            headers=self.headers
        )
        assert response.status_code == 200
        print("PASS: Messaging conversations API working")
    
    def test_automation_rules_api(self):
        """Test automation rules API still works"""
        response = requests.get(
            f"{BASE_URL}/api/automation/rules/aldgate-flats",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Automation rules API working - {len(data)} rules")
    
    def test_reviews_api(self):
        """Test reviews API still works"""
        response = requests.get(
            f"{BASE_URL}/api/reviews",
            headers=self.headers
        )
        assert response.status_code == 200
        print("PASS: Reviews API working")
    
    def test_channel_settings_api(self):
        """Test channel settings API still works"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/channel-settings/aldgate-flats",
            headers=self.headers
        )
        assert response.status_code == 200
        print("PASS: Channel settings API working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
