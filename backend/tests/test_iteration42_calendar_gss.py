"""
Iteration 42 - Availability Calendar & Guest Satisfaction Score (GSS) Tests
Tests for:
1. GET /api/availability/calendar/{property_id} - Real-time availability calendar
2. GET /api/availability/calendar/{property_id}?month=YYYY-MM - Specific month
3. GET /api/availability/calendar/all - All properties aggregation
4. GET /api/gss/{property_id} - Guest Satisfaction Score
5. GET /api/gss/{property_id}?days=7 - GSS with period filter
6. GET /api/gss/all - All properties GSS aggregation
7. Auth requirements for both endpoints
8. Regression tests for existing endpoints
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthLogin:
    """Test admin login to get auth token"""
    
    def test_admin_login(self):
        """POST /api/auth/login - Admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@hotelbox.com",
            "password": "HotelAdmin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, f"Missing 'token' in response: {data.keys()}"
        assert data["role"] == "admin"
        print(f"✓ Admin login successful, role: {data['role']}")
        return data["token"]


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for authenticated requests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@hotelbox.com",
        "password": "HotelAdmin2026!"
    })
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Authentication failed")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestAvailabilityCalendar:
    """Tests for Availability Calendar endpoints"""
    
    def test_calendar_requires_auth(self):
        """GET /api/availability/calendar/{property_id} - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/availability/calendar/city-gate")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Calendar endpoint requires authentication (401 without token)")
    
    def test_calendar_single_property(self, auth_headers):
        """GET /api/availability/calendar/{property_id} - Single property calendar"""
        response = requests.get(
            f"{BASE_URL}/api/availability/calendar/city-gate",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "month" in data, "Missing 'month' field"
        assert "days_in_month" in data, "Missing 'days_in_month' field"
        assert "room_types" in data, "Missing 'room_types' field"
        assert "days" in data, "Missing 'days' field"
        assert "summary" in data, "Missing 'summary' field"
        
        # Validate summary structure
        summary = data["summary"]
        assert "avg_occupancy" in summary
        assert "peak_day" in summary
        assert "lowest_day" in summary
        assert "total_bookings" in summary
        
        print(f"✓ Calendar for city-gate: month={data['month']}, days={data['days_in_month']}, room_types={len(data['room_types'])}")
        print(f"  Summary: avg_occupancy={summary['avg_occupancy']}%, bookings={summary['total_bookings']}")
    
    def test_calendar_specific_month(self, auth_headers):
        """GET /api/availability/calendar/{property_id}?month=2026-02 - Specific month"""
        response = requests.get(
            f"{BASE_URL}/api/availability/calendar/city-gate?month=2026-02",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["month"] == "2026-02", f"Expected month 2026-02, got {data['month']}"
        assert data["days_in_month"] == 28, f"February 2026 should have 28 days, got {data['days_in_month']}"
        
        print(f"✓ Calendar for Feb 2026: {data['days_in_month']} days")
    
    def test_calendar_all_properties(self, auth_headers):
        """GET /api/availability/calendar/all - All properties aggregation"""
        response = requests.get(
            f"{BASE_URL}/api/availability/calendar/all",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "month" in data
        assert "room_types" in data
        assert "days" in data
        assert "summary" in data
        
        # All properties should have more room types
        print(f"✓ Calendar for ALL properties: {len(data['room_types'])} room types, {data['summary']['total_bookings']} bookings")
    
    def test_calendar_day_structure(self, auth_headers):
        """Validate day data structure in calendar"""
        response = requests.get(
            f"{BASE_URL}/api/availability/calendar/city-gate",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Get first day
        days = data["days"]
        assert len(days) > 0, "No days in calendar"
        
        first_day_key = sorted(days.keys())[0]
        day_data = days[first_day_key]
        
        # Validate day structure
        assert "date" in day_data
        assert "total_rooms" in day_data
        assert "occupied" in day_data
        assert "available" in day_data
        assert "occupancy_pct" in day_data
        assert "rooms" in day_data
        assert "bookings" in day_data
        assert "bookings_count" in day_data
        
        print(f"✓ Day structure valid: {first_day_key} - total={day_data['total_rooms']}, occupied={day_data['occupied']}, available={day_data['available']}")


class TestGuestSatisfactionScore:
    """Tests for GSS (Guest Satisfaction Score) endpoints"""
    
    def test_gss_requires_auth(self):
        """GET /api/gss/{property_id} - Requires authentication"""
        response = requests.get(f"{BASE_URL}/api/gss/city-gate")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GSS endpoint requires authentication (401 without token)")
    
    def test_gss_single_property(self, auth_headers):
        """GET /api/gss/{property_id} - Single property GSS"""
        response = requests.get(
            f"{BASE_URL}/api/gss/city-gate",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "gss" in data, "Missing 'gss' field"
        assert "gss_label" in data, "Missing 'gss_label' field"
        assert "trend" in data, "Missing 'trend' field"
        assert "period_days" in data, "Missing 'period_days' field"
        assert "components" in data, "Missing 'components' field"
        assert "reviews" in data, "Missing 'reviews' field"
        assert "messaging" in data, "Missing 'messaging' field"
        assert "response" in data, "Missing 'response' field"
        
        # Validate components
        components = data["components"]
        assert "review_score" in components
        assert "sentiment_score" in components
        assert "response_score" in components
        
        print(f"✓ GSS for city-gate: {data['gss']} ({data['gss_label']}), trend={data['trend']}")
        print(f"  Components: review={components['review_score']}, sentiment={components['sentiment_score']}, response={components['response_score']}")
    
    def test_gss_with_days_filter(self, auth_headers):
        """GET /api/gss/{property_id}?days=7 - GSS with period filter"""
        response = requests.get(
            f"{BASE_URL}/api/gss/city-gate?days=7",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["period_days"] == 7, f"Expected period_days=7, got {data['period_days']}"
        print(f"✓ GSS with 7-day filter: {data['gss']} ({data['gss_label']})")
    
    def test_gss_all_properties(self, auth_headers):
        """GET /api/gss/all - All properties GSS aggregation"""
        response = requests.get(
            f"{BASE_URL}/api/gss/all",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "gss" in data
        assert "gss_label" in data
        assert "components" in data
        assert "reviews" in data
        assert "messaging" in data
        
        print(f"✓ GSS for ALL properties: {data['gss']} ({data['gss_label']})")
        print(f"  Reviews: {data['reviews']['count']} reviews, avg={data['reviews']['avg_rating']}")
        print(f"  Messaging: {data['messaging']['total_conversations']} conversations")
    
    def test_gss_reviews_structure(self, auth_headers):
        """Validate reviews data structure in GSS"""
        response = requests.get(
            f"{BASE_URL}/api/gss/all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        reviews = data["reviews"]
        assert "avg_rating" in reviews
        assert "all_time_avg" in reviews
        assert "count" in reviews
        assert "distribution" in reviews
        
        # Validate distribution
        dist = reviews["distribution"]
        assert "5" in dist
        assert "4" in dist
        assert "3" in dist
        assert "2" in dist
        assert "1" in dist
        
        print(f"✓ Reviews structure valid: count={reviews['count']}, avg={reviews['avg_rating']}, all_time={reviews['all_time_avg']}")
    
    def test_gss_messaging_structure(self, auth_headers):
        """Validate messaging data structure in GSS"""
        response = requests.get(
            f"{BASE_URL}/api/gss/all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        messaging = data["messaging"]
        assert "total_conversations" in messaging
        assert "positive" in messaging
        assert "neutral" in messaging
        assert "negative" in messaging
        assert "resolved" in messaging
        assert "open" in messaging
        assert "resolution_rate" in messaging
        
        print(f"✓ Messaging structure valid: total={messaging['total_conversations']}, resolved={messaging['resolved']}, resolution_rate={messaging['resolution_rate']}%")


class TestRegressionEndpoints:
    """Regression tests for existing endpoints"""
    
    def test_reviews_endpoint(self, auth_headers):
        """GET /api/reviews - Still works after new features"""
        response = requests.get(
            f"{BASE_URL}/api/reviews",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Reviews endpoint failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/reviews working: {len(data)} reviews")
    
    def test_dashboard_overview(self, auth_headers):
        """GET /api/dashboard/overview/{property_id} - Still works"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/overview/city-gate",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Dashboard overview failed: {response.text}"
        data = response.json()
        assert "bookings" in data
        assert "messaging" in data
        assert "reviews" in data
        print(f"✓ GET /api/dashboard/overview working")
    
    def test_messaging_conversations(self, auth_headers):
        """GET /api/messaging/conversations/{property_id} - Still works"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/conversations/city-gate",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Messaging conversations failed: {response.text}"
        data = response.json()
        # Response can be a list or object with conversations key
        if isinstance(data, list):
            print(f"✓ GET /api/messaging/conversations working: {len(data)} conversations")
        else:
            assert "conversations" in data
            print(f"✓ GET /api/messaging/conversations working: {len(data['conversations'])} conversations")
    
    def test_room_types(self, auth_headers):
        """GET /api/room-types - Still works"""
        response = requests.get(
            f"{BASE_URL}/api/room-types",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Room types failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/room-types working: {len(data)} room types")
    
    def test_bookings(self, auth_headers):
        """GET /api/bookings - Still works"""
        response = requests.get(
            f"{BASE_URL}/api/bookings",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Bookings failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/bookings working: {len(data)} bookings")


class TestGSSLabels:
    """Test GSS label thresholds"""
    
    def test_gss_label_values(self, auth_headers):
        """Verify GSS label is one of expected values"""
        response = requests.get(
            f"{BASE_URL}/api/gss/all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        valid_labels = ["Exceptional", "Excellent", "Very Good", "Good", "Average", "Needs Improvement"]
        assert data["gss_label"] in valid_labels, f"Invalid GSS label: {data['gss_label']}"
        
        # Verify label matches score
        gss = data["gss"]
        label = data["gss_label"]
        
        if gss >= 90:
            assert label == "Exceptional"
        elif gss >= 80:
            assert label == "Excellent"
        elif gss >= 70:
            assert label == "Very Good"
        elif gss >= 60:
            assert label == "Good"
        elif gss >= 50:
            assert label == "Average"
        else:
            assert label == "Needs Improvement"
        
        print(f"✓ GSS label '{label}' matches score {gss}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
